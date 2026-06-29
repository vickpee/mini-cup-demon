"""Read keeper position from canvas screenshots."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image

from .config import GameConfig, KeeperBox
from .keeper_js import KEEPER_BBOX_JS

if TYPE_CHECKING:
    from playwright.async_api import Locator


def _is_grass(r: int, g: int, b: int) -> bool:
    return g > r + 15 and g > b + 10 and g > 80


def _is_keeper_pixel(r: int, g: int, b: int) -> bool:
    """Colorful pixels in the goal band (keeper kit), not grass or gray net."""
    if _is_grass(r, g, b):
        return False
    if max(r, g, b) - min(r, g, b) < 35:
        return False
    return True


def _col_to_config_x(col_i: int, num_cols: int, config: GameConfig) -> float:
    if num_cols <= 0:
        return config.goal_left
    return config.goal_left + col_i * (config.goal_right - config.goal_left) / num_cols


def _peak_vertical_score(
    pixels: Image.Image,
    peak_i: int,
    search_left_px: int,
    y0: int,
    y1: int,
    window: int,
) -> int:
    """Prefer tall keeper sprites over flat net/crowd noise."""
    left = max(0, search_left_px + peak_i - window // 2)
    right = search_left_px + peak_i + window // 2
    top, bottom = y1, y0
    mass = 0
    for y in range(y0, y1):
        for x in range(left, right, 2):
            if x < 0 or x >= pixels.width:
                continue
            if _is_keeper_pixel(*pixels.getpixel((x, y))):
                mass += 1
                top = min(top, y)
                bottom = max(bottom, y)
    height = max(0, bottom - top)
    return height * mass


def _pick_peak_column(
    counts: list[int],
    config: GameConfig,
    *,
    scale_x: float,
    hint_x: float | None,
    pixels: Image.Image | None = None,
    search_left_px: int = 0,
    y0: int = 0,
    y1: int = 0,
    window: int = 0,
) -> int | None:
    """Pick the keeper column peak; prefer the peak nearest hint when tracking."""
    if not counts:
        return None

    margin = max(4, int(40 * scale_x))
    peaks: list[tuple[int, int]] = []

    for i in range(margin, len(counts) - margin):
        c = counts[i]
        if c < 4:
            continue
        if c >= counts[i - 1] and c > counts[i + 1]:
            peaks.append((c, i))

    if not peaks:
        interior = range(margin, len(counts) - margin)
        if not interior:
            return None
        best_i = max(interior, key=lambda i: counts[i])
        if counts[best_i] < 4:
            return None
        peaks = [(counts[best_i], best_i)]

    max_count = max(c for c, _ in peaks)
    strong = [(c, i) for c, i in peaks if c >= max_count * 0.55]

    if hint_x is not None and len(strong) > 1:
        _, best_i = min(
            strong,
            key=lambda p: abs(_col_to_config_x(p[1], len(counts), config) - hint_x),
        )
        return best_i

    if pixels is not None and window > 0:
        return max(
            strong,
            key=lambda p: _peak_vertical_score(
                pixels, p[1], search_left_px, y0, y1, window
            ),
        )[1]

    return max(strong, key=lambda p: p[0])[1]


def _keeper_bbox_from_pixels(
    pixels: Image.Image,
    config: GameConfig,
    *,
    region_left: float,
    region_top: float,
    region_width: float,
    region_height: float,
    hint_x: float | None = None,
) -> KeeperBox | None:
    """BBox centroid from a goal-band image (or full frame)."""
    w, h = pixels.size
    if w == 0 or h == 0:
        return None

    scale_x = w / region_width
    scale_y = h / region_height

    goal_top_px = int((config.goal_top - region_top) * scale_y)
    goal_bottom_px = int((config.goal_bottom - region_top) * scale_y)
    goal_top_px = max(0, min(goal_top_px, h))
    goal_bottom_px = max(0, min(goal_bottom_px, h))

    band = goal_bottom_px - goal_top_px
    if band <= 0:
        return None

    y0 = goal_top_px + int(band * config.keeper_scan_top_frac)
    y1 = goal_top_px + int(band * config.keeper_scan_bottom_frac)

    goal_left_px = int((config.goal_left - region_left) * scale_x)
    goal_right_px = int((config.goal_right - region_left) * scale_x)
    goal_left_px = max(0, min(goal_left_px, w))
    goal_right_px = max(0, min(goal_right_px, w))

    search_left_px = goal_left_px
    search_right_px = goal_right_px
    if hint_x is not None:
        hint_px = int((hint_x - region_left) * scale_x)
        half = int(config.keeper_search_half_width * scale_x)
        search_left_px = max(goal_left_px, hint_px - half)
        search_right_px = min(goal_right_px, hint_px + half)

    counts: list[int] = []
    for x in range(search_left_px, search_right_px):
        count = 0
        for y in range(y0, y1, 2):
            if _is_keeper_pixel(*pixels.getpixel((x, y))):
                count += 1
        counts.append(count)

    window = max(8, int(config.keeper_bbox_width * scale_x))
    peak_i = _pick_peak_column(
        counts,
        config,
        scale_x=scale_x,
        hint_x=hint_x,
        pixels=pixels,
        search_left_px=search_left_px,
        y0=y0,
        y1=y1,
        window=window,
    )
    if peak_i is None:
        return None

    center_px = search_left_px + peak_i
    left_px = int(center_px - window / 2)
    right_px = left_px + window

    top_px = y1
    bottom_px = y0
    for y in range(y0, y1):
        for x in range(max(0, left_px), min(w, right_px), 2):
            if _is_keeper_pixel(*pixels.getpixel((x, y))):
                top_px = min(top_px, y)
                bottom_px = max(bottom_px, y)

    if top_px >= bottom_px:
        return None

    to_x = region_width / w
    to_y = region_height / h
    left = region_left + left_px * to_x
    right = region_left + right_px * to_x
    top = region_top + top_px * to_y
    bottom = region_top + bottom_px * to_y
    return KeeperBox(
        cx=(left + right) / 2,
        cy=(top + bottom) / 2,
        left=left,
        right=right,
        top=top,
        bottom=bottom,
    )


def keeper_bbox(
    png_bytes: bytes,
    config: GameConfig,
    *,
    hint_x: float | None = None,
) -> KeeperBox | None:
    """Locate keeper bbox from a full canvas PNG."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return _keeper_bbox_from_pixels(
        img,
        config,
        region_left=0,
        region_top=0,
        region_width=config.canvas_width,
        region_height=config.canvas_height,
        hint_x=hint_x,
    )


def _js_result_to_box(result: dict[str, float]) -> KeeperBox:
    return KeeperBox(
        cx=result["cx"],
        cy=result["cy"],
        left=result["left"],
        right=result["right"],
        top=result["top"],
        bottom=result["bottom"],
    )


def _js_args(config: GameConfig, hint_x: float | None) -> dict:
    return {
        "goalLeft": config.goal_left,
        "goalTop": config.goal_top,
        "goalRight": config.goal_right,
        "goalBottom": config.goal_bottom,
        "scanTopFrac": config.keeper_scan_top_frac,
        "scanBottomFrac": config.keeper_scan_bottom_frac,
        "bboxWidth": config.keeper_bbox_width,
        "canvasWidth": config.canvas_width,
        "canvasHeight": config.canvas_height,
        "hintX": hint_x,
        "searchHalfWidth": config.keeper_search_half_width,
    }


async def _goal_band_image(canvas: Locator, config: GameConfig) -> Image.Image | None:
    """Crop the goal band from a full canvas element screenshot."""
    try:
        png = await canvas.screenshot()
    except Exception:
        return None
    img = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = img.size
    left = int(config.goal_left * w / config.canvas_width)
    top = int(config.goal_top * h / config.canvas_height)
    right = int(config.goal_right * w / config.canvas_width)
    bottom = int(config.goal_bottom * h / config.canvas_height)
    return img.crop((left, top, right, bottom))


async def detect_keeper_bbox(
    canvas: Locator,
    config: GameConfig,
    *,
    hint_x: float | None = None,
) -> KeeperBox | None:
    """
    Fast path: read goal-band pixels in-page via getImageData.
    Fallback: cropped goal-band screenshot + incremental Python scan.
    """
    try:
        result = await canvas.evaluate(KEEPER_BBOX_JS, _js_args(config, hint_x))
        if result:
            return _js_result_to_box(result)
    except Exception:
        pass

    band_img = await _goal_band_image(canvas, config)
    if band_img is None:
        return None

    return _keeper_bbox_from_pixels(
        band_img,
        config,
        region_left=config.goal_left,
        region_top=config.goal_top,
        region_width=config.goal_right - config.goal_left,
        region_height=config.goal_bottom - config.goal_top,
        hint_x=hint_x,
    )


def width_scale(img_w: int, config: GameConfig) -> float:
    return img_w / config.canvas_width


def height_scale(img_h: int, config: GameConfig) -> float:
    return img_h / config.canvas_height


def _scaled_point(img: Image.Image, point_x: float, point_y: float, config: GameConfig) -> tuple[int, int]:
    w, h = img.size
    return (
        int(point_x * width_scale(w, config)),
        int(point_y * height_scale(h, config)),
    )


def is_lobby_screen(png_bytes: bytes, config: GameConfig) -> bool:
    """True when the big blue Play button is on screen (pre-penalty lobby)."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    bx, by = _scaled_point(img, config.play_button.x, config.play_button.y, config)

    blue_hits = 0
    for dx in range(-30, 31, 4):
        for dy in range(-30, 31, 4):
            x, y = bx + dx, by + dy
            if x < 0 or y < 0 or x >= img.width or y >= img.height:
                continue
            r, g, b = img.getpixel((x, y))
            if b > 100 and b > r + 25 and b > g:
                blue_hits += 1
    return blue_hits >= 12


def is_penalty_ready(png_bytes: bytes, config: GameConfig) -> bool:
    """True when the ball is on the pitch and ready to shoot (not lobby / game over)."""
    if is_lobby_screen(png_bytes, config):
        return False

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    bx, by = _scaled_point(img, config.ball.x, config.ball.y, config)

    bright_grass = 0
    bright_ball = 0
    for dx, dy in ((0, 0), (-8, 0), (8, 0), (0, -8), (0, 8)):
        x, y = bx + dx, by + dy
        if x < 0 or y < 0 or x >= img.width or y >= img.height:
            continue
        r, g, b = img.getpixel((x, y))
        brightness = (r + g + b) / 3
        if _is_grass(r, g, b):
            bright_grass += 1
        if brightness > 160 and abs(r - g) < 40:
            bright_ball += 1

    return bright_grass >= 2 and bright_ball >= 1


def _is_game_over_blue(r: int, g: int, b: int) -> bool:
    """Dark navy full-screen wash on miss; not bright keeper/ball highlights."""
    brightness = (r + g + b) / 3
    if brightness > 120:
        return False
    if g > 100:
        return False
    return r < 45 and g < 55 and b > 60 and b > r + 10 and b > g - 5


def _region_blue_grass_ratios(
    img: Image.Image,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> tuple[float, float]:
    blue = 0
    grass = 0
    total = 0
    for y in range(y0, y1, 6):
        for x in range(x0, x1, 6):
            total += 1
            r, g, b = img.getpixel((x, y))
            if _is_grass(r, g, b):
                grass += 1
            if _is_game_over_blue(r, g, b):
                blue += 1
    if total == 0:
        return 0.0, 0.0
    return blue / total, grass / total


def is_miss_screen(png_bytes: bytes, config: GameConfig) -> bool:
    """
    True on miss / game-over: the pitch behind the goal turns a uniform dark
    blue. Ignores the bottom ball UI and colorful keeper pixels.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size

    # Upper + mid pitch only — away from ball button and keeper kit.
    zones = (
        (int(w * 0.15), int(h * 0.12), int(w * 0.85), int(h * 0.38)),
        (int(w * 0.15), int(h * 0.40), int(w * 0.85), int(h * 0.58)),
    )
    for x0, y0, x1, y1 in zones:
        blue, grass = _region_blue_grass_ratios(img, x0, y0, x1, y1)
        if blue < 0.45 or grass > 0.12:
            return False
    return True


def is_game_over_screen(png_bytes: bytes, config: GameConfig) -> bool:
    """Alias for miss screen (blue wash); kept for call-site compatibility."""
    return is_miss_screen(png_bytes, config)
