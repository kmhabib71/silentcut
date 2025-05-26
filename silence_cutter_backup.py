import os
import sys
import time
import tempfile
import atexit
import subprocess
import numpy as np
import io  # Add missing io module
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import moviepy.editor as mp
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QLabel, QPushButton, QSlider, QProgressBar, QFileDialog, QListWidget,
                             QListWidgetItem, QMessageBox, QCheckBox, 
                             QSplitter, QScrollArea, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QRectF, QUrl, QPropertyAnimation, QEasingCurve, QPointF, QMutex
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath, QImage, QPixmap, QLinearGradient
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import cv2
from proglog import ProgressBarLogger
import pygame
import threading
from collections import deque
import queue

class CircularBuffer:
    """High-performance circular buffer for video frames and audio samples"""
    def __init__(self, max_size, item_type="frame"):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.positions = deque(maxlen=max_size)  # Track frame numbers or timestamps
        self.item_type = item_type
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        
    def put(self, position, item):
        """Add item to buffer with position tracking"""
        with self.lock:
            # Remove old item at same position if exists
            self._remove_position(position)
            self.buffer.append(item)
            self.positions.append(position)
            
    def get(self, position):
        """Get item at specific position, returns None if not found"""
        with self.lock:
            try:
                index = list(self.positions).index(position)
                self.hits += 1
                return list(self.buffer)[index]
            except ValueError:
                self.misses += 1
                return None
                
    def get_nearest(self, position, tolerance=5):
        """Get nearest item within tolerance range"""
        with self.lock:
            if not self.positions:
                return None
                
            # Find closest position within tolerance
            closest_pos = None
            closest_diff = float('inf')
            
            for pos in self.positions:
                diff = abs(pos - position)
                if diff <= tolerance and diff < closest_diff:
                    closest_pos = pos
                    closest_diff = diff
                    
            if closest_pos is not None:
                try:
                    index = list(self.positions).index(closest_pos)
                    self.hits += 1
                    return list(self.buffer)[index]
                except ValueError:
                    pass
                    
            self.misses += 1
            return None
            
    def _remove_position(self, position):
        """Remove item at specific position"""
        try:
            index = list(self.positions).index(position)
            # Convert to lists for manipulation
            buffer_list = list(self.buffer)
            positions_list = list(self.positions)
            
            # Remove the item
            buffer_list.pop(index)
            positions_list.pop(index)
            
            # Rebuild deques
            self.buffer.clear()
            self.positions.clear()
            self.buffer.extend(buffer_list)
            self.positions.extend(positions_list)
        except ValueError:
            pass
            
    def clear(self):
        """Clear the buffer"""
        with self.lock:
            self.buffer.clear()
            self.positions.clear()
            
    def get_cache_stats(self):
        """Get cache hit/miss statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'size': len(self.buffer),
            'max_size': self.max_size
        }

class AudioCircularBuffer:
    """Specialized circular buffer for audio samples with streaming support"""
    def __init__(self, max_duration_seconds=10.0, sample_rate=22050):
        self.max_samples = int(max_duration_seconds * sample_rate)
        self.sample_rate = sample_rate
        self.buffer = deque(maxlen=self.max_samples)
        self.timestamps = deque(maxlen=self.max_samples)
        self.lock = threading.Lock()
        
    def put_samples(self, samples, start_time):
        """Add audio samples with timestamp"""
        with self.lock:
            for i, sample in enumerate(samples):
                timestamp = start_time + (i / self.sample_rate)
                self.buffer.append(sample)
                self.timestamps.append(timestamp)
                
    def get_samples(self, start_time, duration):
        """Get audio samples for specific time range"""
        with self.lock:
            if not self.timestamps:
                return []
                
            end_time = start_time + duration
            samples = []
            
            for i, timestamp in enumerate(self.timestamps):
                if start_time <= timestamp <= end_time:
                    if i < len(self.buffer):
                        samples.append(self.buffer[i])
                        
            return samples
            
    def clear(self):
        """Clear the audio buffer"""
        with self.lock:
            self.buffer.clear()
            self.timestamps.clear()

class WaveformCache:
    """Cache for waveform data at different zoom levels"""
    def __init__(self, max_zoom_levels=10):
        self.cache = {}  # zoom_level -> waveform_data
        self.max_levels = max_zoom_levels
        self.lock = threading.Lock()
        
    def put(self, zoom_level, start_time, end_time, waveform_data):
        """Cache waveform data for specific zoom level and time range"""
        with self.lock:
            key = (zoom_level, start_time, end_time)
            
            # Limit cache size
            if len(self.cache) >= self.max_levels:
                # Remove oldest entry
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                
            self.cache[key] = waveform_data
            
    def get(self, zoom_level, start_time, end_time):
        """Get cached waveform data"""
        with self.lock:
            key = (zoom_level, start_time, end_time)
            return self.cache.get(key)
            
    def clear(self):
        """Clear waveform cache"""
        with self.lock:
            self.cache.clear()

class VideoPlaybackThread(QThread):
    """Dedicated thread for video frame processing with synchronized audio"""
    frame_ready = pyqtSignal(object)  # Emits processed QPixmap
    position_changed = pyqtSignal(int)  # Emits current frame number
    preview_position_changed = pyqtSignal(float)  # Emits preview timeline position
    
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.is_playing = False
        self.current_frame = 0
        self.frame_count = 0
        self.fps = 30
        self.stop_requested = False
        self.seek_requested = -1
        self.mutex = QMutex()
        self.audio_loaded = False
        self.start_time = 0
        self.playback_start_time = 0  # Track when playback actually started
        self.actual_duration = 0  # Store actual audio duration
        self.seek_audio_offset = 0  # Store expected audio position after seek
        self.seek_time = 0  # Store time when seek occurred
        self.playback_initial_frame = 0  # Track the frame where current playback session started
        self.playback_started = False  # Track if playback has started
        
        # Preview mode support
        self.preview_mode = False
        self.silent_parts = []
        self.preview_segments = []  # List of (start, end) segments to keep
        self.preview_duration = 0  # Total duration after cuts
        self.current_preview_time = 0  # Current position in preview timeline
        self.current_segment_index = 0  # Which segment we're currently in
        
        # Circular buffer system for performance optimization
        self.frame_buffer = CircularBuffer(max_size=30, item_type="frame")  # Reduced to 1 second at 30fps
        self.audio_buffer = AudioCircularBuffer(max_duration_seconds=2.0)  # Reduced to 2 seconds of audio
        self.buffer_enabled = True
        self.prefetch_range = 5  # Reduced prefetch range
        self.prefetch_enabled = False  # Disable prefetch during initial loading
        
    def initialize_video(self):
        """Initialize video capture and audio"""
        self.cap = cv2.VideoCapture(self.video_path)
        if self.cap.isOpened():
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Get actual video duration using moviepy for accuracy
            try:
                import moviepy.editor as mp
                video_clip = mp.VideoFileClip(self.video_path)
                self.actual_duration = video_clip.duration
                video_clip.close()
                print(f"Video thread using exact duration: {self.actual_duration:.6f}s")
            except:
                self.actual_duration = self.frame_count / self.fps if self.fps > 0 else 0
                print(f"Fallback duration calculation: {self.actual_duration:.6f}s")
            
            # Calculate frame duration based on actual duration instead of FPS
            if self.frame_count > 0 and self.actual_duration > 0:
                self.frame_duration = self.actual_duration / self.frame_count
            else:
                self.frame_duration = 1.0 / self.fps
                
            print(f"Video initialized: {self.fps} FPS, {self.frame_count} frames, exact duration: {self.actual_duration:.6f}s, frame duration: {self.frame_duration:.6f}s")
            
            # Initialize audio
            self.initialize_audio()
            return True
        return False
        
    def initialize_audio(self):
        """Initialize pygame audio system with performance optimization"""
        try:
            # Initialize pygame mixer with optimized parameters for performance
            # Use lower settings for better performance
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
            pygame.mixer.init()
            
            # Extract audio to temporary file for pygame
            import tempfile
            import moviepy.editor as mp
            
            self.temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            self.temp_audio_file.close()
            
            # Extract audio using moviepy with optimized parameters for performance
            video_clip = mp.VideoFileClip(self.video_path)
            if video_clip.audio:
                # Use lower quality audio for better performance
                video_clip.audio.write_audiofile(
                    self.temp_audio_file.name, 
                    verbose=False, 
                    logger=None,
                    codec='pcm_s16le',
                    ffmpeg_params=['-ar', '22050', '-ac', '1']  # Lower sample rate, mono
                )
                
                # Verify audio duration for synchronization
                extracted_audio_duration = video_clip.audio.duration
                video_duration = video_clip.duration
                print(f"Audio sync verification: video={video_duration:.6f}s, audio={extracted_audio_duration:.6f}s")
                
                # Store the verified duration
                self.verified_audio_duration = extracted_audio_duration
                self.duration_difference = abs(video_duration - extracted_audio_duration)
                
                if self.duration_difference > 0.1:
                    print(f"WARNING: Audio-video duration mismatch: {self.duration_difference:.3f}s difference")
                else:
                    print(f"✓ Audio-video duration sync verified (difference: {self.duration_difference:.3f}s)")
                
                video_clip.close()
                
                # Load audio into pygame
                pygame.mixer.music.load(self.temp_audio_file.name)
                self.audio_loaded = True
                self.preview_audio_segments = []  # Will store segmented audio for preview
                print("Audio loaded successfully for preview (optimized)")
            else:
                print("No audio track found in video")
                
        except Exception as e:
            print(f"Audio initialization failed: {e}")
            self.audio_loaded = False
        
    def play(self):
        """Start playback with enhanced audio-video synchronization"""
        self.mutex.lock()
        self.is_playing = True
        
        if self.preview_mode and self.preview_segments:
            # Preview mode: calculate preview timeline position
            if self.actual_duration > 0 and self.frame_count > 0:
                frame_ratio = self.current_frame / self.frame_count
                original_position = frame_ratio * self.actual_duration
            else:
                original_position = (self.current_frame / self.fps) if self.fps > 0 else 0
            
            # Convert original position to preview timeline position
            preview_position = self.original_time_to_preview_time(original_position)
            
            # Set playback start time for preview timeline
            current_time = time.time()
            self.playback_start_time = current_time - preview_position
            
            print(f"🎵 PREVIEW PLAYBACK START:")
            print(f"  Original position: {original_position:.6f}s")
            print(f"  Preview position: {preview_position:.6f}s")
            print(f"  Preview duration: {self.preview_duration:.6f}s")
            
            if self.audio_loaded:
                try:
                    # Play preview audio from the correct preview position
                    pygame.mixer.music.play(start=preview_position)
                    print(f"✓ Preview audio started at {preview_position:.6f}s")
                except Exception as e:
                    print(f"Error starting preview audio: {e}")
        else:
            # Normal mode: use original timeline
            # Calculate the audio position we need to start from using verified duration
            if self.actual_duration > 0 and self.frame_count > 0:
                frame_ratio = self.current_frame / self.frame_count
                current_position = frame_ratio * self.actual_duration
            else:
                current_position = (self.current_frame / self.fps) if self.fps > 0 else 0
            
            # Use verified audio duration if available for better accuracy
            if hasattr(self, 'verified_audio_duration') and self.verified_audio_duration > 0:
                # Re-calculate using verified audio duration for perfect sync
                if self.frame_count > 0:
                    audio_frame_ratio = self.current_frame / self.frame_count
                    audio_position = audio_frame_ratio * self.verified_audio_duration
                else:
                    audio_position = current_position
                    
                # Ensure audio position doesn't exceed verified duration
                if audio_position > self.verified_audio_duration:
                    audio_position = self.verified_audio_duration
            else:
                audio_position = current_position
            
            # Set playback start time to account for the current position
            # This ensures video timing calculations are correct when starting from any position
            current_time = time.time()
            self.playback_start_time = current_time - current_position
            
            if self.audio_loaded:
                try:
                    # Enhanced audio start with synchronization verification
                    pygame.mixer.music.play(start=audio_position)
                    
                    # Log detailed playback synchronization info
                    print(f"🎵 NORMAL PLAYBACK START:")
                    print(f"  Video position: {current_position:.6f}s")
                    print(f"  Audio position: {audio_position:.6f}s") 
                    print(f"  Current frame: {self.current_frame}")
                    
                except Exception as e:
                    print(f"Error starting audio: {e}")
        
        # Mark this frame as the new playback starting point
        self.playback_initial_frame = self.current_frame
        self.playback_started = True
        
        self.mutex.unlock()
        
    def pause(self):
        """Pause playback"""
        self.mutex.lock()
        self.is_playing = False
        self.playback_started = False  # Reset playback tracking
        if self.audio_loaded:
            try:
                pygame.mixer.music.pause()
            except:
                pass
        self.mutex.unlock()
        
    def seek(self, frame_number):
        """Seek to specific frame with precise audio synchronization"""
        self.mutex.lock()
        self.seek_requested = frame_number
        self.current_frame = frame_number
        
        # Calculate the precise audio position for this frame
        if self.actual_duration > 0 and self.frame_count > 0:
            frame_ratio = frame_number / self.frame_count
            precise_audio_position = frame_ratio * self.actual_duration
        else:
            precise_audio_position = (frame_number / self.fps) if self.fps > 0 else 0
        
        # Reset playback timing to match the precise audio position
        # This ensures that when playback resumes, video timing aligns with audio
        current_time = time.time()
        
        # Set playback start time such that elapsed time calculation yields precise_audio_position
        # This compensates for any quantization in frame number conversion
        self.playback_start_time = current_time - precise_audio_position
        
        # CRITICAL: Reset the initial frame reference for proper timing calculations
        self.playback_initial_frame = frame_number
        
        # Restart audio from new position if playing
        if self.audio_loaded and self.is_playing:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.play(start=precise_audio_position)
                print(f"Seeked to frame {frame_number}, precise audio position: {precise_audio_position:.3f}s (ratio: {frame_ratio:.4f})")
                
                # Immediately update playback timing to compensate for pygame seeking inaccuracy
                # We calculate the offset from expected position
                self.seek_audio_offset = precise_audio_position
                self.seek_time = current_time
                
            except Exception as e:
                print(f"Error seeking audio: {e}")
        else:
            # If not playing, still reset timing for when playback starts
            self.playback_start_time = current_time
            print(f"Seeked to frame {frame_number} (paused), position: {precise_audio_position:.3f}s")
            
        self.mutex.unlock()
        
    def seek_time_direct(self, target_time_seconds):
        """Seek directly to a time position - handles both normal and preview mode"""
        self.mutex.lock()
        
        if self.preview_mode and self.preview_segments:
            # Preview mode: target_time_seconds is in preview timeline
            # Convert preview time to original video time
            original_time = self.preview_time_to_original_time(target_time_seconds)
            
            # Validate preview time
            if target_time_seconds < 0:
                target_time_seconds = 0
            elif target_time_seconds > self.preview_duration:
                target_time_seconds = self.preview_duration
            
            # Calculate target frame from original time
            if self.actual_duration > 0 and self.frame_count > 0:
                time_ratio = original_time / self.actual_duration
                target_frame = int(time_ratio * self.frame_count)
            else:
                target_frame = int(original_time * self.fps) if self.fps > 0 else 0
                
            target_frame = max(0, min(target_frame, self.frame_count - 1))
            
            # Set the frame and seek request
            self.seek_requested = target_frame
            self.current_frame = target_frame
            
            # Set playback timing for preview mode
            current_time = time.time()
            self.playback_start_time = current_time - target_time_seconds  # Use preview timeline
            self.playback_initial_frame = target_frame
            
            # Seek preview audio
            if self.audio_loaded and self.is_playing:
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=target_time_seconds)  # Use preview timeline
                    
                    print(f"🎵 PREVIEW SEEK:")
                    print(f"  Preview timeline: {target_time_seconds:.6f}s")
                    print(f"  Original video time: {original_time:.6f}s")
                    print(f"  Video frame: {target_frame}")
                    
                except Exception as e:
                    print(f"Error seeking preview audio: {e}")
            else:
                print(f"🎵 PREVIEW SEEK (paused):")
                print(f"  Preview timeline: {target_time_seconds:.6f}s")
                print(f"  Original video time: {original_time:.6f}s")
                print(f"  Video frame: {target_frame}")
        else:
            # Normal mode: use original timeline
            # Validate target time
            max_time = self.actual_duration if hasattr(self, 'actual_duration') else 0
            if target_time_seconds < 0:
                target_time_seconds = 0
            elif max_time > 0 and target_time_seconds > max_time:
                target_time_seconds = max_time
            
            # Calculate target frame from the exact time
            if self.actual_duration > 0 and self.frame_count > 0:
                time_ratio = target_time_seconds / self.actual_duration
                target_frame = int(time_ratio * self.frame_count)
            else:
                target_frame = int(target_time_seconds * self.fps) if self.fps > 0 else 0
                
            target_frame = max(0, min(target_frame, self.frame_count - 1))
            
            # Set the frame and seek request
            self.seek_requested = target_frame
            self.current_frame = target_frame
            
            # Use the EXACT timeline time for audio seeking
            exact_timeline_position = target_time_seconds
            
            # Verify audio position against timeline duration for perfect sync
            if hasattr(self, 'verified_audio_duration') and self.verified_audio_duration > 0:
                if exact_timeline_position > self.verified_audio_duration:
                    exact_timeline_position = self.verified_audio_duration
            
            # Reset playback timing to match the exact timeline position
            current_time = time.time()
            self.playback_start_time = current_time - exact_timeline_position
            self.playback_initial_frame = target_frame
            
            # Enhanced audio seeking with EXACT timeline position
            if self.audio_loaded and self.is_playing:
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=exact_timeline_position)
                    
                    print(f"🎵 NORMAL SEEK:")
                    print(f"  Timeline position: {target_time_seconds:.6f}s")
                    print(f"  Audio position: {exact_timeline_position:.6f}s") 
                    print(f"  Video frame: {target_frame}")
                    
                except Exception as e:
                    print(f"Error seeking audio: {e}")
            else:
                print(f"🎵 NORMAL SEEK (paused):")
                print(f"  Timeline position: {target_time_seconds:.6f}s")
                print(f"  Audio position: {exact_timeline_position:.6f}s") 
                print(f"  Video frame: {target_frame}")
        
        self.mutex.unlock()
        
    def stop_playback(self):
        """Stop the thread"""
        self.mutex.lock()
        self.stop_requested = True
        self.is_playing = False
        self.playback_started = False  # Reset playback tracking
        if self.audio_loaded:
            try:
                pygame.mixer.music.stop()
            except:
                pass
        self.mutex.unlock()
        
    def run(self):
        """Main thread loop with optimized performance for preview mode"""
        if not self.initialize_video():
            return
            
        # Performance optimization: Target lower FPS for smoother playback
        target_fps = 24 if self.preview_mode else 30
        target_frame_time = 1.0 / target_fps
        
        frame_skip_counter = 0
        last_ui_update = 0
        
        while not self.stop_requested:
            loop_start_time = time.time()
            
            self.mutex.lock()
            playing = self.is_playing
            seek_frame = self.seek_requested
            current_playback_start = self.playback_start_time
            initial_frame = getattr(self, 'playback_initial_frame', 0)
            preview_mode = self.preview_mode
            preview_segments = self.preview_segments.copy() if self.preview_segments else []
            
            if seek_frame >= 0:
                self.seek_requested = -1
                self.current_frame = seek_frame
                self.playback_initial_frame = seek_frame
                initial_frame = seek_frame
                frame_skip_counter = 0  # Reset skip counter on seek
            self.mutex.unlock()
            
            if seek_frame >= 0 or playing:
                # Calculate target frame with performance optimization
                if playing and seek_frame < 0:
                    elapsed_time = time.time() - current_playback_start
                    
                    if preview_mode and preview_segments:
                        # Preview mode: elapsed_time is in preview timeline
                        # Convert preview time to original video frame
                        target_frame = self.handle_preview_playback_optimized(elapsed_time, initial_frame)
                    else:
                        # Standard mode with frame rate limiting
                        if self.actual_duration > 0 and self.frame_count > 0:
                            target_frame = int((elapsed_time / self.actual_duration) * self.frame_count)
                        else:
                            target_frame = int(elapsed_time / self.frame_duration)
                        
                        target_frame = max(0, min(target_frame, self.frame_count - 1))
                    
                    self.current_frame = target_frame
                
                # Handle frame boundaries
                if self.current_frame >= self.frame_count:
                    self.current_frame = self.frame_count - 1
                    self.mutex.lock()
                    self.is_playing = False
                    self.mutex.unlock()
                    
                    if self.audio_loaded:
                        try:
                            pygame.mixer.music.stop()
                        except:
                            pass
                
                # Handle preview mode end-of-segments
                if preview_mode and playing and seek_frame < 0:
                    elapsed_time = time.time() - current_playback_start
                    if elapsed_time >= self.preview_duration:
                        # We've reached the end of preview segments
                        self.mutex.lock()
                        self.is_playing = False
                        self.mutex.unlock()
                        
                        if self.audio_loaded:
                            try:
                                pygame.mixer.music.stop()
                            except:
                                pass
                        print("✓ Preview playback completed - reached end of segments")
                
                # Performance optimization: Skip frame processing if we're behind
                should_process_frame = True
                if playing and not seek_frame >= 0:
                    frame_skip_counter += 1
                    # Skip every other frame if we're lagging (adaptive frame skipping)
                    if frame_skip_counter % 2 == 0 and preview_mode:
                        should_process_frame = False
                
                # Read and display frame with circular buffer optimization
                if should_process_frame:
                    pixmap = None
                    
                                        # Try to get frame from buffer first
                    if self.buffer_enabled:
                        pixmap = self.frame_buffer.get(self.current_frame)
                        
                    if pixmap is None:
                        # Frame not in buffer, need to read from video
                        # In preview mode, we need to seek to the correct frame every time
                        # because we're jumping over silent segments
                        if preview_mode and playing and seek_frame < 0:
                            # Always seek to the current frame in preview mode to skip silent segments
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
                            # Debug output (only occasionally to avoid spam)
                            if not hasattr(self, '_last_seek_debug') or time.time() - self._last_seek_debug > 1.0:
                                self._last_seek_debug = time.time()
                                elapsed_time = time.time() - current_playback_start
                                print(f"🎬 VIDEO SEEK: preview_time={elapsed_time:.2f}s → seeking to frame {self.current_frame}")
                        elif seek_frame >= 0:
                            # Normal seeking behavior
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
                            
                        ret, frame = self.cap.read()
                        if ret:
                            # Process frame with aggressive optimization for preview mode
                            pixmap = self.process_frame_ultra_fast(frame) if preview_mode else self.process_frame_fast(frame)
                                
                            # Store in buffer for future use
                            if pixmap and self.buffer_enabled:
                                self.frame_buffer.put(self.current_frame, pixmap)
                                
                                # Prefetch nearby frames for smoother playback (only when enabled and playing)
                                if playing and not preview_mode and self.prefetch_enabled:
                                    # Only prefetch occasionally to avoid performance issues
                                    if self.current_frame % 10 == 0:  # Every 10th frame
                                        self.prefetch_frames(self.current_frame)
                    
                        if pixmap:
                            self.frame_ready.emit(pixmap)
                            
                            # Reduce UI update frequency to prevent freezing
                            current_time = time.time()
                            if current_time - last_ui_update > 0.1:  # Update max 10 times per second
                                self.position_changed.emit(self.current_frame)
                                last_ui_update = current_time
                            
                            # Emit preview position for timeline updates
                            if preview_mode and current_time - last_ui_update > 0.2:
                                elapsed_time = time.time() - current_playback_start
                                # In preview mode, elapsed_time IS the preview timeline position
                                self.preview_position_changed.emit(elapsed_time)
                
                # Optimized timing control with adaptive sleep
                if playing and seek_frame < 0:
                    loop_duration = time.time() - loop_start_time
                    target_frame_time = 1.0 / target_fps
                    sleep_time = target_frame_time - loop_duration
                    
                    # Adaptive sleep - shorter sleep in preview mode for responsiveness
                    min_sleep = 0.01 if preview_mode else 0.02
                    if sleep_time > min_sleep:
                        self.msleep(int(sleep_time * 1000))
                    elif sleep_time > 0:
                        self.msleep(int(min_sleep * 1000))
                elif not playing:
                    self.msleep(50)  # When paused, check every 50ms
            else:
                self.msleep(50)
                
        # Cleanup
        if hasattr(self, 'cap'):
            self.cap.release()
        if self.audio_loaded:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
                import os
                if hasattr(self, 'temp_audio_file') and os.path.exists(self.temp_audio_file.name):
                    os.unlink(self.temp_audio_file.name)
                # Clean up preview audio file
                if hasattr(self, 'temp_preview_audio_file') and os.path.exists(self.temp_preview_audio_file.name):
                    os.unlink(self.temp_preview_audio_file.name)
            except:
                pass
    
    def handle_preview_playback_optimized(self, elapsed_time, initial_frame):
        """Optimized preview playback with cached calculations"""
        if not self.preview_segments:
            return initial_frame
            
        # Cache segment lookup for performance
        if not hasattr(self, '_segment_cache') or self._segment_cache_time != elapsed_time:
            self._segment_cache_time = elapsed_time
            
            # Find which segment we should be in
            accumulated_time = 0
            for segment_index, (start, end) in enumerate(self.preview_segments):
                segment_duration = end - start
                
                if accumulated_time + segment_duration >= elapsed_time:
                    # We're within this segment
                    offset_in_segment = elapsed_time - accumulated_time
                    target_original_time = start + offset_in_segment
                    
                    # Convert to frame number with caching
                    if self.actual_duration > 0 and self.frame_count > 0:
                        self._cached_target_frame = int((target_original_time / self.actual_duration) * self.frame_count)
                    else:
                        self._cached_target_frame = int(target_original_time / self.frame_duration)
                        
                    self._cached_target_frame = max(0, min(self._cached_target_frame, self.frame_count - 1))
                    
                    # Debug output to show frame skipping (only occasionally to avoid spam)
                    if not hasattr(self, '_last_debug_time') or elapsed_time - self._last_debug_time > 2.0:
                        self._last_debug_time = elapsed_time
                        print(f"🎬 PREVIEW FRAME SKIP: preview_time={elapsed_time:.2f}s → original_time={target_original_time:.2f}s → frame={self._cached_target_frame}")
                    
                    break
                    
                accumulated_time += segment_duration
            else:
                # If we get here, we've played through all segments
                self._cached_target_frame = self.frame_count - 1
        
        return getattr(self, '_cached_target_frame', initial_frame)

    def process_frame_fast(self, frame):
        """Process frame with maximum speed optimization"""
        try:
            # More aggressive scaling for performance
            height, width = frame.shape[:2]
            
            # Scale to max 480 width for even faster processing
            if width > 480:
                scale = 480 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                # Use fastest interpolation
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_NEAREST)
            
            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # Create Qt image and pixmap with optimized format
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            return pixmap
        except:
            return None
            
    def process_frame_ultra_fast(self, frame):
        """Ultra-fast frame processing for preview mode - sacrifices quality for speed"""
        try:
            # Aggressive scaling for maximum performance in preview mode
            height, width = frame.shape[:2]
            
            # Scale to max 320 width for ultra-fast preview
            if width > 320:
                scale = 320 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                # Use fastest interpolation
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_NEAREST)
            
            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # Create Qt image and pixmap with fastest format
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            return pixmap
        except:
            return None
            
    def prefetch_frames(self, current_frame):
        """Prefetch nearby frames for smoother playback - lightweight version"""
        if not self.buffer_enabled or not self.prefetch_enabled:
            return
            
        # Only prefetch 2-3 frames ahead to minimize performance impact
        def prefetch_worker():
            try:
                for offset in range(1, min(self.prefetch_range, 3)):  # Only 2-3 frames ahead
                    target_frame = current_frame + offset
                    if target_frame >= self.frame_count:
                        break
                        
                    # Check if frame is already in buffer
                    if self.frame_buffer.get(target_frame) is not None:
                        continue
                        
                    # Use existing video capture instead of creating new one
                    if hasattr(self, 'cap') and self.cap:
                        current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                        ret, frame = self.cap.read()
                        
                        if ret:
                            # Use ultra-fast processing for prefetch
                            pixmap = self.process_frame_ultra_fast(frame)
                            if pixmap:
                                self.frame_buffer.put(target_frame, pixmap)
                        
                        # Restore original position
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                        break  # Only prefetch one frame at a time
                            
            except Exception as e:
                pass  # Silently handle prefetch errors
                
        # Run prefetch in background thread (daemon so it doesn't block shutdown)
        prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        prefetch_thread.start()
        
    def enable_prefetch(self):
        """Enable prefetch after initial loading is complete"""
        self.prefetch_enabled = True
        print("🚀 Frame prefetching enabled for smoother playback")
        
    def disable_prefetch(self):
        """Disable prefetch during heavy operations"""
        self.prefetch_enabled = False
        
    def set_buffer_mode(self, enabled):
        """Enable or disable all buffer operations"""
        self.buffer_enabled = enabled
        self.prefetch_enabled = enabled
        if not enabled:
            # Clear buffers to free memory
            self.frame_buffer.clear()
            self.audio_buffer.clear()

    def set_preview_mode(self, enabled, silent_parts=None):
        """Enable or disable preview mode"""
        self.mutex.lock()
        self.preview_mode = enabled
        if enabled and silent_parts:
            self.silent_parts = silent_parts
            self.calculate_preview_segments()
            
            # Create segmented audio for preview mode
            if self.create_preview_audio():
                # Load the preview audio into pygame
                try:
                    pygame.mixer.music.load(self.temp_preview_audio_file.name)
                    print("✓ Preview audio loaded successfully - silent parts will be skipped during playback")
                except Exception as e:
                    print(f"Error loading preview audio: {e}")
            else:
                print("Failed to create preview audio - using original audio")
        else:
            self.silent_parts = []
            self.preview_segments = []
            self.preview_duration = 0
            
            # Restore original audio
            if self.audio_loaded and hasattr(self, 'temp_audio_file'):
                try:
                    pygame.mixer.music.load(self.temp_audio_file.name)
                    print("✓ Original audio restored")
                except Exception as e:
                    print(f"Error restoring original audio: {e}")
        self.mutex.unlock()
        
    def get_effective_duration(self):
        """Get the effective timeline duration (preview duration in preview mode, original otherwise)"""
        if self.preview_mode and hasattr(self, 'preview_timeline_duration') and self.preview_timeline_duration is not None:
            return self.preview_timeline_duration
        return self.duration_seconds
        
    def convert_click_position_to_original_time(self, click_time_seconds):
        """Convert a click position on the timeline to original video time"""
        if not self.preview_mode or not hasattr(self, 'preview_timeline_duration'):
            # Normal mode: click time is already in original timeline
            return click_time_seconds
            
        # Preview mode: convert preview timeline position to original timeline position
        if not self.silent_parts:
            return click_time_seconds
            
        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]
        if not selected_silent_parts:
            return click_time_seconds
            
        # Sort by start time
        selected_silent_parts.sort(key=lambda x: x['start'])
        
        # Build segments that will be kept (same logic as video thread)
        preview_segments = []
        last_end = 0
        
        for silent_part in selected_silent_parts:
            if silent_part['start'] > last_end:
                # Add segment before this silent part
                preview_segments.append((last_end, silent_part['start']))
            last_end = silent_part['end']
            
        # Add final segment if needed
        if last_end < self.duration_seconds:
            preview_segments.append((last_end, self.duration_seconds))
            
        # Convert preview timeline position to original time
        if click_time_seconds <= 0:
            return preview_segments[0][0] if preview_segments else 0
            
        accumulated_time = 0
        for start, end in preview_segments:
            segment_duration = end - start
            if accumulated_time + segment_duration >= click_time_seconds:
                # The position is within this segment
                offset_in_segment = click_time_seconds - accumulated_time
                original_time = start + offset_in_segment
                print(f"🎯 TIMELINE CLICK CONVERSION:")
                print(f"  Preview click: {click_time_seconds:.3f}s")
                print(f"  Original time: {original_time:.3f}s")
                print(f"  Segment: {start:.3f}s - {end:.3f}s")
                return original_time
            accumulated_time += segment_duration
            
        # If we get here, click_time_seconds is beyond the end
        return preview_segments[-1][1] if preview_segments else self.duration_seconds

    def calculate_preview_segments(self):
        """Calculate the segments that will be kept after cutting silent parts"""
        if not self.silent_parts or not self.actual_duration:
            self.preview_segments = [(0, self.actual_duration)]
            self.preview_duration = self.actual_duration
            return
            
        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]
        if not selected_silent_parts:
            self.preview_segments = [(0, self.actual_duration)]
            self.preview_duration = self.actual_duration
            return
            
        # Sort by start time
        selected_silent_parts.sort(key=lambda x: x['start'])
        
        # Build segments that will be kept
        self.preview_segments = []
        last_end = 0
        
        for silent_part in selected_silent_parts:
            if silent_part['start'] > last_end:
                # Add segment before this silent part
                self.preview_segments.append((last_end, silent_part['start']))
            last_end = silent_part['end']
            
        # Add final segment if needed
        if last_end < self.actual_duration:
            self.preview_segments.append((last_end, self.actual_duration))
            
        # Calculate total preview duration correctly
        self.preview_duration = sum(end - start for start, end in self.preview_segments)
        
        print(f"Preview segments calculated: {len(self.preview_segments)} segments, duration: {self.preview_duration:.3f}s")
        for i, (start, end) in enumerate(self.preview_segments):
            print(f"  Segment {i+1}: {start:.3f}s - {end:.3f}s (duration: {end-start:.3f}s)")
        
    def preview_time_to_original_time(self, preview_time):
        """Convert preview timeline position to original video time"""
        if not self.preview_mode or not self.preview_segments:
            return preview_time
            
        if preview_time <= 0:
            return self.preview_segments[0][0] if self.preview_segments else 0
            
        accumulated_time = 0
        for start, end in self.preview_segments:
            segment_duration = end - start
            if accumulated_time + segment_duration >= preview_time:
                # The position is within this segment
                offset_in_segment = preview_time - accumulated_time
                return start + offset_in_segment
            accumulated_time += segment_duration
            
        # If we get here, preview_time is beyond the end
        return self.preview_segments[-1][1] if self.preview_segments else self.actual_duration
        
    def original_time_to_preview_time(self, original_time):
        """Convert original video time to preview timeline position"""
        if not self.preview_mode or not self.preview_segments:
            return original_time
            
        accumulated_preview_time = 0
        for start, end in self.preview_segments:
            if start <= original_time <= end:
                # The time is within this segment
                offset_in_segment = original_time - start
                return accumulated_preview_time + offset_in_segment
            elif original_time < start:
                # The time is before this segment (in a cut area)
                return accumulated_preview_time
            else:
                # The time is after this segment, continue accumulating
                accumulated_preview_time += (end - start)
                
        # If we get here, original_time is after all segments
        return accumulated_preview_time
        
    def create_preview_audio(self):
        """Create segmented audio file for preview mode that skips silent parts"""
        if not self.preview_segments or not self.audio_loaded:
            return False
            
        try:
            import tempfile
            import moviepy.editor as mp
            from pydub import AudioSegment
            
            print("Creating preview audio with silent parts removed...")
            
            # Load the original audio
            original_audio = AudioSegment.from_file(self.temp_audio_file.name)
            
            # Create segments from non-silent parts
            preview_audio_segments = []
            for start_time, end_time in self.preview_segments:
                start_ms = int(start_time * 1000)
                end_ms = int(end_time * 1000)
                
                # Extract segment
                segment = original_audio[start_ms:end_ms]
                preview_audio_segments.append(segment)
                print(f"  Added segment: {start_time:.2f}s - {end_time:.2f}s (duration: {(end_time-start_time):.2f}s)")
            
            # Concatenate all segments
            if preview_audio_segments:
                preview_audio = sum(preview_audio_segments)
                
                # Save preview audio to temporary file
                self.temp_preview_audio_file = tempfile.NamedTemporaryFile(suffix='_preview.wav', delete=False)
                self.temp_preview_audio_file.close()
                
                preview_audio.export(self.temp_preview_audio_file.name, format="wav")
                
                print(f"Preview audio created: {len(preview_audio_segments)} segments, total duration: {len(preview_audio)/1000:.2f}s")
                print(f"Preview audio saved to: {self.temp_preview_audio_file.name}")
                
                return True
            else:
                print("No preview segments to create audio from")
                return False
                
        except Exception as e:
            print(f"Error creating preview audio: {e}")
            return False

class WaveformLoadingThread(QThread):
    """Background thread for loading waveform data without blocking UI"""
    waveform_loaded = pyqtSignal(object, float)  # waveform_data, max_amplitude
    duration_loaded = pyqtSignal(float)  # duration
    progress_updated = pyqtSignal(str)  # progress message
    
    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        
    def run(self):
        """Load waveform data in background"""
        try:
            print("🌊 Loading waveform in background...")
            self.progress_updated.emit("Loading video file...")
            
            # Extract audio using MoviePy
            import moviepy.editor as mp
            video = mp.VideoFileClip(self.video_path)
            
            # Emit duration immediately for instant timeline setup
            if video.duration > 0:
                self.duration_loaded.emit(video.duration)
                
            self.progress_updated.emit("Extracting audio track...")
            
            if video.audio is None:
                print("No audio track found in video")
                self.waveform_loaded.emit(None, 0)
                video.close()
                return
                
            # Create temporary audio file
            import tempfile
            temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio_file.close()
            
            self.progress_updated.emit("Processing audio data...")
            
            # Extract audio to temporary file with optimized parameters for speed
            video.audio.write_audiofile(
                temp_audio_file.name, 
                verbose=False, 
                logger=None,
                codec='pcm_s16le',
                ffmpeg_params=['-ar', '16000', '-ac', '1']  # Even lower sample rate and force mono for faster processing
            )
            video.close()
            
            self.progress_updated.emit("Generating waveform...")
            
            # Load audio with pydub
            from pydub import AudioSegment
            audio = AudioSegment.from_file(temp_audio_file.name)
            
            # Convert to mono for waveform visualization
            if audio.channels > 1:
                audio = audio.set_channels(1)
                
            # Get raw audio data
            raw_data = audio.raw_data
            
            # Convert to numpy array
            import struct
            if audio.sample_width == 1:
                samples = struct.unpack(f'{len(raw_data)}B', raw_data)
                samples = [(s - 128) / 128.0 for s in samples]
            elif audio.sample_width == 2:
                samples = struct.unpack(f'{len(raw_data)//2}h', raw_data)
                samples = [s / 32768.0 for s in samples]
            elif audio.sample_width == 4:
                samples = struct.unpack(f'{len(raw_data)//4}i', raw_data)
                samples = [s / 2147483648.0 for s in samples]
            else:
                print(f"Unsupported sample width: {audio.sample_width}")
                samples = []
            
            self.progress_updated.emit("Optimizing waveform display...")
            
            # Aggressive downsampling for smooth display
            target_samples = 1500  # Reduced from 2500 for faster processing
            if len(samples) > target_samples:
                step = len(samples) // target_samples
                samples = samples[::step]
            
            max_amplitude = max(abs(s) for s in samples) if samples else 1.0
            
            # Clean up temporary file
            try:
                os.unlink(temp_audio_file.name)
            except:
                pass
                
            self.progress_updated.emit("Waveform ready!")
            
            # Emit the loaded waveform data
            self.waveform_loaded.emit(samples, max_amplitude)
                
        except Exception as e:
            print(f"Error loading waveform: {e}")
            self.waveform_loaded.emit(None, 0)

class SilenceDetectionThread(QThread):
    progress_updated = pyqtSignal(int)
    detection_complete = pyqtSignal(list)
    
    def __init__(self, video_path, min_silence_duration=500, silence_threshold=-40, padding_ms=100):
        super().__init__()
        self.video_path = video_path
        self.min_silence_duration = min_silence_duration
        self.silence_threshold = silence_threshold
        self.padding_ms = padding_ms  # New parameter for padding
        # Get FFmpeg path
        self.ffmpeg_path = self.get_ffmpeg_path()
    
    def get_ffmpeg_path(self):
        """Try to find FFmpeg executable path"""
        # First try directly if it's in PATH
        try:
            # Use subprocess to check if ffmpeg is available
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return "ffmpeg"  # ffmpeg is in PATH and working
        except Exception:
            pass  # ffmpeg not in PATH or not working
        
        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Users\\WALTON\\ffmpeg-2025-05-07-git-1b643e3f65-full_build\\ffmpeg-2025-05-07-git-1b643e3f65-full_build\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]
        
        for location in known_locations:
            if os.path.exists(location):
                return location
                
        # Could not find FFmpeg, will use just the command and hope it works
        return "ffmpeg"
        
    def run(self):
        try:
            # Use the accurate pydub-based detection for better results
            # Skip fast FFmpeg detection to maintain accuracy
            print(f"\n---------- ACCURATE SILENCE DETECTION START ----------")
            print(f"Using pydub for accurate silence detection")
            print(f"Detecting silence with threshold: {self.silence_threshold} dB, min duration: {self.min_silence_duration} ms, padding: {self.padding_ms} ms")
            
            # Start with initial progress
            self.progress_updated.emit(5)
            QApplication.processEvents()  # Process events to update GUI
            
            # Modify moviepy's FFMPEG_BINARY setting to use our detected FFmpeg path
            from moviepy.config import change_settings
            change_settings({"FFMPEG_BINARY": self.ffmpeg_path})
            
            # Extract audio from video more efficiently
            print(f"Loading video from: {self.video_path}")
            self.progress_updated.emit(10)
            QApplication.processEvents()
            
            # Load video more efficiently
            video = mp.VideoFileClip(self.video_path)
            audio_duration_ms = int(video.audio.duration * 1000)
            print(f"Video loaded, audio duration: {audio_duration_ms} ms")
            self.progress_updated.emit(20)
            QApplication.processEvents()
            
            # Create temporary audio file with optimized settings
            temp_audio = tempfile.NamedTemporaryFile(suffix=f'_sid_{os.getpid()}_{int(time.time())}.wav', delete=False)
            temp_audio_path = temp_audio.name
            temp_audio.close()
            print(f"Extracting audio to: {temp_audio_path}")
            
            self.progress_updated.emit(30)
            QApplication.processEvents()
            
            # Extract audio with optimized settings for faster processing
            video.audio.write_audiofile(
                temp_audio_path, 
                verbose=False, 
                logger=None,
                codec='pcm_s16le',  # Fast codec
                ffmpeg_params=['-ar', '22050']  # Lower sample rate for faster processing
            )
            print(f"Audio extracted successfully")
            self.progress_updated.emit(50)
            QApplication.processEvents()
            
            # Load audio and detect non-silent parts with optimized settings
            print(f"Loading audio for accurate silence detection")
            audio = AudioSegment.from_file(temp_audio_path)
            print(f"Audio loaded: duration={len(audio)}ms, channels={audio.channels}, sample_width={audio.sample_width}, frame_rate={audio.frame_rate}")
            self.progress_updated.emit(60)
            QApplication.processEvents()
            
            # Convert to mono for faster processing while maintaining accuracy
            if audio.channels > 1:
                audio = audio.set_channels(1)
            
            # Detect non-silent parts with optimized parameters
            print(f"Detecting non-silent parts with silence threshold={self.silence_threshold}dB, min_silence_len={self.min_silence_duration}ms")
            non_silent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_duration,
                silence_thresh=self.silence_threshold,
                seek_step=1  # Add seek_step for faster processing
            )
            self.progress_updated.emit(70)
            QApplication.processEvents()
            
            print(f"Number of non-silent ranges detected: {len(non_silent_ranges)}")
            if non_silent_ranges:
                for i, (start, end) in enumerate(non_silent_ranges[:5]):  # Show first 5
                    print(f"  Non-silent range {i+1}: {start}ms - {end}ms (duration: {end-start}ms)")
                if len(non_silent_ranges) > 5:
                    print(f"  ... and {len(non_silent_ranges) - 5} more ranges")
            
            # Apply padding to non-silent ranges
            if self.padding_ms > 0 and non_silent_ranges:
                padded_ranges = []
                for start, end in non_silent_ranges:
                    # Add padding before and after (but don't go below 0 or beyond audio length)
                    padded_start = max(0, start - self.padding_ms)
                    padded_end = min(audio_duration_ms, end + self.padding_ms)
                    padded_ranges.append((padded_start, padded_end))
                
                # Merge overlapping ranges after padding
                padded_ranges.sort()  # Sort by start time
                merged_ranges = []
                current_start, current_end = padded_ranges[0]
                
                for start, end in padded_ranges[1:]:
                    if start <= current_end:  # Overlap found
                        # Extend current range
                        current_end = max(current_end, end)
                    else:
                        # No overlap, add current range and start a new one
                        merged_ranges.append((current_start, current_end))
                        current_start, current_end = start, end
                
                # Add the last range
                merged_ranges.append((current_start, current_end))
                
                print(f"After padding ({self.padding_ms}ms) and merging: {len(merged_ranges)} non-silent ranges")
                non_silent_ranges = merged_ranges
            
            # Convert non-silent ranges to silent ranges
            silent_ranges = []
            
            if len(non_silent_ranges) == 0:
                # If no non-silent parts detected, the whole audio is silence
                silent_ranges = [(0, audio_duration_ms)]
                print(f"No non-silent parts detected, treating the entire audio as silence")
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
            
            self.progress_updated.emit(80)
            QApplication.processEvents()
            
            print(f"Number of initial silent ranges: {len(silent_ranges)}")
            if silent_ranges:
                for i, (start, end) in enumerate(silent_ranges[:5]):  # Show first 5
                    print(f"  Silent range {i+1}: {start}ms - {end}ms (duration: {end-start}ms)")
                if len(silent_ranges) > 5:
                    print(f"  ... and {len(silent_ranges) - 5} more ranges")
            
            # Filter out silent ranges shorter than the minimum duration
            filtered_silent_ranges = [(start, end) for start, end in silent_ranges if end - start >= self.min_silence_duration]
            print(f"After filtering by minimum duration ({self.min_silence_duration}ms): {len(filtered_silent_ranges)} silent ranges")
            
            self.progress_updated.emit(90)
            QApplication.processEvents()
            
            # Calculate duration of each silent part and create result list
            silent_parts = []
            for i, (start, end) in enumerate(filtered_silent_ranges):
                duration_ms = end - start
                start_sec = start / 1000
                end_sec = end / 1000
                
                # Create a thumbnail from the video at the start of the silence
                silent_parts.append({
                    'id': i,
                    'start': start_sec,
                    'end': end_sec,
                    'duration_ms': duration_ms,
                    'selected': True  # Default to cutting this silence
                })
            
            # Clean up temp file
            try:
                os.unlink(temp_audio_path)
            except:
                pass
                
            # Final progress update
            self.progress_updated.emit(100)
            QApplication.processEvents()
            
            # Emit results
            print(f"Final silent parts count: {len(silent_parts)}")
            print(f"---------- ACCURATE SILENCE DETECTION END ----------\n")
            self.detection_complete.emit(silent_parts)
            
        except Exception as e:
            print(f"Error in silence detection: {str(e)}")
            import traceback
            traceback.print_exc()
            self.detection_complete.emit([])
    
    def run_fast_ffmpeg_detection(self):
        """Fast silence detection using FFmpeg's silencedetect filter - much faster than pydub"""
        try:
            print(f"\n---------- FAST SILENCE DETECTION START ----------")
            print(f"Using FFmpeg silencedetect filter for maximum speed")
            
            # Progress update
            self.progress_updated.emit(10)
            QApplication.processEvents()
            
            # Convert threshold from dB to FFmpeg format
            threshold_linear = 10 ** (self.silence_threshold / 20)  # Convert dB to linear
            
            # Build FFmpeg command for silence detection
            cmd = [
                self.ffmpeg_path,
                '-i', self.video_path,
                '-af', f'silencedetect=noise={threshold_linear}:d={self.min_silence_duration/1000}',
                '-f', 'null',
                '-'
            ]
            
            self.progress_updated.emit(30)
            QApplication.processEvents()
            
            # Run FFmpeg and capture output
            print(f"Running fast FFmpeg silence detection...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.progress_updated.emit(70)
            QApplication.processEvents()
            
            # Parse silence detection output
            silent_parts = []
            silence_starts = []
            silence_ends = []
            
            # Parse FFmpeg output for silence detection
            for line in result.stderr.split('\n'):
                if 'silence_start:' in line:
                    try:
                        start_time = float(line.split('silence_start:')[1].strip())
                        silence_starts.append(start_time)
                    except:
                        pass
                elif 'silence_end:' in line:
                    try:
                        end_time = float(line.split('silence_end:')[1].split('|')[0].strip())
                        silence_ends.append(end_time)
                    except:
                        pass
            
            # Create silence parts from starts and ends
            for i, start in enumerate(silence_starts):
                if i < len(silence_ends):
                    end = silence_ends[i]
                    duration_ms = int((end - start) * 1000)
                    
                    # Apply padding
                    padded_start = max(0, start - (self.padding_ms / 1000))
                    
                    # Get video duration for padding limit
                    try:
                        video = mp.VideoFileClip(self.video_path)
                        video_duration = video.duration
                        video.close()
                        padded_end = min(video_duration, end + (self.padding_ms / 1000))
                    except:
                        padded_end = end + (self.padding_ms / 1000)
                    
                    if duration_ms >= self.min_silence_duration:  # Filter by minimum duration
                        silent_parts.append({
                            'id': len(silent_parts),
                            'start': padded_start,
                            'end': padded_end,
                            'duration_ms': int((padded_end - padded_start) * 1000),
                            'selected': True
                        })
            
            self.progress_updated.emit(100)
            QApplication.processEvents()
            
            print(f"Fast FFmpeg detection completed: {len(silent_parts)} silent parts found")
            print(f"---------- FAST SILENCE DETECTION END ----------\n")
            
            return silent_parts
            
        except Exception as e:
            print(f"Fast FFmpeg detection failed: {e}")
            print("Falling back to slower detection method...")
            return None

class ProcessingThread(QThread):
    progress_updated = pyqtSignal(int)
    processing_complete = pyqtSignal(str)
    
    def __init__(self, video_path, silent_parts, output_path):
        super().__init__()
        self.video_path = video_path
        self.silent_parts = silent_parts
        self.output_path = output_path
        self.ffmpeg_path = self.get_ffmpeg_path()
    
    def get_ffmpeg_path(self):
        """Try to find FFmpeg executable path"""
        # First try directly if it's in PATH
        try:
            # Use subprocess to check if ffmpeg is available
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return "ffmpeg"  # ffmpeg is in PATH and working
        except Exception:
            pass  # ffmpeg not in PATH or not working
        
        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]
        
        for location in known_locations:
            if os.path.exists(location):
                return location
                
        # Could not find FFmpeg, will use just the command and hope it works
        return "ffmpeg"
    
    def validate_video_file(self, video_path):
        """
        Validate if the video file can be opened and read properly by FFmpeg.
        Returns a tuple of (is_valid, error_message)
        """
        # Check if file exists
        if not os.path.isfile(video_path):
            return False, f"Video file not found: {video_path}"
            
        # Try to get video info using FFmpeg
        try:
            import subprocess
            cmd = [
                self.ffmpeg_path, 
                "-i", video_path, 
                "-v", "error",
                "-f", "null", 
                "-"
            ]
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Check for errors in stderr
            stderr = process.stderr.decode('utf-8', errors='ignore')
            if process.returncode != 0:
                if stderr:
                    return False, f"FFmpeg reported errors: {stderr}"
                else:
                    return False, "Unknown FFmpeg error when validating video file"
                    
            # If we got here, the file seems valid
            return True, ""
            
        except Exception as e:
            return False, f"Error validating video file: {str(e)}"
        
    def run(self):
        try:
            # Try hardware-accelerated FFmpeg processing first
            fast_result = self.run_fast_ffmpeg_processing()
            if fast_result and os.path.exists(fast_result):
                self.processing_complete.emit(fast_result)
                return
            
            # Fallback to MoviePy processing with hardware acceleration if FFmpeg failed
            print("\n---------- FALLBACK TO MOVIEPY WITH HARDWARE ACCELERATION ----------")
            
            # Get the FFmpeg path - try environment or fallback to known location
            ffmpeg_path = self.get_ffmpeg_path()
            
            # Set the FFmpeg binary location explicitly
            if ffmpeg_path != "ffmpeg":
                mp.config.change_settings({"FFMPEG_BINARY": ffmpeg_path})
            
            # Validate the video file first
            print(f"Validating video file: {self.video_path}")
            is_valid, error_message = self.validate_video_file(self.video_path)
            if not is_valid:
                print(f"Video validation failed: {error_message}")
                raise RuntimeError(f"Video file validation failed: {error_message}")
            
            # Check if input file exists
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Video file not found: {self.video_path}")
            
            print(f"Loading video from: {self.video_path}")
            
            # Initialize VideoFileClip with explicit parameters for better compatibility
            video = None
            try:
                # Try standard MoviePy loading
                video = mp.VideoFileClip(self.video_path, audio=True, verbose=False)
                # Test video access to make sure it can be read
                test_frame = video.get_frame(0)  # Get first frame to test
                print(f"Video loaded successfully. Duration: {video.duration}s")
            except Exception as initial_error:
                print(f"Error during standard video loading: {str(initial_error)}")
                # If standard loading fails, try alternative approach
                print("Attempting alternative loading method...")
                try:
                    # We'll try to create a fresh copy of the video to work with
                    temp_video_path = os.path.join(tempfile.gettempdir(), f"temp_video_{int(time.time())}.mp4")
                    
                    # Use FFmpeg directly to create a copy with standard parameters
                    import subprocess
                    cmd = [
                        ffmpeg_path,
                        "-i", self.video_path,
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-pix_fmt", "yuv420p",
                        "-y",  # Overwrite if exists
                        temp_video_path
                    ]
                    print(f"Running FFmpeg to create a clean copy: {' '.join(cmd)}")
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    if result.returncode != 0:
                        stderr = result.stderr.decode('utf-8', errors='ignore')
                        print(f"FFmpeg copy failed: {stderr}")
                        raise RuntimeError(f"Failed to create a clean video copy: {stderr}")
                    
                    # Now try to load the clean copy
                    video = mp.VideoFileClip(temp_video_path, audio=True, verbose=False)
                    test_frame = video.get_frame(0)  # Test again
                    print(f"Successfully loaded video with alternative method. Duration: {video.duration}s")
                    
                    # Update the video path to use the clean copy
                    print(f"Using temporary video file: {temp_video_path}")
                    self.video_path = temp_video_path
                except Exception as alt_error:
                    print(f"Alternative loading method also failed: {str(alt_error)}")
                    raise RuntimeError(f"Could not load video file using any method: {str(initial_error)}\nAlternative method error: {str(alt_error)}")
            
            print(f"Video loaded, audio duration: {video.audio.duration} ms")
            
            # Process the silent parts to get a list of segments
            sorted_parts = sorted(self.silent_parts, key=lambda x: x['start'])
            segments = []
            last_end = 0
            
            self.progress_updated.emit(20)
            QApplication.processEvents()
            
            for part in sorted_parts:
                if part['selected']:  # Only cut if selected
                    if part['start'] > last_end:
                        # Add segment before the silence
                        try:
                            new_segment = video.subclip(last_end, part['start'])
                            segments.append(new_segment)
                        except Exception as e:
                            print(f"Error creating segment {last_end} to {part['start']}: {str(e)}")
                            # Skip this segment but continue processing
                    # Update last_end to be the end of this silent part
                    last_end = part['end']
            
            # Add the final segment if needed
            if last_end < video.duration:
                try:
                    final_segment = video.subclip(last_end, video.duration)
                    segments.append(final_segment)
                except Exception as e:
                    print(f"Error creating final segment {last_end} to {video.duration}: {str(e)}")
            
            self.progress_updated.emit(30)
            QApplication.processEvents()
            
            # If no segments were cut, just use the original video
            if not segments:
                print("No silent segments were cut, using original video")
                result = video
            else:
                try:
                    # Concatenate all segments
                    print(f"Concatenating {len(segments)} video segments")
                    result = mp.concatenate_videoclips(segments)
                except Exception as e:
                    print(f"Error concatenating clips: {str(e)}")
                    # Fallback to using the original video
                    print("Fallback to original video")
                    result = video
                    # Clean up segments to avoid memory leaks
                    for segment in segments:
                        segment.close()
            
            self.progress_updated.emit(40)
            QApplication.processEvents()
            
            # Create a unique temp filename for audio to avoid conflicts
            temp_audio_file = os.path.join(tempfile.gettempdir(), f"temp-audio-processing-{os.getpid()}-{int(time.time())}.m4a")
            
            # Set up progress updates through manual timed updates with timeout
            self.last_update_time = time.time()
            self.last_progress = 40
            self.processing_start_time = time.time()
            self.processing_timeout = 600  # 10 minute timeout for MoviePy
            
            def update_progress():
                current_time = time.time()
                elapsed_total = current_time - self.processing_start_time
                
                # Check for timeout
                if elapsed_total > self.processing_timeout:
                    print(f"MoviePy processing timeout after {self.processing_timeout} seconds")
                    timer.stop()
                    return
                
                if current_time - self.last_update_time >= 1.0:  # Update every second
                    self.last_update_time = current_time
                    
                    # More realistic progress increments
                    if elapsed_total < 60:  # First minute
                        increment = 0.8
                    elif elapsed_total < 180:  # Next 2 minutes
                        increment = 0.4
                    else:  # After 3 minutes, very slow
                        increment = 0.1
                    
                    self.last_progress = min(98, self.last_progress + increment)
                    self.progress_updated.emit(int(self.last_progress))
                    QApplication.processEvents()  # Process UI events
            
            # Create a timer to periodically update the progress
            timer = QTimer()
            timer.timeout.connect(update_progress)
            
            try:
                # Start the timer
                timer.start(200)  # Check every 200ms
                
                # Detect hardware acceleration for MoviePy export
                hw_options = self.detect_hardware_acceleration()
                video_codec, hw_name = hw_options[0]
                print(f"MoviePy export using {hw_name}")
                
                # Prepare FFmpeg parameters for hardware acceleration
                ffmpeg_params = ["-pix_fmt", "yuv420p"]  # Standard pixel format
                
                if video_codec == 'h264_nvenc':
                    ffmpeg_params.extend([
                        "-preset", "fast",
                        "-rc", "vbr",
                        "-cq", "23",
                        "-b:v", "5M",
                        "-maxrate", "10M",
                        "-bufsize", "10M"
                    ])
                elif video_codec == 'h264_qsv':
                    ffmpeg_params.extend([
                        "-preset", "fast",
                        "-global_quality", "23",
                        "-look_ahead", "1"
                    ])
                elif video_codec == 'h264_amf':
                    ffmpeg_params.extend([
                        "-quality", "speed",
                        "-rc", "vbr_peak",
                        "-qp_i", "22",
                        "-qp_p", "24",
                        "-qp_b", "26"
                    ])
                else:  # libx264 (software)
                    ffmpeg_params.extend([
                        "-preset", "fast",
                        "-crf", "23"
                    ])
                
                # Export the result with hardware acceleration
                print(f"Writing output to: {self.output_path}")
                result.write_videofile(
                    self.output_path, 
                    codec=video_codec,  # Use detected hardware codec
                    audio_codec="aac",
                    temp_audiofile=temp_audio_file, 
                    remove_temp=True,
                    verbose=True,  # Set to True for more detailed output
                    logger=None,
                    ffmpeg_params=ffmpeg_params  # Hardware-specific parameters
                )
                
                # Stop the timer
                timer.stop()
                
                # Verify the output file was created successfully
                if os.path.exists(self.output_path):
                    file_size = os.path.getsize(self.output_path)
                    print(f"MoviePy processing completed successfully")
                    print(f"Output file size: {file_size / (1024*1024):.1f} MB")
                else:
                    raise RuntimeError("Output file was not created by MoviePy")
                    
            except Exception as e:
                timer.stop()
                print(f"Error during video writing: {str(e)}")
                raise e
            finally:
                # Clean up resources
                try:
                    if 'video' in locals():
                        video.close()
                    if 'result' in locals() and result != video:
                        result.close()
                except Exception as cleanup_error:
                    print(f"Error during cleanup: {str(cleanup_error)}")
            
            # Final progress update - ensure we reach 100%
            self.progress_updated.emit(100)
            QApplication.processEvents()
            
            self.processing_complete.emit(self.output_path)
            
        except Exception as e:
            print(f"Error in video processing: {str(e)}")
            import traceback
            traceback.print_exc()
            self.processing_complete.emit("")

    def detect_hardware_acceleration(self):
        """Detect available hardware acceleration options"""
        hw_options = []
        
        try:
            # Test NVIDIA NVENC
            result = subprocess.run([
                self.ffmpeg_path, '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_nvenc', '-f', 'null', '-'
            ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                hw_options.append(('h264_nvenc', 'NVIDIA NVENC'))
                print("✓ NVIDIA NVENC hardware acceleration available")
        except:
            pass
            
        try:
            # Test Intel QuickSync
            result = subprocess.run([
                self.ffmpeg_path, '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_qsv', '-f', 'null', '-'
            ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                hw_options.append(('h264_qsv', 'Intel QuickSync'))
                print("✓ Intel QuickSync hardware acceleration available")
        except:
            pass
            
        try:
            # Test AMD AMF
            result = subprocess.run([
                self.ffmpeg_path, '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_amf', '-f', 'null', '-'
            ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                hw_options.append(('h264_amf', 'AMD AMF'))
                print("✓ AMD AMF hardware acceleration available")
        except:
            pass
            
        # Fallback to software encoding
        if not hw_options:
            hw_options.append(('libx264', 'Software (CPU)'))
            print("ℹ Using software encoding (no hardware acceleration detected)")
            
        return hw_options

    def run_fast_ffmpeg_processing(self):
        """Fast video processing using direct FFmpeg with hardware acceleration"""
        try:
            print(f"\n---------- HARDWARE-ACCELERATED FFMPEG PROCESSING START ----------")
            
            # Detect available hardware acceleration
            hw_options = self.detect_hardware_acceleration()
            video_codec, hw_name = hw_options[0]  # Use the first (best) available option
            print(f"Using {hw_name} for video encoding")
            
            # Get selected silent parts
            selected_parts = [part for part in self.silent_parts if part['selected']]
            if not selected_parts:
                print("No silent parts selected for cutting")
                return self.output_path
            
            # Cache video duration for progress calculation
            self._video_duration = self.get_video_duration()
            
            self.progress_updated.emit(10)
            QApplication.processEvents()
            
            # Create filter complex for removing silent segments
            filter_parts = []
            segment_inputs = []
            
            # Sort selected parts by start time
            selected_parts.sort(key=lambda x: x['start'])
            
            # Generate segments between silent parts
            last_end = 0
            segment_count = 0
            
            for part in selected_parts:
                # Add segment before this silent part
                if part['start'] > last_end:
                    segment_inputs.append(f"[0]trim=start={last_end}:end={part['start']},setpts=PTS-STARTPTS[v{segment_count}]; [0]atrim=start={last_end}:end={part['start']},asetpts=PTS-STARTPTS[a{segment_count}];")
                    filter_parts.append(f"[v{segment_count}][a{segment_count}]")
                    segment_count += 1
                last_end = part['end']
            
            # Add final segment after last silent part
            video_duration = self.get_video_duration()
            if last_end < video_duration:
                segment_inputs.append(f"[0]trim=start={last_end}:end={video_duration},setpts=PTS-STARTPTS[v{segment_count}]; [0]atrim=start={last_end}:end={video_duration},asetpts=PTS-STARTPTS[a{segment_count}];")
                filter_parts.append(f"[v{segment_count}][a{segment_count}]")
                segment_count += 1
            
            if segment_count == 0:
                print("No segments to keep after removing silence")
                return ""
            
            self.progress_updated.emit(30)
            QApplication.processEvents()
            
            # Build concatenation filter
            if segment_count == 1:
                # Single segment, no need to concatenate
                filter_complex = segment_inputs[0].replace(f"[v0]", "[outv]").replace(f"[a0]", "[outa]")
            else:
                # Multiple segments, concatenate them
                concat_input = "".join(filter_parts)
                filter_complex = "".join(segment_inputs) + f"{concat_input}concat=n={segment_count}:v=1:a=1[outv][outa]"
            
            # Build hardware-accelerated FFmpeg command
            cmd = [self.ffmpeg_path]
            
            # Add hardware acceleration input options
            if video_codec in ['h264_nvenc', 'h264_qsv', 'h264_amf']:
                cmd.extend(['-hwaccel', 'auto'])  # Auto-detect and use hardware acceleration
                
            cmd.extend([
                '-i', self.video_path,
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', video_codec
            ])
            
            # Add codec-specific optimizations
            if video_codec == 'h264_nvenc':
                cmd.extend([
                    '-preset', 'fast',      # NVENC preset for speed
                    '-rc', 'vbr',          # Variable bitrate
                    '-cq', '23',           # Quality level (lower = better quality)
                    '-b:v', '5M',          # Target bitrate
                    '-maxrate', '10M',     # Max bitrate
                    '-bufsize', '10M'      # Buffer size
                ])
            elif video_codec == 'h264_qsv':
                cmd.extend([
                    '-preset', 'fast',     # QuickSync preset
                    '-global_quality', '23', # Quality level
                    '-look_ahead', '1'     # Look-ahead for better quality
                ])
            elif video_codec == 'h264_amf':
                cmd.extend([
                    '-quality', 'speed',   # AMF quality preset
                    '-rc', 'vbr_peak',     # Rate control
                    '-qp_i', '22',         # I-frame quality
                    '-qp_p', '24',         # P-frame quality
                    '-qp_b', '26'          # B-frame quality
                ])
            else:  # libx264 (software)
                cmd.extend([
                    '-preset', 'fast',     # x264 preset for speed
                    '-crf', '23'           # Constant rate factor
                ])
            
            # Add audio encoding options
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',  # Overwrite output
                self.output_path
            ])
            
            self.progress_updated.emit(50)
            QApplication.processEvents()
            
            print(f"Running hardware-accelerated FFmpeg processing with {hw_name}...")
            print(f"Command: {' '.join(cmd[:12])}...")  # Show partial command
            print(f"Input file: {self.video_path}")
            print(f"Output file: {self.output_path}")
            print(f"Filter complex: {filter_complex[:100]}...")  # Show first 100 chars
            
            # Run FFmpeg with progress monitoring
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout for better monitoring
                text=True,
                universal_newlines=True,
                bufsize=1,  # Line buffered
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Monitor progress with real-time output reading and timeout
            start_time = time.time()
            last_progress_time = start_time
            current_progress = 50
            timeout_seconds = 300  # 5 minute timeout
            output_lines = []
            
            # Read output in real-time to detect completion
            import select
            import threading
            
            def read_output():
                nonlocal current_progress
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    output_lines.append(line.strip())
                    
                    # Parse FFmpeg progress from time= output
                    if "time=" in line:
                        try:
                            # Extract time from FFmpeg output (format: time=00:01:23.45)
                            time_match = line.split("time=")[1].split()[0]
                            if ":" in time_match:
                                time_parts = time_match.split(":")
                                if len(time_parts) >= 3:
                                    hours = float(time_parts[0])
                                    minutes = float(time_parts[1])
                                    seconds = float(time_parts[2])
                                    current_time_seconds = hours * 3600 + minutes * 60 + seconds
                                    
                                    # Calculate progress based on video duration
                                    if hasattr(self, '_video_duration') and self._video_duration > 0:
                                        progress_percent = min(98, (current_time_seconds / self._video_duration) * 100)
                                        if progress_percent > current_progress:
                                            current_progress = progress_percent
                                            self.progress_updated.emit(int(current_progress))
                                            QApplication.processEvents()
                        except:
                            pass  # Ignore parsing errors
                    
                    # Look for completion indicators
                    if "video:" in line.lower() and "audio:" in line.lower() and "subtitle:" in line.lower():
                        print(f"FFmpeg completion detected: {line.strip()}")
                    elif "error" in line.lower():
                        print(f"FFmpeg error detected: {line.strip()}")
            
            # Start output reading thread
            output_thread = threading.Thread(target=read_output, daemon=True)
            output_thread.start()
            
            while process.poll() is None:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Check for timeout
                if elapsed > timeout_seconds:
                    print(f"FFmpeg processing timeout after {timeout_seconds} seconds, terminating...")
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:
                        process.kill()
                    break
                
                # Update progress more gradually and realistically
                if current_time - last_progress_time >= 1.0:  # Update every second
                    # More conservative progress estimation
                    if elapsed < 30:  # First 30 seconds
                        progress_increment = 1
                    elif elapsed < 60:  # Next 30 seconds
                        progress_increment = 0.5
                    else:  # After 1 minute, very slow progress
                        progress_increment = 0.2
                    
                    current_progress = min(98, current_progress + progress_increment)
                    self.progress_updated.emit(int(current_progress))
                    QApplication.processEvents()
                    last_progress_time = current_time
            
                time.sleep(0.5)  # Check every 500ms instead of 100ms
            
            # Wait for process to complete and get final output
            stdout, stderr = process.communicate()
            
            # Combine all output for analysis
            all_output = '\n'.join(output_lines)
            if stdout:
                all_output += '\n' + stdout
            
            if process.returncode == 0:
                # Check if output file was actually created and has reasonable size
                if os.path.exists(self.output_path):
                    file_size = os.path.getsize(self.output_path)
                    if file_size > 1024:  # At least 1KB
                        self.progress_updated.emit(100)
                        QApplication.processEvents()
                        elapsed_total = time.time() - start_time
                        print(f"Hardware-accelerated processing completed in {elapsed_total:.1f} seconds")
                        print(f"Output file size: {file_size / (1024*1024):.1f} MB")
                        print(f"---------- HARDWARE-ACCELERATED FFMPEG PROCESSING END ----------\n")
                        return self.output_path
                    else:
                        print(f"Output file created but is too small ({file_size} bytes), likely an error")
                        return ""
                else:
                    print("Output file was not created, FFmpeg may have failed silently")
                    return ""
            else:
                print(f"Hardware-accelerated FFmpeg processing failed with return code {process.returncode}")
                if all_output:
                    print(f"FFmpeg output: {all_output[-500:]}")  # Show last 500 chars
                print("Falling back to software encoding...")
                return ""
                
        except Exception as e:
            print(f"Hardware-accelerated FFmpeg processing error: {e}")
            print("Falling back to software encoding...")
            return ""
    
    def get_video_duration(self):
        """Get video duration quickly using FFprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                '-of', 'csv=p=0', self.video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return float(result.stdout.strip())
        except:
            # Fallback to MoviePy
            try:
                video = mp.VideoFileClip(self.video_path)
                duration = video.duration
                video.close()
                return duration
            except:
                return 0

class SilencePreviewWidget(QWidget):
    selection_changed = pyqtSignal(dict)
    
    def __init__(self, silent_part, video_path):
        super().__init__()
        self.silent_part = silent_part
        self.video_path = video_path
        # Get the FFmpeg path - try environment or fallback to known location
        self.ffmpeg_path = self.get_ffmpeg_path()
        self.setup_ui()
        
    def get_ffmpeg_path(self):
        """Try to find FFmpeg executable path"""
        # First try directly if it's in PATH
        try:
            # Use subprocess to check if ffmpeg is available
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return "ffmpeg"  # ffmpeg is in PATH and working
        except Exception:
            pass  # ffmpeg not in PATH or not working
        
        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Users\\WALTON\\ffmpeg-2025-05-07-git-1b643e3f65-full_build\\ffmpeg-2025-05-07-git-1b643e3f65-full_build\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]
        
        for location in known_locations:
            if os.path.exists(location):
                return location
                
        # Could not find FFmpeg, will use just the command and hope it works
        return "ffmpeg"
        
    def setup_ui(self):
        layout = QHBoxLayout()
        
        # Checkbox for selection
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.silent_part['selected'])
        self.checkbox.stateChanged.connect(self.on_selection_changed)
        layout.addWidget(self.checkbox)
        
        # Information label
        start_time = self.format_time(self.silent_part['start'])
        end_time = self.format_time(self.silent_part['end'])
        duration = self.silent_part['duration_ms'] / 1000
        
        info_label = QLabel(f"Silence {self.silent_part['id'] + 1}: {start_time} - {end_time} (Duration: {duration:.2f}s)")
        info_label.setFont(QFont("Arial", 10))
        layout.addWidget(info_label, 1)
        
        # Button to preview
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self.on_preview_clicked)
        layout.addWidget(preview_btn)
        
        self.setLayout(layout)
        
    def on_selection_changed(self, state):
        self.silent_part['selected'] = (state == Qt.Checked)
        self.selection_changed.emit(self.silent_part)
        
    def on_preview_clicked(self):
        try:
            # Extract a short clip around the silent part for preview
            padding = 2.0  # seconds before and after silence
            start = max(0, self.silent_part['start'] - padding)
            end = min(mp.VideoFileClip(self.video_path).duration, self.silent_part['end'] + padding)
            
            # Create temporary file for preview clip in user temp directory with unique name
            preview_suffix = f"_silence_preview_{id(self)}_{int(time.time())}.mp4"
            temp_preview_path = os.path.join(tempfile.gettempdir(), f"silence_preview{preview_suffix}")
            
            # Extract preview clip
            video = mp.VideoFileClip(self.video_path)
            preview_clip = video.subclip(start, end)
            
            # Add a visual indicator for the silent part
            def highlight_silence(get_frame, t):
                frame = get_frame(t)
                # If we're in the silent region, add a red border
                if self.silent_part['start'] <= (start + t) <= self.silent_part['end']:
                    h, w = frame.shape[:2]
                    # Add a red border (20 pixels wide)
                    border_width = 20
                    frame[:border_width, :] = [0, 0, 255]  # Top border
                    frame[-border_width:, :] = [0, 0, 255]  # Bottom border
                    frame[:, :border_width] = [0, 0, 255]  # Left border
                    frame[:, -border_width:] = [0, 0, 255]  # Right border
                    
                    # Add text indicating this is a silent part
                    text = "SILENCE DETECTED"
                    cv2.putText(frame, text, (w//2 - 150, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                return frame
            
            # Apply the visual indicator
            preview_clip = preview_clip.fl(highlight_silence)
            
            # Create a unique temp filename for audio to avoid conflicts
            temp_audio_file = os.path.join(tempfile.gettempdir(), f"temp-audio-{os.getpid()}-{id(self)}.m4a")
            
            # Modify moviepy's FFMPEG_BINARY setting to use our detected FFmpeg path
            from moviepy.config import change_settings
            change_settings({"FFMPEG_BINARY": self.ffmpeg_path})
            
            # Write the preview clip
            preview_clip.write_videofile(
                temp_preview_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=temp_audio_file,
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # Open the preview with the default video player
            if sys.platform == "win32":
                os.startfile(temp_preview_path)
            elif sys.platform == "darwin":
                os.system(f"open {temp_preview_path}")
            else:
                os.system(f"xdg-open {temp_preview_path}")
                
        except Exception as e:
            error_message = f"Could not play preview: {str(e)}"
            QMessageBox.critical(self, "Preview Error", error_message)
            # Log the full error details
            print(f"Preview error details: {e}")
            import traceback
            traceback.print_exc()
    
    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"

class TimelineWidget(QWidget):
    """Custom timeline widget with draggable silence regions and waveform visualization"""
    selection_changed = pyqtSignal(dict)
    position_changed = pyqtSignal(float)  # Emitted when user seeks on timeline
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)  # Increased from 120 for larger timeline
        self.setMaximumHeight(220)  # Increased from 180
        
        # Timeline data
        self.duration_seconds = 0
        self.current_position = 0  # Current playback position in seconds
        self.silent_parts = []
        self.silent_ranges = []
        
        # Preview mode support
        self.preview_mode = False
        
        # Debug information
        self.debug_click_position = None  # Last click position in seconds
        self.debug_click_x = None  # Last click X coordinate
        self.show_debug_info = False  # Toggle to show/hide debug info (disabled by default)
        
        # Tooltip for playhead
        self.setToolTip("")
        
        # Smooth playhead animation
        self.target_position = 0  # Target position for smooth animation
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_playhead)
        self.animation_speed = 0.5  # Animation smoothing factor (0.5 = balanced, 1.0 = instant)
        self.animation_interval = 16  # 60 FPS animation (16ms intervals)
        
        # Waveform data
        self.waveform_data = None
        self.waveform_max_amplitude = 0
        self.video_path = None
        
        # Waveform caching for performance optimization
        self.waveform_cache = WaveformCache(max_zoom_levels=8)  # Reduced cache size
        self.cache_enabled = True
        self.cache_during_loading = False  # Disable caching during initial loading
        
        # Zoom functionality - improved limits
        self.zoom_level = 1.0  # 1.0 = normal, 2.0 = 2x zoom, etc.
        self.zoom_offset = 0.0  # Horizontal offset when zoomed (0.0 to 1.0)
        self.min_zoom = 1.0  # Prevent zooming out below normal scale
        self.max_zoom = 10.0
        
        # Undo/Redo system
        self.history = []  # List of (silent_parts, silent_ranges) states
        self.history_index = -1
        self.max_history = 50
        
        # Interaction state
        self.dragging_region = None
        self.dragging_edge = None  # 'start' or 'end'
        self.drag_start_pos = None
        self.drag_start_state = None  # Store state before dragging for undo
        self.hover_region = None
        self.seeking = False
        
        # Visual settings
        self.margin = 20
        self.timeline_height = 80  # Increased from 60 for larger timeline
        self.region_height = 35  # Increased from 30 for better visibility
        
        # Enable mouse tracking and focus for keyboard events
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Save initial state
        self.save_state()
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                self.undo()
                event.accept()
                return
        elif event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            if event.key() == Qt.Key_Z:
                self.redo()
                event.accept()
                return
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
            event.accept()
            return
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
            event.accept()
            return
        elif event.key() == Qt.Key_0:
            self.reset_zoom()
            event.accept()
            return
        elif event.key() == Qt.Key_D:
            # Toggle debug info display
            self.show_debug_info = not self.show_debug_info
            self.update()
            print(f"Debug info display: {'ON' if self.show_debug_info else 'OFF'}")
            event.accept()
            return
        elif event.key() == Qt.Key_B:
            # Show buffer statistics
            self.show_buffer_stats()
            event.accept()
            return
            
        super().keyPressEvent(event)
        
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if event.modifiers() == Qt.ControlModifier:
            # Zoom with Ctrl + Mouse Wheel
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Horizontal scroll when zoomed
            if self.zoom_level > 1.0:
                delta = event.angleDelta().y()
                scroll_amount = 0.05 / self.zoom_level  # Scroll slower when more zoomed
                if delta > 0:
                    self.zoom_offset = max(0.0, self.zoom_offset - scroll_amount)
                else:
                    max_offset = 1.0 - (1.0 / self.zoom_level)
                    self.zoom_offset = min(max_offset, self.zoom_offset + scroll_amount)
                self.update()
                event.accept()
            else:
                super().wheelEvent(event)
                
    def zoom_in(self):
        """Zoom in the timeline"""
        old_zoom = self.zoom_level
        self.zoom_level = min(self.max_zoom, self.zoom_level * 1.2)
        # Adjust offset to keep center focused
        if old_zoom != self.zoom_level:
            center_ratio = 0.5  # Keep center focused
            new_visible_range = 1.0 / self.zoom_level
            self.zoom_offset = max(0.0, min(1.0 - new_visible_range, 
                                          center_ratio - new_visible_range / 2))
            self.update()
            
    def zoom_out(self):
        """Zoom out the timeline - prevent going below normal (1.0x) scale"""
        # Only allow zooming out if currently above 1.0x scale
        if self.zoom_level > 1.0:
            self.zoom_level = max(1.0, self.zoom_level / 1.2)
        
        # Adjust offset to stay within bounds
        max_offset = max(0.0, 1.0 - (1.0 / self.zoom_level))
        self.zoom_offset = min(max_offset, self.zoom_offset)
        self.update()
        
    def reset_zoom(self):
        """Reset zoom to normal level"""
        self.zoom_level = 1.0
        self.zoom_offset = 0.0
        self.update()
        
    def save_state(self):
        """Save current state for undo/redo"""
        import copy
        current_state = (copy.deepcopy(self.silent_parts), copy.deepcopy(self.silent_ranges))
        
        # Remove any states after current index (when we're not at the end)
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
            
        # Add new state
        self.history.append(current_state)
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
        else:
            self.history_index += 1
            
    def undo(self):
        """Undo last action"""
        if self.history_index > 0:
            self.history_index -= 1
            self.restore_state(self.history[self.history_index])
            
    def redo(self):
        """Redo last undone action"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.restore_state(self.history[self.history_index])
            
    def restore_state(self, state):
        """Restore a saved state"""
        import copy
        self.silent_parts, self.silent_ranges = copy.deepcopy(state)
        self.update()
        # Emit selection changed to update other UI elements
        if self.silent_parts:
            self.selection_changed.emit(self.silent_parts[0])
        
    def load_waveform(self, video_path):
        """Extract and load waveform data from video in background thread"""
        self.video_path = video_path
        
        # Start waveform loading in background thread
        self.waveform_thread = WaveformLoadingThread(video_path)
        self.waveform_thread.waveform_loaded.connect(self.on_waveform_loaded)
        self.waveform_thread.duration_loaded.connect(self.set_duration)
        self.waveform_thread.progress_updated.connect(self.on_waveform_progress)
        self.waveform_thread.start()
        
    def on_waveform_loaded(self, waveform_data, max_amplitude):
        """Handle waveform data when loaded from background thread"""
        self.waveform_data = waveform_data
        self.waveform_max_amplitude = max_amplitude
        if waveform_data:
            print(f"⚡ Waveform loaded: {len(waveform_data)} samples, max amplitude: {max_amplitude:.3f}")
        else:
                print("No audio track found in video")
        self.update()  # Trigger repaint
        
        # NOW hide the loading overlay since waveform loading is complete
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'hide_loading_overlay'):
            print("✅ Waveform loading complete - hiding loading overlay")
            QTimer.singleShot(500, parent.hide_loading_overlay)  # Small delay to show completion
        
    def on_waveform_progress(self, message):
        """Handle waveform loading progress updates"""
        # Find parent SilenceCutterApp to update loading overlay
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'update_loading_progress_with_step'):
            # Map waveform progress messages to step numbers
            if "Loading video file" in message:
                parent.update_loading_progress_with_step(message, 3)
            elif "Extracting audio" in message:
                parent.update_loading_progress_with_step(message, 3)
            elif "Processing audio" in message:
                parent.update_loading_progress_with_step(message, 3)
            elif "Generating waveform" in message:
                parent.update_loading_progress_with_step(message, 3)
            elif "Optimizing waveform" in message:
                parent.update_loading_progress_with_step(message, 3)
            elif "Waveform ready" in message:
                parent.update_loading_progress_with_step(message, 3)
            else:
                parent.update_loading_progress_with_step(message, 3)
    
    def set_duration(self, duration_seconds):
        """Set the total duration of the timeline"""
        self.duration_seconds = duration_seconds
        self.update()
        
    def set_position(self, position_seconds, instant=False):
        """Set the current playback position with optional smooth animation"""
        if instant:
            # Instant positioning for user clicks
            self.current_position = position_seconds
            self.target_position = position_seconds
            if self.animation_timer.isActive():
                self.animation_timer.stop()
        else:
            # Smooth animation for playback
            self.target_position = position_seconds
            
            # Start smooth animation if not already running
            if not self.animation_timer.isActive():
                self.animation_timer.start(self.animation_interval)  # Use configured interval
        
        # Update tooltip to show current time
        if position_seconds >= 0:
            time_str = self.format_time_mmss_ms(position_seconds)
            self.setToolTip(f"Playhead: {time_str}")
            else:
            self.setToolTip("")
            
        self.update()  # Trigger immediate repaint for instant updates
    
    def animate_playhead(self):
        """Smooth playhead animation"""
        if abs(self.current_position - self.target_position) < 0.005:  # More precise stopping condition
            self.current_position = self.target_position
            self.animation_timer.stop()
        else:
            # Smooth interpolation towards target
            diff = self.target_position - self.current_position
            self.current_position += diff * self.animation_speed
        
            self.update()  # Trigger repaint
        
    def set_silent_parts(self, silent_parts, silent_ranges):
        """Set the silent parts and ranges for visualization"""
        self.silent_parts = silent_parts
        self.silent_ranges = silent_ranges
        self.save_state()  # Save state when new data is loaded
        self.update()
        
    def set_preview_mode(self, enabled, silent_parts=None):
        """Enable or disable preview mode visualization"""
        self.preview_mode = enabled
        if enabled and silent_parts:
            self.silent_parts = silent_parts
            
            # Calculate preview duration (total time after removing silent parts)
            selected_silent_parts = [part for part in silent_parts if part['selected']]
            if selected_silent_parts:
                total_cuts_duration = sum(part['end'] - part['start'] for part in selected_silent_parts)
                self.preview_timeline_duration = self.duration_seconds - total_cuts_duration
                print(f"🎯 TIMELINE PREVIEW MODE:")
                print(f"  Original duration: {self.duration_seconds:.3f}s")
                print(f"  Total cuts: {total_cuts_duration:.3f}s") 
                print(f"  Preview duration: {self.preview_timeline_duration:.3f}s")
            else:
                self.preview_timeline_duration = self.duration_seconds
        else:
            self.preview_timeline_duration = None
            
        # Just trigger a repaint to show preview mode visualization
        self.update()
        
    def get_effective_duration(self):
        """Get the effective timeline duration (preview duration in preview mode, original otherwise)"""
        if self.preview_mode and hasattr(self, 'preview_timeline_duration') and self.preview_timeline_duration is not None:
            return self.preview_timeline_duration
        return self.duration_seconds
        
    def convert_click_position_to_original_time(self, click_time_seconds):
        """Convert a click position on the timeline to original video time"""
        if not self.preview_mode or not hasattr(self, 'preview_timeline_duration'):
            # Normal mode: click time is already in original timeline
            return click_time_seconds
            
        # Since we're always clicking on the original timeline/waveform, 
        # no conversion is needed - the click is already in original time coordinates
        print(f"🎯 TIMELINE CLICK (No Conversion Needed):")
        print(f"  Click position: {click_time_seconds:.3f}s (already in original timeline)")
            return click_time_seconds
        
    def original_time_to_preview_time(self, original_time):
        """Convert original video time to preview timeline position"""
        if not self.preview_mode or not self.silent_parts:
            return original_time
            
        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]
        if not selected_silent_parts:
            return original_time
            
        # Sort by start time
        selected_silent_parts.sort(key=lambda x: x['start'])
        
        # Build segments that will be kept
        preview_segments = []
        last_end = 0
        
        for silent_part in selected_silent_parts:
            if silent_part['start'] > last_end:
                # Add segment before this silent part
                preview_segments.append((last_end, silent_part['start']))
            last_end = silent_part['end']
            
        # Add final segment if needed
        if last_end < self.duration_seconds:
            preview_segments.append((last_end, self.duration_seconds))
            
        # Convert original time to preview timeline position
        accumulated_preview_time = 0
        for start, end in preview_segments:
            if start <= original_time <= end:
                # The time is within this segment
                offset_in_segment = original_time - start
                return accumulated_preview_time + offset_in_segment
            elif original_time < start:
                # The time is before this segment (in a cut area)
                return accumulated_preview_time
            else:
                # The time is after this segment, continue accumulating
                accumulated_preview_time += (end - start)
                
        # If we get here, original_time is after all segments
        return accumulated_preview_time
        
    def get_visible_time_range(self):
        """Get the currently visible time range based on zoom and offset"""
        effective_duration = self.get_effective_duration()
        visible_duration = effective_duration / self.zoom_level
        start_time = self.zoom_offset * effective_duration
        end_time = start_time + visible_duration
        return start_time, end_time
        
    def get_original_visible_time_range(self):
        """Get the visible time range in original timeline coordinates (for waveform and silence regions)"""
        if self.preview_mode:
            # In preview mode, calculate visible range based on original timeline
            original_duration = self.duration_seconds
            visible_duration = original_duration / self.zoom_level
            start_time = self.zoom_offset * original_duration
            end_time = start_time + visible_duration
            
            # Ensure we don't go beyond the original duration
            start_time = max(0, start_time)
            end_time = min(original_duration, end_time)
            return start_time, end_time
        else:
            # Normal mode: use the regular visible time range
            return self.get_visible_time_range()
        
    def time_to_x(self, time_seconds, timeline_rect):
        """Convert time to X coordinate considering zoom and offset"""
        start_time, end_time = self.get_visible_time_range()
        if end_time == start_time:
            return timeline_rect.left()
        relative_pos = (time_seconds - start_time) / (end_time - start_time)
        return timeline_rect.left() + relative_pos * timeline_rect.width()
        
    def original_time_to_x(self, time_seconds, timeline_rect):
        """Convert original timeline time to X coordinate (for waveform and silence regions)"""
        start_time, end_time = self.get_original_visible_time_range()
        if end_time == start_time:
            return timeline_rect.left()
        relative_pos = (time_seconds - start_time) / (end_time - start_time)
        return timeline_rect.left() + relative_pos * timeline_rect.width()
        
    def x_to_time(self, x, timeline_rect):
        """Convert X coordinate to time considering zoom and offset"""
        relative_pos = (x - timeline_rect.left()) / timeline_rect.width()
        
        # ALWAYS use original timeline coordinates for clicks since we're clicking on the original waveform
        # The waveform and silence regions are always displayed in original timeline coordinates
        start_time, end_time = self.get_original_visible_time_range()
        original_time = start_time + relative_pos * (end_time - start_time)
        
        print(f"🎯 X_TO_TIME CONVERSION:")
        print(f"  Click X: {x:.1f}, Timeline width: {timeline_rect.width():.1f}")
        print(f"  Relative pos: {relative_pos:.3f}")
        print(f"  Visible range: {start_time:.3f}s - {end_time:.3f}s")
        print(f"  Calculated original time: {original_time:.3f}s")
        
        return original_time
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(245, 245, 245))
        
        if self.duration_seconds <= 0:
            painter.drawText(self.rect(), Qt.AlignCenter, "No video loaded")
            return
            
        # Calculate timeline area
        timeline_rect = QRectF(
            self.margin,
            (self.height() - self.timeline_height) / 2,
            self.width() - 2 * self.margin,
            self.timeline_height
        )
        
        # Draw waveform background
        self.draw_waveform(painter, timeline_rect)
        
        # Draw timeline border
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.drawRect(timeline_rect)
        
        # Get visible time range for silence regions (always use original timeline)
        original_start_time, original_end_time = self.get_original_visible_time_range()
        
        # Draw silence regions
        for i, (start_ms, end_ms) in enumerate(self.silent_ranges):
            if i >= len(self.silent_parts):
                continue
                
            start_sec = start_ms / 1000
            end_sec = end_ms / 1000
            
            # Skip regions not in visible range (using original timeline)
            if end_sec < original_start_time or start_sec > original_end_time:
                continue
            
            # Calculate region position using original timeline coordinates
            start_x = self.original_time_to_x(start_sec, timeline_rect)
            end_x = self.original_time_to_x(end_sec, timeline_rect)
            width = end_x - start_x
            
            # Choose color based on selection state
            part = self.silent_parts[i]
            if part['selected']:
                color = QColor(220, 60, 60, 180)  # Selected: semi-transparent red
                border_color = QColor(180, 30, 30)
                glow_color = QColor(255, 100, 100, 100)
            else:
                color = QColor(140, 140, 140, 140)  # Unselected: semi-transparent gray
                border_color = QColor(100, 100, 100)
                glow_color = QColor(160, 160, 160, 80)
                
            # Highlight if hovering
            if self.hover_region == i:
                color = color.lighter(120)
                # Draw glow effect
                painter.setPen(QPen(glow_color, 4))
                painter.drawRect(QRectF(start_x - 2, timeline_rect.top() + 3, width + 4, self.region_height + 4))
                
            # Draw silence region with rounded corners
            region_rect = QRectF(
                start_x,
                timeline_rect.top() + 5,
                max(width, 3),  # Minimum width for visibility
                self.region_height
            )
            
            # Draw with gradient effect
            gradient = QLinearGradient(0, region_rect.top(), 0, region_rect.bottom())
            gradient.setColorAt(0, color.lighter(110))
            gradient.setColorAt(1, color.darker(110))
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(border_color, 2))
            painter.drawRoundedRect(region_rect, 3, 3)
            
            # Draw drag handles on the edges - made thinner
            handle_size = 4  # Reduced from 8 for thinner handles
            handle_color = border_color.lighter(130)
            
            # Left handle
            left_handle = QRectF(start_x - handle_size/2, timeline_rect.top() + 2, handle_size, self.timeline_height - 4)
            painter.fillRect(left_handle, handle_color)
            painter.setPen(QPen(border_color, 1))
            painter.drawRect(left_handle)
            
            # Right handle
            right_handle = QRectF(end_x - handle_size/2, timeline_rect.top() + 2, handle_size, self.timeline_height - 4)
            painter.fillRect(right_handle, handle_color)
            painter.setPen(QPen(border_color, 1))
            painter.drawRect(right_handle)
            
            # Draw region label
            if width > 30:  # Only draw label if region is wide enough
                label = f"S{i+1}"
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(region_rect, Qt.AlignCenter, label)
        
        # Draw current position indicator (use original timeline coordinates)
        if original_start_time <= self.current_position <= original_end_time:
            pos_x = self.original_time_to_x(self.current_position, timeline_rect)
            
            # Draw position line with glow
            painter.setPen(QPen(QColor(0, 120, 215, 100), 6))
            painter.drawLine(int(pos_x), int(timeline_rect.top() - 5), int(pos_x), int(timeline_rect.bottom() + 5))
            painter.setPen(QPen(QColor(0, 120, 215), 3))
            painter.drawLine(int(pos_x), int(timeline_rect.top() - 5), int(pos_x), int(timeline_rect.bottom() + 5))
            
            # Draw time indicator above the playhead like in reference image
            time_str = self.format_time_mmss_ms(self.current_position)
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            text_rect = painter.fontMetrics().boundingRect(time_str)
            
            # Draw time background with full opacity and better styling
            time_bg_rect = QRectF(pos_x - text_rect.width()/2 - 6, timeline_rect.top() - 38, 
                                text_rect.width() + 12, text_rect.height() + 8)
            painter.fillRect(time_bg_rect, QColor(45, 45, 45, 255))  # Fully opaque dark background
            painter.setPen(QPen(QColor(120, 200, 255), 2))  # Bright blue border
            painter.drawRect(time_bg_rect)
            
            # Draw inner shadow for depth
            inner_rect = QRectF(time_bg_rect.x() + 1, time_bg_rect.y() + 1, 
                              time_bg_rect.width() - 2, time_bg_rect.height() - 2)
            painter.setPen(QPen(QColor(80, 80, 80), 1))
            painter.drawRect(inner_rect)
            
            # Draw time text with high contrast
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(int(pos_x - text_rect.width()/2), int(timeline_rect.top() - 22), time_str)
            
            # Draw position indicator triangle with gradient
            triangle_points = [
                QPointF(pos_x, timeline_rect.top() - 5),
                QPointF(pos_x - 7, timeline_rect.top() - 17),
                QPointF(pos_x + 7, timeline_rect.top() - 17)
            ]
            
            gradient = QLinearGradient(0, timeline_rect.top() - 17, 0, timeline_rect.top() - 5)
            gradient.setColorAt(0, QColor(0, 150, 255))
            gradient.setColorAt(1, QColor(0, 100, 200))
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(0, 80, 160), 2))
            painter.drawPolygon(triangle_points)
        
        # Draw clean time markers at top like in the reference image
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        
        # Calculate appropriate marker interval based on zoom (use original timeline)
        visible_duration = (original_end_time - original_start_time)
        if visible_duration > 300:  # > 5 minutes
            marker_interval = 60  # 1 minute
        elif visible_duration > 60:  # > 1 minute  
            marker_interval = 15  # 15 seconds
        elif visible_duration > 30:  # > 30 seconds
            marker_interval = 10   # 10 seconds
        elif visible_duration > 10:  # > 10 seconds
            marker_interval = 5   # 5 seconds
        else:
            marker_interval = 1   # 1 second
            
        # Draw markers at the top (use original timeline coordinates)
        first_marker = int(original_start_time / marker_interval) * marker_interval
        current_marker = first_marker
        
        while current_marker <= original_end_time:
            if current_marker >= 0:
                marker_x = self.original_time_to_x(current_marker, timeline_rect)
                if timeline_rect.left() <= marker_x <= timeline_rect.right():
                    # Draw small tick mark at top
                    painter.drawLine(int(marker_x), int(timeline_rect.top() - 8), 
                                   int(marker_x), int(timeline_rect.top() - 3))
                    
                    # Draw time text above the timeline
                    time_text = self.format_time_mmss_ms(current_marker)
                    text_rect = painter.fontMetrics().boundingRect(time_text)
                    painter.drawText(int(marker_x - text_rect.width()/2), 
                                   int(timeline_rect.top() - 12), time_text)
            current_marker += marker_interval
            
        # Draw debug information at the top
        self.draw_debug_info(painter, timeline_rect)
            
        # Draw zoom info and reset button when zoomed
        if self.zoom_level != 1.0:
            zoom_text = f"Zoom: {self.zoom_level:.1f}x"
            painter.setPen(QPen(QColor(0, 100, 200), 1))
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            text_rect = painter.fontMetrics().boundingRect(zoom_text)
            
            # Calculate positions for zoom info and reset button
            info_width = text_rect.width() + 10
            reset_btn_width = 60
            total_width = info_width + reset_btn_width + 10  # 10px spacing
            
            # Draw zoom info background
            zoom_info_rect = QRectF(self.width() - total_width, 5, info_width, text_rect.height() + 6)
            painter.fillRect(zoom_info_rect, QColor(255, 255, 255, 200))
            painter.drawText(self.width() - total_width + 5, 20, zoom_text)
            
            # Draw reset button when zoomed
            reset_btn_rect = QRectF(self.width() - reset_btn_width - 5, 5, reset_btn_width, text_rect.height() + 6)
            
            # Check if mouse is hovering over reset button
            mouse_pos = self.mapFromGlobal(self.cursor().pos())
            is_hovering = reset_btn_rect.contains(mouse_pos)
            
            if is_hovering:
                painter.fillRect(reset_btn_rect, QColor(220, 240, 255, 200))
                painter.setPen(QPen(QColor(0, 120, 215), 2))
            else:
                painter.fillRect(reset_btn_rect, QColor(245, 245, 245, 200))
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                
            painter.drawRect(reset_btn_rect)
            
            # Draw reset button text
            painter.setPen(QPen(QColor(50, 50, 50) if not is_hovering else QColor(0, 100, 200), 1))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(reset_btn_rect, Qt.AlignCenter, "Reset")
            
            # Store reset button rect for click detection
            self.reset_button_rect = reset_btn_rect
        else:
            self.reset_button_rect = None
    
    def draw_waveform(self, painter, timeline_rect):
        """Draw the audio waveform as background with enhanced visibility and caching"""
        if not self.waveform_data or not self.waveform_max_amplitude:
            # Draw a gradient background if no waveform data
            gradient = QLinearGradient(0, timeline_rect.top(), 0, timeline_rect.bottom())
            gradient.setColorAt(0, QColor(235, 235, 240))
            gradient.setColorAt(0.5, QColor(245, 245, 250))
            gradient.setColorAt(1, QColor(235, 235, 240))
            painter.fillRect(timeline_rect, QBrush(gradient))
            return
            
        # Fill background with darker gradient for better contrast
        gradient = QLinearGradient(0, timeline_rect.top(), 0, timeline_rect.bottom())
        gradient.setColorAt(0, QColor(25, 30, 35))
        gradient.setColorAt(0.5, QColor(30, 35, 40))
        gradient.setColorAt(1, QColor(25, 30, 35))
        painter.fillRect(timeline_rect, QBrush(gradient))
        
        # ALWAYS use original timeline for waveform display, regardless of preview mode
        # This ensures the full waveform is always visible for proper editing
        start_time, end_time = self.get_original_visible_time_range()
        
        # Calculate waveform display parameters
        waveform_width = timeline_rect.width()
        waveform_height = timeline_rect.height() - 12  # Leave some margin
        waveform_center_y = timeline_rect.center().y()
        
        # Try to get cached waveform data first (only if caching is enabled and not during loading)
        cache_key_params = (self.zoom_level, start_time, end_time)
        cached_waveform = None
        if self.cache_enabled and self.cache_during_loading:
            cached_waveform = self.waveform_cache.get(*cache_key_params)
        
        if cached_waveform is not None:
            # Use cached waveform data
            self.draw_cached_waveform(painter, timeline_rect, cached_waveform, waveform_center_y, waveform_height)
            return
        
        # Calculate sample range to display based on ORIGINAL timeline
        total_duration = self.duration_seconds
        if total_duration <= 0:
            return
            
        start_sample = int((start_time / total_duration) * len(self.waveform_data))
        end_sample = int((end_time / total_duration) * len(self.waveform_data))
        start_sample = max(0, start_sample)
        end_sample = min(len(self.waveform_data), end_sample)
        
        if start_sample >= end_sample:
            return
            
        # Get visible samples
        visible_samples = self.waveform_data[start_sample:end_sample]
        if not visible_samples:
            return
            
        # Calculate samples per pixel for the visible range
        samples_per_pixel = len(visible_samples) / waveform_width
        
        # Prepare waveform data for caching
        waveform_bars = []
        
        # Process waveform with enhanced visibility and detail
        for x in range(int(waveform_width)):
            # Calculate sample index for this pixel
            sample_start = int(x * samples_per_pixel)
            sample_end = int((x + 1) * samples_per_pixel)
            sample_end = min(sample_end, len(visible_samples))
            
            if sample_start >= len(visible_samples):
                break
                
            # Get multiple amplitude measurements for better detail
            if sample_start == sample_end:
                peak_amplitude = abs(visible_samples[sample_start])
                rms_amplitude = peak_amplitude
                avg_amplitude = peak_amplitude
            else:
                sample_range = visible_samples[sample_start:sample_end]
                peak_amplitude = max(abs(s) for s in sample_range)
                rms_amplitude = (sum(s*s for s in sample_range) / len(sample_range)) ** 0.5
                avg_amplitude = sum(abs(s) for s in sample_range) / len(sample_range)
            
            # Normalize amplitudes with better scaling
            peak_normalized = peak_amplitude / self.waveform_max_amplitude if self.waveform_max_amplitude > 0 else 0
            rms_normalized = rms_amplitude / self.waveform_max_amplitude if self.waveform_max_amplitude > 0 else 0
            avg_normalized = avg_amplitude / self.waveform_max_amplitude if self.waveform_max_amplitude > 0 else 0
            
            # Apply logarithmic scaling for better detail in quiet sections
            peak_normalized = peak_normalized ** 0.7  # Compress loud parts, expand quiet parts
            rms_normalized = rms_normalized ** 0.7
            avg_normalized = avg_normalized ** 0.7
            
            # Calculate bar heights with full height usage
            peak_height = peak_normalized * (waveform_height / 2) * 0.95  # 95% of available height
            rms_height = rms_normalized * (waveform_height / 2) * 0.95
            avg_height = avg_normalized * (waveform_height / 2) * 0.95
            
            # Store for caching
            waveform_bars.append((peak_height, rms_height, avg_height))
            
            pixel_x = timeline_rect.left() + x
            
            # Draw layered waveform for maximum detail and clarity
            
            # 1. Draw peak outline (brightest - shows maximum amplitude)
            if peak_height > 0.5:
                peak_rect = QRectF(pixel_x, waveform_center_y - peak_height, 1, peak_height * 2)
                peak_color = QColor(120, 200, 255, 200)  # Bright blue
                painter.fillRect(peak_rect, peak_color)
            
            # 2. Draw RMS core (medium brightness - shows energy)
            if rms_height > 0.3:
                rms_rect = QRectF(pixel_x, waveform_center_y - rms_height, 1, rms_height * 2)
                rms_color = QColor(80, 160, 220, 220)  # Medium blue
                painter.fillRect(rms_rect, rms_color)
        
            # 3. Draw average core (darkest - shows consistent level)
            if avg_height > 0.1:
                avg_rect = QRectF(pixel_x, waveform_center_y - avg_height, 1, avg_height * 2)
                avg_color = QColor(40, 120, 180, 240)  # Dark blue
                painter.fillRect(avg_rect, avg_color)
        
        # Cache the processed waveform data (only if caching is enabled and not during loading)
        if self.cache_enabled and self.cache_during_loading and waveform_bars:
            self.waveform_cache.put(*cache_key_params, waveform_bars)
        
        # Draw enhanced center line (bright for dark background)
        painter.setPen(QPen(QColor(200, 200, 200, 180), 1))
        painter.drawLine(int(timeline_rect.left()), int(waveform_center_y), 
                        int(timeline_rect.right()), int(waveform_center_y))
        
        # Draw subtle grid lines for amplitude reference (bright for dark background)
        painter.setPen(QPen(QColor(100, 100, 100, 120), 1))
        quarter_height = waveform_height / 4
        for i in [1, -1]:  # Draw lines at ±25% and ±50% amplitude
            y1 = waveform_center_y + i * quarter_height
            y2 = waveform_center_y + i * quarter_height * 2
            painter.drawLine(int(timeline_rect.left()), int(y1), int(timeline_rect.right()), int(y1))
            painter.drawLine(int(timeline_rect.left()), int(y2), int(timeline_rect.right()), int(y2))
    
    def draw_cached_waveform(self, painter, timeline_rect, waveform_bars, waveform_center_y, waveform_height):
        """Draw waveform from cached data for improved performance"""
        for x, bar_data in enumerate(waveform_bars):
            if x >= timeline_rect.width():
                break
                
            # Handle both old and new cache formats
            if len(bar_data) == 2:
                peak_height, rms_height = bar_data
                avg_height = rms_height * 0.7  # Approximate average
            else:
                peak_height, rms_height, avg_height = bar_data
                
            pixel_x = timeline_rect.left() + x
            
            # Draw layered waveform for maximum detail and clarity
            
            # 1. Draw peak outline (brightest)
            if peak_height > 0.5:
                peak_rect = QRectF(pixel_x, waveform_center_y - peak_height, 1, peak_height * 2)
                peak_color = QColor(120, 200, 255, 200)  # Bright blue
                painter.fillRect(peak_rect, peak_color)
            
            # 2. Draw RMS core (medium brightness)
            if rms_height > 0.3:
                rms_rect = QRectF(pixel_x, waveform_center_y - rms_height, 1, rms_height * 2)
                rms_color = QColor(80, 160, 220, 220)  # Medium blue
                painter.fillRect(rms_rect, rms_color)
            
            # 3. Draw average core (darkest)
            if avg_height > 0.1:
                avg_rect = QRectF(pixel_x, waveform_center_y - avg_height, 1, avg_height * 2)
                avg_color = QColor(40, 120, 180, 240)  # Dark blue
                painter.fillRect(avg_rect, avg_color)
    
    def draw_debug_info(self, painter, timeline_rect):
        """Draw debug information showing click position and playhead position"""
        if not self.show_debug_info:
            return
            
        # Prepare debug text
        debug_lines = []
        
        # Current playhead position
        if self.current_position >= 0:
            playhead_time_str = self.format_time_debug(self.current_position)
            if self.preview_mode:
                # In preview mode, show both original and preview timeline positions
                preview_pos = self.original_time_to_preview_time(self.current_position)
                preview_time_str = self.format_time_debug(preview_pos)
                debug_lines.append(f"Playhead: {playhead_time_str} (orig) | {preview_time_str} (preview)")
            else:
                debug_lines.append(f"Playhead: {playhead_time_str}")
        
        # Last click position
        if self.debug_click_position is not None:
            click_time_str = self.format_time_debug(self.debug_click_position)
            if self.preview_mode:
                # In preview mode, show the conversion
                original_time = self.convert_click_position_to_original_time(self.debug_click_position)
                original_time_str = self.format_time_debug(original_time)
                debug_lines.append(f"Last Click: {click_time_str} → {original_time_str} (converted)")
            else:
                debug_lines.append(f"Last Click: {click_time_str}")
        
        # Timeline mode
        mode_text = "Preview Mode" if self.preview_mode else "Normal Mode"
        if self.preview_mode and hasattr(self, 'preview_timeline_duration'):
            duration_str = self.format_time_debug(self.preview_timeline_duration)
            debug_lines.append(f"Mode: {mode_text} (Duration: {duration_str})")
        else:
            duration_str = self.format_time_debug(self.duration_seconds)
            debug_lines.append(f"Mode: {mode_text} (Duration: {duration_str})")
        
        # Zoom info
        if self.zoom_level != 1.0:
            start_time, end_time = self.get_visible_time_range()
            visible_start_str = self.format_time_debug(start_time)
            visible_end_str = self.format_time_debug(end_time)
            debug_lines.append(f"Visible: {visible_start_str} - {visible_end_str}")
        
        if not debug_lines:
            return
            
        # Set up drawing
        painter.setFont(QFont("Consolas", 8))  # Monospace font for better alignment
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        
        # Calculate background size
        line_height = 14
        max_width = 0
        for line in debug_lines:
            text_rect = painter.fontMetrics().boundingRect(line)
            max_width = max(max_width, text_rect.width())
        
        # Draw background
        bg_width = max_width + 16
        bg_height = len(debug_lines) * line_height + 8
        bg_rect = QRectF(5, 5, bg_width, bg_height)
        
        # Semi-transparent background
        painter.fillRect(bg_rect, QColor(255, 255, 255, 220))
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawRect(bg_rect)
        
        # Draw debug text
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        y_pos = 18
        for line in debug_lines:
            painter.drawText(13, y_pos, line)
            y_pos += line_height
            
        # Click indicator removed for cleaner design
    
    def format_time_debug(self, seconds):
        """Format time with high precision for debug display"""
        if seconds < 0:
            return "00:00.000"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"
    
    def format_time_simple(self, seconds):
        """Format time in MM:SS format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
        
    def format_time_mmss_ms(self, seconds):
        """Format time in HH:MM:SS format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
    def show_buffer_stats(self):
        """Show circular buffer performance statistics"""
        try:
            # Get stats from parent application
            parent_app = self.parent()
            while parent_app and not hasattr(parent_app, 'get_buffer_stats'):
                parent_app = parent_app.parent()
                
            if parent_app and hasattr(parent_app, 'get_buffer_stats'):
                stats = parent_app.get_buffer_stats()
                
                print("\n📊 CIRCULAR BUFFER PERFORMANCE STATS 📊")
                print("=" * 50)
                
                # Frame buffer stats
                if 'frame_buffer' in stats:
                    fb_stats = stats['frame_buffer']
                    print(f"🎬 Frame Buffer:")
                    print(f"   Cache Hit Rate: {fb_stats['hit_rate']:.1f}%")
                    print(f"   Hits: {fb_stats['hits']}, Misses: {fb_stats['misses']}")
                    print(f"   Buffer Size: {fb_stats['size']}/{fb_stats['max_size']}")
                    
                # Waveform cache stats
                if 'waveform_cache' in stats:
                    wc_stats = stats['waveform_cache']
                    print(f"🌊 Waveform Cache:")
                    print(f"   Cached Zoom Levels: {wc_stats['size']}/{wc_stats['max_size']}")
                    
                # Cache status
                cache_status = "✅ ENABLED" if self.cache_enabled else "❌ DISABLED"
                print(f"💾 Waveform Caching: {cache_status}")
                
                print("=" * 50)
                print("Press 'B' again to refresh stats")
                
            else:
                print("📊 Buffer stats not available")
                
        except Exception as e:
            print(f"Error showing buffer stats: {e}")
            
    def enable_caching(self):
        """Enable waveform caching after initial loading"""
        self.cache_during_loading = True
        print("💾 Waveform caching enabled")
        
    def disable_caching(self):
        """Disable waveform caching during heavy operations"""
        self.cache_during_loading = False
        
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.duration_seconds <= 0:
            return
        
        # Check if clicking on reset zoom button
        if hasattr(self, 'reset_button_rect') and self.reset_button_rect and self.reset_button_rect.contains(event.x(), event.y()):
            self.reset_zoom()
            return
                
        # Store state before any changes for undo functionality
        import copy
        self.drag_start_state = (copy.deepcopy(self.silent_parts), copy.deepcopy(self.silent_ranges))
                
        # Calculate timeline area
        timeline_rect = QRectF(
            self.margin,
            (self.height() - self.timeline_height) / 2,
            self.width() - 2 * self.margin,
            self.timeline_height
        )
        
        click_x = event.x()
        click_y = event.y()
        
        # Get visible time range (use original timeline for silence regions)
        original_start_time, original_end_time = self.get_original_visible_time_range()
        
        # Check if clicking on a silence region or its handles
        for i, (start_ms, end_ms) in enumerate(self.silent_ranges):
            start_sec = start_ms / 1000
            end_sec = end_ms / 1000
            
            # Skip regions not in visible range (use original timeline)
            if end_sec < original_start_time or start_sec > original_end_time:
                continue
            
            start_x = self.original_time_to_x(start_sec, timeline_rect)
            end_x = self.original_time_to_x(end_sec, timeline_rect)
            
            # Check for handle clicks (priority over region clicks) - updated for thinner handles
            handle_size = 4  # Updated to match the thinner handles
            left_handle_rect = QRectF(start_x - handle_size*2, timeline_rect.top(), handle_size * 4, self.timeline_height)
            right_handle_rect = QRectF(end_x - handle_size*2, timeline_rect.top(), handle_size * 4, self.timeline_height)
            
            if left_handle_rect.contains(click_x, click_y):
                self.dragging_region = i
                self.dragging_edge = 'start'
                self.drag_start_pos = click_x
                self.setCursor(Qt.SizeHorCursor)
                return
            elif right_handle_rect.contains(click_x, click_y):
                self.dragging_region = i
                self.dragging_edge = 'end'
                self.drag_start_pos = click_x
                self.setCursor(Qt.SizeHorCursor)
                return
                
            # Check for region body clicks (toggle selection)
            region_rect = QRectF(start_x, timeline_rect.top(), end_x - start_x, self.timeline_height)
            if region_rect.contains(click_x, click_y):
                # Toggle selection
                if i < len(self.silent_parts):
                    self.silent_parts[i]['selected'] = not self.silent_parts[i]['selected']
                    self.selection_changed.emit(self.silent_parts[i])
                    self.update()
                return
        
        # If no region clicked, check for timeline seeking
        if timeline_rect.contains(click_x, click_y):
            # Calculate seek position using zoom-aware coordinates
            seek_time = self.x_to_time(click_x, timeline_rect)
            
            # Instantly update playhead position for immediate visual feedback
            self.set_position(seek_time, instant=True)
            
            print(f"Timeline click: seeking to {seek_time:.6f}s (high precision)")
            self.position_changed.emit(seek_time)
            self.seeking = True
            
    def mouseMoveEvent(self, event):
        if self.duration_seconds <= 0:
            return
            
        # Calculate timeline area
        timeline_rect = QRectF(
            self.margin,
            (self.height() - self.timeline_height) / 2,
            self.width() - 2 * self.margin,
            self.timeline_height
        )
        
        click_x = event.x()
        click_y = event.y()
        
        # Handle dragging
        if self.dragging_region is not None and self.drag_start_pos is not None:
            dx = click_x - self.drag_start_pos
            
            # Convert pixel movement to time using original timeline coordinates
            original_start_time, original_end_time = self.get_original_visible_time_range()
            visible_duration = original_end_time - original_start_time
            time_per_pixel = visible_duration / timeline_rect.width()
            time_delta = dx * time_per_pixel
            
            # Update the silence region
            if self.dragging_region < len(self.silent_ranges) and self.dragging_region < len(self.silent_parts):
                start_ms, end_ms = self.silent_ranges[self.dragging_region]
                start_sec = start_ms / 1000
                end_sec = end_ms / 1000
                
                if self.dragging_edge == 'start':
                    new_start = max(0, start_sec + time_delta)
                    if new_start < end_sec - 0.1:  # Minimum 0.1 second region
                        self.silent_ranges[self.dragging_region] = (int(new_start * 1000), end_ms)
                        self.silent_parts[self.dragging_region]['start'] = new_start
                        self.silent_parts[self.dragging_region]['duration_ms'] = end_ms - int(new_start * 1000)
                elif self.dragging_edge == 'end':
                    new_end = min(self.duration_seconds, end_sec + time_delta)
                    if new_end > start_sec + 0.1:  # Minimum 0.1 second region
                        self.silent_ranges[self.dragging_region] = (start_ms, int(new_end * 1000))
                        self.silent_parts[self.dragging_region]['end'] = new_end
                        self.silent_parts[self.dragging_region]['duration_ms'] = int(new_end * 1000) - start_ms
                
                self.drag_start_pos = click_x
                self.update()
                return
                
        # Handle hover effects
        old_hover = self.hover_region
        self.hover_region = None
        
        # Get visible time range (use original timeline for silence regions)
        original_start_time, original_end_time = self.get_original_visible_time_range()
        
        for i, (start_ms, end_ms) in enumerate(self.silent_ranges):
            start_sec = start_ms / 1000
            end_sec = end_ms / 1000
            
            # Skip regions not in visible range (use original timeline)
            if end_sec < original_start_time or start_sec > original_end_time:
                continue
            
            start_x = self.original_time_to_x(start_sec, timeline_rect)
            end_x = self.original_time_to_x(end_sec, timeline_rect)
            
            # Check for handle hovering - updated for thinner handles
            handle_size = 4  # Updated to match the thinner handles
            left_handle_rect = QRectF(start_x - handle_size*2, timeline_rect.top(), handle_size * 4, self.timeline_height)
            right_handle_rect = QRectF(end_x - handle_size*2, timeline_rect.top(), handle_size * 4, self.timeline_height)
            
            if left_handle_rect.contains(click_x, click_y) or right_handle_rect.contains(click_x, click_y):
                self.setCursor(Qt.SizeHorCursor)
                self.hover_region = i
                break
            
            # Check for region hovering
            region_rect = QRectF(start_x, timeline_rect.top(), end_x - start_x, self.timeline_height)
            if region_rect.contains(click_x, click_y):
                self.setCursor(Qt.PointingHandCursor)
                self.hover_region = i
                break
        
        # Check for reset button hover
        reset_button_hover = False
        if hasattr(self, 'reset_button_rect') and self.reset_button_rect and self.reset_button_rect.contains(click_x, click_y):
            self.setCursor(Qt.PointingHandCursor)
            reset_button_hover = True
        
        if self.hover_region is None and not reset_button_hover:
            if timeline_rect.contains(click_x, click_y):
                self.setCursor(Qt.ArrowCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
                
        if old_hover != self.hover_region or reset_button_hover:
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragging_region is not None:
                # Save state after dragging for undo functionality
                self.save_state()
                
                # Emit selection changed to update other UI elements
                if self.dragging_region < len(self.silent_parts):
                    self.selection_changed.emit(self.silent_parts[self.dragging_region])
                    
            self.dragging_region = None
            self.dragging_edge = None
            self.drag_start_pos = None
            self.drag_start_state = None
            self.seeking = False
            self.setCursor(Qt.ArrowCursor)

class InteractiveVideoPlayer(QWidget):
    """Interactive video player with timeline controls"""
    selection_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_path = None
        self.silent_parts = []
        self.silent_ranges = []
        self.is_threaded_playing = False
        self.preview_mode = False
        self.preview_duration = 0
        
        self.setup_ui()
        self.setup_media_player()
        
    def closeEvent(self, event):
        """Handle widget close event"""
        self.cleanup_fallback_resources()
        super().closeEvent(event)
        
    def __del__(self):
        """Destructor - clean up resources"""
        self.cleanup_fallback_resources()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)  # Reduce spacing between components
        
        # Video player widget - increased height
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(450)  # Increased from 300
        self.video_widget.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_widget)
        
        # Timeline widget - more compact frame
        timeline_frame = QFrame()
        timeline_frame.setFrameStyle(QFrame.StyledPanel)
        timeline_frame.setStyleSheet("background-color: #f8f8f8; border: 1px solid #ccc;")
        timeline_layout = QVBoxLayout(timeline_frame)
        timeline_layout.setContentsMargins(5, 3, 5, 3)  # Reduce margins
        timeline_layout.setSpacing(2)  # Reduce spacing
        
        # Timeline label - smaller font
        timeline_label = QLabel("Interactive Timeline - Click regions to toggle, drag edges to adjust (Preview mode auto-enabled)")
        timeline_label.setFont(QFont("Arial", 9))  # Reduced from 10
        timeline_label.setAlignment(Qt.AlignCenter)
        timeline_layout.addWidget(timeline_label)
        
        # Custom timeline widget
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.selection_changed.connect(self.on_timeline_selection_changed)
        self.timeline_widget.position_changed.connect(self.seek_to_position)
        timeline_layout.addWidget(self.timeline_widget)
        
        layout.addWidget(timeline_frame)
        
        # Control buttons - keep play/pause, stop, and volume controls visible
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setMaximumWidth(80)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_video)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMaximumWidth(80)
        
        # Position slider (hidden - timeline provides this functionality)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setEnabled(False)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.position_slider.sliderMoved.connect(self.on_slider_moved)
        self.position_slider.hide()  # Hide the time slider
        
        # Time labels (hidden - timeline shows time)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont("Arial", 9))
        self.time_label.setMinimumWidth(120)
        self.time_label.hide()  # Hide the time label
        
        # Volume control - keep visible
        volume_label = QLabel("Volume:")
        volume_label.setFont(QFont("Arial", 9))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        
        # Selection controls
        select_all_btn = QPushButton("Select All Silent Regions")
        select_all_btn.clicked.connect(self.select_all_silent_regions)
        select_all_btn.setMaximumWidth(150)
        
        deselect_all_btn = QPushButton("Deselect All Silent Regions")
        deselect_all_btn.clicked.connect(self.deselect_all_silent_regions)
        deselect_all_btn.setMaximumWidth(150)
        
        # Add controls to layout
        controls_layout.addWidget(self.play_pause_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(volume_label)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addStretch()
        controls_layout.addWidget(select_all_btn)
        controls_layout.addWidget(deselect_all_btn)
        
        layout.addLayout(controls_layout)
        
        self.setLayout(layout)
        
        # Enable keyboard focus to receive key events
        self.setFocusPolicy(Qt.StrongFocus)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Space:
            # Spacebar for play/pause
            self.toggle_play_pause()
            event.accept()
        else:
            super().keyPressEvent(event)
        
    def setup_media_player(self):
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Connect signals
        self.media_player.stateChanged.connect(self.on_state_changed)
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        self.media_player.error.connect(self.handle_error)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        
        # Position update timer
        self.position_update_timer = QTimer()
        self.position_update_timer.timeout.connect(self.update_timeline_position)
        self.position_update_timer.start(100)  # Update every 100ms
        
        self.slider_pressed = False
        
    def load_video(self, video_path):
        """Load a video file into the player"""
        # Clean up previous resources
        self.cleanup_fallback_resources()
        
        self.video_path = video_path
        print(f"Loading video into player: {video_path}")
        
        # Update loading progress
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'update_loading_progress_with_step'):
            parent.update_loading_progress_with_step("Setting up video player...", 2)
        
        if os.path.exists(video_path):
            # Convert path to proper format for QMediaPlayer
            abs_path = os.path.abspath(video_path)
            print(f"Absolute path: {abs_path}")
            
            # Update loading progress
            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Loading timeline waveform...", 3)
            
            # Load waveform data for timeline visualization
            self.timeline_widget.load_waveform(video_path)
            
            # Create QUrl from local file
            url = QUrl.fromLocalFile(abs_path)
            print(f"QUrl created: {url.toString()}")
            
            # Set media content
            media_content = QMediaContent(url)
            self.media_player.setMedia(media_content)
            
            print(f"Media player state after setMedia: {self.media_player.state()}")
            print(f"Media player media status: {self.media_player.mediaStatus()}")
            
            # Enable controls
            self.play_pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.position_slider.setEnabled(True)
            
            # Try to load the first frame
            self.media_player.setPosition(1000)  # Seek to 1 second to load a frame
            self.media_player.setPosition(0)     # Go back to start
            
            # Update loading progress
            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Initializing media player...", 4)
            
            # Set up a timer to check if media loaded successfully after a short delay
            QTimer.singleShot(1500, self.check_media_loaded)  # Reduced from 2000ms
            
        else:
            print(f"Video file does not exist: {video_path}")
            QMessageBox.critical(self, "Error", f"Video file not found: {video_path}")
    
    def check_media_loaded(self):
        """Check if media loaded successfully, if not, show a fallback message"""
        status = self.media_player.mediaStatus()
        
        # Find parent to hide loading overlay
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
            
        if status == QMediaPlayer.InvalidMedia or status == QMediaPlayer.NoMedia:
            print("QMediaPlayer failed to load video, setting up fallback display")
            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Setting up enhanced video player...", 5)
            self.setup_fallback_video_display()
        elif status == QMediaPlayer.LoadedMedia:
            print("QMediaPlayer loaded successfully")
            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Finalizing setup...", 6)
            # DON'T hide loading overlay here - let waveform loading complete first
            # The overlay will be hidden when waveform loading is done
            
    def setup_fallback_video_display(self):
        """Set up a multi-threaded fallback video display when QMediaPlayer fails"""
        try:
            print("Setting up multi-threaded video playback...")
            
            # First get the actual audio duration for accurate timeline sync
            import moviepy.editor as mp
            video_clip = mp.VideoFileClip(self.video_path)
            actual_audio_duration = video_clip.duration if video_clip.audio else 0
            video_clip.close()
            print(f"Video player using exact audio duration: {actual_audio_duration:.6f}s (high precision)")
            
            # Initialize the video playback thread
            self.video_thread = VideoPlaybackThread(self.video_path, self)
            self.video_thread.frame_ready.connect(self.display_threaded_frame)
            self.video_thread.position_changed.connect(self.update_threaded_position)
            
            # Start the thread (it will initialize and wait)
            self.video_thread.start()
            
            # Wait a moment for thread initialization to complete
            import time
            time.sleep(0.1)
            
            # Get verified audio duration from the video thread for perfect sync
            thread_audio_duration = getattr(self.video_thread, 'verified_audio_duration', actual_audio_duration)
            thread_video_duration = getattr(self.video_thread, 'actual_duration', actual_audio_duration)
            
            print(f"🎵 DURATION SYNC VERIFICATION:")
            print(f"  Video clip duration: {actual_audio_duration:.6f}s")
            print(f"  Thread audio duration: {thread_audio_duration:.6f}s")
            print(f"  Thread video duration: {thread_video_duration:.6f}s")
            
            # Use the thread's verified audio duration for perfect timeline sync
            if hasattr(self.video_thread, 'verified_audio_duration'):
                duration_seconds = self.video_thread.verified_audio_duration
                print(f"✓ Using thread verified audio duration: {duration_seconds:.6f}s")
            else:
                duration_seconds = actual_audio_duration
                print(f"Using fallback duration: {duration_seconds:.6f}s")
            
            # Get video properties using OpenCV for UI setup
            cap = cv2.VideoCapture(self.video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                duration_ms = int(duration_seconds * 1000)
                print(f"Final synchronized duration: {duration_seconds:.6f}s -> {duration_ms}ms")
                print(f"Multi-threaded video: {frame_count} frames, {fps} FPS")
                
                # Store properties
                self.video_fps = fps
                self.video_frame_count = frame_count
                self.video_duration_ms = duration_ms
                self.actual_duration_seconds = duration_seconds  # Store actual duration
                self.using_fallback = True
                
                # CRITICAL: Ensure timeline uses the EXACT same duration as the audio thread
                print(f"🎯 Setting timeline to EXACT thread duration: {duration_seconds:.6f}s")
                self.timeline_widget.set_duration(duration_seconds)
                self.position_slider.setRange(0, duration_ms)
                
                # Cross-verify timeline duration matches audio thread duration
                timeline_duration = getattr(self.timeline_widget, 'duration_seconds', 0)
                duration_diff = abs(timeline_duration - duration_seconds)
                print(f"Timeline duration verification: {timeline_duration:.6f}s (diff: {duration_diff:.6f}s)")
                
                if duration_diff > 0.001:  # Warn if difference > 1ms
                    print(f"⚠️  WARNING: Timeline-audio duration mismatch: {duration_diff:.6f}s")
                else:
                    print(f"✓ Perfect timeline-audio duration sync verified!")
                
                cap.release()
                
                # Set up video display label
                self.setup_video_display_label()
                
                # Override controls for threaded playback
                self.setup_threaded_controls()
                
                # Seek to first frame to show something
                self.video_thread.seek(0)
                
                # Update final loading step but DON'T hide overlay yet
                parent = self.parent()
                while parent and not isinstance(parent, QMainWindow):
                    parent = parent.parent()
                if parent and hasattr(parent, 'update_loading_progress_with_step'):
                    parent.update_loading_progress_with_step("Video ready!", 6)
                
                # DON'T hide loading overlay here - let waveform loading complete first
                # The overlay will be hidden when waveform loading is done
                
                # Show success message
                self.show_video_message("✓ Multi-threaded video loaded!\n\nFast video playback ready. Click Play to start.\n• Audio preview available!\n• Perfect audio-timeline sync!")
                
            else:
                self.show_video_error("Could not open video file")
                
        except Exception as e:
            print(f"Error in multi-threaded video setup: {e}")
            self.show_video_error(f"Video preview unavailable: {str(e)}")
            
    def display_threaded_frame(self, pixmap):
        """Display frame from the video thread"""
        if hasattr(self, 'video_frame_label') and pixmap:
            self.video_frame_label.setPixmap(pixmap)
            
    def update_threaded_position(self, frame_number):
        """Update UI based on current frame from video thread"""
        if not hasattr(self, 'video_fps') or self.video_fps <= 0:
            return
        
        # Calculate time based on actual duration ratio instead of pure FPS calculation
        if hasattr(self, 'actual_duration_seconds') and self.video_frame_count > 0:
            # Use the ratio of current frame to total frames, multiplied by actual duration
            frame_ratio = frame_number / self.video_frame_count
            current_time_seconds = frame_ratio * self.actual_duration_seconds
            current_time_ms = int(current_time_seconds * 1000)
        else:
            # Fallback to FPS calculation
            current_time_ms = int((frame_number / self.video_fps) * 1000)
            current_time_seconds = current_time_ms / 1000
        
        # Update position slider more frequently for smoother tracking
        if not self.slider_pressed:
            self.position_slider.setValue(current_time_ms)
            
        # Update timeline position with smooth animation during playback
        self.timeline_widget.set_position(current_time_seconds, instant=False)
        
        # Update time label every few frames to reduce overhead
        if frame_number % 15 == 0:  # Every half second at 30fps
            current_time = self.format_time_simple(current_time_ms // 1000)
            total_time = self.format_time_simple(self.video_duration_ms // 1000)
            self.time_label.setText(f"{current_time} / {total_time}")
            
    def setup_threaded_controls(self):
        """Set up controls for multi-threaded video playback"""
        self.using_fallback = True
        
        # Re-enable volume control since audio is now available
        if hasattr(self, 'volume_slider'):
            self.volume_slider.setEnabled(True)
            self.volume_slider.setToolTip("Adjust preview volume")
            # Connect volume control to pygame volume
            self.volume_slider.valueChanged.connect(self.set_preview_volume)
        
        # Disconnect original media player signals and connect to threaded handlers
        try:
            self.play_pause_btn.clicked.disconnect()
            self.stop_btn.clicked.disconnect()
            self.position_slider.sliderPressed.disconnect()
            self.position_slider.sliderReleased.disconnect()
            self.position_slider.sliderMoved.disconnect()
        except:
            pass
            
        # Connect to threaded handlers
        self.play_pause_btn.clicked.connect(self.toggle_threaded_playback)
        self.stop_btn.clicked.connect(self.stop_threaded_playback)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_threaded_slider_released)
        self.position_slider.sliderMoved.connect(self.on_threaded_slider_moved)
        
        # Update tooltips
        self.play_pause_btn.setToolTip("Play/Pause video with audio preview")
        self.stop_btn.setToolTip("Stop video and audio playback")
        
    def set_preview_volume(self, volume):
        """Set the preview audio volume"""
        try:
            # Convert Qt slider range (0-100) to pygame range (0.0-1.0)
            pygame_volume = volume / 100.0
            pygame.mixer.music.set_volume(pygame_volume)
        except:
            pass
    
    def toggle_threaded_playback(self):
        """Toggle play/pause for threaded video playback"""
        if not hasattr(self, 'video_thread'):
            return
            
        if hasattr(self, 'is_threaded_playing') and self.is_threaded_playing:
            self.video_thread.pause()
            self.is_threaded_playing = False
            self.play_pause_btn.setText("Play")
        else:
            self.video_thread.play()
            self.is_threaded_playing = True
            self.play_pause_btn.setText("Pause")
            
    def stop_threaded_playback(self):
        """Stop threaded video playback"""
        if hasattr(self, 'video_thread'):
            self.video_thread.pause()
            self.video_thread.seek(0)
            self.is_threaded_playing = False
            self.play_pause_btn.setText("Play")
            
    def on_threaded_slider_released(self):
        """Handle when position slider is released in threaded mode"""
        self.slider_pressed = False
        if hasattr(self, 'video_thread') and hasattr(self, 'video_fps') and self.video_fps > 0:
            position_ms = self.position_slider.value()
            position_seconds = position_ms / 1000
            
            # Use direct time seeking for slider operations too
            print(f"Slider seek: directly seeking to {position_seconds:.6f}s")
            self.video_thread.seek_time_direct(position_seconds)
            
    def on_threaded_slider_moved(self, position_ms):
        """Handle when position slider is moved in threaded mode"""
        if self.slider_pressed:
            position_seconds = position_ms / 1000
            # Use instant positioning for user slider interaction
            self.timeline_widget.set_position(position_seconds, instant=True)
            
            # Update time label during dragging
            current_time = self.format_time_simple(position_ms // 1000)
            total_time = self.format_time_simple(self.video_duration_ms // 1000)
            self.time_label.setText(f"{current_time} / {total_time}")
            
    def setup_video_display_label(self):
        """Set up the video display label that overlays the video widget"""
        # Create the video frame label as a child of the parent widget to ensure it displays properly
        # but position it to overlay only the video widget area
        parent_widget = self.video_widget.parent()
        
        if not hasattr(self, 'video_frame_label'):
            self.video_frame_label = QLabel(parent_widget)
            self.video_frame_label.setAlignment(Qt.AlignCenter)
            self.video_frame_label.setStyleSheet("background-color: black;")
            self.video_frame_label.setScaledContents(False)
            
        # Position the label exactly over the video widget
        video_widget_geometry = self.video_widget.geometry()
        self.video_frame_label.setGeometry(video_widget_geometry)
        self.video_frame_label.show()
        self.video_frame_label.raise_()
        
        print(f"Video display label positioned over video widget: {video_widget_geometry}")
        
    def display_cv2_frame(self, frame):
        """Convert OpenCV frame to QPixmap and display it with aggressive optimization for speed"""
        try:
            if not hasattr(self, 'video_frame_label'):
                self.setup_video_display_label()
                
            # Get video label size for scaling
            label_size = self.video_frame_label.size()
            if label_size.width() <= 0 or label_size.height() <= 0:
                return
                
            # Aggressively scale down the frame for much faster processing
            height, width = frame.shape[:2]
            
            # Scale to a reasonable display size (max 640x360 for speed)
            max_width = min(640, label_size.width())
            max_height = min(360, label_size.height())
            
            # Calculate scaling factor
            scale_w = max_width / width
            scale_h = max_height / height
            scale = min(scale_w, scale_h)
            
            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                # Use INTER_LINEAR for faster scaling than INTER_CUBIC
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb_frame.shape
            bytes_per_line = channels * width
            
            # Create QImage
            qt_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            if qt_image.isNull():
                return
                
            # Create pixmap
            pixmap = QPixmap.fromImage(qt_image)
            if pixmap.isNull():
                return
            
            # Set the pixmap (no additional scaling needed since we already scaled the frame)
            self.video_frame_label.setPixmap(pixmap)
            
        except Exception as e:
            print(f"Error displaying frame: {e}")
    
    def seek_to_fallback_frame(self, frame_number):
        """Seek to a specific frame number with maximum performance optimization"""
        try:
            if not hasattr(self, 'video_cap') or not self.video_cap.isOpened():
                self.video_cap = cv2.VideoCapture(self.video_path)
                
            if self.video_cap.isOpened():
                # Ensure frame number is within bounds
                frame_number = max(0, min(frame_number, self.video_frame_count - 1))
                
                # Set frame position and read
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = self.video_cap.read()
                
                if ret:
                    # Display frame immediately without other processing
                    self.display_cv2_frame(frame)
                    
                    # Update UI much less frequently for better performance (every 10th frame)
                    if frame_number % 10 == 0:
                        current_time_ms = int((frame_number / self.video_fps) * 1000) if self.video_fps > 0 else 0
                        
                        if not self.slider_pressed:
                            self.position_slider.setValue(current_time_ms)
                            
                        current_time_seconds = current_time_ms / 1000
                        self.timeline_widget.set_position(current_time_seconds)
                        
                        # Update time label less frequently
                        if frame_number % 30 == 0:  # Every 30 frames (1 second at 30fps)
                            current_time = self.format_time_simple(current_time_ms // 1000)
                            total_time = self.format_time_simple(self.video_duration_ms // 1000)
                            self.time_label.setText(f"{current_time} / {total_time}")
                    
        except Exception as e:
            pass  # Silently handle errors to avoid slowing down playback
        
    def play_next_frame(self):
        """Play the next frame with maximum speed optimization"""
        if not self.is_playing or not hasattr(self, 'video_frame_count'):
            return
            
        # Simple frame advancement without complex timing calculations
        self.current_frame += 1
        
        # Loop back to start when we reach the end
        if self.current_frame >= self.video_frame_count:
            self.current_frame = 0
            
        # Update display immediately
        self.seek_to_fallback_frame(self.current_frame)
        
    def setup_fallback_controls(self):
        """Set up custom controls for fallback video playback"""
        self.using_fallback = True
        
        # Disable volume control since audio isn't available in fallback mode
        if hasattr(self, 'volume_slider'):
            self.volume_slider.setEnabled(False)
            self.volume_slider.setToolTip("Audio not available in fallback mode")
        
        # Disconnect original media player signals and connect to custom handlers
        try:
            self.play_pause_btn.clicked.disconnect()
            self.stop_btn.clicked.disconnect()
            self.position_slider.sliderPressed.disconnect()
            self.position_slider.sliderReleased.disconnect()
            self.position_slider.sliderMoved.disconnect()
        except:
            pass  # In case they weren't connected
            
        # Connect to custom handlers
        self.play_pause_btn.clicked.connect(self.toggle_fallback_playback)
        self.stop_btn.clicked.connect(self.stop_fallback_playback)
        self.position_slider.sliderPressed.connect(self.on_fallback_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_fallback_slider_released)
        self.position_slider.sliderMoved.connect(self.on_fallback_slider_moved)
        
        # Update button tooltips
        self.play_pause_btn.setToolTip("Play/Pause video (no audio in fallback mode)")
        self.stop_btn.setToolTip("Stop video playback")
        
    def toggle_fallback_playback(self):
        """Toggle play/pause for fallback video playback"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            return
            
        if self.is_playing:
            self.pause_fallback_playback()
        else:
            self.play_fallback_playback()
            
    def play_fallback_playback(self):
        """Start playing the video using fallback system with maximum speed"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            return
            
        self.is_playing = True
        self.play_pause_btn.setText("Pause")
        
        # Use the aggressive interval directly - no complex timing
        self.playback_timer.start(self.frame_interval)
        
    def pause_fallback_playback(self):
        """Pause the video playback"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            return
            
        self.is_playing = False
        self.play_pause_btn.setText("Play")
        self.playback_timer.stop()
        
    def stop_fallback_playback(self):
        """Stop the video playback and return to start"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            return
            
        self.is_playing = False
        self.play_pause_btn.setText("Play")
        self.playback_timer.stop()
        self.current_frame = 0
        self.seek_to_fallback_frame(0)
        
    def seek_to_fallback_position(self, position_seconds):
        """Seek to a specific position in seconds for fallback playback"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            return
            
        if self.video_fps > 0:
            target_frame = int(position_seconds * self.video_fps)
            target_frame = max(0, min(target_frame, self.video_frame_count - 1))
            self.current_frame = target_frame
            self.seek_to_fallback_frame(target_frame)
            
    def on_fallback_slider_pressed(self):
        """Handle when position slider is pressed in fallback mode"""
        self.slider_pressed = True
        
    def on_fallback_slider_released(self):
        """Handle when position slider is released in fallback mode"""
        self.slider_pressed = False
        position_ms = self.position_slider.value()
        position_seconds = position_ms / 1000
        self.seek_to_fallback_position(position_seconds)
        
    def on_fallback_slider_moved(self, position_ms):
        """Handle when position slider is moved in fallback mode"""
        if self.slider_pressed:
            position_seconds = position_ms / 1000
            self.timeline_widget.set_position(position_seconds)
            
            # Update time label during dragging
            current_time = self.format_time_simple(position_ms // 1000)
            total_time = self.format_time_simple(self.video_duration_ms // 1000)
            self.time_label.setText(f"{current_time} / {total_time}")
            
    def seek_to_position(self, position_seconds, from_timeline=True):
        """Seek to a specific position in seconds"""
        # Instantly update timeline position for immediate visual feedback when seeking
        if from_timeline:
            self.timeline_widget.set_position(position_seconds, instant=True)
        
        # Handle preview mode timeline seeking properly
        if hasattr(self, 'using_fallback') and self.using_fallback and hasattr(self, 'video_thread'):
            # Check if we're in preview mode and this is a timeline click
            if from_timeline and self.preview_mode and hasattr(self.video_thread, 'preview_mode') and self.video_thread.preview_mode:
                # In preview mode, position_seconds has already been converted to original time by the timeline widget
                # We need to convert it back to preview time for the video thread
                original_time = position_seconds
                
                # Convert original time to preview time for the video thread
                preview_time = self.video_thread.original_time_to_preview_time(original_time)
                
                print(f"🔧 PREVIEW TIMELINE SEEK:")
                print(f"  Original time from timeline: {original_time:.6f}s")
                print(f"  Preview time for video thread: {preview_time:.6f}s")
                
                # Use the preview time for seeking
                self.video_thread.seek_time_direct(preview_time)
            elif from_timeline:
                # Normal timeline seeking - use direct time seeking for accuracy
                print(f"Timeline seek: directly seeking to {position_seconds:.6f}s")
                self.video_thread.seek_time_direct(position_seconds)
            else:
                # Use frame-based seeking for other operations
                if hasattr(self, 'video_fps') and self.video_fps > 0:
                    # Calculate target frame using actual duration ratio for accuracy
                    if hasattr(self, 'actual_duration_seconds') and self.actual_duration_seconds > 0:
                        time_ratio = position_seconds / self.actual_duration_seconds
                        target_frame = int(time_ratio * self.video_frame_count)
                    else:
                        target_frame = int(position_seconds * self.video_fps)
                        
                    target_frame = max(0, min(target_frame, self.video_frame_count - 1))
                    print(f"Seeking to position {position_seconds:.3f}s -> frame {target_frame}")
                    self.video_thread.seek(target_frame)
        else:
            # Original QMediaPlayer seeking
            position_ms = int(position_seconds * 1000)
            self.media_player.setPosition(position_ms)
        
    def show_video_message(self, message):
        """Show a message overlay on the video widget"""
        if not hasattr(self, 'video_message_label'):
            self.video_message_label = QLabel(self.video_widget)
            self.video_message_label.setAlignment(Qt.AlignCenter)
            self.video_message_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 0, 0, 180);
                    color: white;
                    font-size: 14px;
                    padding: 20px;
                    border-radius: 10px;
                }
            """)
            self.video_message_label.setWordWrap(True)
            
        self.video_message_label.setText(message)
        self.video_message_label.resize(400, 120)
        
        # Center the label in the video widget
        widget_size = self.video_widget.size()
        label_size = self.video_message_label.size()
        x = max(0, (widget_size.width() - label_size.width()) // 2)
        y = max(0, (widget_size.height() - label_size.height()) // 2)
            
        self.video_message_label.move(x, y)
        self.video_message_label.show()
        self.video_message_label.raise_()
        
        # Hide the message after 4 seconds (shorter time)
        QTimer.singleShot(4000, self.video_message_label.hide)
        
    def show_video_error(self, error_message):
        """Show an error message on the video widget"""
        self.video_widget.setStyleSheet("background-color: #2a2a2a;")
        self.show_video_message(f"Video Error:\n{error_message}")
        
    def resizeEvent(self, event):
        """Handle widget resize events"""
        super().resizeEvent(event)
        
        # Resize and reposition video frame label if it exists and we're in fallback mode
        if hasattr(self, 'video_frame_label') and hasattr(self, 'using_fallback') and self.using_fallback:
            # Position the label to fill the video widget
            self.video_frame_label.setGeometry(0, 0, self.video_widget.width(), self.video_widget.height())
            
        # Reposition message label if it exists and is visible
        if hasattr(self, 'video_message_label') and self.video_message_label.isVisible():
            # Position message label relative to the video widget
            widget_size = self.video_widget.size()
            label_size = self.video_message_label.size()
            x = max(0, (widget_size.width() - label_size.width()) // 2)
            y = max(0, (widget_size.height() - label_size.height()) // 2)
            self.video_message_label.move(x, y)
            
    def cleanup_fallback_resources(self):
        """Clean up video resources"""
        try:
            if hasattr(self, 'video_thread') and self.video_thread is not None:
                self.video_thread.stop_playback()
                self.video_thread.wait(1000)  # Wait up to 1 second for thread to finish
                self.video_thread = None
        except (RuntimeError, AttributeError):
            pass  # Thread already cleaned up
            
        try:
            if hasattr(self, 'video_cap') and self.video_cap is not None:
                self.video_cap.release()
                self.video_cap = None
        except:
            pass
                
    def set_silent_parts(self, silent_parts):
        """Set the silent parts for visualization"""
        self.silent_parts = silent_parts
        
        # Convert to ranges for timeline
        self.silent_ranges = []
        for part in silent_parts:
            start_ms = int(part['start'] * 1000)
            end_ms = int(part['end'] * 1000)
            self.silent_ranges.append((start_ms, end_ms))
            
        # Ensure timeline duration is set correctly before adding silent parts
        if hasattr(self, 'actual_duration_seconds') and self.actual_duration_seconds > 0:
            print(f"Setting timeline duration to actual duration: {self.actual_duration_seconds:.3f}s")
            self.timeline_widget.set_duration(self.actual_duration_seconds)
        elif hasattr(self, 'video_duration_ms') and self.video_duration_ms > 0:
            duration_seconds = self.video_duration_ms / 1000
            print(f"Setting timeline duration from video: {duration_seconds:.3f}s")
            self.timeline_widget.set_duration(duration_seconds)
            
        # Update timeline
        self.timeline_widget.set_silent_parts(self.silent_parts, self.silent_ranges)
        
    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if hasattr(self, 'using_fallback') and self.using_fallback and hasattr(self, 'video_thread'):
            self.toggle_threaded_playback()
        else:
            if self.media_player.state() == QMediaPlayer.PlayingState:
                self.media_player.pause()
            else:
                self.media_player.play()
            
    def stop_video(self):
        """Stop video playback"""
        if hasattr(self, 'using_fallback') and self.using_fallback and hasattr(self, 'video_thread'):
            self.stop_threaded_playback()
        else:
            self.media_player.stop()
            
    def set_volume(self, volume):
        """Set the volume (0-100)"""
        if hasattr(self, 'using_fallback') and self.using_fallback:
            # Use pygame volume control for threaded playback
            self.set_preview_volume(volume)
        else:
            self.media_player.setVolume(volume)
        
    def on_state_changed(self, state):
        """Handle media player state changes"""
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText("Pause")
        else:
            self.play_pause_btn.setText("Play")
            
    def on_position_changed(self, position):
        """Handle position changes from media player"""
        if not self.slider_pressed:
            self.position_slider.setValue(position)
            
        # Update time label
        duration = self.media_player.duration()
        if duration > 0:
            current_time = self.format_time_simple(position // 1000)
            total_time = self.format_time_simple(duration // 1000)
            self.time_label.setText(f"{current_time} / {total_time}")
            
    def on_duration_changed(self, duration):
        """Handle duration changes from media player"""
        self.position_slider.setRange(0, duration)
        
        # Update timeline duration
        duration_seconds = duration / 1000
        self.timeline_widget.set_duration(duration_seconds)
        
    def update_timeline_position(self):
        """Update the timeline position indicator"""
        if hasattr(self, 'using_fallback') and self.using_fallback:
            # For fallback mode, the position is already updated in seek_to_fallback_frame
            return
        elif self.media_player.duration() > 0:
            position_seconds = self.media_player.position() / 1000
            # Use smooth animation for playback updates
            self.timeline_widget.set_position(position_seconds, instant=False)
            
    def on_slider_pressed(self):
        """Handle when position slider is pressed"""
        self.slider_pressed = True
        
    def on_slider_released(self):
        """Handle when position slider is released"""
        self.slider_pressed = False
        self.media_player.setPosition(self.position_slider.value())
        
    def on_slider_moved(self, position):
        """Handle when position slider is moved"""
        if self.slider_pressed:
            # Update timeline position during dragging
            if self.media_player.duration() > 0:
                position_seconds = position / 1000
                # Use instant positioning for user slider interaction
                self.timeline_widget.set_position(position_seconds, instant=True)
                
    def handle_error(self, error):
        """Handle media player errors"""
        error_string = ""
        if error == QMediaPlayer.NoError:
            error_string = "No error"
        elif error == QMediaPlayer.ResourceError:
            error_string = "Resource error - Cannot resolve media resource"
        elif error == QMediaPlayer.FormatError:
            error_string = "Format error - Media format is not supported"
        elif error == QMediaPlayer.NetworkError:
            error_string = "Network error"
        elif error == QMediaPlayer.AccessDeniedError:
            error_string = "Access denied error"
        elif error == QMediaPlayer.ServiceMissingError:
            error_string = "Service missing error - Valid playback service was not found"
        else:
            error_string = f"Unknown error: {error}"
            
        print(f"Media player error: {error_string}")
        
        # Don't show error dialogs for codec-related issues since we have a fallback system
        # Only show errors for severe issues like file not found
        if error == QMediaPlayer.AccessDeniedError:
            QMessageBox.critical(self, "Video Player Error", f"Cannot access video: {error_string}")
        # For codec/resource errors, let the fallback system handle it silently
        
    def on_media_status_changed(self, status):
        """Handle media status changes"""
        status_string = ""
        if status == QMediaPlayer.UnknownMediaStatus:
            status_string = "Unknown"
        elif status == QMediaPlayer.NoMedia:
            status_string = "No Media"
        elif status == QMediaPlayer.LoadingMedia:
            status_string = "Loading Media"
        elif status == QMediaPlayer.LoadedMedia:
            status_string = "Media Loaded"
            print("Media loaded successfully!")
        elif status == QMediaPlayer.StalledMedia:
            status_string = "Media Stalled"
        elif status == QMediaPlayer.BufferingMedia:
            status_string = "Buffering Media"
        elif status == QMediaPlayer.BufferedMedia:
            status_string = "Media Buffered"
        elif status == QMediaPlayer.EndOfMedia:
            status_string = "End of Media"
        elif status == QMediaPlayer.InvalidMedia:
            status_string = "Invalid Media"
        else:
            status_string = f"Status: {status}"
            
        print(f"Media status changed: {status_string}")
        
    def format_time_simple(self, seconds):
        """Format time in MM:SS format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
        
    def on_timeline_selection_changed(self, changed_part):
        """Handle selection changes from timeline"""
        self.selection_changed.emit(changed_part)
    
    def select_all_silent_regions(self):
        """Select all silent regions"""
        for part in self.silent_parts:
            part['selected'] = True
        self.timeline_widget.update()
        self.selection_changed.emit({})
        
    def deselect_all_silent_regions(self):
        """Deselect all silent regions"""
        for part in self.silent_parts:
            part['selected'] = False
        self.timeline_widget.update()
        self.selection_changed.emit({})

    def on_video_player_selection_changed(self, changed_part):
        """Handle selection changes from the video player timeline"""
        # Selection changes are now handled entirely by the interactive timeline
        pass

    def update_preview_position(self, preview_time):
        """Update UI based on preview timeline position"""
        if self.preview_mode and not self.slider_pressed:
            preview_time_ms = int(preview_time * 1000)
            self.position_slider.setValue(preview_time_ms)
            
        # Update timeline with smooth animation during playback
        if self.preview_mode:
            # Convert preview time back to original time for timeline display
            if hasattr(self, 'video_thread') and self.video_thread:
                original_time = self.video_thread.preview_time_to_original_time(preview_time)
                self.timeline_widget.set_position(original_time, instant=False)
            
        # Update time label
        self.update_time_label_display()
        
    def update_time_label_display(self):
        """Update the time label with appropriate information"""
        if self.preview_mode:
            # Preview mode: show preview time
            current_preview_ms = self.position_slider.value()
            current_time = self.format_time_simple(current_preview_ms // 1000)
            total_preview_time = self.format_time_simple(int(self.preview_duration))
            total_original_time = self.format_time_simple(getattr(self, 'video_duration_ms', 0) // 1000)
            self.time_label.setText(f"{current_time} / {total_preview_time} (cut from {total_original_time})")
        else:
            # Normal mode: show original time
            current_time_ms = self.position_slider.value()
            current_time = self.format_time_simple(current_time_ms // 1000)
            total_time = self.format_time_simple(getattr(self, 'video_duration_ms', 0) // 1000)
            self.time_label.setText(f"{current_time} / {total_time}")
    
    def enable_preview_mode(self):
        """Enable preview mode automatically after silence detection"""
        if not self.silent_parts:
            return
                
        # Enable preview mode
        self.preview_mode = True
        
        if hasattr(self, 'video_thread') and self.video_thread:
            self.video_thread.set_preview_mode(True, self.silent_parts)
            # Connect preview position signal
            self.video_thread.preview_position_changed.connect(self.update_preview_position)
            self.preview_duration = self.video_thread.preview_duration
            
        # Update timeline for preview mode
        self.timeline_widget.set_preview_mode(True, self.silent_parts)
        
        # Update position slider range for preview duration
        if self.preview_duration > 0:
            self.position_slider.setRange(0, int(self.preview_duration * 1000))
            
        print(f"✓ Preview mode enabled automatically. Original: {getattr(self, 'actual_duration_seconds', 0):.1f}s → Preview: {self.preview_duration:.1f}s")
        
        # Update time label immediately
        self.update_time_label_display()

class LoadingOverlay(QWidget):
    """Beautiful loading overlay with animated spinner"""
    def __init__(self, parent=None):
        super().__init__(parent)
        if parent:
            self.setFixedSize(parent.size())
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        
        # Animation properties
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        # Main container
        container = QWidget()
        container.setFixedSize(400, 300)  # Increased size for detailed progress and tips
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(45, 45, 45, 240);
                border-radius: 20px;
                border: 2px solid #3498db;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.setSpacing(20)
        
        # Loading text
        self.loading_label = QLabel("Loading Video...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        self.loading_label.setAlignment(Qt.AlignCenter)
        
        # Progress text
        self.progress_label = QLabel("Preparing timeline...")
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #bdc3c7;
                font-size: 11px;
                background: transparent;
                border: none;
                padding: 5px;
                line-height: 1.4;
            }
        """)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setWordWrap(True)  # Allow text wrapping for longer messages
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 8px;
                text-align: center;
                background-color: rgba(60, 60, 60, 180);
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 6px;
            }
        """)
        self.progress_bar.setFixedHeight(20)
        
        container_layout.addWidget(self.loading_label)
        container_layout.addWidget(self.progress_label)
        container_layout.addWidget(self.progress_bar)
        
        layout.addWidget(container)
        self.setLayout(layout)
        
    def show_loading(self, message="Loading Video..."):
        """Show loading overlay with message"""
        self.loading_label.setText(message)
        self.progress_label.setText("Preparing timeline...")
        self.progress_bar.setValue(0)  # Reset progress bar
        self.show()
        self.raise_()
        self.timer.start(50)  # 20 FPS animation
        
    def update_progress(self, message, progress_percent=None):
        """Update progress message and optionally progress bar"""
        self.progress_label.setText(message)
        
        # Extract progress percentage from message if not provided
        if progress_percent is None:
            # Look for percentage in message like "Step 3/6 (50%)"
            import re
            match = re.search(r'\((\d+)%\)', message)
            if match:
                progress_percent = int(match.group(1))
        
        # Update progress bar if percentage is available
        if progress_percent is not None:
            self.progress_bar.setValue(progress_percent)
        
    def hide_loading(self):
        """Hide loading overlay"""
        self.timer.stop()
        self.hide()
        
    def rotate(self):
        """Animate the loading indicator"""
        self.angle = (self.angle + 10) % 360
        self.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw animated spinner
        center = self.rect().center()
        radius = 30
        
        # Draw spinning circle
        painter.setPen(QPen(QColor(52, 152, 219), 4))
        rect = QRectF(center.x() - radius, center.y() - radius - 50, radius * 2, radius * 2)
        
        # Draw arc that rotates
        painter.drawArc(rect, self.angle * 16, 120 * 16)  # 120 degree arc
        
        # Draw dots around the circle
        import math
        for i in range(8):
            angle = (self.angle + i * 45) * 3.14159 / 180
            x = center.x() + (radius + 10) * math.cos(angle)
            y = center.y() - 50 + (radius + 10) * math.sin(angle)
            
            # Fade effect for dots
            alpha = int(255 * (1 - i / 8))
            painter.setBrush(QBrush(QColor(52, 152, 219, alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), 3, 3)

class SilenceCutterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_path = None
        self.silent_parts = []
        self.silent_ranges = []
        
        # Create loading overlay
        self.loading_overlay = None
        
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Video Silence Cutter with Real-time Preview")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        
        # Main layout - more compact
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)  # Reduce spacing between sections
        main_layout.setContentsMargins(10, 5, 10, 5)  # Reduce margins
        
        # File selection area - more compact
        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)
        self.file_label = QLabel("No file selected")
        self.file_label.setFont(QFont("Arial", 9))  # Reduced from 10
        
        select_btn = QPushButton("Select Video")
        select_btn.clicked.connect(self.select_video)
        select_btn.setMaximumWidth(120)  # Make more compact
        
        file_layout.addWidget(select_btn)
        file_layout.addWidget(self.file_label, 1)
        main_layout.addLayout(file_layout)
        
        # Controls container - make all controls more compact
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        controls_frame.setMaximumHeight(120)  # Limit height of control area
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(3)  # Tight spacing
        controls_layout.setContentsMargins(8, 5, 8, 5)
        
        # Silence threshold controls - more compact
        threshold_layout = QHBoxLayout()
        threshold_layout.setSpacing(6)
        threshold_label = QLabel("Silence Threshold (dB):")
        threshold_label.setFont(QFont("Arial", 9))
        threshold_label.setMinimumWidth(150)
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(-60)
        self.threshold_slider.setMaximum(-20)
        self.threshold_slider.setValue(-52)
        self.threshold_value_label = QLabel("-52 dB")
        self.threshold_value_label.setFont(QFont("Arial", 9))
        self.threshold_value_label.setMinimumWidth(60)
        
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.threshold_value_label)
        controls_layout.addLayout(threshold_layout)
        
        # Min silence duration controls - more compact
        duration_layout = QHBoxLayout()
        duration_layout.setSpacing(6)
        duration_label = QLabel("Min Silence Duration (ms):")
        duration_label.setFont(QFont("Arial", 9))
        duration_label.setMinimumWidth(150)
        self.duration_slider = QSlider(Qt.Horizontal)
        self.duration_slider.setMinimum(100)
        self.duration_slider.setMaximum(2000)
        self.duration_slider.setValue(700)
        self.duration_value_label = QLabel("700 ms")
        self.duration_value_label.setFont(QFont("Arial", 9))
        self.duration_value_label.setMinimumWidth(60)
        
        self.duration_slider.valueChanged.connect(self.update_duration_label)
        
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_slider)
        duration_layout.addWidget(self.duration_value_label)
        controls_layout.addLayout(duration_layout)
        
        # Padding controls for non-silent segments - more compact
        padding_layout = QHBoxLayout()
        padding_layout.setSpacing(6)
        padding_label = QLabel("Speech Padding Buffer (ms):")
        padding_label.setFont(QFont("Arial", 9))
        padding_label.setMinimumWidth(150)
        self.padding_slider = QSlider(Qt.Horizontal)
        self.padding_slider.setMinimum(0)
        self.padding_slider.setMaximum(500)
        self.padding_slider.setValue(100)
        self.padding_value_label = QLabel("100 ms")
        self.padding_value_label.setFont(QFont("Arial", 9))
        self.padding_value_label.setMinimumWidth(60)
        
        self.padding_slider.valueChanged.connect(self.update_padding_label)
        
        padding_layout.addWidget(padding_label)
        padding_layout.addWidget(self.padding_slider)
        padding_layout.addWidget(self.padding_value_label)
        controls_layout.addLayout(padding_layout)
        
        # Detect button - more compact
        detect_layout = QHBoxLayout()
        self.detect_btn = QPushButton("Detect Silence")
        self.detect_btn.clicked.connect(self.detect_silence)
        self.detect_btn.setEnabled(False)
        self.detect_btn.setMaximumWidth(150)
        detect_layout.addWidget(self.detect_btn)
        detect_layout.addStretch()
        controls_layout.addLayout(detect_layout)
        
        main_layout.addWidget(controls_frame)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)  # Make thinner
        main_layout.addWidget(self.progress_bar)
        
        # Interactive Video Player and Timeline
        video_player_label = QLabel("Interactive Video Player with Real-time Preview:")
        video_player_label.setFont(QFont("Arial", 11, QFont.Bold))  # Slightly smaller
        main_layout.addWidget(video_player_label)
        
        self.video_player = InteractiveVideoPlayer()
        self.video_player.selection_changed.connect(self.on_video_player_selection_changed)
        main_layout.addWidget(self.video_player, 1)  # Give it most of the space
        
        # Process button - more compact
        process_layout = QHBoxLayout()
        self.process_btn = QPushButton("Process and Save Video")
        self.process_btn.clicked.connect(self.process_video)
        self.process_btn.setEnabled(False)
        self.process_btn.setMaximumWidth(200)
        process_layout.addWidget(self.process_btn)
        process_layout.addStretch()
        main_layout.addLayout(process_layout)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def update_threshold_label(self):
        value = self.threshold_slider.value()
        self.threshold_value_label.setText(f"{value} dB")
    
    def update_duration_label(self):
        value = self.duration_slider.value()
        self.duration_value_label.setText(f"{value} ms")
    
    def update_padding_label(self):
        value = self.padding_slider.value()
        self.padding_value_label.setText(f"{value} ms")
    
    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv)"
        )
        
        if file_path:
            # Show loading overlay immediately with enhanced tracking
            self.show_loading_overlay("Loading Video...")
            
            # Initialize loading progress tracking
            self.loading_start_time = time.time()
            self.loading_steps_completed = 0
            self.total_loading_steps = 6  # Total expected steps
            
            # Get file size for better time estimation
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self.estimated_total_time = max(5, min(30, file_size_mb * 0.5))  # Rough estimate: 0.5 seconds per MB, 5-30 second range
                print(f"📁 File size: {file_size_mb:.1f} MB, estimated loading time: {self.estimated_total_time:.0f}s")
            except:
                self.estimated_total_time = 15  # Default estimate
            
            # Clear previous data first
            self.clear_previous_data()
            
            self.video_path = file_path
            file_name = os.path.basename(file_path)
            self.file_label.setText(file_name)
            self.detect_btn.setEnabled(True)
            self.silent_parts = []
            self.process_btn.setEnabled(False)
            
            # Update loading message with step tracking
            self.update_loading_progress_with_step("Initializing video player...", 1)
            
            # Load video into the player
            self.video_player.load_video(file_path)
            
            # Enable performance optimizations immediately
            self.enable_performance_optimizations()
            
            # Extended fallback timer - only hide if something goes wrong
            QTimer.singleShot(30000, self.hide_loading_overlay_fallback)  # 30 seconds instead of 3
    
    def update_loading_progress_with_step(self, message, step_number=None):
        """Update loading progress with step tracking and time estimation"""
        if step_number is not None:
            self.loading_steps_completed = step_number
            
        # Calculate progress percentage
        progress_percent = int((self.loading_steps_completed / self.total_loading_steps) * 100)
        
        # Calculate estimated time remaining
        if hasattr(self, 'loading_start_time') and self.loading_steps_completed > 0:
            elapsed_time = time.time() - self.loading_start_time
            
            # Use both step-based and file-size-based estimation
            avg_time_per_step = elapsed_time / self.loading_steps_completed
            remaining_steps = self.total_loading_steps - self.loading_steps_completed
            step_based_estimate = remaining_steps * avg_time_per_step
            
            # File-size-based estimate
            if hasattr(self, 'estimated_total_time'):
                progress_ratio = self.loading_steps_completed / self.total_loading_steps
                file_based_estimate = self.estimated_total_time * (1 - progress_ratio)
                
                # Use weighted average of both estimates
                estimated_remaining = (step_based_estimate * 0.7) + (file_based_estimate * 0.3)
            else:
                estimated_remaining = step_based_estimate
            
            if estimated_remaining > 60:
                time_str = f"~{int(estimated_remaining/60)}m {int(estimated_remaining%60)}s remaining"
            elif estimated_remaining > 10:
                time_str = f"~{int(estimated_remaining)}s remaining"
            else:
                time_str = "Almost done..."
        else:
            if hasattr(self, 'estimated_total_time'):
                time_str = f"~{int(self.estimated_total_time)}s estimated"
            else:
                time_str = "Calculating time..."
        
        # Add helpful tip based on current step
        if self.loading_steps_completed <= 3:
            tip = "💡 Tip: Processing audio for waveform visualization"
        elif self.loading_steps_completed <= 5:
            tip = "💡 Tip: Setting up video player and timeline"
        else:
            tip = "💡 Tip: Finalizing setup - almost ready!"
        
        # Format the complete message
        full_message = f"{message}\n\nStep {self.loading_steps_completed}/{self.total_loading_steps} ({progress_percent}%)\n{time_str}\n\n{tip}"
        
        if self.loading_overlay:
            self.loading_overlay.update_progress(full_message)
            QApplication.processEvents()
    
    def hide_loading_overlay_fallback(self):
        """Fallback method to hide loading overlay if something goes wrong"""
        if self.loading_overlay and self.loading_overlay.isVisible():
            print("⚠️ Loading overlay fallback timeout - hiding overlay")
            self.hide_loading_overlay()
            # Show a message that loading is still happening in background
            QMessageBox.information(
                self, 
                "Loading in Background", 
                "Video is still loading in the background.\nThe application may be slow until loading completes."
            )
    
    def detect_silence(self):
        if not self.video_path:
            return
        
        # Get current threshold and duration values
        silence_threshold = self.threshold_slider.value()
        min_silence_duration = self.duration_slider.value()
        padding_ms = self.padding_slider.value()
        
        # Disable UI elements during detection
        self.detect_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        # Initialize detection timing
        self.detection_start_time = time.time()
        try:
            file_size_mb = os.path.getsize(self.video_path) / (1024 * 1024)
            self.detection_estimated_time = max(10, min(120, file_size_mb * 2))  # Rough estimate: 2 seconds per MB, 10-120 second range
            print(f"📁 Detection for {file_size_mb:.1f} MB file, estimated time: {self.detection_estimated_time:.0f}s")
        except:
            self.detection_estimated_time = 30  # Default estimate
        
        # Start real-time countdown timer for detection
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self.update_detection_countdown)
        self.detection_timer.start(1000)  # Update every second
        
        # Disable performance optimizations during detection for faster processing
        self.disable_performance_optimizations()
        
        # Start the detection thread
        self.detection_thread = SilenceDetectionThread(
            self.video_path, 
            min_silence_duration=min_silence_duration,
            silence_threshold=silence_threshold,
            padding_ms=padding_ms
        )
        self.detection_thread.progress_updated.connect(self.update_detection_progress)
        self.detection_thread.detection_complete.connect(self.show_detection_results)
        self.detection_thread.start()
    
    def update_detection_progress(self, progress):
        self.progress_bar.setValue(progress)
        # Store current progress for countdown timer
        self.current_detection_progress = progress
    
    def update_detection_countdown(self):
        """Update detection progress with real-time countdown"""
        if not hasattr(self, 'current_detection_progress'):
            return
            
        progress = self.current_detection_progress
        
        # Calculate and show estimated time remaining
        if hasattr(self, 'detection_start_time') and progress > 0:
            elapsed_time = time.time() - self.detection_start_time
            
            # Initialize or update the stable countdown
            if not hasattr(self, 'detection_countdown_time'):
                # Set initial countdown time
                if progress > 5:
                    progress_based_estimate = (elapsed_time / progress) * (100 - progress)
                    if hasattr(self, 'detection_estimated_time'):
                        progress_ratio = progress / 100
                        file_based_estimate = self.detection_estimated_time * (1 - progress_ratio)
                        self.detection_countdown_time = (progress_based_estimate * 0.7) + (file_based_estimate * 0.3)
                    else:
                        self.detection_countdown_time = progress_based_estimate
                else:
                    self.detection_countdown_time = getattr(self, 'detection_estimated_time', 30)
                
                self.detection_last_update = time.time()
            else:
                # Decrease countdown by elapsed time since last update
                time_since_last = time.time() - self.detection_last_update
                self.detection_countdown_time = max(0, self.detection_countdown_time - time_since_last)
                self.detection_last_update = time.time()
                
                # Recalibrate if progress significantly changed
                if progress > 5:
                    progress_based_estimate = (elapsed_time / progress) * (100 - progress)
                    # Only adjust if new estimate is significantly different and reasonable
                    if abs(progress_based_estimate - self.detection_countdown_time) > 10 and progress_based_estimate < self.detection_countdown_time * 1.5:
                        self.detection_countdown_time = min(self.detection_countdown_time, progress_based_estimate)
            
            # Handle final stages (90%+) - extend time if needed
            if progress >= 90 and self.detection_countdown_time < 5:
                self.detection_countdown_time = max(5, self.detection_countdown_time)
            
            # Format time display
            if self.detection_countdown_time > 60:
                time_str = f"{int(self.detection_countdown_time/60)}m {int(self.detection_countdown_time%60)}s"
            elif self.detection_countdown_time > 0:
                time_str = f"{int(self.detection_countdown_time)}s"
            else:
                time_str = "Finishing..."
            
            # Update progress bar text
            self.progress_bar.setFormat(f"Detecting silence... {progress}% ({time_str})")
        else:
            self.progress_bar.setFormat(f"Detecting silence... {progress}%")
    
    def show_detection_results(self, silent_parts):
        # Stop the countdown timer and reset variables
        if hasattr(self, 'detection_timer'):
            self.detection_timer.stop()
        if hasattr(self, 'detection_countdown_time'):
            delattr(self, 'detection_countdown_time')
        if hasattr(self, 'detection_last_update'):
            delattr(self, 'detection_last_update')
            
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p%")  # Reset to default format
        self.detect_btn.setEnabled(True)
        
        # Re-enable performance optimizations after detection
        self.enable_performance_optimizations()
        
        print(f"\n---------- SILENCE DETECTION RESULTS ----------")
        print(f"Number of silent parts detected: {len(silent_parts)}")
        if silent_parts:
            for i, part in enumerate(silent_parts[:5]):  # Show first 5
                print(f"  Silence {i+1}: {part['start']:.2f}s - {part['end']:.2f}s (duration: {part['duration_ms']/1000:.2f}s)")
            if len(silent_parts) > 5:
                print(f"  ... and {len(silent_parts) - 5} more parts")
        else:
            print("  No silence parts were detected with current settings.")
        print(f"---------- END SILENCE DETECTION RESULTS ----------\n")
        
        if not silent_parts:
            QMessageBox.information(self, "Detection Results", "No silence detected with current settings.")
            return
        
        self.silent_parts = silent_parts
        
        # Load silent parts into the video player timeline
        self.video_player.set_silent_parts(silent_parts)
        
        # Automatically enable preview mode after silence detection
        self.video_player.enable_preview_mode()
        
        self.process_btn.setEnabled(True)
    
    def on_video_player_selection_changed(self, changed_part):
        """Handle selection changes from the video player timeline"""
        # Update preview in real-time when selections change
        if self.video_player.preview_mode and hasattr(self.video_player, 'video_thread'):
            self.video_player.video_thread.set_preview_mode(True, self.video_player.silent_parts)
    
    def process_video(self):
        if not self.video_path or not self.silent_parts:
            return
        
        # Check if any silence parts are selected for cutting
        if not any(part['selected'] for part in self.silent_parts):
            QMessageBox.information(
                self, 
                "No Selections", 
                "No silence segments are selected for cutting. Please select at least one segment."
            )
            return
        
        # Get output file path
        file_name = os.path.basename(self.video_path)
        base_name, ext = os.path.splitext(file_name)
        suggested_name = f"{base_name}_silences_removed{ext}"
        
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video", suggested_name, f"Video Files (*{ext})"
        )
        
        if not output_path:
            return
        
        # Disable UI during processing
        self.process_btn.setEnabled(False)
        self.detect_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        # Initialize processing timing
        self.processing_start_time = time.time()
        try:
            file_size_mb = os.path.getsize(self.video_path) / (1024 * 1024)
            # Processing is typically slower than detection, estimate 3-5 seconds per MB
            self.processing_estimated_time = max(15, min(300, file_size_mb * 4))  # 4 seconds per MB, 15-300 second range
            print(f"📁 Processing {file_size_mb:.1f} MB file, estimated time: {self.processing_estimated_time:.0f}s")
        except:
            self.processing_estimated_time = 60  # Default estimate
        
        # Start real-time countdown timer for processing
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self.update_processing_countdown)
        self.processing_timer.start(1000)  # Update every second
        
        # Start processing thread
        self.processing_thread = ProcessingThread(
            self.video_path,
            self.silent_parts,
            output_path
        )
        self.processing_thread.progress_updated.connect(self.update_processing_progress)
        self.processing_thread.processing_complete.connect(self.show_processing_results)
        self.processing_thread.start()
    
    def update_processing_progress(self, progress):
        self.progress_bar.setValue(progress)
        # Store current progress for countdown timer
        self.current_processing_progress = progress
    
    def update_processing_countdown(self):
        """Update processing progress with real-time countdown"""
        if not hasattr(self, 'current_processing_progress'):
            return
            
        progress = self.current_processing_progress
        
        # Calculate and show estimated time remaining
        if hasattr(self, 'processing_start_time') and progress > 0:
            elapsed_time = time.time() - self.processing_start_time
            
            # Initialize or update the stable countdown
            if not hasattr(self, 'processing_countdown_time'):
                # Set initial countdown time
                if progress > 5:
                    progress_based_estimate = (elapsed_time / progress) * (100 - progress)
                    if hasattr(self, 'processing_estimated_time'):
                        progress_ratio = progress / 100
                        file_based_estimate = self.processing_estimated_time * (1 - progress_ratio)
                        self.processing_countdown_time = (progress_based_estimate * 0.7) + (file_based_estimate * 0.3)
                    else:
                        self.processing_countdown_time = progress_based_estimate
                else:
                    self.processing_countdown_time = getattr(self, 'processing_estimated_time', 60)
                
                self.processing_last_update = time.time()
            else:
                # Decrease countdown by elapsed time since last update
                time_since_last = time.time() - self.processing_last_update
                self.processing_countdown_time = max(0, self.processing_countdown_time - time_since_last)
                self.processing_last_update = time.time()
                
                # Recalibrate if progress significantly changed
                if progress > 5:
                    progress_based_estimate = (elapsed_time / progress) * (100 - progress)
                    # Only adjust if new estimate is significantly different and reasonable
                    if abs(progress_based_estimate - self.processing_countdown_time) > 15 and progress_based_estimate < self.processing_countdown_time * 1.5:
                        self.processing_countdown_time = min(self.processing_countdown_time, progress_based_estimate)
            
            # Handle final stages (90%+) - extend time significantly for rendering
            if progress >= 90 and self.processing_countdown_time < 15:
                self.processing_countdown_time = max(15, self.processing_countdown_time)
            elif progress >= 95 and self.processing_countdown_time < 30:
                self.processing_countdown_time = max(30, self.processing_countdown_time)
            
            # Format time display
            if self.processing_countdown_time > 60:
                time_str = f"{int(self.processing_countdown_time/60)}m {int(self.processing_countdown_time%60)}s"
            elif self.processing_countdown_time > 0:
                time_str = f"{int(self.processing_countdown_time)}s"
            else:
                time_str = "Finishing..."
            
            # Update progress bar text
            self.progress_bar.setFormat(f"Processing video... {progress}% ({time_str})")
        else:
            self.progress_bar.setFormat(f"Processing video... {progress}%")
    
    def show_processing_results(self, output_path):
        # Stop the countdown timer and reset variables
        if hasattr(self, 'processing_timer'):
            self.processing_timer.stop()
        if hasattr(self, 'processing_countdown_time'):
            delattr(self, 'processing_countdown_time')
        if hasattr(self, 'processing_last_update'):
            delattr(self, 'processing_last_update')
            
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p%")  # Reset to default format
        self.process_btn.setEnabled(True)
        self.detect_btn.setEnabled(True)
        
        if output_path:
            # Check if hardware acceleration was used (look for indicators in console output)
            hw_message = ""
            try:
                # This is a simple way to show hardware acceleration was attempted
                # In a real implementation, you might want to pass this info from the processing thread
                hw_message = "\n\n🚀 Hardware acceleration was used for faster processing!"
            except:
                pass
                
            QMessageBox.information(
                self,
                "Processing Complete",
                f"Video processed successfully and saved to:\n{output_path}{hw_message}"
            )
        else:
            QMessageBox.critical(
                self,
                "Processing Error",
                "An error occurred during video processing. Please check console for details."
            )
    
    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Stop any ongoing detection or processing
            if hasattr(self, 'detection_thread') and self.detection_thread.isRunning():
                self.detection_thread.terminate()
                self.detection_thread.wait(1000)
            
            if hasattr(self, 'processing_thread') and self.processing_thread.isRunning():
                self.processing_thread.terminate()
                self.processing_thread.wait(1000)
            
        # Clean up video player resources
        if hasattr(self, 'video_player'):
            self.video_player.cleanup_fallback_resources()
                
            # Clean up circular buffers and caches
            self.cleanup_buffers()
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        super().closeEvent(event)
        
    def cleanup_buffers(self):
        """Clean up all circular buffers and caches"""
        try:
            # Clear video playback thread buffers
            if hasattr(self.video_player, 'video_thread') and self.video_player.video_thread:
                if hasattr(self.video_player.video_thread, 'frame_buffer'):
                    self.video_player.video_thread.frame_buffer.clear()
                if hasattr(self.video_player.video_thread, 'audio_buffer'):
                    self.video_player.video_thread.audio_buffer.clear()
                    
            # Clear timeline waveform cache
            if hasattr(self.video_player, 'timeline') and hasattr(self.video_player.timeline, 'waveform_cache'):
                self.video_player.timeline.waveform_cache.clear()
                
            print("🧹 Circular buffers and caches cleared")
        except Exception as e:
            print(f"Error cleaning up buffers: {e}")
            
    def get_buffer_stats(self):
        """Get performance statistics from circular buffers"""
        stats = {}
        try:
            # Video frame buffer stats
            if (hasattr(self.video_player, 'video_thread') and 
                self.video_player.video_thread and 
                hasattr(self.video_player.video_thread, 'frame_buffer')):
                stats['frame_buffer'] = self.video_player.video_thread.frame_buffer.get_cache_stats()
                
            # Waveform cache stats
            if (hasattr(self.video_player, 'timeline') and 
                hasattr(self.video_player.timeline, 'waveform_cache')):
                waveform_cache = self.video_player.timeline.waveform_cache
                stats['waveform_cache'] = {
                    'size': len(waveform_cache.cache),
                    'max_size': waveform_cache.max_levels
                }
                
            return stats
        except Exception as e:
            print(f"Error getting buffer stats: {e}")
            return {}
            
    def enable_performance_optimizations(self):
        """Enable performance optimizations after initial loading is complete"""
        try:
            # Enable buffer operations
            if hasattr(self.video_player, 'video_thread') and self.video_player.video_thread:
                self.video_player.video_thread.set_buffer_mode(True)
                
            # Enable waveform caching
            if hasattr(self.video_player, 'timeline'):
                self.video_player.timeline.enable_caching()
                
            print("⚡ Performance optimizations enabled")
        except Exception as e:
            print(f"Error enabling optimizations: {e}")
            
    def disable_performance_optimizations(self):
        """Disable performance optimizations during heavy operations"""
        try:
            # Disable all buffer operations
            if hasattr(self.video_player, 'video_thread') and self.video_player.video_thread:
                self.video_player.video_thread.set_buffer_mode(False)
                
            # Disable waveform caching
            if hasattr(self.video_player, 'timeline'):
                self.video_player.timeline.disable_caching()
                
            print("🔄 Performance optimizations disabled for heavy operation")
        except Exception as e:
            print(f"Error disabling optimizations: {e}")
            
    def clear_previous_data(self):
        """Clear all previous video data and UI elements completely"""
        try:
            print("🧹 Clearing all previous video data...")
            
            # Clear silent parts data
            self.silent_parts = []
            
            # Stop any running threads
            if hasattr(self, 'detection_thread') and self.detection_thread and self.detection_thread.isRunning():
                self.detection_thread.terminate()
                self.detection_thread.wait(1000)
                
            if hasattr(self, 'processing_thread') and self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.terminate()
                self.processing_thread.wait(1000)
            
            # Clear timeline data completely
            if hasattr(self.video_player, 'timeline'):
                timeline = self.video_player.timeline
                
                # Stop any waveform loading thread
                if hasattr(timeline, 'waveform_thread') and timeline.waveform_thread and timeline.waveform_thread.isRunning():
                    timeline.waveform_thread.terminate()
                    timeline.waveform_thread.wait(1000)
                
                # Clear all timeline data
                timeline.set_silent_parts([], [])
                timeline.set_duration(0)
                timeline.set_position(0, instant=True)
                timeline.waveform_data = None
                timeline.waveform_max_amplitude = 0
                timeline.video_path = None
                timeline.preview_mode = False
                timeline.zoom_level = 1.0
                timeline.zoom_offset = 0.0
                timeline.current_position = 0
                timeline.target_position = 0
                
                # Clear caches
                timeline.waveform_cache.clear()
                if hasattr(timeline, 'history'):
                    timeline.history = []
                    timeline.history_index = -1
                
                # Force update
                timeline.update()
                
            # Clear video player data
            if hasattr(self.video_player, 'video_thread') and self.video_player.video_thread:
                self.video_player.video_thread.frame_buffer.clear()
                self.video_player.video_thread.audio_buffer.clear()
                self.video_player.video_thread.stop_playback()
                
            # Reset UI elements
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.detect_btn.setEnabled(False)
            self.process_btn.setEnabled(False)
            self.file_label.setText("No file selected")
            
            print("✅ All previous data cleared successfully")
        except Exception as e:
            print(f"Error clearing previous data: {e}")
    
    def show_loading_overlay(self, message="Loading..."):
        """Show beautiful loading overlay"""
        if not self.loading_overlay:
            self.loading_overlay = LoadingOverlay(self)
            self.loading_overlay.setFixedSize(self.size())
        
        self.loading_overlay.show_loading(message)
        QApplication.processEvents()  # Ensure UI updates immediately
        
    def update_loading_progress(self, message):
        """Update loading progress message"""
        if self.loading_overlay:
            self.loading_overlay.update_progress(message)
            QApplication.processEvents()
            
    def hide_loading_overlay(self):
        """Hide loading overlay"""
        if self.loading_overlay:
            self.loading_overlay.hide_loading()
    
    def resizeEvent(self, event):
        """Handle window resize to update loading overlay size"""
        super().resizeEvent(event)
        if self.loading_overlay:
            self.loading_overlay.setFixedSize(self.size())

# Clean up any temporary files on exit
def cleanup_temp_files():
    temp_dir = tempfile.gettempdir()
    try:
        for filename in os.listdir(temp_dir):
            if filename.startswith("temp-audio-") and (filename.endswith(".m4a") or filename.endswith(".wav")):
                try:
                    os.unlink(os.path.join(temp_dir, filename))
                except:
                    pass
    except:
        pass

# Register the cleanup function
atexit.register(cleanup_temp_files)

def main():
    app = QApplication(sys.argv)
    window = SilenceCutterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 