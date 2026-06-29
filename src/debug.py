"""Terminal and on-canvas debug helpers for keeper prediction."""

from __future__ import annotations

from playwright.async_api import Locator

from .config import GameConfig

_OVERLAY_JS = """
(canvas, args) => {
  const {
    keeperX, predictedX, goalTop, goalBottom, goalLeft, goalRight,
    canvasWidth, canvasHeight, shootLeft,
  } = args;

  const id = "mcd-prediction-debug";
  let root = document.getElementById(id);
  if (!root) {
    root = document.createElement("div");
    root.id = id;
    root.style.position = "fixed";
    root.style.pointerEvents = "none";
    root.style.zIndex = "2147483647";
    document.body.appendChild(root);
  }
  root.replaceChildren();

  const rect = canvas.getBoundingClientRect();
  const sx = rect.width / canvasWidth;
  const sy = rect.height / canvasHeight;

  root.style.left = `${rect.left}px`;
  root.style.top = `${rect.top}px`;
  root.style.width = `${rect.width}px`;
  root.style.height = `${rect.height}px`;

  function line(x, color, label) {
    const el = document.createElement("div");
    el.style.position = "absolute";
    el.style.left = `${x * sx - 1}px`;
    el.style.top = `${goalTop * sy}px`;
    el.style.width = "2px";
    el.style.height = `${(goalBottom - goalTop) * sy}px`;
    el.style.background = color;
    el.style.boxShadow = `0 0 4px ${color}`;
    const tag = document.createElement("div");
    tag.textContent = label;
    tag.style.position = "absolute";
    tag.style.left = "4px";
    tag.style.top = "-18px";
    tag.style.font = "bold 11px monospace";
    tag.style.color = color;
    tag.style.textShadow = "0 0 3px #000, 0 0 3px #000";
    tag.style.whiteSpace = "nowrap";
    el.appendChild(tag);
    root.appendChild(el);
  }

  function band(left, right, color) {
    const el = document.createElement("div");
    el.style.position = "absolute";
    el.style.left = `${left * sx}px`;
    el.style.top = `${goalTop * sy}px`;
    el.style.width = `${(right - left) * sx}px`;
    el.style.height = `${(goalBottom - goalTop) * sy}px`;
    el.style.background = color;
    el.style.opacity = "0.18";
    root.appendChild(el);
  }

  const mid = (goalLeft + goalRight) / 2;
  band(goalLeft, mid, shootLeft ? "#22c55e" : "#ef4444");
  band(mid, goalRight, shootLeft ? "#ef4444" : "#22c55e");

  if (keeperX != null) line(keeperX, "#38bdf8", `now ${Math.round(keeperX)}`);
  line(predictedX, "#fbbf24", `pred ${Math.round(predictedX)}`);
  line(mid, "#a3a3a3", "mid");

  const hud = document.createElement("div");
  hud.textContent = `shoot ${shootLeft ? "LEFT" : "RIGHT"} | pred x=${Math.round(predictedX)}`;
  hud.style.position = "absolute";
  hud.style.left = "6px";
  hud.style.bottom = "6px";
  hud.style.padding = "4px 8px";
  hud.style.font = "bold 12px monospace";
  hud.style.color = "#fff";
  hud.style.background = "rgba(0,0,0,0.65)";
  hud.style.borderRadius = "4px";
  root.appendChild(hud);
}
"""

_CLEAR_OVERLAY_JS = """
() => {
  const el = document.getElementById("mcd-prediction-debug");
  if (el) el.remove();
}
"""


def format_prediction_debug(
    *,
    keeper_x: float | None,
    predicted_x: float,
    velocity: float,
    config: GameConfig,
    lead_time: float,
    shoot_left: bool,
    target_x: float,
) -> str:
    mid = (config.goal_left + config.goal_right) / 2
    if abs(velocity) >= config.keeper_slow_velocity:
        rule = f"velocity ({velocity:+.0f} px/s → keeper moving {'right' if velocity > 0 else 'left'})"
    else:
        side = "right of" if predicted_x > mid else "left of"
        rule = f"prediction (pred {side} mid {mid:.0f})"

    lines = [
        f"  keeper now:      x={keeper_x:.0f}" if keeper_x is not None else "  keeper now:      (not detected)",
        f"  keeper predicted:x={predicted_x:.0f}  (lead {lead_time:.2f}s)",
        f"  goal:            x=[{config.goal_left:.0f}, {config.goal_right:.0f}]  mid={mid:.0f}",
        f"  shoot:           {'LEFT' if shoot_left else 'RIGHT'} → target x={target_x:.0f}",
        f"  rule:            {rule}",
    ]
    return "\n".join(lines)


async def show_prediction_overlay(
    canvas: Locator,
    config: GameConfig,
    *,
    keeper_x: float | None,
    predicted_x: float,
    shoot_left: bool,
) -> None:
    await canvas.evaluate(
        _OVERLAY_JS,
        {
            "keeperX": keeper_x,
            "predictedX": predicted_x,
            "goalTop": config.goal_top,
            "goalBottom": config.goal_bottom,
            "goalLeft": config.goal_left,
            "goalRight": config.goal_right,
            "canvasWidth": config.canvas_width,
            "canvasHeight": config.canvas_height,
            "shootLeft": shoot_left,
        },
    )


async def clear_prediction_overlay(canvas: Locator) -> None:
    await canvas.evaluate(_CLEAR_OVERLAY_JS)
