"""Tests for the docset verification."""

import re

import pytest


class TestAbsolutePathDetection:
    """Test patterns that detect absolute paths in HTML."""

    @pytest.fixture
    def asset_pattern(self):
        """Pattern to detect absolute asset paths."""
        return re.compile(r'(href|src)=["\']?/(scss|css|js|fonts|icons|images)/')

    @pytest.fixture
    def docs_pattern(self):
        """Pattern to detect absolute /docs/ paths."""
        return re.compile(r'(href|src)="/docs/')

    def test_absolute_css_detected(self, asset_pattern):
        html = '<link href="/css/style.css">'
        assert asset_pattern.search(html)

    def test_absolute_js_detected(self, asset_pattern):
        html = '<script src="/js/main.js"></script>'
        assert asset_pattern.search(html)

    def test_absolute_images_detected(self, asset_pattern):
        html = '<img src="/images/logo.png">'
        assert asset_pattern.search(html)

    def test_relative_css_not_detected(self, asset_pattern):
        html = '<link href="../css/style.css">'
        assert not asset_pattern.search(html)

    def test_absolute_docs_href_detected(self, docs_pattern):
        html = '<a href="/docs/concepts/">Link</a>'
        assert docs_pattern.search(html)

    def test_absolute_docs_src_detected(self, docs_pattern):
        html = '<img src="/docs/images/diagram.svg">'
        assert docs_pattern.search(html)

    def test_relative_docs_not_detected(self, docs_pattern):
        html = '<a href="../docs/concepts/">Link</a>'
        assert not docs_pattern.search(html)


class TestUnwantedContentDetection:
    """Test patterns that detect tracking/cookie scripts."""

    @pytest.fixture
    def unwanted_patterns(self):
        return [
            (re.compile(r"googletagmanager\.com", re.IGNORECASE), "Google Tag Manager"),
            (re.compile(r"google-analytics\.com", re.IGNORECASE), "Google Analytics"),
            (re.compile(r"cdn\.cookielaw\.org", re.IGNORECASE), "Cookie consent"),
            (re.compile(r"cookieconsent", re.IGNORECASE), "Cookie consent script"),
        ]

    def test_google_tag_manager_detected(self, unwanted_patterns):
        html = '<script src="https://www.googletagmanager.com/gtag/js"></script>'
        detected = [desc for pattern, desc in unwanted_patterns if pattern.search(html)]
        assert "Google Tag Manager" in detected

    def test_google_analytics_detected(self, unwanted_patterns):
        html = '<script src="https://www.google-analytics.com/analytics.js"></script>'
        detected = [desc for pattern, desc in unwanted_patterns if pattern.search(html)]
        assert "Google Analytics" in detected

    def test_clean_html_not_flagged(self, unwanted_patterns):
        html = '<html><body><h1>Hello</h1></body></html>'
        detected = [desc for pattern, desc in unwanted_patterns if pattern.search(html)]
        assert detected == []


class TestBrokenLinkDetection:
    """Test patterns that detect broken links."""

    @pytest.fixture
    def broken_patterns(self):
        return [
            (re.compile(r'href="file:///'), "file:// links"),
            (re.compile(r'href="/blog/'), "links to /blog/"),
            (re.compile(r'href="/training/'), "links to /training/"),
        ]

    def test_file_protocol_detected(self, broken_patterns):
        html = '<a href="file:///docs/concepts/">Broken</a>'
        detected = [desc for pattern, desc in broken_patterns if pattern.search(html)]
        assert "file:// links" in detected

    def test_blog_link_detected(self, broken_patterns):
        html = '<a href="/blog/2024/release/">Blog</a>'
        detected = [desc for pattern, desc in broken_patterns if pattern.search(html)]
        assert "links to /blog/" in detected

    def test_valid_docs_link_not_flagged(self, broken_patterns):
        html = '<a href="../docs/concepts/">Valid</a>'
        detected = [desc for pattern, desc in broken_patterns if pattern.search(html)]
        assert detected == []


class TestTocAnchorValidation:
    """Test TOC anchor placement detection."""

    @pytest.fixture
    def bad_anchor_pattern(self):
        """Pattern to detect anchors placed before headings (bad)."""
        return re.compile(r'<a\s[^>]*dashAnchor[^>]*>\s*</a>\s*<h[123]', re.IGNORECASE)

    def test_anchor_before_heading_detected(self, bad_anchor_pattern):
        # Bad: anchor before heading
        html = '<a name="//apple_ref/cpp/Section/Foo" class="dashAnchor"></a><h2>Foo</h2>'
        assert bad_anchor_pattern.search(html)

    def test_anchor_inside_heading_not_detected(self, bad_anchor_pattern):
        # Good: anchor inside heading
        html = '<h2><a name="//apple_ref/cpp/Section/Foo" class="dashAnchor"></a>Foo</h2>'
        assert not bad_anchor_pattern.search(html)
