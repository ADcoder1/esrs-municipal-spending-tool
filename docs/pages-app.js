import { ESRS_LABELS, analyzeRows, formatNumber, parseCsvMatrix, readTableFile, rowsToObjects } from "./pages-core.mjs";

const invoiceInput = document.querySelector("#invoiceFile");
const mappingInput = document.querySelector("#mappingFile");
const useBuiltInMappingInput = document.querySelector("#useBuiltInMapping");
const analyzeButton = document.querySelector("#analyzeButton");
const sampleButton = document.querySelector("#sampleButton");
const exportButton = document.querySelector("#exportButton");
const statusEl = document.querySelector("#status");
const resultsEl = document.querySelector("#results");

let lastRows = [];

analyzeButton.addEventListener("click", async () => {
  try {
    if (!invoiceInput.files[0]) {
      throw new Error("Choose an invoice or procurement CSV/XLSX file, or use the sample data.");
    }

    setStatus("Analyzing file in your browser...");
    const invoiceRows = await readTableFile(invoiceInput.files[0]);
    const mappingRows = await loadMappingRows();
    const mappingSource = mappingInput.files[0]
      ? mappingInput.files[0].name
      : useBuiltInMappingInput.checked
        ? "built-in demo mapping"
        : "no mapping";

    runAnalysis(invoiceRows, mappingRows, mappingSource);
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
    const invoiceRows = rowsFromText(await invoiceResponse.text());
    const mappingRows = rowsFromText(await mappingResponse.text());
    runAnalysis(invoiceRows, mappingRows, "built-in demo mapping");
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

async function loadMappingRows() {
  if (mappingInput.files[0]) {
    return readTableFile(mappingInput.files[0]);
  }
  if (!useBuiltInMappingInput.checked) {
    throw new Error("Upload a category-to-ESRS mapping file, or enable the built-in demo mapping.");
  }
  const response = await fetch("demo/sample_mapping.csv");
  if (!response.ok) {
    throw new Error("Could not load the built-in demo mapping.");
  }
  return rowsFromText(await response.text());
}

function rowsFromText(text) {
  return rowsToObjects(parseCsvMatrix(text));
}

function runAnalysis(invoiceRows, mappingRows, mappingSource) {
  const { classified, mappingCount } = analyzeRows(invoiceRows, mappingRows);

  lastRows = classified;
  render(classified, mappingCount);
  setStatus(
    `Processed ${classified.length.toLocaleString()} rows in your browser using ${mappingSource}. No data was uploaded.`
  );
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

  renderBars("#themeBars", Object.entries(amounts).map(([code, value]) => ({ label: `${code} · ${ESRS_LABELS[code] || ""}`, value })), formatNumber);
  renderBars("#confidenceBars", Object.entries(confidence).map(([label, value]) => ({ label, value })), (value) => value.toLocaleString());

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

function bestCategory(row) {
  for (const column of [
    "Inköpskategori 3",
    "Inköpskategori 2",
    "Inköpskategori 1",
    "Nivå 3 (SV)",
    "Nivå 2 (SV)",
    "Nivå 1 (SV)",
    "Nivå 3 (EN)",
    "Nivå 2 (EN)",
    "Nivå 1 (EN)",
  ]) {
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
