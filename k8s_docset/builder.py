"""Docset builder - creates the Dash docset structure and SQLite index."""

import shutil
import sqlite3
from pathlib import Path
from typing import Iterator

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
        """Copy HTML documentation to the docset."""
        print("Copying documentation files...")

        # We only want the kubernetes.io docs, not CDN/external resources
        k8s_docs_source = self.source_docs_dir / "kubernetes.io"

        if k8s_docs_source.exists():
            shutil.copytree(
                k8s_docs_source,
                self.documents_dir / "kubernetes.io",
                dirs_exist_ok=True,
            )
        else:
            # Fallback: copy everything
            shutil.copytree(
                self.source_docs_dir,
                self.documents_dir,
                dirs_exist_ok=True,
            )

    def _copy_icon(self) -> None:
        """Copy the docset icon if available."""
        # Check for icon in the source docset
        source_icon = self.source_docs_dir.parent.parent.parent / "icon.tiff"
        if source_icon.exists():
            # Convert TIFF to PNG would be ideal, but for now just copy
            # Dash also supports icon.png and icon@2x.png
            shutil.copy(source_icon, self.docset_dir / "icon.tiff")
            print("Copied icon.tiff")

    def _create_info_plist(self) -> None:
        """Create the Info.plist file."""
        print("Creating Info.plist...")

        plist_content = INFO_PLIST_TEMPLATE.format(
            identifier=f"kubernetes-{self.version}",
            name=f"{self.docset_name} {self.version}",
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
