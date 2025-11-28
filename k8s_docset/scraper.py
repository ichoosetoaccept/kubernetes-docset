"""Web scraper for downloading Kubernetes documentation.

This module uses the kubernetes.io sitemap to download all documentation pages,
avoiding broken links and 404 errors from the link-following approach.
"""

import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


class KubernetesDocScraper:
    """Scraper for downloading Kubernetes documentation using sitemap.

    Uses sitemap-based scraping to avoid 404 errors from broken links.
    """

    SITEMAP_URL = "https://kubernetes.io/en/sitemap.xml"

    def __init__(self, base_url: str, output_dir: Path, version: str = "1.34"):
        """Initialize the scraper.

        Args:
            base_url: Base URL for Kubernetes docs (e.g., https://kubernetes.io)
            output_dir: Directory to save downloaded files
            version: Kubernetes version to scrape
        """
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir
        self.version = version
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Kubernetes-Dash-Docset-Generator/1.0"}
        )

        self.visited_urls: set[str] = set()
        self.downloaded_assets: set[str] = set()

        # Rate limiting
        self.delay = 0.5  # seconds between requests

    def scrape(self, start_path: str = "/docs/") -> None:
        """Scrape documentation using the sitemap.

        Args:
            start_path: Path prefix to filter URLs (default: /docs/)
        """
        print(f"Fetching sitemap from {self.SITEMAP_URL}")
        print(f"Output directory: {self.output_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Get URLs from sitemap
        urls = self._get_urls_from_sitemap(start_path)
        print(f"Found {len(urls)} pages to download")

        # Download each page
        for i, url in enumerate(urls, 1):
            self._download_page(url, i, len(urls))

        print("\nScraping complete!")
        print(f"  HTML pages: {len(self.visited_urls)}")
        print(f"  Assets: {len(self.downloaded_assets)}")

    def _get_urls_from_sitemap(self, path_prefix: str = "/docs/") -> list[str]:
        """Fetch and parse sitemap to get documentation URLs.

        Args:
            path_prefix: Only include URLs with this path prefix

        Returns:
            List of URLs to download
        """
        try:
            response = self.session.get(self.SITEMAP_URL, timeout=30)
            response.raise_for_status()

            # Parse XML sitemap
            root = ET.fromstring(response.content)

            # Handle XML namespace
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            urls = []
            for url_elem in root.findall(".//sm:loc", ns):
                url = url_elem.text
                if url and self._should_include_url(url, path_prefix):
                    urls.append(url)

            return sorted(urls)

        except Exception as e:
            print(f"Error fetching sitemap: {e}")
            return []

    def _should_include_url(self, url: str, path_prefix: str) -> bool:
        """Check if URL should be included from sitemap.

        Args:
            url: URL to check
            path_prefix: Required path prefix

        Returns:
            True if URL should be downloaded
        """
        parsed = urlparse(url)
        path = parsed.path

        # Must start with path prefix
        if not path.startswith(path_prefix):
            return False

        # Skip patterns
        skip_patterns = [
            "/_print/",
            "/contribute/",
        ]

        return not any(p in path for p in skip_patterns)

    def _download_page(self, url: str, current: int, total: int) -> None:
        """Download a single page and its assets.

        Args:
            url: URL to download
            current: Current page number
            total: Total pages to download
        """
        if url in self.visited_urls:
            return

        self.visited_urls.add(url)

        try:
            print(f"Downloading [{current}/{total}]: {url}")

            time.sleep(self.delay)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the HTML file
            file_path = self._url_to_filepath(url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(response.content)

            # Download static assets
            soup = BeautifulSoup(response.content, "lxml")
            self._download_assets(soup, url)

        except Exception as e:
            print(f"  Error: {e}")

    def _download_assets(self, soup: BeautifulSoup, page_url: str) -> None:
        """Download static assets (CSS, JS, images) referenced in the page.

        Args:
            soup: BeautifulSoup object of the page
            page_url: URL of the page being processed
        """
        # CSS files
        for link in soup.find_all("link", rel="stylesheet"):
            if link.get("href"):
                self._download_asset(link["href"], page_url)

        # JavaScript files
        for script in soup.find_all("script", src=True):
            self._download_asset(script["src"], page_url)

        # Images
        for img in soup.find_all("img", src=True):
            self._download_asset(img["src"], page_url)

        # Favicons and other icons
        for link in soup.find_all("link", rel=["icon", "apple-touch-icon"]):
            if link.get("href"):
                self._download_asset(link["href"], page_url)

    def _download_asset(self, asset_url: str, page_url: str) -> None:
        """Download a static asset.

        Args:
            asset_url: URL of the asset (may be relative)
            page_url: URL of the page referencing the asset
        """
        # Resolve relative URLs
        absolute_url = urljoin(page_url, asset_url)

        # Skip external assets (CDNs, etc.) - we only want kubernetes.io assets
        if not absolute_url.startswith(self.base_url):
            return

        if absolute_url in self.downloaded_assets:
            return

        self.downloaded_assets.add(absolute_url)

        try:
            time.sleep(self.delay)
            response = self.session.get(absolute_url, timeout=30)
            response.raise_for_status()

            file_path = self._url_to_filepath(absolute_url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(response.content)

        except Exception as e:
            print(f"  Warning: Failed to download asset {absolute_url}: {e}")

    def _url_to_filepath(self, url: str) -> Path:
        """Convert a URL to a local file path.

        Args:
            url: URL to convert

        Returns:
            Path object for the local file
        """
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Remove leading slash
        if path.startswith("/"):
            path = path[1:]

        # If path ends with /, append index.html
        if path.endswith("/"):
            path = path + "index.html"
        elif "." not in Path(path).name:
            # If no extension, assume it's an HTML page
            path = path + "/index.html"

        return self.output_dir / path


def scrape_kubernetes_docs(output_dir: Path, version: str = "1.34") -> None:
    """Scrape Kubernetes documentation.

    Args:
        output_dir: Directory to save downloaded files
        version: Kubernetes version to scrape
    """
    scraper = KubernetesDocScraper(
        base_url="https://kubernetes.io", output_dir=output_dir, version=version
    )

    scraper.scrape(start_path="/docs/")
