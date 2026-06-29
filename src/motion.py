"""Sinusoidal motion fit for oscillating keeper."""

from __future__ import annotations

import math


def fit_sinusoid(
    samples: list[tuple[float, float]],
) -> tuple[float, float, float, float] | None:
    """
    Fit x(t) = center + amplitude * sin(omega * t + phase).

    Times are normalized to start at zero (callers may pass absolute monotonic
    clocks — only elapsed time matters).

    Returns (center, amplitude, omega, phase) or None if fit fails.
    """
    if len(samples) < 4:
        return None

    t0 = samples[0][0]
    times = [t - t0 for t, _ in samples]
    xs = [x for _, x in samples]
    center = sum(xs) / len(xs)
    demeaned = [x - center for x in xs]

    best: tuple[float, float, float, float, float] | None = None
    # Keeper period is typically ~1–3 s → omega roughly 2–6 rad/s.
    for step in range(8, 40):
        omega = step * 0.25
        sin_v = [math.sin(omega * t) for t in times]
        cos_v = [math.cos(omega * t) for t in times]

        s11 = sum(s * s for s in sin_v)
        s22 = sum(c * c for c in cos_v)
        s12 = sum(sin_v[i] * cos_v[i] for i in range(len(times)))
        sy1 = sum(demeaned[i] * sin_v[i] for i in range(len(times)))
        sy2 = sum(demeaned[i] * cos_v[i] for i in range(len(times)))

        det = s11 * s22 - s12 * s12
        if abs(det) < 1e-9:
            continue

        a = (sy1 * s22 - sy2 * s12) / det
        b = (sy2 * s11 - sy1 * s12) / det
        amplitude = math.hypot(a, b)
        if amplitude < 8:
            continue

        sse = sum(
            (demeaned[i] - a * sin_v[i] - b * cos_v[i]) ** 2
            for i in range(len(times))
        )
        phase = math.atan2(b, a)
        if best is None or sse < best[0]:
            best = (sse, center, amplitude, omega, phase)

    if best is None:
        return None
    _, center, amplitude, omega, phase = best
    return center, amplitude, omega, phase


def predict_sinusoid(
    center: float,
    amplitude: float,
    omega: float,
    phase: float,
    t: float,
) -> float:
    return center + amplitude * math.sin(omega * t + phase)
