#!/usr/bin/env python3
"""
Web server for Avatar Translator Chrome Extension integration.
"""
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional
import json
import base64
import asyncio
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import wave

from .core import AudioTranslator
from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome extension
socketio = SocketIO(app, cors_allowed_origins="*") # Initialize SocketIO

# Global translator instance
translator: Optional[AudioTranslator] = None

# Active sessions for WebSocket communication
active_sessions = {}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_translator():
    """Initialize the AudioTranslator instance."""
    global translator
    if translator is None:
        logger.info("Initializing Avatar Translator...")
        translator = AudioTranslator(
            whisper_model_size="tiny",  # Fast model for real-time processing
            log_level="INFO"
        )
        logger.info("Avatar Translator initialized successfully")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Avatar Translator Web Server",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/translate-audio', methods=['POST'])
def translate_audio():
    """
    Translate audio from Chrome extension.
    
    Expected JSON payload:
    {
        "audio_data": "base64_encoded_audio",
        "target_language": "es",
        "format": "webm" | "wav" | "mp3"
    }
    """
    try:
        # Initialize translator if needed
        init_translator()
        
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        audio_data = data.get('audio_data')
        target_language = data.get('target_language', 'es')
        audio_format = data.get('format', 'webm')
        
        if not audio_data:
            return jsonify({"error": "No audio data provided"}), 400
        
        logger.info(f"Received audio translation request: target_lang={target_language}, format={audio_format}")
        
        # Decode base64 audio data
        try:
            audio_bytes = base64.b64decode(audio_data)
        except Exception as e:
            return jsonify({"error": f"Invalid base64 audio data: {e}"}), 400
        
        # Create temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Save input audio
            input_file = temp_dir_path / f"input.{audio_format}"
            with open(input_file, 'wb') as f:
                f.write(audio_bytes)
            
            # Convert to WAV if needed (Whisper works best with WAV)
            if audio_format != 'wav':
                wav_input = temp_dir_path / "input.wav"
                try:
                    # Try to convert using ffmpeg (if available)
                    import subprocess
                    result = subprocess.run([
                        'ffmpeg', '-i', str(input_file), 
                        '-ar', '16000',  # 16kHz sample rate
                        '-ac', '1',      # Mono
                        str(wav_input)
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        input_file = wav_input
                    else:
                        logger.warning(f"FFmpeg conversion failed: {result.stderr}")
                        # Continue with original file
                except (ImportError, FileNotFoundError):
                    logger.warning("FFmpeg not available, using original audio format")
            
            # Output file
            output_file = temp_dir_path / "output.mp3"
            
            # Perform translation
            logger.info("Starting audio translation...")
            results = translator.translate_audio(
                input_audio=input_file,
                output_audio=output_file,
                intermediate_files=False
            )
            
            if results["success"]:
                # Read translated audio
                with open(output_file, 'rb') as f:
                    translated_audio = base64.b64encode(f.read()).decode('utf-8')
                
                response_data = {
                    "success": True,
                    "english_text": results["english_text"],
                    "spanish_text": results["spanish_text"],
                    "translated_audio": translated_audio,
                    "timings": results["timings"],
                    "target_language": target_language
                }
                
                logger.info("Audio translation completed successfully")
                return jsonify(response_data)
            else:
                return jsonify({
                    "success": False,
                    "error": results.get("error", "Translation failed")
                }), 500
                
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/translate-audio-chunk', methods=['POST'])
def translate_audio_chunk():
    """
    Stateless per-chunk translation for the Chrome extension.
    Body:
      {
        "audio_data": "<base64 webm/ogg/mp3>",
        "input_mime": "audio/webm",
        "target_language": "es",
        "seq": 1,
        "duration_ms": 5000
      }
    Returns:
      {
        "success": true,
        "seq": 1,
        "english_text": "...",
        "spanish_text": "...",
        "translated_audio": "<base64 mp3>",
        "mime_type": "audio/mp3",
        "timings": {...}
      }
    """
    try:
        init_translator()

        data = request.get_json() or {}
        b64 = data.get("audio_data")
        if not b64:
            return jsonify({"success": False, "error": "Missing audio_data"}), 400

        input_mime = data.get("input_mime", "audio/webm")
        seq = int(data.get("seq", 0))
        target_language = data.get("target_language", "es")

        # Decode and transcode to 16k mono WAV (same approach as /translate-audio)
        import base64, subprocess, tempfile
        from pathlib import Path

        raw = base64.b64decode(b64)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            in_path = td / "in.bin"
            wav_path = td / "in.wav"
            out_path = td / "out.mp3"
            in_path.write_bytes(raw)

            # Try ffmpeg transcode; if ffmpeg missing we’ll fall back to original
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", str(in_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                    capture_output=True, text=True
                )
                input_for_asr = wav_path if result.returncode == 0 else in_path
            except Exception:
                input_for_asr = in_path  # best effort

            # Run your existing pipeline (ASR -> MT -> TTS)
            results = translator.translate_audio(
                input_audio=input_for_asr,
                output_audio=out_path,
                intermediate_files=False
            )

            if not results["success"]:
                return jsonify({"success": False, "error": results.get("error", "Translation failed")}), 500

            audio_b64 = base64.b64encode(out_path.read_bytes()).decode("utf-8")
            return jsonify({
                "success": True,
                "seq": seq,
                "english_text": results["english_text"],
                "spanish_text": results["spanish_text"],
                "translated_audio": audio_b64,   # <-- key the extension will read
                "mime_type": "audio/mp3",
                "timings": results["timings"],
                "target_language": target_language
            })

    except Exception as e:
        logger.error(f"/translate-audio-chunk error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/status', methods=['GET'])
def get_status():
    """Get translator status."""
    try:
        init_translator()
        status = translator.get_pipeline_status()
        return jsonify({
            "success": True,
            "status": status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    

@app.route('/test', methods=['POST'])
def test_pipeline():
    """Test the translation pipeline."""
    try:
        init_translator()
        
        data = request.get_json() or {}
        test_text = data.get('text', 'Hello, this is a test.')
        
        success = translator.test_pipeline(test_text)
        
        return jsonify({
            "success": success,
            "test_text": test_text
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    session_id = request.sid
    logger.info(f"WebSocket client connected: {session_id}")
    
    # Initialize session
    active_sessions[session_id] = {
        'connected_at': datetime.now(),
        'audio_buffer': [],
        'translation_queue': [],
        'is_processing': False,
        'target_language': 'es',
        'total_audio_duration': 0,
        'chunks_processed': 0
    }
    
    socketio.emit('connected', {
        'session_id': session_id,
        'status': 'connected',
        'message': 'WebSocket connection established for real-time audio translation'
    }, room=session_id)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    session_id = request.sid
    logger.info(f"WebSocket client disconnected: {session_id}")
    
    if session_id in active_sessions:
        # Clean up session
        session_data = active_sessions[session_id]
        logger.info(f"Session {session_id} processed {session_data['chunks_processed']} chunks, "
                   f"total duration: {session_data['total_audio_duration']:.2f}s")
        del active_sessions[session_id]

@socketio.on('start_streaming')
def handle_start_streaming(data):
    """Handle start of audio streaming session."""
    session_id = request.sid
    if session_id not in active_sessions:
        socketio.emit('error', {'message': 'Session not found'}, room=session_id)
        return
    
    session_data = active_sessions[session_id]
    session_data['target_language'] = data.get('target_language', 'es')
    session_data['is_processing'] = True
    
    logger.info(f"Started streaming session {session_id} for language: {session_data['target_language']}")
    
    socketio.emit('streaming_started', {
        'session_id': session_id,
        'target_language': session_data['target_language'],
        'message': 'Real-time audio streaming started'
    }, room=session_id)

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """Handle incoming audio chunk for real-time translation."""
    session_id = request.sid
    if session_id not in active_sessions:
        socketio.emit('error', {'message': 'Session not found'}, room=session_id)
        return
    
    try:
        session_data = active_sessions[session_id]
        audio_data = data.get('audio_data')
        chunk_duration = data.get('duration', 5.0)  # Default 5 seconds
        
        if not audio_data:
            socketio.emit('error', {'message': 'No audio data received'}, room=session_id)
            return
        
        # Add to audio buffer
        session_data['audio_buffer'].append({
            'data': audio_data,
            'duration': chunk_duration,
            'timestamp': datetime.now()
        })
        
        session_data['total_audio_duration'] += chunk_duration
        session_data['chunks_processed'] += 1
        
        logger.info(f"Received audio chunk {session_data['chunks_processed']} "
                   f"({chunk_duration}s) for session {session_id}")
        
        # Process audio chunk asynchronously
        process_audio_chunk_async(session_id, audio_data, chunk_duration)
        
        # Acknowledge receipt
        socketio.emit('chunk_received', {
            'chunk_id': session_data['chunks_processed'],
            'duration': chunk_duration,
            'total_duration': session_data['total_audio_duration']
        }, room=session_id)
        
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        socketio.emit('error', {'message': f'Error processing audio: {str(e)}'}, room=session_id)

@socketio.on('stop_streaming')
def handle_stop_streaming():
    """Handle stop of audio streaming session."""
    session_id = request.sid
    if session_id not in active_sessions:
        socketio.emit('error', {'message': 'Session not found'}, room=session_id)
        return
    
    session_data = active_sessions[session_id]
    session_data['is_processing'] = False
    
    logger.info(f"Stopped streaming session {session_id}")
    
    socketio.emit('streaming_stopped', {
        'session_id': session_id,
        'total_chunks': session_data['chunks_processed'],
        'total_duration': session_data['total_audio_duration']
    }, room=session_id)

def process_audio_chunk_async(session_id, audio_data, chunk_duration):
    """Process audio chunk asynchronously for translation."""
    try:
        # Initialize translator if needed
        init_translator()
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_data)
        
        # Create temporary file for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Save input audio
            input_file = temp_dir_path / "chunk.webm"
            with open(input_file, 'wb') as f:
                f.write(audio_bytes)
            
            # Convert to WAV if needed
            wav_input = temp_dir_path / "chunk.wav"
            try:
                import subprocess
                result = subprocess.run([
                    'ffmpeg', '-i', str(input_file), 
                    '-ar', '16000', '-ac', '1', str(wav_input)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    input_file = wav_input
            except (ImportError, FileNotFoundError):
                logger.warning("FFmpeg not available, using original audio format")
            
            # Output file
            output_file = temp_dir_path / "chunk_output.mp3"
            
            # Perform translation
            session_data = active_sessions.get(session_id)
            if not session_data:
                return
            
            target_language = session_data['target_language']
            
            results = translator.translate_audio(
                input_audio=input_file,
                output_audio=output_file,
                intermediate_files=False
            )
            
            if results["success"]:
                # Read translated audio
                with open(output_file, 'rb') as f:
                    translated_audio = base64.b64encode(f.read()).decode('utf-8')
                
                # Emit translation result to client
                socketio.emit('translation_result', {
                    'session_id': session_id,
                    'chunk_id': session_data['chunks_processed'],
                    'success': True,
                    'english_text': results["english_text"],
                    'spanish_text': results["spanish_text"],
                    'translated_audio': translated_audio,
                    'timings': results["timings"],
                    'target_language': target_language,
                    'chunk_duration': chunk_duration
                }, room=session_id)
                
                logger.info(f"Chunk {session_data['chunks_processed']} translated successfully")
            else:
                socketio.emit('translation_result', {
                    'session_id': session_id,
                    'chunk_id': session_data['chunks_processed'],
                    'success': False,
                    'error': results.get("error", "Translation failed")
                }, room=session_id)
                
    except Exception as e:
        logger.error(f"Error processing audio chunk {session_id}: {e}")
        socketio.emit('translation_result', {
            'session_id': session_id,
            'chunk_id': active_sessions.get(session_id, {}).get('chunks_processed', 0),
            'success': False,
            'error': str(e)
        }, room=session_id)

def run_server(host='localhost', port=8080, debug=False):
    """Run the web server."""
    logger.info(f"Starting Avatar Translator Web Server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_server(debug=True)
