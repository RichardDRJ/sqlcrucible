"""CLI entry point for stub generation.

Usage:
    python -m sqlcrucible.stubs myapp.models --output stubs/
"""

import argparse
import sys

from sqlcrucible.stubs import generate_stubs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate type stubs for SQLCrucible entities.",
        prog="python -m sqlcrucible.stubs",
    )
    parser.add_argument(
        "modules",
        nargs="+",
        help="Module paths to scan for entities (e.g., myapp.models)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="stubs",
        help="Output directory for generated stubs (default: stubs/)",
    )

    args = parser.parse_args()

    try:
        generate_stubs(args.modules, args.output)
        print(f"Generated stubs in {args.output}/:")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
