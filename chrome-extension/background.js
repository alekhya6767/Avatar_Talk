// background.js — service worker

const CONFIG = {
  SERVER_URL: "http://localhost:8080",
  CHUNK_MS: 5000,
  MAX_CAPTURE_MS: 5 * 60 * 1000,
  DEFAULT_TARGET_LANG: "es"
};

let isRecording = false;
let startedAt = 0;
let targetLang = CONFIG.DEFAULT_TARGET_LANG;
let currentTabId = null;

chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === "install") {
    await chrome.storage.sync.set({ targetLanguage: CONFIG.DEFAULT_TARGET_LANG });
  }
  console.log("Installed:", details.reason);
});

chrome.runtime.onStartup.addListener(() => console.log("Service worker: startup"));

async function ensureOffscreen() {
  if (await chrome.offscreen.hasDocument()) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA", "AUDIO_PLAYBACK"],
    justification: "Bind tab stream ID, record PCM to WAV, send chunks, and play translated audio."
  });
}

async function closeOffscreenIfAny() {
  if (await chrome.offscreen.hasDocument()) await chrome.offscreen.closeDocument();
}

async function getTargetLanguage() {
  const { targetLanguage } = await chrome.storage.sync.get(["targetLanguage"]);
  return targetLanguage || CONFIG.DEFAULT_TARGET_LANG;
}

async function startAudioCapture(tabId, lang) {
  if (isRecording) throw new Error("Already recording");
  await ensureOffscreen();

  targetLang = lang || (await getTargetLanguage());
  currentTabId = tabId;

  try { await chrome.tabs.update(tabId, { muted: false }); } catch {}

  const streamId = await new Promise((resolve, reject) => {
    chrome.tabCapture.getMediaStreamId({ targetTabId: tabId }, (id) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error("getMediaStreamId: " + err.message));
      if (!id) return reject(new Error("getMediaStreamId returned empty id"));
      resolve(id);
    });
  });
  console.log("[bg] got streamId:", (streamId || "").slice(0, 6) + "…");

  await chrome.runtime.sendMessage({
    type: "OFFSCREEN_START",
    payload: { streamId, timeslice: CONFIG.CHUNK_MS, maxMs: CONFIG.MAX_CAPTURE_MS }
  });

  isRecording = true;
  startedAt = Date.now();
}

async function stopAudioCapture() {
  if (!isRecording) return;
  await chrome.runtime.sendMessage({ type: "OFFSCREEN_STOP" });
  isRecording = false;
  currentTabId = null;
  await closeOffscreenIfAny();
}

// Popup RPC
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
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
          startedAt
        });
        return;
      }
      if (msg.action === "startAudioCapture") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab");
        await chrome.tabs.update(tab.id, { muted: false });
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
      console.error(err);
      sendResponse({ success: false, error: err.message });
    }
  })();
  return true; // async
});

// Receive WAV chunks from offscreen and send to server
chrome.runtime.onMessage.addListener((msg) => {
  (async () => {
    if (msg.type === "OFFSCREEN_CHUNK") {
      const { b64, mimeType, durationMs, seq } = msg.payload || {};
      try {
        console.log(`[chunk] seq=${seq} size=${b64?.length || 0} mime=${mimeType}`);
        const res = await fetch(`${CONFIG.SERVER_URL}/translate-audio`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio_data: b64,                // base64 WAV
            target_language: targetLang,
            format: "wav"                   // tell the server this is WAV
          })
        });

        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          console.log("Chunk POST failed:", res.status, txt);
          throw new Error(`Server ${res.status}`);
        }

        const data = await res.json();
        const b64Audio = data.audio_base64 || data.translated_audio;
        if (b64Audio) {
          await chrome.runtime.sendMessage({
            type: "OFFSCREEN_PLAY_TTS",
            payload: { b64: b64Audio, mimeType: data.mime_type || "audio/mp3" }
          });
        }

        const en = data.english_text || data.text;
        const es = data.spanish_text || data.translated_text;
        if (en || es) {
          chrome.runtime.sendMessage({
            type: "POPUP_UPDATE_TEXT",
            payload: { text: en, translated: es }
          }).catch(() => {});
        }
      } catch (e) {
        console.log("Chunk send error:", e.message);
      }
    }

    if (msg.type === "OFFSCREEN_ENDED") {
      isRecording = false;
      await closeOffscreenIfAny();
    }
  })();
});
