#!/usr/bin/env python3
"""Create a local config for a collaborator-friendly ESRS setup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.local.json"


def _load_existing_config() -> Dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def _picker_root():
    try:
        import tkinter as tk
    except Exception:
        return None

    try:
        root = tk.Tk()
        root.withdraw()
        root.update()
        return root
    except Exception:
        return None


def _choose_file(root, title: str, current: str, filetypes):
    if root is None:
        prompt = "Paste the full path, or press Enter to keep the current setting / skip: "
        answer = input(prompt).strip()
        return answer or current

    from tkinter import filedialog

    initial_dir = _initial_dir(current)
    selection = filedialog.askopenfilename(
        title=title,
        initialdir=initial_dir,
        filetypes=filetypes,
    )
    return selection or current


def _choose_directory(root, title: str, current: str):
    if root is None:
        prompt = "Paste the folder path, or press Enter to keep the current setting / skip: "
        answer = input(prompt).strip()
        return answer or current

    from tkinter import filedialog

    initial_dir = _initial_dir(current)
    selection = filedialog.askdirectory(
        title=title,
        initialdir=initial_dir,
        mustexist=True,
    )
    return selection or current


def _initial_dir(current: str) -> str:
    if current:
        path = Path(current).expanduser()
        if path.is_dir():
            return str(path)
        if path.parent.exists():
            return str(path.parent)
    return str(PROJECT_ROOT)


def _print_value(label: str, value: str) -> None:
    print(f"{label}: {value if value else 'Sample/default behavior'}")


def main() -> None:
    config = _load_existing_config()
    root = _picker_root()

    print("\nESRS Municipal Spending Tool setup\n")
    print("This saves local file paths to config.local.json on this machine only.")
    print("If you skip a setting, the tool will keep the current value or fall back to sample data.\n")

    invoice_types = [
        ("Spreadsheet files", "*.xlsx *.xls *.csv"),
        ("Excel workbooks", "*.xlsx *.xls"),
        ("CSV files", "*.csv"),
        ("All files", "*.*"),
    ]

    print("1. Invoice or procurement dataset")
    _print_value("Current", config.get("invoice_path", ""))
    config["invoice_path"] = _choose_file(
        root,
        "Choose the invoice or procurement file",
        config.get("invoice_path", ""),
        invoice_types,
    )

    print("\n2. ESRS category mapping file")
    _print_value("Current", config.get("mapping_path", ""))
    config["mapping_path"] = _choose_file(
        root,
        "Choose the reviewed mapping file",
        config.get("mapping_path", ""),
        invoice_types,
    )

    if _ask_yes_no("\n3. Do you want to choose a data folder now?", default=bool(config.get("data_dir"))):
        _print_value("Current", config.get("data_dir", ""))
        config["data_dir"] = _choose_directory(
            root,
            "Choose the local data folder",
            config.get("data_dir", ""),
        )

    optional_files = [
        ("meeting_notes_path", "4. Choose a meeting notes file now?", "Choose the meeting notes file"),
        ("gap_report_path", "5. Choose a gap-analysis file now?", "Choose the gap-analysis file"),
        ("code_plan_path", "6. Choose a code-plan file now?", "Choose the code-plan file"),
    ]

    for key, prompt, title in optional_files:
        if _ask_yes_no(f"\n{prompt}", default=bool(config.get(key))):
            _print_value("Current", config.get(key, ""))
            config[key] = _choose_file(
                root,
                title,
                config.get(key, ""),
                [("All files", "*.*")],
            )

    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass

    cleaned = {key: value for key, value in config.items() if str(value).strip()}
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"\nSaved local settings to {CONFIG_PATH}")
    for label, key in (
        ("Invoice", "invoice_path"),
        ("Mapping", "mapping_path"),
        ("Data folder", "data_dir"),
        ("Meeting notes", "meeting_notes_path"),
        ("Gap analysis", "gap_report_path"),
        ("Code plan", "code_plan_path"),
    ):
        _print_value(label, cleaned.get(key, ""))

    if _ask_yes_no("\nOpen the tool now?", default=True):
        from launch_local_tool import main as launch_main

        print()
        launch_main()


if __name__ == "__main__":
    main()
