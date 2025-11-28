#!/usr/bin/env python3
"""Validate a Kubernetes Dash docset for correctness and completeness.

This script performs comprehensive validation of a generated docset,
checking structure, assets, paths, and search index integrity.
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path


class DocsetValidator:
    """Validates a Dash docset for correctness."""

    def __init__(self, docset_path: Path, verbose: bool = False):
        self.docset_path = docset_path
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []

        # Standard paths
        self.contents_dir = docset_path / "Contents"
        self.resources_dir = self.contents_dir / "Resources"
        self.documents_dir = self.resources_dir / "Documents"
        self.db_path = self.resources_dir / "docSet.dsidx"
        self.plist_path = self.contents_dir / "Info.plist"

    def error(self, msg: str) -> None:
        """Record an error."""
        self.errors.append(msg)
        if self.verbose:
            print(f"  ❌ {msg}")

    def warning(self, msg: str) -> None:
        """Record a warning."""
        self.warnings.append(msg)
        if self.verbose:
            print(f"  ⚠️  {msg}")

    def success(self, msg: str) -> None:
        """Print success message if verbose."""
        if self.verbose:
            print(f"  ✅ {msg}")

    def validate(self) -> bool:
        """Run all validation checks. Returns True if valid."""
        print(f"Validating docset: {self.docset_path}")
        print("=" * 60)

        self._check_structure()
        self._check_info_plist()
        self._check_icons()
        self._check_search_index()
        self._check_assets()
        self._check_html_paths()

        print("=" * 60)
        if self.errors:
            print(
                f"\n❌ FAILED: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
            )
            for err in self.errors:
                print(f"  - {err}")
            return False
        elif self.warnings:
            print(f"\n⚠️  PASSED with {len(self.warnings)} warning(s)")
            for warn in self.warnings:
                print(f"  - {warn}")
            return True
        else:
            print("\n✅ PASSED: All checks passed!")
            return True

    def _check_structure(self) -> None:
        """Check basic docset directory structure."""
        print("\n📁 Checking directory structure...")

        if not self.docset_path.exists():
            self.error(f"Docset not found: {self.docset_path}")
            return

        if not self.docset_path.suffix == ".docset":
            self.error("Path must end with .docset")

        required_dirs = [
            self.contents_dir,
            self.resources_dir,
            self.documents_dir,
        ]

        for d in required_dirs:
            if d.exists():
                self.success(f"Directory exists: {d.name}")
            else:
                self.error(f"Missing directory: {d}")

    def _check_info_plist(self) -> None:
        """Check Info.plist exists and has required keys."""
        print("\n📋 Checking Info.plist...")

        if not self.plist_path.exists():
            self.error("Missing Info.plist")
            return

        content = self.plist_path.read_text()

        required_keys = [
            "CFBundleIdentifier",
            "CFBundleName",
            "DocSetPlatformFamily",
            "isDashDocset",
            "dashIndexFilePath",
        ]

        for key in required_keys:
            if f"<key>{key}</key>" in content:
                self.success(f"Info.plist has {key}")
            else:
                self.error(f"Info.plist missing key: {key}")

        # Check dashIndexFilePath points to existing file
        match = re.search(
            r"<key>dashIndexFilePath</key>\s*<string>([^<]+)</string>", content
        )
        if match:
            index_path = self.documents_dir / match.group(1)
            if index_path.exists():
                self.success(f"Index file exists: {match.group(1)}")
            else:
                self.warning(f"Index file not found: {match.group(1)}")

    def _check_icons(self) -> None:
        """Check docset icons exist."""
        print("\n🎨 Checking icons...")

        icon_16 = self.docset_path / "icon.png"
        icon_32 = self.docset_path / "icon@2x.png"

        if icon_16.exists():
            self.success("icon.png exists (16x16)")
        else:
            self.warning("Missing icon.png (16x16)")

        if icon_32.exists():
            self.success("icon@2x.png exists (32x32)")
        else:
            self.warning("Missing icon@2x.png (32x32)")

    def _check_search_index(self) -> None:
        """Check SQLite search index."""
        print("\n🔍 Checking search index...")

        if not self.db_path.exists():
            self.error("Missing docSet.dsidx database")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='searchIndex'"
            )
            if not cursor.fetchone():
                self.error("searchIndex table not found")
                conn.close()
                return

            self.success("searchIndex table exists")

            # Check entry count
            cursor.execute("SELECT COUNT(*) FROM searchIndex")
            count = cursor.fetchone()[0]
            if count == 0:
                self.error("searchIndex is empty")
            elif count < 1000:
                self.warning(f"searchIndex has only {count} entries (expected 10000+)")
            else:
                self.success(f"searchIndex has {count} entries")

            # Check entry types
            cursor.execute("SELECT DISTINCT type FROM searchIndex")
            types = [row[0] for row in cursor.fetchall()]
            expected_types = ["Guide", "Section", "Resource", "Command"]
            for t in expected_types:
                if t in types:
                    self.success(f"Has entry type: {t}")
                else:
                    self.warning(f"Missing entry type: {t}")

            # Sample some entries to verify paths exist
            cursor.execute("SELECT path FROM searchIndex ORDER BY RANDOM() LIMIT 10")
            sample_paths = [row[0] for row in cursor.fetchall()]
            missing_count = 0
            for path in sample_paths:
                # Strip anchor
                file_path = path.split("#")[0]
                full_path = self.documents_dir / file_path
                if not full_path.exists():
                    missing_count += 1

            if missing_count > 0:
                self.warning(
                    f"{missing_count}/10 sampled index paths point to missing files"
                )
            else:
                self.success("Sampled index paths all exist")

            conn.close()

        except sqlite3.Error as e:
            self.error(f"SQLite error: {e}")

    def _check_assets(self) -> None:
        """Check that required asset directories exist."""
        print("\n📦 Checking assets...")

        asset_dirs = ["scss", "css", "js", "images", "icons"]
        found_assets = 0

        for asset_dir in asset_dirs:
            asset_path = self.documents_dir / asset_dir
            if asset_path.exists():
                file_count = len(list(asset_path.rglob("*")))
                self.success(f"{asset_dir}/ exists ({file_count} files)")
                found_assets += 1
            else:
                self.warning(f"Missing asset directory: {asset_dir}/")

        if found_assets == 0:
            self.error("No asset directories found - CSS/JS won't work")

    def _check_html_paths(self) -> None:
        """Check HTML files don't have absolute asset paths."""
        print("\n🔗 Checking HTML paths...")

        html_files = list(self.documents_dir.rglob("*.html"))
        if not html_files:
            self.error("No HTML files found")
            return

        self.success(f"Found {len(html_files)} HTML files")

        # Sample some HTML files to check for absolute paths
        sample_size = min(20, len(html_files))
        import random

        sample_files = random.sample(html_files, sample_size)

        absolute_path_pattern = re.compile(
            r'(href|src)=["\']?/(scss|css|js|fonts|icons|images)/'
        )
        files_with_absolute = 0

        for html_file in sample_files:
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")
                if absolute_path_pattern.search(content):
                    files_with_absolute += 1
                    if self.verbose:
                        rel_path = html_file.relative_to(self.documents_dir)
                        self.warning(f"Absolute asset path in: {rel_path}")
            except Exception:
                pass

        if files_with_absolute > 0:
            self.error(
                f"{files_with_absolute}/{sample_size} sampled HTML files have absolute asset paths"
            )
        else:
            self.success("No absolute asset paths found in sampled HTML files")

        # Check for external resource references that should be local
        external_patterns = [
            (r"code\.jquery\.com", "External jQuery reference"),
            (r"googletagmanager\.com", "Google Tag Manager (should be removed)"),
            (r"google-analytics\.com", "Google Analytics (should be removed)"),
        ]

        for pattern, desc in external_patterns:
            for html_file in sample_files[:5]:
                try:
                    content = html_file.read_text(encoding="utf-8", errors="ignore")
                    if re.search(pattern, content):
                        self.warning(f"{desc} found")
                        break
                except Exception:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Dash docset")
    parser.add_argument(
        "docset",
        type=Path,
        nargs="?",
        default=Path("output/Kubernetes.docset"),
        help="Path to .docset directory (default: output/Kubernetes.docset)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    args = parser.parse_args()

    validator = DocsetValidator(args.docset, verbose=args.verbose)
    passed = validator.validate()

    if args.strict and validator.warnings:
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
