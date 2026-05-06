#!/usr/bin/env python3
"""Desktop launcher for the ESRS Municipal Spending Tool."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from esrs_tool import config
from esrs_tool.server import HOST, PORT, create_server, serve, stop_server


WINDOW_TITLE = "ESRS Municipal Spending Tool"


def _find_available_port(host: str, preferred_port: int, attempts: int = 25) -> int:
    for port in range(preferred_port, preferred_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.settimeout(0.2)
            if handle.connect_ex((host, port)) != 0:
                return port
    raise RuntimeError(f"Could not find a free local port between {preferred_port} and {preferred_port + attempts - 1}.")


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command)


def _format_bytes(value: int) -> str:
    if value >= 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024 * 1024):.1f} GB"
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, on_save: Callable[[], None]):
        super().__init__(master)
        self.title("Choose Default Files")
        self.resizable(True, False)
        self.transient(master)
        self.grab_set()
        self.on_save = on_save
        self.vars: Dict[str, tk.StringVar] = {}

        self.columnconfigure(1, weight=1)

        defaults = config.load_local_config()
        rows = [
            ("Invoice / procurement file", "invoice_path", False, [("Spreadsheet files", "*.xlsx *.xls *.csv"), ("All files", "*.*")]),
            ("ESRS mapping file", "mapping_path", False, [("Spreadsheet files", "*.xlsx *.xls *.csv"), ("All files", "*.*")]),
            ("Data folder", "data_dir", True, []),
            ("Meeting notes", "meeting_notes_path", False, [("All files", "*.*")]),
            ("Gap analysis", "gap_report_path", False, [("All files", "*.*")]),
            ("Code plan", "code_plan_path", False, [("All files", "*.*")]),
        ]

        ttk.Label(
            self,
            text="Choose local default files if you want the tool to remember them between launches.",
            wraplength=620,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(16, 10))

        for index, (label, key, is_dir, filetypes) in enumerate(rows, start=1):
            ttk.Label(self, text=label).grid(row=index, column=0, sticky="w", padx=(16, 10), pady=6)
            var = tk.StringVar(value=defaults.get(key, ""))
            self.vars[key] = var
            entry = ttk.Entry(self, textvariable=var)
            entry.grid(row=index, column=1, sticky="ew", pady=6)
            if is_dir:
                browse_command = lambda current_key=key: self._choose_directory(current_key)
            else:
                browse_command = lambda current_key=key, current_filetypes=filetypes: self._choose_file(
                    current_key,
                    current_filetypes,
                )
            button = ttk.Button(
                self,
                text="Browse",
                command=browse_command,
            )
            button.grid(row=index, column=2, padx=8, pady=6)
            ttk.Button(self, text="Clear", command=lambda current_key=key: self.vars[current_key].set("")).grid(
                row=index,
                column=3,
                padx=(0, 16),
                pady=6,
            )

        button_row = len(rows) + 1
        footer = ttk.Frame(self)
        footer.grid(row=button_row, column=0, columnspan=4, sticky="ew", padx=16, pady=(14, 16))
        footer.columnconfigure(0, weight=1)

        ttk.Button(footer, text="Use Sample Defaults", command=self._use_samples).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Cancel", command=self.destroy).grid(row=0, column=1, padx=8)
        ttk.Button(footer, text="Save", command=self._save).grid(row=0, column=2)

    def _initial_dir(self, key: str) -> str:
        current = self.vars[key].get().strip()
        if current:
            path = Path(current).expanduser()
            if path.is_dir():
                return str(path)
            if path.parent.exists():
                return str(path.parent)
        return str(Path.home())

    def _choose_file(self, key: str, filetypes) -> None:
        selection = filedialog.askopenfilename(
            title="Choose local file",
            initialdir=self._initial_dir(key),
            filetypes=filetypes or [("All files", "*.*")],
        )
        if selection:
            self.vars[key].set(selection)

    def _choose_directory(self, key: str) -> None:
        selection = filedialog.askdirectory(
            title="Choose local folder",
            initialdir=self._initial_dir(key),
            mustexist=True,
        )
        if selection:
            self.vars[key].set(selection)

    def _use_samples(self) -> None:
        for var in self.vars.values():
            var.set("")

    def _save(self) -> None:
        payload = {key: var.get().strip() for key, var in self.vars.items() if var.get().strip()}
        path = config.save_local_config(payload)
        messagebox.showinfo("Defaults Saved", f"Saved local defaults to:\n{path}")
        self.on_save()
        self.destroy()


class DesktopLauncher:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("760x520")
        self.root.minsize(680, 460)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.server = None
        self.server_thread: Optional[threading.Thread] = None
        self.port: Optional[int] = None
        self.url: str = ""
        self.auto_open_done = False

        self.status_var = tk.StringVar(value="Starting local engine...")
        self.location_var = tk.StringVar(value="")
        self.invoice_name_var = tk.StringVar(value="Checking...")
        self.invoice_meta_var = tk.StringVar(value="")
        self.mapping_name_var = tk.StringVar(value="Checking...")
        self.mapping_meta_var = tk.StringVar(value="")
        self.notes_name_var = tk.StringVar(value="Checking...")
        self.notes_meta_var = tk.StringVar(value="")

        self._build_ui()
        self.refresh_sources()
        self.start_server()
        self.root.after(500, self.open_tool)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)

        ttk.Label(container, text=WINDOW_TITLE, font=("TkDefaultFont", 20, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(
            container,
            text="Desktop launcher for the local analysis engine. The main analysis interface opens in your browser.",
            wraplength=700,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 16))

        status_frame = ttk.LabelFrame(container, text="Status", padding=14)
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.location_var, foreground="#4f6f5f").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(6, 0),
        )

        action_row = ttk.Frame(container, padding=(0, 14, 0, 10))
        action_row.grid(row=3, column=0, sticky="ew")
        for column in range(5):
            action_row.columnconfigure(column, weight=1 if column == 4 else 0)
        ttk.Button(action_row, text="Open Tool", command=self.open_tool).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(action_row, text="Configure Defaults", command=self.open_settings).grid(row=0, column=1, padx=8)
        ttk.Button(action_row, text="Open Config Folder", command=self.open_config_folder).grid(row=0, column=2, padx=8)
        ttk.Button(action_row, text="Restart Engine", command=self.restart_server).grid(row=0, column=3, padx=8)

        sources = ttk.LabelFrame(container, text="Current Default Sources", padding=14)
        sources.grid(row=4, column=0, sticky="nsew")
        sources.columnconfigure(1, weight=1)

        self._add_source_row(sources, 0, "Invoice dataset", self.invoice_name_var, self.invoice_meta_var)
        self._add_source_row(sources, 1, "Validation mapping", self.mapping_name_var, self.mapping_meta_var)
        self._add_source_row(sources, 2, "Reference notes", self.notes_name_var, self.notes_meta_var)

        ttk.Label(
            container,
            text=f"Local settings live in {config.LOCAL_CONFIG_PATH}",
            foreground="#5f6b65",
            wraplength=700,
            justify="left",
        ).grid(row=5, column=0, sticky="w", pady=(12, 0))

        container.rowconfigure(4, weight=1)

    def _add_source_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        name_var: tk.StringVar,
        meta_var: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w", padx=(0, 14), pady=(0, 2))
        ttk.Label(parent, textvariable=name_var, font=("TkDefaultFont", 11, "bold")).grid(
            row=row * 2,
            column=1,
            sticky="w",
        )
        ttk.Label(parent, textvariable=meta_var, foreground="#5f6b65").grid(
            row=row * 2 + 1,
            column=1,
            sticky="w",
            pady=(0, 10),
        )

    def refresh_sources(self) -> None:
        defaults = config.current_defaults()

        self._set_source_summary(
            defaults["invoice_path"],
            self.invoice_name_var,
            self.invoice_meta_var,
            is_spreadsheet=True,
        )
        self._set_source_summary(
            defaults["mapping_path"],
            self.mapping_name_var,
            self.mapping_meta_var,
            is_spreadsheet=False,
        )
        self._set_source_summary(
            defaults["meeting_notes_path"],
            self.notes_name_var,
            self.notes_meta_var,
            is_spreadsheet=False,
        )

    def _set_source_summary(
        self,
        path: Path,
        name_var: tk.StringVar,
        meta_var: tk.StringVar,
        is_spreadsheet: bool,
    ) -> None:
        if path.exists():
            name_var.set(path.name)
            details = [_format_bytes(path.stat().st_size)]
            if is_spreadsheet and path.suffix.lower() == ".xlsx":
                try:
                    from esrs_tool.tabular import sheet_names

                    details.append(f"{len(sheet_names(path))} worksheets")
                except Exception:
                    pass
            meta_var.set(" · ".join(details))
            return

        name_var.set("Not found")
        meta_var.set(str(path))

    def start_server(self) -> None:
        if self.server is not None:
            return
        preferred_port = int(os.environ.get("ESRS_TOOL_PORT", PORT))
        self.port = _find_available_port(HOST, preferred_port)
        self.url = f"http://{HOST}:{self.port}"
        self.server = create_server(HOST, self.port)
        self.server_thread = threading.Thread(target=serve, args=(self.server,), daemon=True)
        self.server_thread.start()
        self.status_var.set("Local engine is running.")
        if self.port != preferred_port:
            self.location_var.set(f"Opened on {self.url} because port {preferred_port} was already busy.")
        else:
            self.location_var.set(self.url)

    def stop_server(self) -> None:
        if self.server is None:
            return
        stop_server(self.server)
        self.server = None
        self.server_thread = None
        self.status_var.set("Local engine stopped.")
        self.location_var.set("")

    def restart_server(self) -> None:
        try:
            self.stop_server()
            self.start_server()
            messagebox.showinfo("Engine Restarted", "The local analysis engine restarted successfully.")
        except Exception as exc:
            messagebox.showerror("Restart Failed", str(exc))

    def open_tool(self) -> None:
        try:
            if self.server is None:
                self.start_server()
            webbrowser.open(self.url, new=1)
            self.auto_open_done = True
        except Exception as exc:
            messagebox.showerror("Could Not Open Tool", str(exc))

    def open_settings(self) -> None:
        SettingsDialog(self.root, on_save=self.refresh_sources)

    def open_config_folder(self) -> None:
        try:
            config.DATA_ROOT.mkdir(parents=True, exist_ok=True)
            _open_path(config.DATA_ROOT)
        except Exception as exc:
            messagebox.showerror("Could Not Open Folder", str(exc))

    def _on_close(self) -> None:
        self.stop_server()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    DesktopLauncher().run()


if __name__ == "__main__":
    main()
