"""Read keeper position from canvas screenshots."""

from __future__ import annotations

import io

from PIL import Image

from .config import GameConfig


def _is_grass(r: int, g: int, b: int) -> bool:
    return g > r + 15 and g > b + 10 and g > 80


def keeper_center_x(png_bytes: bytes, config: GameConfig) -> float:
    """
    Estimate goalkeeper horizontal center by finding the densest
    non-grass column in the goal band.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    width, _ = img.size

    goal_top = int(config.goal_top * height_scale(img.height, config))
    goal_bottom = int(config.goal_bottom * height_scale(img.height, config))
    left = int(config.goal_left * width_scale(img.width, config))
    right = int(config.goal_right * width_scale(img.width, config))

    best_x = width // 2
    best_score = 0

    for x in range(left, right, 2):
        score = 0
        for y in range(goal_top, goal_bottom, 3):
            r, g, b = img.getpixel((x, y))
            if not _is_grass(r, g, b):
                score += 1
        if score > best_score:
            best_score = score
            best_x = x

    return best_x * (config.canvas_width / img.width)


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


def is_game_over_screen(png_bytes: bytes, config: GameConfig) -> bool:
    """Heuristic: end screen is mostly dark UI, not green pitch."""
    if is_lobby_screen(png_bytes, config):
        return False

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    grass = 0
    samples = 0
    for y in range(int(h * 0.35), int(h * 0.85), 8):
        for x in range(int(w * 0.1), int(w * 0.9), 8):
            r, g, b = img.getpixel((x, y))
            samples += 1
            if _is_grass(r, g, b):
                grass += 1
    return samples > 0 and grass / samples < 0.25
