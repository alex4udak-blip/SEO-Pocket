"""
Cloaking Detection Service.
Compares HTML rendered for Googlebot vs regular user.
"""

import difflib
import re
from typing import Optional
from dataclasses import dataclass
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CloakingResult:
    """Result of cloaking detection."""
    detected: bool
    bot_only_lines: int
    user_only_lines: int
    bot_only_elements: list[str]
    user_only_elements: list[str]


class CloakingDetector:
    """
    Detects cloaking by comparing bot vs user HTML.
    """

    # Tags that often differ legitimately (ignored in strict comparison)
    IGNORE_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Scripts often differ
        r'<!--.*?-->',  # Comments
        r'<noscript[^>]*>.*?</noscript>',  # Noscript blocks
        r'data-[a-z-]+="[^"]*"',  # Data attributes
        r'id="[^"]*"',  # IDs that might be dynamic
        r'class="[^"]*"',  # Classes that might be dynamic
    ]

    # Important SEO elements to check
    SEO_ELEMENTS = [
        r'<title[^>]*>.*?</title>',
        r'<meta[^>]*name=["\']description["\'][^>]*>',
        r'<meta[^>]*name=["\']robots["\'][^>]*>',
        r'<link[^>]*rel=["\']canonical["\'][^>]*>',
        r'<h1[^>]*>.*?</h1>',
        r'<link[^>]*rel=["\']alternate["\'][^>]*hreflang[^>]*>',
    ]

    def __init__(self, strict: bool = False):
        """
        Initialize detector.

        Args:
            strict: If False, ignore common dynamic differences
        """
        self.strict = strict

    def _normalize_html(self, html: str) -> str:
        """
        Normalize HTML for comparison.
        Removes dynamic elements that commonly differ.
        """
        if self.strict:
            return html

        normalized = html

        # Remove ignored patterns
        for pattern in self.IGNORE_PATTERNS:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE | re.DOTALL)

        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized.strip()

    def _extract_seo_elements(self, html: str) -> list[str]:
        """Extract SEO-relevant elements from HTML."""
        elements = []
        for pattern in self.SEO_ELEMENTS:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            elements.extend(matches)
        return elements

    def compare(self, bot_html: str, user_html: str) -> CloakingResult:
        """
        Compare bot and user HTML to detect cloaking.

        Args:
            bot_html: HTML as seen by Googlebot
            user_html: HTML as seen by regular user

        Returns:
            CloakingResult with detection details
        """
        # Normalize both versions
        bot_normalized = self._normalize_html(bot_html)
        user_normalized = self._normalize_html(user_html)

        # Split into lines for diff
        bot_lines = bot_normalized.split('\n')
        user_lines = user_normalized.split('\n')

        # Get diff
        differ = difflib.Differ()
        diff = list(differ.compare(user_lines, bot_lines))

        # Count differences
        bot_only_lines = sum(1 for line in diff if line.startswith('+ '))
        user_only_lines = sum(1 for line in diff if line.startswith('- '))

        # Extract SEO elements
        bot_seo = set(self._extract_seo_elements(bot_html))
        user_seo = set(self._extract_seo_elements(user_html))

        # Find SEO elements that differ
        bot_only_elements = list(bot_seo - user_seo)
        user_only_elements = list(user_seo - bot_seo)

        # Cloaking detected if there are significant differences
        # especially in SEO elements
        detected = (
            len(bot_only_elements) > 0 or
            len(user_only_elements) > 0 or
            (bot_only_lines > 50 and bot_only_lines > len(bot_lines) * 0.1)
        )

        return CloakingResult(
            detected=detected,
            bot_only_lines=bot_only_lines,
            user_only_lines=user_only_lines,
            bot_only_elements=bot_only_elements[:10],  # Limit to 10
            user_only_elements=user_only_elements[:10],
        )

    def to_dict(self, result: CloakingResult) -> dict:
        """Convert CloakingResult to dict for API response."""
        return {
            "detected": result.detected,
            "bot_only_lines": result.bot_only_lines,
            "user_only_lines": result.user_only_lines,
            "bot_only_elements": result.bot_only_elements,
            "user_only_elements": result.user_only_elements,
        }


# Module-level instance for convenience
_detector: Optional[CloakingDetector] = None


def get_detector() -> CloakingDetector:
    """Get or create cloaking detector instance."""
    global _detector
    if _detector is None:
        _detector = CloakingDetector()
    return _detector
