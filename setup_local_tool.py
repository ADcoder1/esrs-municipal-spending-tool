#!/usr/bin/env python3
"""Create a local config for a collaborator-friendly ESRS setup."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from esrs_tool import config


PROJECT_ROOT = config.PROJECT_ROOT
CONFIG_PATH = config.LOCAL_CONFIG_PATH


def _load_existing_config() -> Dict[str, str]:
    return config.load_local_config(CONFIG_PATH)


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
    return str(Path.home())


def _print_value(label: str, value: str) -> None:
    print(f"{label}: {value if value else 'Sample/default behavior'}")


def run_setup_flow(launch_after_prompt: bool = True) -> Dict[str, str]:
    local_config = _load_existing_config()
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
    _print_value("Current", local_config.get("invoice_path", ""))
    local_config["invoice_path"] = _choose_file(
        root,
        "Choose the invoice or procurement file",
        local_config.get("invoice_path", ""),
        invoice_types,
    )

    print("\n2. ESRS category mapping file")
    _print_value("Current", local_config.get("mapping_path", ""))
    local_config["mapping_path"] = _choose_file(
        root,
        "Choose the reviewed mapping file",
        local_config.get("mapping_path", ""),
        invoice_types,
    )

    if _ask_yes_no("\n3. Do you want to choose a data folder now?", default=bool(local_config.get("data_dir"))):
        _print_value("Current", local_config.get("data_dir", ""))
        local_config["data_dir"] = _choose_directory(
            root,
            "Choose the local data folder",
            local_config.get("data_dir", ""),
        )

    optional_files = [
        ("meeting_notes_path", "4. Choose a meeting notes file now?", "Choose the meeting notes file"),
        ("gap_report_path", "5. Choose a gap-analysis file now?", "Choose the gap-analysis file"),
        ("code_plan_path", "6. Choose a code-plan file now?", "Choose the code-plan file"),
    ]

    for key, prompt, title in optional_files:
        if _ask_yes_no(f"\n{prompt}", default=bool(local_config.get(key))):
            _print_value("Current", local_config.get(key, ""))
            local_config[key] = _choose_file(
                root,
                title,
                local_config.get(key, ""),
                [("All files", "*.*")],
            )

    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass

    cleaned = {key: value for key, value in local_config.items() if str(value).strip()}
    config_path = config_save(cleaned)

    print(f"\nSaved local settings to {config_path}")
    for label, key in (
        ("Invoice", "invoice_path"),
        ("Mapping", "mapping_path"),
        ("Data folder", "data_dir"),
        ("Meeting notes", "meeting_notes_path"),
        ("Gap analysis", "gap_report_path"),
        ("Code plan", "code_plan_path"),
    ):
        _print_value(label, cleaned.get(key, ""))

    if launch_after_prompt and _ask_yes_no("\nOpen the tool now?", default=True):
        from launch_local_tool import main as launch_main

        print()
        launch_main()
    return cleaned


def config_save(data: Dict[str, str]) -> Path:
    return config.save_local_config(data, CONFIG_PATH)


def main() -> None:
    run_setup_flow(launch_after_prompt=True)


if __name__ == "__main__":
    main()
