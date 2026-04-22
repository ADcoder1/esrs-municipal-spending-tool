import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .tabular import iter_table


ESRS_LABELS = {
    "E1": "Climate change",
    "E2": "Pollution",
    "E3": "Water and marine resources",
    "E4": "Biodiversity and ecosystems",
    "E5": "Resource use and circular economy",
    "None": "Not environmentally relevant by default",
    "Unmatched": "No mapping found",
}

CATEGORY_PRIORITY = [
    "Inköpskategori 3",
    "Inköpskategori 2",
    "Inköpskategori 1",
    "Nivå 3 (SV)",
    "Nivå 2 (SV)",
    "Nivå 1 (SV)",
    "Nivå 3 (EN)",
    "Nivå 2 (EN)",
    "Nivå 1 (EN)",
    "Procurement Category",
    "UNSPSC",
]

AMOUNT_COLUMNS = [
    "Belopp",
    "Amount",
    "Köp på prislista",
    "Köp inom avtal",
    "Köp utanför avtal",
    "Köp utan avtal",
]

DATA_GAP_COLUMNS = [
    "Förvaltning",
    "Avdelning/Område",
    "Enhet",
    "Projekt",
    "Aktivitet",
    "Objekt",
    "Leverantörskod",
    "Leverantörsnamn",
    "Fakturatext",
    "UNSPSC",
    "Inköpskategori 1",
    "Inköpskategori 2",
    "Inköpskategori 3",
]


@dataclass
class MappingEntry:
    primary: str
    secondary: str
    confidence: str
    comment: str
    source_key: str
    source_column: str


@dataclass
class Classification:
    primary: str
    secondary: str
    confidence: str
    method: str
    matched_value: str
    comment: str = ""


def load_mapping(path: Path) -> Dict[str, MappingEntry]:
    rows = list(iter_table(path))
    if not rows:
        return {}

    header_index = _find_header_row(rows)
    headers = _dedupe_headers(rows[header_index])
    records = rows[header_index + 1 :]
    index = {normalize_key(header): i for i, header in enumerate(headers)}

    primary_idx = _first_index(
        index,
        [
            "proposed esrs primary e1-e5 none",
            "proposed esrs primary e1 e5 none",
            "proposed esrs primary",
            "esrs primary",
            "primary",
        ],
    )
    secondary_idx = _first_index(
        index,
        ["proposed esrs secondary optional", "proposed esrs secondary", "esrs secondary", "secondary"],
    )
    confidence_idx = _first_index(index, ["confidence high medium needs review", "confidence"])
    comment_idx = _first_index(index, ["comments helsingborg", "comments", "comment"])

    category_columns = [
        "Nivå 3 (SV)",
        "Nivå 2 (SV)",
        "Nivå 1 (SV)",
        "Nivå 3 (EN)",
        "Nivå 2 (EN)",
        "Nivå 1 (EN)",
        "Inköpskategori 3 (SV)",
        "Inköpskategori 2 (SV)",
        "Inköpskategori 1 (SV)",
        "Inköpskategori 3 (EN)",
        "Inköpskategori 2 (EN)",
        "Inköpskategori 1 (EN)",
        "Procurement Category",
    ]

    mapping: Dict[str, MappingEntry] = {}
    for row in records:
        primary = _cell(row, primary_idx)
        primary_code = normalize_esrs(primary)
        if primary_code == "Unmatched":
            continue

        secondary = normalize_esrs(_cell(row, secondary_idx), allow_blank=True)
        confidence = _cell(row, confidence_idx) or "Unspecified"
        comment = _cell(row, comment_idx)

        for column_name in category_columns:
            column_idx = _find_header_index(headers, column_name)
            value = _cell(row, column_idx)
            key = normalize_key(value)
            if not key:
                continue
            mapping[key] = MappingEntry(
                primary=primary_code,
                secondary=secondary,
                confidence=confidence,
                comment=comment,
                source_key=value,
                source_column=column_name,
            )
    return mapping


def classify_row(row: Dict[str, str], mapping: Dict[str, MappingEntry]) -> Classification:
    for column in CATEGORY_PRIORITY:
        value = row.get(column, "")
        for candidate in _candidate_keys(value):
            entry = mapping.get(candidate)
            if entry:
                return Classification(
                    primary=entry.primary,
                    secondary=entry.secondary,
                    confidence=entry.confidence,
                    method=f"mapping:{entry.source_column}",
                    matched_value=entry.source_key,
                    comment=entry.comment,
                )

    heuristic = _heuristic_classification(row)
    if heuristic:
        return heuristic

    return Classification(
        primary="Unmatched",
        secondary="",
        confidence="Needs review",
        method="unmatched",
        matched_value="",
    )


def row_amount(row: Dict[str, str]) -> float:
    if row.get("Belopp") or row.get("Amount"):
        return parse_number(row.get("Belopp") or row.get("Amount"))
    total = 0.0
    found = False
    for column in AMOUNT_COLUMNS:
        if column in ("Belopp", "Amount"):
            continue
        if column in row and row[column] != "":
            found = True
            total += parse_number(row[column])
    return total if found else 0.0


def parse_number(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if not text or text in {"-", "–"}:
        return 0.0
    text = re.sub(r"[^\d,.\-]", "", text)
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_esrs(value: str, allow_blank: bool = False) -> str:
    text = (value or "").strip()
    if not text:
        return "" if allow_blank else "Unmatched"
    match = re.search(r"\b(E[1-5])\b", text.upper())
    if match:
        return match.group(1)
    if normalize_key(text) in {"none", "not environmentally relevant by default", "not relevant"}:
        return "None"
    return "Unmatched"


def normalize_key(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("&", " and ")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"[^a-z0-9åäö_\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _candidate_keys(value: str) -> List[str]:
    key = normalize_key(value)
    if not key:
        return []
    candidates = [key]
    if " - " in str(value):
        candidates.append(normalize_key(str(value).split(" - ", 1)[1]))
    if "-" in key:
        candidates.append(normalize_key(key.split("-", 1)[1]))
    return [candidate for candidate in dict.fromkeys(candidates) if candidate]


def _heuristic_classification(row: Dict[str, str]) -> Optional[Classification]:
    text = normalize_key(
        " ".join(
            row.get(column, "")
            for column in [
                "Inköpskategori 1",
                "Inköpskategori 2",
                "Inköpskategori 3",
                "UNSPSC",
                "Konto",
                "Fakturatext",
            ]
        )
    )
    if not text:
        return None

    rules: List[Tuple[str, Sequence[str], str]] = [
        ("E5", ("avfall", "waste", "recycling", "aterbruk", "återbruk", "circular", "material"), "heuristic:E5"),
        ("E3", ("vatten", "water", "marine", "wastewater", "avlopp"), "heuristic:E3"),
        ("E4", ("biodiversity", "biologisk", "gronyta", "gronyteskotsel", "park", "landskap", "växt", "vaxt"), "heuristic:E4"),
        ("E2", ("pollution", "kemisk", "chemical", "sanering", "hazard", "rengoring", "cleaning"), "heuristic:E2"),
        ("E1", ("drivmedel", "fuel", "fordon", "vehicle", "transport", "energy", "energi", "el ", "varme", "värme"), "heuristic:E1"),
    ]
    for code, needles, method in rules:
        if any(needle in text for needle in needles):
            return Classification(
                primary=code,
                secondary="",
                confidence="Needs review",
                method=method,
                matched_value="",
                comment="Suggested by keyword fallback; validate before use.",
            )
    return None


def _find_header_row(rows: Sequence[Sequence[str]]) -> int:
    known = {
        "niva 1 sv",
        "inkopskategori 1",
        "proposed esrs primary e1-e5 none",
        "proposed esrs primary e1 e5 none",
        "forvaltning",
    }
    for idx, row in enumerate(rows[:20]):
        normalized = {normalize_key(cell) for cell in row}
        if normalized & known:
            return idx
    return 0


def _dedupe_headers(headers: Sequence[str]) -> List[str]:
    result: List[str] = []
    counts: Dict[str, int] = {}
    for index, header in enumerate(headers):
        value = str(header).strip() or f"Column {index + 1}"
        count = counts.get(value, 0)
        counts[value] = count + 1
        result.append(value if count == 0 else f"{value}_{count + 1}")
    return result


def _first_index(index: Dict[str, int], names: Sequence[str]) -> Optional[int]:
    for name in names:
        key = normalize_key(name)
        if key in index:
            return index[key]
    return None


def _find_header_index(headers: Sequence[str], name: str) -> Optional[int]:
    target = normalize_key(name)
    for index, header in enumerate(headers):
        if normalize_key(header) == target:
            return index
    return None


def _cell(row: Sequence[str], index: Optional[int]) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index]).strip()
