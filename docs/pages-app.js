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
        ? "built-in Helsingborg mapping"
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
      fetch("demo/helsingborg_esrs_mapping_v2.csv"),
    ]);
    if (!invoiceResponse.ok || !mappingResponse.ok) {
      throw new Error("Could not load sample data.");
    }
    const invoiceRows = rowsFromText(await invoiceResponse.text());
    const mappingRows = rowsFromText(await mappingResponse.text());
    runAnalysis(invoiceRows, mappingRows, "built-in Helsingborg mapping");
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
    throw new Error("Upload a category-to-ESRS mapping file, or enable the built-in Helsingborg mapping.");
  }
  const response = await fetch("demo/helsingborg_esrs_mapping_v2.csv");
  if (!response.ok) {
    throw new Error("Could not load the built-in Helsingborg mapping.");
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
  const guidance = {};
  const subcategories = {};
  let totalAmount = 0;
  let unmatchedAmount = 0;
  rows.forEach((row) => {
    const code = row["ESRS Primary"];
    const amount = parseNumber(row["ESRS Amount"]);
    totalAmount += amount;
    counts[code] = (counts[code] || 0) + 1;
    amounts[code] = (amounts[code] || 0) + amount;
    if (code === "Unmatched") unmatchedAmount += amount;
    confidence[row["ESRS Confidence"]] = (confidence[row["ESRS Confidence"]] || 0) + 1;
    String(row["ESRS Context Tags"] || "")
      .split(";")
      .map((tag) => tag.trim())
      .filter(Boolean)
      .forEach((tag) => {
        guidance[tag] = (guidance[tag] || 0) + 1;
      });
    String(row["ESRS Subcategories"] || "")
      .split("|")
      .map((subcategory) => subcategory.trim())
      .filter(Boolean)
      .forEach((subcategory) => {
        subcategories[subcategory] = (subcategories[subcategory] || 0) + 1;
      });
    const cat = bestCategory(row);
    const subcategory = row["ESRS Subcategories"] || (code === "None" ? "Not applicable (None)" : "Not specific enough in the available data");
    const key = `${code}||${subcategory}||${cat}`;
    category[key] = category[key] || { code, subcategory, cat, rows: 0, amount: 0 };
    category[key].rows += 1;
    category[key].amount += amount;
  });

  const classified = ["E1", "E2", "E3", "E4", "E5"].reduce((sum, code) => sum + (counts[code] || 0), 0);
  const decisionRows = rows.filter(needsManualDecision);
  const reviewRows = representativeDecisionRows(decisionRows);
  const classifiedPercent = Math.round((classified / Math.max(rows.length, 1)) * 100);
  document.querySelector("#rowsMetric").textContent = rows.length.toLocaleString();
  document.querySelector("#amountMetric").textContent = formatNumber(totalAmount);
  document.querySelector("#classifiedMetric").textContent = `${classifiedPercent}%`;
  document.querySelector("#unmatchedMetric").textContent = (counts.Unmatched || 0).toLocaleString();
  document.querySelector("#reviewMetric").textContent = decisionRows.length.toLocaleString();
  renderPriority(counts.Unmatched || 0, unmatchedAmount, decisionRows.length, classifiedPercent);

  renderBars("#themeBars", Object.entries(amounts).map(([code, value]) => ({ label: `${code} · ${ESRS_LABELS[code] || ""}`, value })), formatNumber);
  renderBars("#confidenceBars", Object.entries(confidence).map(([label, value]) => ({ label, value })), (value) => value.toLocaleString());
  renderBars("#guidanceBars", Object.entries(guidance).map(([label, value]) => ({ label, value })), (value) => value.toLocaleString());
  renderBars("#subcategoryBars", Object.entries(subcategories).map(([label, value]) => ({ label, value })), (value) => value.toLocaleString());

  const categoryRows = Object.values(category).sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount)).slice(0, 12);
  const body = document.querySelector("#categoryRows");
  body.innerHTML = "";
  categoryRows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(row.code)}</td><td title="${escapeHtml(row.subcategory)}">${escapeHtml(shortTopicLabel(row.subcategory))}</td><td>${escapeHtml(row.cat)}</td><td>${row.rows.toLocaleString()}</td><td>${formatNumber(row.amount)}</td>`;
    body.appendChild(tr);
  });

  const reviewBody = document.querySelector("#reviewRows");
  reviewBody.innerHTML = "";
  reviewRows
    .slice(0, 25)
    .forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${escapeHtml(row["ESRS Primary"])}</td><td>${escapeHtml(bestCategory(row))}</td><td title="${escapeHtml(row["ESRS Review Focus"] || "")}">${escapeHtml(row["ESRS Context Tags"] || "Confirm category and invoice description")}</td><td>${formatNumber(parseNumber(row["ESRS Amount"]))}</td>`;
      reviewBody.appendChild(tr);
    });
}

function needsManualDecision(row) {
  return (
    row["ESRS Primary"] === "Unmatched" ||
    row["ESRS Confidence"] === "Needs review" ||
    String(row["ESRS Method"] || "").startsWith("heuristic")
  );
}

function representativeDecisionRows(rows) {
  const seen = new Set();
  return rows.filter((row) => Math.abs(parseNumber(row["ESRS Amount"])) > 0.005).filter((row) => {
    const key = [
      row["ESRS Primary"],
      bestCategory(row),
      row["Förvaltning"],
      row["Leverantörsnamn"],
      row["ESRS Method"],
    ].join("||");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function renderPriority(unmatchedRows, unmatchedAmount, reviewRows, classifiedPercent) {
  const heading = document.querySelector("#priorityHeading");
  const text = document.querySelector("#priorityText");
  if (unmatchedRows) {
    heading.textContent = "Review the mapping gaps first";
    text.textContent = `${unmatchedRows.toLocaleString()} rows have no category match yet, representing ${formatNumber(unmatchedAmount)} in net input value. Resolve recurring gaps before using theme totals for decisions. ${reviewRows.toLocaleString()} rows also need a manual decision.`;
    return;
  }
  heading.textContent = "Start with the rows that need a decision";
  text.textContent = `${classifiedPercent}% of rows have an E1-E5 theme. There are no unmatched rows in this run; focus next on the ${reviewRows.toLocaleString()} rows marked for a manual decision.`;
}

function shortTopicLabel(value) {
  const labels = {
    "E1.1 Energy, heating and efficiency": "E1.1 Energy and heating",
    "E1.2 Transport, fleet and mobility": "E1.2 Transport and fleet",
    "E1.3 Freight and deliveries": "E1.3 Freight and deliveries",
    "E1.4 Climate adaptation and resilience": "E1.4 Climate adaptation",
    "E1.5 Food and catering": "E1.5 Food and catering",
    "E1.6 Construction and built environment": "E1.6 Construction",
    "E2.1 Chemicals, hazardous substances and remediation": "E2.1 Chemicals and hazardous substances",
    "E2.2 Cleaning products and services": "E2.2 Cleaning",
    "E2.3 Plastics and pollution pathways": "E2.3 Plastics",
    "E3.1 Water supply and use": "E3.1 Water supply and use",
    "E3.2 Wastewater, stormwater and water systems": "E3.2 Wastewater and stormwater",
    "E3.3 Marine and coastal resources": "E3.3 Marine and coastal",
    "E4.1 Green space and ecological management": "E4.1 Green space",
    "E4.2 Land use and habitat": "E4.2 Land and habitat",
    "E5.1 Waste prevention, reuse and recycling": "E5.1 Waste and reuse",
    "E5.2 Durable goods, repair and take-back": "E5.2 Durable goods and repair",
    "E5.3 ICT equipment and lifecycle": "E5.3 ICT lifecycle",
    "E5.4 Materials and packaging": "E5.4 Materials and packaging",
  };
  return String(value || "").split(" | ").map((label) => labels[label] || label).join(" | ");
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
