#!/usr/bin/env python3
"""Verify docset meets Dash contribution requirements.

Based on: https://github.com/Kapeli/Dash-User-Contributions/wiki/Docset-Contribution-Checklist
"""

import argparse
import plistlib
import re
import sqlite3
import sys
from pathlib import Path


class ContributionChecker:
    """Check docset against Dash contribution requirements."""

    def __init__(self, docset_path: Path, verbose: bool = False):
        self.docset_path = docset_path
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

        self.contents_dir = docset_path / "Contents"
        self.resources_dir = self.contents_dir / "Resources"
        self.documents_dir = self.resources_dir / "Documents"
        self.plist_path = self.contents_dir / "Info.plist"
        self.db_path = self.resources_dir / "docSet.dsidx"

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        if self.verbose:
            print(f"  ❌ {msg}")

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)
        if self.verbose:
            print(f"  ⚠️  {msg}")

    def success(self, msg: str) -> None:
        self.passed.append(msg)
        if self.verbose:
            print(f"  ✅ {msg}")

    def check_structure(self) -> None:
        """Check basic docset structure exists."""
        print("\n📁 Checking docset structure...")

        if not self.docset_path.exists():
            self.error(f"Docset not found: {self.docset_path}")
            return

        if not self.docset_path.suffix == ".docset":
            self.error("Docset must have .docset extension")

        for required in [self.contents_dir, self.resources_dir, self.documents_dir]:
            if required.exists():
                self.success(f"{required.name}/ exists")
            else:
                self.error(f"Missing required directory: {required.name}/")

        if self.plist_path.exists():
            self.success("Info.plist exists")
        else:
            self.error("Missing Info.plist")

        if self.db_path.exists():
            self.success("docSet.dsidx exists")
        else:
            self.error("Missing docSet.dsidx")

    def check_plist(self) -> None:
        """Check Info.plist requirements."""
        print("\n📋 Checking Info.plist...")

        if not self.plist_path.exists():
            return

        with open(self.plist_path, "rb") as f:
            plist = plistlib.load(f)

        # Required keys
        required_keys = ["CFBundleIdentifier", "CFBundleName", "DocSetPlatformFamily", "isDashDocset"]
        for key in required_keys:
            if key in plist:
                self.success(f"Has {key}: {plist[key]}")
            else:
                self.error(f"Missing required key: {key}")

        # Check no version in bundle name (requirement)
        bundle_name = plist.get("CFBundleName", "")
        if re.search(r"\d+\.\d+", bundle_name):
            self.warning(f"Bundle name should not contain version: {bundle_name}")
        else:
            self.success("Bundle name has no version number")

        # Check for index page (recommended)
        if "dashIndexFilePath" in plist:
            index_path = self.documents_dir / plist["dashIndexFilePath"]
            if index_path.exists():
                self.success(f"Index page set: {plist['dashIndexFilePath']}")
            else:
                self.warning(f"Index page path doesn't exist: {plist['dashIndexFilePath']}")
        else:
            self.warning("No index page set (dashIndexFilePath)")

        # Check for TOC support (recommended)
        if plist.get("DashDocSetFamily") == "dashtoc":
            self.success("Table of contents support enabled")
        else:
            self.warning("No table of contents support (DashDocSetFamily: dashtoc)")

    def check_icons(self) -> None:
        """Check icon requirements."""
        print("\n🎨 Checking icons...")

        icon_16 = self.docset_path / "icon.png"
        icon_32 = self.docset_path / "icon@2x.png"

        if icon_16.exists():
            self.success("icon.png exists")
        else:
            self.warning("Missing icon.png (16x16) - recommended")

        if icon_32.exists():
            self.success("icon@2x.png exists")
        else:
            self.warning("Missing icon@2x.png (32x32) - recommended")

    def check_index(self) -> None:
        """Check search index requirements."""
        print("\n🔍 Checking search index...")

        if not self.db_path.exists():
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check for empty entries
            cursor.execute("SELECT COUNT(*) FROM searchIndex WHERE name = '' OR name IS NULL")
            empty_count = cursor.fetchone()[0]
            if empty_count > 0:
                self.error(f"Index contains {empty_count} empty entries")
            else:
                self.success("No empty entries in index")

            # Check for entries with newlines
            cursor.execute("SELECT COUNT(*) FROM searchIndex WHERE name LIKE '%\n%'")
            newline_count = cursor.fetchone()[0]
            if newline_count > 0:
                self.error(f"Index contains {newline_count} entries with newlines")
            else:
                self.success("No entries with newlines")

            # Check for broken paths (sample)
            cursor.execute("SELECT path FROM searchIndex ORDER BY RANDOM() LIMIT 20")
            paths = cursor.fetchall()
            broken_paths = 0
            for (path,) in paths:
                file_path = path.split("#")[0]  # Remove anchor
                full_path = self.documents_dir / file_path
                if not full_path.exists():
                    broken_paths += 1

            if broken_paths > 0:
                self.error(f"{broken_paths}/20 sampled index paths are broken")
            else:
                self.success("All sampled index paths exist")

            # Get entry count
            cursor.execute("SELECT COUNT(*) FROM searchIndex")
            count = cursor.fetchone()[0]
            self.success(f"Index has {count} entries")

            conn.close()
        except sqlite3.Error as e:
            self.error(f"Database error: {e}")

    def validate(self) -> bool:
        """Run all checks and return True if all required checks pass."""
        print(f"Validating docset for Dash contribution: {self.docset_path}")
        print("=" * 60)

        self.check_structure()
        self.check_plist()
        self.check_icons()
        self.check_index()

        print("\n" + "=" * 60)

        if self.errors:
            print(f"\n❌ FAILED: {len(self.errors)} error(s)")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s)")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors:
            if self.warnings:
                print("\n✅ READY for contribution (with warnings)")
            else:
                print("\n✅ READY for contribution!")
            return True
        else:
            print("\n❌ NOT ready for contribution - fix errors first")
            return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify docset meets Dash contribution requirements"
    )
    parser.add_argument(
        "docset",
        type=Path,
        nargs="?",
        default=Path("output/Kubernetes.docset"),
        help="Path to the .docset directory",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    checker = ContributionChecker(args.docset, verbose=args.verbose)
    success = checker.validate()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
