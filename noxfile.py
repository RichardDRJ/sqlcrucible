# /// script
# dependencies = [
#   "nox[uv] >= 2024.4.15"
# ]
# ///

import nox

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS = nox.project.python_versions(nox.project.load_toml("pyproject.toml"))
MIN_PYTHON_VERSION = SUPPORTED_PYTHON_VERSIONS[0]


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


@nox.session(python=SUPPORTED_PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    """Run tests with pytest."""
    uv("sync", "--group", "test", session=session)
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
