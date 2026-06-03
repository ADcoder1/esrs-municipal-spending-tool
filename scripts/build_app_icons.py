#!/usr/bin/env python3
"""Generate branded desktop app icons for macOS and Windows."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOGO = PROJECT_ROOT / "static" / "assets" / "at-last-logo-icon.png"
ICON_DIR = PROJECT_ROOT / "static" / "icons"
MASTER_PNG = ICON_DIR / "app-icon-1024.png"
MAC_ICNS = ICON_DIR / "app.icns"
WIN_ICO = ICON_DIR / "app.ico"


SWIFT_RENDERER = r"""
import AppKit
import Foundation

let arguments = CommandLine.arguments
guard arguments.count == 3 else {
    fputs("usage: render <source-logo> <output-png>\n", stderr)
    exit(2)
}

let sourceURL = URL(fileURLWithPath: arguments[1])
let outputURL = URL(fileURLWithPath: arguments[2])

guard let logo = NSImage(contentsOf: sourceURL) else {
    fputs("failed to load logo\n", stderr)
    exit(1)
}

let size = NSSize(width: 1024, height: 1024)
let image = NSImage(size: size)
image.lockFocus()

guard let context = NSGraphicsContext.current?.cgContext else {
    fputs("failed to get graphics context\n", stderr)
    exit(1)
}

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1.0) -> NSColor {
    return NSColor(calibratedRed: r / 255, green: g / 255, blue: b / 255, alpha: a)
}

let fullRect = NSRect(origin: .zero, size: size)
color(57, 114, 200).setFill()
fullRect.fill()

let overlayPath = NSBezierPath(roundedRect: NSRect(x: 70, y: 70, width: 884, height: 884), xRadius: 220, yRadius: 220)
color(255, 255, 255, 0.08).setFill()
overlayPath.fill()

let tileRect = NSRect(x: 214, y: 214, width: 596, height: 596)
let tilePath = NSBezierPath(roundedRect: tileRect, xRadius: 140, yRadius: 140)

context.saveGState()
context.setShadow(offset: CGSize(width: 0, height: -18), blur: 42, color: NSColor(calibratedWhite: 0.09, alpha: 0.26).cgColor)
color(251, 252, 255, 0.97).setFill()
tilePath.fill()
context.restoreGState()

let haloRect = tileRect.insetBy(dx: 26, dy: 26)
let haloPath = NSBezierPath(roundedRect: haloRect, xRadius: 112, yRadius: 112)
color(57, 114, 200, 0.06).setFill()
haloPath.fill()

let logoRect = NSRect(x: 264, y: 286, width: 500, height: 422)
logo.draw(in: logoRect, from: .zero, operation: .sourceOver, fraction: 1.0)

let accentRect = NSRect(x: 728, y: 764, width: 110, height: 110)
let accentPath = NSBezierPath(ovalIn: accentRect)
color(243, 219, 105, 0.94).setFill()
accentPath.fill()

image.unlockFocus()

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let png = bitmap.representation(using: .png, properties: [:])
else {
    fputs("failed to create png data\n", stderr)
    exit(1)
}

try png.write(to: outputURL)
"""


def _run(command: list[str], *, extra_env: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    subprocess.run(command, check=True, cwd=PROJECT_ROOT, env=env)


def _ensure_tools() -> None:
    for tool in ("swift", "sips", "tiffutil", "tiff2icns"):
        if shutil.which(tool) is None:
            raise SystemExit(f"Missing required tool: {tool}")


def _write_ico(destination: Path, png_paths: list[Path]) -> None:
    payloads = [path.read_bytes() for path in png_paths]
    count = len(payloads)
    header = struct.pack("<HHH", 0, 1, count)

    entries: list[bytes] = []
    offset = 6 + (16 * count)
    for path, payload in zip(png_paths, payloads):
        size = int(path.stem.split("-")[-1])
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        offset += len(payload)

    destination.write_bytes(header + b"".join(entries) + b"".join(payloads))


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("This icon builder currently runs on macOS only.")

    _ensure_tools()
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        module_cache = PROJECT_ROOT / "build" / "swift-module-cache"
        module_cache.mkdir(parents=True, exist_ok=True)
        cache_env = {
            "CLANG_MODULE_CACHE_PATH": str(module_cache),
            "SWIFT_MODULECACHE_PATH": str(module_cache),
        }
        swift_file = temp_path / "render.swift"
        swift_file.write_text(SWIFT_RENDERER, encoding="utf-8")

        _run(["swift", str(swift_file), str(SOURCE_LOGO), str(MASTER_PNG)], extra_env=cache_env)

        tiff_sizes = [16, 32, 48, 128, 256, 512, 1024]
        tiff_paths: list[Path] = []
        for size in tiff_sizes:
            output = temp_path / f"icon-{size}.tiff"
            _run(
                [
                    "sips",
                    "-z",
                    str(size),
                    str(size),
                    "-s",
                    "format",
                    "tiff",
                    str(MASTER_PNG),
                    "--out",
                    str(output),
                ]
            )
            tiff_paths.append(output)

        multi_tiff = temp_path / "app-icon-stack.tiff"
        _run(["tiffutil", "-cat", *map(str, tiff_paths), "-out", str(multi_tiff)])
        _run(["tiff2icns", str(multi_tiff), str(MAC_ICNS)])

        win_sizes = [16, 24, 32, 48, 64, 128, 256]
        win_pngs: list[Path] = []
        for size in win_sizes:
            output = temp_path / f"icon-{size}.png"
            _run(["sips", "-z", str(size), str(size), str(MASTER_PNG), "--out", str(output)])
            win_pngs.append(output)

        _write_ico(WIN_ICO, win_pngs)

    print(f"Created {MASTER_PNG}")
    print(f"Created {MAC_ICNS}")
    print(f"Created {WIN_ICO}")


if __name__ == "__main__":
    main()
