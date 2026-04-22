import json
import os
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"
SAMPLE_DIR = PROJECT_ROOT / "samples"
LOCAL_CONFIG_PATH = PROJECT_ROOT / "config.local.json"


def _load_local_config() -> Dict[str, str]:
    if not LOCAL_CONFIG_PATH.exists():
        return {}
    with LOCAL_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def _path_setting(config: Dict[str, str], env_name: str, config_key: str, fallback: Path) -> Path:
    value = os.environ.get(env_name) or config.get(config_key)
    if not value:
        return fallback
    return Path(value).expanduser()


LOCAL_CONFIG = _load_local_config()

DEFAULT_INVOICE_PATH = _path_setting(
    LOCAL_CONFIG,
    "ESRS_INVOICE_PATH",
    "invoice_path",
    SAMPLE_DIR / "sample_invoices.csv",
)
DEFAULT_MAPPING_PATH = _path_setting(
    LOCAL_CONFIG,
    "ESRS_MAPPING_PATH",
    "mapping_path",
    SAMPLE_DIR / "sample_mapping.csv",
)
DEFAULT_DATA_DIR = _path_setting(
    LOCAL_CONFIG,
    "ESRS_DATA_DIR",
    "data_dir",
    SAMPLE_DIR,
)
DEFAULT_MEETING_NOTES_PATH = _path_setting(
    LOCAL_CONFIG,
    "ESRS_MEETING_NOTES_PATH",
    "meeting_notes_path",
    PROJECT_ROOT / "docs" / "meeting-notes-template.md",
)
DEFAULT_GAP_REPORT_PATH = _path_setting(
    LOCAL_CONFIG,
    "ESRS_GAP_REPORT_PATH",
    "gap_report_path",
    PROJECT_ROOT / "docs" / "gap-analysis-template.md",
)
DEFAULT_CODE_PLAN_PATH = _path_setting(
    LOCAL_CONFIG,
    "ESRS_CODE_PLAN_PATH",
    "code_plan_path",
    PROJECT_ROOT / "docs" / "code-plan-template.csv",
)

EXPORT_DIR = Path("/tmp/esrs-tool-exports")
