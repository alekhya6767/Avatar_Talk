#!/usr/bin/env python3
"""
Command Line Interface for Avatar Translator.
"""
import argparse
import sys
from pathlib import Path
from .core import AudioTranslator


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Avatar Translator - English to Spanish Audio Translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.wav output.wav --voice-model spanish_voice.onnx
  %(prog)s input.wav output.wav --voice-model spanish_voice.onnx --whisper-model small
  %(prog)s --test --voice-model spanish_voice.onnx
        """
    )
    
    # Positional arguments
    parser.add_argument("input_audio", nargs="?", help="Input English audio file")
    parser.add_argument("output_audio", nargs="?", help="Output Spanish audio file")
    
    # Required arguments
    parser.add_argument("--voice-model", 
                       help="Path to Spanish voice model (.onnx file)")
    
    # Optional arguments
    parser.add_argument("--whisper-model", default="base",
                       choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                       help="Whisper model size (default: base)")
    
    parser.add_argument("--piper-path", 
                       help="Path to Piper executable (if not in PATH)")
    
    parser.add_argument("--save-intermediate", action="store_true",
                       help="Save intermediate text files (.en.txt, .es.txt)")
    
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: INFO)")
    
    parser.add_argument("--test", action="store_true",
                       help="Test the pipeline without processing audio")
    
    parser.add_argument("--status", action="store_true",
                       help="Show pipeline component status")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.test and not args.status:
        if not args.input_audio or not args.output_audio:
            parser.error("input_audio and output_audio are required unless using --test or --status")
    
    # Check voice model exists if provided
    if args.voice_model:
        voice_model_path = Path(args.voice_model)
        if not voice_model_path.exists():
            print(f"Error: Voice model not found: {voice_model_path}")
            print("Please download a Spanish voice model from:")
            print("https://huggingface.co/rhasspy/piper-voices/tree/main/es")
            return 1
    
    try:
        # Initialize translator
        print(f"Initializing Avatar Translator...")
        print(f"  Whisper model: {args.whisper_model}")
        if args.voice_model:
            print(f"  Voice model: {args.voice_model}")
        
        translator = AudioTranslator(
            whisper_model_size=args.whisper_model,
            piper_path=args.piper_path,
            spanish_voice_model=args.voice_model,
            log_level=args.log_level
        )
        
        # Handle different modes
        if args.status:
            print("\nPipeline Status:")
            status = translator.get_pipeline_status()
            for component, info in status.items():
                print(f"  {component.upper()}:")
                for key, value in info.items():
                    print(f"    {key}: {value}")
            return 0
        
        if args.test:
            print("\nTesting pipeline...")
            if translator.test_pipeline():
                print("✓ Pipeline test successful")
                return 0
            else:
                print("✗ Pipeline test failed")
                return 1
        
        # Validate input file
        input_path = Path(args.input_audio)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}")
            return 1
        
        # Perform translation
        print(f"\nTranslating: {args.input_audio} -> {args.output_audio}")
        
        results = translator.translate_audio(
            input_audio=args.input_audio,
            output_audio=args.output_audio,
            intermediate_files=args.save_intermediate
        )
        
        if results["success"]:
            print("\n✓ Translation completed successfully!")
            print(f"  English text: {results['english_text']}")
            print(f"  Spanish text: {results['spanish_text']}")
            print(f"  Total time: {results['timings']['total']:.2f}s")
            print(f"    - ASR: {results['timings']['asr']:.2f}s")
            print(f"    - MT: {results['timings']['mt']:.2f}s")
            print(f"    - TTS: {results['timings']['tts']:.2f}s")
            print(f"  Output saved to: {args.output_audio}")
            
            if args.save_intermediate:
                output_path = Path(args.output_audio)
                en_file = output_path.with_suffix(".en.txt")
                es_file = output_path.with_suffix(".es.txt")
                print(f"  Intermediate files:")
                print(f"    - English: {en_file}")
                print(f"    - Spanish: {es_file}")
            
            return 0
        else:
            print("✗ Translation failed")
            return 1
            
    except KeyboardInterrupt:
        print("\nTranslation interrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
