"""Web scraper for downloading Kubernetes documentation.

This module downloads the complete Kubernetes documentation from kubernetes.io
to enable building a Dash docset without requiring Dash's built-in generator.
"""

import time
from pathlib import Path
from typing import Set
from urllib.parse import urljoin, urlparse, unquote
import requests
from bs4 import BeautifulSoup


class KubernetesDocScraper:
    """Scraper for downloading Kubernetes documentation from kubernetes.io."""

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
        self.session.headers.update({
            "User-Agent": "Kubernetes-Dash-Docset-Generator/1.0"
        })

        self.visited_urls: Set[str] = set()
        self.downloaded_assets: Set[str] = set()

        # Rate limiting
        self.delay = 0.5  # seconds between requests

    def scrape(self, start_path: str = "/docs/") -> None:
        """Scrape documentation starting from the given path.

        Args:
            start_path: Path to start scraping from (default: /docs/)
        """
        print(f"Starting scrape of {self.base_url}{start_path}")
        print(f"Output directory: {self.output_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Start crawling from the docs homepage
        start_url = f"{self.base_url}{start_path}"
        self._crawl_page(start_url)

        print(f"\nScraping complete!")
        print(f"  HTML pages: {len(self.visited_urls)}")
        print(f"  Assets: {len(self.downloaded_assets)}")

    def _crawl_page(self, url: str) -> None:
        """Recursively crawl and download a page and all linked pages.

        Args:
            url: URL to crawl
        """
        # Normalize URL
        url = url.split("#")[0]  # Remove fragment

        if url in self.visited_urls:
            return

        # Only crawl URLs under /docs/
        if not self._should_crawl(url):
            return

        self.visited_urls.add(url)

        try:
            print(f"Downloading [{len(self.visited_urls)}]: {url}")

            time.sleep(self.delay)  # Rate limiting
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the HTML file
            file_path = self._url_to_filepath(url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(response.content)

            # Parse HTML to find links and assets
            soup = BeautifulSoup(response.content, "lxml")

            # Download static assets
            self._download_assets(soup, url)

            # Find and crawl linked pages
            for link in soup.find_all("a", href=True):
                href = link["href"]
                absolute_url = urljoin(url, href)

                # Only follow links to documentation pages
                if self._should_crawl(absolute_url):
                    self._crawl_page(absolute_url)

        except Exception as e:
            print(f"  Error downloading {url}: {e}")

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

    def _should_crawl(self, url: str) -> bool:
        """Check if a URL should be crawled.

        Args:
            url: URL to check

        Returns:
            True if the URL should be crawled
        """
        # Must be from the same base URL
        if not url.startswith(self.base_url):
            return False

        parsed = urlparse(url)
        path = parsed.path

        # Must be under /docs/
        if not path.startswith("/docs/"):
            return False

        # Skip certain paths
        skip_patterns = [
            "/docs/contribute/",  # Contributor docs
            "/blog/",
            "/case-studies/",
            "/training/",
            "/partners/",
        ]

        for pattern in skip_patterns:
            if pattern in path:
                return False

        return True

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
        base_url="https://kubernetes.io",
        output_dir=output_dir,
        version=version
    )

    scraper.scrape(start_path="/docs/")
