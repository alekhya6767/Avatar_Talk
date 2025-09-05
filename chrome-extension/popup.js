// popup.js — single control: Start/Stop Continuous Capture

let targetLanguageSelect, continuousCaptureButton, statusDiv, captureStatusDiv, transcriptDiv;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  targetLanguageSelect = document.getElementById("target-language");
  continuousCaptureButton = document.getElementById("continuous-capture");
  statusDiv = document.getElementById("status-message");
  captureStatusDiv = document.getElementById("capture-status");
  transcriptDiv = document.getElementById("transcript");

  // load saved language
  try {
    const resp = await chrome.runtime.sendMessage({ action: "getSettings" });
    if (resp?.success) targetLanguageSelect.value = resp.settings.targetLanguage || "es";
  } catch {
    targetLanguageSelect.value = "es";
  }

  targetLanguageSelect.addEventListener("change", async () => {
    await chrome.storage.sync.set({ targetLanguage: targetLanguageSelect.value });
    showStatus("Target language updated", "success");
  });

  continuousCaptureButton.addEventListener("click", onToggleCapture);

  // poll status for UI
  setInterval(updateStatusFromBG, 1200);

  // receive rolling transcript/translation
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "POPUP_UPDATE_TEXT" && transcriptDiv) {
      const { text, translated } = msg.payload || {};
      transcriptDiv.textContent = translated || text || "";
    }
  });

  updateCaptureButton(false);
  showStatus("");
}

async function onToggleCapture() {
  try {
    const st = await chrome.runtime.sendMessage({ action: "getCaptureStatus" });
    const lang = targetLanguageSelect.value || "es";
    if (st?.isRecording) {
      showStatus("Stopping…", "info");
      const r = await chrome.runtime.sendMessage({ action: "stopAudioCapture" });
      if (!r?.success) throw new Error(r?.error || "Stop failed");
    } else {
      showStatus("Starting…", "info");
      const r = await chrome.runtime.sendMessage({ action: "startAudioCapture", targetLanguage: lang });
      if (!r?.success) throw new Error(r?.error || "Start failed");
    }
  } catch (e) {
    showStatus("Error: " + e.message, "error");
  }
}

async function updateStatusFromBG() {
  try {
    const s = await chrome.runtime.sendMessage({ action: "getCaptureStatus" });
    if (!s?.success) return;
    updateCaptureStatus(s);
    updateCaptureButton(s.isRecording);
  } catch {}
}

function updateCaptureButton(isOn) {
  if (!continuousCaptureButton) return;
  continuousCaptureButton.disabled = false;
  continuousCaptureButton.textContent = isOn ? "Stop Continuous Capture" : "Start Continuous Capture";
  continuousCaptureButton.className = isOn ? "btn btn-danger" : "btn btn-primary";
}

function updateCaptureStatus(s) {
  if (!captureStatusDiv) return;
  captureStatusDiv.classList.toggle("active", !!s.isRecording);
  captureStatusDiv.classList.toggle("inactive", !s.isRecording);
  captureStatusDiv.innerHTML = s.isRecording
    ? `<span class="status-indicator recording"></span><span>Recording…</span>`
    : `<span class="status-indicator stopped"></span><span>Not recording</span>`;
}

function showStatus(msg, type = "info") {
  if (!statusDiv) return;
  statusDiv.textContent = msg || "";
  statusDiv.className = "status " + (msg ? type : "");
}
