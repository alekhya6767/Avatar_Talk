"""
Text-to-Speech module using Google TTS (gTTS) for fast online synthesis.
Now supports dynamic language codes (e.g., 'es', 'fr', 'it', 'hi', 'de', 'pt').
"""
import logging
from pathlib import Path
from typing import Union


class TTSModule:
    """TTS module using Google TTS for fast online speech synthesis."""

    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Google TTS module")
        self._last_lang = "es"

    def synthesize(self, text: str, output_path: Union[str, Path], lang: str = "es") -> None:
        """
        Synthesize speech from text using Google TTS.

        Args:
            text: Text to synthesize
            output_path: Path for output audio file (.mp3)
            lang: gTTS language code ('es','fr','it','hi','de','pt', ...)
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            from gtts import gTTS
        except ImportError:
            raise ImportError("gtts package is required. Install with: pip install gtts")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() != ".mp3":
            output_path = output_path.with_suffix(".mp3")

        self.logger.info(f"Synthesizing ({lang}) to: {output_path}")
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(str(output_path))
        self._last_lang = lang
        self.logger.info(f"Speech synthesis completed: {output_path}")

    def get_status(self) -> dict:
        try:
            import gtts  # noqa: F401
            gtts_available = True
        except ImportError:
            gtts_available = False

        return {
            "method": "google_tts",
            "gtts_available": gtts_available,
            "output_format": "mp3",
            "last_language": self._last_lang,
        }
