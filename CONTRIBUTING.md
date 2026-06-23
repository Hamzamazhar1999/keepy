# Contributing to Keepy

Thanks for your interest in Keepy, the tiny always-on-top pixel-art desktop pet
that juggles a football, plays a rally game, a penalty shootout, and a DVD
bounce mode, idles with little animations, and nudges you to take breaks.

Keepy is deliberately small and dependency-free. Please keep it that way.

## Run from source

You need **Python 3** (3.8+). That's it. Keepy uses only the Python standard
library, so there is nothing to `pip install` to run it.

```sh
python keepy.py
```

(`python3 keepy.py` on macOS/Linux.)

- On **Windows** you get true colour-key transparency and click-through.
- On **macOS/Linux** it still runs, just without the transparency.
- Sound uses the built-in `winsound` on Windows, with a `print("\a")` fallback
  elsewhere. Optional custom WAV playback uses `winsound.PlaySound` / `afplay`
  / `aplay` / `paplay` if available.
- Custom per-action sounds are saved to `~/.keepy/sounds.json`. No other files
  are written and no image assets are needed - all art is drawn in code.

Right-click Keepy for the menu: games, timers, break reminders, mute, the
"Customize sounds" submenu, wander mode, and quit.

## Code style

- **Standard library only.** No third-party runtime dependencies, ever. If you
  reach for a `pip install`, find another way.
- **Single file.** All of Keepy lives in `keepy.py`. Keep it that way - new
  features go in the same file rather than spawning new modules.
- Pure Python 3, GUI via `tkinter`. Match the existing formatting (4-space
  indent, descriptive names, the lightly commented section banners already in
  the file).
- Prefer small, self-contained additions that don't break the no-deps,
  one-file promise. All artwork is drawn in code - no binary assets.

## Building the Windows .exe

End users get a double-click `Keepy.exe`. It is built with PyInstaller:

```sh
pyinstaller --onefile --windowed --name Keepy keepy.py
```

`--windowed` hides the console window; `tkinter` is bundled automatically and
`winsound` is a builtin, so no `--hidden-import` is needed. Since Keepy ships no
image assets, no `--add-data` is required either. The output is a single file:
`dist/Keepy.exe`. A `Keepy.spec` file is also provided for `pyinstaller Keepy.spec`.

CI (GitHub Actions, `windows-latest`, Python 3.12) builds this automatically:
it uploads `Keepy.exe` as a build artifact on every push, and attaches it to a
GitHub Release when a `vX.Y.Z` tag is pushed. Non-technical users just download
the `.exe` from the Releases page.

## Submitting changes

1. Test `python keepy.py` actually launches and behaves before opening a PR.
2. Keep the diff focused and within `keepy.py`.
3. Describe what you changed and how you verified it.

By contributing you agree your work is licensed under the project's MIT License.
