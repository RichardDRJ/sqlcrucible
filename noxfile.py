# /// script
# dependencies = [
#   "nox[uv] >= 2024.4.15"
# ]
# ///

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True

SUPPORTED_PYTHON_VERSIONS = nox.project.python_versions(nox.project.load_toml("pyproject.toml"))
MIN_PYTHON_VERSION = SUPPORTED_PYTHON_VERSIONS[0]
PYDANTIC_VERSIONS = ["2.10", "2.11", "2.12"]
PYDANTIC_MAX_PYTHON: dict[str, str] = {
    "2.10": "3.13",
    "2.11": "3.13",
}
_TEST_MATRIX = [
    (python, pydantic)
    for python in SUPPORTED_PYTHON_VERSIONS
    for pydantic in PYDANTIC_VERSIONS
    if pydantic not in PYDANTIC_MAX_PYTHON or python <= PYDANTIC_MAX_PYTHON[pydantic]
]


def uv(*args: str, session: nox.Session) -> None:
    session.run_install(
        "uv",
        *args,
        *(["--python", str(session.python)] if session.python else []),
        "--quiet",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session(python=MIN_PYTHON_VERSION)
@nox.parametrize("typechecker", ["ty", "pyright"])
def typecheck(session: nox.Session, typechecker: str) -> None:
    """Run type checkers."""

    uv("sync", "--group", "typecheck", session=session)

    match typechecker:
        case "ty":
            session.run("ty", "check", "src", "tests")
        case "pyright":
            session.run("pyright", "src", "tests")
        case _:
            raise RuntimeError(f"Unsupported type checker: {typechecker}")


@nox.session(python=MIN_PYTHON_VERSION)
def check(session: nox.Session) -> None:
    """Check linting/formatting with ruff."""
    uv("sync", "--group", "lint", session=session)
    session.run("ruff", "format", "--check", "src", "tests")
    session.run("ruff", "check", "src", "tests")


@nox.session(python=MIN_PYTHON_VERSION, default=False)
def fix(session: nox.Session) -> None:
    """Auto-fix lint and format errors with ruff."""
    uv("sync", "--group", "lint", session=session)
    session.run("ruff", "check", "--fix", "src", "tests")
    session.run("ruff", "format", "src", "tests")


@nox.session(python=MIN_PYTHON_VERSION)
def depcheck(session: nox.Session) -> None:
    """Check for missing/unused dependencies with deptry."""
    uv("sync", "--group", "depcheck", session=session)
    session.run("deptry", "src", "tests")


@nox.session
@nox.parametrize(("python", "pydantic"), _TEST_MATRIX)
def test(session: nox.Session, pydantic: str) -> None:
    """Run tests with pytest."""
    uv("sync", "--group", "test", session=session)
    session.install(f"pydantic~={pydantic}.0")
    session.run("pytest", *session.posargs)


@nox.session(python=MIN_PYTHON_VERSION)
def coverage(session: nox.Session) -> None:
    """Run tests with coverage reporting."""
    uv("sync", "--group", "test", session=session)
    session.run(
        "pytest",
        "--cov",
        "--cov-report=term-missing",
        "--cov-report=html",
        *session.posargs,
    )


@nox.session(python=MIN_PYTHON_VERSION, default=False)
def docs(session: nox.Session) -> None:
    """Build and serve documentation locally."""
    uv("sync", "--group", "docs", session=session)
    session.run("mkdocs", "serve")
