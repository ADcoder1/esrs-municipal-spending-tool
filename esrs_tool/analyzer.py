import csv
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

from .classifier import (
    AMOUNT_COLUMNS,
    CATEGORY_PRIORITY,
    DATA_GAP_COLUMNS,
    ESRS_LABELS,
    classify_row,
    load_mapping,
    normalize_key,
    row_amount,
)
from .config import EXPORT_DIR
from .tabular import iter_table, sheet_names


def analyze(
    invoice_path: Path,
    mapping_path: Path,
    max_rows: int = 50000,
    sheet_index: int = 0,
    export_rows: bool = True,
) -> Dict[str, object]:
    started = time.time()
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1.")

    mapping = load_mapping(mapping_path)
    row_iter = iter_table(invoice_path, sheet_index=sheet_index, max_rows=max_rows + 1)
    headers = _find_headers(row_iter)
    if not headers:
        raise ValueError("Could not identify a header row in the invoice file.")

    export_id = str(uuid.uuid4())
    export_path = EXPORT_DIR / f"{export_id}.csv"
    export_handle = None
    writer = None
    if export_rows:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_handle = export_path.open("w", newline="", encoding="utf-8")
        writer = csv.DictWriter(
            export_handle,
            fieldnames=headers
            + [
                "ESRS Primary",
                "ESRS Primary Label",
                "ESRS Secondary",
                "ESRS Confidence",
                "ESRS Method",
                "ESRS Matched Value",
                "ESRS Amount",
                "ESRS Comment",
            ],
        )
        writer.writeheader()

    row_count = 0
    total_amount = 0.0
    review_count = 0
    amount_by_esrs = defaultdict(float)
    count_by_esrs = Counter()
    confidence_counts = Counter()
    method_counts = Counter()
    category_amounts = defaultdict(float)
    category_counts = Counter()
    category_meta: Dict[str, Dict[str, object]] = {}
    gap_counts = Counter()
    caution_counts = Counter()
    climate_split = Counter()
    review_rows: List[Dict[str, object]] = []
    unmatched_rows: List[Dict[str, object]] = []

    try:
        for row_values in row_iter:
            if not any(str(cell).strip() for cell in row_values):
                continue
            row = _row_dict(headers, row_values)
            row_count += 1
            amount = row_amount(row)
            classification = classify_row(row, mapping)
            primary = classification.primary
            total_amount += amount
            amount_by_esrs[primary] += amount
            count_by_esrs[primary] += 1
            confidence_counts[_confidence_bucket(classification.confidence)] += 1
            method_counts[classification.method] += 1

            category = _best_category(row)
            category_key = f"{primary}||{category or 'Unspecified'}"
            category_amounts[category_key] += amount
            category_counts[category_key] += 1
            category_meta.setdefault(
                category_key,
                {
                    "category": category or "Unspecified",
                    "esrs": primary,
                    "label": ESRS_LABELS.get(primary, ""),
                    "secondary": classification.secondary,
                    "confidence": classification.confidence,
                    "method": classification.method,
                    "matched": classification.matched_value,
                    "comment": classification.comment,
                },
            )

            for column in DATA_GAP_COLUMNS:
                if column in headers and not row.get(column, "").strip():
                    gap_counts[column] += 1

            for caution in _caution_flags(row, classification):
                caution_counts[caution] += 1
            if primary == "E1":
                climate_split[_climate_subtheme(row)] += 1

            if _needs_review(classification):
                review_count += 1
                _append_sample(review_rows, row, classification, amount)
            if primary == "Unmatched":
                _append_sample(unmatched_rows, row, classification, amount)

            if writer:
                export_row = dict(row)
                export_row.update(
                    {
                        "ESRS Primary": primary,
                        "ESRS Primary Label": ESRS_LABELS.get(primary, ""),
                        "ESRS Secondary": classification.secondary,
                        "ESRS Confidence": classification.confidence,
                        "ESRS Method": classification.method,
                        "ESRS Matched Value": classification.matched_value,
                        "ESRS Amount": f"{amount:.2f}",
                        "ESRS Comment": classification.comment,
                    }
                )
                writer.writerow(export_row)
    finally:
        if export_handle:
            export_handle.close()

    top_categories = []
    for key, amount in sorted(category_amounts.items(), key=lambda item: abs(item[1]), reverse=True)[:25]:
        esrs, category = key.split("||", 1)
        top_categories.append(
            {
                "esrs": esrs,
                "label": ESRS_LABELS.get(esrs, ""),
                "category": category,
                "amount": amount,
                "rows": category_counts[key],
            }
        )

    category_export_id = ""
    if export_rows:
        category_export_id = str(uuid.uuid4())
        _write_category_export(
            EXPORT_DIR / f"{category_export_id}.csv",
            category_amounts,
            category_counts,
            category_meta,
        )

    data_gaps = [
        {
            "column": column,
            "missing": count,
            "percent": (count / row_count * 100) if row_count else 0,
        }
        for column, count in sorted(gap_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        "invoice_file": str(invoice_path),
        "mapping_file": str(mapping_path),
        "sheet_names": _safe_sheet_names(invoice_path),
        "sheet_index": sheet_index,
        "processed_rows": row_count,
        "max_rows": max_rows,
        "mapping_entries": len(mapping),
        "total_amount": total_amount,
        "classified_rows": sum(count for code, count in count_by_esrs.items() if code in {"E1", "E2", "E3", "E4", "E5"}),
        "unmatched_rows": count_by_esrs.get("Unmatched", 0),
        "none_rows": count_by_esrs.get("None", 0),
        "review_count": review_count,
        "amount_by_esrs": _series(amount_by_esrs),
        "count_by_esrs": _series(count_by_esrs),
        "confidence_counts": dict(confidence_counts),
        "method_counts": dict(method_counts),
        "caution_counts": dict(caution_counts),
        "climate_split": dict(climate_split),
        "e5_amount": amount_by_esrs.get("E5", 0),
        "e5_rows": count_by_esrs.get("E5", 0),
        "top_categories": top_categories,
        "data_gaps": data_gaps,
        "review_rows": review_rows,
        "unmatched_samples": unmatched_rows,
        "export_id": export_id if export_rows else "",
        "category_export_id": category_export_id,
        "duration_seconds": round(time.time() - started, 2),
        "headers": headers,
        "methodology_notes": _methodology_notes(),
    }


def export_path(export_id: str) -> Path:
    if not export_id or "/" in export_id or "\\" in export_id:
        raise ValueError("Invalid export id.")
    path = EXPORT_DIR / f"{export_id}.csv"
    if not path.exists():
        raise FileNotFoundError("Export not found.")
    return path


def _find_headers(row_iter) -> List[str]:
    for row in row_iter:
        normalized = {cell.strip() for cell in row if str(cell).strip()}
        if len(normalized) >= 3 and (
            normalized & set(CATEGORY_PRIORITY)
            or normalized & set(AMOUNT_COLUMNS)
            or "Förvaltning" in normalized
        ):
            return _dedupe_headers(row)
    return []


def _row_dict(headers: Sequence[str], values: Sequence[str]) -> Dict[str, str]:
    result = {}
    for index, header in enumerate(headers):
        result[header] = str(values[index]).strip() if index < len(values) else ""
    return result


def _dedupe_headers(headers: Sequence[str]) -> List[str]:
    result: List[str] = []
    counts: Dict[str, int] = {}
    for index, header in enumerate(headers):
        value = str(header).strip() or f"Column {index + 1}"
        count = counts.get(value, 0)
        counts[value] = count + 1
        result.append(value if count == 0 else f"{value}_{count + 1}")
    return result


def _best_category(row: Dict[str, str]) -> str:
    for column in CATEGORY_PRIORITY:
        value = row.get(column, "")
        if value:
            return value
    return ""


def _needs_review(classification) -> bool:
    confidence = _confidence_bucket(classification.confidence)
    return confidence == "Needs review" or classification.primary == "Unmatched" or classification.method.startswith("heuristic")


def _caution_flags(row: Dict[str, str], classification) -> List[str]:
    text = normalize_key(" ".join(str(value) for value in row.values()))
    flags: List[str] = []
    if classification.primary == "E4" and any(term in text for term in ["green", "gronyta", "park", "vaxt", "växt"]):
        flags.append("Green space needs biodiversity review")
    if classification.primary == "E5" and any(term in text for term in ["avfall", "waste", "recycling", "aterbruk"]):
        flags.append("Circular spend may need funding-source review")
    if any(term in text for term in ["bygg", "construction", "asfalt", "infrastruktur", "neighbourhood", "stadsdel"]):
        flags.append("Construction spend may need net-impact review")
    if classification.primary == "Unmatched":
        flags.append("No ESRS lens assigned")
    if classification.primary == "None":
        flags.append("Intentionally outside E1-E5")
    return flags


def _climate_subtheme(row: Dict[str, str]) -> str:
    text = normalize_key(" ".join(str(value) for value in row.values()))
    adaptation_terms = ["klimatanpass", "adaptation", "skyfall", "flood", "oversvam", "dagvatten", "stormwater", "resilien"]
    mitigation_terms = ["mitigation", "utslapp", "emission", "co2", "energi", "energy", "drivmedel", "fuel", "transport", "solar", "elbil"]
    adaptation = any(term in text for term in adaptation_terms)
    mitigation = any(term in text for term in mitigation_terms)
    if adaptation and mitigation:
        return "Mitigation and adaptation"
    if adaptation:
        return "Adaptation"
    if mitigation:
        return "Mitigation"
    return "E1 unspecified"


def _confidence_bucket(value: str) -> str:
    text = (value or "").strip().casefold()
    if "high" in text:
        return "High"
    if "medium" in text:
        return "Medium"
    if "review" in text or "low" in text:
        return "Needs review"
    return value or "Unspecified"


def _append_sample(samples: List[Dict[str, object]], row: Dict[str, str], classification, amount: float) -> None:
    if len(samples) >= 50:
        return
    samples.append(
        {
            "primary": classification.primary,
            "label": ESRS_LABELS.get(classification.primary, ""),
            "confidence": classification.confidence,
            "method": classification.method,
            "amount": amount,
            "category": _best_category(row),
            "department": row.get("Förvaltning", ""),
            "unit": row.get("Avdelning/Område", ""),
            "supplier": row.get("Leverantörsnamn", ""),
            "text": row.get("Fakturatext", ""),
            "matched": classification.matched_value,
        }
    )


def _write_category_export(
    path: Path,
    category_amounts,
    category_counts,
    category_meta: Dict[str, Dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Category",
                "ESRS Primary",
                "ESRS Label",
                "ESRS Secondary",
                "Confidence",
                "Rows",
                "Amount",
                "Method",
                "Matched Value",
                "Comment",
                "City Feedback",
            ],
        )
        writer.writeheader()
        for key, amount in sorted(category_amounts.items(), key=lambda item: abs(item[1]), reverse=True):
            meta = category_meta.get(key, {})
            writer.writerow(
                {
                    "Category": meta.get("category", ""),
                    "ESRS Primary": meta.get("esrs", ""),
                    "ESRS Label": meta.get("label", ""),
                    "ESRS Secondary": meta.get("secondary", ""),
                    "Confidence": meta.get("confidence", ""),
                    "Rows": category_counts[key],
                    "Amount": f"{amount:.2f}",
                    "Method": meta.get("method", ""),
                    "Matched Value": meta.get("matched", ""),
                    "Comment": meta.get("comment", ""),
                    "City Feedback": "",
                }
            )


def _series(values) -> List[Dict[str, object]]:
    order = ["E1", "E2", "E3", "E4", "E5", "None", "Unmatched"]
    return [
        {"code": code, "label": ESRS_LABELS.get(code, ""), "value": values.get(code, 0)}
        for code in order
        if values.get(code, 0)
    ]


def _safe_sheet_names(path: Path) -> List[str]:
    try:
        return sheet_names(path)
    except Exception:
        return []


def _methodology_notes() -> List[str]:
    return [
        "Invoice data is treated as the first interpretation layer.",
        "General Ledger totals should be used as the validation layer.",
        "ESRS E1-E5 are analytical lenses, not formal reporting categories.",
        "None is a valid outcome for spending that is not environmentally relevant by default.",
        "Uncertainty is surfaced through confidence and review flags instead of forced precision.",
    ]
