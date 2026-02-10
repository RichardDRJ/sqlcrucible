"""Shared infrastructure for stub type-checking tests."""

import json
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from sqlcrucible.stubs import generate_stubs


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not find project root (no pyproject.toml found)")


_PROJECT_ROOT = _find_project_root()

_SNIPPET_REGISTRY: dict[str, str] = {}


def _snippet_key(node: pytest.Function) -> str:
    assert node.parent is not None
    return f"{node.parent.nodeid}::{node.originalname}"


_DEFAULT_CHECKERS = ("pyright", "ty")


def typecheck(code: str, *, checkers: Sequence[str] = _DEFAULT_CHECKERS):
    """Declare a type-checking snippet for a test.

    The decorated test is parametrized over the given *checkers* and receives
    a ``typecheck_outcome`` fixture with the checker's verdict.
    """
    dedented = dedent(code)

    def decorator(fn):
        fn._typecheck_code = dedented
        return pytest.mark.parametrize("checker", checkers)(fn)

    return decorator


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if isinstance(item, pytest.Function) and hasattr(item.obj, "_typecheck_code"):
            key = _snippet_key(item)
            _SNIPPET_REGISTRY.setdefault(key, item.obj._typecheck_code)


@dataclass
class TypecheckOutcome:
    """Result of running a type checker on a code snippet."""

    checker: str
    returncode: int
    output: str

    def assert_ok(self) -> None:
        assert self.returncode == 0, f"{self.checker} failed:\n{self.output}"

    def assert_error(self) -> None:
        assert self.returncode != 0, f"{self.checker} should have reported errors"


@pytest.fixture(scope="session")
def stub_dir():
    """Generate stubs once for the entire test session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stub_path = Path(tmpdir)
        generate_stubs(["tests.stubs.sample_models"], output_dir=str(stub_path))
        yield stub_path


def _run_pyright_batch(
    snippets: dict[str, str],
    stub_dir: Path,
) -> dict[str, TypecheckOutcome]:
    if not snippets:
        return {}

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        (tmppath / "pyrightconfig.json").write_text(
            json.dumps(
                {
                    "stubPath": str(stub_dir),
                    "extraPaths": [str(_PROJECT_ROOT)],
                }
            )
        )

        key_to_filename: dict[str, str] = {}
        for i, (key, code) in enumerate(snippets.items()):
            filename = f"snippet_{i}.py"
            (tmppath / filename).write_text(code)
            key_to_filename[key] = filename

        proc = subprocess.run(
            ["pyright", "--outputjson"],
            cwd=tmppath,
            capture_output=True,
            text=True,
        )

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            output = proc.stdout + proc.stderr
            return {key: TypecheckOutcome("pyright", 1, output) for key in snippets}

        file_diagnostics: dict[str, list[str]] = {}
        file_has_error: dict[str, bool] = {}
        for diag in data.get("generalDiagnostics", []):
            fname = Path(diag["file"]).name
            line = diag.get("range", {}).get("start", {}).get("line", "?")
            severity = diag.get("severity", "error")
            msg = f"{severity}: {diag.get('message', '')} (line {line})"
            file_diagnostics.setdefault(fname, []).append(msg)
            if severity == "error":
                file_has_error[fname] = True

        return {
            key: TypecheckOutcome(
                "pyright",
                1 if file_has_error.get(filename, False) else 0,
                "\n".join(file_diagnostics.get(filename, [])),
            )
            for key, filename in key_to_filename.items()
        }


def _run_ty_batch(
    snippets: dict[str, str],
    stub_dir: Path,
) -> dict[str, TypecheckOutcome]:
    if not snippets:
        return {}

    results: dict[str, TypecheckOutcome] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        for i, (key, code) in enumerate(snippets.items()):
            filepath = tmppath / f"snippet_{i}.py"
            filepath.write_text(code)
            proc = subprocess.run(
                [
                    "ty",
                    "check",
                    str(filepath),
                    "--extra-search-path",
                    str(stub_dir),
                    "--extra-search-path",
                    str(_PROJECT_ROOT),
                ],
                capture_output=True,
                text=True,
            )
            results[key] = TypecheckOutcome("ty", proc.returncode, proc.stdout + proc.stderr)

    return results


@pytest.fixture(scope="session")
def _typecheck_batch(stub_dir):
    """Lazily run each type checker once on all collected snippets."""
    cache: dict[str, dict[str, TypecheckOutcome]] = {}

    def get(checker: str) -> dict[str, TypecheckOutcome]:
        if checker not in cache:
            if checker == "pyright":
                cache[checker] = _run_pyright_batch(_SNIPPET_REGISTRY, stub_dir)
            elif checker == "ty":
                cache[checker] = _run_ty_batch(_SNIPPET_REGISTRY, stub_dir)
            else:
                raise ValueError(f"Unknown checker: {checker}")
        return cache[checker]

    return get


@pytest.fixture
def typecheck_outcome(request: pytest.FixtureRequest, _typecheck_batch, checker: str):
    """Look up the type-check result for the current test and checker."""
    assert isinstance(request.node, pytest.Function)
    key = _snippet_key(request.node)
    batch = _typecheck_batch(checker)
    if key not in batch:
        pytest.fail(f"No typecheck snippet registered for {key}")
    return batch[key]
