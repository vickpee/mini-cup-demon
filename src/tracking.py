"""Track goalkeeper lateral motion via bbox centroid samples."""

from __future__ import annotations

import asyncio
import time

from playwright.async_api import Locator

from .config import GameConfig, KeeperBox
from .vision import keeper_bbox


class KeeperTracker:
    def __init__(self) -> None:
        self._samples: list[tuple[float, float, KeeperBox]] = []

    def clear(self) -> None:
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
        self.clear()
        n = samples if samples is not None else config.track_samples
        delay = (interval_ms if interval_ms is not None else config.track_interval_ms) / 1000

        for _ in range(n):
            png = await canvas.screenshot()
            box = keeper_bbox(png, config)
            if box is not None:
                self.add(box)
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
        """Extrapolate keeper centroid forward by lead_time seconds."""
        if not self._samples:
            return 0.0
        _, cx, _ = self._samples[-1]
        return cx + self.lateral_velocity() * lead_time
