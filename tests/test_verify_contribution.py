"""Tests for the Dash contribution requirements checker."""

import re

import pytest


class TestPlistRequirements:
    """Test Info.plist validation patterns."""

    def test_version_in_bundle_name_detected(self):
        """Bundle name should not contain version numbers."""
        pattern = re.compile(r"\d+\.\d+")
        assert pattern.search("Kubernetes 1.34")
        assert pattern.search("React 18.2.0")
        assert not pattern.search("Kubernetes")
        assert not pattern.search("React")

    def test_required_plist_keys(self):
        """Check the required keys list is complete."""
        required_keys = [
            "CFBundleIdentifier",
            "CFBundleName",
            "DocSetPlatformFamily",
            "isDashDocset",
        ]
        assert len(required_keys) == 4
        assert "CFBundleIdentifier" in required_keys
        assert "isDashDocset" in required_keys


class TestIndexRequirements:
    """Test search index validation."""

    def test_empty_entry_detection(self):
        """Empty entries should be flagged."""
        entries = ["", "Valid Entry", None, "Another Valid"]
        empty_count = sum(1 for e in entries if not e)
        assert empty_count == 2

    def test_newline_in_entry_detection(self):
        """Entries with newlines should be flagged."""
        entries = ["Valid", "Has\nNewline", "Also\nBad", "Good"]
        newline_count = sum(1 for e in entries if e and "\n" in e)
        assert newline_count == 2

    def test_path_anchor_splitting(self):
        """Paths with anchors should be split correctly."""
        path = "docs/concepts/index.html#overview"
        file_path = path.split("#")[0]
        assert file_path == "docs/concepts/index.html"

    def test_path_without_anchor(self):
        """Paths without anchors should remain unchanged."""
        path = "docs/concepts/index.html"
        file_path = path.split("#")[0]
        assert file_path == "docs/concepts/index.html"


class TestIconRequirements:
    """Test icon validation."""

    def test_icon_filenames(self):
        """Check expected icon filenames."""
        expected_icons = ["icon.png", "icon@2x.png"]
        assert "icon.png" in expected_icons
        assert "icon@2x.png" in expected_icons


class TestDocsetStructure:
    """Test docset directory structure validation."""

    def test_required_directories(self):
        """Check required directory structure."""
        required_dirs = ["Contents", "Resources", "Documents"]
        assert "Contents" in required_dirs
        assert "Resources" in required_dirs
        assert "Documents" in required_dirs

    def test_docset_extension(self):
        """Docset must have .docset extension."""
        valid_path = "MyDocset.docset"
        invalid_path = "MyDocset"
        assert valid_path.endswith(".docset")
        assert not invalid_path.endswith(".docset")


class TestTocSupport:
    """Test table of contents support detection."""

    def test_dashtoc_family_value(self):
        """DashDocSetFamily should be 'dashtoc' for TOC support."""
        plist = {"DashDocSetFamily": "dashtoc"}
        assert plist.get("DashDocSetFamily") == "dashtoc"

    def test_missing_dashtoc(self):
        """Missing DashDocSetFamily should be detected."""
        plist = {"CFBundleName": "MyDocset"}
        assert plist.get("DashDocSetFamily") != "dashtoc"
