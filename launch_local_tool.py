#!/usr/bin/env python3
"""Launch the ESRS Municipal Spending Tool in a local browser."""

from __future__ import annotations

import os
import socket
import threading
import webbrowser

from esrs_tool.server import HOST, PORT, run


def _find_available_port(host: str, preferred_port: int, attempts: int = 25) -> int:
    for port in range(preferred_port, preferred_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.settimeout(0.2)
            if handle.connect_ex((host, port)) != 0:
                return port
    raise RuntimeError(f"Could not find a free local port between {preferred_port} and {preferred_port + attempts - 1}.")


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=1)
    except Exception:
        pass


def main() -> None:
    preferred_port = int(os.environ.get("ESRS_TOOL_PORT", PORT))
    port = _find_available_port(HOST, preferred_port)
    url = f"http://{HOST}:{port}"

    print("Opening ESRS Municipal Spending Tool...")
    print(f"Local URL: {url}")
    if port != preferred_port:
        print(f"Port {preferred_port} was busy, so the tool is using {port} instead.")
    print("Press Ctrl+C in this window when you want to stop the tool.")

    threading.Timer(0.6, _open_browser, args=(url,)).start()
    run(host=HOST, port=port)


if __name__ == "__main__":
    main()
