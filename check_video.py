import os
import sys
import subprocess
import tempfile
import time
from moviepy.editor import VideoFileClip

def find_ffmpeg():
    """Try to find FFmpeg executable path"""
    # Check known locations
    known_locations = [
        "ffmpeg",  # System PATH
        "C:\\ffmpeg\\bin\\ffmpeg.exe",
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

def check_video_file(video_path, ffmpeg_path):
    """Validate if the video file can be opened and read properly by FFmpeg."""
    print(f"\n📊 Checking video file: {video_path}")
    
    # Check if file exists
    if not os.path.isfile(video_path):
        print(f"❌ Video file not found: {video_path}")
        return False
        
    # Check file size
    file_size = os.path.getsize(video_path)
    print(f"📁 File size: {file_size / (1024*1024):.2f} MB")
    
    # Try to get video info using FFmpeg
    print("\n📋 FFmpeg file analysis:")
    try:
        cmd = [
            ffmpeg_path, 
            "-i", video_path, 
            "-v", "error"
        ]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # FFmpeg outputs to stderr for this command
        stderr = process.stderr.decode('utf-8', errors='ignore')
        print(stderr)
        
        # More detailed analysis
        print("\n📋 Detailed stream information:")
        cmd = [
            ffmpeg_path,
            "-i", video_path,
            "-v", "info"
        ]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stderr = process.stderr.decode('utf-8', errors='ignore')
        for line in stderr.splitlines():
            if "Stream" in line or "Duration" in line:
                print(f"  {line.strip()}")
        
    except Exception as e:
        print(f"❌ Error analyzing video with FFmpeg: {str(e)}")
        return False
    
    # Try to read with MoviePy
    print("\n🎬 Attempting to load with MoviePy:")
    try:
        video = VideoFileClip(video_path, verbose=False)
        print(f"✅ Successfully loaded video with MoviePy")
        print(f"  Duration: {video.duration:.2f} seconds")
        print(f"  Resolution: {video.size[0]}x{video.size[1]}")
        print(f"  FPS: {video.fps}")
        video.close()
        return True
    except Exception as e:
        print(f"❌ Error loading with MoviePy: {str(e)}")
        
    # If we reach here, try an alternative method
    print("\n🔄 Attempting to create a clean copy with FFmpeg:")
    try:
        temp_video_path = os.path.join(tempfile.gettempdir(), f"temp_video_{int(time.time())}.mp4")
        
        cmd = [
            ffmpeg_path,
            "-i", video_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-y",
            temp_video_path
        ]
        print(f"  Running: {' '.join(cmd)}")
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if process.returncode != 0:
            stderr = process.stderr.decode('utf-8', errors='ignore')
            print(f"❌ Failed to create clean copy: {stderr}")
            return False
        
        print(f"✅ Clean copy created: {temp_video_path}")
        
        # Try to load the clean copy with MoviePy
        print("\n🎬 Attempting to load clean copy with MoviePy:")
        video = VideoFileClip(temp_video_path, verbose=False)
        print(f"✅ Successfully loaded clean copy with MoviePy")
        print(f"  Duration: {video.duration:.2f} seconds")
        print(f"  Resolution: {video.size[0]}x{video.size[1]}")
        print(f"  FPS: {video.fps}")
        video.close()
        
        print(f"\n✅ SUCCESS! Video file is valid. The clean copy at {temp_video_path} works with MoviePy.")
        print(f"   Please use this clean copy for your silence cutting operations.")
        return True
    except Exception as e:
        print(f"❌ Error processing clean copy: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_video.py <video_file>")
        sys.exit(1)
        
    video_path = sys.argv[1]
    
    # Find FFmpeg
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        print("❌ FFmpeg not found. Please install FFmpeg and make sure it's in your PATH.")
        print("   You can run reinstall_ffmpeg.bat to reinstall FFmpeg.")
        sys.exit(1)
    
    # Check the video file
    if check_video_file(video_path, ffmpeg_path):
        print("\n✅ Video file check completed.")
    else:
        print("\n❌ Video file check failed. Please try converting the video to a standard format using FFmpeg.")
        print("   Suggested command:")
        print(f"   ffmpeg -i \"{video_path}\" -c:v libx264 -c:a aac -pix_fmt yuv420p \"fixed_{os.path.basename(video_path)}\"")

if __name__ == "__main__":
    main() 