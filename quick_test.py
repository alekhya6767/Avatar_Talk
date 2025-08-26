#!/usr/bin/env python3
"""
Quick test translator without ffmpeg dependency.
Uses direct MP3 output from Google TTS.
"""
import sys
import subprocess
from pathlib import Path
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def install_deps():
    """Install minimal dependencies."""
    packages = ["faster-whisper>=0.10.0", "argostranslate>=1.9.0", "gtts>=2.4.0"]
    for pkg in packages:
        try:
            subprocess.run(["uv", "pip", "install", pkg], check=True, capture_output=True)
        except:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True, capture_output=True)

class QuickTranslator:
    def __init__(self):
        self.whisper_model = None
        
    def setup_asr(self):
        """Setup Whisper tiny model."""
        from faster_whisper import WhisperModel
        self.whisper_model = WhisperModel("tiny", device="auto", compute_type="auto")
        logger.info("✅ Fast ASR loaded")
    
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio to text."""
        if not self.whisper_model:
            self.setup_asr()
        
        logger.info(f"🎤 Transcribing: {audio_path}")
        segments, _ = self.whisper_model.transcribe(audio_path, language="en")
        text = " ".join([seg.text.strip() for seg in segments])
        logger.info(f"📝 Text: {text[:100]}...")
        return text
    
    def translate(self, text: str) -> str:
        """Translate using argostranslate."""
        try:
            import argostranslate.package
            import argostranslate.translate
            
            # Check if EN-ES package is installed
            installed = argostranslate.package.get_installed_packages()
            en_es_installed = any(pkg.from_code == "en" and pkg.to_code == "es" for pkg in installed)
            
            if not en_es_installed:
                logger.info("📦 Installing EN-ES package...")
                available = argostranslate.package.get_available_packages()
                en_es_pkg = next((pkg for pkg in available if pkg.from_code == "en" and pkg.to_code == "es"), None)
                if en_es_pkg:
                    argostranslate.package.install_from_path(en_es_pkg.download())
            
            logger.info("🔄 Translating...")
            translated = argostranslate.translate.translate(text, "en", "es")
            logger.info(f"🔄 Spanish: {translated[:100]}...")
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text  # Fallback to original
    
    def synthesize(self, text: str, output_path: str) -> bool:
        """Generate Spanish speech using Google TTS."""
        try:
            from gtts import gTTS
            
            logger.info("🎤 Generating Spanish speech...")
            tts = gTTS(text=text, lang='es', slow=False)
            
            # Save directly as MP3 (no conversion needed)
            mp3_path = output_path.replace('.wav', '.mp3')
            tts.save(mp3_path)
            
            logger.info(f"✅ Spanish audio saved: {mp3_path}")
            return True
            
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return False
    
    def translate_audio(self, input_file: str, output_file: str):
        """Complete pipeline."""
        start_time = time.time()
        
        print("⚡ Quick Audio Translation")
        print("=" * 30)
        
        try:
            # Step 1: Transcribe
            english_text = self.transcribe(input_file)
            
            # Step 2: Translate
            spanish_text = self.translate(english_text)
            
            # Step 3: Synthesize
            success = self.synthesize(spanish_text, output_file)
            
            duration = time.time() - start_time
            
            if success:
                mp3_output = output_file.replace('.wav', '.mp3')
                print(f"\n🎉 Completed in {duration:.1f}s!")
                print(f"   Output: {mp3_output}")
                print(f"   Play: aplay {mp3_output} (or use any audio player)")
                return True
            else:
                print("❌ Failed")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

def main():
    if len(sys.argv) != 3:
        print("Usage: python quick_test.py <input.mp3> <output.wav>")
        sys.exit(1)
    
    input_file, output_file = sys.argv[1], sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"❌ File not found: {input_file}")
        sys.exit(1)
    
    translator = QuickTranslator()
    success = translator.translate_audio(input_file, output_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
