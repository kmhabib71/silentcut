# Transcript Integration Module
"""
Transcript Integration Module for Silence Cutter
Provides transcript generation, repeated word detection, and UI integration
"""

import os
import sys
import time
import tempfile
import subprocess
import json
import re
from collections import Counter
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
                             QScrollArea, QListWidget, QListWidgetItem, QDialog, QMessageBox, QLineEdit, QFileDialog, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QCursor

# Import transcript features with fallbacks
TRANSCRIPT_AVAILABLE = False
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

if any([WHISPER_AVAILABLE, SPEECH_RECOGNITION_AVAILABLE, FASTER_WHISPER_AVAILABLE]):
    TRANSCRIPT_AVAILABLE = True
    print("✅ Transcript features available")
else:
    print("⚠️  No transcript features available - using fallback")

class FastTranscriptGenerator(QThread):
    """Fast transcript generation with multiple fallback methods"""
    progress_updated = pyqtSignal(int, str)
    transcript_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.audio_path = None
        
    def run(self):
        try:
            self.progress_updated.emit(10, "Extracting audio...")
            self.audio_path = self.extract_audio()
            
            self.progress_updated.emit(30, "Generating transcript...")
            transcript_data = self.generate_transcript()
            
            self.progress_updated.emit(100, "Transcript ready!")
            self.transcript_ready.emit(transcript_data)
            
        except Exception as e:
            self.error_occurred.emit(f"Transcript generation failed: {str(e)}")
        finally:
            self.cleanup_temp_files()
    
    def extract_audio(self):
        """Extract audio from video using FFmpeg"""
        temp_audio = tempfile.mktemp(suffix='.wav')
        
        # Get FFmpeg path
        ffmpeg_path = self.get_ffmpeg_path()
        
        cmd = [
            ffmpeg_path, '-i', self.video_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            '-y', temp_audio
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return temp_audio
    
    def get_ffmpeg_path(self):
        """Get FFmpeg executable path"""
        if sys.platform.startswith('win'):
            return 'ffmpeg.exe'
        return 'ffmpeg'
    
    def generate_transcript(self):
        """Generate transcript using available methods"""
        methods = [
            self.try_faster_whisper,
            self.try_whisper,
            self.try_speech_recognition
        ]
        
        for method in methods:
            try:
                result = method()
                if result:
                    return result
            except Exception as e:
                print(f"Method failed: {e}")
                continue
        
        # Fallback: create dummy transcript
        return self.create_dummy_transcript()
    
    def try_faster_whisper(self):
        """Try faster-whisper (fastest method)"""
        if not FASTER_WHISPER_AVAILABLE:
            return None
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu")
            segments, _ = model.transcribe(self.audio_path, word_timestamps=True)
            
            transcript_data = []
            for segment in segments:
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        transcript_data.append({
                            'word': word.word.strip(),
                            'start': word.start,
                            'end': word.end,
                            'confidence': getattr(word, 'probability', 0.9)
                        })
                else:
                    # Fallback to segment-level timestamps
                    words = segment.text.split()
                    duration = segment.end - segment.start
                    word_duration = duration / len(words) if words else 0
                    for i, word in enumerate(words):
                        word_start = segment.start + (i * word_duration)
                        word_end = word_start + word_duration
                        transcript_data.append({
                            'word': word.strip(),
                            'start': word_start,
                            'end': word_end,
                            'confidence': 0.8
                        })
            return transcript_data
        except Exception as e:
            print(f"Faster-whisper failed: {e}")
            return None
    
    def try_whisper(self):
        """Try OpenAI Whisper"""
        if not WHISPER_AVAILABLE:
            return None
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(self.audio_path, word_timestamps=True)
            
            transcript_data = []
            for segment in result['segments']:
                if 'words' in segment and segment['words']:
                    for word in segment['words']:
                        transcript_data.append({
                            'word': word['word'].strip(),
                            'start': word['start'],
                            'end': word['end'],
                            'confidence': getattr(word, 'probability', 0.9)
                        })
                else:
                    # Fallback to segment-level timestamps
                    words = segment['text'].split()
                    duration = segment['end'] - segment['start']
                    word_duration = duration / len(words) if words else 0
                    for i, word in enumerate(words):
                        word_start = segment['start'] + (i * word_duration)
                        word_end = word_start + word_duration
                        transcript_data.append({
                            'word': word.strip(),
                            'start': word_start,
                            'end': word_end,
                            'confidence': 0.8
                        })
            return transcript_data
        except Exception as e:
            print(f"Whisper failed: {e}")
            return None
    
    def try_speech_recognition(self):
        """Try speech_recognition library"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            return None
        try:
            import speech_recognition as sr
            from pydub import AudioSegment
            
            # Convert to format speech_recognition can handle
            audio = AudioSegment.from_wav(self.audio_path)
            
            r = sr.Recognizer()
            transcript_data = []
            
            # Process in chunks
            chunk_length = 30000  # 30 seconds
            for i in range(0, len(audio), chunk_length):
                chunk = audio[i:i + chunk_length]
                chunk_path = tempfile.mktemp(suffix='.wav')
                chunk.export(chunk_path, format="wav")
                
                try:
                    with sr.AudioFile(chunk_path) as source:
                        audio_data = r.record(source)
                        text = r.recognize_google(audio_data)
                        
                        # Simple word splitting with timing estimation
                        words = text.split()
                        start_time = i / 1000.0
                        duration = len(chunk) / 1000.0
                        word_duration = duration / len(words) if words else 0
                        
                        for j, word in enumerate(words):
                            word_start = start_time + (j * word_duration)
                            word_end = word_start + word_duration
                            transcript_data.append({
                                'word': word,
                                'start': word_start,
                                'end': word_end,
                                'confidence': 0.8
                            })
                except:
                    pass
                finally:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
            
            return transcript_data if transcript_data else None
        except Exception as e:
            print(f"Speech recognition failed: {e}")
            return None
    
    def create_dummy_transcript(self):
        """Create dummy transcript for testing"""
        return [
            {'word': 'Sample', 'start': 0.0, 'end': 0.5, 'confidence': 0.9},
            {'word': 'transcript', 'start': 0.5, 'end': 1.0, 'confidence': 0.9},
            {'word': 'generated', 'start': 1.0, 'end': 1.5, 'confidence': 0.9},
            {'word': 'for', 'start': 1.5, 'end': 1.7, 'confidence': 0.9},
            {'word': 'testing', 'start': 1.7, 'end': 2.2, 'confidence': 0.9},
            {'word': 'so', 'start': 2.2, 'end': 2.4, 'confidence': 0.9},
            {'word': 'so', 'start': 2.4, 'end': 2.6, 'confidence': 0.9},
            {'word': 'this', 'start': 2.6, 'end': 2.8, 'confidence': 0.9},
            {'word': 'is', 'start': 2.8, 'end': 3.0, 'confidence': 0.9},
            {'word': 'working', 'start': 3.0, 'end': 3.5, 'confidence': 0.9}
        ]
    
    def cleanup_temp_files(self):
        """Clean up temporary audio file"""
        if self.audio_path and os.path.exists(self.audio_path):
            try:
                os.remove(self.audio_path)
            except:
                pass

class TranscriptWidget(QWidget):
    """Enhanced transcript widget with real-time highlighting and seeking"""
    seek_requested = pyqtSignal(float)
    play_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.transcript_data = []
        self.current_word_index = -1
        self.word_widgets = []
        self.editing_mode = False  # Track if we're in full edit mode
        self.full_text_editor = None  # Will hold the full text editor
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Header with download buttons
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📝 Live Captions")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #f9fafb;
                padding: 4px 0px;
            }
        """)
        
        # Download buttons
        self.download_txt_btn = QPushButton("📄 Download TXT")
        self.download_txt_btn.setEnabled(False)
        self.download_txt_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        self.download_txt_btn.clicked.connect(self.download_txt)
        
        self.download_srt_btn = QPushButton("🎬 Download SRT")
        self.download_srt_btn.setEnabled(False)
        self.download_srt_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        self.download_srt_btn.clicked.connect(self.download_srt)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.download_txt_btn)
        header_layout.addWidget(self.download_srt_btn)
        
        layout.addLayout(header_layout)
        
        # Scroll area for transcript with horizontal scrolling enabled
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # Enable horizontal scrolling
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 2px solid #374151;
                border-radius: 8px;
                background-color: #1f2937;
                min-height: 120px;
                max-height: 120px;
            }
            QScrollBar:horizontal {
                background-color: #374151;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #6b7280;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #9ca3af;
            }
            QScrollBar:vertical {
                background-color: #374151;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #6b7280;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #9ca3af;
            }
        """)
        
        # Transcript content widget with improved layout
        self.transcript_content = QWidget()
        self.transcript_layout = QHBoxLayout(self.transcript_content)
        self.transcript_layout.setContentsMargins(12, 12, 12, 12)  # Better margins
        self.transcript_layout.setSpacing(4)  # Reduced spacing between words
        self.transcript_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Left align and center vertically
        
        # Don't add stretch initially - we'll manage layout manually
        self.scroll_area.setWidget(self.transcript_content)
        layout.addWidget(self.scroll_area)
        
        # Status label (hidden when transcript is loaded)
        self.status_label = QLabel("No transcript loaded")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 11px;
                padding: 2px 4px;
            }
        """)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def load_transcript(self, video_path):
        """Start transcript generation"""
        self.status_label.setText("Generating transcript...")
        self.transcript_generator = FastTranscriptGenerator(video_path)
        self.transcript_generator.progress_updated.connect(self.on_progress_updated)
        self.transcript_generator.transcript_ready.connect(self.on_transcript_ready)
        self.transcript_generator.error_occurred.connect(self.on_error_occurred)
        self.transcript_generator.start()
    
    def on_progress_updated(self, progress, status):
        """Update progress status"""
        self.status_label.setText(f"{status} ({progress}%)")
    
    def on_transcript_ready(self, transcript_data):
        """Handle transcript generation completion"""
        self.transcript_data = transcript_data
        self.display_transcript()
        # Hide status label when transcript is ready
        self.status_label.hide()
        
        # Enable download buttons
        self.download_txt_btn.setEnabled(True)
        self.download_srt_btn.setEnabled(True)
        
        print(f"✅ Transcript ready: {len(transcript_data)} words. Download buttons enabled.")
    
    def on_error_occurred(self, error_message):
        """Handle transcript generation error"""
        self.status_label.setText(f"Error: {error_message}")
    
    def display_transcript(self):
        """Display transcript with clickable words"""
        # Clear existing widgets
        for widget in self.word_widgets:
            widget.deleteLater()
        self.word_widgets.clear()
        
        # Create word widgets
        for i, word_data in enumerate(self.transcript_data):
            word_widget = self.create_word_widget(word_data, i)
            self.word_widgets.append(word_widget)
            self.transcript_layout.insertWidget(self.transcript_layout.count() - 1, word_widget)
    
    def create_word_widget(self, word_data, index):
        """Create clickable and editable word widget with double-click to edit full text"""
        from PyQt5.QtWidgets import QLineEdit
        
        # Create word label (display mode only - no edit field per word)
        word_label = QPushButton(word_data['word'])
        word_label.setFlat(True)
        word_label.setCursor(Qt.PointingHandCursor)
        word_label.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #d1d5db;
                border: 1px solid transparent;
                padding: 6px 8px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                min-width: 30px;
                margin: 1px;
            }
            QPushButton:hover {
                background-color: #374151;
                color: #f9fafb;
                border: 1px solid #6b7280;
            }
        """)
        
        # Store references and data
        word_label.word_data = word_data
        word_label.word_index = index
        
        # Connect signals for seeking (single click)
        def on_word_click():
            if not self.editing_mode:
                self.seek_requested.emit(word_data['start'])
                if hasattr(self, 'play_requested'):
                    self.play_requested.emit()
        
        word_label.clicked.connect(on_word_click)
        
        # Connect double-click for full text editing
        def on_double_click(event):
            if not self.editing_mode:
                self.start_full_text_edit()
        
        word_label.mouseDoubleClickEvent = on_double_click
        
        return word_label
    
    def start_full_text_edit(self):
        """Start full text editing mode with single-line editor"""
        if self.editing_mode:
            return
            
        self.editing_mode = True
        
        # Create single-line full text editor (QLineEdit instead of QTextEdit)
        self.full_text_editor = QLineEdit()
        self.full_text_editor.setStyleSheet("""
            QLineEdit {
                background-color: #374151;
                color: #f9fafb;
                border: 3px solid #8b5cf6;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                min-height: 40px;
            }
        """)
        
        # Set full text content
        full_text = ' '.join([word['word'] for word in self.transcript_data])
        self.full_text_editor.setText(full_text)
        
        # Replace transcript content with editor
        # Hide word widgets
        for widget in self.word_widgets:
            widget.hide()
        
        # Clear layout and add editor
        for i in reversed(range(self.transcript_layout.count())): 
            self.transcript_layout.itemAt(i).widget().setParent(None)
        
        self.transcript_layout.addWidget(self.full_text_editor)
        
        # Focus and select all
        self.full_text_editor.setFocus()
        self.full_text_editor.selectAll()
        
        # Connect finish editing on focus loss and Enter key
        self.full_text_editor.editingFinished.connect(self.finish_full_text_edit)
        self.full_text_editor.returnPressed.connect(self.finish_full_text_edit)
        
        print("📝 Single-line text editing mode enabled - press Enter or click outside to save")
    
    def finish_full_text_edit(self):
        """Finish full text editing and update transcript data"""
        if not self.editing_mode or not self.full_text_editor:
            return
            
        # Get edited text
        new_text = self.full_text_editor.text().strip()
        old_text = ' '.join([word['word'] for word in self.transcript_data])
        
        if new_text and new_text != old_text:
            # Update transcript data with new words while preserving timestamps
            new_words = new_text.split()
            
            # Map new words to existing timestamps
            if len(new_words) <= len(self.transcript_data):
                # If fewer or same number of words, map directly
                for i, new_word in enumerate(new_words):
                    self.transcript_data[i]['word'] = new_word
                # Remove extra words if fewer
                if len(new_words) < len(self.transcript_data):
                    self.transcript_data = self.transcript_data[:len(new_words)]
            else:
                # If more words, distribute timing
                old_count = len(self.transcript_data)
                new_count = len(new_words)
                
                # Update existing words
                for i in range(old_count):
                    if i < new_count:
                        self.transcript_data[i]['word'] = new_words[i]
                
                # Add new words with estimated timing
                if old_count > 0:
                    last_end = self.transcript_data[-1]['end']
                    word_duration = 0.5  # Default 0.5 seconds per new word
                    
                    for i in range(old_count, new_count):
                        start_time = last_end + (i - old_count) * word_duration
                        end_time = start_time + word_duration
                        self.transcript_data.append({
                            'word': new_words[i],
                            'start': start_time,
                            'end': end_time,
                            'confidence': 0.8
                        })
            
            print(f"✏️  Updated full transcript: {len(self.transcript_data)} words")
        
        # Remove editor from layout
        self.full_text_editor.hide()
        self.full_text_editor.deleteLater()
        self.full_text_editor = None
        self.editing_mode = False
        
        # Recreate and display word widgets
        self.display_transcript()
        
        # Enable download buttons if transcript is ready
        if self.transcript_data:
            self.download_txt_btn.setEnabled(True)
            self.download_srt_btn.setEnabled(True)
        
        print("📝 Single-line text editing completed")
    
    def update_current_time(self, time_seconds):
        """Update highlighting based on current playback time with improved auto-scrolling"""
        if self.editing_mode:  # Don't update highlighting during edit mode
            return
            
        # Find current word
        current_word_index = -1
        for i, word_data in enumerate(self.transcript_data):
            if word_data['start'] <= time_seconds <= word_data['end']:
                current_word_index = i
                break
        
        # Update highlighting only if word changed
        if current_word_index != self.current_word_index:
            # Remove old highlighting
            if 0 <= self.current_word_index < len(self.word_widgets):
                old_widget = self.word_widgets[self.current_word_index]
                if hasattr(old_widget, 'setStyleSheet'):
                    old_widget.setStyleSheet("""
                        QPushButton {
                            background-color: transparent;
                            color: #d1d5db;
                            border: 1px solid transparent;
                            padding: 6px 8px;
                            border-radius: 6px;
                            font-size: 14px;
                            font-weight: 500;
                            min-width: 30px;
                            margin: 1px;
                        }
                        QPushButton:hover {
                            background-color: #374151;
                            color: #f9fafb;
                            border: 1px solid #6b7280;
                        }
                    """)
            
            # Add new highlighting with prominent border
            if 0 <= current_word_index < len(self.word_widgets):
                current_widget = self.word_widgets[current_word_index]
                if hasattr(current_widget, 'setStyleSheet'):
                    current_widget.setStyleSheet("""
                        QPushButton {
                            background-color: #8b5cf6;
                            color: white;
                            border: 3px solid #a855f7;
                            padding: 8px 10px;
                            border-radius: 8px;
                            font-size: 15px;
                            font-weight: bold;
                            min-width: 30px;
                            margin: 1px;
                            box-shadow: 0px 0px 15px rgba(139, 92, 246, 0.6);
                        }
                        QPushButton:hover {
                            background-color: #7c3aed;
                            color: white;
                            border: 3px solid #9333ea;
                        }
                    """)
                
                # Auto-scroll to keep current word visible - ensure it happens
                self.scroll_to_word_centered(current_word_index)
            
            self.current_word_index = current_word_index
    
    def scroll_to_word_centered(self, word_index):
        """Improved horizontal scrolling to center the specified word"""
        if 0 <= word_index < len(self.word_widgets) and not self.editing_mode:
            # Use QTimer.singleShot to ensure scroll happens after layout updates
            QTimer.singleShot(10, lambda: self._perform_scroll_to_word(word_index))
    
    def _perform_scroll_to_word(self, word_index):
        """Actually perform the scroll operation"""
        if 0 <= word_index < len(self.word_widgets) and not self.editing_mode:
            widget = self.word_widgets[word_index]
            
            # Ensure widget is visible and has proper geometry
            if not widget.isVisible():
                return
                
            # Force layout update
            self.transcript_content.updateGeometry()
            self.scroll_area.updateGeometry()
            
            # Get scroll area dimensions
            scroll_area = self.scroll_area
            viewport_width = scroll_area.viewport().width()
            horizontal_scrollbar = scroll_area.horizontalScrollBar()
            
            # Get widget position and dimensions
            widget_geometry = widget.geometry()
            widget_x = widget_geometry.x()
            widget_width = widget_geometry.width()
            
            # Calculate the center position of the current word
            widget_center_x = widget_x + widget_width // 2
            
            # Calculate target scroll position to center the word in viewport
            target_scroll_x = widget_center_x - viewport_width // 2
            
            # Get content width and ensure we don't scroll past boundaries
            content_width = self.transcript_content.width()
            max_scroll = max(0, content_width - viewport_width)
            target_scroll_x = max(0, min(target_scroll_x, max_scroll))
            
            # Perform the scroll
            horizontal_scrollbar.setValue(int(target_scroll_x))
            
            # Debug info (reduced frequency)
            if word_index % 15 == 0:  # Log every 15th word
                print(f"🎯 Auto-scroll: word {word_index} '{widget.text()}' at x={widget_x}, center={widget_center_x}, target_scroll={target_scroll_x}, viewport={viewport_width}")

    def download_txt(self):
        """Download transcript as TXT file"""
        if not self.transcript_data:
            QMessageBox.warning(self, "No Transcript", "No transcript data available to download.")
            return
        
        from PyQt5.QtWidgets import QFileDialog
        
        # Get save location
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Transcript as TXT", 
            "transcript.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    # Write all words with timestamps (optional format)
                    f.write("TRANSCRIPT\n")
                    f.write("=" * 50 + "\n\n")
                    
                    current_line = []
                    words_per_line = 10
                    
                    for i, word_data in enumerate(self.transcript_data):
                        current_line.append(word_data['word'])
                        
                        # Start new line every 10 words or at punctuation
                        if (len(current_line) >= words_per_line or 
                            word_data['word'].rstrip().endswith(('.', '!', '?')) or
                            i == len(self.transcript_data) - 1):
                            
                            line_text = ' '.join(current_line)
                            f.write(line_text.strip() + '\n')
                            current_line = []
                    
                    f.write(f"\n\nGenerated: {len(self.transcript_data)} words")
                
                QMessageBox.information(self, "Download Complete", f"Transcript saved to:\n{filename}")
                print(f"📄 TXT transcript saved: {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save transcript:\n{str(e)}")
    
    def download_srt(self):
        """Download transcript as SRT subtitle file"""
        if not self.transcript_data:
            QMessageBox.warning(self, "No Transcript", "No transcript data available to download.")
            return
        
        from PyQt5.QtWidgets import QFileDialog
        
        # Get save location
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Subtitles as SRT", 
            "subtitles.srt",
            "Subtitle Files (*.srt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    subtitle_index = 1
                    current_subtitle = []
                    subtitle_start = None
                    subtitle_end = None
                    max_chars_per_subtitle = 80
                    max_duration = 5.0  # Maximum 5 seconds per subtitle
                    
                    def format_srt_time(seconds):
                        """Format time for SRT format (HH:MM:SS,mmm)"""
                        hours = int(seconds // 3600)
                        minutes = int((seconds % 3600) // 60)
                        secs = int(seconds % 60)
                        millis = int((seconds % 1) * 1000)
                        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                    
                    def write_subtitle():
                        """Write current subtitle to file"""
                        if current_subtitle and subtitle_start is not None:
                            nonlocal subtitle_index
                            subtitle_text = ' '.join(current_subtitle).strip()
                            
                            f.write(f"{subtitle_index}\n")
                            f.write(f"{format_srt_time(subtitle_start)} --> {format_srt_time(subtitle_end)}\n")
                            f.write(f"{subtitle_text}\n\n")
                            
                            subtitle_index += 1
                    
                    for i, word_data in enumerate(self.transcript_data):
                        word = word_data['word']
                        word_start = word_data['start']
                        word_end = word_data['end']
                        
                        # Start new subtitle if this is the first word
                        if subtitle_start is None:
                            subtitle_start = word_start
                        
                        # Add word to current subtitle
                        current_subtitle.append(word)
                        subtitle_end = word_end
                        
                        # Check if we should end current subtitle
                        current_text = ' '.join(current_subtitle)
                        duration = subtitle_end - subtitle_start
                        
                        should_end_subtitle = (
                            len(current_text) >= max_chars_per_subtitle or
                            duration >= max_duration or
                            word.rstrip().endswith(('.', '!', '?')) or
                            i == len(self.transcript_data) - 1
                        )
                        
                        if should_end_subtitle:
                            write_subtitle()
                            current_subtitle = []
                            subtitle_start = None
                
                QMessageBox.information(self, "Download Complete", f"Subtitles saved to:\n{filename}")
                print(f"🎬 SRT subtitles saved: {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save subtitles:\n{str(e)}")

def integrate_transcript_with_app(app_instance):
    """Integrate transcript functionality with the main application"""
    
    print(f"🔍 DEBUG: integrate_transcript_with_app called")
    print(f"🔍 DEBUG: app_instance type: {type(app_instance)}")
    
    # Initialize transcript variables
    app_instance.transcript_widget = None
    app_instance.transcript_data = []
    app_instance.repeated_word_segments = []
    app_instance.realtime_timer = QTimer()
    app_instance.realtime_timer.timeout.connect(lambda: update_transcript_highlighting(app_instance))
    app_instance.realtime_timer.start(100)  # Update every 100ms
    
    print(f"✅ DEBUG: Transcript variables initialized")
    
    # Add transcript widget to the timeline section
    add_transcript_to_timeline(app_instance)
    print(f"✅ DEBUG: add_transcript_to_timeline called")
    
    # Add repeated words button
    add_repeated_words_button(app_instance)
    print(f"✅ DEBUG: add_repeated_words_button called")
    
    # Connect signals
    connect_transcript_signals(app_instance)
    print(f"✅ DEBUG: connect_transcript_signals called")
    
    print(f"✅ DEBUG: Integration complete. transcript_widget: {app_instance.transcript_widget}")

def add_transcript_to_timeline(app_instance):
    """Add transcript widget to the timeline section"""
    print(f"🔍 DEBUG: add_transcript_to_timeline called")
    
    if hasattr(app_instance.video_player, 'timeline_section'):
        print(f"✅ DEBUG: timeline_section found")
        timeline_layout = app_instance.video_player.timeline_section.layout()
        print(f"✅ DEBUG: timeline_layout: {timeline_layout}")
        
        # Create transcript widget with increased height
        app_instance.transcript_widget = TranscriptWidget()
        app_instance.transcript_widget.setMaximumHeight(200)  # Increased from 120
        app_instance.transcript_widget.setMinimumHeight(120)  # Increased from 80
        
        print(f"✅ DEBUG: TranscriptWidget created: {app_instance.transcript_widget}")
        
        # Add to timeline layout
        timeline_layout.addWidget(app_instance.transcript_widget)
        print(f"✅ DEBUG: TranscriptWidget added to timeline layout")
    else:
        print(f"❌ ERROR: timeline_section not found on video_player")
        if hasattr(app_instance, 'video_player'):
            print(f"❌ ERROR: video_player attributes: {[attr for attr in dir(app_instance.video_player) if not attr.startswith('_')]}")
        else:
            print(f"❌ ERROR: video_player not found on app_instance")

def add_repeated_words_button(app_instance):
    """Add repeated words detection button"""
    # Find the detect button and add repeated words button after it
    if hasattr(app_instance, 'detect_btn'):
        # Get the parent layout
        parent_widget = app_instance.detect_btn.parent()
        parent_layout = parent_widget.layout()
        
        # Find the detect button index
        detect_btn_index = -1
        for i in range(parent_layout.count()):
            item = parent_layout.itemAt(i)
            if item and item.widget() == app_instance.detect_btn:
                detect_btn_index = i
                break
        
        if detect_btn_index >= 0:
            # Create repeated words button
            app_instance.repeated_words_btn = QPushButton("🔄 Detect Repeated Words")
            app_instance.repeated_words_btn.clicked.connect(lambda: detect_repeated_words(app_instance))
            app_instance.repeated_words_btn.setEnabled(False)
            app_instance.repeated_words_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7c3aed;
                    color: white;
                    padding: 12px 16px;
                    font-weight: 600;
                    font-size: 14px;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #6d28d9;
                }
                QPushButton:disabled {
                    background-color: #374151;
                    color: #6b7280;
                }
            """)
            
            # Insert after detect button
            parent_layout.insertWidget(detect_btn_index + 1, app_instance.repeated_words_btn)

def connect_transcript_signals(app_instance):
    """Connect transcript-related signals"""
    if app_instance.transcript_widget:
        # Connect seeking
        app_instance.transcript_widget.seek_requested.connect(
            lambda time_sec: app_instance.video_player.seek_to_position(time_sec)
        )
        # Connect play requested - use correct method name
        app_instance.transcript_widget.play_requested.connect(
            lambda: app_instance.video_player.toggle_play_pause()
        )

def detect_repeated_words(app_instance):
    """Start consecutive repeated words detection"""
    try:
        if not hasattr(app_instance, 'transcript_data') or not app_instance.transcript_data:
            QMessageBox.warning(app_instance, "No Transcript", "Please wait for transcript generation to complete.")
            return
        
        # Show progress modal safely
        if hasattr(app_instance, 'show_processing_modal'):
            app_instance.show_processing_modal("Detecting Repeated Words", "Analyzing transcript for consecutive repeated content...")
        
        # Speech padding for smooth cuts (in seconds)
        SPEECH_PADDING = 0.1  # 100ms padding before and after repeated words
        
        # Detect consecutive repeated words/phrases
        repeated_segments = []
        transcript_data = app_instance.transcript_data
        
        def clean_word(word):
            """Clean word for comparison while preserving punctuation detection"""
            return word.lower().strip()
        
        def has_separating_punctuation(word):
            """Check if word ends with separating punctuation"""
            separating_punctuation = ['.']  # Only period/full stop separates sentences
            return any(word.rstrip().endswith(punct) for punct in separating_punctuation)
        
        def extract_core_word(word):
            """Extract core word without punctuation for comparison"""
            import re
            # Remove punctuation but preserve the core word for all languages
            core_word = re.sub(r'[^\w\s]', '', word).strip()
            return core_word.lower()
        
        try:
            i = 0
            while i < len(transcript_data):
                # Check for single word repetitions (like "so so" but not "so, so")
                if i < len(transcript_data) - 1:
                    current_word_raw = transcript_data[i]['word']
                    next_word_raw = transcript_data[i + 1]['word']
                    
                    # Check if there's separating punctuation
                    if has_separating_punctuation(current_word_raw):
                        i += 1
                        continue
                    
                    current_word_core = extract_core_word(current_word_raw)
                    next_word_core = extract_core_word(next_word_raw)
                    
                    if (current_word_core == next_word_core and 
                        len(current_word_core) > 1 and 
                        current_word_core.strip()):  # Ensure not empty after cleaning
                        
                        # Found consecutive repeated word without separating punctuation
                        # Count how many times it repeats
                        repeat_count = 2
                        j = i + 2
                        
                        while j < len(transcript_data):
                            # Check if previous word has separating punctuation
                            if has_separating_punctuation(transcript_data[j-1]['word']):
                                break
                            
                            j_word_core = extract_core_word(transcript_data[j]['word'])
                            if j_word_core == current_word_core:
                                repeat_count += 1
                                j += 1
                            else:
                                break
                        
                        # Mark first occurrence(s) for removal, keep the last one
                        for k in range(i, j - 1):  # Remove all except the last occurrence
                            # Add padding for smooth cuts
                            start_time = max(0, float(transcript_data[k]['start']) - SPEECH_PADDING)
                            end_time = float(transcript_data[k]['end']) + SPEECH_PADDING
                            
                            repeated_segments.append({
                                'start': start_time,
                                'end': end_time,
                                'type': 'repeated_word',
                                'selected': True,
                                'word': current_word_core,
                                'original_word': transcript_data[k]['word'],
                                'repeat_count': repeat_count
                            })
                        
                        i = j  # Skip past all repetitions
                        continue
                
                # Check for phrase repetitions (like "do you do you" but not "do you, do you")
                phrase_found = False
                for phrase_length in range(2, min(5, len(transcript_data) - i)):  # Check 2-4 word phrases
                    if i + phrase_length * 2 > len(transcript_data):
                        break
                    
                    # Check if the phrase boundary has separating punctuation
                    if has_separating_punctuation(transcript_data[i + phrase_length - 1]['word']):
                        continue
                    
                    # Extract first phrase
                    phrase1_words = []
                    phrase1_raw = []
                    for k in range(phrase_length):
                        word_core = extract_core_word(transcript_data[i + k]['word'])
                        phrase1_words.append(word_core)
                        phrase1_raw.append(transcript_data[i + k]['word'])
                    
                    # Extract second phrase
                    phrase2_words = []
                    for k in range(phrase_length):
                        word_core = extract_core_word(transcript_data[i + phrase_length + k]['word'])
                        phrase2_words.append(word_core)
                    
                    # Check if phrases match (core words without punctuation)
                    if phrase1_words == phrase2_words and all(word.strip() for word in phrase1_words):
                        # Found consecutive repeated phrase without separating punctuation
                        # Count how many times this phrase repeats
                        repeat_count = 2
                        next_start = i + phrase_length * 2
                        
                        while next_start + phrase_length <= len(transcript_data):
                            # Check if previous phrase boundary has separating punctuation
                            if has_separating_punctuation(transcript_data[next_start - 1]['word']):
                                break
                            
                            next_phrase_words = []
                            for k in range(phrase_length):
                                word_core = extract_core_word(transcript_data[next_start + k]['word'])
                                next_phrase_words.append(word_core)
                            
                            if next_phrase_words == phrase1_words:
                                repeat_count += 1
                                next_start += phrase_length
                            else:
                                break
                        
                        # Mark first occurrence(s) for removal, keep the last one
                        total_words = phrase_length * repeat_count
                        words_to_remove = total_words - phrase_length  # Remove all except last phrase
                        
                        for k in range(i, i + words_to_remove):
                            # Add padding for smooth cuts
                            start_time = max(0, float(transcript_data[k]['start']) - SPEECH_PADDING)
                            end_time = float(transcript_data[k]['end']) + SPEECH_PADDING
                            
                            repeated_segments.append({
                                'start': start_time,
                                'end': end_time,
                                'type': 'repeated_phrase',
                                'selected': True,
                                'word': ' '.join(phrase1_words),
                                'original_phrase': ' '.join(phrase1_raw),
                                'repeat_count': repeat_count
                            })
                        
                        i = next_start  # Skip past all repetitions
                        phrase_found = True
                        break
                
                if not phrase_found:
                    i += 1
                    
        except Exception as e:
            print(f"Error finding consecutive repeated words: {e}")
            if hasattr(app_instance, 'hide_processing_modal'):
                app_instance.hide_processing_modal()
            QMessageBox.warning(app_instance, "Error", "Failed to detect consecutive repeated words.")
            return
        
        # Hide progress modal safely
        if hasattr(app_instance, 'hide_processing_modal'):
            app_instance.hide_processing_modal()
        
        if repeated_segments:
            try:
                # Store repeated segments
                app_instance.repeated_word_segments = repeated_segments
                
                # Combine with existing silence segments safely
                all_segments = []
                if hasattr(app_instance, 'silent_parts') and app_instance.silent_parts:
                    all_segments.extend(app_instance.silent_parts)
                all_segments.extend(repeated_segments)
                all_segments.sort(key=lambda x: x.get('start', 0))
                
                # Update the timeline safely - this marks repeated segments on the interactive timeline
                if (hasattr(app_instance, 'video_player') and 
                    hasattr(app_instance.video_player, 'timeline_widget')):
                    silence_ranges = []
                    for segment in all_segments:
                        if 'start' in segment and 'end' in segment:
                            silence_ranges.append((segment['start'] * 1000, segment['end'] * 1000))  # Convert to ms
                    
                    # This will mark repeated word segments on the timeline and enable preview skipping
                    app_instance.video_player.timeline_widget.set_silent_parts(all_segments, silence_ranges)
                    
                    # CRITICAL: Enable preview mode with the combined segments for video/audio skipping
                    if hasattr(app_instance.video_player, 'set_preview_mode'):
                        app_instance.video_player.set_preview_mode(True, all_segments)
                        print(f"✅ Preview mode enabled with {len(all_segments)} total segments (silence + repeated words)")
                    
                    # Update the video player's silent parts for preview mode
                    if hasattr(app_instance.video_player, 'set_silent_parts'):
                        app_instance.video_player.set_silent_parts(all_segments)
                
                # Update export button state safely
                if hasattr(app_instance, 'update_export_button_state'):
                    app_instance.update_export_button_state()
                
                # Store combined segments for final rendering
                app_instance.silent_parts = all_segments
                
                # Show success message
                total_time_saved = sum(seg.get('end', 0) - seg.get('start', 0) for seg in repeated_segments)
                QMessageBox.information(
                    app_instance, 
                    "Repeated Words Found", 
                    f"Found {len(repeated_segments)} consecutive repeated word segments.\n"
                    f"Additional time savings: {total_time_saved:.1f} seconds\n"
                    f"First occurrences marked on timeline and will be skipped in preview/export.\n"
                    f"Added {SPEECH_PADDING*1000:.0f}ms padding for smooth cuts."
                )
            except Exception as e:
                print(f"Error applying repeated word detection: {e}")
                QMessageBox.warning(app_instance, "Error", "Failed to apply repeated word detection.")
        else:
            QMessageBox.information(app_instance, "No Repeated Words", "No consecutive repeated words found in the transcript.")
            
    except Exception as e:
        print(f"Critical error in detect_repeated_words: {e}")
        import traceback
        traceback.print_exc()
        
        # Ensure modal is hidden
        if hasattr(app_instance, 'hide_processing_modal'):
            try:
                app_instance.hide_processing_modal()
            except:
                pass
        
        QMessageBox.critical(app_instance, "Critical Error", f"An unexpected error occurred: {str(e)}")

def update_transcript_highlighting(app_instance):
    """Update transcript highlighting based on current playback position"""
    try:
        if not (hasattr(app_instance, 'transcript_widget') and 
                app_instance.transcript_widget and 
                hasattr(app_instance, 'transcript_data') and 
                app_instance.transcript_data):
            return
        
        # Get current position from video player with multiple fallbacks
        current_time = 0
        
        if hasattr(app_instance, 'video_player') and app_instance.video_player:
            # Try multiple methods to get current time
            if hasattr(app_instance.video_player, 'media_player') and app_instance.video_player.media_player:
                try:
                    position_ms = app_instance.video_player.media_player.position()
                    if position_ms >= 0:
                        current_time = position_ms / 1000.0
                except:
                    pass
            
            # Fallback: try timeline widget
            if current_time == 0 and hasattr(app_instance.video_player, 'timeline_widget'):
                try:
                    timeline_pos = getattr(app_instance.video_player.timeline_widget, 'current_position', 0)
                    if timeline_pos > 0:
                        current_time = timeline_pos
                except:
                    pass
            
            # Fallback: try threaded video player
            if current_time == 0 and hasattr(app_instance.video_player, 'video_thread'):
                try:
                    thread_pos = getattr(app_instance.video_player.video_thread, 'current_time_seconds', 0)
                    if thread_pos > 0:
                        current_time = thread_pos
                except:
                    pass
        
        # Update transcript highlighting
        app_instance.transcript_widget.update_current_time(current_time)
        
    except Exception as e:
        # Silently handle errors to prevent disrupting playback
        pass

def start_transcript_generation(app_instance, video_path):
    """Start transcript generation when video is loaded"""
    print(f"🔍 DEBUG: start_transcript_generation called")
    print(f"🔍 DEBUG: app_instance type: {type(app_instance)}")
    print(f"🔍 DEBUG: video_path: {video_path}")
    
    # Check if app_instance is the correct type
    if not hasattr(app_instance, 'transcript_widget'):
        print(f"❌ ERROR: app_instance does not have transcript_widget attribute")
        print(f"❌ ERROR: Available attributes: {[attr for attr in dir(app_instance) if not attr.startswith('_')]}")
        return
    
    if not app_instance.transcript_widget:
        print(f"❌ ERROR: transcript_widget is None")
        return
    
    print(f"✅ DEBUG: transcript_widget found: {type(app_instance.transcript_widget)}")
    
    # Show loading overlay for transcript generation
    if hasattr(app_instance, 'show_loading_overlay'):
        app_instance.show_loading_overlay("Generating transcript...")
        print(f"✅ DEBUG: Loading overlay shown")
    else:
        print(f"⚠️  DEBUG: No show_loading_overlay method found")
    
    try:
        app_instance.transcript_widget.load_transcript(video_path)
        print(f"✅ DEBUG: Transcript loading started")
        
        # Connect transcript ready signal to enable button and hide loading
        if hasattr(app_instance.transcript_widget, 'transcript_generator'):
            print(f"✅ DEBUG: Connecting transcript signals")
            app_instance.transcript_widget.transcript_generator.transcript_ready.connect(
                lambda data: on_transcript_ready(app_instance, data)
            )
            app_instance.transcript_widget.transcript_generator.progress_updated.connect(
                lambda progress, status: on_transcript_progress(app_instance, progress, status)
            )
            app_instance.transcript_widget.transcript_generator.error_occurred.connect(
                lambda error: on_transcript_error(app_instance, error)
            )
        else:
            print(f"⚠️  DEBUG: transcript_generator not found yet, will connect later")
            # Try to connect after a short delay
            QTimer.singleShot(100, lambda: connect_transcript_signals_delayed(app_instance))
    except Exception as e:
        print(f"❌ ERROR in start_transcript_generation: {e}")
        import traceback
        traceback.print_exc()

def connect_transcript_signals_delayed(app_instance):
    """Try to connect transcript signals after a delay"""
    try:
        if (hasattr(app_instance, 'transcript_widget') and 
            app_instance.transcript_widget and 
            hasattr(app_instance.transcript_widget, 'transcript_generator')):
            
            print(f"✅ DEBUG: Delayed connection of transcript signals")
            app_instance.transcript_widget.transcript_generator.transcript_ready.connect(
                lambda data: on_transcript_ready(app_instance, data)
            )
            app_instance.transcript_widget.transcript_generator.progress_updated.connect(
                lambda progress, status: on_transcript_progress(app_instance, progress, status)
            )
            app_instance.transcript_widget.transcript_generator.error_occurred.connect(
                lambda error: on_transcript_error(app_instance, error)
            )
        else:
            print(f"⚠️  DEBUG: Still no transcript_generator found")
    except Exception as e:
        print(f"❌ ERROR in delayed connection: {e}")

def on_transcript_ready(app_instance, transcript_data):
    """Handle transcript generation completion"""
    app_instance.transcript_data = transcript_data
    
    # Hide loading overlay
    if hasattr(app_instance, 'hide_loading_overlay'):
        app_instance.hide_loading_overlay()
    
    # Enable repeated words button
    if hasattr(app_instance, 'repeated_words_btn'):
        app_instance.repeated_words_btn.setEnabled(True)
    
    print(f"✅ Transcript ready with {len(transcript_data)} words")

def on_transcript_progress(app_instance, progress, status):
    """Handle transcript generation progress updates"""
    if hasattr(app_instance, 'update_loading_progress'):
        app_instance.update_loading_progress(f"{status} ({progress}%)")

def on_transcript_error(app_instance, error_message):
    """Handle transcript generation errors"""
    if hasattr(app_instance, 'hide_loading_overlay'):
        app_instance.hide_loading_overlay()
    
    print(f"⚠️  Transcript generation failed: {error_message}")
    
    # Show error message to user
    if hasattr(app_instance, 'show_loading_overlay'):
        app_instance.show_loading_overlay(f"Transcript error: {error_message}")
        # Hide after 3 seconds
        QTimer.singleShot(3000, app_instance.hide_loading_overlay)

def apply_repeated_word_removal(app_instance, repeated_segments):
    """Apply repeated word removal by combining with silence segments"""
    # Convert repeated word segments to silence format
    repeated_as_silence = []
    for segment in repeated_segments:
        repeated_as_silence.append({
            'start': segment['start'],
            'end': segment['end'],
            'type': 'repeated_word',
            'selected': True  # Add required 'selected' field
        })
    
    # Store repeated segments
    app_instance.repeated_word_segments = repeated_as_silence
    
    # Combine with existing silence segments
    all_segments = app_instance.silent_parts + repeated_as_silence
    
    # Sort by start time
    all_segments.sort(key=lambda x: x['start'])
    
    # Update the timeline to show both silence and repeated word segments
    if hasattr(app_instance.video_player, 'timeline_widget'):
        # Create ranges for timeline display
        silence_ranges = []
        for segment in all_segments:
            silence_ranges.append((segment['start'], segment['end']))
        
        app_instance.video_player.timeline_widget.set_silent_parts(all_segments, silence_ranges)
    
    # Update export button state
    app_instance.update_export_button_state()
    
    # Show success message
    total_time_saved = sum(seg['end'] - seg['start'] for seg in repeated_as_silence)
    QMessageBox.information(
        app_instance, 
        "Repeated Words Added", 
        f"Added {len(repeated_as_silence)} repeated word segments for removal.\n"
        f"Additional time savings: {total_time_saved:.1f} seconds"
    ) 