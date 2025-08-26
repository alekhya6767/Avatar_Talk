#!/usr/bin/env python3
"""
Fast installation script using uv for Avatar Translator dependencies.
"""
import subprocess
import sys

def install_uv():
    """Install uv if not available."""
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        print("✅ uv already available")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("📦 Installing uv...")
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
        print("✅ uv installed")
        return True

def install_dependencies():
    """Install dependencies using uv (much faster than pip)."""
    packages = [
        "torch>=2.0.0",
        "torchaudio>=2.0.0", 
        "transformers>=4.35.0",
        "faster-whisper>=0.10.0",
        "sentencepiece>=0.1.99",
        "scipy>=1.10.0",
        "numpy>=1.24.0"
    ]
    
    print("⚡ Installing dependencies with uv (fast)...")
    
    try:
        # Install all packages at once with uv
        subprocess.run(["uv", "pip", "install"] + packages, check=True)
        print("✅ All dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ uv installation failed: {e}")
        print("Falling back to pip...")
        
        # Fallback to pip
        for package in packages:
            subprocess.run([sys.executable, "-m", "pip", "install", package])
        return True

def main():
    print("🚀 Fast Avatar Translator Setup")
    print("=" * 30)
    
    install_uv()
    install_dependencies()
    
    print("\n🎉 Setup complete! Now run:")
    print("  python3 audio_translator.py airplanes.mp3 output.wav")

if __name__ == "__main__":
    main()
