"""Pick shot targets from predicted keeper position."""

from __future__ import annotations

from .config import GameConfig, Point


def _shoot_left(
    predicted_keeper_x: float,
    config: GameConfig,
    keeper_velocity: float,
) -> bool:
    mid = (config.goal_left + config.goal_right) / 2
    if abs(keeper_velocity) >= config.keeper_slow_velocity:
        # Keeper moving — shoot the far side they're traveling toward.
        return keeper_velocity > 0
    return predicted_keeper_x > mid


def pick_target(
    predicted_keeper_x: float,
    config: GameConfig,
    *,
    keeper_velocity: float = 0.0,
    keeper_x: float | None = None,
) -> Point:
    """
    Aim at the open side of the net.

    Moving keeper: shoot the opposite side from travel direction (they slow
    near posts, so velocity points toward the occupied side).
    Slow keeper: use sinusoidal prediction at ball arrival.
    """
    del keeper_x  # reserved for future position-aware heuristics
    shoot_left = _shoot_left(predicted_keeper_x, config, keeper_velocity)
    if shoot_left:
        return Point(config.goal_left + config.margin, config.shot_y)
    return Point(config.goal_right - config.margin, config.shot_y)
