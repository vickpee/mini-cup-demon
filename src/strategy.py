"""Pick shot targets given keeper position."""

from __future__ import annotations

from .config import GameConfig, Point


def pick_target(keeper_x: float, config: GameConfig) -> Point:
    mid = (config.goal_left + config.goal_right) / 2
    if keeper_x < mid:
        return Point(config.goal_right - config.margin, config.shot_y)
    return Point(config.goal_left + config.margin, config.shot_y)
