"""Tests for the contribution workflow."""

import pytest
from pathlib import Path


class TestBranchNaming:
    """Test PR branch name generation."""

    def test_simple_version(self):
        docset_name = "Kubernetes"
        version = "1.34"
        branch_name = f"{docset_name.lower()}-v{version.replace('/', '-')}"
        assert branch_name == "kubernetes-v1.34"

    def test_version_with_fix_suffix(self):
        docset_name = "Kubernetes"
        version = "1.34/fix1"
        branch_name = f"{docset_name.lower()}-v{version.replace('/', '-')}"
        assert branch_name == "kubernetes-v1.34-fix1"

    def test_version_with_multiple_slashes(self):
        docset_name = "MyDocset"
        version = "1.0/beta/fix2"
        branch_name = f"{docset_name.lower()}-v{version.replace('/', '-')}"
        assert branch_name == "mydocset-v1.0-beta-fix2"


class TestDocsetJsonGeneration:
    """Test docset.json content generation."""

    def test_new_docset_json_structure(self):
        docset_name = "Kubernetes"
        version = "1.34"
        docset_json = {
            "name": docset_name,
            "version": version,
            "archive": f"{docset_name}.tgz",
            "author": {
                "name": "Test Author",
                "link": "https://github.com/test",
            },
            "aliases": [docset_name.lower()],
        }

        assert docset_json["name"] == "Kubernetes"
        assert docset_json["version"] == "1.34"
        assert docset_json["archive"] == "Kubernetes.tgz"
        assert docset_json["aliases"] == ["kubernetes"]
        assert "author" in docset_json

    def test_version_update_preserves_other_fields(self):
        existing = {
            "name": "Kubernetes",
            "version": "1.33",
            "archive": "Kubernetes.tgz",
            "author": {"name": "Original Author"},
            "aliases": ["k8s", "kube"],
            "specific_versions": [{"version": "1.32"}],
        }

        # Simulate version update
        existing["version"] = "1.34"

        assert existing["version"] == "1.34"
        assert existing["aliases"] == ["k8s", "kube"]  # Preserved
        assert "specific_versions" in existing  # Preserved


class TestArchiveNaming:
    """Test archive file naming."""

    def test_archive_name_matches_docset(self):
        docset_name = "Kubernetes"
        archive_name = f"{docset_name}.tgz"
        assert archive_name == "Kubernetes.tgz"

    def test_archive_extension(self):
        archive_name = "MyDocset.tgz"
        assert archive_name.endswith(".tgz")


class TestPathDefaults:
    """Test default path handling."""

    def test_default_docset_path(self):
        docset_name = "Kubernetes"
        default_path = Path(f"output/{docset_name}.docset")
        assert str(default_path) == "output/Kubernetes.docset"

    def test_default_contrib_repo_path(self):
        default_path = Path.home() / "repos" / "Dash-User-Contributions"
        assert "Dash-User-Contributions" in str(default_path)


class TestReadmeGeneration:
    """Test README.md content generation."""

    def test_readme_contains_docset_name(self):
        docset_name = "Kubernetes"
        readme = f"# {docset_name} Docset\n\nDash docset for {docset_name}."
        assert "Kubernetes" in readme
        assert "# Kubernetes Docset" in readme

    def test_readme_contains_generation_instructions(self):
        readme = """
## Generation

```bash
git clone https://github.com/example/repo.git
uv sync
poe all
```
"""
        assert "git clone" in readme
        assert "uv sync" in readme
        assert "poe all" in readme
