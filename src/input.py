"""Canvas coordinate mapping and human-like swipe input."""

from __future__ import annotations

import asyncio

from playwright.async_api import Locator, Page

from .config import GameConfig, Point


def canvas_to_page(
    cx: float,
    cy: float,
    box: dict[str, float],
    config: GameConfig,
) -> tuple[float, float]:
    return (
        box["x"] + (cx / config.canvas_width) * box["width"],
        box["y"] + (cy / config.canvas_height) * box["height"],
    )


async def swipe_shot(
    page: Page,
    canvas: Locator,
    start: Point,
    end: Point,
    config: GameConfig,
) -> None:
    box = await canvas.bounding_box()
    if not box:
        raise RuntimeError("Canvas has no bounding box")

    sx, sy = canvas_to_page(start.x, start.y, box, config)
    ex, ey = canvas_to_page(end.x, end.y, box, config)

    await page.mouse.move(sx, sy)
    await page.mouse.down()

    for i in range(1, config.swipe_steps + 1):
        t = i / config.swipe_steps
        await page.mouse.move(sx + (ex - sx) * t, sy + (ey - sy) * t)
        await asyncio.sleep(config.swipe_step_ms / 1000)

    await page.mouse.up()


async def tap_canvas(
    page: Page,
    canvas: Locator,
    point: Point,
    config: GameConfig,
) -> None:
    box = await canvas.bounding_box()
    if not box:
        raise RuntimeError("Canvas has no bounding box")
    x, y = canvas_to_page(point.x, point.y, box, config)
    await page.mouse.click(x, y)
