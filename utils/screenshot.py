"""Screenshot capture utilities using Playwright."""

import base64
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ScreenshotResult:
    """Result of a screenshot capture."""
    url: str
    screenshot_type: str  # "full_page" or "element"
    base64_data: str
    width: int = 0
    height: int = 0
    element_selector: str = ""
    captured_at: str = ""
    error: str = ""


class ScreenshotManager:
    """
    Manages screenshot capture using Playwright.

    Supports full page captures and element-specific captures.
    Returns screenshots as base64 data URIs for embedding in HTML reports.
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize the screenshot manager.

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self._browser = None
        self._playwright = None

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=self.headless)
            except ImportError:
                raise ImportError(
                    "Playwright not installed. Run: pip install playwright && playwright install chromium"
                )

    async def close(self):
        """Close browser and cleanup."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def capture_full_page(
        self,
        url: str,
        wait_for: str = "networkidle",
        viewport_width: int = 1280,
        viewport_height: int = 800
    ) -> ScreenshotResult:
        """
        Capture a full page screenshot.

        Args:
            url: URL to capture
            wait_for: Wait condition ("networkidle", "load", "domcontentloaded")
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height

        Returns:
            ScreenshotResult with base64 data
        """
        await self._ensure_browser()

        try:
            page = await self._browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            await page.goto(url, wait_until=wait_for, timeout=self.timeout)

            # Wait a bit for any animations to settle
            await page.wait_for_timeout(1000)

            # Capture full page screenshot
            screenshot_bytes = await page.screenshot(full_page=True, type="png")
            b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')

            await page.close()

            return ScreenshotResult(
                url=url,
                screenshot_type="full_page",
                base64_data=f"data:image/png;base64,{b64_data}",
                width=viewport_width,
                captured_at=datetime.now().isoformat()
            )

        except Exception as e:
            return ScreenshotResult(
                url=url,
                screenshot_type="full_page",
                base64_data="",
                error=str(e),
                captured_at=datetime.now().isoformat()
            )

    async def capture_element(
        self,
        url: str,
        selector: str,
        wait_for: str = "networkidle"
    ) -> ScreenshotResult:
        """
        Capture a screenshot of a specific element.

        Args:
            url: URL to load
            selector: CSS selector for the element
            wait_for: Wait condition

        Returns:
            ScreenshotResult with base64 data
        """
        await self._ensure_browser()

        try:
            page = await self._browser.new_page()
            await page.goto(url, wait_until=wait_for, timeout=self.timeout)

            # Wait for element to be visible
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                raise ValueError(f"Element not found: {selector}")

            # Capture element screenshot
            screenshot_bytes = await element.screenshot(type="png")
            b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')

            # Get element dimensions
            box = await element.bounding_box()
            width = int(box['width']) if box else 0
            height = int(box['height']) if box else 0

            await page.close()

            return ScreenshotResult(
                url=url,
                screenshot_type="element",
                base64_data=f"data:image/png;base64,{b64_data}",
                element_selector=selector,
                width=width,
                height=height,
                captured_at=datetime.now().isoformat()
            )

        except Exception as e:
            return ScreenshotResult(
                url=url,
                screenshot_type="element",
                base64_data="",
                element_selector=selector,
                error=str(e),
                captured_at=datetime.now().isoformat()
            )

    async def capture_multiple(
        self,
        urls: List[str],
        full_page: bool = True
    ) -> Dict[str, ScreenshotResult]:
        """
        Capture screenshots of multiple URLs.

        Args:
            urls: List of URLs to capture
            full_page: Whether to capture full page or viewport only

        Returns:
            Dictionary mapping URL to ScreenshotResult
        """
        results = {}
        for url in urls:
            result = await self.capture_full_page(url)
            results[url] = result
        return results

    def capture_sync(
        self,
        url: str,
        selector: Optional[str] = None
    ) -> ScreenshotResult:
        """
        Synchronous wrapper for screenshot capture.

        Args:
            url: URL to capture
            selector: Optional CSS selector for element capture

        Returns:
            ScreenshotResult
        """
        async def _capture():
            if selector:
                return await self.capture_element(url, selector)
            return await self.capture_full_page(url)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_capture())

    def capture_multiple_sync(
        self,
        urls: List[str],
        full_page: bool = True
    ) -> Dict[str, ScreenshotResult]:
        """
        Synchronous wrapper for multiple screenshot capture.

        Args:
            urls: List of URLs to capture
            full_page: Whether to capture full page

        Returns:
            Dictionary mapping URL to ScreenshotResult
        """
        async def _capture_all():
            return await self.capture_multiple(urls, full_page)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_capture_all())

        # Cleanup
        loop.run_until_complete(self.close())

        return result


def capture_page_screenshot(url: str) -> Optional[str]:
    """
    Simple helper function to capture a full page screenshot.

    Args:
        url: URL to capture

    Returns:
        Base64 data URI string, or None if failed
    """
    try:
        manager = ScreenshotManager()
        result = manager.capture_sync(url)
        return result.base64_data if not result.error else None
    except Exception as e:
        print(f"Screenshot capture failed for {url}: {e}")
        return None


def capture_element_screenshot(url: str, selector: str) -> Optional[str]:
    """
    Simple helper function to capture an element screenshot.

    Args:
        url: URL to load
        selector: CSS selector for the element

    Returns:
        Base64 data URI string, or None if failed
    """
    try:
        manager = ScreenshotManager()
        result = manager.capture_sync(url, selector)
        return result.base64_data if not result.error else None
    except Exception as e:
        print(f"Element screenshot capture failed for {url} ({selector}): {e}")
        return None
