#!/usr/bin/env python3
"""Prepare and optionally submit a Dash docset contribution."""

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def create_archive(docset_path: Path, output_path: Path) -> None:
    """Create a .tgz archive of the docset."""
    print(f"Creating archive: {output_path}")
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(docset_path, arcname=docset_path.name)
    print(f"  Created {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")


def prepare_contribution(
    docset_path: Path,
    contrib_repo: Path,
    docset_name: str,
    version: str,
) -> Path:
    """Prepare files for Dash contribution."""
    docset_dir = contrib_repo / "docsets" / docset_name
    docset_dir.mkdir(parents=True, exist_ok=True)

    # Create archive
    archive_path = docset_dir / f"{docset_name}.tgz"
    create_archive(docset_path, archive_path)

    # Copy icons
    for icon_name in ["icon.png", "icon@2x.png"]:
        src = docset_path / icon_name
        if src.exists():
            shutil.copy(src, docset_dir / icon_name)
            print(f"  Copied {icon_name}")

    # Create/update docset.json
    docset_json_path = docset_dir / "docset.json"
    if docset_json_path.exists():
        with open(docset_json_path) as f:
            docset_json = json.load(f)
        docset_json["version"] = version
    else:
        docset_json = {
            "name": docset_name,
            "version": version,
            "archive": f"{docset_name}.tgz",
            "author": {
                "name": "Ismar Iljazovic",
                "link": "https://github.com/ichoosetoaccept",
            },
            "aliases": [docset_name.lower()],
        }

    with open(docset_json_path, "w") as f:
        json.dump(docset_json, f, indent=4)
    print(f"  Updated docset.json (version: {version})")

    # Create README if it doesn't exist
    readme_path = docset_dir / "README.md"
    if not readme_path.exists():
        readme_content = f"""# {docset_name} Docset

Dash docset for [{docset_name}](https://kubernetes.io/docs/) documentation.

## Author

[Ismar Iljazovic](https://github.com/ichoosetoaccept)

## Generation

Generated using [kubernetes-docset](https://github.com/ichoosetoaccept/kubernetes-docset).

```bash
git clone https://github.com/ichoosetoaccept/kubernetes-docset.git
cd kubernetes-docset
uv sync
poe all
```
"""
        readme_path.write_text(readme_content)
        print("  Created README.md")

    return docset_dir


def submit_pr(contrib_repo: Path, docset_name: str, version: str) -> None:
    """Create a branch, commit, push, and open a PR."""
    branch_name = f"{docset_name.lower()}-v{version.replace('/', '-')}"

    # Fetch upstream
    subprocess.run(["git", "fetch", "upstream"], cwd=contrib_repo, check=True)

    # Create branch from upstream/master
    subprocess.run(
        ["git", "checkout", "-B", branch_name, "upstream/master"],
        cwd=contrib_repo,
        check=True,
    )

    # Add and commit
    subprocess.run(["git", "add", f"docsets/{docset_name}"], cwd=contrib_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Add/Update {docset_name} docset to {version}"],
        cwd=contrib_repo,
        check=True,
    )

    # Push
    subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=contrib_repo, check=True)

    # Create PR
    subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            "Kapeli/Dash-User-Contributions",
            "--title",
            f"Add/Update {docset_name} docset to {version}",
            "--body",
            f"Adds/updates the {docset_name} docset.\n\nGenerated using https://github.com/ichoosetoaccept/kubernetes-docset",
        ],
        cwd=contrib_repo,
        check=True,
    )


def update_pr(
    contrib_repo: Path,
    docset_name: str,
    branch_name: str,
    version: str,
    docset_path: Path,
) -> None:
    """Update an existing PR branch with new files.

    Note: This should be called BEFORE prepare_contribution, as it will
    checkout the branch first, then prepare files on that branch.
    """
    # Fetch and checkout existing branch
    subprocess.run(["git", "fetch", "origin"], cwd=contrib_repo, check=True)

    # Reset any local changes first
    subprocess.run(
        ["git", "checkout", "--", "."],
        cwd=contrib_repo,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clean", "-fd", f"docsets/{docset_name}"],
        cwd=contrib_repo,
        capture_output=True,
    )

    subprocess.run(
        ["git", "checkout", branch_name],
        cwd=contrib_repo,
        check=True,
    )

    # Now prepare files on this branch
    prepare_contribution(docset_path, contrib_repo, docset_name, version)

    # Add and commit
    subprocess.run(["git", "add", f"docsets/{docset_name}"], cwd=contrib_repo, check=True)
    result = subprocess.run(
        ["git", "commit", "--amend", "-m", f"Update {docset_name} docset to {version}"],
        cwd=contrib_repo,
    )
    if result.returncode != 0:
        # No changes to amend, try regular commit
        subprocess.run(
            ["git", "commit", "-m", f"Update {docset_name} docset to {version}"],
            cwd=contrib_repo,
            check=True,
        )

    # Force push to update PR
    subprocess.run(["git", "push", "--force-with-lease"], cwd=contrib_repo, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Dash docset contribution")
    parser.add_argument(
        "--docset",
        type=Path,
        default=Path("output/Kubernetes.docset"),
        help="Path to the .docset directory",
    )
    parser.add_argument(
        "--contrib-repo",
        type=Path,
        default=Path.home() / "repos" / "Dash-User-Contributions",
        help="Path to Dash-User-Contributions repo",
    )
    parser.add_argument(
        "--name",
        default="Kubernetes",
        help="Docset name",
    )
    parser.add_argument(
        "--version",
        default="1.34",
        help="Docset version",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Also create and submit a PR",
    )
    parser.add_argument(
        "--update",
        type=str,
        metavar="BRANCH",
        help="Update existing PR branch instead of creating new one",
    )

    args = parser.parse_args()

    if not args.docset.exists():
        print(f"Error: Docset not found at {args.docset}")
        print("Run 'poe build' first to create the docset.")
        return 1

    if not args.contrib_repo.exists():
        print(f"Error: Dash-User-Contributions repo not found at {args.contrib_repo}")
        print("Clone it first: git clone https://github.com/Kapeli/Dash-User-Contributions.git")
        return 1

    if args.update:
        # Update handles prepare internally (needs to checkout branch first)
        print(f"Updating existing PR branch: {args.update}")
        update_pr(
            args.contrib_repo,
            args.name,
            args.update,
            args.version,
            args.docset,
        )
        print("\nPR updated!")
        return 0

    print(f"Preparing {args.name} docset contribution...")
    docset_dir = prepare_contribution(
        args.docset,
        args.contrib_repo,
        args.name,
        args.version,
    )
    print(f"\nFiles prepared in: {docset_dir}")

    if args.submit:
        print("\nSubmitting PR...")
        submit_pr(args.contrib_repo, args.name, args.version)
        print("\nPR submitted!")
    else:
        print("\nTo submit, run with --submit flag or manually:")
        print(f"  cd {args.contrib_repo}")
        print(f"  git checkout -b {args.name.lower()}-v{args.version}")
        print(f"  git add docsets/{args.name}")
        print(f'  git commit -m "Add {args.name} docset"')
        print("  git push origin HEAD")
        print("  gh pr create --repo Kapeli/Dash-User-Contributions")

    return 0


if __name__ == "__main__":
    sys.exit(main())
