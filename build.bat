@echo off
REM ===========================================================================
REM  build.bat - Build Keepy.exe for Windows (double-click .exe)
REM ---------------------------------------------------------------------------
REM  Produces a single-file, windowed (no console) executable at dist\Keepy.exe
REM  using PyInstaller. Keepy itself needs NO third-party packages to run - the
REM  only build-time dependency is PyInstaller (installed below).
REM
REM  Usage: just double-click this file, or run  build.bat  from a terminal.
REM ===========================================================================

setlocal enableextensions
REM Run from the folder this script lives in, so paths are predictable.
cd /d "%~dp0"

echo(
echo === Building Keepy for Windows ===
echo(

REM --- 1. Locate a Python interpreter ---------------------------------------
REM  Prefer the 'py' launcher (ships with python.org installers); fall back to
REM  'python' on PATH.
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python was not found on your PATH.
    echo         Install Python 3 from https://www.python.org/downloads/
    echo         and be sure to tick "Add Python to PATH" during setup.
    pause
    exit /b 1
)
echo Using Python launcher: %PY%
%PY% --version
echo(

REM --- 2. Install PyInstaller (the only build dependency) -------------------
echo Installing/updating PyInstaller...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)
echo(

REM --- 3. Build a single-file, windowed executable -------------------------
REM  --onefile   : bundle everything into one Keepy.exe
REM  --windowed  : no console window pops up behind the pet
REM  --name Keepy : output is named Keepy.exe
REM  tkinter is bundled automatically; winsound is a builtin (no hidden import
REM  needed); there are no data files/assets to add.
echo Running PyInstaller...
%PY% -m PyInstaller --onefile --windowed --icon keepy.ico --name Keepy keepy.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo(
echo === Build complete! ===
echo Your executable is here:
echo     %cd%\dist\Keepy.exe
echo(
echo Double-click dist\Keepy.exe to run Keepy. You can share that single file.
echo(
pause
endlocal
