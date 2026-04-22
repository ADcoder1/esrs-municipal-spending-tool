const form = document.querySelector("#analyzeForm");
const sourceStatus = document.querySelector("#sourceStatus");
const statusPanel = document.querySelector("#statusPanel");
const results = document.querySelector("#results");
const downloadLink = document.querySelector("#downloadLink");
const categoryDownloadLink = document.querySelector("#categoryDownloadLink");

const currency = new Intl.NumberFormat("sv-SE", {
  maximumFractionDigits: 0,
});

fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    if (sourceStatus) {
      const invoice = config.default_invoice_exists ? "invoice found" : "invoice missing";
      const mapping = config.default_mapping_exists ? "mapping found" : "mapping missing";
      const notes = config.meeting_notes_exists ? "meeting notes found" : "meeting notes missing";
      sourceStatus.textContent = `${invoice}; ${mapping}; ${notes}`;
    }
    document.querySelector("#useDefaultInvoice").disabled = !config.default_invoice_exists;
    document.querySelector("#useDefaultInvoice").checked = config.default_invoice_exists;
    document.querySelector("#useDefaultMapping").disabled = !config.default_mapping_exists;
    document.querySelector("#useDefaultMapping").checked = config.default_mapping_exists;
  })
  .catch(() => {
    sourceStatus.textContent = "Local source check failed";
  });

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Analyzing...", false);
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
    setStatus(
      `Processed ${formatNumber(payload.processed_rows)} rows in ${payload.duration_seconds}s using ${formatNumber(payload.mapping_entries)} mapping entries.`,
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
