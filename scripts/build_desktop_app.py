#!/usr/bin/env python3
"""Build a standalone desktop launcher with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "ESRS Municipal Spending Tool"
DIST_DIR = PROJECT_ROOT / "dist" / "desktop"
BUILD_ROOT = PROJECT_ROOT / "build" / "desktop"
SPEC_DIR = BUILD_ROOT / "spec"
WORK_DIR = BUILD_ROOT / "work"
PYINSTALLER_CONFIG_DIR = BUILD_ROOT / "pyinstaller-cache"
ENTRYPOINT = PROJECT_ROOT / "desktop_launcher.py"
ICONS_DIR = PROJECT_ROOT / "static" / "icons"


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except Exception as exc:
        raise SystemExit(
            "PyInstaller is not installed. Run:\n"
            "  python3 -m pip install pyinstaller\n"
            "and then try again."
        ) from exc


def _add_data_arg(source: str, target: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{PROJECT_ROOT / source}{separator}{target}"


def _clean_output() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)


def main() -> None:
    _ensure_pyinstaller()
    _clean_output()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--add-data",
        _add_data_arg("static", "static"),
        "--add-data",
        _add_data_arg("samples", "samples"),
        "--add-data",
        _add_data_arg("docs", "docs"),
        str(ENTRYPOINT),
    ]

    if sys.platform == "darwin":
        command.extend(
            [
                "--osx-bundle-identifier",
                "org.sei.esrs-municipal-spending-tool",
                "--icon",
                str(ICONS_DIR / "app.icns"),
            ]
        )
    elif os.name == "nt":
        command.extend(["--icon", str(ICONS_DIR / "app.ico")])

    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(PYINSTALLER_CONFIG_DIR)

    subprocess.run(command, check=True, cwd=PROJECT_ROOT, env=env)
    print(f"Desktop app built in {DIST_DIR}")


if __name__ == "__main__":
    main()
