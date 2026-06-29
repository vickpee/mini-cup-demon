"""Track goalkeeper lateral motion via bbox centroid samples."""

from __future__ import annotations

import asyncio
import time

from playwright.async_api import Locator

from .config import GameConfig, KeeperBox
from .motion import fit_sinusoid, predict_sinusoid
from .vision import detect_keeper_bbox


class KeeperTracker:
    def __init__(self) -> None:
        self._samples: list[tuple[float, float, KeeperBox]] = []

    def clear_samples(self) -> None:
        self._samples.clear()

    @property
    def samples(self) -> list[tuple[float, float, KeeperBox]]:
        return list(self._samples)

    def add(self, box: KeeperBox, *, at: float | None = None) -> None:
        self._samples.append((at if at is not None else time.monotonic(), box.cx, box))

    async def collect(
        self,
        canvas: Locator,
        config: GameConfig,
        *,
        samples: int | None = None,
        interval_ms: int | None = None,
    ) -> bool:
        """Sample keeper bbox centroids; return False if never detected."""
        self.clear_samples()
        n = samples if samples is not None else config.track_samples
        delay = (interval_ms if interval_ms is not None else config.track_interval_ms) / 1000
        hint: float | None = None

        for i in range(n):
            # Full goal scan on the first sample; narrow search only within this burst.
            box = await detect_keeper_bbox(
                canvas, config, hint_x=hint if i > 0 else None
            )
            if box is not None:
                self.add(box)
                hint = box.cx
            if delay > 0:
                await asyncio.sleep(delay)

        return len(self._samples) >= 2

    def lateral_velocity(self) -> float:
        """Canvas pixels per second (positive = moving right)."""
        if len(self._samples) < 2:
            return 0.0

        t0, x0, _ = self._samples[0]
        t1, x1, _ = self._samples[-1]
        dt = t1 - t0
        if dt < 0.02:
            return 0.0
        return (x1 - x0) / dt

    def latest_centroid_x(self) -> float | None:
        if not self._samples:
            return None
        return self._samples[-1][1]

    def predict_centroid_x(self, lead_time: float) -> float:
        """Predict keeper x at ball arrival using sinusoidal fit, else linear."""
        if not self._samples:
            return 0.0

        t0 = self._samples[0][0]
        rel = [(t - t0, x) for t, x, _ in self._samples]
        t_last_rel = self._samples[-1][0] - t0
        _, cx, _ = self._samples[-1]
        velocity = self.lateral_velocity()
        linear = cx + velocity * lead_time

        fit = fit_sinusoid(rel)
        if fit is None:
            return linear

        center, amplitude, omega, phase = fit
        sin_pred = predict_sinusoid(
            center, amplitude, omega, phase, t_last_rel + lead_time
        )

        # Reject sin extrapolation that fights observed motion direction.
        if abs(velocity) > 8 and (sin_pred - cx) * velocity < 0:
            return linear
        return sin_pred

    def using_sinusoid(self) -> bool:
        t0 = self._samples[0][0]
        rel = [(t - t0, x) for t, x, _ in self._samples]
        return fit_sinusoid(rel) is not None
