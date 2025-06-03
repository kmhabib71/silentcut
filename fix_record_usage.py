#!/usr/bin/env python3
"""
Script to fix the record_usage section that still uses problematic file size calculation
"""

def fix_record_usage():
    print("🔧 Fixing record_usage section in process_video method...")
    
    # Read the current file
    with open('silence_cutter.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the problematic record usage calculation
    old_record_code = """        # Record usage after successful processing
        if API_COMMUNICATION_AVAILABLE and hasattr(self, 'video_path') and self.video_path:
            try:
                # Calculate actual processing time/duration
                if hasattr(self, 'video_player') and hasattr(self.video_player, 'duration_seconds'):
                    duration_minutes = self.video_player.duration_seconds / 60
                else:
                    # Fallback estimation
                    file_size_bytes = os.path.getsize(self.video_path)
                    duration_minutes = max(1, file_size_bytes / (1024 * 1024))
                
                api_client.record_usage(
                    file_path=self.video_path,
                    duration_minutes=duration_minutes,
                    processing_type='silence_removal'
                )
                print(f"✅ Usage recorded: {duration_minutes:.1f} minutes")
            except Exception as e:
                print(f"⚠️ Failed to record usage: {e}")"""
    
    new_record_code = """        # Record usage after successful processing
        if API_COMMUNICATION_AVAILABLE and hasattr(self, 'video_path') and self.video_path:
            try:
                # Calculate actual processing time/duration
                if hasattr(self, 'video_player') and hasattr(self.video_player, 'duration_seconds'):
                    duration_minutes = self.video_player.duration_seconds / 60
                    print(f"🎥 Recording usage with video player duration: {duration_minutes:.2f} minutes")
                else:
                    # Use the same improved duration calculation as validation
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
                            print(f"🔍 Recording usage with FFprobe duration: {duration_minutes:.2f} minutes")
                        else:
                            raise Exception("FFprobe failed")
                            
                    except Exception:
                        try:
                            # Method 2: Try MoviePy if available
                            from moviepy.editor import VideoFileClip, AudioFileClip
                            
                            if getattr(self, 'is_audio_only', False):
                                with AudioFileClip(self.video_path) as clip:
                                    duration_minutes = clip.duration / 60
                            else:
                                with VideoFileClip(self.video_path) as clip:
                                    duration_minutes = clip.duration / 60
                            print(f"🎬 Recording usage with MoviePy duration: {duration_minutes:.2f} minutes")
                            
                        except Exception:
                            # Method 3: Conservative estimate (last resort)
                            try:
                                file_size_bytes = os.path.getsize(self.video_path)
                                file_size_mb = file_size_bytes / (1024 * 1024)
                                duration_minutes = max(0.1, min(file_size_mb / 25, 10))  # Cap at 10 minutes for safety
                                print(f"⚠️ Recording usage with conservative file size estimation: {duration_minutes:.2f} minutes")
                            except Exception:
                                duration_minutes = 1  # Safe fallback
                                print(f"⚠️ Recording usage with fallback duration: {duration_minutes:.2f} minutes")
                
                api_client.record_usage(
                    file_path=self.video_path,
                    duration_minutes=duration_minutes,
                    processing_type='silence_removal'
                )
                print(f"✅ Usage recorded: {duration_minutes:.1f} minutes")
            except Exception as e:
                print(f"⚠️ Failed to record usage: {e}")"""
    
    if old_record_code in content:
        content = content.replace(old_record_code, new_record_code)
        print("✅ Found and replaced problematic record_usage calculation")
    else:
        print("❌ Could not find the exact record_usage code to replace")
        return False
    
    # Write back to file
    with open('silence_cutter.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Successfully fixed record_usage calculation")
    return True

if __name__ == "__main__":
    fix_record_usage() 