"""Enhanced parsers that extract high-quality entries from raw HTML.

These parsers work with raw HTML from kubernetes.io, without requiring
Dash's embedded dashAnchor elements.
"""

import re
from pathlib import Path
from typing import Iterator


from .parsers import IndexEntry, parse_html_file


class EnhancedAPIReferenceParser:
    """Enhanced parser for API reference pages that extracts detailed entries.

    Extracts from raw HTML structure:
    - H2 headings as Type entries (PodSpec, Container, DeploymentSpec, etc.)
    - H3 headings as Section entries (Containers, Volumes, Scheduling, etc.)
    - Field definitions as Property entries
    """

    PATH_PATTERN = re.compile(
        r"docs/reference/kubernetes-api/[\w-]+/([\w-]+)-(v\d+(?:alpha\d+|beta\d+)?)/index\.html$"
    )

    # Pattern to match field definitions: <strong>fieldName</strong> (TypeName)
    FIELD_PATTERN = re.compile(r"^([a-zA-Z0-9_\.]+)\s*\((.*?)\)(?:,\s*required)?$")

    def matches(self, relative_path: str) -> bool:
        """Check if this parser should handle the given path."""
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Extract detailed entries from API reference HTML."""
        soup = parse_html_file(file_path)

        # Extract the main resource name from the path
        match = self.PATH_PATTERN.search(relative_path)
        if match:
            resource_name = match.group(1)
            # Capitalize resource name (pod -> Pod, deployment -> Deployment)
            resource_name = resource_name.replace("-", " ").title().replace(" ", "")

            # Add main Resource entry
            yield IndexEntry(
                name=resource_name,
                entry_type="Resource",
                path=relative_path,
            )

        # Extract Type entries from H2 headings
        for h2 in soup.find_all("h2", id=True):
            type_name = h2.get("id")
            if type_name and isinstance(type_name, str) and type_name not in [
                "Pod",
                "Write",
                "Read",
                "Delete",
                "List",
                "Status",
                "Misc",
            ]:
                # These are type definitions like PodSpec, PodStatus, Container, etc.
                if not type_name.endswith("Operations"):  # Skip operation headings
                    yield IndexEntry(
                        name=type_name,
                        entry_type="Type",
                        path=f"{relative_path}#{type_name}",
                    )

        # Extract Section entries from H3 headings
        for h3 in soup.find_all("h3", id=True):
            section_name = h3.get_text().strip()
            section_id = h3.get("id")

            if section_name and section_id:
                # Clean up section name
                section_name = section_name.replace("\n", " ").strip()

                # Skip common navigation sections
                skip_sections = {
                    "Operations",
                    "Read Operations",
                    "Write Operations",
                    "Patch Operations",
                }
                if section_name not in skip_sections:
                    yield IndexEntry(
                        name=section_name,
                        entry_type="Section",
                        path=f"{relative_path}#{section_id}",
                    )

        # Extract field definitions as Property entries
        # Fields are in <li> elements with <strong>fieldName</strong> (TypeName) pattern
        for li in soup.find_all("li"):
            strong = li.find("strong")
            if not strong:
                continue

            # Get the text immediately following the <strong> tag
            field_text = ""
            for sibling in strong.next_siblings:
                if isinstance(sibling, str):
                    field_text += sibling
                    break
                elif sibling.name == "a":
                    # Sometimes the type is in a link
                    break

            # Try to match field pattern
            field_name = strong.get_text().strip()
            if field_name and "(" in str(li):
                # This looks like a field definition
                # Extract the type from the text
                full_text = li.get_text()

                # Look for pattern: fieldName (TypeName)
                if field_name in full_text:
                    # Find the type in parentheses
                    type_match = re.search(
                        rf"{re.escape(field_name)}\s*\((.*?)\)", full_text
                    )
                    if type_match:
                        type_name = type_match.group(1)

                        # Create entry for complex types
                        if type_name and type_name not in [
                            "string",
                            "boolean",
                            "int",
                            "int32",
                            "int64",
                            "number",
                        ]:
                            # Strip array notation
                            clean_type = type_name.replace("[]", "").strip()

                            # Only create entries for named types (not primitives)
                            if clean_type and clean_type[0].isupper():
                                yield IndexEntry(
                                    name=field_name,
                                    entry_type="Property",
                                    path=f"{relative_path}#{field_name}",
                                )


class EnhancedKubectlParser:
    """Enhanced parser for kubectl command reference pages."""

    PATH_PATTERN = re.compile(
        r"docs/reference/(generated/)?kubectl/[\w-]+/index\.html$"
    )

    def matches(self, relative_path: str) -> bool:
        """Check if this parser should handle the given path."""
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Extract kubectl command entries."""
        soup = parse_html_file(file_path)

        # Extract command name from H1 or title
        h1 = soup.find("h1")
        if h1:
            command_text = h1.get_text().strip()

            # Parse command name (e.g., "kubectl create" -> "create")
            if "kubectl" in command_text:
                parts = command_text.split()
                if len(parts) >= 2:
                    command_name = parts[1]
                    yield IndexEntry(
                        name=f"kubectl {command_name}",
                        entry_type="Command",
                        path=relative_path,
                    )

        # Extract subcommands from H2 or H3 headings
        for heading in soup.find_all(["h2", "h3"], id=True):
            heading_text = heading.get_text().strip()
            heading_id = heading.get("id")

            # Look for command syntax patterns
            if "kubectl" in heading_text.lower() or heading_text.startswith(
                ("create", "delete", "get", "apply", "describe")
            ):
                yield IndexEntry(
                    name=heading_text,
                    entry_type="Command",
                    path=f"{relative_path}#{heading_id}",
                )


class CodeSampleParser:
    """Parser that extracts code samples from documentation pages."""

    def matches(self, relative_path: str) -> bool:
        """This parser runs on all pages to extract code samples."""
        # Run on concept/guide/tutorial pages
        patterns = [
            r"docs/concepts/",
            r"docs/tasks/",
            r"docs/tutorials/",
        ]
        return any(re.search(pattern, relative_path) for pattern in patterns)

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Extract code samples from pages."""
        soup = parse_html_file(file_path)

        # Find code blocks with YAML/JSON content
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if not code:
                continue

            code_text = code.get_text()

            # Check if it looks like a Kubernetes manifest
            if any(
                keyword in code_text
                for keyword in ["apiVersion:", "kind:", "metadata:", "spec:"]
            ):
                # Try to find preceding heading for context
                sample_name = None
                prev = pre

                # Look back for a heading
                for _ in range(10):  # Look back up to 10 elements
                    prev = prev.find_previous(["h1", "h2", "h3", "h4", "p"])
                    if not prev:
                        break

                    if prev.name in ["h1", "h2", "h3", "h4"]:
                        sample_name = prev.get_text().strip()
                        break

                # Extract kind from YAML
                kind_match = re.search(r"kind:\s*(\w+)", code_text)
                if kind_match:
                    kind = kind_match.group(1)

                    if sample_name:
                        name = f"{kind} - {sample_name}"
                    else:
                        name = f"{kind} Example"

                    # Create unique anchor based on position
                    anchor = f"sample-{abs(hash(code_text[:100])) % 10000}"

                    yield IndexEntry(
                        name=name[:100],  # Limit length
                        entry_type="Sample",
                        path=f"{relative_path}#{anchor}",
                    )


# List of enhanced parsers (these will be added to the existing parsers)
ENHANCED_PARSERS = [
    EnhancedAPIReferenceParser(),
    EnhancedKubectlParser(),
    CodeSampleParser(),
]
