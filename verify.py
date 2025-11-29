"""Validate a Kubernetes Dash docset for correctness and completeness.

This script performs comprehensive validation of a generated docset,
checking structure, assets, paths, and search index integrity.
"""

# ruff: noqa: T201, PLR0912, C901

import argparse
import random
import re
import sqlite3
import sys
from pathlib import Path

# Minimum expected entries in search index
MIN_EXPECTED_ENTRIES = 1000


class DocsetValidator:
    """Validates a Dash docset for correctness."""

    def __init__(self, docset_path: Path, *, verbose: bool = False) -> None:
        """Initialize validator with docset path."""
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
        self._check_html_content()
        self._check_toc_anchors()

        print("=" * 60)
        if self.errors:
            err_count = len(self.errors)
            warn_count = len(self.warnings)
            print(f"\n❌ FAILED: {err_count} error(s), {warn_count} warning(s)")
            for err in self.errors:
                print(f"  - {err}")
            return False
        if self.warnings:
            print(f"\n⚠️  PASSED with {len(self.warnings)} warning(s)")
            for warn in self.warnings:
                print(f"  - {warn}")
            return True
        print("\n✅ PASSED: All checks passed!")
        return True

    def _check_structure(self) -> None:
        """Check basic docset directory structure."""
        print("\n📁 Checking directory structure...")

        if not self.docset_path.exists():
            self.error(f"Docset not found: {self.docset_path}")
            return

        if self.docset_path.suffix != ".docset":
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
            r"<key>dashIndexFilePath</key>\s*<string>([^<]+)</string>",
            content,
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
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='searchIndex'",
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
            elif count < MIN_EXPECTED_ENTRIES:
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
                    f"{missing_count}/10 sampled index paths point to missing files",
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

    def _check_html_content(self) -> None:
        """Check HTML files for unwanted content (tracking, cookies, etc.)."""
        print("\n🔗 Checking HTML content...")

        html_files = list(self.documents_dir.rglob("*.html"))
        if not html_files:
            self.error("No HTML files found")
            return

        self.success(f"Found {len(html_files)} HTML files")

        # Sample some HTML files to check for absolute paths and unwanted content
        sample_size = min(20, len(html_files))
        sample_files = random.sample(html_files, sample_size)

        # Check for absolute asset paths
        absolute_path_pattern = re.compile(
            r'(href|src)=["\']?/(scss|css|js|fonts|icons|images)/',
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
            except OSError:
                pass

        if files_with_absolute > 0:
            msg = (
                f"{files_with_absolute}/{sample_size} sampled files have absolute paths"
            )
            self.error(msg)
        else:
            self.success("No absolute asset paths found in sampled HTML files")

        # Patterns that indicate unwanted content
        unwanted_patterns = [
            (r"googletagmanager\.com", "Google Tag Manager"),
            (r"google-analytics\.com", "Google Analytics"),
            (r"cdn\.cookielaw\.org", "Cookie consent (OneTrust)"),
            (r"cookieconsent", "Cookie consent script"),
            (r"gdpr|privacy.?consent", "GDPR/privacy consent"),
            (r"code\.jquery\.com", "External jQuery reference"),
        ]

        found_issues: set[str] = set()
        for html_file in sample_files:
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")
                for pattern, desc in unwanted_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        found_issues.add(desc)
            except OSError:
                pass

        for issue in found_issues:
            self.warning(f"Found unwanted content: {issue}")

        if not found_issues:
            self.success("No tracking/cookie scripts detected")

        # Check for broken navigation links (file:/// or unscraped sections)
        broken_link_patterns = [
            (r'href="file:///', "file:// links"),
            (r'href="/blog/', "links to /blog/ (not scraped)"),
            (r'href="/training/', "links to /training/ (not scraped)"),
            (r'href="/partners/', "links to /partners/ (not scraped)"),
            (r'href="/community/', "links to /community/ (not scraped)"),
        ]
        broken_links: set[str] = set()
        for html_file in sample_files[:5]:
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")
                for pattern, desc in broken_link_patterns:
                    if re.search(pattern, content):
                        broken_links.add(desc)
            except OSError:
                pass

        for issue in broken_links:
            self.warning(f"Found broken links: {issue}")

        if not broken_links:
            self.success("No broken navigation links detected")

        # Check that navbar has been removed (causes broken links in offline docset)
        navbar_found = False
        for html_file in sample_files[:3]:
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")
                if re.search(r'<nav[^>]*class="[^"]*navbar[^"]*"', content):
                    navbar_found = True
                    break
            except OSError:
                pass

        if navbar_found:
            self.warning("Navbar elements found (should be removed for offline docset)")
        else:
            self.success("No navbar elements (clean offline display)")

    def _check_toc_anchors(self) -> None:
        """Check that TOC anchors are properly formed and targets exist."""
        print("\n📑 Checking TOC anchors...")

        html_files = list(self.documents_dir.rglob("*.html"))
        if not html_files:
            return

        sample_size = min(10, len(html_files))
        sample_files = random.sample(html_files, sample_size)

        total_anchors = 0
        anchors_outside_headings = 0

        for html_file in sample_files:
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")

                # Count anchors
                anchor_matches = re.findall(r'class="dashAnchor"', content)
                total_anchors += len(anchor_matches)

                # Check if anchors are inside headings (not before them)
                # Good: <h2><a class="dashAnchor"...></a>Title</h2>
                # Bad:  <a class="dashAnchor"...></a><h2>Title</h2>
                # Match anchor tags with dashAnchor class followed by heading tags
                bad_pattern = re.compile(
                    r'<a\s[^>]*dashAnchor[^>]*>\s*</a>\s*<h[123]',
                    re.IGNORECASE
                )
                bad_matches = bad_pattern.findall(content)
                anchors_outside_headings += len(bad_matches)
            except OSError:
                pass

        if total_anchors == 0:
            self.warning("No dashAnchor elements found in sampled files")
        else:
            self.success(f"Found {total_anchors} TOC anchors in {sample_size} sampled files")

        if anchors_outside_headings > 0:
            self.warning(
                f"{anchors_outside_headings} anchors placed before headings (should be inside)"
            )

        # Check search index entries have valid anchor targets
        if self.db_path.exists():
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT path FROM searchIndex WHERE path LIKE '%#%' "
                    "ORDER BY RANDOM() LIMIT 10"
                )
                anchor_paths = cursor.fetchall()
                conn.close()

                missing_targets = 0
                for (path,) in anchor_paths:
                    file_path, anchor = path.split("#", 1)
                    full_path = self.documents_dir / file_path
                    if full_path.exists():
                        content = full_path.read_text(encoding="utf-8", errors="ignore")
                        # Check if the anchor ID exists in the file
                        if f'id="{anchor}"' not in content and f"id='{anchor}'" not in content:
                            missing_targets += 1

                if missing_targets > 0:
                    self.warning(
                        f"{missing_targets}/10 sampled TOC entries point to missing anchors"
                    )
                elif anchor_paths:
                    self.success("Sampled TOC anchor targets exist")

            except sqlite3.Error:
                pass


def main() -> int:
    """CLI entry point."""
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
