// offscreen.js — Capture tab audio as PCM and send WAV chunks to the SW.
// Also plays back the returned TTS (base64 MP3) sent from the SW.

let stream = null;
let ctx = null;
let source = null;
let processor = null;
let zeroGain = null;

let seq = 0;
let sampleRate = 48000;          // will be overridden by AudioContext
let chunkMs = 5000;
let maxMs = 300000;              // safety stop
let stopTimer = null;

// Simple, robust ArrayBuffer -> base64 (chunked)
function abToBase64(ab) {
  const bytes = new Uint8Array(ab);
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

// Encode Float32 samples -> 16-bit PCM WAV (mono)
function encodeWAV(samples, sr) {
  const dataLen = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataLen);
  const view = new DataView(buffer);

  // RIFF header
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLen, true);
  writeString(view, 8, "WAVE");

  // fmt  chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);     // PCM fmt chunk size
  view.setUint16(20, 1, true);      // audio format: 1 = PCM
  view.setUint16(22, 1, true);      // channels: 1 (mono)
  view.setUint32(24, sr, true);     // sample rate
  view.setUint32(28, sr * 2, true); // byte rate = sr * blockAlign
  view.setUint16(32, 2, true);      // blockAlign = channels * 2 bytes
  view.setUint16(34, 16, true);     // bits per sample

  // data chunk
  writeString(view, 36, "data");
  view.setUint32(40, dataLen, true);

  // PCM samples
  floatTo16BitPCM(view, 44, samples);
  return buffer;

  function writeString(dataview, offset, str) {
    for (let i = 0; i < str.length; i++) dataview.setUint8(offset + i, str.charCodeAt(i));
  }
  function floatTo16BitPCM(dataview, offset, input) {
    let pos = offset;
    for (let i = 0; i < input.length; i++, pos += 2) {
      let s = Math.max(-1, Math.min(1, input[i]));
      dataview.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
  }
}

// A very small ring buffer to accumulate audio between flushes
const ring = {
  chunks: [],
  length: 0,
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

chrome.runtime.onMessage.addListener(async (msg) => {
  if (msg.type === "OFFSCREEN_START") {
    const { streamId, timeslice = 5000, maxMs: mm = 300000 } = msg.payload || {};
    chunkMs = timeslice;
    maxMs = mm;

    try {
      // Bind to tab stream
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
        video: false
      });

      ctx = new (window.AudioContext || window.webkitAudioContext)();
      sampleRate = ctx.sampleRate;

      source = ctx.createMediaStreamSource(stream);

      // ScriptProcessor is deprecated but works across Chrome/Offscreen.
      const BUFFER_SIZE = 4096;
      processor = ctx.createScriptProcessor(BUFFER_SIZE, 1, 1);
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        // Copy to avoid retaining the large backing store
        ring.push(new Float32Array(input));
      };

      // Keep node chain "alive" without audible output
      zeroGain = ctx.createGain();
      zeroGain.gain.value = 0;

      source.connect(processor);
      processor.connect(zeroGain);
      zeroGain.connect(ctx.destination);

      await ctx.resume();

      // Periodically flush to WAV
      const flush = async () => {
        const samplesPerChunk = Math.floor(sampleRate * (chunkMs / 1000));
        const samples = ring.take(samplesPerChunk);
        if (samples.length > 0) {
          const wavBuf = encodeWAV(samples, sampleRate);
          const b64 = abToBase64(wavBuf);
          chrome.runtime.sendMessage({
            type: "OFFSCREEN_CHUNK",
            payload: { b64, mimeType: "audio/wav", durationMs: chunkMs, seq: ++seq }
          });
        }
      };

      // First flush happens after chunkMs; then at a fixed interval
      flush();
      stopTimer = setInterval(flush, chunkMs);

      // Safety timeout to auto-stop (optional)
      setTimeout(() => chrome.runtime.sendMessage({ type: "OFFSCREEN_ENDED" }), maxMs);
    } catch (err) {
      console.error("OFFSCREEN_START failed:", err?.name, err?.message, err);
      chrome.runtime.sendMessage({ type: "OFFSCREEN_ENDED" });
    }
  }

  if (msg.type === "OFFSCREEN_STOP") {
    try { clearInterval(stopTimer); } catch {}
    try { processor?.disconnect(); } catch {}
    try { zeroGain?.disconnect(); } catch {}
    try { source?.disconnect(); } catch {}
    try { stream?.getTracks().forEach(t => t.stop()); } catch {}
    try { ctx?.close(); } catch {}
    stream = ctx = source = processor = zeroGain = null;
    ring.clear();
    chrome.runtime.sendMessage({ type: "OFFSCREEN_ENDED" });
  }

  // Play back translated audio returned by SW
  if (msg.type === "OFFSCREEN_PLAY_TTS") {
    try {
      const { b64, mimeType = "audio/mp3" } = msg.payload || {};
      const a = new Audio(`data:${mimeType};base64,${b64}`);
      a.play().catch(() => {});
    } catch (e) {
      console.warn("Play TTS failed:", e.message);
    }
  }
});
