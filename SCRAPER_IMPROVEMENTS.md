# Scraper Improvements

## Problem

Current scraper follows links blindly, resulting in:
- 100s of 404 errors from broken/old links
- Downloading `_print/` pages (duplicates)
- Following external links
- Wasted bandwidth and time

## Solution: Sitemap-based Scraping

### Sitemap Structure

```
https://kubernetes.io/sitemap.xml          # Index of all language sitemaps
https://kubernetes.io/en/sitemap.xml       # English docs sitemap (936 URLs)
```

### Implementation Plan

1. **Fetch sitemap** - Parse `/en/sitemap.xml` for all `/docs/` URLs
2. **Filter URLs** - Only include pages we want:
   - Include: `/docs/` pages
   - Exclude: `/_print/`, `/contribute/`, translations
3. **Download pages** - Fetch only the URLs from sitemap
4. **Download assets** - Extract and download CSS/JS/images from HTML

### Benefits

- **No 404 errors** - Only download known-good URLs
- **Faster** - No wasted requests to broken pages
- **Predictable** - Exact list of pages upfront
- **Maintainable** - Easy to update when site structure changes

### Code Changes

```python
# k8s_docset/scraper.py

class KubernetesDocScraper:
    SITEMAP_URL = "https://kubernetes.io/en/sitemap.xml"

    def get_docs_urls_from_sitemap(self) -> list[str]:
        """Fetch and parse sitemap to get all doc URLs."""
        response = requests.get(self.SITEMAP_URL)
        # Parse XML, extract URLs matching /docs/
        # Filter out _print, contribute, etc.
        return urls

    def scrape(self):
        urls = self.get_docs_urls_from_sitemap()
        print(f"Found {len(urls)} pages to download")

        for url in urls:
            self._download_page(url)
            self._download_page_assets(url)
```

### URL Count Comparison

| Source | Count |
|--------|-------|
| Sitemap `/docs/` | 936 |
| Current scrape | 915+ (with many 404s) |
| Expected final | ~900-950 |

## Assets Strategy

Assets are referenced in HTML and need separate handling:
- CSS: `/scss/`, `/css/`
- JS: `/js/`
- Images: `/images/`
- Icons: `/icons/`
- Fonts: `/fonts/`

Download these by parsing HTML files after page download.
