"""Stub generator for SQLCrucible entities.

Generates type stubs that provide type checker support for SAType[Entity] access.
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from sqlcrucible.entity.core import SQLCrucibleEntity
from sqlcrucible.stubs.codegen import (
    ClassDef,
    build_import_block,
    construct_sa_type_stub,
    generate_model_defs_for_entity,
    subclass_first,
)
from sqlcrucible.stubs.discovery import get_entities_from_module

_T = TypeVar("_T")
_K = TypeVar("_K")


def _unique_by(iterable: Iterable[_T], key: Callable[[_T], Any]) -> Iterable[_T]:
    seen: set[Any] = set()
    for entry in iterable:
        identifier = key(entry)
        if identifier not in seen:
            seen.add(identifier)
            yield entry


def _group_by(iterable: Iterable[_T], key: Callable[[_T], _K]) -> dict[_K, list[_T]]:
    return reduce(
        lambda acc, it: {**acc, key(it): [*acc.get(key(it), []), it]},
        iterable,
        {},
    )


def _stub_path(root: Path, module_name: str) -> Path:
    module_parts = module_name.split(".")
    return root.joinpath(
        *module_parts[:-1],
        f"{module_parts[-1]}.pyi",
    )


def _package_exists_in_source(package_name: str) -> bool:
    """Check if a package exists in the source (not just as a stub)."""
    import importlib.util

    try:
        spec = importlib.util.find_spec(package_name)
        return spec is not None and spec.submodule_search_locations is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _write_to_stub_file(classdefs: list[ClassDef], stubs_root: Path, module_name: str):
    imports = [it for classdef in classdefs for it in classdef.imports]

    import_block = build_import_block(imports, module_name)
    class_block = "\n\n".join(it.class_def for it in classdefs)

    stub_path = _stub_path(stubs_root, module_name)
    stub_path.parent.mkdir(parents=True, exist_ok=True)

    # Create __init__.pyi files in parent directories that don't exist in source.
    # For packages that exist in source, we use namespace packages (no __init__.pyi)
    # so type checkers can merge stubs with the real source.
    current = stubs_root
    package_path = ""
    for part in module_name.split(".")[:-1]:
        current = current / part
        package_path = f"{package_path}.{part}" if package_path else part
        init_file = current / "__init__.pyi"
        if not init_file.exists() and not _package_exists_in_source(package_path):
            init_file.touch()

    with open(stub_path, "w") as fd:
        fd.write(import_block)
        fd.write("\n\n")
        fd.write(class_block)


def _generate_automodel_stubs(
    entities: list[type[SQLCrucibleEntity]],
    output_dir: Path,
):
    all_classdefs = [
        classdef for entity in entities for classdef in generate_model_defs_for_entity(entity)
    ]
    classdefs_by_module = _group_by(all_classdefs, lambda it: it.module)
    for module, classdefs in classdefs_by_module.items():
        classdefs = list(_unique_by(classdefs, lambda it: it.source))
        _write_to_stub_file(classdefs, output_dir, module)


def _generate_sa_type_stub(entities: list[type[SQLCrucibleEntity]], output_dir: Path) -> None:
    sa_type_stub = construct_sa_type_stub(entities)
    sa_type_path = _stub_path(output_dir, "sqlcrucible.entity.sa_type")
    sa_type_path.parent.mkdir(parents=True, exist_ok=True)
    sa_type_path.write_text(sa_type_stub)


def generate_stubs(
    module_paths: list[str],
    output_dir: str = "stubs",
):
    """Generate stubs for one or more modules.

    Discovers all entities across all modules before generating stubs.
    This ensures automodels (and their backing tables) are all created
    first, so foreign-key column types can be resolved when the tables
    they reference share the same MetaData.

    Args:
        module_paths: List of dotted module paths.
        output_dir: Root output directory for stubs.
    """
    output_path = Path(output_dir)

    entities_by_module = {
        module_path: get_entities_from_module(module_path) for module_path in module_paths
    }
    modules_without_entities = [
        module_path for module_path, entities in entities_by_module.items() if not entities
    ]
    if modules_without_entities:
        raise ValueError(
            f"No SQLCrucibleEntity subclasses found in modules: {modules_without_entities}"
        )

    all_entities = [entity for entities in entities_by_module.values() for entity in entities]

    # Expand to include base classes (SQLCrucibleBaseModel, etc.) that
    # will appear in SAType overloads, so their automodel stubs are generated too.
    all_with_bases = subclass_first(all_entities)

    # Force automodel creation for all entities before generating stubs.
    # This populates the shared MetaData with all tables, allowing SQLAlchemy
    # to resolve foreign-key column types that reference other entities' tables.
    for entity in all_with_bases:
        _ = entity.__sqlalchemy_type__

    _generate_automodel_stubs(all_with_bases, output_path)

    _generate_sa_type_stub(all_entities, output_path)
