"""Shared infrastructure for stub type-checking tests."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from sqlcrucible.stubs import generate_stubs


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not find project root (no pyproject.toml found)")


_PROJECT_ROOT = _find_project_root()


def run_typechecker(
    checker: str,
    code: str,
    stub_dir: Path,
) -> tuple[int, str]:
    """Run a type checker on code string with stubs configured.

    Args:
        checker: Type checker to use ("pyright" or "ty")
        code: Python code to check
        stub_dir: Path to generated stubs
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        test_file = tmppath / "test_code.py"
        test_file.write_text(code)

        if checker == "pyright":
            config = tmppath / "pyrightconfig.json"
            config_data: dict = {
                "stubPath": str(stub_dir),
                "extraPaths": [str(_PROJECT_ROOT)],
            }
            config.write_text(json.dumps(config_data))
            cmd = ["pyright", str(test_file)]
        elif checker == "ty":
            # Stubs searched first so SAType overloads take priority over source.
            # Project root searched second so test entity modules are resolvable.
            cmd = ["ty", "check", str(test_file)]
            cmd.extend(["--extra-search-path", str(stub_dir)])
            cmd.extend(["--extra-search-path", str(_PROJECT_ROOT)])
        else:
            raise ValueError(f"Unknown checker: {checker}")

        result = subprocess.run(cmd, cwd=tmppath, capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr


@pytest.fixture(scope="module")
def stub_dir():
    """Generate stubs once per test module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stub_path = Path(tmpdir)
        generate_stubs(["tests.stubs.sample_models"], output_dir=str(stub_path))
        yield stub_path
