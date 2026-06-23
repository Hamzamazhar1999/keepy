#!/usr/bin/env bash
# ============================================================================
#  build.sh - Build a Keepy binary for macOS / Linux
# ----------------------------------------------------------------------------
#  Produces a single-file, windowed (no console) binary at dist/Keepy using
#  PyInstaller.
#
#  NOTE: This produces a NATIVE macOS/Linux binary named "dist/Keepy" - it is
#        NOT a Windows .exe. PyInstaller cannot cross-compile; to get
#        dist/Keepy.exe you must build on Windows (use build.bat) or via the
#        windows-latest GitHub Actions runner.
#
#  Keepy needs NO third-party packages to run; the only build-time dependency
#  is PyInstaller (installed below).
#
#  Usage:  ./build.sh        (run  chmod +x build.sh  once if needed)
# ============================================================================

set -euo pipefail

# Run from the directory this script lives in, so paths are predictable.
cd "$(dirname "$0")"

echo
echo "=== Building Keepy for $(uname -s) ==="
echo

# --- 1. Locate a Python 3 interpreter ---------------------------------------
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[ERROR] Python 3 was not found on your PATH." >&2
    echo "        Install it from https://www.python.org/downloads/ (or your" >&2
    echo "        package manager / Homebrew) and try again." >&2
    exit 1
fi
echo "Using Python: $PY"
"$PY" --version
echo

# --- 2. Install PyInstaller (the only build dependency) ---------------------
echo "Installing/updating PyInstaller..."
"$PY" -m pip install --upgrade pip
"$PY" -m pip install --upgrade pyinstaller
echo

# --- 3. Build a single-file, windowed executable ----------------------------
#  --onefile   : bundle everything into one binary
#  --windowed  : no console/terminal window is spawned
#  --name Keepy : output is named Keepy
#  tkinter is bundled automatically; there are no data files/assets to add.
echo "Running PyInstaller..."
"$PY" -m PyInstaller --onefile --windowed --icon keepy.ico --name Keepy keepy.py

echo
echo "=== Build complete! ==="
echo "Your binary is here:"
echo "    $(pwd)/dist/Keepy"
echo
echo "Reminder: dist/Keepy is a native $(uname -s) binary, NOT a Windows .exe."
echo
