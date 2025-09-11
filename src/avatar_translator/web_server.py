#!/usr/bin/env python3
"""
Web server for Avatar Translator Chrome Extension integration.
Now respects 'target_language' on every request and returns 'translated_text'.
"""
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional
import json
import base64
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import wave

from .core import AudioTranslator
from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

translator: Optional[AudioTranslator] = None
active_sessions = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_translator():
    global translator
    if translator is None:
        logger.info("Initializing Avatar Translator...")
        translator = AudioTranslator(whisper_model_size="tiny", log_level="INFO")
        logger.info("Avatar Translator initialized successfully")

@app.get("/health")
def health_check():
    return jsonify({"status": "healthy", "service": "Avatar Translator Web Server", "timestamp": datetime.now().isoformat()})

@app.post("/translate-audio")
def translate_audio():
    """
    Body:
    {
      "audio_data": "<base64 wav/webm/mp3>",
      "target_language": "es|fr|it|hi|de|pt",
      "format": "wav|webm|mp3"
    }
    """
    try:
        init_translator()
        data = request.get_json() or {}
        b64 = data.get("audio_data")
        target_language = (data.get("target_language") or "es").lower()
        audio_format = (data.get("format") or "webm").lower()
        if not b64:
            return jsonify({"success": False, "error": "No audio data provided"}), 400

        raw = base64.b64decode(b64)

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            in_path = td / f"in.{audio_format}"
            in_path.write_bytes(raw)

            # Try to convert to 16k mono WAV (best for ASR)
            wav_path = td / "in.wav"
            input_for_asr = in_path
            try:
                import subprocess
                r = subprocess.run(["ffmpeg", "-y", "-i", str(in_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    input_for_asr = wav_path
                else:
                    logger.warning(f"FFmpeg conversion failed: {r.stderr}")
            except Exception:
                logger.warning("FFmpeg not available; using original format")

            out_path = td / "out.mp3"
            results = translator.translate_audio(
                input_audio=input_for_asr,
                output_audio=out_path,
                intermediate_files=False,
                target_lang=target_language,
            )

            if not results["success"]:
                return jsonify({"success": False, "error": results.get("error", "Translation failed")}), 500

            audio_b64 = base64.b64encode(out_path.read_bytes()).decode("utf-8")
            return jsonify({
                "success": True,
                "english_text": results["english_text"],
                "translated_text": results["translated_text"],
                "spanish_text": results.get("spanish_text", ""),   # legacy
                "translated_audio": audio_b64,
                "mime_type": "audio/mp3",
                "timings": results["timings"],
                "target_language": target_language,
            })
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/translate-audio-chunk")
def translate_audio_chunk():
    """
    Stateless per-chunk translation for the Chrome extension.
    Body:
      {
        "audio_data": "<base64 webm/ogg/mp3>",
        "input_mime": "audio/webm",
        "target_language": "es|fr|it|hi|de|pt",
        "seq": 1,
        "duration_ms": 5000
      }
    """
    try:
        init_translator()
        data = request.get_json() or {}
        b64 = data.get("audio_data")
        if not b64:
            return jsonify({"success": False, "error": "Missing audio_data"}), 400

        target_language = (data.get("target_language") or "es").lower()
        seq = int(data.get("seq", 0))

        raw = base64.b64decode(b64)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            in_path = td / "in.bin"
            wav_path = td / "in.wav"
            out_path = td / "out.mp3"
            in_path.write_bytes(raw)

            try:
                import subprocess
                r = subprocess.run(["ffmpeg", "-y", "-i", str(in_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                                   capture_output=True, text=True)
                input_for_asr = wav_path if r.returncode == 0 else in_path
            except Exception:
                input_for_asr = in_path

            results = translator.translate_audio(
                input_audio=input_for_asr,
                output_audio=out_path,
                intermediate_files=False,
                target_lang=target_language,
            )
            if not results["success"]:
                return jsonify({"success": False, "error": results.get("error", "Translation failed")}), 500

            audio_b64 = base64.b64encode(out_path.read_bytes()).decode("utf-8")
            return jsonify({
                "success": True,
                "seq": seq,
                "english_text": results["english_text"],
                "translated_text": results["translated_text"],
                "spanish_text": results.get("spanish_text", ""),
                "translated_audio": audio_b64,
                "mime_type": "audio/mp3",
                "timings": results["timings"],
                "target_language": target_language,
            })
    except Exception as e:
        logger.error(f"/translate-audio-chunk error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/status")
def get_status():
    try:
        init_translator()
        return jsonify({"success": True, "status": translator.get_pipeline_status()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --------------- WebSocket realtime ---------------
@socketio.on("connect")
def handle_connect():
    session_id = request.sid
    logger.info(f"WebSocket client connected: {session_id}")
    active_sessions[session_id] = {
        "connected_at": datetime.now(),
        "audio_buffer": [],
        "translation_queue": [],
        "is_processing": False,
        "target_language": "es",
        "total_audio_duration": 0,
        "chunks_processed": 0,
    }
    socketio.emit("connected", {
        "session_id": session_id,
        "status": "connected",
        "message": "WebSocket connection established for real-time audio translation",
    }, room=session_id)

@socketio.on("disconnect")
def handle_disconnect():
    session_id = request.sid
    logger.info(f"WebSocket client disconnected: {session_id}")
    if session_id in active_sessions:
        session_data = active_sessions[session_id]
        logger.info(f"Session {session_id} processed {session_data['chunks_processed']} chunks, "
                    f"total duration: {session_data['total_audio_duration']:.2f}s")
        del active_sessions[session_id]

@socketio.on("start_streaming")
def handle_start_streaming(data):
    session_id = request.sid
    if session_id not in active_sessions:
        socketio.emit("error", {"message": "Session not found"}, room=session_id)
        return
    session_data = active_sessions[session_id]
    session_data["target_language"] = (data.get("target_language") or "es").lower()
    session_data["is_processing"] = True
    logger.info(f"Started streaming session {session_id} lang={session_data['target_language']}")
    socketio.emit("streaming_started", {
        "session_id": session_id,
        "target_language": session_data["target_language"],
        "message": "Real-time audio streaming started",
    }, room=session_id)

@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    session_id = request.sid
    if session_id not in active_sessions:
        socketio.emit("error", {"message": "Session not found"}, room=session_id)
        return
    try:
        audio_data = data.get("audio_data")
        chunk_duration = float(data.get("duration", 5.0))
        if not audio_data:
            socketio.emit("error", {"message": "No audio data received"}, room=session_id)
            return

        sd = active_sessions[session_id]
        sd["audio_buffer"].append({"data": audio_data, "duration": chunk_duration, "timestamp": datetime.now()})
        sd["total_audio_duration"] += chunk_duration
        sd["chunks_processed"] += 1

        process_audio_chunk_async(session_id, audio_data, chunk_duration, sd["target_language"])
        socketio.emit("chunk_received", {
            "chunk_id": sd["chunks_processed"],
            "duration": chunk_duration,
            "total_duration": sd["total_audio_duration"],
        }, room=session_id)
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        socketio.emit("error", {"message": f"Error processing audio: {str(e)}"}, room=session_id)

@socketio.on("stop_streaming")
def handle_stop_streaming():
    session_id = request.sid
    if session_id not in active_sessions:
        socketio.emit("error", {"message": "Session not found"}, room=session_id)
        return
    sd = active_sessions[session_id]
    sd["is_processing"] = False
    logger.info(f"Stopped streaming session {session_id}")
    socketio.emit("streaming_stopped", {
        "session_id": session_id,
        "total_chunks": sd["chunks_processed"],
        "total_duration": sd["total_audio_duration"],
    }, room=session_id)

def process_audio_chunk_async(session_id, audio_data, chunk_duration, target_language):
    try:
        init_translator()
        raw = base64.b64decode(audio_data)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            in_path = td / "chunk.webm"
            in_path.write_bytes(raw)
            wav_path = td / "chunk.wav"
            try:
                import subprocess
                r = subprocess.run(["ffmpeg", "-y", "-i", str(in_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                                   capture_output=True, text=True)
                input_for_asr = wav_path if r.returncode == 0 else in_path
            except Exception:
                input_for_asr = in_path

            out_path = td / "chunk_out.mp3"
            results = translator.translate_audio(
                input_audio=input_for_asr,
                output_audio=out_path,
                intermediate_files=False,
                target_lang=target_language,
            )
            if results["success"]:
                audio_b64 = base64.b64encode(out_path.read_bytes()).decode("utf-8")
                socketio.emit("translation_result", {
                    "session_id": session_id,
                    "chunk_id": active_sessions.get(session_id, {}).get("chunks_processed", 0),
                    "success": True,
                    "english_text": results["english_text"],
                    "translated_text": results["translated_text"],
                    "spanish_text": results.get("spanish_text", ""),
                    "translated_audio": audio_b64,
                    "mime_type": "audio/mp3",
                    "timings": results["timings"],
                    "target_language": target_language,
                    "chunk_duration": chunk_duration,
                }, room=session_id)
            else:
                socketio.emit("translation_result", {
                    "session_id": session_id,
                    "chunk_id": active_sessions.get(session_id, {}).get("chunks_processed", 0),
                    "success": False,
                    "error": results.get("error", "Translation failed"),
                }, room=session_id)
    except Exception as e:
        logger.error(f"Error processing audio chunk {session_id}: {e}")
        socketio.emit("translation_result", {
            "session_id": session_id,
            "chunk_id": active_sessions.get(session_id, {}).get("chunks_processed", 0),
            "success": False,
            "error": str(e),
        }, room=session_id)

def run_server(host="localhost", port=8080, debug=False):
    logger.info(f"Starting Avatar Translator Web Server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug)

if __name__ == "__main__":
    run_server(debug=True)
