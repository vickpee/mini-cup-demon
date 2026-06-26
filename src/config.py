"""Game geometry and tuning defaults for 451×594 canvas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class GameConfig:
    canvas_width: int = 451
    canvas_height: int = 594
    canvas_selector: str = 'canvas[jsname="mECglb"]'

    ball: Point = Point(225, 520)
    play_button: Point = Point(225, 510)
    goal_left: float = 80
    goal_right: float = 370
    goal_top: float = 100
    goal_bottom: float = 280
    shot_y: float = 150
    margin: float = 50

    swipe_steps: int = 25
    swipe_step_ms: int = 12

    default_search_url: str = (
        "https://www.google.com/search?q=Norway+vs+France&fbx=worldcup"
    )
