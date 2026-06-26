"""Read keeper position from canvas screenshots."""

from __future__ import annotations

import io

from PIL import Image

from .config import GameConfig, KeeperBox


def _is_grass(r: int, g: int, b: int) -> bool:
    return g > r + 15 and g > b + 10 and g > 80


def _is_keeper_pixel(r: int, g: int, b: int) -> bool:
    """Colorful pixels in the goal band (keeper kit), not grass or gray net."""
    if _is_grass(r, g, b):
        return False
    if max(r, g, b) - min(r, g, b) < 35:
        return False
    return True


def keeper_bbox(png_bytes: bytes, config: GameConfig) -> KeeperBox | None:
    """
    Locate the goalkeeper via a saturated-pixel bounding box in the lower
    goal band, then return its centroid in canvas coordinates.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size

    goal_top = int(config.goal_top * height_scale(h, config))
    goal_bottom = int(config.goal_bottom * height_scale(h, config))
    goal_left = int(config.goal_left * width_scale(w, config))
    goal_right = int(config.goal_right * width_scale(w, config))

    band = goal_bottom - goal_top
    y0 = goal_top + int(band * config.keeper_scan_top_frac)
    y1 = goal_top + int(band * config.keeper_scan_bottom_frac)

    counts: list[int] = []
    for x in range(goal_left, goal_right):
        count = 0
        for y in range(y0, y1, 2):
            if _is_keeper_pixel(*img.getpixel((x, y))):
                count += 1
        counts.append(count)

    window = max(8, int(config.keeper_bbox_width * width_scale(w, config)))
    if len(counts) <= window:
        return None

    best_sum = 0
    best_start = 0
    for i in range(len(counts) - window):
        total = sum(counts[i : i + window])
        if total > best_sum:
            best_sum = total
            best_start = i

    if best_sum < 12:
        return None

    left_px = goal_left + best_start
    right_px = goal_left + best_start + window

    top_px = y1
    bottom_px = y0
    for y in range(y0, y1):
        for x in range(left_px, right_px, 2):
            if _is_keeper_pixel(*img.getpixel((x, y))):
                top_px = min(top_px, y)
                bottom_px = max(bottom_px, y)

    if top_px >= bottom_px:
        return None

    to_x = config.canvas_width / w
    to_y = config.canvas_height / h
    left = left_px * to_x
    right = right_px * to_x
    top = top_px * to_y
    bottom = bottom_px * to_y
    return KeeperBox(
        cx=(left + right) / 2,
        cy=(top + bottom) / 2,
        left=left,
        right=right,
        top=top,
        bottom=bottom,
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
