"""
Automatic Speech Recognition module using faster-whisper.
"""
import logging
from pathlib import Path
from typing import Optional, Union
from faster_whisper import WhisperModel


class ASRModule:
    """ASR module using faster-whisper with CTranslate2 backend."""
    
    def __init__(self, model_size: str = "base", device: str = "auto", compute_type: str = "auto"):
        """
        Initialize the ASR module.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to run on ("cpu", "cuda", "auto")
            compute_type: Compute type ("int8", "int16", "float16", "float32", "auto")
        """
        self.logger = logging.getLogger(__name__)
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        
    def load_model(self) -> None:
        """Load the Whisper model."""
        try:
            self.logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            self.logger.info("Whisper model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe(self, audio_path: Union[str, Path], language: str = "en") -> str:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to audio file
            language: Source language code (default: "en")
            
        Returns:
            Transcribed text
        """
        if self.model is None:
            self.load_model()
            
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
                
            self.logger.info(f"Transcribing audio: {audio_path}")
            
            segments, info = self.model.transcribe(
                str(audio_path),
                language=language,
                beam_size=5,
                best_of=5,
                temperature=0.0
            )
            
            # Combine all segments into a single text
            transcription = " ".join([segment.text.strip() for segment in segments])
            
            self.logger.info(f"Transcription completed. Language: {info.language}, "
                           f"Probability: {info.language_probability:.2f}")
            
            return transcription.strip()
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            raise
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        if self.model is None:
            return {"status": "not_loaded"}
            
        return {
            "status": "loaded",
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type
        }
