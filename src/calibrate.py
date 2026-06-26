#!/usr/bin/env python3
"""Save canvas frames and print click coordinates for manual calibration."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .browser import GameBrowser, wait_for_user_ready
from .config import GameConfig


async def run(args: argparse.Namespace) -> int:
    config = GameConfig()
    browser = GameBrowser(config)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        await browser.start(headed=True)
        print("Browser started.")

        if args.auto:
            await browser.open_search(args.url or config.default_search_url)
            await browser.try_open_mini_cup()
            await browser.try_start_match(team=args.team)
        elif args.url:
            await browser.open_search(args.url)

        await wait_for_user_ready(
            "Get to the penalty screen with the ball ready.\n"
            "Press Enter here when ready to capture frames…"
        )

        canvas = await browser.wait_for_canvas()
        assert browser.page is not None

        for i in range(args.frames):
            png = await canvas.screenshot()
            path = out_dir / f"calibrate_{i:03d}.png"
            path.write_bytes(png)
            print(f"Saved {path}")

            box = await canvas.bounding_box()
            if box:
                meta = {
                    "bounding_box": box,
                    "canvas_width": config.canvas_width,
                    "canvas_height": config.canvas_height,
                    "defaults": {
                        "ball": [config.ball.x, config.ball.y],
                        "goal": [
                            config.goal_left,
                            config.goal_top,
                            config.goal_right,
                            config.goal_bottom,
                        ],
                    },
                }
                (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))

            await asyncio.sleep(args.interval)

        print(f"\nFrames in {out_dir}/")
        print("Tune src/config.py using meta.json and your frame images.")
        return 0

    except KeyboardInterrupt:
        return 0
    finally:
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Mini Cup canvas zones")
    parser.add_argument("--url", default="", help="Optional starting URL")
    parser.add_argument("--team", default="Norway", help="Team name for --auto")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Try to open Mini Cup automatically before you press Enter",
    )
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--output", default="screenshots")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
