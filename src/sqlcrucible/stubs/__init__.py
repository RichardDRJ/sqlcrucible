"""Stub generator for SQLCrucible entities.

Generates type stubs that provide type checker support for SAType[Entity] access.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from sqlcrucible.entity.core import SQLCrucibleEntity
from sqlcrucible.stubs.codegen import (
    ClassDef,
    build_import_block,
    construct_sa_type_stub,
    generate_model_defs_for_entity,
    specificity_order,
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
    groups: dict[_K, list[_T]] = {}
    for it in iterable:
        groups.setdefault(key(it), []).append(it)
    return groups


_STUB_SUFFIX = "-stubs"


def _stub_path(root: Path, module_name: str) -> Path:
    """Map a dotted module to its file inside the ``<pkg>-stubs`` package.

    The generated stubs override and extend the ``sqlcrucible`` package, so they
    are emitted as a PEP 561 ``sqlcrucible-stubs`` partial stub package rather
    than a parallel ``sqlcrucible`` tree. Type checkers (ty, pyright) resolve a
    ``<pkg>-stubs`` package independently of the installed package, which a
    namespace tree in a separate search path no longer reliably does.
    """
    top, *parts = module_name.split(".")
    parts = [f"{top}{_STUB_SUFFIX}", *parts]
    return root.joinpath(*parts[:-1], f"{parts[-1]}.pyi")


def _real_package_init(module_name: str) -> str | None:
    """Return the source of a real package's ``__init__`` module, if it exists.

    Used to mirror re-exports into the stub package's ``__init__.pyi`` so the
    empty stub does not shadow the runtime package's public API.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ModuleNotFoundError, ValueError, ImportError):
        return None
    if spec is None or spec.submodule_search_locations is None or spec.origin is None:
        return None
    origin = Path(spec.origin)
    return origin.read_text() if origin.name == "__init__.py" else None


def _finalize_stub_package(output_dir: Path) -> None:
    """Mark each generated ``*-stubs`` tree as a PEP 561 partial stub package.

    Type checkers only treat a ``<pkg>-stubs`` directory as a stub package when
    every directory is an explicit package (has ``__init__.pyi``) and the
    distribution is flagged partial (``py.typed`` containing ``partial``) so
    modules absent from the stubs fall through to the runtime package. Each
    ``__init__.pyi`` mirrors the corresponding real package's ``__init__`` (when
    one exists) so the stub does not shadow the runtime package's exports.
    """
    for stub_package_dir in output_dir.glob(f"*{_STUB_SUFFIX}"):
        (stub_package_dir / "py.typed").write_text("partial\n")
        real_top = stub_package_dir.name[: -len(_STUB_SUFFIX)]
        directories = [stub_package_dir, *(p for p in stub_package_dir.rglob("*") if p.is_dir())]
        for directory in directories:
            init_file = directory / "__init__.pyi"
            if init_file.exists():
                continue
            module_name = ".".join((real_top, *directory.relative_to(stub_package_dir).parts))
            init_file.write_text(_real_package_init(module_name) or "")


def _write_to_stub_file(classdefs: list[ClassDef], stubs_root: Path, module_name: str):
    imports = [it for classdef in classdefs for it in classdef.imports]

    import_block = build_import_block(imports, module_name)
    class_block = "\n\n".join(it.class_def for it in classdefs)

    stub_path = _stub_path(stubs_root, module_name)
    stub_path.parent.mkdir(parents=True, exist_ok=True)

    with open(stub_path, "w") as fd:
        fd.write(import_block)
        fd.write("\n\n")
        fd.write(class_block)


def _generate_automodel_stubs(
    entities: list[type[SQLCrucibleEntity]],
    output_dir: Path,
) -> None:
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
    all_with_bases = specificity_order(all_entities)

    # Force automodel creation for all entities before generating stubs.
    # This populates the shared MetaData with all tables, allowing SQLAlchemy
    # to resolve foreign-key column types that reference other entities' tables.
    for entity in all_with_bases:
        _ = entity.__sqlalchemy_type__

    _generate_automodel_stubs(all_with_bases, output_path)

    _generate_sa_type_stub(all_entities, output_path)

    _finalize_stub_package(output_path)
