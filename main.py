#!/usr/bin/env python3
"""
Kubernetes Docset Generator for Dash.

This tool creates a Dash docset from existing Kubernetes documentation,
with improved semantic indexing for better search results.
"""

import argparse
import sys
from pathlib import Path

from k8s_docset.builder import build_docset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Dash docset for Kubernetes documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build from the Dash-generated docset
  python main.py --source ~/Library/Application\\ Support/Dash/Docset\\ Generator/Kubernetes/Kubernetes.docset

  # Specify output directory
  python main.py --source /path/to/source.docset --output ./output

  # Custom version
  python main.py --source /path/to/source.docset --version 1.34
        """,
    )

    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the source .docset directory (from Dash's docset generator)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd(),
        help="Output directory for the generated docset (default: current directory)",
    )

    parser.add_argument(
        "--name",
        default="Kubernetes",
        help="Name for the docset (default: Kubernetes)",
    )

    parser.add_argument(
        "--version",
        default="1.34",
        help="Kubernetes version (default: 1.34)",
    )

    args = parser.parse_args()

    # Validate source path
    if not args.source.exists():
        print(f"Error: Source docset not found: {args.source}", file=sys.stderr)
        return 1

    if not args.source.is_dir() or not args.source.suffix == ".docset":
        print(f"Error: Source must be a .docset directory: {args.source}", file=sys.stderr)
        return 1

    # Create output directory if needed
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        docset_path = build_docset(
            source_docset_path=args.source,
            output_dir=args.output,
            docset_name=args.name,
            version=args.version,
        )
        print(f"\nSuccess! Docset created at: {docset_path}")
        print("\nTo install in Dash:")
        print(f"  1. Open Dash")
        print(f"  2. Go to Preferences > Docsets")
        print(f"  3. Click + and select '{docset_path}'")
        print(f"\nOr double-click the .docset file to install it.")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
