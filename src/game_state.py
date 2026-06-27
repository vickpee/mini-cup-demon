"""Poll for game-over UI after a shot."""

from __future__ import annotations

import asyncio
from typing import Literal

from playwright.async_api import Locator

from .browser import GameBrowser
from .config import GameConfig
from .vision import is_miss_screen

ShotResult = Literal["miss", "continue"]


async def _is_miss(browser: GameBrowser, canvas: Locator, config: GameConfig) -> bool:
    if await browser.is_game_over():
        return True
    png = await canvas.screenshot()
    return is_miss_screen(png, config)


async def wait_after_shot(
    browser: GameBrowser,
    canvas: Locator,
    config: GameConfig,
    *,
    timeout: float,
    poll_interval: float = 0.2,
    confirm_reads: int = 2,
) -> ShotResult:
    """
    After a shot, return ``miss`` only when game-over is confirmed repeatedly
    (blue pitch wash or Try again text). Otherwise ``continue`` for another goal.
    """
    streak = 0
    elapsed = 0.0
    while elapsed < timeout:
        if await _is_miss(browser, canvas, config):
            streak += 1
            if streak >= confirm_reads:
                return "miss"
        else:
            streak = 0
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return "continue"
