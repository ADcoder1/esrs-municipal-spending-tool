#!/usr/bin/env python3
"""Build a shareable local bundle for collaborators."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
BUNDLE_NAME = "esrs-municipal-spending-tool-local"
BUNDLE_DIR = DIST_DIR / BUNDLE_NAME
ZIP_PATH = DIST_DIR / f"{BUNDLE_NAME}.zip"

INCLUDE_PATHS = [
    "app.py",
    "launch_local_tool.py",
    "setup_local_tool.py",
    "README.md",
    "LOCAL_COLLABORATOR_SETUP.md",
    "LICENSE",
    "NOTICE",
    "config.local.example.json",
    "pyproject.toml",
    "Run-ESRS-Tool.command",
    "Configure-ESRS-Tool.command",
    "Run-ESRS-Tool.bat",
    "Configure-ESRS-Tool.bat",
    "esrs_tool",
    "static",
    "samples",
    "docs",
]


def _copy_path(relative_path: str) -> None:
    source = PROJECT_ROOT / relative_path
    target = BUNDLE_DIR / relative_path
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".DS_Store",
            ),
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _write_bundle_notes() -> None:
    data_dir = BUNDLE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "PUT-PRIVATE-FILES-HERE.txt").write_text(
        "Optional local folder for private datasets and reference files.\n"
        "Nothing in this folder is uploaded by the tool.\n",
        encoding="utf-8",
    )


def _make_launchers_executable() -> None:
    for name in ("Run-ESRS-Tool.command", "Configure-ESRS-Tool.command"):
        path = BUNDLE_DIR / name
        if path.exists():
            path.chmod(0o755)


def _build_zip() -> None:
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BUNDLE_DIR.rglob("*")):
            archive.write(path, path.relative_to(DIST_DIR))


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    for relative_path in INCLUDE_PATHS:
        _copy_path(relative_path)

    _write_bundle_notes()
    _make_launchers_executable()
    _build_zip()

    print(f"Bundle folder: {BUNDLE_DIR}")
    print(f"Bundle zip: {ZIP_PATH}")


if __name__ == "__main__":
    main()
