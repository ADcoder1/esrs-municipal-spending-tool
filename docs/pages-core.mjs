const ESRS_LABELS = {
  E1: "Climate change",
  E2: "Pollution",
  E3: "Water and marine resources",
  E4: "Biodiversity and ecosystems",
  E5: "Resource use and circular economy",
  None: "Not environmentally relevant by default",
  Unmatched: "No mapping found",
};

const CATEGORY_COLUMNS = [
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
];

const MAPPING_CATEGORY_COLUMNS = [
  "Nivå 3 (SV)",
  "Nivå 2 (SV)",
  "Nivå 1 (SV)",
  "Nivå 3 (EN)",
  "Nivå 2 (EN)",
  "Nivå 1 (EN)",
  "Inköpskategori 3",
  "Inköpskategori 2",
  "Inköpskategori 1",
  "Inköpskategori 3 (SV)",
  "Inköpskategori 2 (SV)",
  "Inköpskategori 1 (SV)",
  "Inköpskategori 3 (EN)",
  "Inköpskategori 2 (EN)",
  "Inköpskategori 1 (EN)",
  "Procurement Category",
];

const KNOWN_HEADER_KEYS = new Set([
  "niva 1 sv",
  "inkopskategori 1",
  "proposed esrs primary e1-e5 none",
  "proposed esrs primary e1 e5 none",
  "forvaltning",
]);

const MAX_BROWSER_XLSX_BYTES = 25 * 1024 * 1024;

export {
  ESRS_LABELS,
  CATEGORY_COLUMNS,
  buildMapping,
  formatNumber,
  normalizeKey,
  parseCsvMatrix,
  parseNumber,
  rowsToObjects,
};

export async function readTableFile(file) {
  const name = String(file?.name || "").toLowerCase();
  if (name.endsWith(".csv")) {
    return rowsToObjects(parseCsvMatrix(await file.text()));
  }
  if (name.endsWith(".xlsx")) {
    if ((file?.size || 0) > MAX_BROWSER_XLSX_BYTES) {
      const sizeMb = ((file.size || 0) / (1024 * 1024)).toFixed(1);
      throw new Error(
        `This Excel file is ${sizeMb} MB. The browser demo is for smaller files only. Use the local Python app for large municipal workbooks.`
      );
    }
    return rowsToObjects(await parseXlsxMatrix(await file.arrayBuffer()));
  }
  throw new Error("Unsupported file type. Use CSV or XLSX.");
}

export function analyzeRows(invoiceRows, mappingRows) {
  const mapping = buildMapping(mappingRows);
  const classified = invoiceRows.map((row) => {
    const classification = classify(row, mapping);
    const amount = amountFor(row);
    return {
      ...row,
      "ESRS Primary": classification.primary,
      "ESRS Label": ESRS_LABELS[classification.primary] || "",
      "ESRS Secondary": classification.secondary,
      "ESRS Confidence": classification.confidence,
      "ESRS Method": classification.method,
      "ESRS Amount": amount.toFixed(2),
    };
  });
  return { classified, mappingCount: Object.keys(mapping).length };
}

function parseXlsxMatrix(buffer) {
  return unzipEntries(new Uint8Array(buffer)).then(async (entries) => {
    const sharedStrings = entries.has("xl/sharedStrings.xml")
      ? parseSharedStrings(await entryText(entries.get("xl/sharedStrings.xml")))
      : [];
    const sheets = await sheetPaths(entries);
    if (!sheets.length) {
      throw new Error("No worksheets were found in the XLSX file.");
    }
    const sheetXml = await entryText(entries.get(sheets[0].path));
    return parseSheetRows(sheetXml, sharedStrings);
  });
}

async function unzipEntries(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const eocdOffset = findEocdOffset(bytes);
  if (eocdOffset < 0) {
    throw new Error("Could not read XLSX container.");
  }
  const entryCount = view.getUint16(eocdOffset + 10, true);
  const centralDirOffset = view.getUint32(eocdOffset + 16, true);
  let cursor = centralDirOffset;
  const entries = new Map();

  for (let index = 0; index < entryCount; index += 1) {
    if (view.getUint32(cursor, true) !== 0x02014b50) {
      throw new Error("Invalid XLSX central directory.");
    }
    const compression = view.getUint16(cursor + 10, true);
    const compressedSize = view.getUint32(cursor + 20, true);
    const fileNameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const localHeaderOffset = view.getUint32(cursor + 42, true);
    const fileName = decodeText(bytes.subarray(cursor + 46, cursor + 46 + fileNameLength));

    if (view.getUint32(localHeaderOffset, true) !== 0x04034b50) {
      throw new Error("Invalid XLSX local file header.");
    }
    const localNameLength = view.getUint16(localHeaderOffset + 26, true);
    const localExtraLength = view.getUint16(localHeaderOffset + 28, true);
    const dataOffset = localHeaderOffset + 30 + localNameLength + localExtraLength;
    const compressed = bytes.slice(dataOffset, dataOffset + compressedSize);
    entries.set(fileName, {
      compression,
      bytes: await inflateEntry(compression, compressed),
    });

    cursor += 46 + fileNameLength + extraLength + commentLength;
  }
  return entries;
}

async function inflateEntry(compression, compressed) {
  if (compression === 0) {
    return compressed;
  }
  if (compression !== 8) {
    throw new Error(`Unsupported XLSX compression method: ${compression}`);
  }
  if (typeof DecompressionStream !== "function") {
    throw new Error("This browser cannot read Excel files yet. Please use CSV.");
  }
  const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  const buffer = await new Response(stream).arrayBuffer();
  return new Uint8Array(buffer);
}

function findEocdOffset(bytes) {
  for (let cursor = bytes.length - 22; cursor >= Math.max(0, bytes.length - 65557); cursor -= 1) {
    if (
      bytes[cursor] === 0x50 &&
      bytes[cursor + 1] === 0x4b &&
      bytes[cursor + 2] === 0x05 &&
      bytes[cursor + 3] === 0x06
    ) {
      return cursor;
    }
  }
  return -1;
}

async function sheetPaths(entries) {
  if (!entries.has("xl/workbook.xml") || !entries.has("xl/_rels/workbook.xml.rels")) {
    return [...entries.keys()]
      .filter((name) => name.startsWith("xl/worksheets/sheet"))
      .sort()
      .map((name) => ({ name: name.split("/").pop().replace(".xml", ""), path: name }));
  }

  const workbook = await entryText(entries.get("xl/workbook.xml"));
  const rels = await entryText(entries.get("xl/_rels/workbook.xml.rels"));
  const relationships = new Map();

  for (const rel of matchXmlElements(rels, "Relationship")) {
    const relId = attrValue(rel.attrs, "Id");
    const target = attrValue(rel.attrs, "Target") || "";
    if (!relId) return;
    relationships.set(relId, target.startsWith("/") ? target.slice(1) : `xl/${target.replace(/^\/+/, "")}`);
  }

  return matchXmlElements(workbook, "sheet")
    .map((sheet) => {
      const relId = attrValue(sheet.attrs, "r:id") || attrValue(sheet.attrs, "id");
      const path = relationships.get(relId);
      if (!path) return null;
      return { name: attrValue(sheet.attrs, "name") || "Sheet", path };
    })
    .filter(Boolean);
}

function parseSharedStrings(xmlText) {
  const strings = [];
  const siPattern = /<si\b[^>]*>([\s\S]*?)<\/si>/g;
  let siMatch;
  while ((siMatch = siPattern.exec(xmlText))) {
    const parts = [];
    const tPattern = /<t\b[^>]*>([\s\S]*?)<\/t>/g;
    let tMatch;
    while ((tMatch = tPattern.exec(siMatch[1]))) {
      parts.push(decodeXmlText(tMatch[1]));
    }
    strings.push(parts.join(""));
  }
  return strings;
}

function parseSheetRows(xmlText, sharedStrings) {
  const rows = [];
  const rowPattern = /<row\b[^>]*>([\s\S]*?)<\/row>/g;
  let rowMatch;
  while ((rowMatch = rowPattern.exec(xmlText))) {
    rows.push(parseSheetRow(rowMatch[1], sharedStrings));
  }
  return rows;
}

function parseSheetRow(row, sharedStrings) {
  const values = [];
  const cellPattern = /<c\b([^>]*)>([\s\S]*?)<\/c>|<c\b([^>]*)\/>/g;
  let cellMatch;
  while ((cellMatch = cellPattern.exec(row))) {
    const attrs = cellMatch[1] || cellMatch[3] || "";
    const inner = cellMatch[2] || "";
    const ref = attrValue(attrs, "r") || "";
    const columnIndex = columnIndexFromRef(ref);
    while (values.length <= columnIndex) {
      values.push("");
    }
    values[columnIndex] = parseSheetCell(attrs, inner, sharedStrings);
  }
  return values;
}

function parseSheetCell(attrs, inner, sharedStrings) {
  const cellType = attrValue(attrs, "t");
  const rawValue = inner.match(/<v\b[^>]*>([\s\S]*?)<\/v>/)?.[1] || "";
  let inlineValue = "";
  const inlineMatch = inner.match(/<is\b[^>]*>([\s\S]*?)<\/is>/);
  if (inlineMatch) {
    const tPattern = /<t\b[^>]*>([\s\S]*?)<\/t>/g;
    let tMatch;
    const parts = [];
    while ((tMatch = tPattern.exec(inlineMatch[1]))) {
      parts.push(decodeXmlText(tMatch[1]));
    }
    inlineValue = parts.join("");
  }

  if (cellType === "s") {
    return sharedStrings[Number.parseInt(rawValue, 10)] || "";
  }
  if (cellType === "inlineStr") {
    return inlineValue;
  }
  if (cellType === "b") {
    return rawValue === "1" ? "TRUE" : "FALSE";
  }
  return rawValue || inlineValue;
}

function matchXmlElements(xmlText, tagName) {
  const escapedTag = tagName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(
    `<${escapedTag}\\b([^>]*)>([\\s\\S]*?)<\\/${escapedTag}>|<${escapedTag}\\b([^>]*)\\/>`,
    "g"
  );
  const matches = [];
  let match;
  while ((match = pattern.exec(xmlText))) {
    matches.push({
      attrs: match[1] || match[3] || "",
      inner: match[2] || "",
    });
  }
  return matches;
}

function attrValue(attrs, name) {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?:^|\\s)${escapedName}="([^"]*)"`);
  const match = pattern.exec(attrs);
  return match ? decodeXmlText(match[1]) : "";
}

function decodeXmlText(text) {
  return String(text || "")
    .replace(/&#(\d+);/g, (_, value) => String.fromCodePoint(Number.parseInt(value, 10)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, value) => String.fromCodePoint(Number.parseInt(value, 16)))
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

async function entryText(entry) {
  return decodeText(entry.bytes);
}

function decodeText(bytes) {
  return new TextDecoder("utf-8").decode(bytes);
}

function columnIndexFromRef(reference) {
  const match = String(reference).toUpperCase().match(/^([A-Z]+)/);
  if (!match) return 0;
  let value = 0;
  for (const char of match[1]) {
    value = value * 26 + (char.charCodeAt(0) - 64);
  }
  return value - 1;
}

function parseCsvMatrix(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

function rowsToObjects(rows) {
  const filtered = rows.filter((row) => row.some((value) => String(value || "").trim()));
  if (!filtered.length) {
    return [];
  }
  const headerIndex = findHeaderRow(filtered);
  const headers = dedupeHeaders(filtered[headerIndex].map((value) => String(value || "").trim()));
  return filtered
    .slice(headerIndex + 1)
    .filter((row) => row.some((value) => String(value || "").trim()))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, String(row[index] || "").trim()])));
}

function findHeaderRow(rows) {
  for (let index = 0; index < Math.min(rows.length, 20); index += 1) {
    const normalized = new Set(rows[index].map((cell) => normalizeKey(cell)));
    for (const key of normalized) {
      if (KNOWN_HEADER_KEYS.has(key)) {
        return index;
      }
    }
  }
  return 0;
}

function dedupeHeaders(headers) {
  const counts = new Map();
  return headers.map((header, index) => {
    const value = String(header || "").trim() || `Column ${index + 1}`;
    const count = counts.get(value) || 0;
    counts.set(value, count + 1);
    return count ? `${value}_${count + 1}` : value;
  });
}

function buildMapping(rows) {
  const mapping = {};
  rows.forEach((row) => {
    const primary = normalizeEsrs(row["Proposed ESRS Primary (E1–E5 / None)"] || row["Proposed ESRS Primary"] || "");
    if (!primary || primary === "Unmatched") {
      return;
    }
    const secondary = normalizeEsrs(row["Proposed ESRS Secondary (optional)"] || row["Proposed ESRS Secondary"] || "", true);
    const confidence = row["Confidence (High / Medium / Needs review)"] || row.Confidence || "Unspecified";
    MAPPING_CATEGORY_COLUMNS.forEach((column) => {
      if (!row[column]) return;
      mapping[normalizeKey(row[column])] = {
        primary,
        secondary,
        confidence,
        method: `mapping:${column}`,
      };
    });
  });
  return mapping;
}

function classify(row, mapping) {
  for (const column of CATEGORY_COLUMNS) {
    const value = row[column];
    if (!value) continue;
    for (const candidate of candidateKeys(value)) {
      if (mapping[candidate]) return mapping[candidate];
    }
  }
  const heuristic = heuristicClassification(row);
  if (heuristic) {
    return heuristic;
  }
  return { primary: "Unmatched", secondary: "", confidence: "Needs review", method: "unmatched" };
}

function heuristicClassification(row) {
  const text = normalizeKey(
    [
      row["Inköpskategori 1"],
      row["Inköpskategori 2"],
      row["Inköpskategori 3"],
      row.UNSPSC,
      row.Konto,
      row.Fakturatext,
    ]
      .filter(Boolean)
      .join(" ")
  );
  if (!text) {
    return null;
  }
  const rules = [
    ["E5", ["avfall", "waste", "recycling", "aterbruk", "återbruk", "circular", "material"], "heuristic:E5"],
    ["E3", ["vatten", "water", "marine", "wastewater", "avlopp"], "heuristic:E3"],
    ["E4", ["biodiversity", "biologisk", "gronyta", "gronyteskotsel", "park", "landskap", "växt", "vaxt"], "heuristic:E4"],
    ["E2", ["pollution", "kemisk", "chemical", "sanering", "hazard", "rengoring", "cleaning"], "heuristic:E2"],
    ["E1", ["drivmedel", "fuel", "fordon", "vehicle", "transport", "energy", "energi", "el ", "varme", "värme"], "heuristic:E1"],
  ];
  for (const [primary, needles, method] of rules) {
    if (needles.some((needle) => text.includes(needle))) {
      return {
        primary,
        secondary: "",
        confidence: "Needs review",
        method,
      };
    }
  }
  return null;
}

function amountFor(row) {
  if (row.Belopp || row.Amount) return parseNumber(row.Belopp || row.Amount);
  return ["Köp på prislista", "Köp inom avtal", "Köp utanför avtal", "Köp utan avtal"]
    .map((column) => parseNumber(row[column]))
    .reduce((sum, value) => sum + value, 0);
}

function parseNumber(value) {
  let text = String(value || "").trim().replace(/\s/g, "");
  if (!text || text === "-") return 0;
  text = text.replace(/[^\d,.-]/g, "");
  if (text.includes(",") && text.includes(".")) {
    text = text.lastIndexOf(",") > text.lastIndexOf(".") ? text.replaceAll(".", "").replace(",", ".") : text.replaceAll(",", "");
  } else if (text.includes(",")) {
    text = text.replace(",", ".");
  }
  return Number.parseFloat(text) || 0;
}

function normalizeEsrs(value, allowBlank = false) {
  const text = String(value || "").trim();
  if (!text) return allowBlank ? "" : "Unmatched";
  const match = text.toUpperCase().match(/\b(E[1-5])\b/);
  if (match) return match[1];
  if (normalizeKey(text) === "none" || normalizeKey(text) === "not environmentally relevant by default") return "None";
  return "Unmatched";
}

function candidateKeys(value) {
  const key = normalizeKey(value);
  const candidates = [key];
  if (String(value).includes(" - ")) candidates.push(normalizeKey(String(value).split(" - ").slice(1).join(" - ")));
  if (key.includes("-")) candidates.push(normalizeKey(key.split("-").slice(1).join("-")));
  return [...new Set(candidates.filter(Boolean))];
}

function normalizeKey(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("sv-SE")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("&", " and ")
    .replace(/[\u2010-\u2015]/g, "-")
    .replace(/[^\p{L}\p{N}_\- ]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatNumber(value) {
  return new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 0 }).format(value);
}
