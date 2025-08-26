#!/usr/bin/env python3
"""
Fast English Audio to Spanish Audio Translation Pipeline.
Optimized for speed using lighter models.
"""
import sys
import subprocess
from pathlib import Path
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def install_dependencies():
    """Install required dependencies using uv (faster) or pip."""
    required_packages = [
        "faster-whisper>=0.10.0",
        "argostranslate>=1.9.0",
        "gtts>=2.4.0",
        "pydub>=0.25.0"
    ]
    
    print("🔧 Installing lightweight dependencies...")
    
    for package in required_packages:
        try:
            # Try uv first (faster)
            subprocess.run(["uv", "pip", "install", package], check=True, capture_output=True)
            print(f"✅ {package} (uv)")
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                # Fallback to pip
                subprocess.run([sys.executable, "-m", "pip", "install", package], check=True, capture_output=True)
                print(f"✅ {package} (pip)")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {package}: {e}")

class FastAudioTranslator:
    """Fast audio translation pipeline using lightweight models."""
    
    def __init__(self):
        self.whisper_model = None
        self.translator = None
        
    def setup_asr(self):
        """Setup Faster Whisper (lightweight ASR)."""
        try:
            from faster_whisper import WhisperModel
            # Use tiny model for speed
            self.whisper_model = WhisperModel("tiny", device="auto", compute_type="auto")
            logger.info("✅ Fast ASR model loaded (tiny)")
        except Exception as e:
            logger.error(f"Failed to load ASR model: {e}")
            install_dependencies()
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel("tiny", device="auto", compute_type="auto")
    
    def setup_translation(self):
        """Setup Argos Translate (fast offline translation)."""
        try:
            import argostranslate.package
            import argostranslate.translate
            
            # Install EN-ES package if not available
            available_packages = argostranslate.package.get_available_packages()
            en_es_package = None
            
            for package in available_packages:
                if package.from_code == "en" and package.to_code == "es":
                    en_es_package = package
                    break
            
            if en_es_package and not en_es_package.is_installed():
                print("📦 Installing EN-ES translation package...")
                argostranslate.package.install_from_path(en_es_package.download())
            
            self.translator = argostranslate.translate
            logger.info("✅ Fast translation model loaded (Argos)")
            
        except Exception as e:
            logger.error(f"Failed to load translation model: {e}")
            install_dependencies()
            import argostranslate.package
            import argostranslate.translate
            self.translator = argostranslate.translate
    
    def setup_tts(self):
        """Setup Google TTS (fast online TTS)."""
        try:
            from gtts import gTTS
            logger.info("✅ Fast TTS ready (Google)")
            return True
        except Exception as e:
            logger.error(f"Failed to load TTS: {e}")
            install_dependencies()
            return True
    
    def transcribe_audio(self, audio_path: str) -> str:
        """Convert English audio to text using tiny Whisper."""
        if self.whisper_model is None:
            self.setup_asr()
        
        logger.info(f"🎤 Transcribing: {audio_path}")
        segments, info = self.whisper_model.transcribe(audio_path, language="en")
        text = " ".join([segment.text.strip() for segment in segments])
        logger.info(f"📝 Transcribed: {text[:100]}...")
        return text
    
    def translate_text(self, text: str) -> str:
        """Translate English text to Spanish using Argos."""
        if self.translator is None:
            self.setup_translation()
        
        logger.info("🔄 Translating to Spanish...")
        translated = self.translator.translate(text, "en", "es")
        logger.info(f"🔄 Translated: {translated[:100]}...")
        return translated
    
    def synthesize_speech(self, text: str, output_path: str) -> bool:
        """Convert Spanish text to speech using Google TTS."""
        self.setup_tts()
        
        logger.info(f"🎤 Synthesizing Spanish speech...")
        
        try:
            from gtts import gTTS
            from pydub import AudioSegment
            import io
            
            # Generate TTS
            tts = gTTS(text=text, lang='es', slow=False)
            
            # Save to memory buffer first
            mp3_buffer = io.BytesIO()
            tts.write_to_fp(mp3_buffer)
            mp3_buffer.seek(0)
            
            # Convert MP3 to WAV using pydub
            audio = AudioSegment.from_mp3(mp3_buffer)
            audio.export(output_path, format="wav")
            
            duration = len(audio) / 1000.0  # Convert to seconds
            logger.info(f"✅ Spanish audio saved: {output_path} ({duration:.1f}s)")
            return True
            
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            return False
    
    def translate_audio(self, input_audio: str, output_audio: str) -> dict:
        """Complete fast pipeline: English audio -> Spanish audio."""
        start_time = time.time()
        
        print("⚡ Fast English Audio → Spanish Audio Translation")
        print("=" * 55)
        
        try:
            # Step 1: Fast Speech Recognition (tiny model)
            english_text = self.transcribe_audio(input_audio)
            
            # Step 2: Fast Translation (Argos)
            spanish_text = self.translate_text(english_text)
            
            # Step 3: Fast Text-to-Speech (Google TTS)
            success = self.synthesize_speech(spanish_text, output_audio)
            
            total_time = time.time() - start_time
            
            if success:
                print(f"\n🎉 Fast translation completed in {total_time:.1f}s!")
                print(f"   Input: {input_audio}")
                print(f"   Output: {output_audio}")
                print(f"   Play with: aplay {output_audio}")
                
                return {
                    "success": True,
                    "english_text": english_text,
                    "spanish_text": spanish_text,
                    "output_file": output_audio,
                    "duration": total_time
                }
            else:
                return {"success": False, "error": "Speech synthesis failed"}
                
        except Exception as e:
            logger.error(f"Translation pipeline failed: {e}")
            return {"success": False, "error": str(e)}

def main():
    """Main function for command line usage."""
    if len(sys.argv) != 3:
        print("Usage: python fast_audio_translator.py <input_audio.mp3> <output_audio.wav>")
        print("Example: python fast_audio_translator.py birthdays.mp3 birthdays_spanish.wav")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)
    
    # Create fast translator and run pipeline
    translator = FastAudioTranslator()
    result = translator.translate_audio(input_file, output_file)
    
    if result["success"]:
        print("\n📊 Results:")
        print(f"   English: {result['english_text'][:100]}...")
        print(f"   Spanish: {result['spanish_text'][:100]}...")
        sys.exit(0)
    else:
        print(f"❌ Translation failed: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
