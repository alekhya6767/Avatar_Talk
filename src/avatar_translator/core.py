"""
Avatar Translator - Main pipeline orchestrator for English to Spanish audio translation.
"""
import logging
from pathlib import Path
from typing import Optional, Union
import time

from .asr import ASRModule
from .mt import MTModule
from .tts import TTSModule


class AudioTranslator:
    """Main pipeline orchestrator for audio translation."""
    
    def __init__(self, 
                 whisper_model_size: str = "tiny",
                 piper_path: Optional[str] = None,
                 spanish_voice_model: Optional[str] = None,
                 log_level: str = "INFO"):
        """
        Initialize the Audio Translator pipeline.
        
        Args:
            whisper_model_size: Whisper model size for ASR
            piper_path: Path to Piper executable (deprecated)
            spanish_voice_model: Path to Spanish voice model for TTS (deprecated)
            log_level: Logging level
        """
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize modules
        self.logger.info("Initializing Avatar Translator pipeline")
        
        self.asr = ASRModule(model_size=whisper_model_size)
        self.mt = MTModule(source_lang="en", target_lang="es")
        self.tts = TTSModule()
        
        self.logger.info("Pipeline initialization complete")
    
    def translate_audio(self, 
                       input_audio: Union[str, Path], 
                       output_audio: Union[str, Path],
                       intermediate_files: bool = False) -> dict:
        """
        Translate audio from English to Spanish.
        
        Args:
            input_audio: Path to input English audio file
            output_audio: Path for output Spanish audio file
            intermediate_files: Whether to save intermediate text files
            
        Returns:
            Dictionary with pipeline results and timing information
        """
        start_time = time.time()
        results = {
            "input_file": str(input_audio),
            "output_file": str(output_audio),
            "english_text": "",
            "spanish_text": "",
            "timings": {},
            "success": False
        }
        
        try:
            input_path = Path(input_audio)
            output_path = Path(output_audio)
            
            if not input_path.exists():
                raise FileNotFoundError(f"Input audio file not found: {input_path}")
            
            # Create output directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Starting translation pipeline: {input_path} -> {output_path}")
            
            # Step 1: ASR (Speech to Text)
            self.logger.info("Step 1: Transcribing English audio...")
            asr_start = time.time()
            
            english_text = self.asr.transcribe(input_path, language="en")
            results["english_text"] = english_text
            
            asr_time = time.time() - asr_start
            results["timings"]["asr"] = asr_time
            
            self.logger.info(f"ASR completed in {asr_time:.2f}s")
            self.logger.info(f"Transcribed text: {english_text}")
            
            if not english_text.strip():
                raise ValueError("No speech detected in input audio")
            
            # Save intermediate file if requested
            if intermediate_files:
                english_text_file = output_path.with_suffix(".en.txt")
                english_text_file.write_text(english_text, encoding="utf-8")
                self.logger.info(f"Saved English text to: {english_text_file}")
            
            # Step 2: MT (Text Translation)
            self.logger.info("Step 2: Translating text to Spanish...")
            mt_start = time.time()
            
            spanish_text = self.mt.translate(english_text)
            results["spanish_text"] = spanish_text
            
            mt_time = time.time() - mt_start
            results["timings"]["mt"] = mt_time
            
            self.logger.info(f"MT completed in {mt_time:.2f}s")
            self.logger.info(f"Translated text: {spanish_text}")
            
            # Save intermediate file if requested
            if intermediate_files:
                spanish_text_file = output_path.with_suffix(".es.txt")
                spanish_text_file.write_text(spanish_text, encoding="utf-8")
                self.logger.info(f"Saved Spanish text to: {spanish_text_file}")
            
            # Step 3: TTS (Text to Speech)
            self.logger.info("Step 3: Synthesizing Spanish audio...")
            tts_start = time.time()
            
            self.tts.synthesize(spanish_text, output_path)
            
            tts_time = time.time() - tts_start
            results["timings"]["tts"] = tts_time
            
            self.logger.info(f"TTS completed in {tts_time:.2f}s")
            
            # Calculate total time
            total_time = time.time() - start_time
            results["timings"]["total"] = total_time
            results["success"] = True
            
            self.logger.info(f"Pipeline completed successfully in {total_time:.2f}s")
            self.logger.info(f"Output saved to: {output_path}")
            
            return results
            
        except Exception as e:
            error_msg = f"Pipeline failed: {e}"
            self.logger.error(error_msg)
            results["error"] = str(e)
            results["timings"]["total"] = time.time() - start_time
            raise RuntimeError(error_msg)
    
    def get_pipeline_status(self) -> dict:
        """Get status of all pipeline components."""
        return {
            "asr": self.asr.get_model_info(),
            "mt": self.mt.get_status(),
            "tts": self.tts.get_status()
        }
    
    def test_pipeline(self, test_text: str = "Hello, this is a test.") -> bool:
        """
        Test the pipeline with sample text (MT + TTS only).
        
        Args:
            test_text: Text to test with
            
        Returns:
            True if test successful, False otherwise
        """
        try:
            self.logger.info("Testing pipeline components...")
            
            # Test MT
            spanish_text = self.mt.translate(test_text)
            self.logger.info(f"MT test: '{test_text}' -> '{spanish_text}'")
            
            # Test TTS
            test_output = Path("test_output.mp3")
            self.tts.synthesize(spanish_text, test_output)
            
            if test_output.exists():
                test_output.unlink()  # Clean up
                self.logger.info("TTS test successful")
            else:
                self.logger.error("TTS test failed - no output file")
                return False
            
            self.logger.info("Pipeline test completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Pipeline test failed: {e}")
            return False
