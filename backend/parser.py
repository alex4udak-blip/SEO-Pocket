"""
HTML Parser
Extracts SEO-relevant data from HTML
"""

from typing import Optional
from bs4 import BeautifulSoup
import re


class HTMLParser:
    """
    Parses HTML and extracts SEO-relevant metadata.
    """

    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, "lxml")

    def parse(self) -> dict:
        """
        Parse HTML and return structured data.

        Returns:
            dict with keys:
                - title: str
                - h1: str
                - description: str
                - canonical: str
                - html_lang: str
                - hreflang: list[dict]
                - robots: str
        """
        return {
            "title": self._get_title(),
            "h1": self._get_h1(),
            "description": self._get_description(),
            "canonical": self._get_canonical(),
            "html_lang": self._get_html_lang(),
            "hreflang": self._get_hreflang(),
            "robots": self._get_robots(),
        }

    def _get_title(self) -> Optional[str]:
        """Get page title"""
        title_tag = self.soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        return None

    def _get_h1(self) -> Optional[str]:
        """Get first H1 tag"""
        h1_tag = self.soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)
        return None

    def _get_description(self) -> Optional[str]:
        """Get meta description"""
        meta = self.soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta and meta.get("content"):
            return meta["content"]
        return None

    def _get_canonical(self) -> Optional[str]:
        """Get canonical URL"""
        link = self.soup.find("link", attrs={"rel": "canonical"})
        if link and link.get("href"):
            return link["href"]
        return None

    def _get_html_lang(self) -> Optional[str]:
        """Get html lang attribute"""
        html_tag = self.soup.find("html")
        if html_tag:
            return html_tag.get("lang")
        return None

    def _get_hreflang(self) -> list[dict]:
        """Get all hreflang tags"""
        hreflangs = []
        links = self.soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})
        for link in links:
            hreflangs.append({
                "lang": link.get("hreflang"),
                "href": link.get("href")
            })
        return hreflangs

    def _get_robots(self) -> Optional[str]:
        """Get robots meta tag"""
        meta = self.soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        if meta and meta.get("content"):
            return meta["content"]
        return None


# Test
if __name__ == "__main__":
    test_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Test Page - Example</title>
        <meta name="description" content="This is a test page description">
        <link rel="canonical" href="https://example.com/test">
        <link rel="alternate" hreflang="en" href="https://example.com/en/test">
        <link rel="alternate" hreflang="de" href="https://example.com/de/test">
        <meta name="robots" content="index, follow">
    </head>
    <body>
        <h1>Test Page Heading</h1>
        <p>Content here</p>
    </body>
    </html>
    """

    parser = HTMLParser(test_html)
    result = parser.parse()

    print("Title:", result["title"])
    print("H1:", result["h1"])
    print("Description:", result["description"])
    print("Canonical:", result["canonical"])
    print("HTML Lang:", result["html_lang"])
    print("Hreflang:", result["hreflang"])
    print("Robots:", result["robots"])
