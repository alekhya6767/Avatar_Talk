// background.js — Avatar Translator (stable)

const CONFIG = {
  SERVER_URL: "http://localhost:8080",
  CHUNK_MS: 5000,
  MAX_CAPTURE_MS: 5 * 60 * 1000,
  DEFAULT_TARGET_LANG: "es",
  // Mute the source tab while we play translated audio to avoid overlap.
  MUTE_SOURCE_WHILE_PLAYING: true,
  // How long we wait for offscreen ack (ms)
  OFFSCREEN_ACK_TIMEOUT: 3000,
};

let isRecording = false;
let startedAt = 0;
let targetLang = CONFIG.DEFAULT_TARGET_LANG;
let currentTabId = null;
let offscreenReady = false;

// ---------- tiny helpers ----------
const log = (...a) => { try { console.log(...a); } catch {} };
const warn = (...a) => { try { console.warn(...a); } catch {} };
const fail = (e) => {
  const m = (e && (e.message || String(e))) || "Unknown error";
  console.error("[bg] fail:", m);
  return { ok: false, error: m };
};

async function getTargetLanguage() {
  const { targetLanguage } = await chrome.storage.sync.get(["targetLanguage"]);
  return targetLanguage || CONFIG.DEFAULT_TARGET_LANG;
}

async function waitForOffscreenReady() {
  if (offscreenReady && await chrome.offscreen.hasDocument()) return true;

  return new Promise(async (resolve) => {
    let resolved = false;
    const timer = setTimeout(() => {
      if (!resolved) { resolved = true; resolve(false); }
    }, CONFIG.OFFSCREEN_ACK_TIMEOUT);

    const listener = (msg) => {
      if (msg && msg.type === "OFFSCREEN_READY") {
        offscreenReady = true;
        try { chrome.runtime.onMessage.removeListener(listener); } catch {}
        clearTimeout(timer);
        if (!resolved) { resolved = true; resolve(true); }
      }
    };
    chrome.runtime.onMessage.addListener(listener);

    if (!(await chrome.offscreen.hasDocument())) {
      await chrome.offscreen.createDocument({
        url: "offscreen.html",
        reasons: ["USER_MEDIA", "AUDIO_PLAYBACK"],
        justification: "Record tab audio, send WAV chunks, play translated TTS.",
      });
    } else {
      // poke the offscreen page to re-announce readiness
      try { await chrome.runtime.sendMessage({ type: "PING_OFFSCREEN" }); } catch {}
    }
  });
}

async function ensureOffscreen() {
  const ok = await waitForOffscreenReady();
  if (!ok) throw new Error("Offscreen page did not become ready");
}

async function closeOffscreenIfAny() {
  try {
    if (await chrome.offscreen.hasDocument()) {
      offscreenReady = false;
      await chrome.offscreen.closeDocument();
    }
  } catch (e) { /* ignore */ }
}

// ---------- capture control ----------
async function startAudioCapture(tabId, lang) {
  if (isRecording) throw new Error("Already recording");

  await ensureOffscreen();
  targetLang = lang || (await getTargetLanguage());
  currentTabId = tabId;

  // Avoid overlap, optionally mute the source tab while we speak the translation
  try { await chrome.tabs.update(tabId, { muted: CONFIG.MUTE_SOURCE_WHILE_PLAYING }); } catch {}

  const streamId = await new Promise((resolve, reject) => {
    chrome.tabCapture.getMediaStreamId({ targetTabId: tabId }, (id) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error("getMediaStreamId: " + err.message));
      if (!id) return reject(new Error("getMediaStreamId returned empty id"));
      resolve(id);
    });
  });
  log("[bg] got streamId:", (streamId || "").slice(0, 6) + "…");

  // Wait for explicit OFFSCREEN_STARTED acknowledgment so we don't race.
  const started = new Promise((resolve) => {
    const listener = (msg) => {
      if (msg && msg.type === "OFFSCREEN_STARTED") {
        try { chrome.runtime.onMessage.removeListener(listener); } catch {}
        resolve(true);
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    // safety timeout also resolves; the offscreen might still be fine
    setTimeout(() => resolve(true), CONFIG.OFFSCREEN_ACK_TIMEOUT);
  });

  try {
    await chrome.runtime.sendMessage({
      type: "OFFSCREEN_START",
      payload: { streamId, timeslice: CONFIG.CHUNK_MS, maxMs: CONFIG.MAX_CAPTURE_MS },
    });
  } catch {
    // If offscreen was closed between ensure and send, surface a clean error
    throw new Error("Failed to start offscreen recorder");
  }

  await started;

  isRecording = true;
  startedAt = Date.now();
}

async function stopAudioCapture() {
  if (!isRecording) return;
  try { await chrome.runtime.sendMessage({ type: "OFFSCREEN_STOP" }); } catch {}
  isRecording = false;
  const tid = currentTabId; currentTabId = null;

  // Unmute the tab back to normal if we muted it.
  if (tid != null && CONFIG.MUTE_SOURCE_WHILE_PLAYING) {
    try { await chrome.tabs.update(tid, { muted: false }); } catch {}
  }
  await closeOffscreenIfAny();
}

// ---------- popup RPC ----------
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === "install") {
    await chrome.storage.sync.set({ targetLanguage: CONFIG.DEFAULT_TARGET_LANG });
  }
  log("Installed:", details.reason);
});

chrome.runtime.onStartup.addListener(() => log("Service worker: startup"));

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (!msg || !msg.action) return;

      if (msg.action === "getSettings") {
        sendResponse({ success: true, settings: { targetLanguage: await getTargetLanguage() } });
        return;
      }

      if (msg.action === "getCaptureStatus") {
        sendResponse({
          success: true,
          isRecording,
          isProcessing: false,
          queueLength: 0,
          currentStream: isRecording ? "active" : "inactive",
          startedAt,
        });
        return;
      }

      if (msg.action === "startAudioCapture") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab");
        await startAudioCapture(tab.id, msg.targetLanguage);
        sendResponse({ success: true, message: "Continuous audio capture started" });
        return;
      }

      if (msg.action === "stopAudioCapture") {
        await stopAudioCapture();
        sendResponse({ success: true, message: "Audio capture stopped" });
        return;
      }
    } catch (err) {
      sendResponse(fail(err));
    }
  })();
  return true; // async
});

// ---------- data path: receive chunks from offscreen, call server, play TTS ----------
chrome.runtime.onMessage.addListener((msg) => {
  (async () => {
    if (!msg || !msg.type) return;

    // Offscreen lifecycle pings
    if (msg.type === "OFFSCREEN_READY") { offscreenReady = true; return; }
    if (msg.type === "OFFSCREEN_ENDED") {
      // Offscreen stopped itself (timeout or user stop). Keep state coherent.
      isRecording = false;
      const tid = currentTabId; currentTabId = null;
      if (tid != null && CONFIG.MUTE_SOURCE_WHILE_PLAYING) {
        try { await chrome.tabs.update(tid, { muted: false }); } catch {}
      }
      await closeOffscreenIfAny();
      return;
    }

    // Audio chunk from offscreen
    if (msg.type === "OFFSCREEN_CHUNK") {
      const { b64, mimeType, seq } = msg.payload || {};
      try {
        log(`[chunk] seq=${seq} size=${b64?.length || 0} mime=${mimeType}`);
        const res = await fetch(`${CONFIG.SERVER_URL}/translate-audio`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio_data: b64,          // base64 WAV
            target_language: targetLang,
            format: "wav"
          }),
        });

        if (!res.ok) {
          // Avoid noisy logs for common "no speech" cases
          const txt = await res.text().catch(() => "");
          if (!/No speech detected/i.test(txt)) {
            warn("Chunk POST failed:", res.status, txt);
          }
          return;
        }

        const data = await res.json();
        const b64Audio = data.audio_base64 || data.translated_audio;
        if (b64Audio) {
          try {
            await chrome.runtime.sendMessage({
              type: "OFFSCREEN_PLAY_TTS",
              payload: { b64: b64Audio, mimeType: data.mime_type || "audio/mp3" },
            });
          } catch {
            // Offscreen might have been closed—ignore
          }
        }

        const en = data.english_text || data.text;
        const tr = data.translated_text || data.spanish_text;
        if (en || tr) {
          try {
            await chrome.runtime.sendMessage({
              type: "POPUP_UPDATE_TEXT",
              payload: { text: en, translated: tr },
            });
          } catch {}
        }
      } catch (e) {
        warn("Chunk send error:", e.message);
      }
      return;
    }

    // Ignore anything else to prevent "Unknown message" noise
  })();
});
