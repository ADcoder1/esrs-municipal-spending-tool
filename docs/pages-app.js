const invoiceInput = document.querySelector("#invoiceFile");
const mappingInput = document.querySelector("#mappingFile");
const analyzeButton = document.querySelector("#analyzeButton");
const sampleButton = document.querySelector("#sampleButton");
const exportButton = document.querySelector("#exportButton");
const statusEl = document.querySelector("#status");
const resultsEl = document.querySelector("#results");

let lastRows = [];

const labels = {
  E1: "Climate change",
  E2: "Pollution",
  E3: "Water and marine resources",
  E4: "Biodiversity and ecosystems",
  E5: "Resource use and circular economy",
  None: "Not environmentally relevant by default",
  Unmatched: "No mapping found",
};

const categoryColumns = [
  "Inköpskategori 3",
  "Inköpskategori 2",
  "Inköpskategori 1",
  "Nivå 3 (SV)",
  "Nivå 2 (SV)",
  "Nivå 1 (SV)",
  "Nivå 3 (EN)",
  "Nivå 2 (EN)",
  "Nivå 1 (EN)",
];

analyzeButton.addEventListener("click", async () => {
  try {
    if (!invoiceInput.files[0] || !mappingInput.files[0]) {
      throw new Error("Choose both an invoice CSV and a mapping CSV, or use the sample data.");
    }
    setStatus("Analyzing local CSV files...");
    const invoiceText = await invoiceInput.files[0].text();
    const mappingText = await mappingInput.files[0].text();
    runAnalysis(invoiceText, mappingText);
  } catch (error) {
    setStatus(error.message, true);
  }
});

sampleButton.addEventListener("click", async () => {
  try {
    setStatus("Loading synthetic sample data...");
    const [invoiceResponse, mappingResponse] = await Promise.all([
      fetch("demo/sample_invoices.csv"),
      fetch("demo/sample_mapping.csv"),
    ]);
    if (!invoiceResponse.ok || !mappingResponse.ok) {
      throw new Error("Could not load sample data.");
    }
    runAnalysis(await invoiceResponse.text(), await mappingResponse.text());
  } catch (error) {
    setStatus(error.message, true);
  }
});

exportButton.addEventListener("click", () => {
  const csv = toCsv(lastRows);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "classified_esrs_rows.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
});

function runAnalysis(invoiceText, mappingText) {
  const mappingRows = parseCsv(mappingText);
  const invoiceRows = parseCsv(invoiceText);
  const mapping = buildMapping(mappingRows);
  const classified = invoiceRows.map((row) => {
    const c = classify(row, mapping);
    const amount = amountFor(row);
    return {
      ...row,
      "ESRS Primary": c.primary,
      "ESRS Label": labels[c.primary] || "",
      "ESRS Secondary": c.secondary,
      "ESRS Confidence": c.confidence,
      "ESRS Method": c.method,
      "ESRS Amount": amount.toFixed(2),
    };
  });

  lastRows = classified;
  render(classified, Object.keys(mapping).length);
  setStatus(`Processed ${classified.length.toLocaleString()} rows in your browser. No data was uploaded.`);
}

function buildMapping(rows) {
  const mapping = {};
  rows.forEach((row) => {
    const primary = normalizeEsrs(row["Proposed ESRS Primary (E1–E5 / None)"] || row["Proposed ESRS Primary"] || "");
    if (!primary) return;
    const secondary = normalizeEsrs(row["Proposed ESRS Secondary (optional)"] || "", true);
    const confidence = row["Confidence (High / Medium / Needs review)"] || row.Confidence || "Unspecified";
    categoryColumns.forEach((column) => {
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
  for (const column of categoryColumns) {
    const value = row[column];
    if (!value) continue;
    for (const candidate of candidateKeys(value)) {
      if (mapping[candidate]) return mapping[candidate];
    }
  }
  return { primary: "Unmatched", secondary: "", confidence: "Needs review", method: "unmatched" };
}

function amountFor(row) {
  if (row.Belopp || row.Amount) return parseNumber(row.Belopp || row.Amount);
  return ["Köp på prislista", "Köp inom avtal", "Köp utanför avtal", "Köp utan avtal"]
    .map((column) => parseNumber(row[column]))
    .reduce((sum, value) => sum + value, 0);
}

function render(rows, mappingCount) {
  resultsEl.classList.remove("hidden");
  exportButton.classList.remove("hidden");

  const counts = {};
  const amounts = {};
  const confidence = {};
  const category = {};
  rows.forEach((row) => {
    const code = row["ESRS Primary"];
    const amount = parseNumber(row["ESRS Amount"]);
    counts[code] = (counts[code] || 0) + 1;
    amounts[code] = (amounts[code] || 0) + amount;
    confidence[row["ESRS Confidence"]] = (confidence[row["ESRS Confidence"]] || 0) + 1;
    const cat = bestCategory(row);
    const key = `${code}||${cat}`;
    category[key] = category[key] || { code, cat, rows: 0, amount: 0 };
    category[key].rows += 1;
    category[key].amount += amount;
  });

  const classified = ["E1", "E2", "E3", "E4", "E5"].reduce((sum, code) => sum + (counts[code] || 0), 0);
  document.querySelector("#rowsMetric").textContent = rows.length.toLocaleString();
  document.querySelector("#mappingMetric").textContent = mappingCount.toLocaleString();
  document.querySelector("#classifiedMetric").textContent = `${Math.round((classified / Math.max(rows.length, 1)) * 100)}%`;
  document.querySelector("#noneMetric").textContent = (counts.None || 0).toLocaleString();

  renderBars("#themeBars", Object.entries(amounts).map(([code, value]) => ({ label: `${code} · ${labels[code] || ""}`, value })), formatNumber);
  renderBars("#confidenceBars", Object.entries(confidence).map(([label, value]) => ({ label, value })), (v) => v.toLocaleString());

  const categoryRows = Object.values(category).sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount)).slice(0, 12);
  const body = document.querySelector("#categoryRows");
  body.innerHTML = "";
  categoryRows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(row.code)}</td><td>${escapeHtml(row.cat)}</td><td>${row.rows.toLocaleString()}</td><td>${formatNumber(row.amount)}</td>`;
    body.appendChild(tr);
  });
}

function renderBars(selector, rows, formatter) {
  const el = document.querySelector(selector);
  el.innerHTML = "";
  const max = Math.max(...rows.map((row) => Math.abs(row.value)), 1);
  rows.sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).forEach((row) => {
    const item = document.createElement("div");
    item.className = "bar-row";
    item.innerHTML = `
      <div class="bar-meta"><span>${escapeHtml(row.label)}</span><span>${escapeHtml(formatter(row.value))}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, Math.abs(row.value) / max * 100)}%"></div></div>
    `;
    el.appendChild(item);
  });
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
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
  const headers = rows.shift().map((value) => value.trim());
  return rows
    .filter((values) => values.some((value) => value.trim()))
    .map((values) => Object.fromEntries(headers.map((header, index) => [header, (values[index] || "").trim()])));
}

function toCsv(rows) {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const lines = [headers];
  rows.forEach((row) => lines.push(headers.map((header) => row[header] || "")));
  return lines.map((line) => line.map(csvCell).join(",")).join("\n");
}

function csvCell(value) {
  const text = String(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function candidateKeys(value) {
  const key = normalizeKey(value);
  const candidates = [key];
  if (String(value).includes(" - ")) candidates.push(normalizeKey(String(value).split(" - ").slice(1).join(" - ")));
  if (key.includes("-")) candidates.push(normalizeKey(key.split("-").slice(1).join("-")));
  return [...new Set(candidates.filter(Boolean))];
}

function normalizeEsrs(value, allowBlank = false) {
  const text = String(value || "").trim();
  if (!text) return allowBlank ? "" : "";
  const match = text.toUpperCase().match(/\b(E[1-5])\b/);
  if (match) return match[1];
  if (normalizeKey(text) === "none") return "None";
  return "";
}

function normalizeKey(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("sv-SE")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("&", " and ")
    .replace(/[^\p{L}\p{N}_\- ]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function bestCategory(row) {
  for (const column of categoryColumns) {
    if (row[column]) return row[column];
  }
  return "Unspecified";
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

function formatNumber(value) {
  return new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 0 }).format(value);
}

function setStatus(message, error = false) {
  statusEl.textContent = message;
  statusEl.className = error ? "status error" : "status";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
