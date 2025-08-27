"""
Text-to-Speech module using Google TTS for fast online synthesis.
"""
import logging
from pathlib import Path
from typing import Union


class TTSModule:
    """TTS module using Google TTS for fast online speech synthesis."""
    
    def __init__(self, **kwargs):
        """
        Initialize the TTS module with Google TTS.
        
        Args:
            **kwargs: Compatibility arguments (ignored for Google TTS)
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Google TTS module")
        
    def synthesize(self, text: str, output_path: Union[str, Path]) -> None:
        """
        Synthesize speech from text using Google TTS.
        
        Args:
            text: Text to synthesize
            output_path: Path for output audio file (.mp3)
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            from gtts import gTTS
        except ImportError:
            raise ImportError("gtts package is required. Install with: pip install gtts")
        
        # Prepare output path
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure output has .mp3 extension for Google TTS
        if output_path.suffix.lower() != ".mp3":
            output_path = output_path.with_suffix(".mp3")
        
        try:
            self.logger.info(f"Synthesizing speech to: {output_path}")
            
            # Generate TTS with Google TTS
            tts = gTTS(text=text, lang='es', slow=False)
            
            # Save directly as MP3
            tts.save(str(output_path))
            
            self.logger.info(f"Speech synthesis completed: {output_path}")
                
        except Exception as e:
            self.logger.error(f"Speech synthesis failed: {e}")
            raise
    
    def get_status(self) -> dict:
        """Get status of TTS components."""
        try:
            import gtts
            gtts_available = True
        except ImportError:
            gtts_available = False
            
        return {
            "method": "google_tts",
            "gtts_available": gtts_available,
            "output_format": "mp3",
            "language": "es"
        }
