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
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath, QImage, QPixmap, QLinearGradient, QIcon
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import cv2
from proglog import ProgressBarLogger
import pygame
import threading
from collections import deque
import queue

# Add webbrowser for opening URLs
import webbrowser

# Import API communication for SaaS integration
try:
    from features.api_communication import api_client
    API_COMMUNICATION_AVAILABLE = True
    print("✅ API communication module loaded successfully")
except ImportError as e:
    print(f"⚠️  API communication not available: {e}")
    API_COMMUNICATION_AVAILABLE = False
    # Create dummy api_client for fallback
    class DummyAPIClient:
        def validate_file_usage(self, *args, **kwargs):
            return {'allowed': True, 'message': 'Offline mode'}
        def record_usage(self, *args, **kwargs):
            return True
        def open_upgrade_page(self):
            return "https://silencecutter.com/pricing"
    api_client = DummyAPIClient()

# Import manual cutting feature
try:
    from features import ManualCuttingManager, ManualCuttingIntegration
    MANUAL_CUTTING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Manual cutting feature not available: {e}")
    MANUAL_CUTTING_AVAILABLE = False

# Import batch processing feature
try:
    from features.batch_processing import BatchProcessingIntegration
    BATCH_PROCESSING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Batch processing feature not available: {e}")
    BATCH_PROCESSING_AVAILABLE = False

# Import resolution optimizer
try:
    from features.resolution_optimizer import ResolutionOptimizer, ResolutionAwareProcessingMixin
    RESOLUTION_OPTIMIZER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Resolution optimizer not available: {e}")
    RESOLUTION_OPTIMIZER_AVAILABLE = False
# Import transcript integration
try:
    from transcript_integration import (
        integrate_transcript_with_app, start_transcript_generation,
        detect_repeated_words, apply_repeated_word_removal
    )
    TRANSCRIPT_INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Transcript integration not available: {e}")
    TRANSCRIPT_INTEGRATION_AVAILABLE = False


    # Create dummy classes for fallback
    class ResolutionOptimizer:
        def __init__(self): pass
        def get_optimized_settings(self, video_path): return {}
        def print_optimization_summary(self, video_path, settings): pass

    class ResolutionAwareProcessingMixin:
        def __init__(self, *args, **kwargs): super().__init__(*args, **kwargs)
        def set_optimization_settings(self, settings): pass
        def get_optimized_ffmpeg_params(self, video_codec): return []

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
            pass
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
            pass
            if not self.positions:
                pass
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
                pass
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
            pass
            for i, sample in enumerate(samples):
                timestamp = start_time + (i / self.sample_rate)
                self.buffer.append(sample)
                self.timestamps.append(timestamp)

    def get_samples(self, start_time, duration):
        """Get audio samples for specific time range"""
        with self.lock:
            pass
            if not self.timestamps:
                pass
                return []

            end_time = start_time + duration
            samples = []

            for i, timestamp in enumerate(self.timestamps):
                pass
                if start_time <= timestamp <= end_time:
                    pass
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
            detected_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            # Ensure minimum 30 FPS for smooth playback
            self.fps = max(detected_fps, 30)
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Get actual video duration using moviepy for accuracy
            try:
                import moviepy.editor as mp
                video_clip = mp.VideoFileClip(self.video_path)
                self.actual_duration = video_clip.duration
                video_clip.close()
            except:
                self.actual_duration = self.frame_count / self.fps if self.fps > 0 else 0

            # Calculate frame duration based on actual duration instead of FPS
            if self.frame_count > 0 and self.actual_duration > 0:
                self.frame_duration = self.actual_duration / self.frame_count
            else:
                self.frame_duration = 1.0 / self.fps


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

                # Store the verified duration
                self.verified_audio_duration = extracted_audio_duration
                self.duration_difference = abs(video_duration - extracted_audio_duration)

                if self.duration_difference > 0.1:
                    print(f"WARNING: Audio-video duration mismatch: {self.duration_difference:.3f}s difference")
                else:
                    pass

                video_clip.close()

                # Load audio into pygame
                pygame.mixer.music.load(self.temp_audio_file.name)
                self.audio_loaded = True
                self.preview_audio_segments = []  # Will store segmented audio for preview
            else:
                pass

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


            if self.audio_loaded:
                pass
                try:
                    # Play preview audio from the correct preview position
                    pygame.mixer.music.play(start=preview_position)
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
                pass
                try:
                    # Enhanced audio start with synchronization verification
                    pygame.mixer.music.play(start=audio_position)

                    # Log detailed playback synchronization info

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
            pass
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
            pass
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.play(start=precise_audio_position)

                # Immediately update playback timing to compensate for pygame seeking inaccuracy
                # We calculate the offset from expected position
                self.seek_audio_offset = precise_audio_position
                self.seek_time = current_time

            except Exception as e:
                print(f"Error seeking audio: {e}")
        else:
            # If not playing, still reset timing for when playback starts
            self.playback_start_time = current_time

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
                pass
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=target_time_seconds)  # Use preview timeline


                except Exception as e:
                    print(f"Error seeking preview audio: {e}")
            else:
                pass
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
                pass
                if exact_timeline_position > self.verified_audio_duration:
                    exact_timeline_position = self.verified_audio_duration

            # Reset playback timing to match the exact timeline position
            current_time = time.time()
            self.playback_start_time = current_time - exact_timeline_position
            self.playback_initial_frame = target_frame

            # Enhanced audio seeking with EXACT timeline position
            if self.audio_loaded and self.is_playing:
                pass
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=exact_timeline_position)


                except Exception as e:
                    print(f"Error seeking audio: {e}")
            else:
                pass

        self.mutex.unlock()

    def stop_playback(self):
        """Stop the thread"""
        self.mutex.lock()
        self.stop_requested = True
        self.is_playing = False
        self.playback_started = False  # Reset playback tracking
        if self.audio_loaded:
            pass
            try:
                pygame.mixer.music.stop()
            except:
                pass
        self.mutex.unlock()

    def run(self):
        """Main thread loop with optimized performance for preview mode"""
        if not self.initialize_video():
            pass
            return

        # Use original video framerate for accurate playback
        target_fps = self.fps
        target_frame_time = 1.0 / target_fps

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
                        pass
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
                            pass
                            try:
                                pygame.mixer.music.stop()
                            except:
                                pass

                # Always process frames to maintain original framerate
                should_process_frame = True

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

                            # Update UI at video framerate for smooth playback
                            current_time = time.time()
                            ui_update_interval = 1.0 / target_fps  # Match video framerate
                            if current_time - last_ui_update >= ui_update_interval:
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
            pass
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
            pass

            # Check if this is an audio-only file
            audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
            file_ext = os.path.splitext(self.video_path)[1].lower()
            is_audio_only = file_ext in audio_extensions

            if is_audio_only:
                self.progress_updated.emit("Loading audio file...")

                # Load audio directly using pydub
                from pydub import AudioSegment
                audio = AudioSegment.from_file(self.video_path)

                # Emit duration immediately for instant timeline setup
                duration_seconds = len(audio) / 1000.0
                self.duration_loaded.emit(duration_seconds)

                self.progress_updated.emit("Processing audio data...")

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
                target_samples = 1500
                if len(samples) > target_samples:
                    step = len(samples) // target_samples
                    samples = samples[::step]

                max_amplitude = max(abs(s) for s in samples) if samples else 1.0

                self.progress_updated.emit("Audio waveform ready!")

                # Emit the loaded waveform data
                self.waveform_loaded.emit(samples, max_amplitude)
                return

            else:
                # Handle video files
                self.progress_updated.emit("Loading video file...")

                # Extract audio using MoviePy
                import moviepy.editor as mp
                video = mp.VideoFileClip(self.video_path)

                # Emit duration immediately for instant timeline setup
                if video.duration > 0:
                    self.duration_loaded.emit(video.duration)

                self.progress_updated.emit("Extracting audio track...")

                if video.audio is None:
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

                self.progress_updated.emit("Video waveform ready!")

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
                pass
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
            pass
            if os.path.exists(location):
                pass
                return location

        # Could not find FFmpeg, will use just the command and hope it works
        return "ffmpeg"

    def run(self):
        try:
            # Use the accurate pydub-based detection for better results
            # Skip fast FFmpeg detection to maintain accuracy

            # Start with initial progress
            self.progress_updated.emit(5)
            QApplication.processEvents()  # Process events to update GUI

            # Check if this is an audio-only file
            audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
            file_ext = os.path.splitext(self.video_path)[1].lower()
            is_audio_only = file_ext in audio_extensions

            if is_audio_only:
                self.progress_updated.emit(10)
                QApplication.processEvents()

                # For audio files, load directly with pydub
                audio = AudioSegment.from_file(self.video_path)
                audio_duration_ms = len(audio)
                self.progress_updated.emit(40)
                QApplication.processEvents()

                # Convert to mono for faster processing while maintaining accuracy
                if audio.channels > 1:
                    audio = audio.set_channels(1)

                self.progress_updated.emit(60)
                QApplication.processEvents()

            else:
                # For video files, extract audio using moviepy
                # Modify moviepy's FFMPEG_BINARY setting to use our detected FFmpeg path
                from moviepy.config import change_settings
                change_settings({"FFMPEG_BINARY": self.ffmpeg_path})

                # Extract audio from video more efficiently
                self.progress_updated.emit(10)
                QApplication.processEvents()

                # Load video more efficiently
                video = mp.VideoFileClip(self.video_path)
                audio_duration_ms = int(video.audio.duration * 1000)
                self.progress_updated.emit(20)
                QApplication.processEvents()

                # Create temporary audio file with optimized settings
                temp_audio = tempfile.NamedTemporaryFile(suffix=f'_sid_{os.getpid()}_{int(time.time())}.wav', delete=False)
                temp_audio_path = temp_audio.name
                temp_audio.close()

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
                self.progress_updated.emit(50)
                QApplication.processEvents()

                # Load audio and detect non-silent parts with optimized settings
                audio = AudioSegment.from_file(temp_audio_path)
                self.progress_updated.emit(60)
                QApplication.processEvents()

                # Convert to mono for faster processing while maintaining accuracy
                if audio.channels > 1:
                    audio = audio.set_channels(1)

            # Detect non-silent parts with optimized parameters
            non_silent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_duration,
                silence_thresh=self.silence_threshold,
                seek_step=1  # Add seek_step for faster processing
            )
            self.progress_updated.emit(70)
            QApplication.processEvents()

            if non_silent_ranges:
                pass
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
                    pass
                    if start <= current_end:  # Overlap found
                        # Extend current range
                        current_end = max(current_end, end)
                    else:
                        # No overlap, add current range and start a new one
                        merged_ranges.append((current_start, current_end))
                        current_start, current_end = start, end

                # Add the last range
                merged_ranges.append((current_start, current_end))

                non_silent_ranges = merged_ranges

            # Convert non-silent ranges to silent ranges
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

            self.progress_updated.emit(80)
            QApplication.processEvents()

            if silent_ranges:
                pass
                for i, (start, end) in enumerate(silent_ranges[:5]):  # Show first 5
                    print(f"  Silent range {i+1}: {start}ms - {end}ms (duration: {end-start}ms)")
                if len(silent_ranges) > 5:
                    print(f"  ... and {len(silent_ranges) - 5} more ranges")

            # Filter out silent ranges shorter than the minimum duration
            filtered_silent_ranges = [(start, end) for start, end in silent_ranges if end - start >= self.min_silence_duration]

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

            # Clean up temp file (only for video files)
            if not is_audio_only:
                pass
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass

                # Clean up video clip
                try:
                    video.close()
                except:
                    pass

            # Final progress update
            self.progress_updated.emit(100)
            QApplication.processEvents()

            # Emit results
            self.detection_complete.emit(silent_parts)

        except Exception as e:
            print(f"Error in silence detection: {str(e)}")
            import traceback
            traceback.print_exc()
            self.detection_complete.emit([])

    def run_fast_ffmpeg_detection(self):
        """Fast silence detection using FFmpeg's silencedetect filter - much faster than pydub"""
        try:
            pass

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
                pass
                if 'silence_start:' in line:
                    pass
                    try:
                        start_time = float(line.split('silence_start:')[1].strip())
                        silence_starts.append(start_time)
                    except:
                        pass
                elif 'silence_end:' in line:
                    pass
                    try:
                        end_time = float(line.split('silence_end:')[1].split('|')[0].strip())
                        silence_ends.append(end_time)
                    except:
                        pass

            # Create silence parts from starts and ends
            for i, start in enumerate(silence_starts):
                pass
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


            return silent_parts

        except Exception as e:
            print(f"Fast FFmpeg detection failed: {e}")
            return None

class AudioProcessingThread(QThread):
    """Dedicated thread for processing audio-only files"""
    progress_updated = pyqtSignal(int)
    processing_complete = pyqtSignal(str)

    def __init__(self, audio_path, silent_parts, output_path):
        super().__init__()
        self.audio_path = audio_path
        self.silent_parts = silent_parts
        self.output_path = output_path
        self.ffmpeg_path = self.get_ffmpeg_path()

    def get_ffmpeg_path(self):
        """Try to find FFmpeg executable path"""
        # First try directly if it's in PATH
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                pass
                return "ffmpeg"
        except Exception:
            pass

        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]

        for location in known_locations:
            pass
            if os.path.exists(location):
                pass
                return location

        return "ffmpeg"

    def run(self):
        try:
            pass

            # Load audio using pydub
            from pydub import AudioSegment
            audio = AudioSegment.from_file(self.audio_path)

            self.progress_updated.emit(20)

            # Process the silent parts to get segments to keep
            sorted_parts = sorted(self.silent_parts, key=lambda x: x['start'])
            segments = []
            last_end = 0

            for part in sorted_parts:
                pass
                if part['selected']:  # Only cut if selected
                    if part['start'] > last_end:
                        # Add segment before the silence (convert seconds to milliseconds)
                        start_ms = int(last_end * 1000)
                        end_ms = int(part['start'] * 1000)
                        segment = audio[start_ms:end_ms]
                        segments.append(segment)
                    # Update last_end to be the end of this silent part
                    last_end = part['end']

            self.progress_updated.emit(50)

            # Add the final segment if needed
            if last_end < len(audio) / 1000.0:  # Convert audio length to seconds
                start_ms = int(last_end * 1000)
                final_segment = audio[start_ms:]
                segments.append(final_segment)

            self.progress_updated.emit(70)

            # Combine all segments
            if segments:
                result_audio = segments[0]
                for segment in segments[1:]:
                    result_audio += segment
            else:
                # No segments were cut, use original audio
                result_audio = audio

            self.progress_updated.emit(90)

            # Export the result
            # Determine output format based on file extension
            output_ext = os.path.splitext(self.output_path)[1].lower()

            if output_ext == '.mp3':
                result_audio.export(self.output_path, format="mp3", bitrate="192k")
            elif output_ext == '.wav':
                result_audio.export(self.output_path, format="wav")
            elif output_ext == '.flac':
                result_audio.export(self.output_path, format="flac")
            elif output_ext == '.aac':
                result_audio.export(self.output_path, format="aac", bitrate="128k")
            elif output_ext == '.ogg':
                result_audio.export(self.output_path, format="ogg")
            elif output_ext == '.m4a':
                result_audio.export(self.output_path, format="mp4", bitrate="192k")
            else:
                # Default to mp3
                result_audio.export(self.output_path, format="mp3", bitrate="192k")

            self.progress_updated.emit(100)
            self.processing_complete.emit(self.output_path)

        except Exception as e:
            print(f"❌ Audio processing error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.processing_complete.emit("")

class ProcessingThread(ResolutionAwareProcessingMixin, QThread):
    progress_updated = pyqtSignal(int)
    processing_complete = pyqtSignal(str)

    def __init__(self, video_path, silent_parts, output_path):
        super().__init__()
        self.video_path = video_path
        self.silent_parts = silent_parts
        self.output_path = output_path
        self.ffmpeg_path = self.get_ffmpeg_path()

        # Initialize resolution optimizer if available
        if RESOLUTION_OPTIMIZER_AVAILABLE:
            self.resolution_optimizer = ResolutionOptimizer()
            self.optimization_settings = self.resolution_optimizer.get_optimized_settings(video_path)
            self.resolution_optimizer.print_optimization_summary(video_path, self.optimization_settings)
        else:
            self.optimization_settings = {}

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
                pass
                return "ffmpeg"  # ffmpeg is in PATH and working
        except Exception:
            pass  # ffmpeg not in PATH or not working

        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]

        for location in known_locations:
            pass
            if os.path.exists(location):
                pass
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
            pass
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
                pass
                if stderr:
                    pass
                    return False, f"FFmpeg reported errors: {stderr}"
                else:
                    pass
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

            # Get the FFmpeg path - try environment or fallback to known location
            ffmpeg_path = self.get_ffmpeg_path()

            # Set the FFmpeg binary location explicitly
            if ffmpeg_path != "ffmpeg":
                mp.config.change_settings({"FFMPEG_BINARY": ffmpeg_path})

            # Validate the video file first
            is_valid, error_message = self.validate_video_file(self.video_path)
            if not is_valid:
                raise RuntimeError(f"Video file validation failed: {error_message}")

            # Check if input file exists
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Video file not found: {self.video_path}")


            # Initialize VideoFileClip with explicit parameters for better compatibility
            video = None
            try:
                # Try standard MoviePy loading
                video = mp.VideoFileClip(self.video_path, audio=True, verbose=False)
                # Test video access to make sure it can be read
                test_frame = video.get_frame(0)  # Get first frame to test
            except Exception as initial_error:
                # If standard loading fails, try alternative approach
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
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )

                    if result.returncode != 0:
                        stderr = result.stderr.decode('utf-8', errors='ignore')
                        raise RuntimeError(f"Failed to create a clean video copy: {stderr}")

                    # Now try to load the clean copy
                    video = mp.VideoFileClip(temp_video_path, audio=True, verbose=False)
                    test_frame = video.get_frame(0)  # Test again

                    # Update the video path to use the clean copy
                    self.video_path = temp_video_path
                except Exception as alt_error:
                    raise RuntimeError(f"Could not load video file using any method: {str(initial_error)}\nAlternative method error: {str(alt_error)}")


            # Process the silent parts to get a list of segments
            sorted_parts = sorted(self.silent_parts, key=lambda x: x['start'])
            segments = []
            last_end = 0

            self.progress_updated.emit(20)
            QApplication.processEvents()

            for part in sorted_parts:
                pass
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
                pass
                try:
                    final_segment = video.subclip(last_end, video.duration)
                    segments.append(final_segment)
                except Exception as e:
                    print(f"Error creating final segment {last_end} to {video.duration}: {str(e)}")

            self.progress_updated.emit(30)
            QApplication.processEvents()

            # If no segments were cut, just use the original video
            if not segments:
                result = video
            else:
                pass
                try:
                    # Concatenate all segments
                    print(f"Concatenating {len(segments)} video segments")
                    result = mp.concatenate_videoclips(segments)
                except Exception as e:
                    print(f"Error concatenating clips: {str(e)}")
                    # Fallback to using the original video
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
                    timer.stop()
                    return

                if current_time - self.last_update_time >= 1.0:  # Update every second
                    self.last_update_time = current_time

                    # Estimate progress based on elapsed time and video duration
                    if hasattr(self, '_video_duration') and self._video_duration > 0:
                        # Estimate total processing time (typically 2-3x video duration)
                        estimated_total_time = self._video_duration * 2.5
                        time_based_progress = (elapsed_total / estimated_total_time) * 95
                        time_based_progress = min(95, max(self.last_progress, time_based_progress))

                        # Use smooth progression towards estimated progress
                        if time_based_progress > self.last_progress:
                            self.last_progress = time_based_progress
                        else:
                            # Fallback gentle increment
                            increment = 0.5 if self.last_progress < 70 else 0.3
                            self.last_progress = min(95, self.last_progress + increment)
                    else:
                        # Fallback time-based increments
                        if elapsed_total < 60:
                            increment = 1.0
                        elif elapsed_total < 180:
                            increment = 0.6
                        else:
                            increment = 0.3
                        self.last_progress = min(95, self.last_progress + increment)
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

                # Prepare FFmpeg parameters for hardware acceleration
                # Use resolution-optimized parameters if available
                if RESOLUTION_OPTIMIZER_AVAILABLE and hasattr(self, 'optimization_settings'):
                    ffmpeg_params = self.get_optimized_ffmpeg_params(video_codec)
                else:
                    # Fallback to standard parameters
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
                    # Get file size for reporting (but don't block on it)
                    try:
                        file_size = os.path.getsize(self.output_path)
                    except:
                        pass
                else:
                    raise RuntimeError("Output file was not created by MoviePy")

            except Exception as e:
                timer.stop()
                print(f"Error during video writing: {str(e)}")
                raise e
            finally:
                # Clean up resources
                try:
                    pass
                    if 'video' in locals():
                        video.close()
                    if 'result' in locals() and result != video:
                        result.close()
                except Exception as cleanup_error:
                    print(f"Error during cleanup: {str(cleanup_error)}")

            # Smooth transition to completion
            for progress in [96, 97, 98, 99, 100]:
                self.progress_updated.emit(progress)
                QApplication.processEvents()
                time.sleep(0.02)  # Very brief pause for smooth animation

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
        except:
            pass

        # Fallback to software encoding
        if not hw_options:
            hw_options.append(('libx264', 'Software (CPU)'))

        return hw_options

    def run_fast_ffmpeg_processing(self):
        """Fast video processing using direct FFmpeg with hardware acceleration"""
        try:
            pass

            # Detect available hardware acceleration
            hw_options = self.detect_hardware_acceleration()
            video_codec, hw_name = hw_options[0]  # Use the first (best) available option

            # Get selected silent parts
            selected_parts = [part for part in self.silent_parts if part['selected']]
            if not selected_parts:
                pass
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
                pass
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
            # Use resolution-optimized parameters if available
            if RESOLUTION_OPTIMIZER_AVAILABLE and hasattr(self, 'optimization_settings'):
                optimized_params = self.get_optimized_ffmpeg_params(video_codec)
                # Remove the pixel format since it's already added above
                optimized_params = [p for p in optimized_params if p != '-pix_fmt' and p != 'yuv420p']
                cmd.extend(optimized_params)
            else:
                # Fallback to standard parameters
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

            print(f"Command: {' '.join(cmd[:12])}...")  # Show partial command
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
                        pass
                        break
                    output_lines.append(line.strip())

                    # Parse FFmpeg progress from time= output
                    if "time=" in line:
                        pass
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
                                        progress_percent = min(99, (current_time_seconds / self._video_duration) * 100)
                                        if progress_percent > current_progress:
                                            current_progress = progress_percent
                                            self.progress_updated.emit(int(current_progress))
                                            QApplication.processEvents()
                        except:
                            pass  # Ignore parsing errors

                    # Look for completion indicators
                    if "video:" in line.lower() and "audio:" in line.lower() and "subtitle:" in line.lower():
                        pass
                    elif "error" in line.lower():
                        pass

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

                # Parse FFmpeg output for real progress
                progress_updated = False
                if output_lines:
                    latest_output = output_lines[-1] if output_lines else ""

                    # Look for time information in FFmpeg output
                    if "time=" in latest_output:
                        pass
                        try:
                            time_match = latest_output.split("time=")[1].split()[0]
                            time_parts = time_match.split(":")
                            if len(time_parts) == 3:
                                current_time_seconds = (
                                    float(time_parts[0]) * 3600 +
                                    float(time_parts[1]) * 60 +
                                    float(time_parts[2])
                                )
                                if self._video_duration > 0:
                                    # Calculate real progress (0-95% based on actual processing)
                                    real_progress = (current_time_seconds / self._video_duration) * 95
                                    real_progress = max(current_progress, min(95, real_progress))

                                    if real_progress > current_progress + 0.3:  # Update more frequently
                                        current_progress = real_progress
                                        self.progress_updated.emit(int(current_progress))
                                        QApplication.processEvents()
                                        last_progress_time = current_time
                                        progress_updated = True
                        except:
                            pass

                # More aggressive fallback progress if no FFmpeg time detected
                if not progress_updated and current_time - last_progress_time >= 1.0:  # Update every second
                    # Estimate progress based on elapsed time vs expected total time
                    if self._video_duration > 0:
                        # Assume processing takes roughly 1.5-2x the video duration
                        estimated_total_time = self._video_duration * 1.8
                        time_based_progress = (elapsed / estimated_total_time) * 95
                        time_based_progress = min(95, max(current_progress, time_based_progress))

                        if time_based_progress > current_progress:
                            current_progress = time_based_progress
                            self.progress_updated.emit(int(current_progress))
                            QApplication.processEvents()
                            last_progress_time = current_time
                            progress_updated = True

                    # Final fallback: steady increments
                    if not progress_updated:
                        increment = 1.0 if current_progress < 70 else 0.5
                        new_progress = min(95, current_progress + increment)

                        if new_progress > current_progress:
                            current_progress = new_progress
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
                # Check if output file was actually created
                if os.path.exists(self.output_path):
                    # Smooth transition to completion
                    for progress in [96, 97, 98, 99, 100]:
                        self.progress_updated.emit(progress)
                        QApplication.processEvents()
                        time.sleep(0.02)  # Very brief pause for smooth animation

                    # Get file size for reporting (but don't block on it)
                    try:
                        file_size = os.path.getsize(self.output_path)
                        if file_size <= 1024:  # Less than 1KB is suspicious
                            print(f"Warning: Output file is very small ({file_size} bytes)")
                    except:
                        file_size = 0  # If we can't get size, continue anyway

                    elapsed_total = time.time() - start_time
                    if file_size > 0:
                        pass
                    else:
                        pass
                    return self.output_path
                else:
                    pass
                    return ""
            else:
                pass
                if all_output:
                    print(f"FFmpeg output: {all_output[-500:]}")  # Show last 500 chars
                return ""

        except Exception as e:
            print(f"Hardware-accelerated FFmpeg processing error: {e}")
            return ""

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
                pass
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
            pass
            if os.path.exists(location):
                pass
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
        self.setMinimumHeight(190)  # Increased by 40px for top/bottom padding
        self.setMaximumHeight(260)  # Increased by 40px for top/bottom padding

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
            pass
            if event.key() == Qt.Key_Z:
                self.undo()
                event.accept()
                return
        elif event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            pass
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
        """Zoom in the timeline keeping playhead centered"""
        old_zoom = self.zoom_level
        self.zoom_level = min(self.max_zoom, self.zoom_level * 1.2)

        # Adjust offset to keep playhead centered during zoom
        if old_zoom != self.zoom_level and self.duration_seconds > 0:
            # Calculate where the playhead should be positioned (center of view)
            playhead_ratio = self.current_position / self.duration_seconds
            new_visible_range = 1.0 / self.zoom_level

            # Position offset so playhead is in center of visible area
            self.zoom_offset = max(0.0, min(1.0 - new_visible_range,
                                          playhead_ratio - new_visible_range / 2))
            self.update()

    def zoom_out(self):
        """Zoom out the timeline keeping playhead centered"""
        # Only allow zooming out if currently above 1.0x scale
        if self.zoom_level > 1.0:
            old_zoom = self.zoom_level
            self.zoom_level = max(1.0, self.zoom_level / 1.2)

            # Adjust offset to keep playhead centered during zoom out
            if old_zoom != self.zoom_level and self.duration_seconds > 0:
                playhead_ratio = self.current_position / self.duration_seconds
                new_visible_range = 1.0 / self.zoom_level

                # Position offset so playhead is in center of visible area
                self.zoom_offset = max(0.0, min(1.0 - new_visible_range,
                                              playhead_ratio - new_visible_range / 2))

        # Ensure offset stays within bounds
        max_offset = max(0.0, 1.0 - (1.0 / self.zoom_level))
        self.zoom_offset = min(max_offset, self.zoom_offset)
        self.update()

    def reset_zoom(self):
        """Reset zoom to normal level"""
        self.zoom_level = 1.0
        self.zoom_offset = 0.0
        self.update()

    def handle_resize(self):
        """Handle timeline widget resize - clear cache and force redraw for proper waveform scaling"""
        if hasattr(self, 'waveform_cache'):
            self.waveform_cache.clear()

        # Force immediate update to redraw waveform with new dimensions
        self.update()

    def resizeEvent(self, event):
        """Handle resize events for the timeline widget"""
        super().resizeEvent(event)

        # Clear waveform cache when timeline widget is resized to ensure proper scaling
        if hasattr(self, 'waveform_cache') and self.waveform_data:
            self.waveform_cache.clear()
            # Small delay to allow layout to settle before redrawing
            QTimer.singleShot(50, self.update)

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
            pass
        else:
            pass
        self.update()  # Trigger repaint

        # NOW hide the loading overlay since waveform loading is complete
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'hide_loading_overlay'):
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
            else:
                self.preview_timeline_duration = self.duration_seconds
        else:
            self.preview_timeline_duration = None

        # Just trigger a repaint to show preview mode visualization
        self.update()

    def get_effective_duration(self):
        """Get the effective timeline duration - ALWAYS return original duration for timeline display"""
        # The timeline should ALWAYS show the complete original duration
        # Preview mode only affects playback behavior, not the visual timeline
        return self.duration_seconds

    def convert_click_position_to_original_time(self, click_time_seconds):
        """Convert a click position on the timeline to original video time"""
        if not self.preview_mode or not hasattr(self, 'preview_timeline_duration'):
            # Normal mode: click time is already in original timeline
            return click_time_seconds

        # Since we're always clicking on the original timeline/waveform,
        # no conversion is needed - the click is already in original time coordinates
        return click_time_seconds

    def original_time_to_preview_time(self, original_time):
        """Convert original video time to preview timeline position"""
        if not self.preview_mode or not self.silent_parts:
            pass
            return original_time

        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]

    def handle_resize(self):
        """Handle timeline widget resize - clear cache and force redraw for proper waveform scaling"""
        if hasattr(self, 'waveform_cache'):
            self.waveform_cache.clear()

        # Force immediate update to redraw waveform with new dimensions
        self.update()

    def resizeEvent(self, event):
        """Handle resize events for the timeline widget"""
        super().resizeEvent(event)

        # Clear waveform cache when timeline widget is resized to ensure proper scaling
        if hasattr(self, 'waveform_cache') and self.waveform_data:
            self.waveform_cache.clear()
            # Small delay to allow layout to settle before redrawing
            QTimer.singleShot(50, self.update)

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
            pass
        else:
            pass
        self.update()  # Trigger repaint

        # NOW hide the loading overlay since waveform loading is complete
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'hide_loading_overlay'):
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
            else:
                self.preview_timeline_duration = self.duration_seconds
        else:
            self.preview_timeline_duration = None

        # Just trigger a repaint to show preview mode visualization
        self.update()

    def get_effective_duration(self):
        """Get the effective timeline duration - ALWAYS return original duration for timeline display"""
        # The timeline should ALWAYS show the complete original duration
        # Preview mode only affects playback behavior, not the visual timeline
        return self.duration_seconds

    def convert_click_position_to_original_time(self, click_time_seconds):
        """Convert a click position on the timeline to original video time"""
        if not self.preview_mode or not hasattr(self, 'preview_timeline_duration'):
            # Normal mode: click time is already in original timeline
            return click_time_seconds

        # Since we're always clicking on the original timeline/waveform,
        # no conversion is needed - the click is already in original time coordinates
        return click_time_seconds

    def original_time_to_preview_time(self, original_time):
        """Convert original video time to preview timeline position"""
        if not self.preview_mode or not self.silent_parts:
            pass
            return original_time

        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]
        if not selected_silent_parts:
            pass
            return original_time

        # Sort by start time
        selected_silent_parts.sort(key=lambda x: x['start'])

        # Build segments that will be kept
        preview_segments = []
        last_end = 0

        for silent_part in selected_silent_parts:
            pass
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
            pass
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
        # ALWAYS use original timeline coordinates since the timeline always shows the original duration
        original_duration = self.duration_seconds
        visible_duration = original_duration / self.zoom_level
        start_time = self.zoom_offset * original_duration
        end_time = start_time + visible_duration

        # Ensure we don't go beyond the original duration
        start_time = max(0, start_time)
        end_time = min(original_duration, end_time)
        return start_time, end_time

    def time_to_x(self, time_seconds, timeline_rect):
        """Convert time to X coordinate considering zoom and offset"""
        start_time, end_time = self.get_visible_time_range()
        if end_time == start_time:
            pass
            return timeline_rect.left()
        relative_pos = (time_seconds - start_time) / (end_time - start_time)
        return timeline_rect.left() + relative_pos * timeline_rect.width()

    def original_time_to_x(self, time_seconds, timeline_rect):
        """Convert original timeline time to X coordinate (for waveform and silence regions)"""
        start_time, end_time = self.get_original_visible_time_range()
        if end_time == start_time:
            pass
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


        return original_time
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
            pass
            for i, sample in enumerate(samples):
                timestamp = start_time + (i / self.sample_rate)
                self.buffer.append(sample)
                self.timestamps.append(timestamp)

    def get_samples(self, start_time, duration):
        """Get audio samples for specific time range"""
        with self.lock:
            pass
            if not self.timestamps:
                pass
                return []

            end_time = start_time + duration
            samples = []

            for i, timestamp in enumerate(self.timestamps):
                pass
                if start_time <= timestamp <= end_time:
                    pass
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
            detected_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            # Ensure minimum 30 FPS for smooth playback
            self.fps = max(detected_fps, 30)
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Get actual video duration using moviepy for accuracy
            try:
                import moviepy.editor as mp
                video_clip = mp.VideoFileClip(self.video_path)
                self.actual_duration = video_clip.duration
                video_clip.close()
            except:
                self.actual_duration = self.frame_count / self.fps if self.fps > 0 else 0

            # Calculate frame duration based on actual duration instead of FPS
            if self.frame_count > 0 and self.actual_duration > 0:
                self.frame_duration = self.actual_duration / self.frame_count
            else:
                self.frame_duration = 1.0 / self.fps


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

                # Store the verified duration
                self.verified_audio_duration = extracted_audio_duration
                self.duration_difference = abs(video_duration - extracted_audio_duration)

                if self.duration_difference > 0.1:
                    print(f"WARNING: Audio-video duration mismatch: {self.duration_difference:.3f}s difference")
                else:
                    pass

                video_clip.close()

                # Load audio into pygame
                pygame.mixer.music.load(self.temp_audio_file.name)
                self.audio_loaded = True
                self.preview_audio_segments = []  # Will store segmented audio for preview
            else:
                pass

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


            if self.audio_loaded:
                pass
                try:
                    # Play preview audio from the correct preview position
                    pygame.mixer.music.play(start=preview_position)
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
                pass
                try:
                    # Enhanced audio start with synchronization verification
                    pygame.mixer.music.play(start=audio_position)

                    # Log detailed playback synchronization info

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
            pass
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
            pass
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.play(start=precise_audio_position)

                # Immediately update playback timing to compensate for pygame seeking inaccuracy
                # We calculate the offset from expected position
                self.seek_audio_offset = precise_audio_position
                self.seek_time = current_time

            except Exception as e:
                print(f"Error seeking audio: {e}")
        else:
            # If not playing, still reset timing for when playback starts
            self.playback_start_time = current_time

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
                pass
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=target_time_seconds)  # Use preview timeline


                except Exception as e:
                    print(f"Error seeking preview audio: {e}")
            else:
                pass
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
                pass
                if exact_timeline_position > self.verified_audio_duration:
                    exact_timeline_position = self.verified_audio_duration

            # Reset playback timing to match the exact timeline position
            current_time = time.time()
            self.playback_start_time = current_time - exact_timeline_position
            self.playback_initial_frame = target_frame

            # Enhanced audio seeking with EXACT timeline position
            if self.audio_loaded and self.is_playing:
                pass
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=exact_timeline_position)


                except Exception as e:
                    print(f"Error seeking audio: {e}")
            else:
                pass

        self.mutex.unlock()

    def stop_playback(self):
        """Stop the thread"""
        self.mutex.lock()
        self.stop_requested = True
        self.is_playing = False
        self.playback_started = False  # Reset playback tracking
        if self.audio_loaded:
            pass
            try:
                pygame.mixer.music.stop()
            except:
                pass
        self.mutex.unlock()

    def run(self):
        """Main thread loop with optimized performance for preview mode"""
        if not self.initialize_video():
            pass
            return

        # Use original video framerate for accurate playback
        target_fps = self.fps
        target_frame_time = 1.0 / target_fps

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
                        pass
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
                            pass
                            try:
                                pygame.mixer.music.stop()
                            except:
                                pass

                # Always process frames to maintain original framerate
                should_process_frame = True

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

                            # Update UI at video framerate for smooth playback
                            current_time = time.time()
                            ui_update_interval = 1.0 / target_fps  # Match video framerate
                            if current_time - last_ui_update >= ui_update_interval:
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
            pass
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
            pass
            for i, sample in enumerate(samples):
                timestamp = start_time + (i / self.sample_rate)
                self.buffer.append(sample)
                self.timestamps.append(timestamp)

    def get_samples(self, start_time, duration):
        """Get audio samples for specific time range"""
        with self.lock:
            pass
            if not self.timestamps:
                pass
                return []

            end_time = start_time + duration
            samples = []

            for i, timestamp in enumerate(self.timestamps):
                pass
                if start_time <= timestamp <= end_time:
                    pass
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
            detected_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            # Ensure minimum 30 FPS for smooth playback
            self.fps = max(detected_fps, 30)
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Get actual video duration using moviepy for accuracy
            try:
                import moviepy.editor as mp
                video_clip = mp.VideoFileClip(self.video_path)
                self.actual_duration = video_clip.duration
                video_clip.close()
            except:
                self.actual_duration = self.frame_count / self.fps if self.fps > 0 else 0

            # Calculate frame duration based on actual duration instead of FPS
            if self.frame_count > 0 and self.actual_duration > 0:
                self.frame_duration = self.actual_duration / self.frame_count
            else:
                self.frame_duration = 1.0 / self.fps


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

                # Store the verified duration
                self.verified_audio_duration = extracted_audio_duration
                self.duration_difference = abs(video_duration - extracted_audio_duration)

                if self.duration_difference > 0.1:
                    print(f"WARNING: Audio-video duration mismatch: {self.duration_difference:.3f}s difference")
                else:
                    pass

                video_clip.close()

                # Load audio into pygame
                pygame.mixer.music.load(self.temp_audio_file.name)
                self.audio_loaded = True
                self.preview_audio_segments = []  # Will store segmented audio for preview
            else:
                pass

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


            if self.audio_loaded:
                pass
                try:
                    # Play preview audio from the correct preview position
                    pygame.mixer.music.play(start=preview_position)
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
                pass
                try:
                    # Enhanced audio start with synchronization verification
                    pygame.mixer.music.play(start=audio_position)

                    # Log detailed playback synchronization info

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
            pass
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
            pass
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.play(start=precise_audio_position)

                # Immediately update playback timing to compensate for pygame seeking inaccuracy
                # We calculate the offset from expected position
                self.seek_audio_offset = precise_audio_position
                self.seek_time = current_time

            except Exception as e:
                print(f"Error seeking audio: {e}")
        else:
            # If not playing, still reset timing for when playback starts
            self.playback_start_time = current_time

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
                pass
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=target_time_seconds)  # Use preview timeline


                except Exception as e:
                    print(f"Error seeking preview audio: {e}")
            else:
                pass
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
                pass
                if exact_timeline_position > self.verified_audio_duration:
                    exact_timeline_position = self.verified_audio_duration

            # Reset playback timing to match the exact timeline position
            current_time = time.time()
            self.playback_start_time = current_time - exact_timeline_position
            self.playback_initial_frame = target_frame

            # Enhanced audio seeking with EXACT timeline position
            if self.audio_loaded and self.is_playing:
                pass
                try:
                    pygame.mixer.music.stop()
                    time.sleep(0.001)
                    pygame.mixer.music.play(start=exact_timeline_position)


                except Exception as e:
                    print(f"Error seeking audio: {e}")
            else:
                pass

        self.mutex.unlock()

    def stop_playback(self):
        """Stop the thread"""
        self.mutex.lock()
        self.stop_requested = True
        self.is_playing = False
        self.playback_started = False  # Reset playback tracking
        if self.audio_loaded:
            pass
            try:
                pygame.mixer.music.stop()
            except:
                pass
        self.mutex.unlock()

    def run(self):
        """Main thread loop with optimized performance for preview mode"""
        if not self.initialize_video():
            pass
            return

        # Use original video framerate for accurate playback
        target_fps = self.fps
        target_frame_time = 1.0 / target_fps

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
                        pass
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
                            pass
                            try:
                                pygame.mixer.music.stop()
                            except:
                                pass

                # Always process frames to maintain original framerate
                should_process_frame = True

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

                            # Update UI at video framerate for smooth playback
                            current_time = time.time()
                            ui_update_interval = 1.0 / target_fps  # Match video framerate
                            if current_time - last_ui_update >= ui_update_interval:
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
            pass
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
            pass
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

                    break

                accumulated_time += segment_duration
            else:
                # If we get here, we've played through all segments
                self._cached_target_frame = self.frame_count - 1

        return getattr(self, '_cached_target_frame', initial_frame)

    def process_frame_fast(self, frame):
        """Process frame with balanced quality and performance"""
        try:
            # Balance between quality and performance
            height, width = frame.shape[:2]
            original_size = f"{width}x{height}"

            # Determine target resolution based on input resolution
            if RESOLUTION_OPTIMIZER_AVAILABLE:
                # Use adaptive scaling based on input resolution
                if width >= 7680:  # 8K
                    target_width = 1920  # 1080p preview for 8K
                    interpolation = cv2.INTER_AREA  # Better for downscaling
                elif width >= 3840:  # 4K
                    target_width = 1920  # 1080p preview for 4K
                    interpolation = cv2.INTER_AREA
                elif width >= 1920:  # 1080p
                    target_width = 1280  # 720p preview for 1080p
                    interpolation = cv2.INTER_LINEAR
                else:
                    target_width = 1280  # 720p target for lower resolutions
                    interpolation = cv2.INTER_LINEAR
            else:
                # Fallback to original behavior
                target_width = 1280  # 720p width
                interpolation = cv2.INTER_LINEAR

            if width > target_width:
                scale = target_width / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=interpolation)

            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w

            # Create Qt image and pixmap with optimized format
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            return pixmap
        except:
            pass
            return None

    def process_frame_ultra_fast(self, frame):
        """Fast frame processing for preview mode - maintains good quality"""
        try:
            height, width = frame.shape[:2]

            # Use resolution-aware scaling for ultra-fast mode
            if RESOLUTION_OPTIMIZER_AVAILABLE:
                # More aggressive scaling for ultra-fast mode
                if width >= 7680:  # 8K
                    target_width = 1280  # 720p preview for 8K ultra-fast
                    interpolation = cv2.INTER_NEAREST  # Fastest for 8K
                elif width >= 3840:  # 4K
                    target_width = 1280  # 720p preview for 4K ultra-fast
                    interpolation = cv2.INTER_AREA
                elif width >= 1920:  # 1080p
                    target_width = 960   # Smaller preview for 1080p ultra-fast
                    interpolation = cv2.INTER_LINEAR
                else:
                    target_width = 1280  # 720p target for lower resolutions
                    interpolation = cv2.INTER_LINEAR
            else:
                # Fallback to original behavior
                target_width = 1280  # 720p width
                interpolation = cv2.INTER_LINEAR

            if width > target_width:
                scale = target_width / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=interpolation)

            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w

            # Create Qt image and pixmap
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            return pixmap
        except:
            pass
            return None

    def prefetch_frames(self, current_frame):
        """Prefetch nearby frames for smoother playback - lightweight version"""
        if not self.buffer_enabled or not self.prefetch_enabled:
            pass
            return

        # Only prefetch 2-3 frames ahead to minimize performance impact
        def prefetch_worker():
            try:
                pass
                for offset in range(1, min(self.prefetch_range, 3)):  # Only 2-3 frames ahead
                    target_frame = current_frame + offset
                    if target_frame >= self.frame_count:
                        pass
                        break

                    # Check if frame is already in buffer
                    if self.frame_buffer.get(target_frame) is not None:
                        pass
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
                except Exception as e:
                    print(f"Error loading preview audio: {e}")
            else:
                pass
        else:
            self.silent_parts = []
            self.preview_segments = []
            self.preview_duration = 0

            # Restore original audio
            if self.audio_loaded and hasattr(self, 'temp_audio_file'):
                pass
                try:
                    pygame.mixer.music.load(self.temp_audio_file.name)
                except Exception as e:
                    print(f"Error restoring original audio: {e}")
        self.mutex.unlock()

    def get_effective_duration(self):
        """Get the effective timeline duration (preview duration in preview mode, original otherwise)"""
        if self.preview_mode and hasattr(self, 'preview_timeline_duration') and self.preview_timeline_duration is not None:
            pass
            return self.preview_timeline_duration
        return self.duration_seconds

    def convert_click_position_to_original_time(self, click_time_seconds):
        """Convert a click position on the timeline to original video time"""
        if not self.preview_mode or not hasattr(self, 'preview_timeline_duration'):
            # Normal mode: click time is already in original timeline
            return click_time_seconds

        # Preview mode: convert preview timeline position to original timeline position
        if not self.silent_parts:
            pass
            return click_time_seconds

        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]
        if not selected_silent_parts:
            pass
            return click_time_seconds

        # Sort by start time
        selected_silent_parts.sort(key=lambda x: x['start'])

        # Build segments that will be kept (same logic as video thread)
        preview_segments = []
        last_end = 0

        for silent_part in selected_silent_parts:
            pass
            if silent_part['start'] > last_end:
                # Add segment before this silent part
                preview_segments.append((last_end, silent_part['start']))
            last_end = silent_part['end']

        # Add final segment if needed
        if last_end < self.duration_seconds:
            preview_segments.append((last_end, self.duration_seconds))

        # Convert preview timeline position to original time
        if click_time_seconds <= 0:
            pass
            return preview_segments[0][0] if preview_segments else 0

        accumulated_time = 0
        for start, end in preview_segments:
            segment_duration = end - start
            if accumulated_time + segment_duration >= click_time_seconds:
                # The position is within this segment
                offset_in_segment = click_time_seconds - accumulated_time
                original_time = start + offset_in_segment
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
            pass
            if silent_part['start'] > last_end:
                # Add segment before this silent part
                self.preview_segments.append((last_end, silent_part['start']))
            last_end = silent_part['end']

        # Add final segment if needed
        if last_end < self.actual_duration:
            self.preview_segments.append((last_end, self.actual_duration))

        # Calculate total preview duration correctly
        self.preview_duration = sum(end - start for start, end in self.preview_segments)

        for i, (start, end) in enumerate(self.preview_segments):
            print(f"  Segment {i+1}: {start:.3f}s - {end:.3f}s (duration: {end-start:.3f}s)")

    def preview_time_to_original_time(self, preview_time):
        """Convert preview timeline position to original video time"""
        if not self.preview_mode or not self.preview_segments:
            pass
            return preview_time

        if preview_time <= 0:
            pass
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
            pass
            return original_time

        accumulated_preview_time = 0
        for start, end in self.preview_segments:
            pass
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
            pass
            return False

        try:
            import tempfile
            import moviepy.editor as mp
            from pydub import AudioSegment


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

            # Concatenate all segments
            if preview_audio_segments:
                preview_audio = sum(preview_audio_segments)

                # Save preview audio to temporary file
                self.temp_preview_audio_file = tempfile.NamedTemporaryFile(suffix='_preview.wav', delete=False)
                self.temp_preview_audio_file.close()

                preview_audio.export(self.temp_preview_audio_file.name, format="wav")


                return True
            else:
                pass
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
            pass

            # Check if this is an audio-only file
            audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
            file_ext = os.path.splitext(self.video_path)[1].lower()
            is_audio_only = file_ext in audio_extensions

            if is_audio_only:
                self.progress_updated.emit("Loading audio file...")

                # Load audio directly using pydub
                from pydub import AudioSegment
                audio = AudioSegment.from_file(self.video_path)

                # Emit duration immediately for instant timeline setup
                duration_seconds = len(audio) / 1000.0
                self.duration_loaded.emit(duration_seconds)

                self.progress_updated.emit("Processing audio data...")

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
                target_samples = 1500
                if len(samples) > target_samples:
                    step = len(samples) // target_samples
                    samples = samples[::step]

                max_amplitude = max(abs(s) for s in samples) if samples else 1.0

                self.progress_updated.emit("Audio waveform ready!")

                # Emit the loaded waveform data
                self.waveform_loaded.emit(samples, max_amplitude)
                return

            else:
                # Handle video files
                self.progress_updated.emit("Loading video file...")

                # Extract audio using MoviePy
                import moviepy.editor as mp
                video = mp.VideoFileClip(self.video_path)

                # Emit duration immediately for instant timeline setup
                if video.duration > 0:
                    self.duration_loaded.emit(video.duration)

                self.progress_updated.emit("Extracting audio track...")

                if video.audio is None:
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

                self.progress_updated.emit("Video waveform ready!")

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
                pass
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
            pass
            if os.path.exists(location):
                pass
                return location

        # Could not find FFmpeg, will use just the command and hope it works
        return "ffmpeg"

    def run(self):
        try:
            # Use the accurate pydub-based detection for better results
            # Skip fast FFmpeg detection to maintain accuracy

            # Start with initial progress
            self.progress_updated.emit(5)
            QApplication.processEvents()  # Process events to update GUI

            # Check if this is an audio-only file
            audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
            file_ext = os.path.splitext(self.video_path)[1].lower()
            is_audio_only = file_ext in audio_extensions

            if is_audio_only:
                self.progress_updated.emit(10)
                QApplication.processEvents()

                # For audio files, load directly with pydub
                audio = AudioSegment.from_file(self.video_path)
                audio_duration_ms = len(audio)
                self.progress_updated.emit(40)
                QApplication.processEvents()

                # Convert to mono for faster processing while maintaining accuracy
                if audio.channels > 1:
                    audio = audio.set_channels(1)

                self.progress_updated.emit(60)
                QApplication.processEvents()

            else:
                # For video files, extract audio using moviepy
                # Modify moviepy's FFMPEG_BINARY setting to use our detected FFmpeg path
                from moviepy.config import change_settings
                change_settings({"FFMPEG_BINARY": self.ffmpeg_path})

                # Extract audio from video more efficiently
                self.progress_updated.emit(10)
                QApplication.processEvents()

                # Load video more efficiently
                video = mp.VideoFileClip(self.video_path)
                audio_duration_ms = int(video.audio.duration * 1000)
                self.progress_updated.emit(20)
                QApplication.processEvents()

                # Create temporary audio file with optimized settings
                temp_audio = tempfile.NamedTemporaryFile(suffix=f'_sid_{os.getpid()}_{int(time.time())}.wav', delete=False)
                temp_audio_path = temp_audio.name
                temp_audio.close()

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
                self.progress_updated.emit(50)
                QApplication.processEvents()

                # Load audio and detect non-silent parts with optimized settings
                audio = AudioSegment.from_file(temp_audio_path)
                self.progress_updated.emit(60)
                QApplication.processEvents()

                # Convert to mono for faster processing while maintaining accuracy
                if audio.channels > 1:
                    audio = audio.set_channels(1)

            # Detect non-silent parts with optimized parameters
            non_silent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_duration,
                silence_thresh=self.silence_threshold,
                seek_step=1  # Add seek_step for faster processing
            )
            self.progress_updated.emit(70)
            QApplication.processEvents()

            if non_silent_ranges:
                pass
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
                    pass
                    if start <= current_end:  # Overlap found
                        # Extend current range
                        current_end = max(current_end, end)
                    else:
                        # No overlap, add current range and start a new one
                        merged_ranges.append((current_start, current_end))
                        current_start, current_end = start, end

                # Add the last range
                merged_ranges.append((current_start, current_end))

                non_silent_ranges = merged_ranges

            # Convert non-silent ranges to silent ranges
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

            self.progress_updated.emit(80)
            QApplication.processEvents()

            if silent_ranges:
                pass
                for i, (start, end) in enumerate(silent_ranges[:5]):  # Show first 5
                    print(f"  Silent range {i+1}: {start}ms - {end}ms (duration: {end-start}ms)")
                if len(silent_ranges) > 5:
                    print(f"  ... and {len(silent_ranges) - 5} more ranges")

            # Filter out silent ranges shorter than the minimum duration
            filtered_silent_ranges = [(start, end) for start, end in silent_ranges if end - start >= self.min_silence_duration]

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

            # Clean up temp file (only for video files)
            if not is_audio_only:
                pass
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass

                # Clean up video clip
                try:
                    video.close()
                except:
                    pass

            # Final progress update
            self.progress_updated.emit(100)
            QApplication.processEvents()

            # Emit results
            self.detection_complete.emit(silent_parts)

        except Exception as e:
            print(f"Error in silence detection: {str(e)}")
            import traceback
            traceback.print_exc()
            self.detection_complete.emit([])

    def run_fast_ffmpeg_detection(self):
        """Fast silence detection using FFmpeg's silencedetect filter - much faster than pydub"""
        try:
            pass

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
                pass
                if 'silence_start:' in line:
                    pass
                    try:
                        start_time = float(line.split('silence_start:')[1].strip())
                        silence_starts.append(start_time)
                    except:
                        pass
                elif 'silence_end:' in line:
                    pass
                    try:
                        end_time = float(line.split('silence_end:')[1].split('|')[0].strip())
                        silence_ends.append(end_time)
                    except:
                        pass

            # Create silence parts from starts and ends
            for i, start in enumerate(silence_starts):
                pass
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


            return silent_parts

        except Exception as e:
            print(f"Fast FFmpeg detection failed: {e}")
            return None

class AudioProcessingThread(QThread):
    """Dedicated thread for processing audio-only files"""
    progress_updated = pyqtSignal(int)
    processing_complete = pyqtSignal(str)

    def __init__(self, audio_path, silent_parts, output_path):
        super().__init__()
        self.audio_path = audio_path
        self.silent_parts = silent_parts
        self.output_path = output_path
        self.ffmpeg_path = self.get_ffmpeg_path()

    def get_ffmpeg_path(self):
        """Try to find FFmpeg executable path"""
        # First try directly if it's in PATH
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                pass
                return "ffmpeg"
        except Exception:
            pass

        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]

        for location in known_locations:
            pass
            if os.path.exists(location):
                pass
                return location

        return "ffmpeg"

    def run(self):
        try:
            pass

            # Load audio using pydub
            from pydub import AudioSegment
            audio = AudioSegment.from_file(self.audio_path)

            self.progress_updated.emit(20)

            # Process the silent parts to get segments to keep
            sorted_parts = sorted(self.silent_parts, key=lambda x: x['start'])
            segments = []
            last_end = 0

            for part in sorted_parts:
                pass
                if part['selected']:  # Only cut if selected
                    if part['start'] > last_end:
                        # Add segment before the silence (convert seconds to milliseconds)
                        start_ms = int(last_end * 1000)
                        end_ms = int(part['start'] * 1000)
                        segment = audio[start_ms:end_ms]
                        segments.append(segment)
                    # Update last_end to be the end of this silent part
                    last_end = part['end']

            self.progress_updated.emit(50)

            # Add the final segment if needed
            if last_end < len(audio) / 1000.0:  # Convert audio length to seconds
                start_ms = int(last_end * 1000)
                final_segment = audio[start_ms:]
                segments.append(final_segment)

            self.progress_updated.emit(70)

            # Combine all segments
            if segments:
                result_audio = segments[0]
                for segment in segments[1:]:
                    result_audio += segment
            else:
                # No segments were cut, use original audio
                result_audio = audio

            self.progress_updated.emit(90)

            # Export the result
            # Determine output format based on file extension
            output_ext = os.path.splitext(self.output_path)[1].lower()

            if output_ext == '.mp3':
                result_audio.export(self.output_path, format="mp3", bitrate="192k")
            elif output_ext == '.wav':
                result_audio.export(self.output_path, format="wav")
            elif output_ext == '.flac':
                result_audio.export(self.output_path, format="flac")
            elif output_ext == '.aac':
                result_audio.export(self.output_path, format="aac", bitrate="128k")
            elif output_ext == '.ogg':
                result_audio.export(self.output_path, format="ogg")
            elif output_ext == '.m4a':
                result_audio.export(self.output_path, format="mp4", bitrate="192k")
            else:
                # Default to mp3
                result_audio.export(self.output_path, format="mp3", bitrate="192k")

            self.progress_updated.emit(100)
            self.processing_complete.emit(self.output_path)

        except Exception as e:
            print(f"❌ Audio processing error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.processing_complete.emit("")

class ProcessingThread(ResolutionAwareProcessingMixin, QThread):
    progress_updated = pyqtSignal(int)
    processing_complete = pyqtSignal(str)

    def __init__(self, video_path, silent_parts, output_path):
        super().__init__()
        self.video_path = video_path
        self.silent_parts = silent_parts
        self.output_path = output_path
        self.ffmpeg_path = self.get_ffmpeg_path()

        # Initialize resolution optimizer if available
        if RESOLUTION_OPTIMIZER_AVAILABLE:
            self.resolution_optimizer = ResolutionOptimizer()
            self.optimization_settings = self.resolution_optimizer.get_optimized_settings(video_path)
            self.resolution_optimizer.print_optimization_summary(video_path, self.optimization_settings)
        else:
            self.optimization_settings = {}

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
                pass
                return "ffmpeg"  # ffmpeg is in PATH and working
        except Exception:
            pass  # ffmpeg not in PATH or not working

        # Check known locations
        known_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        ]

        for location in known_locations:
            pass
            if os.path.exists(location):
                pass
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
            pass
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
                pass
                if stderr:
                    pass
                    return False, f"FFmpeg reported errors: {stderr}"
                else:
                    pass
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

            # Get the FFmpeg path - try environment or fallback to known location
            ffmpeg_path = self.get_ffmpeg_path()

            # Set the FFmpeg binary location explicitly
            if ffmpeg_path != "ffmpeg":
                mp.config.change_settings({"FFMPEG_BINARY": ffmpeg_path})

            # Validate the video file first
            is_valid, error_message = self.validate_video_file(self.video_path)
            if not is_valid:
                raise RuntimeError(f"Video file validation failed: {error_message}")

            # Check if input file exists
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Video file not found: {self.video_path}")


            # Initialize VideoFileClip with explicit parameters for better compatibility
            video = None
            try:
                # Try standard MoviePy loading
                video = mp.VideoFileClip(self.video_path, audio=True, verbose=False)
                # Test video access to make sure it can be read
                test_frame = video.get_frame(0)  # Get first frame to test
            except Exception as initial_error:
                # If standard loading fails, try alternative approach
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
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )

                    if result.returncode != 0:
                        stderr = result.stderr.decode('utf-8', errors='ignore')
                        raise RuntimeError(f"Failed to create a clean video copy: {stderr}")

                    # Now try to load the clean copy
                    video = mp.VideoFileClip(temp_video_path, audio=True, verbose=False)
                    test_frame = video.get_frame(0)  # Test again

                    # Update the video path to use the clean copy
                    self.video_path = temp_video_path
                except Exception as alt_error:
                    raise RuntimeError(f"Could not load video file using any method: {str(initial_error)}\nAlternative method error: {str(alt_error)}")


            # Process the silent parts to get a list of segments
            sorted_parts = sorted(self.silent_parts, key=lambda x: x['start'])
            segments = []
            last_end = 0

            self.progress_updated.emit(20)
            QApplication.processEvents()

            for part in sorted_parts:
                pass
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
                pass
                try:
                    final_segment = video.subclip(last_end, video.duration)
                    segments.append(final_segment)
                except Exception as e:
                    print(f"Error creating final segment {last_end} to {video.duration}: {str(e)}")

            self.progress_updated.emit(30)
            QApplication.processEvents()

            # If no segments were cut, just use the original video
            if not segments:
                result = video
            else:
                pass
                try:
                    # Concatenate all segments
                    print(f"Concatenating {len(segments)} video segments")
                    result = mp.concatenate_videoclips(segments)
                except Exception as e:
                    print(f"Error concatenating clips: {str(e)}")
                    # Fallback to using the original video
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
                    timer.stop()
                    return

                if current_time - self.last_update_time >= 1.0:  # Update every second
                    self.last_update_time = current_time

                    # Estimate progress based on elapsed time and video duration
                    if hasattr(self, '_video_duration') and self._video_duration > 0:
                        # Estimate total processing time (typically 2-3x video duration)
                        estimated_total_time = self._video_duration * 2.5
                        time_based_progress = (elapsed_total / estimated_total_time) * 95
                        time_based_progress = min(95, max(self.last_progress, time_based_progress))

                        # Use smooth progression towards estimated progress
                        if time_based_progress > self.last_progress:
                            self.last_progress = time_based_progress
                        else:
                            # Fallback gentle increment
                            increment = 0.5 if self.last_progress < 70 else 0.3
                            self.last_progress = min(95, self.last_progress + increment)
                    else:
                        # Fallback time-based increments
                        if elapsed_total < 60:
                            increment = 1.0
                        elif elapsed_total < 180:
                            increment = 0.6
                        else:
                            increment = 0.3
                        self.last_progress = min(95, self.last_progress + increment)
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

                # Prepare FFmpeg parameters for hardware acceleration
                # Use resolution-optimized parameters if available
                if RESOLUTION_OPTIMIZER_AVAILABLE and hasattr(self, 'optimization_settings'):
                    ffmpeg_params = self.get_optimized_ffmpeg_params(video_codec)
                else:
                    # Fallback to standard parameters
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
                    # Get file size for reporting (but don't block on it)
                    try:
                        file_size = os.path.getsize(self.output_path)
                    except:
                        pass
                else:
                    raise RuntimeError("Output file was not created by MoviePy")

            except Exception as e:
                timer.stop()
                print(f"Error during video writing: {str(e)}")
                raise e
            finally:
                # Clean up resources
                try:
                    pass
                    if 'video' in locals():
                        video.close()
                    if 'result' in locals() and result != video:
                        result.close()
                except Exception as cleanup_error:
                    print(f"Error during cleanup: {str(cleanup_error)}")

            # Smooth transition to completion
            for progress in [96, 97, 98, 99, 100]:
                self.progress_updated.emit(progress)
                QApplication.processEvents()
                time.sleep(0.02)  # Very brief pause for smooth animation

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
        except:
            pass

        # Fallback to software encoding
        if not hw_options:
            hw_options.append(('libx264', 'Software (CPU)'))

        return hw_options

    def run_fast_ffmpeg_processing(self):
        """Fast video processing using direct FFmpeg with hardware acceleration"""
        try:
            pass

            # Detect available hardware acceleration
            hw_options = self.detect_hardware_acceleration()
            video_codec, hw_name = hw_options[0]  # Use the first (best) available option

            # Get selected silent parts
            selected_parts = [part for part in self.silent_parts if part['selected']]
            if not selected_parts:
                pass
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
                pass
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
            # Use resolution-optimized parameters if available
            if RESOLUTION_OPTIMIZER_AVAILABLE and hasattr(self, 'optimization_settings'):
                optimized_params = self.get_optimized_ffmpeg_params(video_codec)
                # Remove the pixel format since it's already added above
                optimized_params = [p for p in optimized_params if p != '-pix_fmt' and p != 'yuv420p']
                cmd.extend(optimized_params)
            else:
                # Fallback to standard parameters
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

            print(f"Command: {' '.join(cmd[:12])}...")  # Show partial command
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
                        pass
                        break
                    output_lines.append(line.strip())

                    # Parse FFmpeg progress from time= output
                    if "time=" in line:
                        pass
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
                                        progress_percent = min(99, (current_time_seconds / self._video_duration) * 100)
                                        if progress_percent > current_progress:
                                            current_progress = progress_percent
                                            self.progress_updated.emit(int(current_progress))
                                            QApplication.processEvents()
                        except:
                            pass  # Ignore parsing errors

                    # Look for completion indicators
                    if "video:" in line.lower() and "audio:" in line.lower() and "subtitle:" in line.lower():
                        pass
                    elif "error" in line.lower():
                        pass

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

                # Parse FFmpeg output for real progress
                progress_updated = False
                if output_lines:
                    latest_output = output_lines[-1] if output_lines else ""

                    # Look for time information in FFmpeg output
                    if "time=" in latest_output:
                        pass
                        try:
                            time_match = latest_output.split("time=")[1].split()[0]
                            time_parts = time_match.split(":")
                            if len(time_parts) == 3:
                                current_time_seconds = (
                                    float(time_parts[0]) * 3600 +
                                    float(time_parts[1]) * 60 +
                                    float(time_parts[2])
                                )
                                if self._video_duration > 0:
                                    # Calculate real progress (0-95% based on actual processing)
                                    real_progress = (current_time_seconds / self._video_duration) * 95
                                    real_progress = max(current_progress, min(95, real_progress))

                                    if real_progress > current_progress + 0.3:  # Update more frequently
                                        current_progress = real_progress
                                        self.progress_updated.emit(int(current_progress))
                                        QApplication.processEvents()
                                        last_progress_time = current_time
                                        progress_updated = True
                        except:
                            pass

                # More aggressive fallback progress if no FFmpeg time detected
                if not progress_updated and current_time - last_progress_time >= 1.0:  # Update every second
                    # Estimate progress based on elapsed time vs expected total time
                    if self._video_duration > 0:
                        # Assume processing takes roughly 1.5-2x the video duration
                        estimated_total_time = self._video_duration * 1.8
                        time_based_progress = (elapsed / estimated_total_time) * 95
                        time_based_progress = min(95, max(current_progress, time_based_progress))

                        if time_based_progress > current_progress:
                            current_progress = time_based_progress
                            self.progress_updated.emit(int(current_progress))
                            QApplication.processEvents()
                            last_progress_time = current_time
                            progress_updated = True

                    # Final fallback: steady increments
                    if not progress_updated:
                        increment = 1.0 if current_progress < 70 else 0.5
                        new_progress = min(95, current_progress + increment)

                        if new_progress > current_progress:
                            current_progress = new_progress
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
                # Check if output file was actually created
                if os.path.exists(self.output_path):
                    # Smooth transition to completion
                    for progress in [96, 97, 98, 99, 100]:
                        self.progress_updated.emit(progress)
                        QApplication.processEvents()
                        time.sleep(0.02)  # Very brief pause for smooth animation

                    # Get file size for reporting (but don't block on it)
                    try:
                        file_size = os.path.getsize(self.output_path)
                        if file_size <= 1024:  # Less than 1KB is suspicious
                            print(f"Warning: Output file is very small ({file_size} bytes)")
                    except:
                        file_size = 0  # If we can't get size, continue anyway

                    elapsed_total = time.time() - start_time
                    if file_size > 0:
                        pass
                    else:
                        pass
                    return self.output_path
                else:
                    pass
                    return ""
            else:
                pass
                if all_output:
                    print(f"FFmpeg output: {all_output[-500:]}")  # Show last 500 chars
                return ""

        except Exception as e:
            print(f"Hardware-accelerated FFmpeg processing error: {e}")
            return ""

class TimelineWidget(QWidget):
    """Custom timeline widget with draggable silence regions and waveform visualization"""
    selection_changed = pyqtSignal(dict)
    position_changed = pyqtSignal(float)  # Emitted when user seeks on timeline

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)  # Increased by 40px for top/bottom padding
        self.setMaximumHeight(260)  # Increased by 40px for top/bottom padding

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
            pass
            if event.key() == Qt.Key_Z:
                self.undo()
                event.accept()
                return
        elif event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            pass
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
        """Zoom in the timeline keeping playhead centered"""
        old_zoom = self.zoom_level
        self.zoom_level = min(self.max_zoom, self.zoom_level * 1.2)

        # Adjust offset to keep playhead centered during zoom
        if old_zoom != self.zoom_level and self.duration_seconds > 0:
            # Calculate where the playhead should be positioned (center of view)
            playhead_ratio = self.current_position / self.duration_seconds
            new_visible_range = 1.0 / self.zoom_level

            # Position offset so playhead is in center of visible area
            self.zoom_offset = max(0.0, min(1.0 - new_visible_range,
                                          playhead_ratio - new_visible_range / 2))
            self.update()

    def zoom_out(self):
        """Zoom out the timeline keeping playhead centered"""
        # Only allow zooming out if currently above 1.0x scale
        if self.zoom_level > 1.0:
            old_zoom = self.zoom_level
            self.zoom_level = max(1.0, self.zoom_level / 1.2)

            # Adjust offset to keep playhead centered during zoom out
            if old_zoom != self.zoom_level and self.duration_seconds > 0:
                playhead_ratio = self.current_position / self.duration_seconds
                new_visible_range = 1.0 / self.zoom_level

                # Position offset so playhead is in center of visible area
                self.zoom_offset = max(0.0, min(1.0 - new_visible_range,
                                              playhead_ratio - new_visible_range / 2))

        # Ensure offset stays within bounds
        max_offset = max(0.0, 1.0 - (1.0 / self.zoom_level))
        self.zoom_offset = min(max_offset, self.zoom_offset)
        self.update()

    def reset_zoom(self):
        """Reset zoom to normal level"""
        self.zoom_level = 1.0
        self.zoom_offset = 0.0
        self.update()

    def handle_resize(self):
        """Handle timeline widget resize - clear cache and force redraw for proper waveform scaling"""
        if hasattr(self, 'waveform_cache'):
            self.waveform_cache.clear()

        # Force immediate update to redraw waveform with new dimensions
        self.update()

    def resizeEvent(self, event):
        """Handle resize events for the timeline widget"""
        super().resizeEvent(event)

        # Clear waveform cache when timeline widget is resized to ensure proper scaling
        if hasattr(self, 'waveform_cache') and self.waveform_data:
            self.waveform_cache.clear()
            # Small delay to allow layout to settle before redrawing
            QTimer.singleShot(50, self.update)

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
            pass
        else:
            pass
        self.update()  # Trigger repaint

        # NOW hide the loading overlay since waveform loading is complete
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'hide_loading_overlay'):
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
            else:
                self.preview_timeline_duration = self.duration_seconds
        else:
            self.preview_timeline_duration = None

        # Just trigger a repaint to show preview mode visualization
        self.update()

    def get_effective_duration(self):
        """Get the effective timeline duration - ALWAYS return original duration for timeline display"""
        # The timeline should ALWAYS show the complete original duration
        # Preview mode only affects playback behavior, not the visual timeline
        return self.duration_seconds

    def convert_click_position_to_original_time(self, click_time_seconds):
        """Convert a click position on the timeline to original video time"""
        if not self.preview_mode or not hasattr(self, 'preview_timeline_duration'):
            # Normal mode: click time is already in original timeline
            return click_time_seconds

        # Since we're always clicking on the original timeline/waveform,
        # no conversion is needed - the click is already in original time coordinates
        return click_time_seconds

    def original_time_to_preview_time(self, original_time):
        """Convert original video time to preview timeline position"""
        if not self.preview_mode or not self.silent_parts:
            pass
            return original_time

        # Get selected silent parts (ones that will be cut)
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]
        if not selected_silent_parts:
            pass
            return original_time

        # Sort by start time
        selected_silent_parts.sort(key=lambda x: x['start'])

        # Build segments that will be kept
        preview_segments = []
        last_end = 0

        for silent_part in selected_silent_parts:
            pass
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
            pass
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
        # ALWAYS use original timeline coordinates since the timeline always shows the original duration
        original_duration = self.duration_seconds
        visible_duration = original_duration / self.zoom_level
        start_time = self.zoom_offset * original_duration
        end_time = start_time + visible_duration

        # Ensure we don't go beyond the original duration
        start_time = max(0, start_time)
        end_time = min(original_duration, end_time)
        return start_time, end_time

    def time_to_x(self, time_seconds, timeline_rect):
        """Convert time to X coordinate considering zoom and offset"""
        start_time, end_time = self.get_visible_time_range()
        if end_time == start_time:
            pass
            return timeline_rect.left()
        relative_pos = (time_seconds - start_time) / (end_time - start_time)
        return timeline_rect.left() + relative_pos * timeline_rect.width()

    def original_time_to_x(self, time_seconds, timeline_rect):
        """Convert original timeline time to X coordinate (for waveform and silence regions)"""
        start_time, end_time = self.get_original_visible_time_range()
        if end_time == start_time:
            pass
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


        return original_time

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw modern dark background
        painter.fillRect(self.rect(), QColor(31, 41, 55))  # Dark gray background

        if self.duration_seconds <= 0:
            painter.setPen(QPen(QColor(156, 163, 175), 1))  # Light gray text
            painter.setFont(QFont("Segoe UI", 14))
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

        # Draw modern timeline border
        painter.setPen(QPen(QColor(75, 85, 99), 2))  # Subtle border
        painter.drawRoundedRect(timeline_rect, 4, 4)

        # Get visible time range for silence regions (always use original timeline)
        original_start_time, original_end_time = self.get_original_visible_time_range()

        # Draw silence regions
        for i, (start_ms, end_ms) in enumerate(self.silent_ranges):
            pass
            if i >= len(self.silent_parts):
                pass
                continue

            start_sec = start_ms / 1000
            end_sec = end_ms / 1000

            # Skip regions not in visible range (using original timeline)
            if end_sec < original_start_time or start_sec > original_end_time:
                pass
                continue

            # Calculate region position using original timeline coordinates
            start_x = self.original_time_to_x(start_sec, timeline_rect)
            end_x = self.original_time_to_x(end_sec, timeline_rect)
            width = end_x - start_x

            # Choose modern colors based on selection state
            part = self.silent_parts[i]
            segment_type = part.get('type', 'silence')  # Default to silence if no type specified

            if part['selected']:
                pass
                if segment_type in ['repeated_word', 'repeated_phrase']:
                    # Purple/violet color for repeated words - different from red silence
                    color = QColor(147, 51, 234, 180)  # Modern purple with transparency
                    border_color = QColor(126, 34, 206)
                    glow_color = QColor(196, 181, 253, 120)
                else:
                    # Red color for silence segments
                    color = QColor(239, 68, 68, 180)  # Modern red with transparency
                    border_color = QColor(220, 38, 38)
                    glow_color = QColor(248, 113, 113, 120)
            else:
                color = QColor(107, 114, 128, 140)  # Modern gray with transparency
                border_color = QColor(75, 85, 99)
                glow_color = QColor(156, 163, 175, 80)

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

            # Draw modern region label
            if width > 30:  # Only draw label if region is wide enough
                label = f"S{i+1}"
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.drawText(region_rect, Qt.AlignCenter, label)

        # Store playhead info for drawing last (to appear on top)
        playhead_info = None
        if original_start_time <= self.current_position <= original_end_time:
            pos_x = self.original_time_to_x(self.current_position, timeline_rect)
            playhead_info = (pos_x, timeline_rect)

        # Draw modern time markers at top
        painter.setPen(QPen(QColor(156, 163, 175), 1))  # Modern gray
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))

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
            pass
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

        # Draw zoom controls at bottom of timeline with + and - icons
        button_size = 24
        button_spacing = 8
        bottom_margin = 15  # Increased to use more of the bottom padding space

        # Position buttons at bottom right of timeline
        zoom_out_rect = QRectF(
            timeline_rect.right() - (button_size * 2 + button_spacing + 10),
            timeline_rect.bottom() + bottom_margin,
            button_size, button_size
        )
        zoom_in_rect = QRectF(
            timeline_rect.right() - (button_size + 10),
            timeline_rect.bottom() + bottom_margin,
            button_size, button_size
        )

        # Get mouse position for hover detection
        mouse_pos = self.mapFromGlobal(self.cursor().pos())

        # Draw zoom out button (-)
        zoom_out_hover = zoom_out_rect.contains(mouse_pos)
        if zoom_out_hover:
            painter.fillRect(zoom_out_rect, QColor(60, 70, 85, 220))
            painter.setPen(QPen(QColor(120, 130, 140), 2))
        else:
            painter.fillRect(zoom_out_rect, QColor(45, 55, 70, 200))
            painter.setPen(QPen(QColor(100, 110, 120), 1))

        painter.drawRoundedRect(zoom_out_rect, 4, 4)

        # Draw - icon
        painter.setPen(QPen(QColor(200, 210, 220), 2))
        painter.drawLine(
            int(zoom_out_rect.center().x() - 6), int(zoom_out_rect.center().y()),
            int(zoom_out_rect.center().x() + 6), int(zoom_out_rect.center().y())
        )

        # Draw zoom in button (+)
        zoom_in_hover = zoom_in_rect.contains(mouse_pos)
        if zoom_in_hover:
            painter.fillRect(zoom_in_rect, QColor(60, 70, 85, 220))
            painter.setPen(QPen(QColor(120, 130, 140), 2))
        else:
            painter.fillRect(zoom_in_rect, QColor(45, 55, 70, 200))
            painter.setPen(QPen(QColor(100, 110, 120), 1))

        painter.drawRoundedRect(zoom_in_rect, 4, 4)

        # Draw + icon
        painter.setPen(QPen(QColor(200, 210, 220), 2))
        center_x, center_y = int(zoom_in_rect.center().x()), int(zoom_in_rect.center().y())
        painter.drawLine(center_x - 6, center_y, center_x + 6, center_y)  # Horizontal line
        painter.drawLine(center_x, center_y - 6, center_x, center_y + 6)  # Vertical line

        # Store button rects for click detection
        self.zoom_out_button_rect = zoom_out_rect
        self.zoom_in_button_rect = zoom_in_rect

        # Draw reset button only when zoomed
        if self.zoom_level != 1.0:
            reset_rect = QRectF(
                timeline_rect.left() + 10,
                timeline_rect.bottom() + bottom_margin,
                50, button_size
            )

            reset_hover = reset_rect.contains(mouse_pos)
            if reset_hover:
                painter.fillRect(reset_rect, QColor(60, 70, 85, 220))
                painter.setPen(QPen(QColor(120, 130, 140), 2))
            else:
                painter.fillRect(reset_rect, QColor(45, 55, 70, 200))
                painter.setPen(QPen(QColor(100, 110, 120), 1))

            painter.drawRoundedRect(reset_rect, 4, 4)

            # Draw reset text
            painter.setPen(QPen(QColor(200, 210, 220), 1))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.drawText(reset_rect, Qt.AlignCenter, "Reset")

            self.reset_button_rect = reset_rect
        else:
            self.reset_button_rect = None

        # Draw playhead last so it appears on top of everything
        if playhead_info:
            pos_x, timeline_rect = playhead_info

            # Draw modern position line with glow effect
            painter.setPen(QPen(QColor(37, 99, 235, 100), 6))  # Blue glow
            painter.drawLine(int(pos_x), int(timeline_rect.top() - 5), int(pos_x), int(timeline_rect.bottom() + 5))
            painter.setPen(QPen(QColor(37, 99, 235), 3))  # Solid blue line
            painter.drawLine(int(pos_x), int(timeline_rect.top() - 5), int(pos_x), int(timeline_rect.bottom() + 5))

            # Draw modern time indicator above the playhead
            time_str = self.format_time_mmss_ms(self.current_position)
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            text_rect = painter.fontMetrics().boundingRect(time_str)

            # Draw modern time background with rounded corners
            time_bg_rect = QRectF(pos_x - text_rect.width()/2 - 8, timeline_rect.top() - 45,
                                text_rect.width() + 16, text_rect.height() + 8)
            painter.fillRect(time_bg_rect, QColor(31, 41, 55, 255))  # Dark background matching theme
            painter.setPen(QPen(QColor(37, 99, 235), 2))  # Blue border matching position line
            painter.drawRoundedRect(time_bg_rect, 4, 4)

            # Draw subtle inner glow
            inner_rect = QRectF(time_bg_rect.x() + 1, time_bg_rect.y() + 1,
                              time_bg_rect.width() - 2, time_bg_rect.height() - 2)
            painter.setPen(QPen(QColor(55, 65, 81), 1))
            painter.drawRoundedRect(inner_rect, 3, 3)

            # Draw time text with high contrast
            painter.setPen(QPen(QColor(249, 250, 251), 1))  # Light text
            painter.drawText(int(pos_x - text_rect.width()/2), int(timeline_rect.top() - 29), time_str)

            # Draw modern position indicator triangle with gradient
            triangle_points = [
                QPointF(pos_x, timeline_rect.top() - 5),
                QPointF(pos_x - 7, timeline_rect.top() - 20),
                QPointF(pos_x + 7, timeline_rect.top() - 20)
            ]

            gradient = QLinearGradient(0, timeline_rect.top() - 17, 0, timeline_rect.top() - 5)
            gradient.setColorAt(0, QColor(37, 99, 235))  # Modern blue
            gradient.setColorAt(1, QColor(29, 78, 216))  # Darker blue
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(30, 64, 175), 2))  # Dark blue border
            painter.drawPolygon(triangle_points)

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
            pass
            return

        start_sample = int((start_time / total_duration) * len(self.waveform_data))
        end_sample = int((end_time / total_duration) * len(self.waveform_data))
        start_sample = max(0, start_sample)
        end_sample = min(len(self.waveform_data), end_sample)

        if start_sample >= end_sample:
            pass
            return

        # Get visible samples
        visible_samples = self.waveform_data[start_sample:end_sample]
        if not visible_samples:
            pass
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
                pass
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
            pass
            if x >= timeline_rect.width():
                pass
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

    def draw_debug_info(self, painter, timeline_rect):
        """Draw debug information showing click position and playhead position"""
        if not self.show_debug_info:
            pass
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
            pass
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
            pass
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
                    print(f"   Cache Hit Rate: {fb_stats['hit_rate']:.1f}%")
                    print(f"   Hits: {fb_stats['hits']}, Misses: {fb_stats['misses']}")
                    print(f"   Buffer Size: {fb_stats['size']}/{fb_stats['max_size']}")

                # Waveform cache stats
                if 'waveform_cache' in stats:
                    wc_stats = stats['waveform_cache']
                    print(f"   Cached Zoom Levels: {wc_stats['size']}/{wc_stats['max_size']}")

                # Cache status
                cache_status = "✅ ENABLED" if self.cache_enabled else "❌ DISABLED"

                print("=" * 50)
                print("Press 'B' again to refresh stats")

            else:
                pass

        except Exception as e:
            print(f"Error showing buffer stats: {e}")

    def enable_caching(self):
        """Enable waveform caching after initial loading"""
        self.cache_during_loading = True

    def disable_caching(self):
        """Disable waveform caching during heavy operations"""
        self.cache_during_loading = False

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.duration_seconds <= 0:
            pass
            return

        # Check if clicking on reset zoom button
        if hasattr(self, 'reset_button_rect') and self.reset_button_rect and self.reset_button_rect.contains(event.x(), event.y()):
            self.reset_zoom()
            return

        # Check if clicking on zoom in button
        if hasattr(self, 'zoom_in_button_rect') and self.zoom_in_button_rect and self.zoom_in_button_rect.contains(event.x(), event.y()):
            self.zoom_in()
            return

        # Check if clicking on zoom out button
        if hasattr(self, 'zoom_out_button_rect') and self.zoom_out_button_rect and self.zoom_out_button_rect.contains(event.x(), event.y()):
            self.zoom_out()
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
                pass
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

            self.position_changed.emit(seek_time)
            self.seeking = True

    def mouseMoveEvent(self, event):
        if self.duration_seconds <= 0:
            pass
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
                pass
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

        # Check for button hovers
        button_hover = False
        if hasattr(self, 'reset_button_rect') and self.reset_button_rect and self.reset_button_rect.contains(click_x, click_y):
            self.setCursor(Qt.PointingHandCursor)
            button_hover = True
        elif hasattr(self, 'zoom_in_button_rect') and self.zoom_in_button_rect and self.zoom_in_button_rect.contains(click_x, click_y):
            self.setCursor(Qt.PointingHandCursor)
            button_hover = True
        elif hasattr(self, 'zoom_out_button_rect') and self.zoom_out_button_rect and self.zoom_out_button_rect.contains(click_x, click_y):
            self.setCursor(Qt.PointingHandCursor)
            button_hover = True

        if self.hover_region is None and not button_hover:
            pass
            if timeline_rect.contains(click_x, click_y):
                self.setCursor(Qt.ArrowCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

        if old_hover != self.hover_region or button_hover:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pass
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
        layout.setSpacing(0)  # No spacing - video fills container

        # Video player widget with modern styling - fills available height
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Expand in both directions
        self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)  # Maintain aspect ratio
        self.video_widget.setStyleSheet("""
            QVideoWidget {
                background-color: #000000;
                border-radius: 8px;
                border: 1px solid #374151;
            }
        """)
        layout.addWidget(self.video_widget, 1)  # Stretch to fill available space

        self.setLayout(layout)

        # Create separate timeline section that will be added to splitter
        self.timeline_section = QFrame()
        self.timeline_section.setStyleSheet("""
            QFrame {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 12px;
            }
        """)

        timeline_layout = QVBoxLayout(self.timeline_section)
        timeline_layout.setSpacing(16)
        timeline_layout.setContentsMargins(24, 16, 24, 16)

        # Custom timeline widget (create first so zoom buttons can connect to it)
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.selection_changed.connect(self.on_timeline_selection_changed)
        self.timeline_widget.position_changed.connect(self.seek_to_position)
        self.timeline_widget.setMinimumHeight(160)  # Increased by 40px for padding

        # Timeline widget directly without header buttons
        timeline_layout.addWidget(self.timeline_widget)

        # Timeline controls
        timeline_controls = QHBoxLayout()
        timeline_controls.setSpacing(16)

        # Playback controls
        playback_controls = QHBoxLayout()
        playback_controls.setSpacing(8)

        self.play_pause_btn = QPushButton("▶️")
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 8px;
                font-size: 16px;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)

        self.stop_btn = QPushButton("⏹️")
        self.stop_btn.clicked.connect(self.stop_video)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #d1d5db;
                border: 1px solid #4b5563;
                border-radius: 20px;
                padding: 8px;
                font-size: 16px;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: #4b5563;
                border-color: #6b7280;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)

        # Volume control - properly contained in a box
        volume_frame = QFrame()
        volume_frame.setStyleSheet("""
            QFrame {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)

        volume_layout = QHBoxLayout(volume_frame)
        volume_layout.setSpacing(8)
        volume_layout.setContentsMargins(8, 4, 8, 4)

        volume_label = QLabel("Volume:")
        volume_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #d1d5db;
                font-weight: 500;
                background: transparent;
                border: none;
            }
        """)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(120)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setStyleSheet("""
            QSlider {
                background: transparent;
                border: none;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #1f2937;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #2563eb;
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #1d4ed8;
            }
            QSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 2px;
            }
        """)

        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)

        playback_controls.addWidget(self.play_pause_btn)
        playback_controls.addWidget(self.stop_btn)
        playback_controls.addWidget(volume_frame)

        # Selection controls
        selection_controls = QHBoxLayout()
        selection_controls.setSpacing(8)

        self.select_all_btn = QPushButton("☑️ Select All Silent Regions")
        self.select_all_btn.clicked.connect(self.toggle_all_silent_regions)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #d1d5db;
                border: 1px solid #4b5563;
                padding: 6px 12px;
                border-radius: 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4b5563;
                border-color: #6b7280;
            }
        """)

        selection_controls.addWidget(self.select_all_btn)

        timeline_controls.addLayout(playback_controls)
        timeline_controls.addStretch()
        timeline_controls.addLayout(selection_controls)

        timeline_layout.addLayout(timeline_controls)

        # Position slider (hidden - timeline provides this functionality)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setEnabled(False)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.position_slider.sliderMoved.connect(self.on_slider_moved)
        self.position_slider.hide()

        # Time labels (hidden - timeline shows time)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.hide()

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
        """Load a video or audio file into the player"""
        # Clean up previous resources
        self.cleanup_fallback_resources()

        self.video_path = video_path

        # Check if this is an audio-only file
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
        file_ext = os.path.splitext(video_path)[1].lower()
        is_audio_only = file_ext in audio_extensions

        if is_audio_only:
            print(f"Loading audio file into player: {video_path}")
            self.load_audio_only(video_path)
            return
        else:
            pass

        # Update loading progress
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'update_loading_progress_with_step'):
            parent.update_loading_progress_with_step("Setting up video player...", 2)

        if os.path.exists(video_path):
            # Convert path to proper format for QMediaPlayer
            abs_path = os.path.abspath(video_path)

            # Update loading progress
            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Loading timeline waveform...", 3)

            # Load waveform data for timeline visualization
            self.timeline_widget.load_waveform(video_path)

            # Create QUrl from local file
            url = QUrl.fromLocalFile(abs_path)

            # Set media content
            media_content = QMediaContent(url)
            self.media_player.setMedia(media_content)


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

    def load_audio_only(self, audio_path):
        """Load an audio-only file and hide video display"""
        print(f"Setting up audio-only mode for: {audio_path}")

        # Set the audio-only flag
        self.is_audio_only = True
        self.video_path = audio_path

        # Update loading progress
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, 'update_loading_progress_with_step'):
            parent.update_loading_progress_with_step("Setting up audio player...", 2)

        # Hide video display area and show audio message
        if hasattr(self, 'video_widget'):
            self.video_widget.hide()

        # Show audio-only message in video area
        self.show_video_message("🎵 Audio File Loaded\n\nThis is an audio-only file.\nUse the timeline below to navigate and preview audio.\n\n• Waveform visualization available\n• All silence detection features work normally")

        # Load waveform data for timeline visualization
        if parent and hasattr(parent, 'update_loading_progress_with_step'):
            parent.update_loading_progress_with_step("Loading audio waveform...", 3)

        # Get audio duration first for proper timeline setup
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            duration_seconds = len(audio) / 1000.0

            # Set timeline duration immediately
            self.timeline_widget.set_duration(duration_seconds)

            # Set position slider range
            duration_ms = int(duration_seconds * 1000)
            self.position_slider.setRange(0, duration_ms)

        except Exception as e:
            print(f"Error getting audio duration: {e}")

        self.timeline_widget.load_waveform(audio_path)

        # Set up basic audio playback using QMediaPlayer
        if os.path.exists(audio_path):
            abs_path = os.path.abspath(audio_path)
            url = QUrl.fromLocalFile(abs_path)
            media_content = QMediaContent(url)
            self.media_player.setMedia(media_content)

            # Enable basic controls
            self.play_pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.position_slider.setEnabled(True)

            # Try to get duration
            self.media_player.setPosition(1000)
            self.media_player.setPosition(0)

            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Audio ready!", 4)

            # Check if media loaded successfully
            QTimer.singleShot(1000, self.check_media_loaded)
        else:
            print(f"Audio file does not exist: {audio_path}")
            QMessageBox.critical(self, "Error", f"Audio file not found: {audio_path}")

    def check_media_loaded(self):
        """Check if media loaded successfully, if not, show a fallback message"""
        status = self.media_player.mediaStatus()

        # Find parent to hide loading overlay
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()

        if status == QMediaPlayer.InvalidMedia or status == QMediaPlayer.NoMedia:
            if parent and hasattr(parent, 'update_loading_progress_with_step'):
                parent.update_loading_progress_with_step("Setting up enhanced video player...", 5)
            self.setup_fallback_video_display()
        elif status == QMediaPlayer.LoadedMedia:
            print("QMediaPlayer loaded successfully")

            # For audio files, set up duration properly
            if hasattr(self, 'is_audio_only') and self.is_audio_only:
                # Get duration from QMediaPlayer
                duration_ms = self.media_player.duration()
                if duration_ms > 0:
                    duration_seconds = duration_ms / 1000.0
                    self.timeline_widget.set_duration(duration_seconds)
                    self.position_slider.setRange(0, duration_ms)

                    # Store duration for the main app
                    parent = self.parent()
                    while parent and not isinstance(parent, QMainWindow):
                        parent = parent.parent()
                    if parent:
                        parent.actual_duration_seconds = duration_seconds
                        parent.video_duration_ms = duration_ms  # For time label display

                    print(f"Audio duration from QMediaPlayer: {duration_seconds:.2f}s")

                if parent and hasattr(parent, 'update_loading_progress_with_step'):
                    parent.update_loading_progress_with_step("Audio ready!", 4)
            else:
                pass
                if parent and hasattr(parent, 'update_loading_progress_with_step'):
                    parent.update_loading_progress_with_step("Finalizing setup...", 6)

            # DON'T hide loading overlay here - let waveform loading complete first
            # The overlay will be hidden when waveform loading is done

    def setup_fallback_video_display(self):
        """Set up a multi-threaded fallback video display when QMediaPlayer fails"""
        try:
            # Check if this is an audio-only file
            if hasattr(self, 'is_audio_only') and self.is_audio_only:
                print("Setting up audio-only playback...")

                # For audio files, get duration using pydub
                from pydub import AudioSegment
                audio = AudioSegment.from_file(self.video_path)
                actual_audio_duration = len(audio) / 1000.0

                # Set up basic audio playback without video thread
                duration_ms = int(actual_audio_duration * 1000)
                self.video_duration_ms = duration_ms
                self.actual_duration_seconds = actual_audio_duration
                self.using_fallback = False  # Audio doesn't need fallback

                # Set timeline duration
                self.timeline_widget.set_duration(actual_audio_duration)
                self.position_slider.setRange(0, duration_ms)

                # Update loading progress
                parent = self.parent()
                while parent and not isinstance(parent, QMainWindow):
                    parent = parent.parent()
                if parent and hasattr(parent, 'update_loading_progress_with_step'):
                    parent.update_loading_progress_with_step("Audio ready!", 4)

                return


            # First get the actual audio duration for accurate timeline sync
            import moviepy.editor as mp
            video_clip = mp.VideoFileClip(self.video_path)
            actual_audio_duration = video_clip.duration if video_clip.audio else 0
            video_clip.close()

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

            print(f"  Video clip duration: {actual_audio_duration:.6f}s")
            print(f"  Thread audio duration: {thread_audio_duration:.6f}s")
            print(f"  Thread video duration: {thread_video_duration:.6f}s")

            # Use the thread's verified audio duration for perfect timeline sync
            if hasattr(self.video_thread, 'verified_audio_duration'):
                duration_seconds = self.video_thread.verified_audio_duration
            else:
                duration_seconds = actual_audio_duration

            # Get video properties using OpenCV for UI setup
            cap = cv2.VideoCapture(self.video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                duration_ms = int(duration_seconds * 1000)

                # Store properties
                self.video_fps = fps
                self.video_frame_count = frame_count
                self.video_duration_ms = duration_ms
                self.actual_duration_seconds = duration_seconds  # Store actual duration
                self.using_fallback = True

                # CRITICAL: Ensure timeline uses the EXACT same duration as the audio thread
                self.timeline_widget.set_duration(duration_seconds)
                self.position_slider.setRange(0, duration_ms)

                # Cross-verify timeline duration matches audio thread duration
                timeline_duration = getattr(self.timeline_widget, 'duration_seconds', 0)
                duration_diff = abs(timeline_duration - duration_seconds)

                if duration_diff > 0.001:  # Warn if difference > 1ms
                    print(f"⚠️  WARNING: Timeline-audio duration mismatch: {duration_diff:.6f}s")
                else:
                    pass

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
        """Display frame from the video thread with proper scaling to fit container"""
        if hasattr(self, 'video_frame_label') and pixmap:
            # DEBUG: Track threaded frame display
            if not hasattr(self, '_debug_threaded_frame_count'):
                self._debug_threaded_frame_count = 0
                self._debug_threaded_last_label_size = None

            self._debug_threaded_frame_count += 1

            label_size = self.video_frame_label.size()

            # DEBUG: Monitor threaded frame display size changes
            if (self._debug_threaded_frame_count % 30 == 0 or
                self._debug_threaded_last_label_size != label_size):


                container_widget = self.video_frame_label.parent()
                if container_widget:
                    pass


                # Check if label size increased
                if (self._debug_threaded_last_label_size and label_size and
                    (label_size.height() > self._debug_threaded_last_label_size.height() or
                     label_size.width() > self._debug_threaded_last_label_size.width())):
                    print(f"  📈 From: {self._debug_threaded_last_label_size}")
                    print(f"  📈 To: {label_size}")

                self._debug_threaded_last_label_size = label_size
                print()

            # Scale pixmap to fit the container while maintaining aspect ratio
            if label_size.width() > 0 and label_size.height() > 0:
                # Scale to fit within the container (not exceed it)
                scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # DEBUG: Log scaling details
                if self._debug_threaded_frame_count % 30 == 0:
                    print()

                self.video_frame_label.setPixmap(scaled_pixmap)
            else:
                # Fallback if container size not available yet
                self.video_frame_label.setPixmap(pixmap)

    def update_threaded_position(self, frame_number):
        """Update UI based on current frame from video thread"""
        if not hasattr(self, 'video_fps') or self.video_fps <= 0:
            pass
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
            pass
            return

        # DEBUG: Log playback state changes and container size
        if hasattr(self, 'video_frame_label'):
            container_widget = self.video_frame_label.parent()
            if container_widget:
                pass

        if hasattr(self, 'is_threaded_playing') and self.is_threaded_playing:
            print(f"  ⏸️  Pausing playback...")
            self.video_thread.pause()
            self.is_threaded_playing = False
            self.play_pause_btn.setText("Play")
        else:
            self.video_thread.play()
            self.is_threaded_playing = True
            self.play_pause_btn.setText("Pause")

        # DEBUG: Log container size after playback change
        if hasattr(self, 'video_frame_label'):
            container_widget = self.video_frame_label.parent()
            if container_widget:
                pass
            print()

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
        """Set up the video display label that replaces the video widget in the layout"""
        if not hasattr(self, 'video_frame_label'):
            # Create the video frame label and add it to the layout instead of overlaying
            self.video_frame_label = QLabel()
            self.video_frame_label.setAlignment(Qt.AlignCenter)
            self.video_frame_label.setStyleSheet("""
                QLabel {
                    background-color: #000000;
                    border-radius: 8px;
                    border: 1px solid #374151;
                }
            """)
            self.video_frame_label.setScaledContents(False)  # Don't force scaling - we'll handle it manually

            # CRITICAL FIX: Use Fixed size policy to prevent auto-resizing during frame display
            # This prevents the cascading resize issue where each frame causes the container to grow
            self.video_frame_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            # Get the current container size to set as the fixed size
            container_size = self.size()
            if container_size.width() > 0 and container_size.height() > 0:
                # Set the label to exactly match the container size
                self.video_frame_label.setFixedSize(container_size)
            else:
                # Fallback to a reasonable default size
                default_size = QSize(800, 450)  # 16:9 aspect ratio
                self.video_frame_label.setFixedSize(default_size)

            # Replace the video widget in the layout with the video frame label
            layout = self.layout()
            if layout:
                # Hide the video widget and add the frame label to the layout
                self.video_widget.hide()
                layout.addWidget(self.video_frame_label, 1)  # Stretch to fill available space

            # DEBUG: Log initial setup
            print(f"  🏷️  Initial label size: {self.video_frame_label.size()}")
            print(f"  🏷️  Initial label geometry: {self.video_frame_label.geometry()}")
            if self.video_frame_label.parent():
                print(f"  📦 Parent size: {self.video_frame_label.parent().size()}")
                print(f"  📐 Parent geometry: {self.video_frame_label.parent().geometry()}")
            print()


    def display_cv2_frame(self, frame):
        """Convert OpenCV frame to QPixmap and display it with proper aspect ratio and quality"""
        try:
            pass
            if not hasattr(self, 'video_frame_label'):
                self.setup_video_display_label()

            # DEBUG: Track video container size changes
            if not hasattr(self, '_debug_frame_count'):
                self._debug_frame_count = 0
                self._debug_last_container_size = None
                self._debug_last_label_size = None

            self._debug_frame_count += 1

            # Get video label size for scaling
            label_size = self.video_frame_label.size()
            if label_size.width() <= 0 or label_size.height() <= 0:
                pass
                return

            # DEBUG: Monitor container and label size changes
            container_widget = self.video_frame_label.parent()
            container_size = container_widget.size() if container_widget else None

            # Log size changes every 30 frames or when size changes
            if (self._debug_frame_count % 30 == 0 or
                self._debug_last_container_size != container_size or
                self._debug_last_label_size != label_size):

                print(f"  📏 Frame dimensions: {frame.shape[:2]}")

                if container_widget:
                    pass


                # Check if size increased
                if (self._debug_last_container_size and container_size and
                    (container_size.height() > self._debug_last_container_size.height() or
                     container_size.width() > self._debug_last_container_size.width())):
                    print(f"  📈 From: {self._debug_last_container_size}")
                    print(f"  📈 To: {container_size}")

                if (self._debug_last_label_size and label_size and
                    (label_size.height() > self._debug_last_label_size.height() or
                     label_size.width() > self._debug_last_label_size.width())):
                    print(f"  📈 From: {self._debug_last_label_size}")
                    print(f"  📈 To: {label_size}")

                self._debug_last_container_size = container_size
                self._debug_last_label_size = label_size
                print()

            # Convert BGR to RGB (OpenCV uses BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            original_height, original_width, channels = rgb_frame.shape
            bytes_per_line = channels * original_width

            # Create QImage from original frame
            qt_image = QImage(rgb_frame.data, original_width, original_height, bytes_per_line, QImage.Format_RGB888)
            if qt_image.isNull():
                pass
                return

            # Create pixmap from QImage
            pixmap = QPixmap.fromImage(qt_image)
            if pixmap.isNull():
                pass
                return

            # Scale pixmap to fit within the label while maintaining aspect ratio
            # This prevents the video from expanding beyond its container
            scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # DEBUG: Log pixmap scaling details
            if self._debug_frame_count % 30 == 0:
                print()

            # Set the scaled pixmap - this will maintain stable dimensions
            self.video_frame_label.setPixmap(scaled_pixmap)

        except Exception as e:
            print(f"Error displaying frame: {e}")

    def seek_to_fallback_frame(self, frame_number):
        """Seek to a specific frame number with maximum performance optimization"""
        try:
            pass
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
            pass
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
            pass
            return

        if self.is_playing:
            self.pause_fallback_playback()
        else:
            self.play_fallback_playback()

    def play_fallback_playback(self):
        """Start playing the video using fallback system with maximum speed"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            pass
            return

        self.is_playing = True
        self.play_pause_btn.setText("Pause")

        # Use the aggressive interval directly - no complex timing
        self.playback_timer.start(self.frame_interval)

    def pause_fallback_playback(self):
        """Pause the video playback"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            pass
            return

        self.is_playing = False
        self.play_pause_btn.setText("Play")
        self.playback_timer.stop()

    def stop_fallback_playback(self):
        """Stop the video playback and return to start"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            pass
            return

        self.is_playing = False
        self.play_pause_btn.setText("Play")
        self.playback_timer.stop()
        self.current_frame = 0
        self.seek_to_fallback_frame(0)

    def seek_to_fallback_position(self, position_seconds):
        """Seek to a specific position in seconds for fallback playback"""
        if not hasattr(self, 'using_fallback') or not self.using_fallback:
            pass
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
        """Show a message overlay on the video display area"""
        if not hasattr(self, 'video_message_label'):
            # Parent to the main widget instead of video_widget
            self.video_message_label = QLabel(self)
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

        # Center the label in the video display area
        if hasattr(self, 'video_frame_label') and self.video_frame_label.isVisible():
            widget_size = self.video_frame_label.size()
        else:
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
        # DEBUG: Log video player widget resize events

        # DEBUG: Log video frame label size before resize
        if hasattr(self, 'video_frame_label'):
            pass

        super().resizeEvent(event)

        # CRITICAL FIX: Update video frame label size when container is resized
        # This allows proper resizing when window changes, but prevents auto-growth during playback
        if hasattr(self, 'video_frame_label') and event.size().isValid():
            new_size = event.size()
            if new_size.width() > 0 and new_size.height() > 0:
                # Only resize if the new size is significantly different (avoid micro-adjustments)
                current_size = self.video_frame_label.size()
                size_diff = abs(new_size.width() - current_size.width()) + abs(new_size.height() - current_size.height())

                if size_diff > 5:  # Only resize if difference is more than 5 pixels total
                    self.video_frame_label.setFixedSize(new_size)

                    # If there's a current frame, rescale it to fit the new container size
                    if hasattr(self.video_frame_label, 'pixmap') and self.video_frame_label.pixmap():
                        current_pixmap = self.video_frame_label.pixmap()
                        if current_pixmap and not current_pixmap.isNull():
                            # Scale pixmap to fit new container size while maintaining aspect ratio
                            scaled_pixmap = current_pixmap.scaled(new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.video_frame_label.setPixmap(scaled_pixmap)
                else:
                    print(f"  ⏭️  Skipping micro-resize (diff: {size_diff}px)")

        # DEBUG: Log video frame label size after resize
        if hasattr(self, 'video_frame_label'):
            pass
        print()

        # Reposition message label if it exists and is visible
        if hasattr(self, 'video_message_label') and self.video_message_label.isVisible():
            # Position message label relative to the video frame label (or widget if no label)
            if hasattr(self, 'video_frame_label') and self.video_frame_label.isVisible():
                widget_size = self.video_frame_label.size()
            else:
                widget_size = self.video_widget.size()
            label_size = self.video_message_label.size()
            x = max(0, (widget_size.width() - label_size.width()) // 2)
            y = max(0, (widget_size.height() - label_size.height()) // 2)
            self.video_message_label.move(x, y)

        # In fullscreen mode, ensure video frame label fills the screen
        if hasattr(self.parent(), 'is_fullscreen') and self.parent().is_fullscreen:
            pass
            if hasattr(self, 'video_frame_label') and self.video_frame_label:
                print(f"  🖥️  Setting fullscreen geometry: {event.size()}")
                self.video_frame_label.setFixedSize(event.size())

    def cleanup_fallback_resources(self):
        """Clean up video resources"""
        try:
            pass
            if hasattr(self, 'video_thread') and self.video_thread is not None:
                self.video_thread.stop_playback()
                self.video_thread.wait(1000)  # Wait up to 1 second for thread to finish
                self.video_thread = None
        except (RuntimeError, AttributeError):
            pass  # Thread already cleaned up

        try:
            pass
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
            self.timeline_widget.set_duration(self.actual_duration_seconds)
        elif hasattr(self, 'video_duration_ms') and self.video_duration_ms > 0:
            duration_seconds = self.video_duration_ms / 1000
            self.timeline_widget.set_duration(duration_seconds)

        # Update timeline
        self.timeline_widget.set_silent_parts(self.silent_parts, self.silent_ranges)

    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if hasattr(self, 'using_fallback') and self.using_fallback and hasattr(self, 'video_thread'):
            self.toggle_threaded_playback()
        else:
            pass
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
        # Handle audio preview mode
        if hasattr(self, 'is_audio_only') and self.is_audio_only and hasattr(self, 'audio_preview_active') and self.audio_preview_active:
            self.handle_audio_preview_position(position)
            return

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

        # Handle audio preview mode seeking
        if hasattr(self, 'is_audio_only') and self.is_audio_only and hasattr(self, 'audio_preview_active') and self.audio_preview_active:
            preview_time_ms = self.position_slider.value()
            preview_time_s = preview_time_ms / 1000.0
            original_time_s = self.convert_preview_to_original_time(preview_time_s)
            original_time_ms = int(original_time_s * 1000)
            self.media_player.setPosition(original_time_ms)
        else:
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


    def format_time_simple(self, seconds):
        """Format time in MM:SS format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def on_timeline_selection_changed(self, changed_part):
        """Handle selection changes from timeline"""
        # Update preview mode in real-time when selections change
        if self.preview_mode:
            pass
            if hasattr(self, 'video_thread') and self.video_thread:
                # Video file preview mode
                self.video_thread.set_preview_mode(True, self.silent_parts)
                self.preview_duration = self.video_thread.preview_duration
            elif hasattr(self, 'is_audio_only') and self.is_audio_only:
                # Audio file preview mode
                self.setup_audio_preview_mode()

            # DON'T update timeline preview mode - timeline should always show original duration
            # Only update the video thread for playback behavior

            # Update position slider range for new preview duration
            if hasattr(self, 'preview_duration') and self.preview_duration > 0:
                self.position_slider.setRange(0, int(self.preview_duration * 1000))

            # Update time label to reflect new duration
            self.update_time_label_display()


        self.selection_changed.emit(changed_part)

    def toggle_all_silent_regions(self):
        """Toggle all silent regions - if any are selected, deselect all; if none are selected, select all"""
        if not self.silent_parts:
            pass
            return

        # Check if any regions are currently selected
        any_selected = any(part['selected'] for part in self.silent_parts)

        if any_selected:
            # Deselect all
            for part in self.silent_parts:
                part['selected'] = False
            self.select_all_btn.setText("☑️ Select All Silent Regions")
        else:
            # Select all
            for part in self.silent_parts:
                part['selected'] = True
            self.select_all_btn.setText("☐ Deselect All Silent Regions")

        self.timeline_widget.update()

        # Update preview mode in real-time
        if self.preview_mode:
            pass
            if hasattr(self, 'video_thread') and self.video_thread:
                # Video file preview mode
                self.video_thread.set_preview_mode(True, self.silent_parts)
                self.preview_duration = self.video_thread.preview_duration
            elif hasattr(self, 'is_audio_only') and self.is_audio_only:
                # Audio file preview mode
                self.setup_audio_preview_mode()

            # DON'T update timeline preview mode - timeline should always show original duration
            if hasattr(self, 'preview_duration') and self.preview_duration > 0:
                self.position_slider.setRange(0, int(self.preview_duration * 1000))
            self.update_time_label_display()

        self.selection_changed.emit({})

    def select_all_silent_regions(self):
        """Select all silent regions (legacy method for compatibility)"""
        for part in self.silent_parts:
            part['selected'] = True
        self.timeline_widget.update()

        # Update preview mode in real-time
        if self.preview_mode and hasattr(self, 'video_thread') and self.video_thread:
            self.video_thread.set_preview_mode(True, self.silent_parts)
            self.preview_duration = self.video_thread.preview_duration
            # DON'T update timeline preview mode - timeline should always show original duration
            if self.preview_duration > 0:
                self.position_slider.setRange(0, int(self.preview_duration * 1000))
            self.update_time_label_display()

        self.selection_changed.emit({})

    def deselect_all_silent_regions(self):
        """Deselect all silent regions (legacy method for compatibility)"""
        for part in self.silent_parts:
            part['selected'] = False
        self.timeline_widget.update()

        # Update preview mode in real-time
        if self.preview_mode and hasattr(self, 'video_thread') and self.video_thread:
            self.video_thread.set_preview_mode(True, self.silent_parts)
            self.preview_duration = self.video_thread.preview_duration
            # DON'T update timeline preview mode - timeline should always show original duration
            if self.preview_duration > 0:
                self.position_slider.setRange(0, int(self.preview_duration * 1000))
            self.update_time_label_display()

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

    def set_preview_mode(self, enabled, silent_parts=None):
        """Set preview mode with optional silent parts (supports manual cuts)"""
        if enabled and silent_parts:
            self.silent_parts = silent_parts
            self.enable_preview_mode()
        elif enabled and not silent_parts:
            # Enable with existing silent parts
            self.enable_preview_mode()
        else:
            # Disable preview mode
            self.preview_mode = False
            if hasattr(self, 'video_thread') and self.video_thread:
                self.video_thread.set_preview_mode(False)

    def enable_preview_mode(self):
        """Enable preview mode automatically after silence detection"""
        if not self.silent_parts:
            pass
            return

        # Enable preview mode
        self.preview_mode = True

        if hasattr(self, 'video_thread') and self.video_thread:
            # Video file preview mode
            self.video_thread.set_preview_mode(True, self.silent_parts)
            # Connect preview position signal
            self.video_thread.preview_position_changed.connect(self.update_preview_position)
            self.preview_duration = self.video_thread.preview_duration
        elif hasattr(self, 'is_audio_only') and self.is_audio_only:
            # Audio file preview mode
            self.setup_audio_preview_mode()

        # DON'T set timeline to preview mode - timeline should always show original duration
        # Only the video playback behavior should be affected by preview mode

        # Update position slider range for preview duration
        if hasattr(self, 'preview_duration') and self.preview_duration > 0:
            self.position_slider.setRange(0, int(self.preview_duration * 1000))


        # Update time label immediately
        self.update_time_label_display()

    def setup_audio_preview_mode(self):
        """Set up preview mode for audio files using QMediaPlayer"""
        if not self.silent_parts:
            pass
            return

        # Calculate preview segments (non-silent parts)
        self.audio_preview_segments = []
        selected_silent_parts = [part for part in self.silent_parts if part['selected']]

        if not selected_silent_parts:
            # No silent parts selected, preview is same as original
            self.preview_duration = getattr(self, 'actual_duration_seconds', 0)
            return

        # Sort silent parts by start time
        selected_silent_parts.sort(key=lambda x: x['start'])

        # Create segments between silent parts
        current_time = 0.0
        preview_time = 0.0

        for silent_part in selected_silent_parts:
            # Add segment before this silent part
            if current_time < silent_part['start']:
                segment_duration = silent_part['start'] - current_time
                self.audio_preview_segments.append({
                    'original_start': current_time,
                    'original_end': silent_part['start'],
                    'preview_start': preview_time,
                    'preview_end': preview_time + segment_duration,
                    'duration': segment_duration
                })
                preview_time += segment_duration

            # Skip the silent part
            current_time = silent_part['end']

        # Add final segment after last silent part
        total_duration = getattr(self, 'actual_duration_seconds', 0)
        if current_time < total_duration:
            segment_duration = total_duration - current_time
            self.audio_preview_segments.append({
                'original_start': current_time,
                'original_end': total_duration,
                'preview_start': preview_time,
                'preview_end': preview_time + segment_duration,
                'duration': segment_duration
            })
            preview_time += segment_duration

        self.preview_duration = preview_time

        # Set up audio preview tracking
        self.audio_preview_active = True
        self.current_preview_segment = None
        self.preview_start_time = None


    def convert_preview_to_original_time(self, preview_time):
        """Convert preview time to original time for audio files"""
        if not hasattr(self, 'audio_preview_segments') or not self.audio_preview_segments:
            pass
            return preview_time

        # Find which segment this preview time belongs to
        for segment in self.audio_preview_segments:
            pass
            if segment['preview_start'] <= preview_time <= segment['preview_end']:
                # Calculate offset within the segment
                offset = preview_time - segment['preview_start']
                return segment['original_start'] + offset

        # If not found in any segment, return the closest boundary
        if preview_time < self.audio_preview_segments[0]['preview_start']:
            pass
            return self.audio_preview_segments[0]['original_start']
        else:
            pass
            return self.audio_preview_segments[-1]['original_end']

    def convert_original_to_preview_time(self, original_time):
        """Convert original time to preview time for audio files"""
        if not hasattr(self, 'audio_preview_segments') or not self.audio_preview_segments:
            pass
            return original_time

        # Find which segment this original time belongs to
        for segment in self.audio_preview_segments:
            pass
            if segment['original_start'] <= original_time <= segment['original_end']:
                # Calculate offset within the segment
                offset = original_time - segment['original_start']
                return segment['preview_start'] + offset

        # If in a silent part, find the nearest segment boundary
        preview_time = 0.0
        for segment in self.audio_preview_segments:
            pass
            if original_time < segment['original_start']:
                pass
                return preview_time
            elif original_time <= segment['original_end']:
                offset = original_time - segment['original_start']
                return segment['preview_start'] + offset
            preview_time = segment['preview_end']

        return preview_time

    def handle_audio_preview_position(self, position_ms):
        """Handle position updates during audio preview mode"""
        original_time_s = position_ms / 1000.0

        # Check if we're in a silent part that should be skipped
        if hasattr(self, 'audio_preview_segments') and self.audio_preview_segments:
            # Find if current position is in a non-silent segment
            current_segment = None
            for segment in self.audio_preview_segments:
                pass
                if segment['original_start'] <= original_time_s <= segment['original_end']:
                    current_segment = segment
                    break

            if current_segment:
                # We're in a valid segment, update preview position
                offset = original_time_s - current_segment['original_start']
                preview_time_s = current_segment['preview_start'] + offset
                preview_time_ms = int(preview_time_s * 1000)

                if not self.slider_pressed:
                    self.position_slider.setValue(preview_time_ms)

                # Update time label with preview time
                current_time = self.format_time_simple(preview_time_s)
                total_time = self.format_time_simple(self.preview_duration)
                self.time_label.setText(f"{current_time} / {total_time}")

                # Update timeline position (convert to original time for timeline)
                self.timeline_widget.set_position(original_time_s, instant=False)

            else:
                # We're in a silent part, skip to next non-silent segment
                next_segment = None
                for segment in self.audio_preview_segments:
                    pass
                    if segment['original_start'] > original_time_s:
                        next_segment = segment
                        break

                if next_segment:
                    # Jump to the start of the next segment
                    next_position_ms = int(next_segment['original_start'] * 1000)
                    self.media_player.setPosition(next_position_ms)
                else:
                    # No more segments, stop playback
                    self.media_player.pause()

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
        self.is_audio_only = False
        self.silent_parts = []
        self.silent_ranges = []

        # Create loading overlay
        self.loading_overlay = None

        # Initialize manual cutting feature
        if MANUAL_CUTTING_AVAILABLE:
            self.manual_cutting_manager = ManualCuttingManager(self)
        else:
            self.manual_cutting_manager = None

        self.setup_ui()

        # Initialize transcript integration
        global TRANSCRIPT_INTEGRATION_AVAILABLE
        if TRANSCRIPT_INTEGRATION_AVAILABLE:
            pass
            try:
                integrate_transcript_with_app(self)
            except Exception as e:
                print(f"⚠️  Transcript integration failed: {e}")
                TRANSCRIPT_INTEGRATION_AVAILABLE = False

    def setup_ui(self):
        self.setWindowTitle("Media Silence Cutter")
        self.setWindowIcon(QIcon("zaplogo.png"))
        self.setMinimumWidth(1200)
        self.setMinimumHeight(800)

        # Set modern dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #111827;
                color: #f9fafb;
            }
            QWidget {
                background-color: #111827;
                color: #f9fafb;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel {
                color: #f9fafb;
                font-weight: 500;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 14px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
            QPushButton#secondaryButton {
                background-color: #374151;
                color: #d1d5db;
                border: 1px solid #4b5563;
            }
            QPushButton#secondaryButton:hover {
                background-color: #4b5563;
                border-color: #6b7280;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #374151;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #2563eb;
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #1d4ed8;
            }
            QSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 2px;
            }
            QFrame {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 12px;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #374151;
                text-align: center;
                color: white;
                font-weight: 500;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)

        # Main layout with proper spacing
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # Header section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        # App title with icon
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)

        # Icon placeholder (you can replace with actual icon)
        icon_label = QLabel()
        # Load the zap logo PNG image
        try:
            pixmap = QPixmap("zaplogo.png")
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(45, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setAlignment(Qt.AlignCenter)
            else:
                icon_label.setText("⚡")
        except Exception as e:
            print(f"Error loading zaplogo.png: {e}")
            icon_label.setText("⚡")
        icon_label.setStyleSheet("""
            QLabel {
               
                
                
                min-width: 45px;
                max-width: 45px;
                min-height: 45px;
                max-height: 45px;
            }
        """)

        app_title = QLabel("Media Silence Cutter")
        app_title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 600;
                color: #f9fafb;
                margin: 0;
            }
        """)

        title_layout.addWidget(icon_label)
        title_layout.addWidget(app_title)
        title_layout.addStretch()

        # Header buttons - all with consistent height
        tutorial_btn = QPushButton("📚 Tutorial")
        tutorial_btn.setObjectName("secondaryButton")
        tutorial_btn.setMaximumWidth(120)
        tutorial_btn.setMinimumHeight(40)
        tutorial_btn.setMaximumHeight(40)
        tutorial_btn.clicked.connect(self.open_tutorial)

        help_upgrade_btn = QPushButton("🚀 Help & Upgrade")
        help_upgrade_btn.setObjectName("secondaryButton")
        help_upgrade_btn.setMaximumWidth(150)
        help_upgrade_btn.setMinimumHeight(40)
        help_upgrade_btn.setMaximumHeight(40)
        help_upgrade_btn.clicked.connect(self.open_help_upgrade)

        # Batch Processing button
        batch_btn = QPushButton("📦 Batch Processing")
        batch_btn.setObjectName("batchButton")
        batch_btn.setMaximumWidth(150)
        batch_btn.setMinimumHeight(40)
        batch_btn.setMaximumHeight(40)
        batch_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 14px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        if BATCH_PROCESSING_AVAILABLE:
            batch_btn.clicked.connect(self.open_batch_processing)
        else:
            batch_btn.setEnabled(False)
            batch_btn.setToolTip("Batch processing feature not available")

        # Export button (moved from processing status section)
        self.export_btn = QPushButton("📤 Export Processed Media")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.process_video)
        self.export_btn.setMinimumHeight(40)
        self.export_btn.setMaximumHeight(40)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 14px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)

        header_layout.addLayout(title_layout)
        header_layout.addWidget(tutorial_btn)
        header_layout.addWidget(help_upgrade_btn)
        header_layout.addWidget(batch_btn)
        header_layout.addWidget(self.export_btn)

        main_layout.addLayout(header_layout)

        # Main content grid
        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)

        # Left Panel - Control Parameters
        left_panel = QFrame()
        left_panel.setMaximumWidth(380)
        left_panel.setMinimumWidth(380)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 0;
            }
        """)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(24)
        left_layout.setContentsMargins(24, 24, 24, 24)

        # Control Parameters Title
        params_title = QLabel("Control Parameters")
        params_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 600;
                color: #f9fafb;
                margin-bottom: 8px;
            }
        """)
        left_layout.addWidget(params_title)

        # File Selection Section
        file_section = QVBoxLayout()
        file_section.setSpacing(8)

        file_header = QHBoxLayout()
        file_label_title = QLabel("Select Media File")
        file_label_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
                color: #d1d5db;
            }
        """)

        self.file_name_label = QLabel("No file selected")
        self.file_name_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #6b7280;
            }
        """)

        file_header.addWidget(file_label_title)
        file_header.addStretch()
        file_header.addWidget(self.file_name_label)

        file_buttons = QHBoxLayout()
        file_buttons.setSpacing(8)

        select_btn = QPushButton("📁 Browse Files")
        select_btn.clicked.connect(self.select_video)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #d1d5db;
                border: 1px solid #4b5563;
                padding: 10px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4b5563;
                border-color: #6b7280;
            }
        """)

        upload_btn = QPushButton("⬆️")
        upload_btn.setObjectName("secondaryButton")
        upload_btn.setMaximumWidth(50)
        upload_btn.setToolTip("Drag & Drop")
        upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 8px;
                padding: 10px;
                min-width: 40px;
                max-width: 40px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)

        file_buttons.addWidget(select_btn, 1)
        file_buttons.addWidget(upload_btn)

        file_section.addLayout(file_header)
        file_section.addLayout(file_buttons)
        left_layout.addLayout(file_section)

        # Silence Threshold Section
        threshold_section = self.create_parameter_section(
            "Silence Threshold (dB)",
            "ℹ️",
            "Audio level below which is considered silence",
            -52, "dB", -80, -20, -52
        )
        self.threshold_slider = threshold_section['slider']
        self.threshold_value_label = threshold_section['value_label']
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        left_layout.addLayout(threshold_section['layout'])

        # Min Silence Duration Section
        duration_section = self.create_parameter_section(
            "Min Silence Duration (ms)",
            "ℹ️",
            "Minimum duration to be considered silence",
            700, "ms", 100, 2000, 700
        )
        self.duration_slider = duration_section['slider']
        self.duration_value_label = duration_section['value_label']
        self.duration_slider.valueChanged.connect(self.update_duration_label)
        left_layout.addLayout(duration_section['layout'])

        # Speech Padding Buffer Section
        padding_section = self.create_parameter_section(
            "Speech Padding Buffer (ms)",
            "ℹ️",
            "Buffer to preserve around speech segments",
            100, "ms", 0, 500, 100
        )
        self.padding_slider = padding_section['slider']
        self.padding_value_label = padding_section['value_label']
        self.padding_slider.valueChanged.connect(self.update_padding_label)
        left_layout.addLayout(padding_section['layout'])

        # Detect Silence Button
        self.detect_btn = QPushButton("🔊 Detect Silence")
        self.detect_btn.clicked.connect(self.detect_silence)
        self.detect_btn.setEnabled(False)
        self.detect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                padding: 12px 16px;
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        left_layout.addWidget(self.detect_btn)
        left_layout.addStretch()

        content_layout.addWidget(left_panel)

        # Right Panel - Video Preview & Timeline with Resizable Splitter
        right_panel = QVBoxLayout()
        right_panel.setSpacing(0)  # Remove spacing for splitter

        # Create vertical splitter for resizable video/timeline areas
        self.video_timeline_splitter = QSplitter(Qt.Vertical)
        self.video_timeline_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #374151;
                border: 1px solid #4b5563;
                height: 8px;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSplitter::handle:hover {
                background-color: #4b5563;
                border-color: #6b7280;
            }
            QSplitter::handle:pressed {
                background-color: #2563eb;
            }
        """)

        # Video Preview Section (resizable)
        video_section = QFrame()
        video_section.setStyleSheet("""
            QFrame {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 12px;
            }
        """)

        video_layout = QVBoxLayout(video_section)
        video_layout.setSpacing(0)  # No spacing to maximize video height
        video_layout.setContentsMargins(0, 0, 0, 0)  # No margins to maximize video height

        # Video container with fullscreen button overlay
        video_container = QWidget()
        video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        video_container_layout = QVBoxLayout(video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        video_container_layout.setSpacing(0)

        # Interactive Video Player (fills container height)
        self.video_player = InteractiveVideoPlayer()
        self.video_player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_player.selection_changed.connect(self.on_video_player_selection_changed)
        video_container_layout.addWidget(self.video_player, 1)

        # Integrate manual cutting with video player and timeline
        if MANUAL_CUTTING_AVAILABLE and self.manual_cutting_manager:
            # Integrate with video player
            ManualCuttingIntegration.integrate_with_video_player(self.video_player, self.manual_cutting_manager)

            # Integrate with timeline (timeline is created inside video player)
            if hasattr(self.video_player, 'timeline_widget'):
                ManualCuttingIntegration.integrate_with_timeline(self.video_player.timeline_widget, self.manual_cutting_manager)

                # Connect manual cutting signals to update export button
                self.manual_cutting_manager.manual_cuts_changed.connect(self.update_export_button_state)


        # Fullscreen button overlay
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setParent(self)  # Parent to main window for flexible positioning
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(55, 65, 81, 200);
                color: #d1d5db;
                border: 1px solid #4b5563;
                border-radius: 8px;
                padding: 8px;
                font-size: 16px;
                font-weight: bold;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(75, 85, 99, 220);
                border-color: #6b7280;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background-color: rgba(37, 99, 235, 200);
            }
        """)
        self.fullscreen_btn.setToolTip("Toggle Fullscreen (F11)")

        video_layout.addWidget(video_container, 1)

        # Progress bar (hidden by default, shown during processing) - don't add to layout to save space
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setParent(self)  # Parent to main window instead of video layout
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #374151;
                text-align: center;
                color: white;
                font-weight: 500;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)

        # Add video section to splitter
        self.video_timeline_splitter.addWidget(video_section)

        # Add timeline section from video player to splitter
        self.video_timeline_splitter.addWidget(self.video_player.timeline_section)

        # Set initial splitter sizes (60% video, 40% timeline)
        self.video_timeline_splitter.setSizes([600, 400])
        self.video_timeline_splitter.setCollapsible(0, False)  # Don't allow video section to collapse
        self.video_timeline_splitter.setCollapsible(1, False)  # Don't allow timeline section to collapse

        right_panel.addWidget(self.video_timeline_splitter, 1)

        content_layout.addLayout(right_panel, 1)
        main_layout.addLayout(content_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Initialize file label
        self.file_label = self.file_name_label

        # Initialize process_btn reference for compatibility
        self.process_btn = self.export_btn

        # Initialize fullscreen state
        self.is_fullscreen = False
        self.original_geometry = None

    def create_parameter_section(self, title, icon, tooltip, value, unit, min_val, max_val, default_val):
        """Create a modern parameter control section"""
        section_layout = QVBoxLayout()
        section_layout.setSpacing(8)

        # Header with title, icon, and value
        header_layout = QHBoxLayout()

        title_with_icon = QHBoxLayout()
        title_with_icon.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
                color: #d1d5db;
            }
        """)

        info_icon = QLabel(icon)
        info_icon.setToolTip(tooltip)
        info_icon.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
                padding: 2px;
            }
            QLabel:hover {
                color: #9ca3af;
            }
        """)

        title_with_icon.addWidget(title_label)
        title_with_icon.addWidget(info_icon)
        title_with_icon.addStretch()

        # Value display
        value_layout = QHBoxLayout()
        value_layout.setSpacing(4)

        value_input = QLabel(str(value))
        value_input.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #d1d5db;
                font-size: 14px;
                font-weight: 500;
                min-width: 40px;
                text-align: right;
            }
        """)

        unit_label = QLabel(unit)
        unit_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
            }
        """)

        value_layout.addWidget(value_input)
        value_layout.addWidget(unit_label)

        header_layout.addLayout(title_with_icon)
        header_layout.addStretch()
        header_layout.addLayout(value_layout)

        # Slider
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default_val)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #374151;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #2563eb;
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #1d4ed8;
            }
            QSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 2px;
            }
        """)

        # Scale labels
        scale_layout = QHBoxLayout()
        scale_layout.setContentsMargins(0, 4, 0, 0)

        min_label = QLabel(str(min_val))
        mid_label = QLabel(str((min_val + max_val) // 2))
        max_label = QLabel(str(max_val))

        for label in [min_label, mid_label, max_label]:
            label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #6b7280;
                }
            """)

        scale_layout.addWidget(min_label)
        scale_layout.addStretch()
        scale_layout.addWidget(mid_label)
        scale_layout.addStretch()
        scale_layout.addWidget(max_label)

        section_layout.addLayout(header_layout)
        section_layout.addWidget(slider)
        section_layout.addLayout(scale_layout)

        return {
            'layout': section_layout,
            'slider': slider,
            'value_label': value_input
        }

    def update_threshold_label(self):
        value = self.threshold_slider.value()
        self.threshold_value_label.setText(f"{value}")

    def update_duration_label(self):
        value = self.duration_slider.value()
        self.duration_value_label.setText(f"{value}")

    def update_padding_label(self):
        value = self.padding_slider.value()
        self.padding_value_label.setText(f"{value}")

    def is_audio_file(self, file_path):
        """Check if the file is an audio-only file based on extension"""
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in audio_extensions

    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Media File", "",
            "All Supported Files (*.mp4 *.avi *.mkv *.mov *.wmv *.mp3 *.wav *.flac *.aac *.ogg *.m4a);;Video Files (*.mp4 *.avi *.mkv *.mov *.wmv);;Audio Files (*.mp3 *.wav *.flac *.aac *.ogg *.m4a)"
        )

        if file_path:
            # Validate file usage with API
            if API_COMMUNICATION_AVAILABLE:
                try:
                    # Get file size in minutes (estimate)
                    file_size_bytes = os.path.getsize(file_path)
                    # Rough estimate: 1MB = ~1 minute for compressed video
                    estimated_minutes = max(1, file_size_bytes / (1024 * 1024))
                    
                    validation_result = api_client.validate_file_usage(
                        file_path=file_path,
                        estimated_duration_minutes=estimated_minutes
                    )
                    
                    if not validation_result.get('allowed', False):
                        message = validation_result.get('message', 'Usage limit exceeded')
                        QMessageBox.warning(
                            self,
                            "Usage Limit Exceeded",
                            f"{message}\n\nPlease upgrade your plan to continue processing files."
                        )
                        # Open upgrade page
                        self.open_help_upgrade()
                        return
                        
                    print(f"✅ File usage validated: {validation_result.get('message', 'OK')}")
                except Exception as e:
                    print(f"⚠️ API validation failed: {e}")
                    # Continue in offline mode
            
            # Check if this is an audio file
            is_audio = self.is_audio_file(file_path)

            # Show loading overlay with appropriate message
            if is_audio:
                self.show_loading_overlay("Loading Audio...")
            else:
                self.show_loading_overlay("Loading Video...")

            # Initialize loading progress tracking
            self.loading_start_time = time.time()
            self.loading_steps_completed = 0
            self.total_loading_steps = 4 if is_audio else 6  # Fewer steps for audio

            # Get file size for better time estimation
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                # Audio files load faster than video files
                time_multiplier = 0.2 if is_audio else 0.5
                self.estimated_total_time = max(3, min(20, file_size_mb * time_multiplier))
            except:
                self.estimated_total_time = 10 if is_audio else 15  # Default estimate

            # Clear previous data first
            self.clear_previous_data()

            
            # Additional clearing for repeated word segments
            if hasattr(self, "repeated_word_segments"):
                self.repeated_word_segments = []
            
            # Reset repeated words button state
            if hasattr(self, "repeated_words_btn"):
                self.repeated_words_btn.setEnabled(False)
                self.repeated_words_btn.setText("🔄 Detect Repeated Words")

            
            # IMMEDIATE TIMELINE CLEARING - Force clear before loading new file
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
                timeline = self.video_player.timeline_widget
                
                # Immediate clearing of all timeline data
                timeline.set_duration(0)
                timeline.silent_parts = []
                timeline.silent_ranges = []
                timeline.waveform_data = None
                timeline.waveform_max_amplitude = 0
                timeline.current_position = 0
                timeline.duration_seconds = 0
                timeline.target_position = 0
                
                # Clear repeated word data immediately
                if hasattr(timeline, 'repeated_word_segments'):
                    timeline.repeated_word_segments = []
                if hasattr(timeline, 'all_segments'):
                    timeline.all_segments = []
                
                # Clear all caches immediately
                if hasattr(timeline, 'waveform_cache') and timeline.waveform_cache:
                    timeline.waveform_cache.clear()
                
                # Clear all interaction state
                timeline.hover_region = None
                timeline.dragging_region = None
                timeline.dragging_edge = None
                timeline.preview_mode = False
                timeline.seeking = False
                
                # Force immediate visual update
                timeline.update()
                timeline.repaint()
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()

            
            # CLEAR MANUAL CUTTING DATA
            if MANUAL_CUTTING_AVAILABLE and hasattr(self, 'manual_cutting_manager') and self.manual_cutting_manager:
                # Clear all manual cuts and ranges
                self.manual_cutting_manager.manual_cuts.clear()
                self.manual_cutting_manager.manual_cut_ranges.clear()
                # Emit signal to update UI
                self.manual_cutting_manager.manual_cuts_changed.emit([])
                print("✅ Cleared manual cutting data")
            
            # Clear manual cut overlay if present
            if hasattr(self, 'manual_cut_overlay') and self.manual_cut_overlay:
                self.manual_cut_overlay.clear_all_cuts()
                self.manual_cut_overlay.reset_state()
                print("✅ Cleared manual cut overlay")

            self.video_path = file_path

            # Start transcript generation if available
            if TRANSCRIPT_INTEGRATION_AVAILABLE:
                pass
                try:
                    start_transcript_generation(self, file_path)
                except Exception as e:
                    print(f"⚠️  Transcript generation failed: {e}")
            self.is_audio_only = is_audio
            file_name = os.path.basename(file_path)
            self.file_label.setText(file_name)
            self.detect_btn.setEnabled(True)
            self.silent_parts = []
            self.process_btn.setEnabled(False)

            if is_audio:
                # For audio files, load into video player for playback controls
                self.update_loading_progress_with_step("Setting up audio player...", 1)
                self.video_player.load_video(file_path)  # This will detect audio and call load_audio_only

                # Enable performance optimizations immediately
                self.enable_performance_optimizations()

                # Extended fallback timer - only hide if something goes wrong
                QTimer.singleShot(30000, self.hide_loading_overlay_fallback)  # 30 seconds instead of 3
            else:
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
            pass
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
            pass
            return

        # Get current threshold and duration values
        silence_threshold = self.threshold_slider.value()
        min_silence_duration = self.duration_slider.value()
        padding_ms = self.padding_slider.value()

        # Disable UI elements during detection
        self.detect_btn.setEnabled(False)

        # Show processing modal for detection
        self.show_processing_modal("Detecting Silence", "Analyzing audio for silent regions...")

        # Initialize detection timing
        self.detection_start_time = time.time()
        try:
            file_size_mb = os.path.getsize(self.video_path) / (1024 * 1024)
            self.detection_estimated_time = max(10, min(120, file_size_mb * 2))  # Rough estimate: 2 seconds per MB, 10-120 second range
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
        # Update modal progress
        self.update_processing_modal(progress)
        # Store current progress for countdown timer
        self.current_detection_progress = progress

    def update_detection_countdown(self):
        """Update detection progress with real-time countdown"""
        if not hasattr(self, 'current_detection_progress'):
            pass
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

    def show_detection_results(self, silent_parts):
        # Stop the countdown timer and reset variables
        if hasattr(self, 'detection_timer'):
            self.detection_timer.stop()
            delattr(self, 'detection_timer')

        # Clean up countdown variables
        for attr in ['detection_countdown_time', 'detection_last_update', 'current_detection_progress']:
            pass
            if hasattr(self, attr):
                delattr(self, attr)

        # Ensure progress reaches 100% before showing results
        self.update_processing_modal(100, "Detection complete!")
        QApplication.processEvents()

        # Small delay to show 100% completion then hide modal
        QTimer.singleShot(1000, self.hide_processing_modal)

        self.silent_parts = silent_parts
        self.silent_ranges = [(part['start'] * 1000, part['end'] * 1000) for part in silent_parts]

        # Enable process button
        self.process_btn.setEnabled(True)
        self.detect_btn.setEnabled(True)

        # Update video player with silent parts
        self.video_player.set_silent_parts(silent_parts)

        # Enable preview mode to activate silent region skipping during playback
        self.video_player.enable_preview_mode()

        # Re-enable performance optimizations after detection
        self.enable_performance_optimizations()


        # Log results to console (no popup)
        total_silence_duration = sum(part['end'] - part['start'] for part in silent_parts)
        print(f"  • Found {len(silent_parts)} silent regions")
        print(f"  • Total silence duration: {total_silence_duration:.1f} seconds")
        print(f"  • Click on timeline regions to select/deselect them for processing")

    def on_video_player_selection_changed(self, changed_part):
        """Handle selection changes from the video player"""
        # This method is called when a silent part selection changes
        self.update_export_button_state()

    def update_export_button_state(self):
        """Update export button state based on selected regions"""
        if not hasattr(self, 'export_btn'):
            pass
            return

        # Check if there are selected silence regions
        selected_silence = any(part.get('selected', False) for part in self.silent_parts)

        # Check if there are selected manual cuts
        selected_manual_cuts = False
        if MANUAL_CUTTING_AVAILABLE and self.manual_cutting_manager:
            selected_manual_cuts = any(cut.get('selected', False) for cut in self.manual_cutting_manager.manual_cuts)

        # Enable export button if there are any selected regions
        has_selections = selected_silence or selected_manual_cuts
        self.export_btn.setEnabled(has_selections and self.video_path is not None)

        if has_selections:
            silence_count = sum(1 for part in self.silent_parts if part.get('selected', False))
            manual_count = 0
            if MANUAL_CUTTING_AVAILABLE and self.manual_cutting_manager:
                manual_count = sum(1 for cut in self.manual_cutting_manager.manual_cuts if cut.get('selected', False))

            total_count = silence_count + manual_count

    def process_video(self):
        if not self.video_path:
            pass
            return

        # Get selected silent parts
        selected_parts = [part for part in self.silent_parts if part.get('selected', False)]

        # Get selected manual cuts if available
        manual_cuts = []
        if MANUAL_CUTTING_AVAILABLE and self.manual_cutting_manager:
            manual_cuts = [cut for cut in self.manual_cutting_manager.manual_cuts if cut.get('selected', False)]

        # Combine silent parts and manual cuts
        all_selected_parts = selected_parts + manual_cuts

        if not all_selected_parts:
            pass
            if not self.silent_parts and not manual_cuts:
                QMessageBox.warning(self, "No Regions", "Please detect silence or create manual cuts first.")
            else:
                QMessageBox.warning(self, "No Selection", "Please select at least one region (silence or manual cut) to process.")
            return

        # Sort combined parts by start time for processing
        all_selected_parts.sort(key=lambda x: x['start'])

        # Check if this is an audio file
        is_audio = getattr(self, 'is_audio_only', False)

        # Get output file path with appropriate filter
        base_name = os.path.splitext(os.path.basename(self.video_path))[0]

        if is_audio:
            # For audio files, preserve the original format or allow format selection
            original_ext = os.path.splitext(self.video_path)[1]
            default_name = f"{base_name}_silences_removed{original_ext}"
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Save Processed Audio", default_name,
                "Audio Files (*.mp3 *.wav *.flac *.aac *.ogg *.m4a);;MP3 Files (*.mp3);;WAV Files (*.wav);;FLAC Files (*.flac);;AAC Files (*.aac);;OGG Files (*.ogg);;M4A Files (*.m4a)"
            )
        else:
            # For video files
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Save Processed Video", f"{base_name}_silences_removed.mp4",
                "Video Files (*.mp4)"
            )

        if not output_path:
            pass
            return

        # Disable UI elements during processing
        self.process_btn.setEnabled(False)
        self.detect_btn.setEnabled(False)

        # Show processing modal with appropriate message
        if is_audio:
            self.show_processing_modal("Processing Audio", "Removing silent regions from audio...")
        else:
            self.show_processing_modal("Processing Video", "Removing silent regions from video...")

        # Initialize processing timing
        self.processing_start_time = time.time()
        try:
            file_size_mb = os.path.getsize(self.video_path) / (1024 * 1024)
            # Audio processing is generally faster than video processing
            time_multiplier = 2 if is_audio else 5
            self.processing_estimated_time = max(15 if is_audio else 30, min(120 if is_audio else 300, file_size_mb * time_multiplier))
        except:
            self.processing_estimated_time = 30 if is_audio else 60  # Default estimate

        # Start real-time countdown timer for processing
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self.update_processing_countdown)
        self.processing_timer.start(1000)  # Update every second

        # Start the appropriate processing thread
        if is_audio:
            self.processing_thread = AudioProcessingThread(self.video_path, all_selected_parts, output_path)
        else:
            self.processing_thread = ProcessingThread(self.video_path, all_selected_parts, output_path)

        self.processing_thread.progress_updated.connect(self.update_processing_progress)
        self.processing_thread.processing_complete.connect(self.show_processing_results)
        self.processing_thread.start()

    
        # Record usage after successful processing
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
                print(f"⚠️ Failed to record usage: {e}")

    def update_processing_progress(self, progress):
        # Update modal progress
        self.update_processing_modal(progress)
        # Store current progress for countdown timer
        self.current_processing_progress = progress

    def update_processing_countdown(self):
        """Update processing progress with real-time countdown"""
        if not hasattr(self, 'current_processing_progress'):
            pass
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
                    if abs(progress_based_estimate - self.processing_countdown_time) > 10 and progress_based_estimate < self.processing_countdown_time * 1.5:
                        self.processing_countdown_time = min(self.processing_countdown_time, progress_based_estimate)

            # Handle final stages (90%+) - extend time if needed
            if progress >= 90 and self.processing_countdown_time < 10:
                self.processing_countdown_time = max(10, self.processing_countdown_time)

    def show_processing_results(self, output_path):
        # Stop the countdown timer and reset variables
        if hasattr(self, 'processing_timer'):
            self.processing_timer.stop()
            delattr(self, 'processing_timer')

        # Clean up countdown variables
        for attr in ['processing_countdown_time', 'processing_last_update', 'current_processing_progress']:
            pass
            if hasattr(self, attr):
                delattr(self, attr)

        # Ensure progress reaches 100% before showing results
        self.update_processing_modal(100, "Processing complete!")
        QApplication.processEvents()

        # Small delay to show 100% completion then hide modal
        QTimer.singleShot(1000, self.hide_processing_modal)

        # Re-enable UI elements
        self.process_btn.setEnabled(True)
        self.detect_btn.setEnabled(True)


        # Show completion message with option to open output folder
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Processing Complete")
        msg.setText(f"Video processing completed successfully!\n\nOutput saved to:\n{output_path}")
        msg.setStandardButtons(QMessageBox.Ok)

        # Add button to open output folder
        open_folder_btn = msg.addButton("Open Folder", QMessageBox.ActionRole)

        msg.exec_()

        if msg.clickedButton() == open_folder_btn:
            # Open the output folder
            import subprocess
            import platform

            folder_path = os.path.dirname(output_path)
            try:
                pass
                if platform.system() == "Windows":
                    # Use proper list format and normalize path separators
                    normalized_path = os.path.normpath(output_path)
                    subprocess.Popen(['explorer', '/select,', normalized_path])
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", "-R", output_path])
                else:  # Linux
                    subprocess.Popen(["xdg-open", folder_path])
            except Exception as e:
                print(f"Error opening folder: {e}")
                # Fallback: try to open just the folder
                try:
                    pass
                    if platform.system() == "Windows":
                        subprocess.Popen(['explorer', folder_path])
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.Popen(["open", folder_path])
                    else:  # Linux
                        subprocess.Popen(["xdg-open", folder_path])
                except Exception as e2:
                    print(f"Fallback folder opening also failed: {e2}")

    def closeEvent(self, event):
        """Handle application close event"""
        # Stop any running threads
        if hasattr(self, 'detection_thread') and self.detection_thread.isRunning():
            self.detection_thread.terminate()
            self.detection_thread.wait()

        if hasattr(self, 'processing_thread') and self.processing_thread.isRunning():
            self.processing_thread.terminate()
            self.processing_thread.wait()

        # Clean up video player resources
        if hasattr(self, 'video_player'):
            self.video_player.cleanup_fallback_resources()

        # Clean up buffers and caches
        self.cleanup_buffers()

        event.accept()

    def cleanup_buffers(self):
        """Clean up all circular buffers and caches"""
        try:
            # Clean up timeline widget buffers
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
                timeline = self.video_player.timeline_widget

                # Clear waveform cache
                if hasattr(timeline, 'waveform_cache'):
                    timeline.waveform_cache.clear()

                # Clear any other buffers
                if hasattr(timeline, 'frame_buffer'):
                    timeline.frame_buffer.clear()

                if hasattr(timeline, 'audio_buffer'):
                    timeline.audio_buffer.clear()

        except Exception as e:
            print(f"⚠️ Error cleaning up buffers: {e}")

    def get_buffer_stats(self):
        """Get statistics from all buffers for debugging"""
        stats = {}

        try:
            pass
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
                timeline = self.video_player.timeline_widget

                if hasattr(timeline, 'frame_buffer'):
                    stats['frame_buffer'] = timeline.frame_buffer.get_cache_stats()

                if hasattr(timeline, 'audio_buffer'):
                    stats['audio_buffer'] = {
                        'size': len(timeline.audio_buffer.buffer),
                        'max_size': timeline.audio_buffer.max_samples
                    }

                if hasattr(timeline, 'waveform_cache'):
                    stats['waveform_cache'] = {
                        'entries': len(timeline.waveform_cache.cache),
                        'max_entries': timeline.waveform_cache.max_levels
                    }
        except Exception as e:
            stats['error'] = str(e)

        return stats

    def enable_performance_optimizations(self):
        """Enable performance optimizations for smooth playback"""
        try:
            pass
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
                timeline = self.video_player.timeline_widget
                timeline.enable_caching()

        except Exception as e:
            print(f"⚠️ Error enabling optimizations: {e}")

    def disable_performance_optimizations(self):
        """Disable performance optimizations for faster processing"""
        try:
            pass
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
                timeline = self.video_player.timeline_widget
                timeline.disable_caching()

        except Exception as e:
            print(f"⚠️ Error disabling optimizations: {e}")

    def clear_previous_data(self):
        """Clear all previous video/audio data and completely reset interface to pristine state"""
        try:
            # Reset core data
            self.video_path = None
            self.is_audio_only = False
            self.silent_parts = []
            self.silent_ranges = []

            # === CAPTION/TRANSCRIPT COMPLETE RESET ===
            if hasattr(self, 'transcript_data'):
                self.transcript_data = []

            # Clear all forms of caption/transcript text widgets
            if hasattr(self, 'caption_text'):
                self.caption_text.clear()
                self.caption_text.setPlainText("")  # Ensure text widget is completely empty
                self.caption_text.update()  # Force visual update

            if hasattr(self, 'transcript_label'):
                self.transcript_label.setText("")
                self.transcript_label.update()

            # Clear transcript widget completely with all its components
            if hasattr(self, 'transcript_widget') and self.transcript_widget:
                pass
                try:
                    # Clear all transcript data
                    self.transcript_widget.transcript_data = []
                    if hasattr(self.transcript_widget, 'word_widgets'):
                        # Delete all word widgets
                        for widget in self.transcript_widget.word_widgets:
                            pass
                            if widget:
                                widget.deleteLater()
                        self.transcript_widget.word_widgets = []

                    self.transcript_widget.current_word_index = -1

                    # Reset UI elements
                    if hasattr(self.transcript_widget, 'status_label'):
                        self.transcript_widget.status_label.setText("No transcript loaded")
                        self.transcript_widget.status_label.show()
                    if hasattr(self.transcript_widget, 'download_txt_btn'):
                        self.transcript_widget.download_txt_btn.setEnabled(False)
                    if hasattr(self.transcript_widget, 'download_srt_btn'):
                        self.transcript_widget.download_srt_btn.setEnabled(False)

                    # Clear transcript layout completely
                    if hasattr(self.transcript_widget, 'transcript_layout'):
                        pass
                        while self.transcript_widget.transcript_layout.count():
                            item = self.transcript_widget.transcript_layout.takeAt(0)
                            if item and item.widget():
                                item.widget().deleteLater()

                    # Force complete visual update
                    if hasattr(self.transcript_widget, 'scroll_area'):
                        self.transcript_widget.scroll_area.update()
                    if hasattr(self.transcript_widget, 'transcript_content'):
                        self.transcript_widget.transcript_content.update()
                    self.transcript_widget.update()
                    self.transcript_widget.repaint()

                except Exception as e:
                    print(f"⚠️ Error clearing transcript widget: {e}")

            # Clear any enhanced transcript widgets
            if hasattr(self, 'enhanced_transcript_widget') and self.enhanced_transcript_widget:
                pass
                try:
                    self.enhanced_transcript_widget.transcript_data = []
                    if hasattr(self.enhanced_transcript_widget, 'clear_transcript'):
                        self.enhanced_transcript_widget.clear_transcript()
                except:
                    pass

            # === VIDEO/AUDIO PREVIEW COMPLETE RESET ===
            if hasattr(self, 'video_player'):
                # Stop and clear media player completely
                if hasattr(self.video_player, 'media_player') and self.video_player.media_player:
                    self.video_player.media_player.stop()
                    self.video_player.media_player.setMedia(None)
                    self.video_player.media_player.setPosition(0)

                # Clear video display
                if hasattr(self.video_player, 'video_widget'):
                    pass
                    try:
                        # Reset video widget to blank state
                        self.video_player.video_widget.update()
                    except:
                        pass

                # Clear video frame label
                if hasattr(self.video_player, 'video_frame_label'):
                    self.video_player.video_frame_label.clear()
                    self.video_player.video_frame_label.setText("No video loaded")

                # Clean up all video player resources
                self.video_player.cleanup_fallback_resources()

            # === INTERACTIVE TIMELINE COMPLETE RESET ===
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
                timeline = self.video_player.timeline_widget

                # STOP ALL TIMELINE TIMERS FIRST
                if hasattr(timeline, 'animation_timer') and timeline.animation_timer:
                    timeline.animation_timer.stop()

                # CLEAR ALL TIMELINE DATA COMPLETELY
                timeline.set_duration(0)
                timeline.set_silent_parts([], [])
                timeline.silent_parts = []
                timeline.silent_ranges = []
                timeline.current_position = 0
                timeline.duration_seconds = 0
                timeline.video_path = None

                # CLEAR ANIMATION STATE
                timeline.target_position = 0

                # CLEAR DEBUG STATE
                timeline.debug_click_position = None
                timeline.debug_click_x = None

                # RESET ZOOM AND VIEW COMPLETELY
                timeline.zoom_level = 1.0
                timeline.zoom_offset = 0.0
                timeline.min_zoom = 1.0
                timeline.max_zoom = 10.0
                if hasattr(timeline, 'reset_zoom'):
                    timeline.reset_zoom()

                # CLEAR ALL WAVEFORM DATA COMPLETELY
                timeline.waveform_data = None
                timeline.waveform_max_amplitude = 0
                if hasattr(timeline, 'waveform_cache'):
                    timeline.waveform_cache.clear()
                    # Force cache rebuild on next load
                    timeline.cache_enabled = True
                    timeline.cache_during_loading = False

                # CLEAR UNDO/REDO HISTORY COMPLETELY
                timeline.history = []
                timeline.history_index = -1

                # RESET ALL INTERACTION STATE COMPLETELY
                timeline.dragging_region = None
                timeline.dragging_edge = None
                timeline.drag_start_pos = None
                timeline.drag_start_state = None
                timeline.hover_region = None
                timeline.seeking = False
                timeline.preview_mode = False

                # CLEAR ALL CACHED VISUAL DATA
                if hasattr(timeline, 'cached_regions'):
                    timeline.cached_regions = []
                if hasattr(timeline, 'drawn_regions'):
                    timeline.drawn_regions = []
                if hasattr(timeline, 'reset_button_rect'):
                    timeline.reset_button_rect = None
                if hasattr(timeline, 'zoom_in_button_rect'):
                    timeline.zoom_in_button_rect = None
                if hasattr(timeline, 'zoom_out_button_rect'):
                    timeline.zoom_out_button_rect = None

                # CLEAR TOOLTIP STATE
                timeline.setToolTip("")

                # FORCE COMPLETE VISUAL AND DATA RESET
                timeline.update()
                timeline.repaint()

                # ADDITIONAL FORCED CLEARING WITH DELAY
                from PyQt5.QtCore import QTimer
                from PyQt5.QtWidgets import QApplication

                def force_timeline_clear():
                    try:
                        # AGGRESSIVE SECOND PASS CLEARING - REMOVE ALL VISUAL ARTIFACTS
                        timeline.silent_parts = []
                        timeline.silent_ranges = []
                        timeline.waveform_data = None

                        
                        # CLEAR REPEATED WORD DATA
                        if hasattr(timeline, "repeated_word_segments"):
                            timeline.repeated_word_segments = []
                        if hasattr(timeline, "all_segments"):
                            timeline.all_segments = []

                        
                        # CLEAR WAVEFORM AMPLITUDE AND CACHES
                        timeline.waveform_max_amplitude = 0
                        if hasattr(timeline, 'waveform_cache') and timeline.waveform_cache:
                            timeline.waveform_cache.clear()

                        # CLEAR VISUAL INTERACTION STATE
                        timeline.hover_region = None
                        timeline.dragging_region = None
                        timeline.dragging_edge = None
                        timeline.preview_mode = False
                        timeline.seeking = False

                        # FORCE CLEAR ALL VISUAL STATES
                        timeline.current_position = 0
                        timeline.duration_seconds = 0
                        timeline.target_position = 0

                        # CLEAR WIDGET INTERNAL STATES
                        if hasattr(timeline, 'waveform_cache'):
                            timeline.waveform_cache.clear()

                        # FORCE WIDGET GEOMETRY UPDATE
                        timeline.updateGeometry()
                        timeline.adjustSize()

                        # MULTIPLE VISUAL UPDATES TO FORCE REDRAW
                        timeline.update()
                        timeline.repaint()
                        QApplication.processEvents()
                        timeline.update()
                        timeline.repaint()
                        QApplication.processEvents()

                    except:
                        pass

                def ultra_timeline_clear():
                    try:
                        # ULTRA AGGRESSIVE THIRD PASS - NUCLEAR OPTION
                        timeline.silent_parts = []
                        timeline.silent_ranges = []
                        timeline.waveform_data = None
                        timeline.waveform_max_amplitude = 0
                        timeline.current_position = 0
                        timeline.duration_seconds = 0

                        
                        # CLEAR REPEATED WORD SEGMENTS AGAIN
                        if hasattr(timeline, "repeated_word_segments"):
                            timeline.repeated_word_segments = []
                        if hasattr(timeline, "all_segments"):
                            timeline.all_segments = []

                        
                        # NUCLEAR CACHE CLEARING
                        if hasattr(timeline, 'waveform_cache') and timeline.waveform_cache:
                            timeline.waveform_cache.clear()
                            if hasattr(timeline.waveform_cache, 'cache'):
                                timeline.waveform_cache.cache.clear()

                        # RESET ALL POSITIONING AND ANIMATION
                        timeline.target_position = 0
                        timeline.hover_region = None
                        timeline.dragging_region = None
                        timeline.dragging_edge = None
                        timeline.preview_mode = False
                        timeline.seeking = False

                        # FORCE COMPLETE WIDGET REFRESH
                        timeline.hide()
                        QApplication.processEvents()
                        timeline.show()
                        QApplication.processEvents()

                        # FINAL CLEARING
                        timeline.update()
                        timeline.repaint()

                    except:
                        pass

                # Schedule multiple delayed clearing passes to ensure complete removal
                QTimer.singleShot(100, force_timeline_clear)
                QTimer.singleShot(300, ultra_timeline_clear)  # Ultra aggressive clearing


            # === UI ELEMENTS RESET ===
            if hasattr(self, 'file_label'):
                self.file_label.setText("No file selected")

            if hasattr(self, 'detect_btn'):
                self.detect_btn.setEnabled(False)

            if hasattr(self, 'process_btn'):
                self.process_btn.setEnabled(False)

            if hasattr(self, 'progress_bar'):
                self.progress_bar.setVisible(False)
                self.progress_bar.setValue(0)

            # Clear all result displays
            if hasattr(self, 'results_list'):
                self.results_list.clear()

            # Reset sliders to default values
            if hasattr(self, 'threshold_slider'):
                self.threshold_slider.setValue(-40)  # Default threshold
            if hasattr(self, 'duration_slider'):
                self.duration_slider.setValue(1000)  # Default min duration
            if hasattr(self, 'padding_slider'):
                self.padding_slider.setValue(100)  # Default padding

            # === FEATURES COMPLETE RESET ===

            # Clear manual cuts completely
            if hasattr(self, 'manual_cut_overlay') and self.manual_cut_overlay:
                self.manual_cut_overlay.clear_all_cuts()
                self.manual_cut_overlay.reset_state()

            # Clear manual cutting manager data
            if MANUAL_CUTTING_AVAILABLE and hasattr(self, 'manual_cutting_manager') and self.manual_cutting_manager:
                self.manual_cutting_manager.manual_cuts.clear()
                self.manual_cutting_manager.manual_cut_ranges.clear()
                self.manual_cutting_manager.manual_cuts_changed.emit([])

            # Reset batch processing
            if hasattr(self, 'batch_widget') and self.batch_widget:
                pass
                try:
                    self.batch_widget.clear_files()
                    self.batch_widget.reset_interface()
                except:
                    pass

            # Clear any resolution optimizer data
            if hasattr(self, 'resolution_optimizer'):
                pass
                try:
                    self.resolution_optimizer = None
                except:
                    pass

            # === SYSTEM CLEANUP ===

            # Hide any processing modals
            self.hide_processing_modal()

            # Stop all running timers
            for attr_name in dir(self):
                attr = getattr(self, attr_name)
                if isinstance(attr, QTimer) and attr.isActive():
                    attr.stop()

            # Clean up all buffers and caches
            self.cleanup_buffers()

            # Force garbage collection for memory cleanup
            import gc
            gc.collect()


        except Exception as e:
            print(f"⚠️ Error during complete interface reset: {e}")

    def show_loading_overlay(self, message="Loading..."):
        """Show loading overlay with message"""
        if not self.loading_overlay:
            self.loading_overlay = LoadingOverlay(self)

        self.loading_overlay.show_loading(message)
        self.loading_overlay.raise_()
        QApplication.processEvents()

    def update_loading_progress(self, message):
        """Update loading overlay message"""
        if self.loading_overlay:
            self.loading_overlay.update_progress(message)
            QApplication.processEvents()

    def hide_loading_overlay(self):
        """Hide loading overlay"""
        if self.loading_overlay:
            self.loading_overlay.hide_loading()

    def resizeEvent(self, event):
        """Handle window resize events"""
        # DEBUG: Log resize events

        super().resizeEvent(event)
        if self.loading_overlay:
            self.loading_overlay.resize(self.size())

        # Handle fullscreen video sizing
        if self.is_fullscreen and hasattr(self, 'video_player') and hasattr(self.video_player, 'video_frame_label'):
            video_frame_label = self.video_player.video_frame_label
            print(f"  🖥️  Fullscreen video resize: {self.size()}")

            # In fullscreen, make sure video frame label fills the entire window
            fullscreen_size = self.size()
            video_frame_label.setFixedSize(fullscreen_size)
            video_frame_label.setGeometry(0, 0, fullscreen_size.width(), fullscreen_size.height())

            # If there's a current frame, rescale it to new fullscreen size
            if hasattr(video_frame_label, 'pixmap') and video_frame_label.pixmap():
                current_pixmap = video_frame_label.pixmap()
                if current_pixmap:
                    fullscreen_pixmap = current_pixmap.scaled(fullscreen_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    video_frame_label.setPixmap(fullscreen_pixmap)
                    print(f"  🖼️  Rescaled frame for fullscreen resize: {fullscreen_pixmap.size()}")

            video_frame_label.repaint()

        # DEBUG: Log video container size after resize
        if hasattr(self, 'video_player') and hasattr(self.video_player, 'video_frame_label'):
            container_widget = self.video_player.video_frame_label.parent()
            print(f"  🏷️  Video label geometry after resize: {self.video_player.video_frame_label.geometry()}")
            if container_widget:
                pass
        print()

        # Position fullscreen button in lower right corner of video container
        if hasattr(self, 'fullscreen_btn') and hasattr(self, 'video_player'):
            QTimer.singleShot(10, self.position_fullscreen_button)  # Delay to ensure layout is updated

        # Reset timeline zoom when window is resized to ensure complete waveform is visible
        if hasattr(self, 'video_player') and hasattr(self.video_player, 'timeline_widget'):
            timeline = self.video_player.timeline_widget

            # Only reset zoom if the window size change is significant (e.g., maximizing)
            if event.oldSize().isValid():
                old_area = event.oldSize().width() * event.oldSize().height()
                new_area = event.size().width() * event.size().height()
                area_change_ratio = new_area / old_area if old_area > 0 else 1.0

                # If window area changed by more than 30%, reset timeline zoom and clear cache for proper waveform fitting
                if area_change_ratio > 1.3 or area_change_ratio < 0.77:
                    print(f"  📊 Significant window resize detected (area change: {area_change_ratio:.2f}x), resetting timeline zoom and clearing cache")

                    # Clear waveform cache to force complete redraw with new dimensions
                    if hasattr(timeline, 'waveform_cache'):
                        timeline.waveform_cache.clear()
                        print("  🧹 Waveform cache cleared for proper scaling")

                    # Reset zoom to show complete waveform
                    timeline.reset_zoom()

                    # Handle resize to clear cache and force proper redraw
                    timeline.handle_resize()

                    # Additional update after a short delay to ensure proper layout
                    QTimer.singleShot(100, timeline.update)

    def position_fullscreen_button(self):
        """Position the fullscreen button in the lower right corner of the video section"""
        if hasattr(self, 'fullscreen_btn') and hasattr(self, 'video_player'):
            # Get the video section from the splitter (first widget)
            if hasattr(self, 'video_timeline_splitter') and self.video_timeline_splitter.count() > 0:
                video_section = self.video_timeline_splitter.widget(0)
                if video_section:
                    # Get video section geometry
                    section_rect = video_section.geometry()
                    button_size = self.fullscreen_btn.size()

                    # Position relative to the main window, accounting for video section position
                    # Get the video section's position relative to main window
                    section_pos = video_section.mapTo(self, video_section.rect().topLeft())

                    # Position in lower right corner with 16px margin
                    x = section_pos.x() + section_rect.width() - button_size.width() - 16
                    y = section_pos.y() + section_rect.height() - button_size.height() - 16

                    self.fullscreen_btn.move(x, y)
                    self.fullscreen_btn.raise_()  # Ensure button is on top
                    self.fullscreen_btn.show()  # Ensure button is visible

    def open_batch_processing(self):
        """Open batch processing dialog"""
        if not BATCH_PROCESSING_AVAILABLE:
            QMessageBox.warning(
                self,
                "Feature Not Available",
                "Batch processing feature is not available. Please ensure the batch_processing module is properly installed."
            )
            return

        try:
            from features.batch_processing import BatchProcessingDialog

            # Create and show batch processing dialog
            dialog = BatchProcessingDialog(
                self,
                SilenceDetectionThread,
                ProcessingThread,
                AudioProcessingThread
            )
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Batch Processing Error",
                f"Failed to open batch processing dialog:\n{str(e)}"
            )
    def open_tutorial(self):
        """Open tutorial video in browser"""
        tutorial_url = "https://youtu.be/YOUR_TUTORIAL_VIDEO_ID"  # Replace with actual tutorial URL
        try:
            webbrowser.open(tutorial_url)
            print(f"✅ Opening tutorial: {tutorial_url}")
        except Exception as e:
            print(f"❌ Failed to open tutorial: {e}")
            QMessageBox.information(
                self,
                "Tutorial",
                f"Please visit our tutorial at:\n{tutorial_url}"
            )

    def open_help_upgrade(self):
        """Open help and upgrade page"""
        try:
            if API_COMMUNICATION_AVAILABLE:
                upgrade_url = api_client.open_upgrade_page()
            else:
                upgrade_url = "https://silencecutter.com/pricing"
            
            webbrowser.open(upgrade_url)
            print(f"✅ Opening help & upgrade: {upgrade_url}")
        except Exception as e:
            print(f"❌ Failed to open help & upgrade: {e}")
            QMessageBox.information(
                self,
                "Help & Upgrade",
                f"Please visit our help page at:\n{upgrade_url if 'upgrade_url' in locals() else 'https://silencecutter.com/pricing'}"
            )



    def show_shortcuts_modal(self):
        """Show keyboard shortcuts in a modal dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setModal(True)
        dialog.setFixedSize(500, 350)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #111827;
                color: #f9fafb;
            }
            QLabel {
                color: #f9fafb;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(24)
        layout.setContentsMargins(32, 32, 32, 32)

        # Title
        title = QLabel("⌨️ Keyboard Shortcuts")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 600;
                color: #f9fafb;
                margin-bottom: 16px;
            }
        """)
        layout.addWidget(title)

        # Shortcuts grid
        shortcuts_data = [
            ("Space", "Play/Pause video"),
            ("S", "Stop playback"),
            ("←/→", "Navigate 5 seconds"),
            ("Ctrl+S", "Save project"),
            ("Ctrl+O", "Open video file"),
            ("Ctrl+E", "Export processed video"),
            ("Ctrl+D", "Detect silence"),
            ("Shift+Click", "Manual cut selection"),
            ("Ctrl+X", "Cut selected regions"),
            ("Esc", "Close dialogs/Cancel selection")
        ]

        for key, action in shortcuts_data:
            shortcut_layout = QHBoxLayout()
            shortcut_layout.setSpacing(16)

            key_label = QLabel(key)
            key_label.setStyleSheet("""
                QLabel {
                    background-color: #374151;
                    color: #d1d5db;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                    font-family: 'Consolas', 'Monaco', monospace;
                    min-width: 80px;
                    text-align: center;
                }
            """)

            action_label = QLabel(action)
            action_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #d1d5db;
                }
            """)

            shortcut_layout.addWidget(key_label)
            shortcut_layout.addWidget(action_label)
            shortcut_layout.addStretch()

            layout.addLayout(shortcut_layout)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        dialog.exec_()

    def show_processing_modal(self, title="Processing Video", message="Processing your video..."):
        """Show processing progress in a modal dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
        from PyQt5.QtCore import Qt

        self.processing_dialog = QDialog(self)
        self.processing_dialog.setWindowTitle(title)
        self.processing_dialog.setModal(True)
        self.processing_dialog.setFixedSize(400, 200)
        self.processing_dialog.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.processing_dialog.setStyleSheet("""
            QDialog {
                background-color: #111827;
                color: #f9fafb;
            }
            QLabel {
                color: #f9fafb;
            }
        """)

        layout = QVBoxLayout(self.processing_dialog)
        layout.setSpacing(24)
        layout.setContentsMargins(32, 32, 32, 32)

        # Title
        title_label = QLabel("🎬 " + title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: 600;
                color: #f9fafb;
                text-align: center;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Message
        self.processing_message = QLabel(message)
        self.processing_message.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #d1d5db;
                text-align: center;
            }
        """)
        self.processing_message.setAlignment(Qt.AlignCenter)
        self.processing_message.setWordWrap(True)
        layout.addWidget(self.processing_message)

        # Progress bar
        self.processing_progress = QProgressBar()
        self.processing_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 8px;
                background-color: #374151;
                text-align: center;
                color: white;
                font-weight: 500;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.processing_progress)

        # Time remaining label
        self.time_remaining_label = QLabel("Calculating time...")
        self.time_remaining_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #6b7280;
                text-align: center;
            }
        """)
        self.time_remaining_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_remaining_label)

        self.processing_dialog.show()

    def update_processing_modal(self, progress, message=None, time_remaining=None):
        """Update processing modal progress"""
        if hasattr(self, 'processing_dialog') and self.processing_dialog.isVisible():
            self.processing_progress.setValue(progress)

            if message:
                self.processing_message.setText(message)

            if time_remaining:
                self.time_remaining_label.setText(time_remaining)

            QApplication.processEvents()

    def hide_processing_modal(self):
        """Hide processing modal"""
        if hasattr(self, 'processing_dialog'):
            self.processing_dialog.close()
            delattr(self, 'processing_dialog')

    def toggle_fullscreen(self):
        """Toggle fullscreen mode for the video player"""
        print(f"🖥️  FULLSCREEN TOGGLE DEBUG:")
        print(f"  📊 Current fullscreen state: {self.is_fullscreen}")
        print(f"  📏 Current window size: {self.size()}")
        print(f"  📐 Current window geometry: {self.geometry()}")

        if not self.is_fullscreen:
            # Enter fullscreen
            print(f"  ▶️  Entering fullscreen mode...")
            self.is_fullscreen = True
            self.original_geometry = self.geometry()
            self.original_window_state = self.windowState()

            print(f"  💾 Saved original geometry: {self.original_geometry}")
            print(f"  💾 Saved original window state: {self.original_window_state}")

            # Hide all UI elements except video
            self.hide_ui_for_fullscreen()

            # Make the main window fullscreen
            print(f"  🖥️  Setting window to fullscreen...")
            self.setWindowState(Qt.WindowFullScreen)

            # Force update and check new size
            QApplication.processEvents()
            print(f"  📏 New fullscreen size: {self.size()}")
            print(f"  📐 New fullscreen geometry: {self.geometry()}")

            # Update fullscreen button text
            self.fullscreen_btn.setText("⛶")
            self.fullscreen_btn.setToolTip("Exit Fullscreen (ESC)")

        else:
            print(f"  ⏹️  Exiting fullscreen mode...")
            self.exit_fullscreen()

        print()

    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        print(f"  🚪 EXITING FULLSCREEN:")
        if self.is_fullscreen:
            print(f"    📊 Setting fullscreen state to False")
            self.is_fullscreen = False

            # Restore window state
            print(f"    🪟 Restoring window state: {self.original_window_state}")
            self.setWindowState(self.original_window_state)

            # Show all UI elements
            print(f"    👁️  Showing UI after fullscreen...")
            self.show_ui_after_fullscreen()

            # Update fullscreen button text
            self.fullscreen_btn.setText("⛶")
            self.fullscreen_btn.setToolTip("Toggle Fullscreen (F11)")

            print(f"    ✅ Fullscreen exit complete")
        else:
            print(f"    ⚠️  Not in fullscreen mode, nothing to exit")

    def hide_ui_for_fullscreen(self):
        """Hide UI elements for fullscreen mode"""
        print(f"  🫥 HIDING UI FOR FULLSCREEN:")

        # Store references to hidden widgets
        self.hidden_widgets = []

        # Find and hide the main content layout children except video splitter
        main_widget = self.centralWidget()
        if main_widget and main_widget.layout():
            print(f"    📦 Found main widget with layout")
            main_layout = main_widget.layout()
            for i in range(main_layout.count()):
                item = main_layout.itemAt(i)
                if item:
                    pass
                    if item.layout():
                        # This is the header layout - hide all its widgets
                        header_layout = item.layout()
                        print(f"    🎯 Hiding header layout widgets...")
                        for j in range(header_layout.count()):
                            header_item = header_layout.itemAt(j)
                            if header_item and header_item.widget():
                                widget = header_item.widget()
                                widget.hide()
                                self.hidden_widgets.append(widget)
                                print(f"      🫥 Hidden widget: {widget.__class__.__name__}")
                            elif header_item and header_item.layout():
                                # Hide widgets in nested layouts (like title layout)
                                nested_layout = header_item.layout()
                                for k in range(nested_layout.count()):
                                    nested_item = nested_layout.itemAt(k)
                                    if nested_item and nested_item.widget():
                                        widget = nested_item.widget()
                                        widget.hide()
                                        self.hidden_widgets.append(widget)
                                        print(f"      🫥 Hidden nested widget: {widget.__class__.__name__}")
                    elif item.layout() and hasattr(self, 'video_timeline_splitter'):
                        # This is the content layout - hide the sidebar
                        content_layout = item.layout()
                        if content_layout.count() > 0:
                            # Hide the left panel (sidebar)
                            left_panel_item = content_layout.itemAt(0)
                            if left_panel_item and left_panel_item.widget():
                                left_panel = left_panel_item.widget()
                                left_panel.hide()
                                self.hidden_widgets.append(left_panel)
                                print(f"      🫥 Hidden sidebar: {left_panel.__class__.__name__}")

        # Hide the timeline section from the splitter
        if hasattr(self, 'video_timeline_splitter'):
            print(f"    📺 Processing video timeline splitter...")
            print(f"      🔢 Splitter widget count: {self.video_timeline_splitter.count()}")

            # Hide timeline (second widget in splitter)
            if self.video_timeline_splitter.count() > 1:
                timeline_widget = self.video_timeline_splitter.widget(1)
                if timeline_widget:
                    timeline_widget.hide()
                    self.hidden_widgets.append(timeline_widget)
                    print(f"      🫥 Hidden timeline widget: {timeline_widget.__class__.__name__}")

            # Make the video section take full space
            print(f"      📏 Setting splitter sizes to [1, 0]...")
            self.video_timeline_splitter.setSizes([1, 0])

            # Ensure video frame label is visible and properly sized for fullscreen
            video_section = self.video_timeline_splitter.widget(0)  # This is the QFrame containing video
            if video_section:
                print(f"      🎬 Found video section: {video_section.__class__.__name__}")

                # The actual video player is self.video_player, which contains the video_frame_label
                if hasattr(self, 'video_player') and hasattr(self.video_player, 'video_frame_label'):
                    video_frame_label = self.video_player.video_frame_label
                    print(f"        🎬 Found video frame label in self.video_player")
                    print(f"        📏 Video section size: {video_section.size()}")

                    video_frame_label.show()

                    # CRITICAL FIX: For fullscreen, temporarily change to Expanding policy to fill screen
                    # Then immediately set fixed size to prevent auto-resizing during playback
                    fullscreen_size = self.size()
                    print(f"        🖥️  Setting fullscreen video size: {fullscreen_size}")

                    # Step 1: Temporarily set expanding policy to fill the screen
                    video_frame_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    # Step 2: Set geometry to fill entire window (relative to main window, not parent)
                    video_frame_label.setParent(self)  # Temporarily reparent to main window for fullscreen
                    video_frame_label.setGeometry(0, 0, fullscreen_size.width(), fullscreen_size.height())

                    # Step 3: Force layout update
                    QApplication.processEvents()

                    # Step 4: Now set back to Fixed policy with the fullscreen size to prevent auto-resizing
                    video_frame_label.setFixedSize(fullscreen_size)
                    video_frame_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


                    # Step 5: Ensure the video frame label is visible and on top
                    video_frame_label.show()
                    video_frame_label.raise_()
                    video_frame_label.repaint()

                    # Step 6: If there's a current frame, redisplay it at fullscreen size
                    if hasattr(video_frame_label, 'pixmap') and video_frame_label.pixmap():
                        current_pixmap = video_frame_label.pixmap()
                        if current_pixmap:
                            # Scale the current frame to fullscreen size
                            fullscreen_pixmap = current_pixmap.scaled(fullscreen_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            video_frame_label.setPixmap(fullscreen_pixmap)

                else:
                    print(f"      ❌ No video_player.video_frame_label found!")
            else:
                print(f"      ❌ No video section found!")
        else:
            print(f"    ❌ No video timeline splitter found!")

    def show_ui_after_fullscreen(self):
        """Show UI elements after exiting fullscreen"""
        print(f"  🪟 RESTORING UI AFTER FULLSCREEN:")

        # Show all previously hidden widgets
        if hasattr(self, 'hidden_widgets'):
            print(f"    👁️  Showing {len(self.hidden_widgets)} hidden widgets...")
            for widget in self.hidden_widgets:
                widget.show()
                print(f"      👁️  Showed widget: {widget.__class__.__name__}")
            delattr(self, 'hidden_widgets')

        # Restore the splitter sizes to normal
        if hasattr(self, 'video_timeline_splitter'):
            print(f"    📏 Restoring splitter sizes...")
            # Restore 60% video, 40% timeline split
            total_height = self.video_timeline_splitter.height()
            video_height = int(total_height * 0.6)
            timeline_height = total_height - video_height
            self.video_timeline_splitter.setSizes([video_height, timeline_height])
            print(f"      📏 Set splitter sizes: video={video_height}, timeline={timeline_height}")

            # CRITICAL FIX: Restore video frame label size and policy to normal windowed mode
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'video_frame_label'):
                video_frame_label = self.video_player.video_frame_label
                print(f"    🎬 Restoring video frame label...")

                # Step 1: Wait for layout to settle
                QApplication.processEvents()

                # Step 2: Restore the video frame label to its original parent (video_player)
                video_frame_label.setParent(self.video_player)
                print(f"      🔄 Reparented video frame label back to video_player")

                # Step 3: Wait for reparenting to complete
                QApplication.processEvents()

                # Step 4: Get the current video player size after splitter resize
                windowed_size = self.video_player.size()
                print(f"      📏 Video player windowed size: {windowed_size}")

                # Step 5: Restore the original size policy (Fixed to prevent auto-resizing)
                video_frame_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

                # Step 6: Set the label to match the video player size and position it correctly
                video_frame_label.setFixedSize(windowed_size)
                video_frame_label.setGeometry(0, 0, windowed_size.width(), windowed_size.height())
                print(f"      🏷️  Set video label size to: {windowed_size}")
                print(f"      📐 Set video label geometry to: {video_frame_label.geometry()}")

                # Step 7: Ensure the video frame label is visible and on top
                video_frame_label.show()
                video_frame_label.raise_()

                # Step 8: Force layout update
                if hasattr(self.video_player, 'layout') and self.video_player.layout():
                    self.video_player.layout().update()
                QApplication.processEvents()

                # Step 9: If there's a current frame, rescale it to windowed size
                if hasattr(video_frame_label, 'pixmap') and video_frame_label.pixmap():
                    current_pixmap = video_frame_label.pixmap()
                    if current_pixmap:
                        # Scale the current frame to windowed size
                        windowed_pixmap = current_pixmap.scaled(windowed_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        video_frame_label.setPixmap(windowed_pixmap)

                # Step 10: Final repaint
                video_frame_label.repaint()

            else:
                print(f"    ❌ No video_player.video_frame_label found for restoration!")
        else:
            print(f"    ❌ No video timeline splitter found for restoration!")

        print(f"  ✅ UI restoration complete")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        # Check for modifier combinations first
        if event.modifiers() == Qt.ControlModifier:
            pass
            if event.key() == Qt.Key_O:
                # Ctrl+O: Open file
                self.select_video()
                event.accept()
                return
            elif event.key() == Qt.Key_N:
                # Ctrl+N: New - Complete application reset
                self.new_project()
                event.accept()
                return

        # Check for individual key shortcuts
        if event.key() == Qt.Key_Space:
            # Spacebar: Play/Pause video
            if hasattr(self, 'video_player') and self.video_player:
                self.video_player.toggle_play_pause()
                event.accept()
                return
        elif event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        elif event.key() == Qt.Key_Escape and self.is_fullscreen:
            self.exit_fullscreen()
            event.accept()
            return

        # Call parent implementation for unhandled keys
        super().keyPressEvent(event)

    def new_project(self):
        """Create a new project with complete application reset"""
        # Show confirmation dialog
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "New Project",
            "Are you sure you want to start a new project?\n\nThis will clear all current data and reset the application to its initial state.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            pass
            try:
                # Perform complete application reset
                self.clear_previous_data()

                # Additional reset for new project
                self.video_path = None
                self.is_audio_only = False

                # Reset UI to initial state
                if hasattr(self, 'file_label'):
                    self.file_label.setText("No file selected")

                # Clear any remaining UI elements
                if hasattr(self, 'results_list'):
                    self.results_list.clear()

                # Reset buttons to initial state
                if hasattr(self, 'detect_btn'):
                    self.detect_btn.setEnabled(False)
                if hasattr(self, 'process_btn'):
                    self.process_btn.setEnabled(False)

                # Reset sliders to default values
                if hasattr(self, 'threshold_slider'):
                    self.threshold_slider.setValue(-40)
                if hasattr(self, 'duration_slider'):
                    self.duration_slider.setValue(1000)
                if hasattr(self, 'padding_slider'):
                    self.padding_slider.setValue(100)

                # Hide any dialogs or overlays
                if hasattr(self, 'loading_overlay') and self.loading_overlay:
                    self.loading_overlay.hide_loading()

                self.hide_processing_modal()

                # Force complete GUI update
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()
                self.update()
                self.repaint()


                # Show success message
                QMessageBox.information(
                    self,
                    "New Project",
                    "New project created successfully!\n\nThe application has been reset to its initial state."
                )

            except Exception as e:
                print(f"⚠️ Error creating new project: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create new project:\n{str(e)}"
                )

# Clean up any temporary files on exit
def cleanup_temp_files():
    temp_dir = tempfile.gettempdir()
    try:
        pass
        for filename in os.listdir(temp_dir):
            pass
            if filename.startswith("temp-audio-") and (filename.endswith(".m4a") or filename.endswith(".wav")):
                pass
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
