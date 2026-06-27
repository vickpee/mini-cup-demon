"""Pick shot targets from predicted keeper position."""

from __future__ import annotations

from .config import GameConfig, Point


def pick_target(
    predicted_keeper_x: float,
    config: GameConfig,
    *,
    keeper_velocity: float = 0.0,
) -> Point:
    """
    Aim at the open side of the net, using predicted keeper position
    (centroid + velocity extrapolation) at ball arrival time.
    """
    mid = (config.goal_left + config.goal_right) / 2
    lead = abs(predicted_keeper_x - mid)

    if lead < 20 and abs(keeper_velocity) > 5:
        shoot_left = keeper_velocity > 0
    else:
        shoot_left = predicted_keeper_x > mid

    if shoot_left:
        return Point(config.goal_left + config.margin, config.shot_y)
    return Point(config.goal_right - config.margin, config.shot_y)
