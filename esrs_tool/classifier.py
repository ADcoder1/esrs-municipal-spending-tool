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
    review_focus: Tuple[str, ...] = ()
    context_tags: Tuple[str, ...] = ()
    subcategories: Tuple[str, ...] = ()
    related_topics: Tuple[str, ...] = ()


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
                return _with_context_guidance(
                    row,
                    Classification(
                        primary=entry.primary,
                        secondary=entry.secondary,
                        confidence=entry.confidence,
                        method=f"mapping:{entry.source_column}",
                        matched_value=entry.source_key,
                        comment=entry.comment,
                    ),
                )

    heuristic = _heuristic_classification(row)
    if heuristic:
        return _with_context_guidance(row, heuristic)

    return _with_context_guidance(
        row,
        Classification(
            primary="Unmatched",
            secondary="",
            confidence="Needs review",
            method="unmatched",
            matched_value="",
        ),
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


def _with_context_guidance(row: Dict[str, str], classification: Classification) -> Classification:
    """Add review prompts without turning a category label into an impact claim.

    The prompts reflect the municipal co-design feedback: broad spending labels are
    useful first signals, but normally need purpose, specification or project-level
    context before they can be interpreted.
    """

    # A reviewed None mapping is deliberately outside the environmental scope.
    # Do not add an E1-E5 subcategory from incidental invoice keywords.
    if classification.primary == "None":
        return classification

    text = _guidance_text(row)
    detail_text = _guidance_detail_text(row)
    focus: List[str] = []
    tags: List[str] = []

    def add(tag: str, prompt: str) -> None:
        if tag not in tags:
            tags.append(tag)
        if prompt not in focus:
            focus.append(prompt)

    is_construction = _contains_any(
        text,
        (
            "bygg",
            "anlaggning",
            "entreprenad",
            "markentreprenor",
            "groundwork",
            "construction",
            "asfalt",
            "infrastruktur",
            "landskap",
            "landscape",
        ),
    )
    is_transport = _contains_any(
        text,
        (
            "fordon",
            "vehicle",
            "drivmedel",
            "fuel",
            "transport",
            "skolskjuts",
            "taxi",
            "buss",
            "bus",
            "fleet",
        ),
    )
    is_freight = _contains_any(text, ("frakt", "freight", "leverans", "delivery", "flytt"))
    is_energy = _contains_any(
        text,
        (
            "energi",
            "energy",
            "elektric",
            "electricity",
            "varme",
            "värme",
            "gasol",
            "heat pump",
            "varmepump",
            "ventilation",
        ),
    )
    is_adaptation = _contains_any(
        text,
        (
            "klimatanpass",
            "adaptation",
            "skyfall",
            "flood",
            "oversvam",
            "dagvatten",
            "stormwater",
            "resilien",
        ),
    )
    is_food = _contains_any(
        text,
        (
            "livsmedel",
            "food",
            "catering",
            "kott",
            "kött",
            "mejeri",
            "dairy",
            "fisk",
            "fish",
            "kitchen",
            "kok ",
        ),
    )
    is_chemicals = _contains_any(
        text,
        (
            "kemisk",
            "chemical",
            "pfas",
            "bekampnings",
            "pesticide",
            "farligt avfall",
            "hazard",
            "sanering",
            "remediation",
        ),
    )
    is_cleaning = _contains_any(text, ("stadning", "städning", "stadmaterial", "städmaterial", "rengor", "rengör", "cleaning", "lokalvard"))
    water_terms = ("vatten", "water", "avlopp", "wastewater", "dagvatten", "stormwater", "spillvatten")
    is_water = _contains_any(detail_text, water_terms) or (
        _contains_any(text, water_terms)
        and not _contains_any(text, ("gasol", "heat pump", "varmepump", "varme", "värme", "energi", "energy"))
    )
    is_marine = _contains_any(text, ("marine", "marin", "coastal", "kust", "skaldjur", "seafood"))
    is_green_space = _contains_any(
        text,
        (
            "gronyta",
            "grönyta",
            "gronyteskotsel",
            "grönyteskötsel",
            "green space",
            "green area",
            "park",
            "biodiversity",
            "biologisk",
            "trad ",
            "träd ",
            "vaxt",
            "växt",
        ),
    )
    is_circular = _contains_any(
        text,
        ("avfall", "waste", "recycling", "atervinning", "återvinning", "aterbruk", "återbruk", "reuse"),
    )
    is_durable_goods = _contains_any(
        text,
        (
            "mobler",
            "möbler",
            "inventar",
            "furniture",
            "vitvaror",
            "appliance",
            "textil",
            "textile",
        ),
    )
    is_ict = _contains_any(
        text,
        (
            "it och teknik",
            "hardvara",
            "hårdvara",
            "dator",
            "computer",
            "mobiltelefon",
            "server",
            "skrivare",
            "printer",
            "ict",
            "network",
            "nätverk",
        ),
    )
    is_plastics = _contains_any(text, ("plast", "plastic"))

    if is_construction:
        add(
            "Construction and land",
            "Check materials, reuse, energy performance, land use and biodiversity; the category alone does not show a positive or negative outcome.",
        )
    if is_transport:
        add(
            "Transport and fleet",
            "Check the purpose, mode, fuel or technology and available alternative; transport is not automatically lower impact.",
        )
    if is_freight:
        add(
            "Freight and deliveries",
            "Check whether demand can be reduced and record vehicle or fuel, load, route and delivery efficiency where available.",
        )
    if is_energy:
        add(
            "Energy and heating",
            "Check the energy source and whether the purchase concerns supply, efficiency or fossil combustion; interpret it in its system context.",
        )
    if is_adaptation:
        add(
            "Climate adaptation",
            "Record the resilience function, such as flood, stormwater, heat or climate-proof building measures.",
        )
    if is_food:
        add(
            "Food and catering",
            "Distinguish product groups and sourcing. Meat and dairy can have higher climate relevance than other food purchases.",
        )
    if is_chemicals:
        add(
            "Chemicals and hazardous substances",
            "Check the substance, hazard profile, likely release pathway and disposal route before treating it as a pollution issue.",
        )
    if is_cleaning and not is_chemicals:
        add(
            "Cleaning products and services",
            "Cleaning is not automatically a pollution issue. Check chemical content, concentration and disposal information.",
        )
    if is_water:
        add(
            "Water and wastewater",
            "Distinguish water quantity, water quality, wastewater or stormwater function, and any relevant infrastructure effects.",
        )
    if is_marine:
        add(
            "Marine and coastal resources",
            "Check whether there is a direct marine or coastal dependency or impact; local coastal expertise may be needed.",
        )
    if is_green_space:
        add(
            "Green space and biodiversity",
            "Check habitat outcome, native species, pesticide use and ecological management. Maintenance alone is not evidence of a biodiversity benefit.",
        )
    if is_circular:
        add(
            "Waste, reuse and circularity",
            "Check the treatment path and whether the purchase prevents waste, enables reuse or only manages disposal.",
        )
    if is_durable_goods:
        add(
            "Durability and repair",
            "Look for specification evidence on lifespan, warranty, repairability, spare parts, reuse or take-back arrangements.",
        )
    if is_ict:
        add(
            "ICT equipment",
            "Check device lifespan, repairability, reuse or take-back arrangements, and relevant energy use for hardware or networks.",
        )
    if is_plastics:
        add(
            "Plastics",
            "Consider both material use and pollution pathways. Plastic can cut across resource use and pollution rather than sit in only one theme.",
        )
    if classification.primary == "Unmatched":
        add(
            "Mapping gap",
            "Review the category hierarchy and invoice description, then add a municipal mapping entry if this is a recurring purchase.",
        )
    topic_labels = _topic_subcategories(tags, detail_text)
    classification.review_focus = tuple(focus)
    classification.context_tags = tuple(tags)
    classification.subcategories = _subcategories_for(classification.primary, topic_labels)
    classification.related_topics = _related_topics_for(classification.primary, topic_labels)
    return classification


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle in text for needle in needles)


def _guidance_text(row: Dict[str, str]) -> str:
    """Use categories and descriptions, not department names, for context prompts."""

    columns = (
        "Inköpskategori 1",
        "Inköpskategori 2",
        "Inköpskategori 3",
        "Nivå 1 (SV)",
        "Nivå 2 (SV)",
        "Nivå 3 (SV)",
        "Nivå 1 (EN)",
        "Nivå 2 (EN)",
        "Nivå 3 (EN)",
        "Procurement Category",
        "UNSPSC",
        "Konto",
        "Fakturatext",
        "Description",
    )
    values = [str(row.get(column, "")) for column in columns if row.get(column, "")]
    return normalize_key(" ".join(values or [str(value) for value in row.values()]))


def _guidance_detail_text(row: Dict[str, str]) -> str:
    columns = (
        "Inköpskategori 3",
        "Nivå 3 (SV)",
        "Nivå 3 (EN)",
        "Fakturatext",
        "Description",
    )
    return normalize_key(" ".join(str(row.get(column, "")) for column in columns if row.get(column, "")))


def _topic_subcategories(context_tags: Sequence[str], detail_text: str) -> Tuple[str, ...]:
    """Map contextual signals to the practical E1-E5 hierarchy used in the tool.

    These labels are then separated into a primary-theme subcategory and any
    related cross-theme topics. This prevents an E2 row, for example, from
    appearing to have an E1 subcategory in the dashboard.
    """

    labels: List[str] = []

    def add(*values: str) -> None:
        for value in values:
            if value not in labels:
                labels.append(value)

    for tag in context_tags:
        if tag == "Energy and heating":
            add("E1.1 Energy, heating and efficiency")
        elif tag == "Transport and fleet":
            add("E1.2 Transport, fleet and mobility")
        elif tag == "Freight and deliveries":
            add("E1.3 Freight and deliveries")
        elif tag == "Climate adaptation":
            add("E1.4 Climate adaptation and resilience")
        elif tag == "Food and catering":
            add("E1.5 Food and catering")
        elif tag == "Construction and land":
            add("E1.6 Construction and built environment", "E4.2 Land use and habitat")
        elif tag == "Chemicals and hazardous substances":
            add("E2.1 Chemicals, hazardous substances and remediation")
        elif tag == "Cleaning products and services":
            add("E2.2 Cleaning products and services")
        elif tag == "Plastics":
            add("E2.3 Plastics and pollution pathways", "E5.4 Materials and packaging")
        elif tag == "Water and wastewater":
            if _contains_any(detail_text, ("avlopp", "wastewater", "dagvatten", "stormwater", "spillvatten")):
                add("E3.2 Wastewater, stormwater and water systems")
            else:
                add("E3.1 Water supply and use")
        elif tag == "Marine and coastal resources":
            add("E3.3 Marine and coastal resources")
        elif tag == "Green space and biodiversity":
            add("E4.1 Green space and ecological management")
        elif tag == "Waste, reuse and circularity":
            add("E5.1 Waste prevention, reuse and recycling")
        elif tag == "Durability and repair":
            add("E5.2 Durable goods, repair and take-back")
        elif tag == "ICT equipment":
            add("E5.3 ICT equipment and lifecycle")

    return tuple(labels)


def _subcategories_for(primary: str, topic_labels: Sequence[str]) -> Tuple[str, ...]:
    return tuple(label for label in topic_labels if label.startswith(f"{primary}."))


def _related_topics_for(primary: str, topic_labels: Sequence[str]) -> Tuple[str, ...]:
    return tuple(label for label in topic_labels if not label.startswith(f"{primary}."))


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
