#!/usr/bin/env python3

import os
import sys
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

def test_audio_detection(audio_file):
    """Test audio silence detection"""
    print(f"Testing audio file: {audio_file}")
    
    # Check if file exists
    if not os.path.exists(audio_file):
        print(f"❌ File not found: {audio_file}")
        return False
    
    # Check if it's an audio file
    audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
    file_ext = os.path.splitext(audio_file)[1].lower()
    is_audio_only = file_ext in audio_extensions
    
    print(f"File extension: {file_ext}")
    print(f"Is audio file: {is_audio_only}")
    
    if not is_audio_only:
        print(f"❌ Not an audio file")
        return False
    
    try:
        # Load audio directly
        print("Loading audio...")
        audio = AudioSegment.from_file(audio_file)
        duration_ms = len(audio)
        print(f"✅ Audio loaded: {duration_ms}ms, {audio.channels} channels, {audio.frame_rate}Hz")
        
        # Test silence detection
        print("Detecting silence...")
        silence_threshold = -40  # dB
        min_silence_duration = 500  # ms
        
        non_silent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_duration,
            silence_thresh=silence_threshold,
            seek_step=1
        )
        
        print(f"✅ Found {len(non_silent_ranges)} non-silent ranges")
        if non_silent_ranges:
            for i, (start, end) in enumerate(non_silent_ranges[:3]):
                print(f"  Range {i+1}: {start}ms - {end}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_audio_detection(sys.argv[1])
    else:
        print("Usage: python test_audio_detection.py <audio_file>")
        print("Example: python test_audio_detection.py test.wav") 