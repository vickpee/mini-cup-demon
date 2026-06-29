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


def _touch_point(x: float, y: float) -> dict[str, float | int]:
    return {"identifier": 0, "clientX": x, "clientY": y}


def _touch_payload(x: float, y: float) -> dict[str, list[dict[str, float | int]]]:
    point = _touch_point(x, y)
    return {"touches": [point], "changedTouches": [point], "targetTouches": [point]}


def _pointer_payload(x: float, y: float, *, buttons: int) -> dict[str, float | int | bool | str]:
    return {
        "pointerId": 1,
        "pointerType": "touch",
        "isPrimary": True,
        "clientX": x,
        "clientY": y,
        "buttons": buttons,
        "pressure": 0.5 if buttons else 0.0,
    }


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

    await canvas.dispatch_event("pointerdown", _pointer_payload(sx, sy, buttons=1))
    await canvas.dispatch_event("touchstart", _touch_payload(sx, sy))

    step_delay = config.swipe_step_ms / 1000
    for i in range(1, config.swipe_steps + 1):
        t = i / config.swipe_steps
        x = sx + (ex - sx) * t
        y = sy + (ey - sy) * t
        await canvas.dispatch_event("pointermove", _pointer_payload(x, y, buttons=1))
        await canvas.dispatch_event("touchmove", _touch_payload(x, y))
        if i < config.swipe_steps:
            await asyncio.sleep(step_delay)

    # touchend must list the lifted finger in changedTouches (empty breaks release).
    end_touch = _touch_point(ex, ey)
    await canvas.dispatch_event("pointerup", _pointer_payload(ex, ey, buttons=0))
    await canvas.dispatch_event(
        "touchend",
        {
            "touches": [],
            "changedTouches": [end_touch],
            "targetTouches": [],
        },
    )


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
