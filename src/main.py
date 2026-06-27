#!/usr/bin/env python3
"""Mini Cup demon — automated penalty shooter for Google Mini Cup."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .browser import GameBrowser, wait_for_user_ready
from .config import GameConfig
from .game_state import wait_after_shot
from .input import swipe_shot
from .strategy import pick_target
from .tracking import KeeperTracker


async def run(args: argparse.Namespace) -> int:
    config = GameConfig()
    browser = GameBrowser(config)

    try:
        page = await browser.start(headed=not args.headless)
        print("Browser started (mobile viewport).")

        if args.auto:
            print(f"Auto mode: opening {args.url}")
            await browser.open_search(args.url)
            opened = await browser.try_open_mini_cup()
            if opened:
                print("Mini Cup overlay opened.")
            await browser.try_start_match(team=args.team)
            print("Waiting for game canvas…")
            canvas = await browser.wait_for_canvas(timeout_ms=args.timeout * 1000)
        else:
            if args.url:
                print(f"Opening {args.url} — navigate to the penalty screen yourself.")
                await browser.open_search(args.url)
            else:
                print("Navigate to Google Mini Cup in the browser window.")
            await wait_for_user_ready()
            print("Waiting for game canvas…")
            canvas = await browser.wait_for_canvas(timeout_ms=args.timeout * 1000)

        print("Canvas found. Shooting in a moment…")
        await asyncio.sleep(0.5)

        goals = 0
        tracker = KeeperTracker()
        for attempt in range(1, args.max_shots + 1):
            await tracker.collect(canvas, config)
            velocity = tracker.lateral_velocity()
            cx = tracker.latest_centroid_x()
            predicted = tracker.predict_centroid_x(config.shot_flight_time)
            target = pick_target(predicted, config, keeper_velocity=velocity)

            if cx is None:
                print(f"Shot {attempt}: keeper not detected — shooting {target.x:.0f}")
            else:
                print(
                    f"Shot {attempt}: keeper cx≈{cx:.0f} v≈{velocity:+.0f}px/s "
                    f"→ predict {predicted:.0f} → target ({target.x:.0f}, {target.y:.0f})"
                )

            if args.save_frames:
                out = Path(args.save_frames)
                out.mkdir(parents=True, exist_ok=True)
                png = await canvas.screenshot()
                (out / f"frame_{attempt:03d}.png").write_bytes(png)

            await swipe_shot(page, canvas, config.ball, target, config)

            result = await wait_after_shot(
                browser, canvas, config, timeout=args.shot_delay
            )
            if result == "miss":
                print(f"Game over after {goals} goal(s).")
                break

            goals += 1
            print(f"Goal {goals} — lining up next shot…")
            await asyncio.sleep(0.3)

        if goals == args.max_shots:
            print(f"Completed {goals} shots without game-over signal.")

        if args.pause:
            print("Paused — close the browser window or press Ctrl+C.")
            await asyncio.sleep(3600)

        return 0

    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Mini Cup penalty bot",
        epilog="By default the bot waits for you to open the game and press Enter before shooting.",
    )
    parser.add_argument(
        "--url",
        default="",
        help="Optional starting URL (e.g. Google Search with fbx=worldcup). Omit to use a blank page.",
    )
    parser.add_argument("--team", default="Norway", help="Team name for --auto menu clicks")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Try to open Mini Cup and start the match automatically (often blocked by Google)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without visible browser (often blocked by Google)",
    )
    parser.add_argument("--max-shots", type=int, default=50, help="Max penalties to attempt")
    parser.add_argument("--shot-delay", type=float, default=1.8, help="Seconds between shots")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds to wait for canvas after you press Enter")
    parser.add_argument("--save-frames", type=str, default="", help="Directory to save screenshots")
    parser.add_argument("--pause", action="store_true", help="Keep browser open after run")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
