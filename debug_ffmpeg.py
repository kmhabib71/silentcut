import os
import sys
import subprocess
import tempfile
import numpy as np
import matplotlib.pyplot as plt
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

def find_ffmpeg():
    """Try to find FFmpeg executable path"""
    # Check known locations
    known_locations = [
        "ffmpeg",  # System PATH
        "C:\\ffmpeg\\bin\\ffmpeg.exe",
        "C:\\Users\\WALTON\\ffmpeg-2025-05-07-git-1b643e3f65-full_build\\ffmpeg-2025-05-07-git-1b643e3f65-full_build\\bin\\ffmpeg.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
    ]
    
    for location in known_locations:
        try:
            # Try to run FFmpeg version command
            process = subprocess.run(
                [location, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if process.returncode == 0:
                print(f"✅ FFmpeg found at: {location}")
                return location
        except Exception as e:
            continue
    
    print("❌ FFmpeg not found in any known location")
    return None

def extract_audio(video_path, ffmpeg_path):
    """Extract audio from video using direct FFmpeg command"""
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return None
    
    # Create a temporary WAV file
    temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_audio_path = temp_audio.name
    temp_audio.close()
    
    try:
        print(f"📥 Extracting audio from: {video_path}")
        # Use subprocess to run FFmpeg directly
        process = subprocess.run(
            [
                ffmpeg_path,
                "-i", video_path,
                "-y",  # Overwrite output file if it exists
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # PCM 16-bit little-endian audio
                "-ar", "44100",  # 44.1kHz sample rate
                "-ac", "2",  # 2 channels (stereo)
                temp_audio_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if process.returncode != 0:
            print(f"❌ Error extracting audio: {process.stderr.decode()}")
            return None
        
        print(f"✅ Audio extracted to: {temp_audio_path}")
        return temp_audio_path
    except Exception as e:
        print(f"❌ Exception during audio extraction: {str(e)}")
        return None

def analyze_audio(audio_path, min_silence_duration=500, silence_threshold=-40):
    """Analyze audio file to detect silent parts"""
    try:
        print(f"🔍 Analyzing audio for silence: {audio_path}")
        # Load audio using pydub
        audio = AudioSegment.from_file(audio_path)
        
        # Detect non-silent parts
        non_silent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_duration,
            silence_thresh=silence_threshold
        )
        
        print(f"📊 Found {len(non_silent_ranges)} non-silent segments")
        
        # Convert to silent ranges
        audio_duration_ms = len(audio)
        silent_ranges = []
        
        if len(non_silent_ranges) == 0:
            # If no non-silent parts detected, the whole audio is silence
            silent_ranges = [(0, audio_duration_ms)]
        else:
            # Add silent range at the beginning if the first non-silent part doesn't start at 0
            if non_silent_ranges[0][0] > 0:
                silent_ranges.append((0, non_silent_ranges[0][0]))
            
            # Add silent ranges between non-silent parts
            for i in range(len(non_silent_ranges) - 1):
                silent_ranges.append((non_silent_ranges[i][1], non_silent_ranges[i+1][0]))
            
            # Add silent range at the end if the last non-silent part doesn't end at the audio duration
            if non_silent_ranges[-1][1] < audio_duration_ms:
                silent_ranges.append((non_silent_ranges[-1][1], audio_duration_ms))
        
        # Filter out silent ranges shorter than the minimum duration
        silent_ranges = [(start, end) for start, end in silent_ranges if end - start >= min_silence_duration]
        
        print(f"🔇 Found {len(silent_ranges)} silent segments")
        
        # Get the audio waveform
        waveform = np.array(audio.get_array_of_samples())
        if audio.channels == 2:
            # Convert stereo to mono by averaging channels
            waveform = np.array(waveform).reshape((-1, 2)).mean(axis=1)
        
        return waveform, silent_ranges, audio_duration_ms
    except Exception as e:
        print(f"❌ Exception during audio analysis: {str(e)}")
        return None, [], 0

def visualize_waveform(waveform, silent_ranges, audio_duration_ms, output_path=None):
    """Visualize audio waveform with silent parts highlighted"""
    try:
        print("🎨 Creating waveform visualization...")
        # Downsample for better visualization
        if len(waveform) > 100000:
            step = len(waveform) // 100000
            waveform = waveform[::step]
        
        # Normalize
        if np.max(np.abs(waveform)) > 0:
            waveform = waveform / np.max(np.abs(waveform))
        
        # Create figure and plot
        plt.figure(figsize=(12, 6))
        
        # Plot waveform
        plt.plot(waveform, color='blue', alpha=0.7)
        
        # Highlight silent regions
        for start_ms, end_ms in silent_ranges:
            # Convert to sample positions (approximately)
            start_pos = int((start_ms / audio_duration_ms) * len(waveform))
            end_pos = int((end_ms / audio_duration_ms) * len(waveform))
            
            # Make sure we don't go out of bounds
            start_pos = max(0, min(start_pos, len(waveform)-1))
            end_pos = max(0, min(end_pos, len(waveform)-1))
            
            # Add a red background for silence
            plt.axvspan(start_pos, end_pos, color='red', alpha=0.3)
        
        plt.title('Audio Waveform with Silent Regions Highlighted')
        plt.xlabel('Sample')
        plt.ylabel('Amplitude')
        plt.grid(True, alpha=0.3)
        
        # Save or show the figure
        if output_path:
            plt.savefig(output_path)
            print(f"✅ Waveform visualization saved to: {output_path}")
        else:
            plt.show()
            
        return True
    except Exception as e:
        print(f"❌ Exception during visualization: {str(e)}")
        return False

def create_preview(video_path, start_sec, end_sec, ffmpeg_path, output_path=None):
    """Create a preview clip of a specific segment"""
    if not output_path:
        temp_preview = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        output_path = temp_preview.name
        temp_preview.close()
    
    try:
        print(f"🎬 Creating preview clip from {start_sec}s to {end_sec}s")
        # Use FFmpeg to extract the segment
        process = subprocess.run(
            [
                ffmpeg_path,
                "-ss", str(start_sec),  # Start time
                "-i", video_path,       # Input file
                "-t", str(end_sec - start_sec),  # Duration
                "-c:v", "libx264",      # Video codec
                "-c:a", "aac",          # Audio codec
                "-y",                   # Overwrite output
                output_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if process.returncode != 0:
            print(f"❌ Error creating preview: {process.stderr.decode()}")
            return None
        
        print(f"✅ Preview created at: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Exception during preview creation: {str(e)}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_ffmpeg.py <video_file>")
        sys.exit(1)
        
    video_path = sys.argv[1]
    if not os.path.isfile(video_path):
        print(f"❌ Video file not found: {video_path}")
        sys.exit(1)
    
    # Find FFmpeg
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        print("❌ FFmpeg not found. Please install FFmpeg and make sure it's in your PATH.")
        sys.exit(1)
    
    # Extract audio
    audio_path = extract_audio(video_path, ffmpeg_path)
    if not audio_path:
        print("❌ Failed to extract audio. Exiting.")
        sys.exit(1)
    
    # Analyze audio
    waveform, silent_ranges, audio_duration_ms = analyze_audio(audio_path)
    if waveform is None:
        print("❌ Failed to analyze audio. Exiting.")
        sys.exit(1)
    
    # Print detected silent ranges
    print("\n🔇 Detected Silent Segments:")
    for i, (start_ms, end_ms) in enumerate(silent_ranges):
        start_sec = start_ms / 1000
        end_sec = end_ms / 1000
        duration_sec = (end_ms - start_ms) / 1000
        print(f"  Silence {i+1}: {start_sec:.2f}s - {end_sec:.2f}s (Duration: {duration_sec:.2f}s)")
    
    # Visualize waveform
    waveform_path = os.path.splitext(video_path)[0] + "_waveform.png"
    visualize_waveform(waveform, silent_ranges, audio_duration_ms, waveform_path)
    
    # Create a preview of the first silent segment if any exist
    if silent_ranges:
        start_ms, end_ms = silent_ranges[0]
        start_sec = max(0, (start_ms / 1000) - 2)  # Start 2 seconds before silence
        end_sec = min((end_ms / 1000) + 2, audio_duration_ms / 1000)  # End 2 seconds after silence
        
        preview_path = os.path.splitext(video_path)[0] + "_preview.mp4"
        create_preview(video_path, start_sec, end_sec, ffmpeg_path, preview_path)
    
    print("\n✅ Debug analysis completed successfully!")
    print(f"🔍 Check {waveform_path} for the waveform visualization")
    if silent_ranges:
        print(f"🎬 Check {preview_path} for a preview of the first silent segment")
    
    # Clean up
    try:
        os.unlink(audio_path)
    except:
        pass

if __name__ == "__main__":
    main() 