import json
import os
import sys
from pathlib import Path
from typing import Dict


APP_ID = "ESRSMunicipalSpendingTool"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _resource_root() -> Path:
    if is_frozen() and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return PROJECT_ROOT


def _data_root() -> Path:
    override = os.environ.get("ESRS_TOOL_HOME")
    if override:
        return Path(override).expanduser()

    if not is_frozen():
        return PROJECT_ROOT

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_ID
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_ID
        return Path.home() / "AppData" / "Roaming" / APP_ID

    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_ID
    return Path.home() / ".config" / APP_ID


RESOURCE_ROOT = _resource_root()
DATA_ROOT = _data_root()
STATIC_DIR = RESOURCE_ROOT / "static"
SAMPLE_DIR = RESOURCE_ROOT / "samples"
DOCS_DIR = RESOURCE_ROOT / "docs"
LOCAL_CONFIG_PATH = DATA_ROOT / "config.local.json"
EXPORT_DIR = DATA_ROOT / "exports"


def load_local_config(path: Path = LOCAL_CONFIG_PATH) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def save_local_config(data: Dict[str, str], path: Path = LOCAL_CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {str(key): str(value) for key, value in data.items() if str(value).strip()}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def _path_setting(config: Dict[str, str], env_name: str, config_key: str, fallback: Path) -> Path:
    value = os.environ.get(env_name) or config.get(config_key)
    if not value:
        return fallback
    return Path(value).expanduser()


def current_defaults() -> Dict[str, Path]:
    local_config = load_local_config()
    return {
        "invoice_path": _path_setting(
            local_config,
            "ESRS_INVOICE_PATH",
            "invoice_path",
            SAMPLE_DIR / "sample_invoices.csv",
        ),
        "mapping_path": _path_setting(
            local_config,
            "ESRS_MAPPING_PATH",
            "mapping_path",
            SAMPLE_DIR / "sample_mapping.csv",
        ),
        "data_dir": _path_setting(
            local_config,
            "ESRS_DATA_DIR",
            "data_dir",
            SAMPLE_DIR,
        ),
        "meeting_notes_path": _path_setting(
            local_config,
            "ESRS_MEETING_NOTES_PATH",
            "meeting_notes_path",
            DOCS_DIR / "meeting-notes-template.md",
        ),
        "gap_report_path": _path_setting(
            local_config,
            "ESRS_GAP_REPORT_PATH",
            "gap_report_path",
            DOCS_DIR / "gap-analysis-template.md",
        ),
        "code_plan_path": _path_setting(
            local_config,
            "ESRS_CODE_PLAN_PATH",
            "code_plan_path",
            DOCS_DIR / "code-plan-template.csv",
        ),
    }


DEFAULTS = current_defaults()
DEFAULT_INVOICE_PATH = DEFAULTS["invoice_path"]
DEFAULT_MAPPING_PATH = DEFAULTS["mapping_path"]
DEFAULT_DATA_DIR = DEFAULTS["data_dir"]
DEFAULT_MEETING_NOTES_PATH = DEFAULTS["meeting_notes_path"]
DEFAULT_GAP_REPORT_PATH = DEFAULTS["gap_report_path"]
DEFAULT_CODE_PLAN_PATH = DEFAULTS["code_plan_path"]
