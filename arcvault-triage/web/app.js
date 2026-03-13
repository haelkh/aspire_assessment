const state = {
  samples: [],
  selectedSampleId: null,
};

const sourceInput = document.getElementById("source");
const messageInput = document.getElementById("message");
const requestIdInput = document.getElementById("request-id");
const externalIdInput = document.getElementById("external-id");
const customerIdInput = document.getElementById("customer-id");
const receivedAtInput = document.getElementById("received-at");
const channelMetadataInput = document.getElementById("channel-metadata");

const sampleButtonsEl = document.getElementById("sample-buttons");
const samplePreviewEl = document.getElementById("sample-preview");
const statusLineEl = document.getElementById("status-line");

const metricCategoryEl = document.getElementById("metric-category");
const metricPriorityEl = document.getElementById("metric-priority");
const metricQueueEl = document.getElementById("metric-queue");
const metricConfidenceEl = document.getElementById("metric-confidence");
const metricConfidenceLevelEl = document.getElementById("metric-confidence-level");
const metricConfidenceSourceEl = document.getElementById("metric-confidence-source");
const confidenceBarEl = document.getElementById("confidence-bar");
const summaryTextEl = document.getElementById("summary-text");
const rulesListEl = document.getElementById("rules-list");
const evidenceListEl = document.getElementById("evidence-list");
const jsonOutputEl = document.getElementById("json-output");

const escalationBannerEl = document.getElementById("escalation-banner");
const escalationReasonEl = document.getElementById("escalation-reason");
const errorBannerEl = document.getElementById("error-banner");
const errorReasonEl = document.getElementById("error-reason");

const batchBodyEl = document.getElementById("batch-body");
const batchBtn = document.getElementById("btn-batch");
const processBtn = document.getElementById("btn-process");

const aiAlertsCardEl = document.getElementById("ai-alerts-card");
const aiAlertsListEl = document.getElementById("ai-alerts-list");

function setStatus(message, isError = false) {
  statusLineEl.textContent = message;
  statusLineEl.classList.toggle("error", isError);
}

function setTab(tabName) {
  const intakeTab = document.getElementById("tab-intake");
  const batchTab = document.getElementById("tab-batch");
  const intakeView = document.getElementById("view-intake");
  const batchView = document.getElementById("view-batch");

  if (tabName === "batch") {
    intakeTab.classList.remove("active");
    batchTab.classList.add("active");
    intakeView.classList.remove("active");
    batchView.classList.add("active");
  } else {
    batchTab.classList.remove("active");
    intakeTab.classList.add("active");
    batchView.classList.remove("active");
    intakeView.classList.add("active");
  }
}

function asPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "-";
  }
  return `${(num * 100).toFixed(1)}%`;
}

function escapeHtml(raw) {
  const text = String(raw ?? "");
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getSourcePlaceholder(source) {
  if (source === "Email") {
    return "Subject: Login blocked for multiple users\n\nHi support,\nWe started seeing 403 errors after the latest update...";
  }
  if (source === "Web Form") {
    return "Organization: Northbridge Compliance Group\nRequest type: Feature Request\nDetails: Need bulk export for audit logs...";
  }
  return "Ticket #SP-2001\nSeverity: High\nDescription: Invoice mismatch between contract and charged amount...";
}

function applySourcePlaceholder() {
  messageInput.placeholder = getSourcePlaceholder(sourceInput.value);
}

function renderSampleButtons() {
  sampleButtonsEl.innerHTML = "";
  state.samples.forEach((sample) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sample-btn";
    button.textContent = `#${sample.id} ${sample.source}`;
    if (sample.id === state.selectedSampleId) {
      button.classList.add("active");
    }
    button.addEventListener("click", () => {
      state.selectedSampleId = sample.id;
      renderSampleButtons();
      applySample(sample);
    });
    sampleButtonsEl.appendChild(button);
  });
}

function renderEmailPreview(payload) {
  return `
    <div class="sample-email">
      <div class="sample-email-head">
        <span class="key">From</span><span>${escapeHtml(payload.from || "-")}</span>
        <span class="key">To</span><span>${escapeHtml(payload.to || "-")}</span>
        <span class="key">Subject</span><span>${escapeHtml(payload.subject || "-")}</span>
      </div>
      <div class="sample-email-body">${escapeHtml(payload.body || "")}</div>
    </div>
  `;
}

function renderWebFormPreview(payload) {
  return `
    <div class="sample-web-form">
      <div class="sample-form-grid">
        <div class="sample-field">
          <span class="key">Organization</span>
          <span>${escapeHtml(payload.organization || "-")}</span>
        </div>
        <div class="sample-field">
          <span class="key">Contact</span>
          <span>${escapeHtml(payload.contact_name || "-")}</span>
        </div>
        <div class="sample-field">
          <span class="key">Email</span>
          <span>${escapeHtml(payload.contact_email || "-")}</span>
        </div>
        <div class="sample-field">
          <span class="key">Request Type</span>
          <span>${escapeHtml(payload.request_type || "-")}</span>
        </div>
        <div class="sample-field full">
          <span class="key">Details</span>
          <span>${escapeHtml(payload.details || "-")}</span>
        </div>
        <div class="sample-field full">
          <span class="key">Business Impact</span>
          <span>${escapeHtml(payload.business_impact || "-")}</span>
        </div>
      </div>
    </div>
  `;
}

function renderPortalPreview(payload) {
  const tags = Array.isArray(payload.tags) ? payload.tags.join(", ") : "-";
  return `
    <div class="sample-portal">
      <div class="portal-head">
        <span><strong>Ticket:</strong> ${escapeHtml(payload.ticket_id || "-")}</span>
        <span><strong>Workspace:</strong> ${escapeHtml(payload.workspace || "-")}</span>
        <span><strong>Reporter:</strong> ${escapeHtml(payload.reporter || "-")}</span>
        <span><strong>Severity:</strong> ${escapeHtml(payload.severity || "-")}</span>
      </div>
      <p class="portal-desc">${escapeHtml(payload.description || "-")}</p>
      <p class="portal-desc"><strong>Tags:</strong> ${escapeHtml(tags)}</p>
    </div>
  `;
}

function renderSamplePreview(sample = null) {
  if (!sample) {
    samplePreviewEl.innerHTML = `<p class="sample-empty">Choose a sample to preview realistic channel format.</p>`;
    return;
  }

  if (sample.source === "Email" && sample.email_payload) {
    samplePreviewEl.innerHTML = renderEmailPreview(sample.email_payload);
    return;
  }
  if (sample.source === "Web Form" && sample.web_form_payload) {
    samplePreviewEl.innerHTML = renderWebFormPreview(sample.web_form_payload);
    return;
  }
  if (sample.source === "Support Portal" && sample.portal_payload) {
    samplePreviewEl.innerHTML = renderPortalPreview(sample.portal_payload);
    return;
  }

  samplePreviewEl.innerHTML = `<p class="sample-empty">${escapeHtml(sample.message || "")}</p>`;
}

function applySample(sample) {
  sourceInput.value = sample.source || "Email";
  messageInput.value = sample.message || "";

  const prefill = sample.prefill || {};
  requestIdInput.value = prefill.request_id || "";
  externalIdInput.value = prefill.external_id || "";
  customerIdInput.value = prefill.customer_id || "";
  receivedAtInput.value = prefill.received_at || "";
  channelMetadataInput.value = prefill.channel_metadata
    ? JSON.stringify(prefill.channel_metadata, null, 2)
    : "";

  applySourcePlaceholder();
  renderSamplePreview(sample);
}

function resetResultPanel() {
  metricCategoryEl.textContent = "-";
  metricPriorityEl.textContent = "-";
  metricQueueEl.textContent = "-";
  metricConfidenceEl.textContent = "-";
  setConfidenceBadge(null);
  metricConfidenceSourceEl.textContent = "-";
  confidenceBarEl.style.width = "0%";
  summaryTextEl.textContent = "Submit a request to see a human-readable summary.";
  rulesListEl.innerHTML = "";
  evidenceListEl.innerHTML = "";
  jsonOutputEl.textContent = "{}";
  escalationBannerEl.classList.add("hidden");
  errorBannerEl.classList.add("hidden");
  errorReasonEl.textContent = "-";
  aiAlertsCardEl.classList.add("hidden");
  aiAlertsListEl.innerHTML = "";
}

function renderRules(rules) {
  rulesListEl.innerHTML = "";
  if (!Array.isArray(rules) || rules.length === 0) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = "none";
    rulesListEl.appendChild(chip);
    return;
  }

  rules.forEach((rule) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = rule;
    rulesListEl.appendChild(chip);
  });
}

function renderEvidence(evidence) {
  evidenceListEl.innerHTML = "";
  if (!Array.isArray(evidence) || evidence.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No rule evidence for this request.";
    evidenceListEl.appendChild(item);
    return;
  }

  evidence.forEach((line) => {
    const item = document.createElement("li");
    item.textContent = line;
    evidenceListEl.appendChild(item);
  });
}

function confidenceColor(confidence) {
  if (confidence >= 0.85) {
    return "#2dd4bf";
  }
  if (confidence >= 0.7) {
    return "#f7b267";
  }
  return "#ff6b6b";
}

function confidenceLevel(confidence) {
  if (confidence >= 0.85) {
    return "High";
  }
  if (confidence >= 0.7) {
    return "Medium";
  }
  return "Low";
}

function confidenceBadgeClass(level) {
  if (level === "High") return "high";
  if (level === "Medium") return "medium";
  if (level === "Low") return "low";
  return "neutral";
}

function formatConfidenceSource(source) {
  if (source === "model") return "Model";
  if (source === "fallback") return "Fallback";
  return "-";
}

function setConfidenceBadge(level) {
  metricConfidenceLevelEl.textContent = level || "-";
  metricConfidenceLevelEl.className = `confidence-badge ${confidenceBadgeClass(level)}`;
}

function retriggerAnimation(element, className) {
  if (!element) return;
  element.classList.remove(className);
  void element.offsetWidth;
  element.classList.add(className);
}

function triggerResultRefresh() {
  retriggerAnimation(document.querySelector(".pane-output"), "result-refresh");
}

function renderResult(result) {
  const confidence = Number(result.confidence);
  const confidenceSafe = Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence)) : 0;
  const confidencePct = confidenceSafe * 100;
  const level = result.confidence_level || confidenceLevel(confidenceSafe);
  const source = formatConfidenceSource(result.confidence_source);

  metricCategoryEl.textContent = result.category || "-";
  metricPriorityEl.textContent = result.priority || "-";
  metricQueueEl.textContent = result.destination_queue || "-";
  metricConfidenceEl.textContent = asPercent(confidenceSafe);
  setConfidenceBadge(level);
  metricConfidenceSourceEl.textContent = source;
  confidenceBarEl.style.width = `${Math.max(0, Math.min(100, confidencePct))}%`;
  confidenceBarEl.style.background = confidenceColor(confidenceSafe);

  summaryTextEl.textContent = result.human_summary || "No summary returned.";
  renderRules(result.escalation_rules_triggered);
  renderEvidence(result.escalation_rule_evidence);
  errorBannerEl.classList.add("hidden");
  errorReasonEl.textContent = "-";

  const aiFlags = [
    ...(result.classification_guardrail_flags || []),
    ...(result.enrichment_guardrail_flags || []),
  ];

  if (aiFlags.length > 0) {
    aiAlertsCardEl.classList.remove("hidden");
    aiAlertsListEl.innerHTML = "";
    aiFlags.forEach((flag) => {
      const chip = document.createElement("span");
      chip.className = "chip error";
      chip.textContent = flag;
      aiAlertsListEl.appendChild(chip);
    });
  } else {
    aiAlertsCardEl.classList.add("hidden");
  }

  if (result.escalation_flag) {
    escalationBannerEl.classList.remove("hidden");
    escalationReasonEl.textContent = result.escalation_reason || "Escalation required.";
  } else {
    escalationBannerEl.classList.add("hidden");
  }

  jsonOutputEl.textContent = JSON.stringify(result, null, 2);
  triggerResultRefresh();
}

function renderProcessingError(message) {
  resetResultPanel();
  errorReasonEl.textContent = message || "Request failed.";
  errorBannerEl.classList.remove("hidden");
  aiAlertsCardEl.classList.add("hidden");
  aiAlertsListEl.innerHTML = "";
  jsonOutputEl.textContent = JSON.stringify({ error: message || "Request failed." }, null, 2);
  triggerResultRefresh();
}

function parseChannelMetadata() {
  const raw = channelMetadataInput.value.trim();
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error("Channel metadata must be a JSON object.");
    }
    return parsed;
  } catch (error) {
    throw new Error("Channel metadata must be valid JSON object.");
  }
}

function buildPayload() {
  const payload = {
    source: sourceInput.value,
    message: messageInput.value,
  };

  const requestId = requestIdInput.value.trim();
  const externalId = externalIdInput.value.trim();
  const customerId = customerIdInput.value.trim();
  const receivedAt = receivedAtInput.value.trim();

  if (requestId) payload.request_id = requestId;
  if (externalId) payload.external_id = externalId;
  if (customerId) payload.customer_id = customerId;
  if (receivedAt) payload.received_at = receivedAt;

  const channelMetadata = parseChannelMetadata();
  if (channelMetadata) {
    payload.channel_metadata = channelMetadata;
  }

  return payload;
}

async function processRequest(event) {
  event.preventDefault();
  setStatus("Processing...");
  processBtn.disabled = true;

  try {
    const payload = buildPayload();
    const response = await fetch("/api/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      const detail = data?.detail || "Request failed.";
      throw new Error(detail);
    }

    renderResult(data);
    const replay = data.idempotent_replay ? " (idempotent replay)" : "";
    setStatus(`Processed successfully${replay}.`);
  } catch (error) {
    renderProcessingError(error.message || "Failed to process request.");
    setStatus(error.message || "Failed to process request.", true);
  } finally {
    processBtn.disabled = false;
  }
}

function clearForm() {
  sourceInput.value = "Email";
  messageInput.value = "";
  requestIdInput.value = "";
  externalIdInput.value = "";
  customerIdInput.value = "";
  receivedAtInput.value = "";
  channelMetadataInput.value = "";
  state.selectedSampleId = null;
  renderSampleButtons();
  renderSamplePreview(null);
  applySourcePlaceholder();
  resetResultPanel();
  setStatus("Form cleared.");
}

function renderBatchRows(records) {
  batchBodyEl.innerHTML = "";

  if (!Array.isArray(records) || records.length === 0) {
    batchBodyEl.innerHTML = `<tr><td colspan="8" class="muted-row">No batch records returned.</td></tr>`;
    return;
  }

  records.forEach((record) => {
    if (record.error) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${escapeHtml(record.sample_id ?? "-")}</td>
        <td>${escapeHtml(record.source ?? "-")}</td>
        <td colspan="6">${escapeHtml(record.error)}</td>
      `;
      batchBodyEl.appendChild(row);
      return;
    }

    const escalatedBadge = record.escalation_flag
      ? `<span class="badge yes">YES</span>`
      : `<span class="badge no">NO</span>`;
    const replayBadge = record.idempotent_replay
      ? `<span class="badge replay">Replay</span>`
      : `<span class="badge no">Fresh</span>`;
    const confidence = Number(record.confidence);
    const confidenceSafe = Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence)) : 0;
    const level = record.confidence_level || confidenceLevel(confidenceSafe);
    const source = formatConfidenceSource(record.confidence_source);
    const confidenceCell = `
      <div class="batch-confidence">
        <strong>${escapeHtml(asPercent(confidenceSafe))}</strong>
        <span class="batch-confidence-meta">${escapeHtml(level)} | ${escapeHtml(source)}</span>
      </div>
    `;

    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(record.sample_id ?? "-")}</td>
      <td>${escapeHtml(record.source ?? "-")}</td>
      <td>${escapeHtml(record.category ?? "-")}</td>
      <td>${escapeHtml(record.priority ?? "-")}</td>
      <td>${confidenceCell}</td>
      <td>${escapeHtml(record.destination_queue ?? "-")}</td>
      <td>${escalatedBadge}</td>
      <td>${replayBadge}</td>
    `;
    batchBodyEl.appendChild(row);
  });
}

async function runBatch() {
  batchBtn.disabled = true;
  batchBtn.textContent = "Running...";
  setStatus("Running batch QA...");

  try {
    const response = await fetch("/api/batch", { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.detail || "Batch run failed.");
    }

    renderBatchRows(data.records);
    setStatus(`Batch complete: ${data.count} samples processed.`);
  } catch (error) {
    setStatus(error.message || "Batch run failed.", true);
  } finally {
    batchBtn.disabled = false;
    batchBtn.textContent = "Run Batch (All Samples)";
  }
}

async function bootstrap() {
  resetResultPanel();
  applySourcePlaceholder();
  renderSamplePreview(null);
  setStatus("Loading samples...");

  try {
    const response = await fetch("/api/samples");
    const data = await response.json();
    state.samples = Array.isArray(data.samples) ? data.samples : [];
    renderSampleButtons();
    setStatus("Ready.");
  } catch (error) {
    setStatus("Failed to load samples.", true);
  }
}

document.getElementById("triage-form").addEventListener("submit", processRequest);
document.getElementById("btn-clear").addEventListener("click", clearForm);
document.getElementById("tab-intake").addEventListener("click", () => setTab("intake"));
document.getElementById("tab-batch").addEventListener("click", () => setTab("batch"));
batchBtn.addEventListener("click", runBatch);
sourceInput.addEventListener("change", () => {
  applySourcePlaceholder();
  const selected = state.samples.find((sample) => sample.id === state.selectedSampleId);
  if (selected) {
    renderSamplePreview(selected);
  }
});

bootstrap();
