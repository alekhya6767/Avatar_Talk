#!/usr/bin/env python3
"""
Quick fix for audio_translator.py model name issue.
"""

def fix_model_name():
    """Replace incorrect model name with correct one."""
    with open('audio_translator.py', 'r') as f:
        content = f.read()
    
    # Replace the incorrect model name
    old_model = 'facebook/xm_transformer_600m-en_es-multi_domain'
    new_model = 'facebook/m2m100_418M'
    
    content = content.replace(old_model, new_model)
    
    with open('audio_translator.py', 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed model name: {old_model} → {new_model}")

if __name__ == "__main__":
    fix_model_name()
    print("🎉 Run: python3 audio_translator.py airplanes.mp3 output.wav")
