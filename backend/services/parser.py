"""
HTML Parser Service.
Extracts SEO-relevant metadata from HTML.
"""

import re
from typing import Optional
from bs4 import BeautifulSoup
from core.logging import get_logger

logger = get_logger(__name__)


class HTMLParser:
    """
    Parses HTML and extracts SEO-relevant metadata.
    """

    def __init__(self, html: str):
        """
        Initialize parser with HTML content.

        Args:
            html: Raw HTML string
        """
        self.html = html
        self.soup = BeautifulSoup(html, "lxml")

    def parse(self) -> dict:
        """
        Parse HTML and return structured SEO data.

        Returns:
            dict with keys:
                - title: str
                - h1: str
                - description: str
                - canonical: str
                - html_lang: str
                - hreflang: list[dict]
                - robots: str
                - alternate_urls: list[str]
        """
        return {
            "title": self._get_title(),
            "h1": self._get_h1(),
            "description": self._get_description(),
            "canonical": self._get_canonical(),
            "html_lang": self._get_html_lang(),
            "hreflang": self._get_hreflang(),
            "robots": self._get_robots(),
            "alternate_urls": self._get_alternate_urls(),
        }

    def _get_title(self) -> Optional[str]:
        """Get page title."""
        title_tag = self.soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        return None

    def _get_h1(self) -> Optional[str]:
        """Get first H1 tag content."""
        h1_tag = self.soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)
        return None

    def _get_description(self) -> Optional[str]:
        """Get meta description."""
        meta = self.soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta and meta.get("content"):
            return meta["content"]
        return None

    def _get_canonical(self) -> Optional[str]:
        """Get canonical URL."""
        link = self.soup.find("link", attrs={"rel": "canonical"})
        if link and link.get("href"):
            return link["href"]
        return None

    def _get_html_lang(self) -> Optional[str]:
        """Get html lang attribute."""
        html_tag = self.soup.find("html")
        if html_tag:
            return html_tag.get("lang")
        return None

    def _get_hreflang(self) -> list[dict]:
        """Get all hreflang tags."""
        hreflangs = []
        links = self.soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})
        for link in links:
            hreflangs.append({
                "lang": link.get("hreflang"),
                "url": link.get("href")
            })
        return hreflangs

    def _get_robots(self) -> Optional[str]:
        """Get robots meta tag content."""
        meta = self.soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        if meta and meta.get("content"):
            return meta["content"]
        return None

    def _get_alternate_urls(self) -> list[str]:
        """Get all alternate URLs (excluding hreflang which have separate field)."""
        alternates = []
        links = self.soup.find_all("link", attrs={"rel": "alternate"})
        for link in links:
            href = link.get("href")
            # Skip hreflang entries (they have hreflang attribute)
            if href and not link.get("hreflang"):
                # Skip feed links
                link_type = link.get("type", "")
                if "rss" not in link_type.lower() and "atom" not in link_type.lower():
                    alternates.append(href)
        return alternates


def extract_seo_data_fast(html: str) -> dict:
    """
    Fast regex-based SEO extraction.
    Use when BeautifulSoup is too slow.

    Args:
        html: Raw HTML string

    Returns:
        dict with basic SEO fields
    """
    data = {}

    # Title
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    if title_match:
        data['title'] = title_match.group(1).strip()

    # H1
    h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
    if h1_match:
        data['h1'] = h1_match.group(1).strip()

    # Meta description
    desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.I
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']',
            html, re.I
        )
    if desc_match:
        data['description'] = desc_match.group(1).strip()

    # Canonical
    canonical_match = re.search(
        r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
        html, re.I
    )
    if canonical_match:
        data['canonical'] = canonical_match.group(1).strip()

    # HTML lang
    lang_match = re.search(r'<html[^>]*lang=["\']([^"\']+)["\']', html, re.I)
    if lang_match:
        data['html_lang'] = lang_match.group(1).strip()

    # Robots
    robots_match = re.search(
        r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.I
    )
    if robots_match:
        data['robots'] = robots_match.group(1).strip()

    return data
