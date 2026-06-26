"""Playwright browser setup and navigation helpers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from .config import GameConfig

if TYPE_CHECKING:
    from playwright.async_api import Locator

READY_PROMPT = (
    "Get to the penalty screen with the ball ready (tap Play yourself first).\n"
    "Press Enter here when you're ready for the bot to shoot…"
)


async def wait_for_user_ready(prompt: str = READY_PROMPT) -> None:
    """Block until the user presses Enter in the terminal."""
    print(prompt)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input)


class GameBrowser:
    def __init__(self, config: GameConfig | None = None) -> None:
        self.config = config or GameConfig()
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self, *, headed: bool = True) -> Page:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=not headed,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 476, "height": 594},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="en-CA",
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        self.page = await self.context.new_page()
        return self.page

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def open_search(self, url: str | None = None) -> None:
        assert self.page is not None
        await self.page.goto(url or self.config.default_search_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

    async def try_open_mini_cup(self) -> bool:
        """Tap the soccer-ball FAB or any obvious game entry point."""
        assert self.page is not None
        page = self.page

        selectors = [
            '[aria-label*="Mini Cup" i]',
            '[aria-label*="penalty" i]',
            '[aria-label*="soccer" i]',
            '[aria-label*="football" i]',
            'a[href*="worldcup"]',
        ]
        for selector in selectors:
            loc = page.locator(selector).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                await asyncio.sleep(1.5)
                return True

        # Fixed bottom-right FAB fallback (common Mini Cup placement).
        await page.mouse.click(430, 560)
        await asyncio.sleep(1.5)
        return await self.canvas_visible()

    async def try_start_match(self, team: str = "Norway") -> None:
        """Click through team / play UI outside the canvas."""
        assert self.page is not None
        page = self.page

        for text in (team, "Play", "Start", "Shoot", "Continue"):
            btn = page.get_by_role("button", name=text, exact=False)
            if await btn.count() > 0:
                try:
                    await btn.first.click(timeout=2000)
                    await asyncio.sleep(0.8)
                except Exception:
                    pass

            link = page.get_by_text(text, exact=False)
            if await link.count() > 0:
                try:
                    await link.first.click(timeout=2000)
                    await asyncio.sleep(0.8)
                except Exception:
                    pass

    def canvas_locator(self) -> Locator:
        assert self.page is not None
        return self.page.locator(self.config.canvas_selector)

    async def canvas_visible(self) -> bool:
        loc = self.canvas_locator()
        try:
            return await loc.is_visible()
        except Exception:
            return False

    async def wait_for_canvas(self, timeout_ms: int = 120_000) -> Locator:
        loc = self.canvas_locator()
        await loc.wait_for(state="visible", timeout=timeout_ms)
        return loc

    def _game_overlay(self) -> Locator:
        assert self.page is not None
        return self.page.locator(".JHxP8e, .wYIgTb").last

    async def is_game_over(self) -> bool:
        """Detect miss / end screen via overlay text only (not goal celebrations)."""
        assert self.page is not None
        page = self.page

        for text in ("Try again", "Game over"):
            loc = page.get_by_text(text, exact=False)
            try:
                if await loc.count() > 0 and await loc.first.is_visible():
                    return True
            except Exception:
                continue

        overlay = self._game_overlay()
        for text in ("Try again", "Game over"):
            loc = overlay.get_by_text(text, exact=True)
            try:
                if await loc.count() > 0 and await loc.first.is_visible():
                    return True
            except Exception:
                continue
        return False
