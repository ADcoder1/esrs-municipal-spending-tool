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
    sourceSummary.textContent = "Could not read the current local defaults";
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
      ? "Reviewing the first worksheet..."
      : `Reviewing worksheet ${sheetIndexInput.value}...`;
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
      `Reviewed ${formatNumber(payload.processed_rows)} purchases from ${sheetName} in ${payload.duration_seconds}s using the selected category guide for ${invoiceLabel}.`,
      false
    );
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tab));
});

document.querySelectorAll("[data-tab-target]").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tabTarget));
});

function renderResults(payload) {
  results.classList.remove("hidden");
  const classifiedPercent = payload.processed_rows
    ? Math.round((payload.classified_rows / payload.processed_rows) * 100)
    : 0;
  document.querySelector("#rowsMetric").textContent = formatNumber(payload.processed_rows);
  document.querySelector("#amountMetric").textContent = formatValueInThousands(payload.total_amount);
  document.querySelector("#classifiedMetric").textContent = `${classifiedPercent}%`;
  document.querySelector("#noneMetric").textContent = formatNumber(payload.none_rows);
  document.querySelector("#unmatchedMetric").textContent = formatNumber(payload.unmatched_rows);
  document.querySelector("#reviewMetric").textContent = formatNumber(payload.review_count);
  renderPriority(payload, classifiedPercent);

  renderBars("#amountBars", payload.amount_by_esrs, "value", formatValueInThousands, true);
  renderBars("#confidenceBars", counterToSeries(payload.confidence_counts), "value", formatNumber, false);
  renderBars("#cautionBars", counterToSeries(payload.caution_counts), "value", formatNumber, false);
  renderBars("#subcategoryBars", counterToSeries(payload.subcategory_counts), "value", formatNumber, false);
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
    const label = row.code ? readableThemeLabel(row.code, row.label) : row.column || row.label;
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
      <td>${escapeHtml(readableThemeLabel(row.esrs, row.label))}</td>
      <td title="${escapeHtml(row.subcategories)}">${escapeHtml(shortTopicLabel(row.subcategories || (row.esrs === "None" ? "Not applicable" : "No detailed topic available")))}</td>
      <td>${escapeHtml(row.category)}</td>
      <td>${formatNumber(row.rows)}</td>
      <td class="amount">${formatValueInThousands(row.amount)}</td>
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
      <td>${escapeHtml(readableThemeLabel(row.primary, row.label))}</td>
      <td title="${escapeHtml(row.subcategories)}">${escapeHtml(shortTopicLabel(row.subcategories || (row.primary === "None" ? "Not applicable" : "No detailed topic available")))}</td>
      <td>${escapeHtml(row.category)}</td>
      <td title="${escapeHtml(row.review_focus)}">${escapeHtml(row.context_tags || "Confirm category and invoice description")}</td>
      <td>${escapeHtml(row.department || row.unit)}</td>
      <td>${escapeHtml(row.supplier)}</td>
      <td class="amount">${formatValueInThousands(row.amount)}</td>
    `;
    body.appendChild(tr);
  });
}

function renderPriority(payload, classifiedPercent) {
  const heading = document.querySelector("#priorityHeading");
  const text = document.querySelector("#priorityText");
  const unmatchedRows = Number(payload.unmatched_rows) || 0;
  const reviewRows = Number(payload.review_count) || 0;
  const noneRows = Number(payload.none_rows) || 0;

  if (unmatchedRows) {
    heading.textContent = "Start with the purchases that are not yet categorised";
    text.textContent = `${formatNumber(unmatchedRows)} purchases could not be linked to an environmental topic. Together they represent ${formatValueInThousands(payload.unmatched_amount)} ('000). Check recurring purchasing categories first, then add them to your category guide. ${formatNumber(reviewRows)} purchases also need a human check.`;
    return;
  }

  if (reviewRows) {
    heading.textContent = "Next, check the suggested links";
    text.textContent = `${classifiedPercent}% of purchases were linked to an environmental topic and ${formatNumber(noneRows)} are outside environmental scope by default. Focus on the ${formatNumber(reviewRows)} purchases that need a human check before using the results in a discussion or decision.`;
    return;
  }

  heading.textContent = "Your results are ready to explore";
  text.textContent = `${classifiedPercent}% of purchases were linked to an environmental topic and ${formatNumber(noneRows)} are outside environmental scope by default. Use the environmental topics tab to see the largest groups of spending.`;
}

function activateTab(tabId) {
  const target = document.querySelector(`#${tabId}`);
  const tab = document.querySelector(`.tab[data-tab="${tabId}"]`);
  if (!target || !tab) return;
  document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
  tab.classList.add("active");
  target.classList.add("active");
}

function readableThemeLabel(code, label) {
  if (code === "None") return "Outside environmental scope";
  if (code === "Unmatched") return "Not yet categorised";
  return `${label} (${code})`;
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

  if (invoiceReady && mappingReady) {
    sourceSummary.textContent = notesReady
      ? "Review setup is ready, with meeting notes available"
      : "Review setup is ready";
  } else if (invoiceReady) {
    sourceSummary.textContent = "Add a category guide before running a full review";
  } else if (mappingReady) {
    sourceSummary.textContent = "Add a spending file to begin";
  } else {
    sourceSummary.textContent = "Add a spending file and category guide to begin";
  }

  invoiceSourceName.textContent = invoiceReady ? config.default_invoice_name : "Not detected";
  invoiceSourceMeta.textContent = invoiceReady
    ? `${formatBytes(config.default_invoice_size_bytes)} · ${formatSheetMeta(config.default_invoice_sheet_names)}`
    : "Choose a local spending file below or save one in the desktop app.";

  mappingSourceName.textContent = mappingReady ? config.default_mapping_name : "Not detected";
  mappingSourceMeta.textContent = mappingReady
    ? `${formatBytes(config.default_mapping_size_bytes)} · Links purchasing categories to environmental topics`
    : "Choose a reviewed category guide below or save one in the desktop app.";

  notesSourceName.textContent = notesReady ? config.meeting_notes_name : "Not detected";
  notesSourceMeta.textContent = notesReady
    ? "Optional meeting notes available for review discussions"
    : "Optional notes file for review discussions";
}

function renderSheetHint(config) {
  const names = config.default_invoice_sheet_names || [];
  if (!names.length) {
    sheetHint.textContent = "Worksheet 0 is usually the main spending sheet.";
    return;
  }
  sheetHint.textContent = `Available worksheets: ${names.map((name, index) => `${index}: ${name}`).join(" · ")}`;
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

function formatValueInThousands(value) {
  return currency.format((Number(value) || 0) / 1000);
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
