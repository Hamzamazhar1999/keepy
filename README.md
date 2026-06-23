# Keepy

A tiny always-on-top pixel-art desktop pet who lives on your screen, juggles a football with his head and feet, boots it off your screen edges, plays games with you, and nudges you to take breaks.

Keepy is a single Python file drawn entirely in code — no image assets, no third-party packages. The football has real gravity-and-bounce physics and lives in its own little transparent window, so Keepy can volley it around your actual desktop. On Windows he is fully transparent and click-through; on macOS and Linux he runs in a small framed window instead.

## Features

- **Endless juggling** — keepy-ups, headers, and around-the-world tricks that flow seamlessly into one another, plus the occasional wall kick where he boots the ball off the nearest screen edge and traps the rebound.
- **Rally game** — Keepy serves the ball; click it mid-air to volley it back. You get **3 lives**, every rally speeds the ball up, and a missed ball costs a life. Build the longest **streak** you can.
- **Penalty shootout** — a sudden-death keeper challenge in its own arena: drag to aim, pull back for power, curve your swipe to bend the ball. One miss and you're out. Beat your best run.
- **DVD bounce mode** — Keepy glides corner-to-corner like the old DVD logo, changing colour on every wall bounce and celebrating the rare perfect corner hit.
- **Idle animations** — when left alone he juggles, blinks, fidgets, and runs through ball-free moods: yawning, stretching, napping (with Zzz), pondering, dancing, waving, whistling, head-bopping, and more.
- **Break and timer reminders** — a configurable break interval (default every 30 minutes) plus one-off timers, each with a speech bubble and a sound.
- **Customizable sounds** — replace the default beeps with your own `.wav` file for any action (pat, kick, volley/goal, miss, game over, break, timer).
- **Multi-monitor aware** — the ball bounces within whichever monitor Keepy is sitting on, and a frantic timer alert can sweep the ball across every monitor.
- **Wander mode** — let Keepy slowly roam around the screen on his own.

## Install (for normal users — Windows)

1. Go to the [Releases](../../releases) page.
2. Download **`Keepy.exe`** from the latest release.
3. Double-click it. That's it — no installer, no Python needed.

> **Windows SmartScreen note:** because the `.exe` isn't code-signed, Windows may show a blue "Windows protected your PC" dialog the first time you run it. Click **More info**, then **Run anyway**. This is expected for small open-source apps.

To quit Keepy, right-click him and choose **Quit**.

## Run from source

Keepy needs only **Python 3.8+** and uses the standard library only (Tkinter, which ships with Python). There are **no dependencies to install**.

```bash
python keepy.py
```

On most systems `tkinter` is included with Python. On some Linux distros you may need to install it separately (for example `sudo apt install python3-tk`).

## Controls

| Action | What it does |
| --- | --- |
| **Left-click + drag** | Pick Keepy up and move him anywhere on screen |
| **Quick left-click** (no drag) | Pat / boop him — he hops, spins, squashes, or wiggles |
| **Right-click** | Open the menu (games, timers, sounds, settings, quit) |
| **Click the ball mid-air** | In the rally game, volley the serve back |
| **Drag in the arena** | In the penalty shootout, aim and power your shot (pull back further = harder; curve the swipe to bend it) |
| **Click Keepy after game over** | Start a fresh rally |

### Right-click menu

- **Play football!** — start the rally game (3 lives, streaks)
- **Penalty shootout** — sudden-death keeper challenge
- **DVD bounce mode** — corner-bouncing screensaver mode
- **Take a break now** — trigger a break reminder immediately
- **Pause / Resume break reminders**
- **Set break interval...** — change how often Keepy nudges you
- **Set a one-off timer...** — a single countdown reminder
- **Mute / Unmute sounds**
- **Customize sounds** — pick a custom `.wav` per action (see below)
- **Wander mode** — let Keepy roam on his own
- **Quit**

## Customizing sounds

Right-click Keepy → **Customize sounds**, then pick the action you want to change:

- Pat / boop
- Kick
- Good volley / goal
- Miss / save
- Game over
- Break reminder
- Timer

For each one, choose **Choose WAV file...** and select a `.wav` file — it plays a quick preview and is used from then on. **Reset to default beep** restores the built-in tune for that action, and **Reset all to default beeps** clears everything.

Your choices are saved to `~/.keepy/sounds.json` (that's `C:\Users\<you>\.keepy\sounds.json` on Windows). This is the only file Keepy writes — there are no other data files or image assets.

Custom WAV playback uses `winsound` on Windows and falls back to `afplay` / `aplay` / `paplay` on macOS and Linux.

## Build your own exe

Want to build `Keepy.exe` yourself on Windows? Use [PyInstaller](https://pyinstaller.org):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon keepy.ico --name Keepy keepy.py
```

The result is a single file at `dist/Keepy.exe`.

- `--onefile` bundles everything into one `.exe`.
- `--windowed` stops a console window from popping up behind Keepy.
- Tkinter is bundled automatically, and `winsound` is a Python builtin, so no `--hidden-import` is needed.
- Keepy uses no image assets, so no `--add-data` is needed.

For convenience, a [`build.bat`](build.bat) script runs the same command — just double-click it on Windows. There's also a [`build.sh`](build.sh) for macOS/Linux (which produces a native binary, not a Windows `.exe`), and a [`Keepy.spec`](Keepy.spec) file so power users can build with `pyinstaller Keepy.spec`.

This repo also ships a GitHub Actions workflow at [`.github/workflows/build.yml`](.github/workflows/build.yml) that builds the Windows `.exe` on a `windows-latest` runner (using Python 3.12). On every push it uploads `Keepy.exe` as a build artifact, and when you push a tag like `v1.0.0` it attaches `Keepy.exe` to a GitHub Release so end users can download it from the Releases page. (Keepy itself runs on Python 3.8+; 3.12 is just the interpreter CI happens to build with.)

## Platform notes

- **Windows** — the full experience: true colour-key transparency (Keepy and the ball have no visible window box) and click-through on the transparent areas.
- **macOS / Linux** — Keepy runs, juggles, and plays, but without transparency (he sits in a small framed window with a solid background). The penalty arena is opaque on all platforms by design.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). A few things to keep in mind:

- Keepy is intentionally a **single file** (`keepy.py`) using the **Python standard library only** — please don't add third-party runtime dependencies.
- All art is drawn in code as pixel grids; there are no image files to add.
- Test on Windows where possible, since that's where the transparency and click-through behaviour live.

## License

MIT License — Copyright (c) 2026 Hamza Bin Mazhar. See [LICENSE](LICENSE) for details.
