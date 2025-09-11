// offscreen.js — capture tab audio -> WAV chunks, play TTS
// This script runs in the offscreen document (offscreen.html).

let stream = null;
let ctx = null;
let source = null;
let processor = null;
let zeroGain = null;

let seq = 0;
let sampleRate = 48000;
let chunkMs = 5000;
let maxMs = 300000;
let flushTimer = null;

let ttsAudio = null;   // single player we can stop immediately

// -------------- utils --------------
function abToBase64(ab) {
  const bytes = new Uint8Array(ab);
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

function encodeWAV(samples, sr) {
  const dataLen = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataLen);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLen, true);
  writeString(view, 8, "WAVE");

  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);  // PCM
  view.setUint16(22, 1, true);  // mono
  view.setUint32(24, sr, true);
  view.setUint32(28, sr * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);

  writeString(view, 36, "data");
  view.setUint32(40, dataLen, true);
  floatTo16PCM(view, 44, samples);
  return buffer;

  function writeString(dv, off, s) { for (let i = 0; i < s.length; i++) dv.setUint8(off + i, s.charCodeAt(i)); }
  function floatTo16PCM(dv, off, input) {
    let pos = off;
    for (let i = 0; i < input.length; i++, pos += 2) {
      let v = Math.max(-1, Math.min(1, input[i]));
      dv.setInt16(pos, v < 0 ? v * 0x8000 : v * 0x7FFF, true);
    }
  }
}

// Simple ring to accumulate input
const ring = {
  chunks: [], length: 0,
  push(f32) { this.chunks.push(f32); this.length += f32.length; },
  take(n) {
    n = Math.min(n, this.length);
    const out = new Float32Array(n);
    let off = 0;
    while (off < n && this.chunks.length) {
      const first = this.chunks[0];
      const take = Math.min(first.length, n - off);
      out.set(first.subarray(0, take), off);
      if (take < first.length) this.chunks[0] = first.subarray(take);
      else this.chunks.shift();
      off += take;
    }
    this.length -= n;
    return out;
  },
  clear() { this.chunks = []; this.length = 0; }
};

// Announce readiness so the service worker can sync up.
try { chrome.runtime.sendMessage({ type: "OFFSCREEN_READY" }); } catch {}

// Accept a ping to re-announce (used after service worker restarts)
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "PING_OFFSCREEN") {
    try { chrome.runtime.sendMessage({ type: "OFFSCREEN_READY" }); } catch {}
  }
});

// ---------- main control ----------
chrome.runtime.onMessage.addListener(async (msg) => {
  if (!msg || !msg.type) return;

  if (msg.type === "OFFSCREEN_START") {
    const { streamId, timeslice = 5000, maxMs: mm = 300000 } = msg.payload || {};
    chunkMs = timeslice;
    maxMs = mm;

    try {
      // Bind to the tab audio stream
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
        video: false,
      });

      ctx = new (window.AudioContext || window.webkitAudioContext)();
      sampleRate = ctx.sampleRate;

      const sourceNode = ctx.createMediaStreamSource(stream);
      source = sourceNode;

      // ScriptProcessor is deprecated but works reliably in offscreen contexts.
      const BUFFER_SIZE = 4096;
      processor = ctx.createScriptProcessor(BUFFER_SIZE, 1, 1);
      processor.onaudioprocess = (e) => {
        // Copy to avoid retaining the large backing store
        ring.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      };

      // Keep the graph alive without producing audible output
      zeroGain = ctx.createGain();
      zeroGain.gain.value = 0;
      source.connect(processor);
      processor.connect(zeroGain);
      zeroGain.connect(ctx.destination);
      await ctx.resume();

      // Periodically flush ring -> WAV
      const flush = async () => {
        const samplesPerChunk = Math.floor(sampleRate * (chunkMs / 1000));
        const samples = ring.take(samplesPerChunk);
        if (samples.length > 0) {
          const wavBuf = encodeWAV(samples, sampleRate);
          const b64 = abToBase64(wavBuf);
          try {
            await chrome.runtime.sendMessage({
              type: "OFFSCREEN_CHUNK",
              payload: { b64, mimeType: "audio/wav", durationMs: chunkMs, seq: ++seq },
            });
          } catch { /* bg might be sleeping; ignore */ }
        }
      };
      flush(); // first one after ~chunkMs
      flushTimer = setInterval(flush, chunkMs);

      // Safety timeout to auto-stop capture if left running
      setTimeout(() => {
        try { chrome.runtime.sendMessage({ type: "OFFSCREEN_ENDED" }); } catch {}
      }, maxMs);

      // Tell background we've started so it can mark state
      try { chrome.runtime.sendMessage({ type: "OFFSCREEN_STARTED" }); } catch {}
    } catch (err) {
      console.error("OFFSCREEN_START failed:", err?.name, err?.message, err);
      try { chrome.runtime.sendMessage({ type: "OFFSCREEN_ENDED" }); } catch {}
    }
    return;
  }

  if (msg.type === "OFFSCREEN_STOP") {
    // Stop timers and audio graph
    try { clearInterval(flushTimer); } catch {}
    try { processor?.disconnect(); } catch {}
    try { zeroGain?.disconnect(); } catch {}
    try { source?.disconnect(); } catch {}
    try { stream?.getTracks().forEach(t => t.stop()); } catch {}
    try { ctx?.close(); } catch {}
    stream = ctx = source = processor = zeroGain = null;
    ring.clear();

    // Stop any TTS currently playing
    try {
      if (ttsAudio) {
        ttsAudio.pause();
        ttsAudio.src = "";
      }
    } catch {}

    try { chrome.runtime.sendMessage({ type: "OFFSCREEN_ENDED" }); } catch {}
    return;
  }

  if (msg.type === "OFFSCREEN_PLAY_TTS") {
    try {
      const { b64, mimeType = "audio/mp3" } = msg.payload || {};
      // Stop any previous clip immediately to avoid overlap tails.
      if (!ttsAudio) ttsAudio = new Audio();
      try {
        ttsAudio.pause();
        ttsAudio.currentTime = 0;
      } catch {}
      ttsAudio.src = `data:${mimeType};base64,${b64}`;
      // Play without blocking; ignore user gesture restrictions in offscreen.
      ttsAudio.play().catch(() => {});
    } catch (e) {
      console.warn("Play TTS failed:", e.message);
    }
    return;
  }
});
