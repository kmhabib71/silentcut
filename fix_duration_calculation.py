#!/usr/bin/env python3
"""
Script to fix the duration calculation in process_video method
"""

def fix_duration_calculation():
    print("🔧 Fixing duration calculation in process_video method...")
    
    # Read the current file
    with open('silence_cutter.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the problematic duration calculation
    old_code = """                else:
                    # Fallback: Use file size estimation
                    try:
                        file_size_bytes = os.path.getsize(self.video_path)
                        duration_minutes = max(1, file_size_bytes / (1024 * 1024))
                        print(f"📊 Using file size estimation: {duration_minutes:.2f} minutes")
                    except Exception as e:
                        print(f"⚠️ Duration calculation failed: {e}")
                        duration_minutes = 1"""
    
    new_code = """                else:
                    # Try to get duration from file metadata using multiple methods
                    try:
                        # Method 1: Try FFprobe if available
                        import subprocess
                        result = subprocess.run([
                            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                            '-of', 'csv=p=0', self.video_path
                        ], capture_output=True, text=True, timeout=10)
                        
                        if result.returncode == 0 and result.stdout.strip():
                            duration_seconds = float(result.stdout.strip())
                            duration_minutes = duration_seconds / 60
                            print(f"🔍 Using FFprobe duration: {duration_minutes:.2f} minutes")
                        else:
                            raise Exception("FFprobe failed")
                            
                    except Exception as e:
                        try:
                            # Method 2: Try MoviePy if available
                            from moviepy.editor import VideoFileClip, AudioFileClip
                            
                            if getattr(self, 'is_audio_only', False):
                                with AudioFileClip(self.video_path) as clip:
                                    duration_minutes = clip.duration / 60
                            else:
                                with VideoFileClip(self.video_path) as clip:
                                    duration_minutes = clip.duration / 60
                            print(f"🎬 Using MoviePy duration: {duration_minutes:.2f} minutes")
                            
                        except Exception as e2:
                            # Method 3: Conservative estimate (last resort)
                            try:
                                file_size_bytes = os.path.getsize(self.video_path)
                                file_size_mb = file_size_bytes / (1024 * 1024)
                                
                                # More reasonable estimation: assume ~25MB per minute for video
                                # Use conservative estimate to avoid overcharging
                                duration_minutes = max(0.1, min(file_size_mb / 25, 10))  # Cap at 10 minutes for safety
                                print(f"⚠️ Using conservative file size estimation: {duration_minutes:.2f} minutes")
                            except Exception as e3:
                                print(f"⚠️ All duration calculation methods failed: {e3}")
                                duration_minutes = 1  # Safe fallback"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        print("✅ Found and replaced problematic duration calculation")
    else:
        print("❌ Could not find the exact duration calculation code to replace")
        return False
    
    # Write back to file
    with open('silence_cutter.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Successfully fixed duration calculation")
    return True

if __name__ == "__main__":
    fix_duration_calculation() 