#!/usr/bin/env python3
"""
Test script for WebSocket audio streaming functionality.
"""
import socketio
import time
import base64
import json

# Create a Socket.IO client
sio = socketio.Client()

@sio.event
def connect():
    print('✅ Connected to WebSocket server')
    
    # Start streaming session
    sio.emit('start_streaming', {'target_language': 'es'})

@sio.event
def streaming_started(data):
    print(f'🔄 Streaming session started: {data}')

@sio.event
def chunk_received(data):
    print(f'📡 Audio chunk received: {data}')

@sio.event
def translation_result(data):
    print(f'🎯 Translation result: {data}')
    
    if data.get('success'):
        print(f"✅ Chunk {data.get('chunk_id')} translated successfully!")
        print(f"🔤 English: {data.get('english_text', 'N/A')}")
        print(f"🇪🇸 Spanish: {data.get('spanish_text', 'N/A')}")
        print(f"⏱️ Duration: {data.get('chunk_duration', 'N/A')}s")
    else:
        print(f"❌ Translation failed: {data.get('error', 'Unknown error')}")

@sio.event
def error(data):
    print(f'❌ WebSocket error: {data}')

@sio.event
def disconnect():
    print('🔌 Disconnected from WebSocket server')

def test_audio_streaming():
    """Test audio streaming functionality."""
    try:
        # Connect to the WebSocket server
        print('🔌 Connecting to WebSocket server...')
        sio.connect('http://localhost:8080')
        
        # Wait for connection
        time.sleep(2)
        
        if sio.connected:
            print('🎙️ Testing audio streaming...')
            
            # Simulate sending audio chunks
            for i in range(3):
                # Create dummy audio data (base64 encoded)
                dummy_audio = base64.b64encode(f"dummy_audio_chunk_{i}".encode()).decode()
                
                # Send audio chunk
                sio.emit('audio_chunk', {
                    'audio_data': dummy_audio,
                    'duration': 5.0,
                    'chunk_id': i + 1,
                    'timestamp': int(time.time() * 1000)
                })
                
                print(f'📤 Sent audio chunk {i + 1}')
                time.sleep(2)  # Wait between chunks
            
            # Wait for translations
            print('⏳ Waiting for translation results...')
            time.sleep(10)
            
            # Stop streaming
            sio.emit('stop_streaming')
            print('⏹️ Stopped streaming')
            
        else:
            print('❌ Failed to connect to WebSocket server')
            
    except Exception as e:
        print(f'❌ Test failed: {e}')
    
    finally:
        # Disconnect
        if sio.connected:
            sio.disconnect()
        print('🔌 Test completed')

if __name__ == '__main__':
    test_audio_streaming()
