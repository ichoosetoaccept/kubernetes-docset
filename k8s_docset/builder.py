"""Docset builder - creates the Dash docset structure and SQLite index."""

import shutil
import sqlite3
from io import BytesIO
from pathlib import Path
from typing import Iterator

import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from PIL import Image

from .parsers import ALL_PARSERS, IndexEntry


# Info.plist template for the docset
INFO_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>{identifier}</string>
    <key>CFBundleName</key>
    <string>{name}</string>
    <key>DocSetPlatformFamily</key>
    <string>{family}</string>
    <key>isDashDocset</key>
    <true/>
    <key>isJavaScriptEnabled</key>
    <true/>
    <key>dashIndexFilePath</key>
    <string>{index_path}</string>
    <key>DashDocSetKeyword</key>
    <string>{keyword}</string>
    <key>DashDocSetFallbackURL</key>
    <string>{fallback_url}</string>
    <key>DashDocSetFamily</key>
    <string>dashtoc</string>
</dict>
</plist>
"""


class DocsetBuilder:
    """Builds a Dash docset from existing HTML documentation."""

    def __init__(
        self,
        source_docs_dir: Path,
        output_dir: Path,
        docset_name: str = "Kubernetes",
        version: str = "1.34",
    ):
        self.source_docs_dir = source_docs_dir
        self.output_dir = output_dir
        self.docset_name = docset_name
        self.version = version

        # Docset paths
        self.docset_dir = output_dir / f"{docset_name}.docset"
        self.contents_dir = self.docset_dir / "Contents"
        self.resources_dir = self.contents_dir / "Resources"
        self.documents_dir = self.resources_dir / "Documents"
        self.db_path = self.resources_dir / "docSet.dsidx"

    def build(self) -> None:
        """Build the complete docset."""
        print(f"Building {self.docset_name} {self.version} docset...")

        # Create directory structure
        self._create_structure()

        # Copy HTML files
        self._copy_documents()

        # Create Info.plist
        self._create_info_plist()

        # Copy icon if it exists in source
        self._copy_icon()

        # Create SQLite index
        self._create_index()

        print(f"Docset created at: {self.docset_dir}")

    def _create_structure(self) -> None:
        """Create the docset directory structure."""
        print("Creating directory structure...")

        # Remove existing docset if present
        if self.docset_dir.exists():
            shutil.rmtree(self.docset_dir)

        # Create directories
        self.documents_dir.mkdir(parents=True)

    def _copy_documents(self) -> None:
        """Copy HTML documentation to the docset, injecting TOC anchors."""
        print("Copying documentation files...")

        # We only want the kubernetes.io docs, not CDN/external resources
        k8s_docs_source = self.source_docs_dir / "kubernetes.io"

        if k8s_docs_source.exists():
            source_root = k8s_docs_source
            dest_root = self.documents_dir / "kubernetes.io"
        else:
            source_root = self.source_docs_dir
            dest_root = self.documents_dir

        # Copy all files, processing HTML files for TOC injection
        html_count = 0
        for source_file in source_root.rglob("*"):
            if source_file.is_dir():
                continue

            relative = source_file.relative_to(source_root)
            dest_file = dest_root / relative
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if source_file.suffix == ".html":
                # Process HTML files to inject TOC anchors
                self._copy_html_with_toc(source_file, dest_file)
                html_count += 1
                if html_count % 200 == 0:
                    print(f"  Processed {html_count} HTML files...")
            else:
                # Copy other files directly
                shutil.copy2(source_file, dest_file)

        print(f"  Processed {html_count} HTML files with TOC injection")

    def _copy_html_with_toc(self, source_file: Path, dest_file: Path) -> None:
        """Copy an HTML file, injecting dashAnchor elements for TOC support."""
        try:
            content = source_file.read_text(encoding="utf-8", errors="replace")
            soup = BeautifulSoup(content, "lxml")

            # Find all headings with IDs (h1, h2, h3)
            for heading in soup.find_all(["h1", "h2", "h3"], id=True):
                heading_id = heading.get("id")
                heading_text = heading.get_text().strip()

                if not heading_id or not heading_text:
                    continue

                # Skip common navigation headings
                skip_headings = {"feedback", "what-s-next", "what's next", "see also"}
                if heading_text.lower() in skip_headings:
                    continue

                # Determine entry type based on heading level
                if heading.name == "h1":
                    entry_type = "Guide"
                elif heading.name == "h2":
                    entry_type = "Section"
                else:
                    entry_type = "Section"

                # URL encode the name for the anchor
                encoded_name = quote(heading_text, safe="")

                # Create dashAnchor element
                # Format: <a name="//apple_ref/cpp/TYPE/NAME" class="dashAnchor"></a>
                anchor = soup.new_tag("a")
                anchor["name"] = f"//apple_ref/cpp/{entry_type}/{encoded_name}"
                anchor["class"] = "dashAnchor"

                # Insert anchor before the heading
                heading.insert_before(anchor)

            # Write modified HTML
            dest_file.write_text(str(soup), encoding="utf-8")

        except Exception:
            # If processing fails, just copy the file as-is
            shutil.copy2(source_file, dest_file)

    def _copy_icon(self) -> None:
        """Copy or create the docset icon."""
        # Check for existing icons in source docset
        source_base = self.source_docs_dir.parent.parent.parent

        # Prefer PNG icons (Dash contribution standard)
        icon_copied = False
        for icon_name in ["icon.png", "icon@2x.png"]:
            source_icon = source_base / icon_name
            if source_icon.exists():
                shutil.copy(source_icon, self.docset_dir / icon_name)
                icon_copied = True

        if icon_copied:
            print("Copied PNG icons")
            return

        # Fall back to TIFF if no PNG
        source_tiff = source_base / "icon.tiff"
        if source_tiff.exists():
            shutil.copy(source_tiff, self.docset_dir / "icon.tiff")
            print("Copied icon.tiff")
            return

        # Download official Kubernetes icon if no icon found
        self._download_kubernetes_icon()

    def _download_kubernetes_icon(self) -> None:
        """Download and create Kubernetes icons in required sizes."""
        print("Downloading Kubernetes icon...")

        # Official Kubernetes logo SVG is complex, use the PNG from CNCF
        icon_url = "https://raw.githubusercontent.com/kubernetes/kubernetes/master/logo/logo.png"

        try:
            response = requests.get(icon_url, timeout=30)
            response.raise_for_status()

            # Open the image
            img = Image.open(BytesIO(response.content))

            # Convert to RGBA if necessary
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Create 16x16 icon
            icon_16 = img.resize((16, 16), Image.Resampling.LANCZOS)
            icon_16.save(self.docset_dir / "icon.png", "PNG")

            # Create 32x32 icon
            icon_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
            icon_32.save(self.docset_dir / "icon@2x.png", "PNG")

            print("Created icon.png (16x16) and icon@2x.png (32x32)")

        except Exception as e:
            print(f"Warning: Could not download icon: {e}")

    def _create_info_plist(self) -> None:
        """Create the Info.plist file."""
        print("Creating Info.plist...")

        # Per Dash contribution guidelines:
        # - identifier should not contain version
        # - name should not contain version (except for version-specific docsets)
        plist_content = INFO_PLIST_TEMPLATE.format(
            identifier="kubernetes",
            name=self.docset_name,
            family="kubernetes",
            index_path="kubernetes.io/docs/home/index.html",
            keyword="k8s",
            fallback_url="https://kubernetes.io/docs/",
        )

        plist_path = self.contents_dir / "Info.plist"
        plist_path.write_text(plist_content)

    def _create_index(self) -> None:
        """Create the SQLite search index."""
        print("Creating search index...")

        # Create database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create table
        cursor.execute("""
            CREATE TABLE searchIndex(
                id INTEGER PRIMARY KEY,
                name TEXT,
                type TEXT,
                path TEXT
            )
        """)

        # Create unique index to prevent duplicates
        cursor.execute("""
            CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path)
        """)

        # Index all documents
        entries_count = 0
        for entry in self._collect_entries():
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?, ?, ?)",
                    (entry.name, entry.entry_type, entry.path),
                )
                entries_count += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate entry, skip

        conn.commit()
        conn.close()

        print(f"Indexed {entries_count} entries")

    def _collect_entries(self) -> Iterator[IndexEntry]:
        """Collect all index entries from the documentation."""
        docs_root = self.documents_dir

        # Find all HTML files
        html_files = list(docs_root.rglob("*.html"))
        total_files = len(html_files)

        print(f"Processing {total_files} HTML files...")

        for i, html_file in enumerate(html_files, 1):
            if i % 100 == 0:
                print(f"  Progress: {i}/{total_files} files...")

            # Get relative path from documents root
            relative_path = str(html_file.relative_to(docs_root))

            # Run ALL matching parsers to collect entries from multiple sources
            for parser in ALL_PARSERS:
                if parser.matches(relative_path):
                    try:
                        yield from parser.parse(html_file, relative_path)
                    except Exception as e:
                        print(f"  Warning: Error parsing {relative_path}: {e}")


def build_docset(
    source_docset_path: Path,
    output_dir: Path,
    docset_name: str = "Kubernetes",
    version: str = "1.34",
) -> Path:
    """
    Build a new Dash docset from an existing one with improved indexing.

    Args:
        source_docset_path: Path to the source .docset directory
        output_dir: Directory where the new docset will be created
        docset_name: Name for the docset
        version: Kubernetes version

    Returns:
        Path to the created docset
    """
    # The source documents are inside Contents/Resources/Documents
    source_docs = source_docset_path / "Contents" / "Resources" / "Documents"

    if not source_docs.exists():
        raise ValueError(f"Source documents not found at {source_docs}")

    builder = DocsetBuilder(
        source_docs_dir=source_docs,
        output_dir=output_dir,
        docset_name=docset_name,
        version=version,
    )

    builder.build()
    return builder.docset_dir
