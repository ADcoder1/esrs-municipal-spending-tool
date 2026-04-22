import csv
import re
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET


def iter_table(path: Path, sheet_index: int = 0, max_rows: Optional[int] = None) -> Iterator[List[str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        yield from iter_csv_rows(path, max_rows=max_rows)
    elif suffix == ".xlsx":
        yield from iter_xlsx_rows(path, sheet_index=sheet_index, max_rows=max_rows)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use CSV or XLSX.")


def iter_csv_rows(path: Path, max_rows: Optional[int] = None) -> Iterator[List[str]]:
    encodings = ("utf-8-sig", "utf-8", "latin-1")
    last_error = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    dialect = csv.excel
                reader = csv.reader(handle, dialect)
                for index, row in enumerate(reader):
                    if max_rows is not None and index >= max_rows:
                        break
                    yield [cell.strip() for cell in row]
            return
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error


def iter_xlsx_rows(
    path: Path, sheet_index: int = 0, max_rows: Optional[int] = None
) -> Iterator[List[str]]:
    with zipfile.ZipFile(path) as archive:
        strings = _read_shared_strings(archive)
        sheets = _sheet_paths(archive)
        if not sheets:
            raise ValueError("No worksheets were found in the XLSX file.")
        if sheet_index < 0 or sheet_index >= len(sheets):
            raise ValueError(f"Sheet index {sheet_index} is out of range.")
        sheet_path = sheets[sheet_index][1]
        emitted = 0
        with archive.open(sheet_path) as handle:
            for event, elem in ET.iterparse(handle, events=("end",)):
                if _local_name(elem.tag) != "row":
                    continue
                row = _parse_row(elem, strings)
                elem.clear()
                if max_rows is not None and emitted >= max_rows:
                    break
                emitted += 1
                yield row


def sheet_names(path: Path) -> List[str]:
    if path.suffix.lower() != ".xlsx":
        return ["CSV"]
    with zipfile.ZipFile(path) as archive:
        return [name for name, _path in _sheet_paths(archive)]


def _read_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    try:
        handle = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: List[str] = []
    with handle:
        for event, elem in ET.iterparse(handle, events=("end",)):
            if _local_name(elem.tag) != "si":
                continue
            parts = []
            for child in elem.iter():
                if _local_name(child.tag) == "t" and child.text:
                    parts.append(child.text)
            strings.append("".join(parts))
            elem.clear()
    return strings


def _sheet_paths(archive: zipfile.ZipFile) -> List[Tuple[str, str]]:
    try:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        names = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet"))
        return [(Path(name).stem, name) for name in names]

    relationships: Dict[str, str] = {}
    for rel in rels:
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if not rel_id:
            continue
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = "xl/" + target
        relationships[rel_id] = path

    sheets: List[Tuple[str, str]] = []
    for sheet in workbook.iter():
        if _local_name(sheet.tag) != "sheet":
            continue
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if rel_id in relationships:
            sheets.append((name, relationships[rel_id]))
    return sheets


def _parse_row(row_elem: ET.Element, strings: Sequence[str]) -> List[str]:
    values: List[str] = []
    for cell in row_elem:
        if _local_name(cell.tag) != "c":
            continue
        ref = cell.attrib.get("r", "")
        column_index = _column_index(ref)
        while len(values) <= column_index:
            values.append("")
        values[column_index] = _parse_cell(cell, strings)
    return values


def _parse_cell(cell: ET.Element, strings: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t")
    raw_value = ""
    inline_value = ""
    for child in cell:
        child_name = _local_name(child.tag)
        if child_name == "v" and child.text is not None:
            raw_value = child.text
        elif child_name == "is":
            inline_parts = []
            for inline_child in child.iter():
                if _local_name(inline_child.tag) == "t" and inline_child.text:
                    inline_parts.append(inline_child.text)
            inline_value = "".join(inline_parts)

    if cell_type == "s":
        try:
            return strings[int(raw_value)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "inlineStr":
        return inline_value
    if cell_type == "b":
        return "TRUE" if raw_value == "1" else "FALSE"
    return raw_value or inline_value


def _column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref.upper())
    if not match:
        return 0
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag

