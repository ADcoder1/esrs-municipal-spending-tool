import cgi
import json
import mimetypes
import shutil
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .analyzer import analyze, export_path
from .config import (
    DEFAULT_CODE_PLAN_PATH,
    DEFAULT_GAP_REPORT_PATH,
    DEFAULT_INVOICE_PATH,
    DEFAULT_MAPPING_PATH,
    DEFAULT_MEETING_NOTES_PATH,
    DEFAULT_DATA_DIR,
    PROJECT_ROOT,
    STATIC_DIR,
)
from .tabular import sheet_names


HOST = "127.0.0.1"
PORT = 8765


class EsrsHandler(BaseHTTPRequestHandler):
    server_version = "ESRSTool/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(STATIC_DIR / "index.html")
            return
        if parsed.path == "/api/config":
            self._send_json(
                {
                    "default_invoice_path": str(DEFAULT_INVOICE_PATH),
                    "default_invoice_exists": DEFAULT_INVOICE_PATH.exists(),
                    "default_invoice_name": DEFAULT_INVOICE_PATH.name,
                    "default_invoice_size_bytes": _safe_size(DEFAULT_INVOICE_PATH),
                    "default_invoice_sheet_names": _safe_sheet_names(DEFAULT_INVOICE_PATH),
                    "default_mapping_path": str(DEFAULT_MAPPING_PATH),
                    "default_mapping_exists": DEFAULT_MAPPING_PATH.exists(),
                    "default_mapping_name": DEFAULT_MAPPING_PATH.name,
                    "default_mapping_size_bytes": _safe_size(DEFAULT_MAPPING_PATH),
                    "data_dir": str(DEFAULT_DATA_DIR),
                    "data_dir_exists": DEFAULT_DATA_DIR.exists(),
                    "meeting_notes_path": str(DEFAULT_MEETING_NOTES_PATH),
                    "meeting_notes_exists": DEFAULT_MEETING_NOTES_PATH.exists(),
                    "meeting_notes_name": DEFAULT_MEETING_NOTES_PATH.name,
                    "gap_report_path": str(DEFAULT_GAP_REPORT_PATH),
                    "gap_report_exists": DEFAULT_GAP_REPORT_PATH.exists(),
                    "gap_report_name": DEFAULT_GAP_REPORT_PATH.name,
                    "code_plan_path": str(DEFAULT_CODE_PLAN_PATH),
                    "code_plan_exists": DEFAULT_CODE_PLAN_PATH.exists(),
                    "code_plan_name": DEFAULT_CODE_PLAN_PATH.name,
                    "project_root": str(PROJECT_ROOT),
                }
            )
            return
        if parsed.path.startswith("/api/export/"):
            export_id = parsed.path.rsplit("/", 1)[-1]
            try:
                self._send_file(export_path(export_id), download_name="classified_esrs_rows.csv")
            except Exception as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            return
        static_path = STATIC_DIR / parsed.path.lstrip("/")
        if static_path.exists() and static_path.is_file():
            self._send_file(static_path)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self._send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                },
            )
            with tempfile.TemporaryDirectory(prefix="esrs-upload-") as temp_dir:
                temp_path = Path(temp_dir)
                invoice_path = self._field_file(form, "invoice_file", temp_path)
                mapping_path = self._field_file(form, "mapping_file", temp_path)

                if invoice_path is None:
                    if _truthy(_form_value(form, "use_default_invoice")):
                        invoice_path = DEFAULT_INVOICE_PATH
                    else:
                        raise ValueError("Choose an invoice/procurement CSV or XLSX file.")
                if mapping_path is None:
                    if _truthy(_form_value(form, "use_default_mapping")):
                        mapping_path = DEFAULT_MAPPING_PATH
                    else:
                        raise ValueError("Choose an ESRS mapping CSV or XLSX file.")

                if not invoice_path.exists():
                    raise FileNotFoundError(f"Invoice file not found: {invoice_path}")
                if not mapping_path.exists():
                    raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

                max_rows = int(_form_value(form, "max_rows") or "50000")
                sheet_index = int(_form_value(form, "sheet_index") or "0")
                export_rows = _truthy(_form_value(form, "export_rows", "true"))

                result = analyze(
                    invoice_path=invoice_path,
                    mapping_path=mapping_path,
                    max_rows=max_rows,
                    sheet_index=sheet_index,
                    export_rows=export_rows,
                )
            self._send_json(result)
        except Exception as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def _field_file(self, form: cgi.FieldStorage, name: str, temp_path: Path):
        item = form[name] if name in form else None
        if item is None or not getattr(item, "filename", ""):
            return None
        filename = Path(item.filename).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".csv", ".xlsx"}:
            raise ValueError(f"{filename} is not supported. Use CSV or XLSX.")
        target = temp_path / filename
        with target.open("wb") as output:
            shutil.copyfileobj(item.file, output)
        return target

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _send_file(self, path: Path, download_name: str = "") -> None:
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(data)


def run(host: str = HOST, port: int = PORT) -> None:
    server = ThreadingHTTPServer((host, port), EsrsHandler)
    print(f"ESRS tool running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ESRS tool.")
    finally:
        server.server_close()


def _form_value(form: cgi.FieldStorage, name: str, default: str = "") -> str:
    if name not in form:
        return default
    value = form.getvalue(name)
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value)


def _truthy(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _safe_sheet_names(path: Path):
    try:
        return sheet_names(path)
    except Exception:
        return []


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0
