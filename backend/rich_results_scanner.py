"""
Rich Results Test Scanner - Optimized Version
Based on MCP browser research (30 Jan 2026)

Features:
- Precise element selectors from live analysis
- Mobile + Desktop scanning
- HTML + Screenshot extraction
- Multi-account support preparation
- Rate limit awareness
"""

import asyncio
import base64
import re
import time
import logging
import json
from pathlib import Path
from urllib.parse import quote
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a single scan (mobile or desktop)."""
    url: str
    user_agent: str  # 'mobile' or 'desktop'
    html: str
    title: Optional[str]
    canonical: Optional[str]
    screenshot_base64: Optional[str]
    scan_time_ms: int
    success: bool
    error: Optional[str] = None


@dataclass
class FullScanResult:
    """Combined result of mobile + desktop scans."""
    url: str
    mobile: Optional[ScanResult]
    desktop: Optional[ScanResult]
    total_time_ms: int


class RichResultsScanner:
    """
    Optimized Rich Results Test scanner.

    Key findings from MCP research:
    - User agent selector: aria-label="Выбор агента пользователя" at (1452, 72)
    - Desktop option: menuitem "Google Inspection Tool на компьютере"
    - HTML: .CodeMirror-line elements
    - Screenshot: img with data:image src, position x > 900
    - Scan completion: "Просканировано:" text appears
    """

    BASE_URL = 'https://search.google.com/test/rich-results'

    # Precise selectors discovered through MCP
    SELECTORS = {
        'url_input': 'input[type="url"]',
        'test_button': 'button[aria-label="Проверить страницу"]',
        'ua_selector': '[aria-label="Выбор агента пользователя"]',
        'desktop_option': '[aria-label="Google Inspection Tool на компьютере"]',
        'mobile_option': '[aria-label="Google Inspection Tool на смартфоне"]',
        'view_page_btn': 'button[aria-label="Посмотреть проверенную страницу"]',
        'html_lines': '.CodeMirror-line',
        'screenshot_tab': '[role="tab"]:has-text("СКРИНШОТ")',
        'html_tab': '[role="tab"]:has-text("HTML")',
    }

    def __init__(self, profile_dir: str = 'data/rrt_profile', headless: bool = False):
        self.profile_dir = Path(profile_dir)
        self.headless = headless
        self.driver = None
        self._last_scan_time = None

    def start(self) -> 'RichResultsScanner':
        """Initialize browser with persistent profile."""
        logger.info('Starting browser...')

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # Clean up lock files
        for lock in self.profile_dir.glob('Singleton*'):
            try:
                lock.unlink()
            except:
                pass

        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1512,900')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--lang=ru-RU')

        if self.headless:
            options.add_argument('--headless=new')

        self.driver = uc.Chrome(
            options=options,
            user_data_dir=str(self.profile_dir.absolute()),
            headless=self.headless,
            version_main=144
        )

        # Give browser time to stabilize
        import time as _time
        _time.sleep(2)

        try:
            self.driver.set_window_size(1512, 900)
        except Exception as e:
            logger.warning(f'Could not set window size: {e}')

        logger.info('Browser ready!')
        return self

    def scan(self, url: str, user_agent: str = 'mobile') -> ScanResult:
        """
        Scan a single URL with specified user agent.

        Args:
            url: URL to scan
            user_agent: 'mobile' or 'desktop'
        """
        start_time = time.time()

        try:
            # Navigate to Rich Results Test with URL
            encoded_url = quote(url, safe='')
            test_url = f'{self.BASE_URL}?url={encoded_url}'

            logger.info(f'Scanning {url} ({user_agent})...')
            self.driver.get(test_url)

            # Select user agent if desktop
            if user_agent == 'desktop':
                self._select_user_agent('desktop')
                # Click test button to start scan
                self._click_test_button()

            # Wait for scan completion
            if not self._wait_for_scan():
                return ScanResult(
                    url=url,
                    user_agent=user_agent,
                    html='',
                    title=None,
                    canonical=None,
                    screenshot_base64=None,
                    scan_time_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    error='Scan timeout'
                )

            # Extract data
            html = self._extract_html()
            screenshot = self._extract_screenshot()

            # Parse metadata from HTML
            title = self._parse_title(html)
            canonical = self._parse_canonical(html)

            return ScanResult(
                url=url,
                user_agent=user_agent,
                html=html,
                title=title,
                canonical=canonical,
                screenshot_base64=screenshot,
                scan_time_ms=int((time.time() - start_time) * 1000),
                success=True
            )

        except Exception as e:
            logger.error(f'Scan error: {e}')
            return ScanResult(
                url=url,
                user_agent=user_agent,
                html='',
                title=None,
                canonical=None,
                screenshot_base64=None,
                scan_time_ms=int((time.time() - start_time) * 1000),
                success=False,
                error=str(e)
            )

    def scan_both(self, url: str) -> FullScanResult:
        """
        Scan URL with both mobile and desktop user agents.

        Strategy:
        1. Load page (starts mobile scan automatically)
        2. Extract mobile data
        3. Switch to desktop via dropdown
        4. Wait for rescan
        5. Extract desktop data
        """
        total_start = time.time()

        # Navigate to Rich Results Test
        encoded_url = quote(url, safe='')
        test_url = f'{self.BASE_URL}?url={encoded_url}'

        logger.info(f'Starting full scan for: {url}')
        self.driver.get(test_url)

        # === MOBILE SCAN ===
        logger.info('=== MOBILE SCAN ===')
        mobile_start = time.time()

        if not self._wait_for_scan():
            return FullScanResult(
                url=url,
                mobile=ScanResult(
                    url=url, user_agent='mobile', html='', title=None,
                    canonical=None, screenshot_base64=None,
                    scan_time_ms=int((time.time() - mobile_start) * 1000),
                    success=False, error='Mobile scan timeout'
                ),
                desktop=None,
                total_time_ms=int((time.time() - total_start) * 1000)
            )

        # Store scan time to detect new scan
        self._last_scan_time = self._get_scan_time()

        mobile_html = self._extract_html()
        mobile_screenshot = self._extract_screenshot()

        mobile_result = ScanResult(
            url=url,
            user_agent='mobile',
            html=mobile_html,
            title=self._parse_title(mobile_html),
            canonical=self._parse_canonical(mobile_html),
            screenshot_base64=mobile_screenshot,
            scan_time_ms=int((time.time() - mobile_start) * 1000),
            success=True
        )
        logger.info(f'Mobile done: {len(mobile_html)} chars, {mobile_result.scan_time_ms}ms')

        # === DESKTOP SCAN ===
        logger.info('=== DESKTOP SCAN ===')
        desktop_start = time.time()

        # Close preview panel if open
        self._close_preview_panel()

        # Switch to desktop
        if not self._select_user_agent('desktop'):
            return FullScanResult(
                url=url,
                mobile=mobile_result,
                desktop=ScanResult(
                    url=url, user_agent='desktop', html='', title=None,
                    canonical=None, screenshot_base64=None,
                    scan_time_ms=int((time.time() - desktop_start) * 1000),
                    success=False, error='Failed to switch to desktop'
                ),
                total_time_ms=int((time.time() - total_start) * 1000)
            )

        # Wait for NEW scan (different timestamp)
        if not self._wait_for_scan(check_new=True):
            return FullScanResult(
                url=url,
                mobile=mobile_result,
                desktop=ScanResult(
                    url=url, user_agent='desktop', html='', title=None,
                    canonical=None, screenshot_base64=None,
                    scan_time_ms=int((time.time() - desktop_start) * 1000),
                    success=False, error='Desktop scan timeout'
                ),
                total_time_ms=int((time.time() - total_start) * 1000)
            )

        desktop_html = self._extract_html()
        desktop_screenshot = self._extract_screenshot()

        desktop_result = ScanResult(
            url=url,
            user_agent='desktop',
            html=desktop_html,
            title=self._parse_title(desktop_html),
            canonical=self._parse_canonical(desktop_html),
            screenshot_base64=desktop_screenshot,
            scan_time_ms=int((time.time() - desktop_start) * 1000),
            success=True
        )
        logger.info(f'Desktop done: {len(desktop_html)} chars, {desktop_result.scan_time_ms}ms')

        return FullScanResult(
            url=url,
            mobile=mobile_result,
            desktop=desktop_result,
            total_time_ms=int((time.time() - total_start) * 1000)
        )

    def _wait_for_scan(self, timeout: int = 120, check_new: bool = False) -> bool:
        """Wait for scan to complete."""
        logger.info(f'Waiting for scan (timeout={timeout}s)...')

        for i in range(timeout):
            time.sleep(1)

            try:
                body_text = self.driver.find_element(By.TAG_NAME, 'body').text
            except:
                continue

            # Check for scan completion
            if 'Просканировано' in body_text:
                if check_new:
                    new_time = self._get_scan_time()
                    if new_time and new_time != self._last_scan_time:
                        logger.info(f'New scan completed in {i+1}s')
                        return True
                else:
                    logger.info(f'Scan completed in {i+1}s')
                    return True

            # Progress indicator
            if i > 0 and i % 15 == 0:
                logger.info(f'Still scanning... ({i}s)')

        logger.warning(f'Scan timeout after {timeout}s')
        return False

    def _get_scan_time(self) -> Optional[str]:
        """Get timestamp of last scan from page."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, 'body').text
            match = re.search(r'Просканировано[^\d]*(\d{1,2}[^\d]+\d{4}[^\d]+\d{1,2}:\d{2}:\d{2})', body_text)
            return match.group(1) if match else None
        except:
            return None

    def _select_user_agent(self, agent: str) -> bool:
        """Select user agent (mobile or desktop)."""
        try:
            logger.info(f'Selecting {agent} user agent...')

            # Find and click UA selector button (at position ~1452, 72)
            ua_btns = self.driver.find_elements(By.CSS_SELECTOR, '[aria-label="Выбор агента пользователя"]')

            clicked = False
            for btn in ua_btns:
                try:
                    rect = self.driver.execute_script(
                        'var r = arguments[0].getBoundingClientRect(); return {x: r.x, y: r.y};',
                        btn
                    )
                    # The visible one should be around y=72
                    if rect['y'] > 50 and rect['y'] < 100:
                        btn.click()
                        clicked = True
                        logger.info(f'Clicked UA selector at ({rect["x"]}, {rect["y"]})')
                        break
                except:
                    continue

            if not clicked:
                logger.error('Could not find UA selector')
                return False

            time.sleep(0.5)

            # Select agent from dropdown
            target_label = 'компьютере' if agent == 'desktop' else 'смартфоне'

            items = self.driver.find_elements(By.CSS_SELECTOR, '[role="menuitem"]')
            for item in items:
                if target_label in (item.text or '').lower():
                    item.click()
                    logger.info(f'Selected {agent}')
                    time.sleep(1)
                    return True

            # Fallback: click by aria-label
            selector = f'[aria-label*="{target_label}"]'
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                elements[0].click()
                logger.info(f'Selected {agent} via aria-label')
                time.sleep(1)
                return True

            logger.error(f'Could not select {agent}')
            return False

        except Exception as e:
            logger.error(f'Error selecting user agent: {e}')
            return False

    def _click_test_button(self):
        """Click the test/rescan button."""
        try:
            # Try "Проверить URL ещё раз" first
            btns = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in btns:
                text = btn.text or ''
                if 'Проверить URL' in text or 'ПРОВЕРИТЬ' in text.upper():
                    btn.click()
                    logger.info('Clicked test button')
                    return
        except Exception as e:
            logger.error(f'Error clicking test button: {e}')

    def _close_preview_panel(self):
        """Close the preview panel if open."""
        try:
            close_btns = self.driver.find_elements(By.CSS_SELECTOR, '[aria-label="Закрыть"]')
            for btn in close_btns:
                try:
                    rect = self.driver.execute_script(
                        'var r = arguments[0].getBoundingClientRect(); return {x: r.x, y: r.y};',
                        btn
                    )
                    # Preview panel close button should be around x=1140
                    if rect['x'] > 1100:
                        btn.click()
                        logger.info('Closed preview panel')
                        time.sleep(0.5)
                        return
                except:
                    continue
        except:
            pass

    def _scroll_to_top(self):
        """Scroll page to top to ensure buttons are visible."""
        try:
            self.driver.execute_script('window.scrollTo(0, 0);')
            time.sleep(0.3)
        except:
            pass

    def _extract_html(self) -> str:
        """Extract rendered HTML from the page."""
        try:
            # First, open the preview panel
            self._open_preview_panel()
            time.sleep(1)

            # Extract from CodeMirror
            html = self.driver.execute_script('''
                var lines = document.querySelectorAll('.CodeMirror-line');
                var html = '';
                lines.forEach(function(line) {
                    html += line.textContent + '\\n';
                });
                return html;
            ''') or ''

            return html.strip()

        except Exception as e:
            logger.error(f'Error extracting HTML: {e}')
            return ''

    def _extract_screenshot(self) -> Optional[str]:
        """Extract screenshot as base64."""
        try:
            # Try multiple methods to click the screenshot tab
            clicked = False

            # Method 1: Find visible tab element and click via Selenium
            tabs = self.driver.find_elements(By.CSS_SELECTOR, '[role="tab"]')
            for tab in tabs:
                try:
                    tab_text = (tab.text or '').upper()
                    if 'СКРИНШОТ' in tab_text:
                        # Check if visible
                        if tab.is_displayed():
                            tab.click()
                            clicked = True
                            logger.info('Clicked screenshot tab via Selenium')
                            break
                except Exception as e:
                    logger.warning(f'Selenium click failed: {e}')

            # Method 2: JavaScript click if Selenium failed
            if not clicked:
                clicked = self.driver.execute_script('''
                    var tabs = document.querySelectorAll('[role="tab"]');
                    for (var tab of tabs) {
                        var text = (tab.innerText || tab.textContent || '').toUpperCase();
                        if (text.includes('СКРИНШОТ')) {
                            tab.click();
                            return true;
                        }
                    }
                    return false;
                ''')
                if clicked:
                    logger.info('Clicked screenshot tab via JS')

            # Method 3: ActionChains click at approximate coordinates
            if not clicked:
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    # Screenshot tab is approximately at x=1311, y=252 based on MCP research
                    actions = ActionChains(self.driver)
                    actions.move_by_offset(1311, 252).click().perform()
                    actions.reset_actions()
                    actions.move_by_offset(-1311, -252).perform()
                    clicked = True
                    logger.info('Clicked screenshot tab via ActionChains')
                except Exception as e:
                    logger.warning(f'ActionChains click failed: {e}')

            if not clicked:
                logger.warning('Could not click screenshot tab by any method')
                return None

            time.sleep(3)  # Give time for screenshot to fully load (desktop is larger!)
            logger.info('Waiting for screenshot image...')

            # Find data:image img - try multiple times with wait
            # Look for the VISIBLE image with largest size (to handle multiple images in DOM)
            screenshot = None
            for attempt in range(5):
                screenshot = self.driver.execute_script('''
                    var imgs = document.querySelectorAll('img');
                    var bestImg = null;
                    var bestSize = 0;

                    for (var i = 0; i < imgs.length; i++) {
                        var img = imgs[i];
                        if (img.src && img.src.indexOf('data:image') === 0) {
                            var rect = img.getBoundingClientRect();
                            // Screenshot should be visible (width > 0) and in right panel area
                            if (rect.width > 100 && rect.x > 900) {
                                // Prefer the larger image (by src length)
                                if (img.src.length > bestSize) {
                                    bestSize = img.src.length;
                                    bestImg = img.src;
                                }
                            }
                        }
                    }
                    return bestImg;
                ''')
                if screenshot:
                    logger.info(f'Screenshot found: {len(screenshot)} bytes')
                    break
                logger.info(f'Screenshot attempt {attempt + 1}/5 - not found yet')
                time.sleep(2)  # Wait longer between attempts

            if not screenshot:
                logger.warning('Screenshot image not found in panel after 5 attempts')

            # Switch back to HTML tab via JS
            self.driver.execute_script('''
                var tabs = document.querySelectorAll('[role="tab"]');
                for (var tab of tabs) {
                    var text = (tab.innerText || tab.textContent || '').toUpperCase();
                    if (text.includes('HTML')) {
                        tab.click();
                        break;
                    }
                }
            ''')

            return screenshot

        except Exception as e:
            logger.error(f'Error extracting screenshot: {e}')
            return None

    def _open_preview_panel(self):
        """Open the 'View tested page' panel."""
        try:
            # First scroll to top to ensure button is visible
            self._scroll_to_top()
            time.sleep(0.5)

            # Wait for the button to be present and visible
            btns = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in btns:
                text = btn.text or ''
                if 'ПОСМОТРЕТЬ ПРОВЕРЕННУЮ' in text.upper() or 'Посмотреть проверенную' in text:
                    # Check if button is displayed and enabled
                    if btn.is_displayed() and btn.is_enabled():
                        # Scroll element into view
                        self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', btn)
                        time.sleep(0.3)
                        btn.click()
                        logger.info('Opened preview panel')
                        time.sleep(1)  # Wait for panel to fully open
                        return
                    else:
                        logger.warning('Preview button found but not interactable, trying JS click')
                        self.driver.execute_script('arguments[0].click();', btn)
                        logger.info('Opened preview panel via JS click')
                        time.sleep(1)
                        return

            # Fallback via aria-label
            btns = self.driver.find_elements(By.CSS_SELECTOR, '[aria-label*="проверенную"]')
            for btn in btns:
                if btn.is_displayed():
                    self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', btn)
                    time.sleep(0.3)
                    try:
                        btn.click()
                    except:
                        self.driver.execute_script('arguments[0].click();', btn)
                    logger.info('Opened preview panel via aria-label')
                    time.sleep(1)
                    return

            logger.warning('Preview panel button not found!')

        except Exception as e:
            logger.error(f'Error opening preview panel: {e}')

    def _parse_title(self, html: str) -> Optional[str]:
        """Parse title from HTML."""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _parse_canonical(self, html: str) -> Optional[str]:
        """Parse canonical URL from HTML."""
        match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', html, re.IGNORECASE)
        return match.group(1) if match else None

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info('Browser closed')


# === Multi-Account Manager ===

class MultiAccountScanner:
    """
    Manages multiple Google accounts for rate limit distribution.

    Strategy:
    - N profiles with different Google accounts
    - Round-robin distribution of scans
    - Track rate limits per profile
    - Auto-switch when hitting limits
    """

    def __init__(self, profile_dirs: List[str]):
        self.profile_dirs = profile_dirs
        self.scanners: List[RichResultsScanner] = []
        self.scan_counts: Dict[int, int] = {}  # profile_idx -> scan count
        self.last_scan_time: Dict[int, float] = {}  # profile_idx -> timestamp
        self.current_idx = 0

        # Rate limit settings (conservative estimates)
        self.max_scans_per_hour = 50
        self.min_delay_between_scans = 5  # seconds

    def start_all(self):
        """Start all scanner instances."""
        for i, profile_dir in enumerate(self.profile_dirs):
            logger.info(f'Starting scanner {i+1}/{len(self.profile_dirs)}...')
            scanner = RichResultsScanner(profile_dir=profile_dir)
            scanner.start()
            self.scanners.append(scanner)
            self.scan_counts[i] = 0
            self.last_scan_time[i] = 0

        logger.info(f'Started {len(self.scanners)} scanners')

    def get_next_scanner(self) -> tuple[RichResultsScanner, int]:
        """Get the next available scanner (round-robin with rate limit check)."""
        attempts = 0
        while attempts < len(self.scanners):
            idx = self.current_idx
            self.current_idx = (self.current_idx + 1) % len(self.scanners)

            # Check if this scanner is rate limited
            if self._is_rate_limited(idx):
                attempts += 1
                continue

            return self.scanners[idx], idx

        # All scanners rate limited - wait and return first
        logger.warning('All scanners rate limited, waiting...')
        time.sleep(60)
        return self.scanners[0], 0

    def _is_rate_limited(self, idx: int) -> bool:
        """Check if scanner is hitting rate limits."""
        now = time.time()

        # Check hourly limit
        # (simplified - would need proper time window tracking in production)
        if self.scan_counts[idx] >= self.max_scans_per_hour:
            return True

        # Check minimum delay
        if now - self.last_scan_time[idx] < self.min_delay_between_scans:
            return True

        return False

    def scan(self, url: str, user_agent: str = 'mobile') -> ScanResult:
        """Scan using next available scanner."""
        scanner, idx = self.get_next_scanner()

        result = scanner.scan(url, user_agent)

        self.scan_counts[idx] += 1
        self.last_scan_time[idx] = time.time()

        return result

    def scan_both(self, url: str) -> FullScanResult:
        """Full scan using next available scanner."""
        scanner, idx = self.get_next_scanner()

        result = scanner.scan_both(url)

        self.scan_counts[idx] += 2  # Mobile + Desktop
        self.last_scan_time[idx] = time.time()

        return result

    def close_all(self):
        """Close all scanners."""
        for scanner in self.scanners:
            scanner.close()
        self.scanners = []


# === Demo ===

async def demo():
    """Demo single scanner."""
    print('=' * 60)
    print('RICH RESULTS TEST SCANNER - OPTIMIZED')
    print('=' * 60)

    scanner = RichResultsScanner(profile_dir='data/rrt_profile_demo')
    scanner.start()

    url = 'https://casino-ohne.gaststaette-hillenbrand.de/'

    print(f'\nScanning: {url}\n')

    result = scanner.scan_both(url)

    print('\n' + '=' * 60)
    print('RESULTS')
    print('=' * 60)

    if result.mobile and result.mobile.success:
        print(f'\nMOBILE:')
        print(f'  Title: {result.mobile.title}')
        print(f'  Canonical: {result.mobile.canonical}')
        print(f'  HTML: {len(result.mobile.html)} chars')
        print(f'  Screenshot: {"Yes" if result.mobile.screenshot_base64 else "No"}')
        print(f'  Time: {result.mobile.scan_time_ms}ms')
    else:
        print(f'\nMOBILE: Error - {result.mobile.error if result.mobile else "No result"}')

    if result.desktop and result.desktop.success:
        print(f'\nDESKTOP:')
        print(f'  Title: {result.desktop.title}')
        print(f'  Canonical: {result.desktop.canonical}')
        print(f'  HTML: {len(result.desktop.html)} chars')
        print(f'  Screenshot: {"Yes" if result.desktop.screenshot_base64 else "No"}')
        print(f'  Time: {result.desktop.scan_time_ms}ms')
    else:
        print(f'\nDESKTOP: Error - {result.desktop.error if result.desktop else "No result"}')

    print(f'\nTOTAL TIME: {result.total_time_ms}ms ({result.total_time_ms/1000:.1f}s)')

    # Save results
    Path('data').mkdir(exist_ok=True)

    with open('data/scan_result.json', 'w') as f:
        json.dump({
            'url': result.url,
            'mobile': asdict(result.mobile) if result.mobile else None,
            'desktop': asdict(result.desktop) if result.desktop else None,
            'total_time_ms': result.total_time_ms
        }, f, indent=2, ensure_ascii=False, default=str)
    print('\nResults saved to data/scan_result.json')

    scanner.close()
    print('\nDone!')


if __name__ == '__main__':
    asyncio.run(demo())
