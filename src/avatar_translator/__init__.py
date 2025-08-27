"""
Avatar Translator - A local FOSS pipeline for English to Spanish audio translation.

This package provides:
- ASR: faster-whisper (CTranslate2 backend)
- MT: MarianMT (Helsinki-NLP opus-mt-en-es) with Argos Translate fallback
- TTS: Piper (ONNX voices) via subprocess
"""

__version__ = "0.1.0"
__author__ = "Avatar Translator Team"

from .core import AudioTranslator
from .asr import ASRModule
from .mt import MTModule
from .tts import TTSModule

__all__ = [
    "AudioTranslator",
    "ASRModule", 
    "MTModule",
    "TTSModule",
]
