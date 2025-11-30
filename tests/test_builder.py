"""Tests for the docset builder."""

import re

import pytest


class TestAbsolutePathFixing:
    """Test the regex patterns that fix absolute paths."""

    @pytest.fixture
    def href_pattern(self):
        """Pattern to fix href="/docs/..." to relative paths."""
        return re.compile(r'href="/docs/([^"]*)"')

    @pytest.fixture
    def src_pattern(self):
        """Pattern to fix src="/docs/..." to relative paths."""
        return re.compile(r'src="/docs/([^"]*)"')

    def test_href_docs_link_is_matched(self, href_pattern):
        html = '<a href="/docs/concepts/overview/">Overview</a>'
        assert href_pattern.search(html)

    def test_href_docs_link_is_replaced(self, href_pattern):
        html = '<a href="/docs/concepts/overview/">Overview</a>'
        prefix = "../../../"
        result = href_pattern.sub(rf'href="{prefix}docs/\1"', html)
        assert result == '<a href="../../../docs/concepts/overview/">Overview</a>'

    def test_src_docs_image_is_matched(self, src_pattern):
        html = '<img src="/docs/images/kubernetes.svg">'
        assert src_pattern.search(html)

    def test_src_docs_image_is_replaced(self, src_pattern):
        html = '<img src="/docs/images/kubernetes.svg">'
        prefix = "../../"
        result = src_pattern.sub(rf'src="{prefix}docs/\1"', html)
        assert result == '<img src="../../docs/images/kubernetes.svg">'

    def test_external_links_not_matched(self, href_pattern):
        html = '<a href="https://kubernetes.io/docs/concepts/">External</a>'
        assert not href_pattern.search(html)

    def test_relative_links_not_matched(self, href_pattern):
        html = '<a href="../docs/concepts/">Relative</a>'
        assert not href_pattern.search(html)


class TestUnscrapedSectionNeutralization:
    """Test neutralizing links to sections we didn't scrape."""

    @pytest.fixture
    def unscraped_sections(self):
        return [
            "/blog/", "/training/", "/partners/", "/community/",
            "/case-studies/", "/careers/", "/releases",
            "/zh-cn/", "/bn/", "/fr/", "/de/", "/hi/", "/id/", "/it/",
            "/ja/", "/ko/", "/pl/", "/pt-br/", "/ru/", "/es/", "/uk/", "/vi/",
        ]

    def test_blog_link_is_neutralized(self, unscraped_sections):
        html = '<a href="/blog/2024/kubernetes-release/">Blog Post</a>'
        for section in unscraped_sections:
            pattern = re.compile(
                rf'<a[^>]*href="{re.escape(section)}[^"]*"[^>]*>([^<]*)</a>'
            )
            html = pattern.sub(r'<span style="opacity:0.3">\1</span>', html)
        assert '<span style="opacity:0.3">Blog Post</span>' in html

    def test_docs_link_not_neutralized(self, unscraped_sections):
        html = '<a href="/docs/concepts/">Concepts</a>'
        original = html
        for section in unscraped_sections:
            pattern = re.compile(
                rf'<a[^>]*href="{re.escape(section)}[^"]*"[^>]*>([^<]*)</a>'
            )
            html = pattern.sub(r'<span style="opacity:0.3">\1</span>', html)
        assert html == original  # Unchanged


class TestNavbarRemoval:
    """Test navbar detection patterns."""

    @pytest.fixture
    def navbar_pattern(self):
        return re.compile(r'<nav[^>]*class="[^"]*navbar[^"]*"', re.IGNORECASE)

    def test_navbar_with_class_is_detected(self, navbar_pattern):
        html = '<nav class="navbar navbar-expand-lg">'
        assert navbar_pattern.search(html)

    def test_navbar_class_anywhere_is_detected(self, navbar_pattern):
        html = '<nav class="site-navbar main-nav">'
        assert navbar_pattern.search(html)

    def test_nav_without_navbar_class_not_detected(self, navbar_pattern):
        html = '<nav class="sidebar-nav">'
        assert not navbar_pattern.search(html)

    def test_plain_nav_not_detected(self, navbar_pattern):
        html = '<nav>'
        assert not navbar_pattern.search(html)


class TestDepthCalculation:
    """Test the relative path prefix calculation."""

    def calculate_depth(self, path_parts: int) -> str:
        """Calculate ../ prefix based on depth from documents root."""
        depth = path_parts - 1  # -1 for the file itself
        return "../" * depth

    def test_root_level_file(self):
        # docs/index.html -> 1 part -> depth 0
        assert self.calculate_depth(1) == ""

    def test_one_level_deep(self):
        # docs/concepts/index.html -> 2 parts -> depth 1
        assert self.calculate_depth(2) == "../"

    def test_two_levels_deep(self):
        # docs/concepts/overview/index.html -> 3 parts -> depth 2
        assert self.calculate_depth(3) == "../../"

    def test_three_levels_deep(self):
        # docs/tasks/run-application/configure/index.html -> 4 parts -> depth 3
        assert self.calculate_depth(4) == "../../../"


class TestDashAnchorFormat:
    """Test Dash anchor name format."""

    def test_anchor_format(self):
        entry_type = "Section"
        name = "Getting Started"
        from urllib.parse import quote
        encoded_name = quote(name, safe="")
        anchor_name = f"//apple_ref/cpp/{entry_type}/{encoded_name}"
        assert anchor_name == "//apple_ref/cpp/Section/Getting%20Started"

    def test_special_characters_encoded(self):
        from urllib.parse import quote
        name = "C++ & Python"
        encoded = quote(name, safe="")
        assert encoded == "C%2B%2B%20%26%20Python"
