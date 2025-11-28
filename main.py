#!/usr/bin/env python3
"""
Kubernetes Docset Generator for Dash.

This tool creates a Dash docset from Kubernetes documentation,
with improved semantic indexing for better search results.

Can either:
1. Scrape docs directly from kubernetes.io (--scrape)
2. Use an existing source docset (--source)
"""

import argparse
import sys
from pathlib import Path

from k8s_docset.builder import build_docset
from k8s_docset.scraper import scrape_kubernetes_docs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Dash docset for Kubernetes documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape docs from kubernetes.io and build docset (recommended)
  python main.py --scrape

  # Scrape and specify output directory
  python main.py --scrape --output ./output

  # Build from an existing source docset
  python main.py --source ~/Library/Application\\ Support/Dash/Docset\\ Generator/Kubernetes/Kubernetes.docset

  # Custom version
  python main.py --scrape --version 1.34
        """,
    )

    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Scrape documentation directly from kubernetes.io",
    )

    parser.add_argument(
        "--source",
        type=Path,
        help="Path to the source .docset directory (alternative to --scrape)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "output",
        help="Output directory for the generated docset (default: ./output)",
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

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.cwd() / ".cache" / "kubernetes-docs",
        help="Directory to cache scraped docs (default: .cache/kubernetes-docs)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.scrape and not args.source:
        print("Error: Either --scrape or --source must be provided", file=sys.stderr)
        print("Run 'python main.py --help' for usage examples", file=sys.stderr)
        return 1

    if args.scrape and args.source:
        print("Error: Cannot use both --scrape and --source", file=sys.stderr)
        return 1

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        # If scraping, download docs first
        if args.scrape:
            print("=" * 60)
            print("STEP 1: Scraping Kubernetes documentation")
            print("=" * 60)
            print()

            scrape_kubernetes_docs(output_dir=args.cache_dir, version=args.version)

            # Use the scraped content as source
            # Create a fake .docset structure with the scraped docs
            source_path = args.cache_dir / "Kubernetes.docset"
            source_path.mkdir(parents=True, exist_ok=True)

            # Create Contents/Resources directory
            resources_dir = source_path / "Contents" / "Resources" / "Documents"
            resources_dir.mkdir(parents=True, exist_ok=True)

            # Move scraped docs into the docset structure
            import shutil

            # Copy docs directory into Resources/Documents
            docs_dir = args.cache_dir / "docs"
            if docs_dir.exists():
                if (resources_dir / "docs").exists():
                    shutil.rmtree(resources_dir / "docs")
                shutil.copytree(docs_dir, resources_dir / "docs")

            # Copy static asset directories (CSS, JS, fonts, images, etc.)
            asset_dirs = ["scss", "css", "js", "fonts", "icons", "images"]
            for asset_dir in asset_dirs:
                asset_source = args.cache_dir / asset_dir
                if asset_source.exists():
                    asset_dest = resources_dir / asset_dir
                    if asset_dest.exists():
                        shutil.rmtree(asset_dest)
                    shutil.copytree(asset_source, asset_dest)

            print()
            print("=" * 60)
            print("STEP 2: Building Dash docset with enhanced indexing")
            print("=" * 60)
            print()

            source = source_path
        else:
            # Validate source path
            source = args.source
            if not source.exists():
                print(f"Error: Source docset not found: {source}", file=sys.stderr)
                return 1

            if not source.is_dir() or not source.suffix == ".docset":
                print(
                    f"Error: Source must be a .docset directory: {source}",
                    file=sys.stderr,
                )
                return 1

        # Build the docset
        docset_path = build_docset(
            source_docset_path=source,
            output_dir=args.output,
            docset_name=args.name,
            version=args.version,
        )

        print()
        print("=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"\nDocset created at: {docset_path}")
        print("\nTo install in Dash:")
        print("  1. Open Dash")
        print("  2. Go to Preferences > Docsets")
        print(f"  3. Click + and select '{docset_path}'")
        print("\nOr double-click the .docset file to install it.")
        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
