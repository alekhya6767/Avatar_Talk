"""
Avatar Translator - Main pipeline orchestrator for audio translation.
Now supports dynamic target_language per call.
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

    def __init__(
        self,
        whisper_model_size: str = "tiny",
        piper_path: Optional[str] = None,         # deprecated
        spanish_voice_model: Optional[str] = None, # deprecated
        log_level: str = "INFO",
    ):
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        self.logger.info("Initializing Avatar Translator pipeline")
        self.asr = ASRModule(model_size=whisper_model_size)
        self.mt = MTModule(source_lang="en", target_lang="es")
        self.tts = TTSModule()
        self.logger.info("Pipeline initialization complete")

    def translate_audio(
        self,
        input_audio: Union[str, Path],
        output_audio: Union[str, Path],
        intermediate_files: bool = False,
        target_lang: str = "es",
    ) -> dict:
        """
        Translate audio from English to the specified target language.

        Returns dict with english_text, translated_text, timings, success, etc.
        """
        start_time = time.time()
        results = {
            "input_file": str(input_audio),
            "output_file": str(output_audio),
            "english_text": "",
            "translated_text": "",
            "spanish_text": "",   # kept for backward-compat with old clients
            "target_language": target_lang,
            "timings": {},
            "success": False,
        }

        try:
            input_path = Path(input_audio)
            output_path = Path(output_audio)
            if not input_path.exists():
                raise FileNotFoundError(f"Input audio file not found: {input_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Pipeline: {input_path} -> {output_path}  lang={target_lang}")

            # 1) ASR (English)
            asr_start = time.time()
            english_text = self.asr.transcribe(input_path, language="en")
            results["english_text"] = english_text
            results["timings"]["asr"] = time.time() - asr_start
            if not english_text.strip():
                raise ValueError("No speech detected in input audio")

            if intermediate_files:
                output_path.with_suffix(".en.txt").write_text(english_text, encoding="utf-8")

            # 2) MT → dynamic target
            mt_start = time.time()
            translated = self.mt.translate(english_text, target_lang=target_lang)
            results["translated_text"] = translated
            # For older code paths that still look for 'spanish_text'
            results["spanish_text"] = translated if target_lang == "es" else ""
            results["timings"]["mt"] = time.time() - mt_start

            if intermediate_files:
                # Save as .<lang>.txt, e.g., .fr.txt
                output_path.with_suffix(f".{target_lang}.txt").write_text(translated, encoding="utf-8")

            # 3) TTS → dynamic target
            tts_start = time.time()
            self.tts.synthesize(translated, output_path, lang=target_lang)
            results["timings"]["tts"] = time.time() - tts_start

            # Totals
            results["timings"]["total"] = time.time() - start_time
            results["success"] = True
            return results

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            results["error"] = str(e)
            results["timings"]["total"] = time.time() - start_time
            raise RuntimeError(f"Pipeline failed: {e}")

    def get_pipeline_status(self) -> dict:
        return {
            "asr": self.asr.get_model_info(),
            "mt": self.mt.get_status(),
            "tts": self.tts.get_status(),
        }

    def test_pipeline(self, test_text: str = "Hello, this is a test.") -> bool:
        try:
            # Quick sanity: en->es
            spanish_text = self.mt.translate(test_text, target_lang="es")
            test_output = Path("test_output.mp3")
            self.tts.synthesize(spanish_text, test_output, lang="es")
            if test_output.exists():
                test_output.unlink()
                return True
            return False
        except Exception:
            return False
