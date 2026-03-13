/**
 * ArcVault Triage Console - Application Logic
 * ============================================
 */

// ============================================
// State Management
// ============================================
const state = {
  samples: [],
  selectedSampleId: null,
};

// ============================================
// DOM Elements
// ============================================
const elements = {
  // Form Inputs
  source: document.getElementById("source"),
  message: document.getElementById("message"),
  requestId: document.getElementById("request-id"),
  externalId: document.getElementById("external-id"),
  customerId: document.getElementById("customer-id"),
  receivedAt: document.getElementById("received-at"),
  channelMetadata: document.getElementById("channel-metadata"),

  // Sample Elements
  sampleButtons: document.getElementById("sample-buttons"),
  samplePreview: document.getElementById("sample-preview"),

  // Status
  statusLine: document.getElementById("status-line"),

  // Metrics
  metricCategory: document.getElementById("metric-category"),
  metricPriority: document.getElementById("metric-priority"),
  metricQueue: document.getElementById("metric-queue"),
  metricConfidence: document.getElementById("metric-confidence"),
  metricConfidenceLevel: document.getElementById("metric-confidence-level"),
  metricConfidenceSource: document.getElementById("metric-confidence-source"),
  confidenceBar: document.getElementById("confidence-bar"),

  // Results
  summaryText: document.getElementById("summary-text"),
  rulesList: document.getElementById("rules-list"),
  evidenceList: document.getElementById("evidence-list"),
  jsonOutput: document.getElementById("json-output"),

  // Banners
  escalationBanner: document.getElementById("escalation-banner"),
  escalationReason: document.getElementById("escalation-reason"),
  errorBanner: document.getElementById("error-banner"),
  errorReason: document.getElementById("error-reason"),

  // AI Alerts
  aiAlertsCard: document.getElementById("ai-alerts-card"),
  aiAlertsList: document.getElementById("ai-alerts-list"),

  // Batch
  batchBody: document.getElementById("batch-body"),
  batchBtn: document.getElementById("btn-batch"),
  processBtn: document.getElementById("btn-process"),

  // Tabs
  tabIntake: document.getElementById("tab-intake"),
  tabBatch: document.getElementById("tab-batch"),
  viewIntake: document.getElementById("view-intake"),
  viewBatch: document.getElementById("view-batch"),
};

// ============================================
// Utility Functions
// ============================================

/**
 * Sets the status message
 */
function setStatus(message, isError = false) {
  const statusSpan = elements.statusLine.querySelector("span");
  if (statusSpan) {
    statusSpan.textContent = message;
  }
  elements.statusLine.classList.toggle("error", isError);
}

/**
 * Builds a user-facing status line for processing + Sheets outcomes.
 */
function buildProcessingStatus(result) {
  if (result.idempotent_replay) {
    return "Processed as idempotent replay; no new Sheets row was written. Change Request ID (or message) for a fresh row.";
  }

  if (result.sheets_saved === true) {
    return "Processed successfully. Google Sheets row saved.";
  }

  const sheetsError = result.sheets_error
    ? ` Sheets error: ${result.sheets_error}`
    : "";
  return `Processed, but Google Sheets write failed.${sheetsError}`;
}

/**
 * Switches between tabs
 */
function setTab(tabName) {
  if (tabName === "batch") {
    elements.tabIntake.classList.remove("active");
    elements.tabBatch.classList.add("active");
    elements.viewIntake.classList.remove("active");
    elements.viewBatch.classList.add("active");
  } else {
    elements.tabBatch.classList.remove("active");
    elements.tabIntake.classList.add("active");
    elements.viewBatch.classList.remove("active");
    elements.viewIntake.classList.add("active");
  }
}

/**
 * Formats a number as a percentage
 */
function asPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `${(num * 100).toFixed(1)}%`;
}

/**
 * Escapes HTML special characters
 */
function escapeHtml(raw) {
  const text = String(raw ?? "");
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * Returns placeholder text based on source type
 */
function getSourcePlaceholder(source) {
  if (source === "Email") {
    return "Subject: Login blocked for multiple users\n\nHi support,\nWe started seeing 403 errors after the latest update...";
  }
  if (source === "Web Form") {
    return "Organization: Northbridge Compliance Group\nRequest type: Feature Request\nDetails: Need bulk export for audit logs...";
  }
  return "Ticket #SP-2001\nSeverity: High\nDescription: Invoice mismatch between contract and charged amount...";
}

/**
 * Updates the message placeholder based on source
 */
function applySourcePlaceholder() {
  elements.message.placeholder = getSourcePlaceholder(elements.source.value);
}

/**
 * Determines confidence level from score
 */
function confidenceLevel(confidence) {
  if (confidence >= 0.85) return "High";
  if (confidence >= 0.7) return "Medium";
  return "Low";
}

/**
 * Returns CSS class for confidence badge
 */
function confidenceBadgeClass(level) {
  if (level === "High") return "high";
  if (level === "Medium") return "medium";
  if (level === "Low") return "low";
  return "neutral";
}

/**
 * Formats confidence source for display
 */
function formatConfidenceSource(source) {
  if (source === "model") return "Model";
  if (source === "fallback") return "Fallback";
  return "-";
}

/**
 * Sets the confidence badge styling
 */
function setConfidenceBadge(level) {
  elements.metricConfidenceLevel.textContent = level || "-";
  elements.metricConfidenceLevel.className = `confidence-badge ${confidenceBadgeClass(level)}`;
}

/**
 * Triggers animation restart on an element
 */
function retriggerAnimation(element, className) {
  if (!element) return;
  element.classList.remove(className);
  void element.offsetWidth; // Force reflow
  element.classList.add(className);
}

/**
 * Triggers the result refresh animation
 */
function triggerResultRefresh() {
  const outputPane = document.querySelector(".panel-output");
  retriggerAnimation(outputPane, "result-refresh");
}

// ============================================
// Sample Rendering
// ============================================

/**
 * Renders the sample selection buttons
 */
function renderSampleButtons() {
  elements.sampleButtons.innerHTML = "";

  state.samples.forEach((sample) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sample-btn";
    if (sample.id === state.selectedSampleId) {
      button.classList.add("active");
    }
    button.textContent = `#${sample.id} ${sample.source}`;

    button.addEventListener("click", () => {
      state.selectedSampleId = sample.id;
      renderSampleButtons();
      applySample(sample);
    });

    elements.sampleButtons.appendChild(button);
  });
}

/**
 * Renders email sample preview
 */
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

/**
 * Renders web form sample preview
 */
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

/**
 * Renders support portal sample preview
 */
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

/**
 * Renders the sample preview based on type
 */
function renderSamplePreview(sample = null) {
  if (!sample) {
    elements.samplePreview.innerHTML = `<p class="empty-state">Choose a sample to preview realistic channel format.</p>`;
    return;
  }

  if (sample.source === "Email" && sample.email_payload) {
    elements.samplePreview.innerHTML = renderEmailPreview(sample.email_payload);
    return;
  }
  if (sample.source === "Web Form" && sample.web_form_payload) {
    elements.samplePreview.innerHTML = renderWebFormPreview(
      sample.web_form_payload,
    );
    return;
  }
  if (sample.source === "Support Portal" && sample.portal_payload) {
    elements.samplePreview.innerHTML = renderPortalPreview(
      sample.portal_payload,
    );
    return;
  }

  elements.samplePreview.innerHTML = `<p class="empty-state">${escapeHtml(sample.message || "")}</p>`;
}

/**
 * Applies a sample to the form
 */
function applySample(sample) {
  elements.source.value = sample.source || "Email";
  elements.message.value = sample.message || "";

  const prefill = sample.prefill || {};
  elements.requestId.value = prefill.request_id || "";
  elements.externalId.value = prefill.external_id || "";
  elements.customerId.value = prefill.customer_id || "";
  elements.receivedAt.value = prefill.received_at || "";
  elements.channelMetadata.value = prefill.channel_metadata
    ? JSON.stringify(prefill.channel_metadata, null, 2)
    : "";

  applySourcePlaceholder();
  renderSamplePreview(sample);
}

// ============================================
// Result Panel Management
// ============================================

/**
 * Resets the result panel to initial state
 */
function resetResultPanel() {
  elements.metricCategory.textContent = "-";
  elements.metricPriority.textContent = "-";
  elements.metricQueue.textContent = "-";
  elements.metricConfidence.textContent = "-";
  setConfidenceBadge(null);
  elements.metricConfidenceSource.textContent = "-";
  elements.confidenceBar.style.width = "0%";
  elements.summaryText.textContent =
    "Submit a request to see a human-readable summary.";
  elements.rulesList.innerHTML = "";
  elements.evidenceList.innerHTML = "";
  elements.jsonOutput.textContent = "{}";
  elements.escalationBanner.classList.add("hidden");
  elements.errorBanner.classList.add("hidden");
  elements.errorReason.textContent = "-";
  elements.aiAlertsCard.classList.add("hidden");
  elements.aiAlertsList.innerHTML = "";
}

/**
 * Renders escalation rules as chips
 */
function renderRules(rules) {
  elements.rulesList.innerHTML = "";

  if (!Array.isArray(rules) || rules.length === 0) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = "none";
    elements.rulesList.appendChild(chip);
    return;
  }

  rules.forEach((rule) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = rule;
    elements.rulesList.appendChild(chip);
  });
}

/**
 * Renders evidence list items
 */
function renderEvidence(evidence) {
  elements.evidenceList.innerHTML = "";

  if (!Array.isArray(evidence) || evidence.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No rule evidence for this request.";
    elements.evidenceList.appendChild(item);
    return;
  }

  evidence.forEach((line) => {
    const item = document.createElement("li");
    item.textContent = line;
    elements.evidenceList.appendChild(item);
  });
}

/**
 * Renders the complete result from API response
 */
function renderResult(result) {
  const confidence = Number(result.confidence);
  const confidenceSafe = Number.isFinite(confidence)
    ? Math.max(0, Math.min(1, confidence))
    : 0;
  const confidencePct = confidenceSafe * 100;
  const level = result.confidence_level || confidenceLevel(confidenceSafe);
  const source = formatConfidenceSource(result.confidence_source);

  // Update metrics
  elements.metricCategory.textContent = result.category || "-";
  elements.metricPriority.textContent = result.priority || "-";
  elements.metricQueue.textContent = result.destination_queue || "-";
  elements.metricConfidence.textContent = asPercent(confidenceSafe);
  setConfidenceBadge(level);
  elements.metricConfidenceSource.textContent = source;

  // Animate confidence bar
  elements.confidenceBar.style.width = `${Math.max(0, Math.min(100, confidencePct))}%`;

  // Update result cards
  elements.summaryText.textContent =
    result.human_summary || "No summary returned.";
  renderRules(result.escalation_rules_triggered);
  renderEvidence(result.escalation_rule_evidence);

  // Clear error state
  elements.errorBanner.classList.add("hidden");
  elements.errorReason.textContent = "-";

  // Handle AI alerts
  const aiFlags = [
    ...(result.classification_guardrail_flags || []),
    ...(result.enrichment_guardrail_flags || []),
  ];

  if (aiFlags.length > 0) {
    elements.aiAlertsCard.classList.remove("hidden");
    elements.aiAlertsList.innerHTML = "";
    aiFlags.forEach((flag) => {
      const chip = document.createElement("span");
      chip.className = "chip error";
      chip.textContent = flag;
      elements.aiAlertsList.appendChild(chip);
    });
  } else {
    elements.aiAlertsCard.classList.add("hidden");
  }

  // Handle escalation banner
  if (result.escalation_flag) {
    elements.escalationBanner.classList.remove("hidden");
    elements.escalationReason.textContent =
      result.escalation_reason || "Escalation required.";
  } else {
    elements.escalationBanner.classList.add("hidden");
  }

  // Update JSON output
  elements.jsonOutput.textContent = JSON.stringify(result, null, 2);

  // Trigger animation
  triggerResultRefresh();
}

/**
 * Renders a processing error
 */
function renderProcessingError(message) {
  resetResultPanel();
  elements.errorReason.textContent = message || "Request failed.";
  elements.errorBanner.classList.remove("hidden");
  elements.aiAlertsCard.classList.add("hidden");
  elements.aiAlertsList.innerHTML = "";
  elements.jsonOutput.textContent = JSON.stringify(
    { error: message || "Request failed." },
    null,
    2,
  );
  triggerResultRefresh();
}

// ============================================
// Form Handling
// ============================================

/**
 * Parses channel metadata JSON
 */
function parseChannelMetadata() {
  const raw = elements.channelMetadata.value.trim();
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    if (
      parsed === null ||
      Array.isArray(parsed) ||
      typeof parsed !== "object"
    ) {
      throw new Error("Channel metadata must be a JSON object.");
    }
    return parsed;
  } catch (error) {
    throw new Error("Channel metadata must be valid JSON object.");
  }
}

/**
 * Builds the request payload from form data
 */
function buildPayload() {
  const payload = {
    source: elements.source.value,
    message: elements.message.value,
  };

  const requestId = elements.requestId.value.trim();
  const externalId = elements.externalId.value.trim();
  const customerId = elements.customerId.value.trim();
  const receivedAt = elements.receivedAt.value.trim();

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

/**
 * Handles form submission
 */
async function processRequest(event) {
  event.preventDefault();
  setStatus("Processing...");
  elements.processBtn.disabled = true;

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
    const statusMessage = buildProcessingStatus(data);
    const hasSheetsFailure = !data.idempotent_replay && data.sheets_saved === false;
    setStatus(statusMessage, hasSheetsFailure);
  } catch (error) {
    renderProcessingError(error.message || "Failed to process request.");
    setStatus(error.message || "Failed to process request.", true);
  } finally {
    elements.processBtn.disabled = false;
  }
}

/**
 * Clears the form
 */
function clearForm() {
  elements.source.value = "Email";
  elements.message.value = "";
  elements.requestId.value = "";
  elements.externalId.value = "";
  elements.customerId.value = "";
  elements.receivedAt.value = "";
  elements.channelMetadata.value = "";
  state.selectedSampleId = null;

  renderSampleButtons();
  renderSamplePreview(null);
  applySourcePlaceholder();
  resetResultPanel();
  setStatus("Form cleared.");
}

// ============================================
// Batch Processing
// ============================================

/**
 * Renders batch results in the table
 */
function renderBatchRows(records) {
  elements.batchBody.innerHTML = "";

  if (!Array.isArray(records) || records.length === 0) {
    elements.batchBody.innerHTML = `<tr><td colspan="8" class="empty-row">No batch records returned.</td></tr>`;
    return;
  }

  records.forEach((record) => {
    const row = document.createElement("tr");

    if (record.error) {
      row.innerHTML = `
        <td>${escapeHtml(record.sample_id ?? "-")}</td>
        <td>${escapeHtml(record.source ?? "-")}</td>
        <td colspan="6">${escapeHtml(record.error)}</td>
      `;
      elements.batchBody.appendChild(row);
      return;
    }

    const escalatedBadge = record.escalation_flag
      ? `<span class="badge yes">YES</span>`
      : `<span class="badge no">NO</span>`;

    const replayBadge = record.idempotent_replay
      ? `<span class="badge replay">Replay</span>`
      : `<span class="badge no">Fresh</span>`;

    const confidence = Number(record.confidence);
    const confidenceSafe = Number.isFinite(confidence)
      ? Math.max(0, Math.min(1, confidence))
      : 0;
    const level = record.confidence_level || confidenceLevel(confidenceSafe);
    const source = formatConfidenceSource(record.confidence_source);

    const confidenceCell = `
      <div class="batch-confidence">
        <strong>${escapeHtml(asPercent(confidenceSafe))}</strong>
        <span class="batch-confidence-meta">${escapeHtml(level)} | ${escapeHtml(source)}</span>
      </div>
    `;

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

    elements.batchBody.appendChild(row);
  });
}

/**
 * Runs batch processing
 */
async function runBatch() {
  elements.batchBtn.disabled = true;
  elements.batchBtn.querySelector("span").textContent = "Running...";
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
    elements.batchBtn.disabled = false;
    elements.batchBtn.querySelector("span").textContent =
      "Run Batch (All Samples)";
  }
}

// ============================================
// Initialization
// ============================================

/**
 * Bootstraps the application
 */
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

// ============================================
// Event Listeners
// ============================================

// Form events
document
  .getElementById("triage-form")
  .addEventListener("submit", processRequest);
document.getElementById("btn-clear").addEventListener("click", clearForm);

// Tab events
elements.tabIntake.addEventListener("click", () => setTab("intake"));
elements.tabBatch.addEventListener("click", () => setTab("batch"));

// Batch event
elements.batchBtn.addEventListener("click", runBatch);

// Source change event
elements.source.addEventListener("change", () => {
  applySourcePlaceholder();
  const selected = state.samples.find(
    (sample) => sample.id === state.selectedSampleId,
  );
  if (selected) {
    renderSamplePreview(selected);
  }
});

// Initialize application
bootstrap();
