# Avatar Translator

A local, fully FOSS pipeline that converts English audio to Spanish audio using state-of-the-art open-source models.

## Components

- **ASR**: faster-whisper (CTranslate2 backend) - Fast and accurate speech recognition
- **MT**: MarianMT (Helsinki-NLP opus-mt-en-es) with Argos Translate fallback - Neural machine translation
- **TTS**: Piper (ONNX voices) via subprocess - High-quality text-to-speech synthesis

## Features

- ✅ Fully offline operation
- ✅ No API keys or cloud dependencies
- ✅ Automatic fallback translation system
- ✅ Comprehensive error handling and logging
- ✅ Intermediate file saving for debugging
- ✅ Performance timing metrics
- ✅ Multiple Whisper model sizes supported
- ✅ GPU acceleration support (CUDA)
- ✅ Modern Python packaging with `uv`

## Quick Start

1. **Install with uv (recommended):**
```bash
# Install uv if not already installed
pip install uv

# Install all dependencies automatically
uv sync
```

2. **Or install manually:**
```bash
pip install -e .
```

3. **Download Piper TTS:**
   - Windows: Download from [Piper Releases](https://github.com/rhasspy/piper/releases)
   - Extract and add to PATH or note installation directory

4. **Download Spanish voice model:**
   - Visit [Piper Voices](https://huggingface.co/rhasspy/piper-voices/tree/main/es)
   - Recommended: `es_ES-mms-female.onnx` or `es_MX-claude-high.onnx`
   - Download both `.onnx` and `.json` files

5. **Run translation:**
```bash
# Using uv (recommended)
uv run avatar-translator input_audio.wav output_audio.wav --voice-model path/to/spanish_voice.onnx

# Or using installed package
avatar-translator input_audio.wav output_audio.wav --voice-model path/to/spanish_voice.onnx
```

## Usage Examples

### Command Line Interface
```bash
# Basic usage
python cli.py input.wav output.wav --voice-model spanish_voice.onnx

# With custom Whisper model and intermediate files
python cli.py input.wav output.wav --voice-model spanish_voice.onnx --whisper-model small --save-intermediate

# Test pipeline
python cli.py --test --voice-model spanish_voice.onnx
```

### Python API
```python
from avatar_translator import AudioTranslator

# Initialize translator
translator = AudioTranslator(
    whisper_model_size="base",
    spanish_voice_model="path/to/spanish_voice.onnx"
)

# Translate audio
results = translator.translate_audio(
    input_audio="english_audio.wav",
    output_audio="spanish_audio.wav",
    intermediate_files=True
)

print(f"Translation completed in {results['timings']['total']:.2f}s")
```

## Supported Audio Formats

- Input: WAV, MP3, M4A, FLAC, OGG (any format supported by ffmpeg)
- Output: WAV (16-bit, 22050 Hz)

## Model Options

### Whisper Models (ASR)
- `tiny` - Fastest, least accurate (~39 MB)
- `base` - Good balance (~74 MB) **[Recommended]**
- `small` - Better accuracy (~244 MB)
- `medium` - High accuracy (~769 MB)
- `large-v2/large-v3` - Best accuracy (~1550 MB)

### Translation Models
- **Primary**: MarianMT (Helsinki-NLP opus-mt-en-es)
- **Fallback**: Argos Translate (automatically installed)

## Performance Tips

- Use GPU acceleration: Install CUDA-compatible PyTorch
- For faster processing: Use `tiny` or `base` Whisper models
- For better quality: Use `small` or `medium` models
- Enable intermediate files for debugging translation quality

## Troubleshooting

### Common Issues

1. **Piper not found**: Ensure Piper is in PATH or specify full path
2. **Voice model error**: Download both `.onnx` and `.json` files
3. **CUDA errors**: Install CUDA-compatible PyTorch version
4. **Audio format issues**: Convert to WAV using ffmpeg

### Logs and Debugging

Enable verbose logging:
```python
translator = AudioTranslator(log_level="DEBUG")
```

Save intermediate files for inspection:
```python
results = translator.translate_audio(..., intermediate_files=True)
```

## Requirements

- Python 3.8+
- 4GB+ RAM (8GB+ recommended for larger models)
- Optional: CUDA-compatible GPU for acceleration
