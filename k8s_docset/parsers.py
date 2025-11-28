"""Parsers for extracting index entries from Kubernetes documentation HTML."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup


@dataclass
class IndexEntry:
    """Represents a single entry in the Dash search index."""

    name: str
    entry_type: str
    path: str


def parse_html_file(file_path: Path) -> BeautifulSoup:
    """Parse an HTML file and return a BeautifulSoup object."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return BeautifulSoup(f.read(), "lxml")


def get_title_from_soup(soup: BeautifulSoup) -> str | None:
    """Extract the page title from a BeautifulSoup object."""
    title_tag = soup.find("title")
    if title_tag:
        # Titles are usually "Name | Kubernetes"
        title = title_tag.get_text()
        if " | " in title:
            return title.split(" | ")[0].strip()
        return title.strip()
    return None


class APIResourceParser:
    """Parser for Kubernetes API resource reference pages.

    These are pages like:
    - docs/reference/kubernetes-api/workload-resources/pod-v1/
    - docs/reference/kubernetes-api/workload-resources/deployment-v1/
    """

    # Pattern to match API resource paths
    PATH_PATTERN = re.compile(
        r"docs/reference/kubernetes-api/[\w-]+/([\w-]+)-(v\d+(?:alpha\d+|beta\d+)?)/index\.html$"
    )

    # Map path segments to resource categories
    CATEGORY_MAP = {
        "workload-resources": "Workload",
        "service-resources": "Service",
        "config-and-storage-resources": "Config",
        "authentication-resources": "Authentication",
        "authorization-resources": "Authorization",
        "policy-resources": "Policy",
        "extend-resources": "Extension",
        "cluster-resources": "Cluster",
        "common-definitions": "Definition",
    }

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse an API resource page and yield index entries."""
        match = self.PATH_PATTERN.search(relative_path)
        if not match:
            return

        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if title:
            # Main resource entry (e.g., "Deployment")
            yield IndexEntry(
                name=title,
                entry_type="Resource",
                path=relative_path,
            )

            # Also add with version suffix for disambiguation
            version = match.group(2)
            versioned_name = f"{title} ({version})"
            if versioned_name != title:
                yield IndexEntry(
                    name=versioned_name,
                    entry_type="Resource",
                    path=relative_path,
                )

            # Parse fields/properties from the page
            yield from self._parse_fields(soup, relative_path, title)

    def _parse_fields(
        self, soup: BeautifulSoup, relative_path: str, resource_name: str
    ) -> Iterator[IndexEntry]:
        """Parse field definitions from the API resource page."""
        # Look for field definitions - they're typically in <code> tags or specific patterns
        # The K8s docs use various structures, so we'll look for common patterns

        # Look for headings that indicate fields
        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text().strip()
            heading_id = heading.get("id")

            # Skip generic headings
            if heading_text.lower() in [
                "description",
                "example",
                "see also",
                "what's next",
            ]:
                continue

            # If the heading has an ID and looks like a field name
            if heading_id and re.match(r"^[a-z][a-zA-Z0-9]*$", heading_text):
                yield IndexEntry(
                    name=f"{resource_name}.{heading_text}",
                    entry_type="Field",
                    path=f"{relative_path}#{heading_id}",
                )


class KubectlCommandParser:
    """Parser for kubectl command reference pages."""

    # Pattern to match kubectl command paths
    PATH_PATTERN = re.compile(r"docs/(kubectl_[\w-]+)/index\.html$")

    # Also match the generated kubectl commands page
    GENERATED_PATTERN = re.compile(
        r"docs/reference/generated/kubectl/kubectl-commands/index\.html$"
    )

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        # Skip _print versions
        if "/_print/" in relative_path:
            return False
        return bool(
            self.PATH_PATTERN.search(relative_path)
            or self.GENERATED_PATTERN.search(relative_path)
        )

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse a kubectl command page and yield index entries."""
        if self.GENERATED_PATTERN.search(relative_path):
            yield from self._parse_generated_commands(file_path, relative_path)
        else:
            yield from self._parse_single_command(file_path, relative_path)

    def _parse_single_command(
        self, file_path: Path, relative_path: str
    ) -> Iterator[IndexEntry]:
        """Parse a single kubectl command page."""
        match = self.PATH_PATTERN.search(relative_path)
        if not match:
            return

        # Convert kubectl_get to "kubectl get"
        command_slug = match.group(1)
        command_name = command_slug.replace("_", " ")

        yield IndexEntry(
            name=command_name,
            entry_type="Command",
            path=relative_path,
        )

    def _parse_generated_commands(
        self, file_path: Path, relative_path: str
    ) -> Iterator[IndexEntry]:
        """Parse the generated kubectl commands reference page."""
        soup = parse_html_file(file_path)

        # The generated page has command sections with IDs
        for heading in soup.find_all(["h2", "h3"]):
            heading_text = heading.get_text().strip()
            heading_id = heading.get("id")

            if heading_id and heading_text.startswith("kubectl"):
                yield IndexEntry(
                    name=heading_text,
                    entry_type="Command",
                    path=f"{relative_path}#{heading_id}",
                )


class GuideParser:
    """Parser for concept and guide pages."""

    # Patterns for different guide types
    CONCEPTS_PATTERN = re.compile(r"docs/concepts/")
    TASKS_PATTERN = re.compile(r"docs/tasks/")
    TUTORIALS_PATTERN = re.compile(r"docs/tutorials/")
    SETUP_PATTERN = re.compile(r"docs/setup/")
    CONTRIB_PATTERN = re.compile(r"docs/contribute/")

    # Category index pages to skip (these are just navigation, not content)
    # e.g., docs/concepts/index.html but NOT docs/concepts/pods/index.html
    CATEGORY_INDEX_PATTERNS = [
        re.compile(r"docs/concepts/index\.html$"),
        re.compile(r"docs/tasks/index\.html$"),
        re.compile(r"docs/tutorials/index\.html$"),
        re.compile(r"docs/setup/index\.html$"),
    ]

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        # Skip print versions
        if "/_print/" in relative_path:
            return False

        # Skip top-level category index pages
        for pattern in self.CATEGORY_INDEX_PATTERNS:
            if pattern.search(relative_path):
                return False

        return any(
            pattern.search(relative_path)
            for pattern in [
                self.CONCEPTS_PATTERN,
                self.TASKS_PATTERN,
                self.TUTORIALS_PATTERN,
                self.SETUP_PATTERN,
            ]
        )

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse a guide/concept page and yield index entries."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if not title:
            return

        # Determine the entry type based on the path
        if self.CONCEPTS_PATTERN.search(relative_path):
            entry_type = "Guide"
        elif self.TASKS_PATTERN.search(relative_path):
            entry_type = "Guide"
        elif self.TUTORIALS_PATTERN.search(relative_path):
            entry_type = "Sample"
        else:
            entry_type = "Guide"

        yield IndexEntry(
            name=title,
            entry_type=entry_type,
            path=relative_path,
        )


class GlossaryParser:
    """Parser for the Kubernetes glossary."""

    # Only match the main glossary page, not filtered views like /-_-all=true/
    PATH_PATTERN = re.compile(r"docs/reference/glossary/index\.html$")

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        # Skip filtered glossary views
        if "=-" in relative_path or "=true" in relative_path:
            return False
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse the glossary page and yield index entries."""
        soup = parse_html_file(file_path)

        # Find glossary terms - they're typically in specific elements
        # Look for dt/dd pairs or specific glossary item structures
        for term_elem in soup.find_all(class_=re.compile(r"glossary")):
            term_text = term_elem.get_text().strip()
            term_id = term_elem.get("id")

            if term_text and len(term_text) < 100:  # Avoid grabbing full descriptions
                path = relative_path
                if term_id:
                    path = f"{relative_path}#{term_id}"

                yield IndexEntry(
                    name=term_text,
                    entry_type="Word",
                    path=path,
                )

        # Also parse headings that might be terms
        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text().strip()
            heading_id = heading.get("id")

            # Skip generic headings
            if heading_text.lower() in ["glossary", "terms", "definitions"]:
                continue

            if heading_id and len(heading_text) < 50:
                yield IndexEntry(
                    name=heading_text,
                    entry_type="Word",
                    path=f"{relative_path}#{heading_id}",
                )


class ComponentParser:
    """Parser for Kubernetes component reference pages (kube-apiserver, kubelet, etc.)."""

    PATH_PATTERN = re.compile(
        r"docs/reference/(?:command-line-tools-reference|generated)/(kube-[\w-]+|kubelet|etcd)/"
    )

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        if "/_print/" in relative_path:
            return False
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse a component reference page."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if title:
            yield IndexEntry(
                name=title,
                entry_type="Component",
                path=relative_path,
            )


class DashAnchorParser:
    """Parser that extracts existing dashAnchor entries embedded by Dash's scraper.

    Dash's built-in docset generator embeds anchors like:
    <a name="//apple_ref/Entry/PodSpec" class="dashAnchor"></a>

    Our TOC injector also creates anchors like:
    <a name="//apple_ref/cpp/Section/Name" class="dashAnchor"></a>

    These contain high-quality, granular entries for API types, fields, etc.
    """

    # Pattern to extract type and name from apple_ref format
    # Dash format: //apple_ref/TYPE/NAME
    # Our format: //apple_ref/cpp/TYPE/NAME (cpp is language indicator)
    ANCHOR_PATTERN = re.compile(r"//apple_ref/(?:cpp/)?(\w+)/(.+)")

    # Map Dash's apple_ref types to our preferred types
    TYPE_MAP = {
        "Entry": "Type",  # API types like PodSpec, Container
        "Function": "Section",  # Sections like Containers, Volumes, Scheduling
        "Section": "Section",
        "Guide": "Guide",
        "Sample": "Sample",
        "Command": "Command",
    }

    # Generic/noisy entries to skip (lowercase for comparison)
    SKIP_NAMES = {
        "feedback",
        "before you begin",
        "what's next",
        "what-s-next",
        "see also",
        "options",
        "synopsis",
        "examples",
        "parent options inherited",
        "operations",
        "metadata",
        "items",
        "spec",
        "status",
        "clean up",
        "objectives",
        "resource types",
    }

    # Patterns that indicate noisy entries
    SKIP_PATTERNS = [
        r"^.+ - Note:$",  # "Pod - Note:", "ConfigMap - Note:"
    ]

    def matches(self, relative_path: str) -> bool:
        """Match any HTML file that might contain dashAnchors."""
        if "/_print/" in relative_path:
            return False
        return relative_path.endswith(".html")

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Extract dashAnchor entries from the HTML."""
        soup = parse_html_file(file_path)

        # Find all dashAnchor elements
        for anchor in soup.find_all("a", class_="dashAnchor"):
            name_attr = anchor.get("name", "")
            match = self.ANCHOR_PATTERN.match(name_attr)

            if match:
                entry_type = match.group(1)
                entry_name = match.group(2)

                # URL decode the name (e.g., %20 -> space)
                from urllib.parse import unquote

                entry_name = unquote(entry_name)

                # Skip generic/noisy entries
                if entry_name.lower() in self.SKIP_NAMES:
                    continue

                # Skip entries matching noise patterns
                skip = False
                for pattern in self.SKIP_PATTERNS:
                    if re.match(pattern, entry_name):
                        skip = True
                        break
                if skip:
                    continue

                # Map to our preferred type
                mapped_type = self.TYPE_MAP.get(entry_type, entry_type)

                # Find the anchor's ID for linking
                # The anchor itself often doesn't have an ID, but the next heading does
                anchor_id = None
                next_sibling = anchor.find_next_sibling()
                if next_sibling and next_sibling.get("id"):
                    anchor_id = next_sibling.get("id")

                # Construct the path with anchor
                path = relative_path
                if anchor_id:
                    path = f"{relative_path}#{anchor_id}"

                # Truncate very long names
                if len(entry_name) > 80:
                    entry_name = entry_name[:77] + "..."

                yield IndexEntry(
                    name=entry_name,
                    entry_type=mapped_type,
                    path=path,
                )


class FallbackParser:
    """Fallback parser for any HTML page not matched by other parsers."""

    def matches(self, relative_path: str) -> bool:
        """Always matches."""
        # Skip print pages and non-doc pages
        if "/_print/" in relative_path:
            return False
        if not relative_path.startswith("kubernetes.io/docs/"):
            return False
        return relative_path.endswith("/index.html") or relative_path.endswith(".html")

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse any documentation page as a generic entry."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if title and title != "Kubernetes":
            yield IndexEntry(
                name=title,
                entry_type="Guide",
                path=relative_path,
            )


# Import enhanced parsers
try:
    from .enhanced_parsers import ENHANCED_PARSERS
except ImportError:
    ENHANCED_PARSERS = []


# All parsers in order of specificity
# DashAnchorParser runs on ALL files to extract granular entries (if they exist)
# Enhanced parsers extract the same information from raw HTML structure
# Then specific parsers add their own entries
ALL_PARSERS = [
    DashAnchorParser(),  # Extract embedded anchors first (if present from Dash)
    *ENHANCED_PARSERS,  # Enhanced parsers for raw HTML extraction
    APIResourceParser(),
    KubectlCommandParser(),
    ComponentParser(),
    GlossaryParser(),
    GuideParser(),
    FallbackParser(),
]
