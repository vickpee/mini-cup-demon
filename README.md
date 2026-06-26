# mini-cup-demon

Automated penalty shooter for [Google Mini Cup](https://www.google.com/search?q=world+cup&fbx=worldcup) (mobile search easter egg).

Uses Playwright to drive a mobile Chrome session, reads the game `canvas[jsname="mECglb"]`, detects the goalkeeper from pixels, and swipes toward the open corner.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chrome
```

Requires **Google Chrome** installed (`channel="chrome"`).

## Run

**Default** — you open the game, press Enter when ready, then the bot shoots:

```bash
python run.py --pause
```

1. Browser opens (mobile viewport).
2. Open Mini Cup, tap **Play**, wait until the ball is on the pitch.
3. **Press Enter** in the terminal — bot shoots immediately (no lobby handling).

Optional starting URL (still waits for Enter before shooting):

```bash
python run.py --url "https://www.google.com/search?q=Norway+vs+France&fbx=worldcup" --pause
```

**Auto-open** (may hit CAPTCHA — opt-in only):

```bash
python run.py --auto --team Norway --pause
```

**Calibrate** — save canvas frames to tune `src/config.py`:

```bash
python calibrate.py
```

**Save frames for debugging:**

```bash
python run.py --save-frames screenshots --max-shots 5
```

## Options

| Flag | Description |
|------|-------------|
| *(default)* | You tap Play and get the ball ready; press **Enter** to shoot |
| `--url URL` | Open this page first (bot still waits for Enter) |
| `--auto` | Try to open Mini Cup and pick team automatically |
| `--team Norway` | Team name for `--auto` menu clicks |
| `--headless` | Headless mode (often blocked by Google) |
| `--max-shots 50` | Stop after N attempts |
| `--shot-delay 1.8` | Pause between shots (seconds) |
| `--pause` | Keep browser open after run |

## How it works

1. **Browser** — mobile viewport (476×594), touch enabled, `en-CA` locale.
2. **Vision** — screenshot canvas; scan goal band for non-grass columns → keeper X.
3. **Strategy** — shoot to the opposite corner with a margin.
4. **Input** — interpolated mouse drag from ball → target in canvas coordinates (451×594 internal).

Tune ball position, goal bounds, and margins in `src/config.py` after running `calibrate.py`.

## Notes

- Google may show CAPTCHAs on automated Search traffic; open the game yourself and use Enter to start.
- Keeper detection is color-heuristic; adjust after inspecting saved frames.
- One miss ends the run in Mini Cup — the bot stops when it sees game-over UI text.
