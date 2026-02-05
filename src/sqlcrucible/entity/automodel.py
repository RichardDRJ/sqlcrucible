from __future__ import annotations

import sys
from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec
from typing import Any, get_args, get_origin

import sqlalchemy.orm
from sqlalchemy.orm.attributes import Mapped

from sqlcrucible.entity.core import SQLAlchemyBase, SQLCrucibleEntity
from sqlcrucible.entity.field_metadata import SQLAlchemyFieldDefinition
from sqlcrucible.utils.types.forward_refs import resolve_forward_refs
from sqlcrucible.utils.types.transformer import (
    TypeTransformerChain,
    TypeTransformer,
    TypeTransformerResult,
)


class SQLCrucibleEntityTransformer(TypeTransformer):
    """Transforms SQLCrucibleEntity types to their SQLAlchemy automodel types.

    Eagerly accesses __sqlalchemy_type__ to ensure the target automodel exists
    before the referencing class is created, which is required for SQLAlchemy
    mapper configuration. Falls back to string forward refs when a cycle is
    detected to support back_populates.
    """

    def matches(self, annotation: Any) -> bool:
        return isinstance(annotation, type) and issubclass(annotation, SQLCrucibleEntity)

    def apply(
        self,
        annotation: type[SQLCrucibleEntity],
        chain: TypeTransformerChain,
    ) -> TypeTransformerResult:
        # Check if this entity is currently being created (cycle detection)
        if annotation in auto_sqlalchemy_model_factory._creating:
            # We're in a cycle - use a forward ref to break it
            qualname = f"{annotation.__module__}.{annotation.__name__}"
            top_level = annotation.__module__.split(".")[0]
            return TypeTransformerResult(
                result=f"{qualname}.__sqlalchemy_type__",
                additional_globals={top_level: sys.modules[top_level]},
            )

        # No cycle - eagerly access to ensure target automodel exists first
        sa_type = annotation.__sqlalchemy_type__
        return TypeTransformerResult(result=sa_type)


field_transformer_chain = TypeTransformerChain(
    transformers=[
        SQLCrucibleEntityTransformer(),
        *TypeTransformerChain.DEFAULT_TRANSFORMERS,
    ]
)


def _public_fields(it: dict[str, Any]) -> dict[str, Any]:
    if "__all__" in it:
        names = it["__all__"]
    else:
        names = [name for name in it if not name.startswith("_")]
    return {name: it[name] for name in names}


def _create_automodel(source: type[SQLCrucibleEntity]) -> type[Any]:
    """Create a SQLAlchemy automodel class for an entity.

    Field types referencing other entities are transformed to their SQLAlchemy
    types. Referenced automodels are eagerly created to ensure they exist before
    mapper configuration, except when a cycle is detected (in which case string
    forward refs are used to break the cycle).
    """
    params = vars(source).get("__sqlalchemy_params__", {})
    base = _get_sa_base(source)

    field_defs = source.__sqlalchemy_field_definitions__().values()

    # Determine which fields need type annotations based on SQLAlchemy's Mapped type.
    # Mapped represents attributes instrumented by the Mapper (columns, relationships),
    # which require annotations for SQLAlchemy to configure them. Non-Mapped descriptors
    # like hybrid_property and association_proxy are extensions that provide their own
    # functionality without mapper instrumentation, so they only need class attributes.
    def needs_annotation(f: SQLAlchemyFieldDefinition) -> bool:
        return f.mapped_attr is None or isinstance(f.mapped_attr, Mapped)

    annotated_field_defs = [f for f in field_defs if needs_annotation(f)]

    # All fields with mapped_attr become class attributes (mapped_column, relationship, etc.)
    field_defaults = {f.mapped_name: f.mapped_attr for f in field_defs if f.mapped_attr is not None}

    # Transform field types for annotations (columns and relationships, but not computed descriptors)
    field_transform_results = {
        field_def.mapped_name: _transform_field_type(source, field_def)
        for field_def in annotated_field_defs
    }

    annotations = {key: it.result for key, it in field_transform_results.items()}
    additional_globals = {
        key: value
        for it in field_transform_results.values()
        for key, value in it.additional_globals.items()
    }

    namespace = {
        **field_defaults,
        **params,
        "__annotations__": annotations,
    }

    automodel_name = f"{source.__name__}AutoModel"
    target_module_name = f"sqlcrucible.generated.{source.__module__}"

    result = type(automodel_name, (base,), namespace)

    source_module = sys.modules[source.__module__]

    # Create or reuse the generated module
    if target_module_name in sys.modules:
        target_module = sys.modules[target_module_name]
    else:
        target_module = module_from_spec(ModuleSpec(target_module_name, loader=None))
        sys.modules[target_module_name] = target_module

    # Populate the generated module's namespace so string forward refs can be resolved.
    # This includes the source module's symbols, the source class's symbols, and any
    # additional globals needed to resolve cycle-breaking forward refs.
    target_module.__dict__.update(_public_fields(source_module.__dict__))
    target_module.__dict__.update(source.__dict__)
    target_module.__dict__.update(additional_globals)
    target_module.__dict__[automodel_name] = result
    result.__module__ = target_module_name

    return result


def _get_sa_base(annotation: type[SQLCrucibleEntity]) -> type[Any]:
    if explicit_base := vars(annotation).get("__sqlalchemy_base__"):
        return explicit_base
    return next(
        (
            it.__sqlalchemy_type__
            for it in annotation.__mro__[1:]
            if issubclass(it, SQLCrucibleEntity)
        ),
        SQLAlchemyBase,
    )


def _transform_field_type(
    owner: type[SQLCrucibleEntity],
    field_def: SQLAlchemyFieldDefinition,
) -> TypeTransformerResult:
    # Resolve any forward references in the source type first
    resolved_tp = resolve_forward_refs(field_def.source_tp, owner)

    match (get_origin(resolved_tp), get_args(resolved_tp)):
        case (sqlalchemy.orm.Mapped, _):
            return TypeTransformerResult(result=resolved_tp)
        case _:
            inner = field_transformer_chain.apply(resolved_tp)
            return TypeTransformerResult(
                result=Mapped[inner.result],
                additional_globals=inner.additional_globals,
            )


class AutoSQLAlchemyModelFactory:
    def __init__(self):
        self._cache: dict[type[SQLCrucibleEntity], type[Any]] = {}
        self._creating: set[type[SQLCrucibleEntity]] = set()

    def __call__(self, source: type[SQLCrucibleEntity]) -> type[Any]:
        """Generate or retrieve cached SQLAlchemy model for an entity class.

        Uses cycle detection to support circular relationships (back_populates).
        When creating an automodel, if a field references another entity that's
        not in a cycle, that entity's automodel is eagerly created first.
        For cycles, string forward refs are used instead.

        Args:
            source: The SQLCrucibleEntity subclass to generate a model for.

        Returns:
            The generated SQLAlchemy model class.
        """
        if source in self._cache:
            return self._cache[source]

        # Mark that we're creating this automodel (for cycle detection)
        self._creating.add(source)
        try:
            result = _create_automodel(source)
            self._cache[source] = result
            return result
        finally:
            self._creating.discard(source)


auto_sqlalchemy_model_factory = AutoSQLAlchemyModelFactory()
