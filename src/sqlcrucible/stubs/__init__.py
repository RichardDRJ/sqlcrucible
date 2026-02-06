"""Stub generator for SQLCrucible entities.

Generates type stubs that provide type checker support for SAType[Entity] access.
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from sqlcrucible.stubs.codegen import ClassDef, build_import_block, generate_model_defs_for_entity
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


def generate_stubs_for_module(
    module_path: str,
    output_dir: Path,
):
    """Generate stub files for a module.

    Args:
        module_path: Dotted module path (e.g., 'myapp.models')
        output_dir: Root output directory for stubs.
    """
    entities = get_entities_from_module(module_path)
    if not entities:
        raise ValueError(f"No SQLCrucibleEntity subclasses found in {module_path}")

    all_classdefs = [
        classdef for entity in entities for classdef in generate_model_defs_for_entity(entity)
    ]
    classdefs_by_module = _group_by(all_classdefs, lambda it: it.module)
    for module, classdefs in classdefs_by_module.items():
        classdefs = list(_unique_by(classdefs, lambda it: it.source))
        _write_to_stub_file(classdefs, output_dir, module)


def generate_stubs(
    module_paths: list[str],
    output_dir: str = "stubs",
):
    """Generate stubs for multiple modules.

    Args:
        module_paths: List of dotted module paths.
        output_dir: Root output directory for stubs.
    """
    output_path = Path(output_dir)

    for module_path in module_paths:
        generate_stubs_for_module(module_path, output_path)
