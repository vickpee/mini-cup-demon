"""Game geometry and tuning defaults for 451×594 canvas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class KeeperBox:
    """Goalkeeper bounding box in canvas coordinates."""

    cx: float
    cy: float
    left: float
    right: float
    top: float
    bottom: float


@dataclass(frozen=True)
class GameConfig:
    canvas_width: int = 451
    canvas_height: int = 594
    canvas_selector: str = 'canvas[jsname="mECglb"]'

    ball: Point = Point(225, 565)
    play_button: Point = Point(225, 565)
    goal_left: float = 80
    goal_right: float = 370
    goal_top: float = 100
    goal_bottom: float = 280
    shot_y: float = 150
    margin: float = 50

    swipe_steps: int = 8
    swipe_step_ms: int = 4

    # Keeper tracking (bbox centroid + sinusoidal motion).
    track_samples: int = 8
    track_interval_ms: int = 50
    keeper_bbox_width: float = 95
    keeper_scan_top_frac: float = 0.55
    keeper_scan_bottom_frac: float = 1.0
    keeper_search_half_width: float = 110
    shot_flight_time: float = 0.55
    keeper_slow_velocity: float = 12

    default_search_url: str = (
        "https://www.google.com/search?q=Norway+vs+France&fbx=worldcup"
    )


def shot_lead_time(config: GameConfig, *, extra_delay: float = 0.0) -> float:
    """Seconds from last keeper sample to expected ball-at-net time."""
    swipe_s = config.swipe_steps * config.swipe_step_ms / 1000.0
    return swipe_s + extra_delay + config.shot_flight_time
