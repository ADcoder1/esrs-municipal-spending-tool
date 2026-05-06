const form = document.querySelector("#analyzeForm");
const statusPanel = document.querySelector("#statusPanel");
const results = document.querySelector("#results");
const downloadLink = document.querySelector("#downloadLink");
const categoryDownloadLink = document.querySelector("#categoryDownloadLink");
const invoiceInput = document.querySelector("#invoiceFile");
const mappingInput = document.querySelector("#mappingFile");
const useDefaultInvoice = document.querySelector("#useDefaultInvoice");
const useDefaultMapping = document.querySelector("#useDefaultMapping");
const sheetIndexInput = document.querySelector("#sheetIndex");
const sheetHint = document.querySelector("#sheetHint");
const sourceSummary = document.querySelector("#sourceSummary");
const invoiceSourceName = document.querySelector("#invoiceSourceName");
const invoiceSourceMeta = document.querySelector("#invoiceSourceMeta");
const mappingSourceName = document.querySelector("#mappingSourceName");
const mappingSourceMeta = document.querySelector("#mappingSourceMeta");
const notesSourceName = document.querySelector("#notesSourceName");
const notesSourceMeta = document.querySelector("#notesSourceMeta");

let currentConfig = null;

const currency = new Intl.NumberFormat("sv-SE", {
  maximumFractionDigits: 0,
});

fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    currentConfig = config;
    useDefaultInvoice.disabled = !config.default_invoice_exists;
    useDefaultInvoice.checked = config.default_invoice_exists;
    useDefaultMapping.disabled = !config.default_mapping_exists;
    useDefaultMapping.checked = config.default_mapping_exists;
    renderSourceSummary(config);
    renderSheetHint(config);
    syncInputToggles();
  })
  .catch(() => {
    sourceSummary.textContent = "Local source check failed";
  });

invoiceInput.addEventListener("change", () => {
  if (invoiceInput.files.length) {
    useDefaultInvoice.checked = false;
  }
  syncInputToggles();
});

mappingInput.addEventListener("change", () => {
  if (mappingInput.files.length) {
    useDefaultMapping.checked = false;
  }
  syncInputToggles();
});

useDefaultInvoice.addEventListener("change", syncInputToggles);
useDefaultMapping.addEventListener("change", syncInputToggles);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const label =
    sheetIndexInput.value === "0"
      ? "Analyzing first worksheet..."
      : `Analyzing worksheet ${sheetIndexInput.value}...`;
  setStatus(label, false);
  downloadLink.classList.add("disabled");
  categoryDownloadLink.classList.add("disabled");
  results.classList.add("hidden");

  const body = new FormData(form);
  body.set("export_rows", "true");

  try {
    const response = await fetch("/api/analyze", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Analysis failed");
    }
    renderResults(payload);
    const sheetName = payload.sheet_names?.[payload.sheet_index] || `worksheet ${payload.sheet_index}`;
    const invoiceLabel = fileNameFromPath(payload.invoice_file);
    setStatus(
      `Processed ${formatNumber(payload.processed_rows)} rows from ${sheetName} in ${payload.duration_seconds}s using ${formatNumber(payload.mapping_entries)} mapping entries from ${invoiceLabel}.`,
      false
    );
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelector(`#${button.dataset.tab}`).classList.add("active");
  });
});

function renderResults(payload) {
  results.classList.remove("hidden");
  const classifiedPercent = payload.processed_rows
    ? Math.round((payload.classified_rows / payload.processed_rows) * 100)
    : 0;
  document.querySelector("#rowsMetric").textContent = formatNumber(payload.processed_rows);
  document.querySelector("#amountMetric").textContent = formatMoney(payload.total_amount);
  document.querySelector("#classifiedMetric").textContent = `${classifiedPercent}%`;
  document.querySelector("#reviewMetric").textContent = formatNumber(payload.review_count);

  renderBars("#amountBars", payload.amount_by_esrs, "value", formatMoney, true);
  renderBars("#confidenceBars", counterToSeries(payload.confidence_counts), "value", formatNumber, false);
  renderBars("#cautionBars", counterToSeries(payload.caution_counts), "value", formatNumber, false);
  renderBars("#climateBars", counterToSeries(payload.climate_split), "value", formatNumber, false);
  renderBars("#gapBars", payload.data_gaps, "missing", (value, item) => `${formatNumber(value)} (${item.percent.toFixed(1)}%)`, false);
  renderMethodology(payload.methodology_notes || []);
  renderCategories(payload.top_categories);
  renderReviewRows(payload.review_rows);

  if (payload.export_id) {
    downloadLink.href = `/api/export/${payload.export_id}`;
    downloadLink.classList.remove("disabled");
  }
  if (payload.category_export_id) {
    categoryDownloadLink.href = `/api/export/${payload.category_export_id}`;
    categoryDownloadLink.classList.remove("disabled");
  }
}

function renderBars(selector, rows, valueKey, formatter, useEsrsClass) {
  const element = document.querySelector(selector);
  element.innerHTML = "";
  const max = Math.max(...rows.map((row) => Math.abs(Number(row[valueKey]) || 0)), 1);
  rows.forEach((row) => {
    const label = row.code ? `${row.code} · ${row.label}` : row.column || row.label;
    const value = Number(row[valueKey]) || 0;
    const bar = document.createElement("div");
    bar.className = "bar-row";
    const fillClass = useEsrsClass ? row.code : "";
    bar.innerHTML = `
      <div class="bar-meta">
        <span>${escapeHtml(label)}</span>
        <span>${escapeHtml(formatter(value, row))}</span>
      </div>
      <div class="bar-track"><div class="bar-fill ${escapeHtml(fillClass)}" style="width:${Math.max(2, Math.abs(value) / max * 100)}%"></div></div>
    `;
    element.appendChild(bar);
  });
  if (!rows.length) {
    element.textContent = "No rows.";
  }
}

function renderCategories(rows) {
  const body = document.querySelector("#categoryRows");
  body.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.esrs)}<br><small>${escapeHtml(row.label)}</small></td>
      <td>${escapeHtml(row.category)}</td>
      <td>${formatNumber(row.rows)}</td>
      <td class="amount">${formatMoney(row.amount)}</td>
    `;
    body.appendChild(tr);
  });
}

function renderReviewRows(rows) {
  const body = document.querySelector("#reviewRows");
  body.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.primary)}<br><small>${escapeHtml(row.label)}</small></td>
      <td>${escapeHtml(row.confidence)}</td>
      <td>${escapeHtml(row.category)}</td>
      <td>${escapeHtml(row.department || row.unit)}</td>
      <td>${escapeHtml(row.supplier)}</td>
      <td class="amount">${formatMoney(row.amount)}</td>
    `;
    body.appendChild(tr);
  });
}

function renderMethodology(notes) {
  const list = document.querySelector("#methodologyNotes");
  list.innerHTML = "";
  notes.forEach((note) => {
    const item = document.createElement("li");
    item.textContent = note;
    list.appendChild(item);
  });
}

function counterToSeries(counter) {
  return Object.entries(counter).map(([label, value]) => ({ label, value }));
}

function renderSourceSummary(config) {
  const invoiceReady = config.default_invoice_exists;
  const mappingReady = config.default_mapping_exists;
  const notesReady = config.meeting_notes_exists;
  sourceSummary.textContent = `${invoiceReady ? "invoice ready" : "invoice missing"} · ${mappingReady ? "mapping ready" : "mapping missing"} · ${notesReady ? "notes ready" : "notes missing"}`;

  invoiceSourceName.textContent = invoiceReady ? config.default_invoice_name : "Not detected";
  invoiceSourceMeta.textContent = invoiceReady
    ? `${formatBytes(config.default_invoice_size_bytes)} · ${formatSheetMeta(config.default_invoice_sheet_names)}`
    : "Choose a local file or update config.local.json";

  mappingSourceName.textContent = mappingReady ? config.default_mapping_name : "Not detected";
  mappingSourceMeta.textContent = mappingReady
    ? `${formatBytes(config.default_mapping_size_bytes)}`
    : "Choose a local file or update config.local.json";

  notesSourceName.textContent = notesReady ? config.meeting_notes_name : "Not detected";
  notesSourceMeta.textContent = notesReady
    ? "Meeting notes available"
    : "Optional reference file";
}

function renderSheetHint(config) {
  const names = config.default_invoice_sheet_names || [];
  if (!names.length) {
    sheetHint.textContent = "0 = first worksheet";
    return;
  }
  sheetHint.textContent = names.map((name, index) => `${index}: ${name}`).join(" · ");
}

function syncInputToggles() {
  const useConfiguredInvoice = useDefaultInvoice.checked;
  const useConfiguredMapping = useDefaultMapping.checked;

  invoiceInput.disabled = useConfiguredInvoice;
  mappingInput.disabled = useConfiguredMapping;

  if (useConfiguredInvoice && invoiceInput.value) {
    invoiceInput.value = "";
  }
  if (useConfiguredMapping && mappingInput.value) {
    mappingInput.value = "";
  }
}

function setStatus(message, isError) {
  statusPanel.textContent = message;
  statusPanel.classList.remove("hidden", "error");
  if (isError) {
    statusPanel.classList.add("error");
  }
}

function formatMoney(value) {
  return currency.format(Number(value) || 0);
}

function formatNumber(value) {
  return currency.format(Number(value) || 0);
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (!bytes) {
    return "0 B";
  }
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${bytes} B`;
}

function formatSheetMeta(sheetNames) {
  const names = sheetNames || [];
  if (!names.length) {
    return "worksheet list unavailable";
  }
  return `${names.length} worksheet${names.length === 1 ? "" : "s"}`;
}

function fileNameFromPath(path) {
  const value = String(path || "");
  const parts = value.split(/[\\/]/);
  return parts[parts.length - 1] || value;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
