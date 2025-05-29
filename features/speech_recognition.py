"""
Speech Recognition Feature for Silence Cutter
Provides speech-to-text transcription and consecutive repeated word detection functionality.
"""

import os
import sys
import tempfile
import subprocess
import json
import re
import math
from collections import Counter, defaultdict
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QProgressBar, QCheckBox, QSpinBox, QSlider,
                             QGroupBox, QScrollArea, QListWidget, QListWidgetItem,
                             QMessageBox, QFrame, QSplitter)
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtCore import Qt

class SpeechRecognitionThread(QThread):
    """Background thread for speech recognition processing"""
    progress_updated = pyqtSignal(str)  # Progress message
    transcription_complete = pyqtSignal(str)  # Full transcription
    repeated_words_found = pyqtSignal(list)  # List of repeated words with timestamps
    error_occurred = pyqtSignal(str)  # Error message
    
    def __init__(self, video_path, mode='transcription'):
        super().__init__()
        self.video_path = video_path
        self.mode = mode  # 'transcription' or 'repeated_words'
        self.min_repetitions = 2  # Minimum consecutive repetitions
        self.sensitivity = 0.8
        
    def run(self):
        """Main processing method"""
        try:
            self.progress_updated.emit("Extracting audio from video...")
            
            # Extract audio from video
            audio_path = self.extract_audio()
            
            self.progress_updated.emit("Converting audio to speech...")
            
            # Perform speech recognition with timestamps
            transcription_data = self.recognize_speech_with_timestamps(audio_path)
            
            if self.mode == 'transcription':
                # Just return the full text
                full_text = ' '.join([item['word'] for item in transcription_data])
                self.transcription_complete.emit(full_text)
            elif self.mode == 'repeated_words':
                self.progress_updated.emit("Analyzing for consecutive repeated words...")
                repeated_segments = self.find_consecutive_repeated_words(transcription_data)
                self.repeated_words_found.emit(repeated_segments)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            # Clean up temporary files
            if hasattr(self, 'temp_audio_path') and os.path.exists(self.temp_audio_path):
                try:
                    os.unlink(self.temp_audio_path)
                except:
                    pass
    
    def extract_audio(self):
        """Extract audio from video file"""
        import tempfile
        
        # Create temporary audio file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
        os.close(temp_fd)
        self.temp_audio_path = temp_path
        
        # Use ffmpeg to extract audio
        cmd = [
            'ffmpeg', '-i', self.video_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            '-y', temp_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return temp_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to extract audio: {e}")
    
    def recognize_speech_with_timestamps(self, audio_path):
        """Perform speech recognition with word-level timestamps"""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            # Load audio file
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)
            
            # Perform recognition
            try:
                # Get basic transcription first
                text = recognizer.recognize_google(audio)
                
                # Split into words and estimate timestamps
                words = text.split()
                audio_duration = self.get_audio_duration(audio_path)
                
                # Simple timestamp estimation (could be improved with more sophisticated methods)
                word_data = []
                words_per_second = len(words) / audio_duration if audio_duration > 0 else 1
                
                for i, word in enumerate(words):
                    start_time = i / words_per_second
                    end_time = (i + 1) / words_per_second
                    word_data.append({
                        'word': word.lower().strip('.,!?;:"'),
                        'start_time': start_time,
                        'end_time': end_time,
                        'original_word': word
                    })
                
                return word_data
                
            except sr.UnknownValueError:
                return []
            except sr.RequestError as e:
                raise Exception(f"Speech recognition service error: {e}")
                
        except ImportError:
            raise Exception("speech_recognition library not installed")
    
    def get_audio_duration(self, audio_path):
        """Get audio duration using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
        except:
            return 60.0  # Default fallback
    
    def find_consecutive_repeated_words(self, word_data):
        """Find consecutive repeated words/phrases in the transcription"""
        if not word_data:
            return []
        
        repeated_segments = []
        i = 0
        
        while i < len(word_data):
            # Check for single word repetitions
            current_word = word_data[i]['word']
            repetition_count = 1
            j = i + 1
            
            # Count consecutive repetitions of the same word
            while j < len(word_data) and word_data[j]['word'] == current_word:
                repetition_count += 1
                j += 1
            
            # If we found repetitions, record them
            if repetition_count >= self.min_repetitions:
                repeated_segments.append({
                    'type': 'single_word',
                    'word': current_word,
                    'original_words': [word_data[k]['original_word'] for k in range(i, j)],
                    'count': repetition_count,
                    'start_time': word_data[i]['start_time'],
                    'end_time': word_data[j-1]['end_time'],
                    'remove_start': word_data[i]['start_time'],
                    'remove_end': word_data[j-2]['end_time'],  # Keep the last occurrence
                    'keep_start': word_data[j-1]['start_time'],
                    'keep_end': word_data[j-1]['end_time']
                })
                i = j
                continue
            
            # Check for phrase repetitions (2-5 words)
            phrase_found = False
            for phrase_length in range(2, min(6, len(word_data) - i + 1)):
                if i + phrase_length * 2 > len(word_data):
                    break
                
                # Extract the phrase
                phrase1 = [word_data[i + k]['word'] for k in range(phrase_length)]
                phrase2 = [word_data[i + phrase_length + k]['word'] for k in range(phrase_length)]
                
                # Check if phrases match
                if phrase1 == phrase2:
                    # Count how many times this phrase repeats
                    phrase_count = 2
                    next_start = i + phrase_length * 2
                    
                    while next_start + phrase_length <= len(word_data):
                        next_phrase = [word_data[next_start + k]['word'] for k in range(phrase_length)]
                        if next_phrase == phrase1:
                            phrase_count += 1
                            next_start += phrase_length
                        else:
                            break
                    
                    repeated_segments.append({
                        'type': 'phrase',
                        'phrase': ' '.join(phrase1),
                        'original_phrase': ' '.join([word_data[i + k]['original_word'] for k in range(phrase_length)]),
                        'count': phrase_count,
                        'start_time': word_data[i]['start_time'],
                        'end_time': word_data[next_start - 1]['end_time'],
                        'remove_start': word_data[i]['start_time'],
                        'remove_end': word_data[next_start - phrase_length - 1]['end_time'],  # Keep last occurrence
                        'keep_start': word_data[next_start - phrase_length]['start_time'],
                        'keep_end': word_data[next_start - 1]['end_time']
                    })
                    
                    i = next_start
                    phrase_found = True
                    break
            
            if not phrase_found:
                i += 1
        
        return repeated_segments

class SpeechRecognitionDialog(QDialog):
    """Dialog for speech recognition operations"""
    
    def __init__(self, parent, video_path, mode='transcription'):
        super().__init__(parent)
        self.video_path = video_path
        self.mode = mode
        self.setModal(True)
        self.setMinimumSize(800, 600)
        
        if mode == 'transcription':
            self.setWindowTitle("🗣️ Video Transcription")
        else:
            self.setWindowTitle("🔄 Repeated Words Detection")
        
        self.setup_ui()
        self.start_processing()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"Processing: {os.path.basename(self.video_path)}")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2563eb;
                padding: 10px;
                background-color: white;
            }
        """)
        layout.addWidget(header)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self.progress_bar)
        
        # Progress label
        self.progress_label = QLabel("Initializing...")
        self.progress_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                color: #333333;
                background-color: white;
            }
        """)
        layout.addWidget(self.progress_label)
        
        # Results area - FIXED: Dark text on light background
        self.results_area = QTextEdit()
        self.results_area.setReadOnly(True)
        self.results_area.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.results_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setEnabled(False)
        
        self.copy_btn = QPushButton("Copy Results")
        self.copy_btn.clicked.connect(self.copy_results)
        self.copy_btn.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def start_processing(self):
        """Start the speech recognition processing"""
        self.thread = SpeechRecognitionThread(self.video_path, self.mode)
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.transcription_complete.connect(self.show_transcription)
        self.thread.repeated_words_found.connect(self.show_repeated_words)
        self.thread.error_occurred.connect(self.show_error)
        self.thread.start()
    
    def update_progress(self, message):
        """Update progress display"""
        self.progress_label.setText(message)
    
    def show_transcription(self, text):
        """Display transcription results"""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText("Transcription complete!")
        
        self.results_area.setPlainText(text)
        
        self.close_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
    
    def show_repeated_words(self, repeated_segments):
        """Display repeated words results"""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText("Analysis complete!")
        
        if not repeated_segments:
            self.results_area.setPlainText("No consecutive repeated words found.")
        else:
            results = "Consecutive Repeated Words/Phrases Found:\n\n"
            for i, segment in enumerate(repeated_segments, 1):
                if segment['type'] == 'single_word':
                    results += f"{i}. Word: '{segment['word']}'\n"
                    results += f"   Repeated {segment['count']} times consecutively\n"
                    results += f"   Time: {segment['start_time']:.1f}s - {segment['end_time']:.1f}s\n"
                    results += f"   Will remove: {segment['remove_start']:.1f}s - {segment['remove_end']:.1f}s\n"
                    results += f"   Will keep: {segment['keep_start']:.1f}s - {segment['keep_end']:.1f}s\n\n"
                else:
                    results += f"{i}. Phrase: '{segment['phrase']}'\n"
                    results += f"   Repeated {segment['count']} times consecutively\n"
                    results += f"   Time: {segment['start_time']:.1f}s - {segment['end_time']:.1f}s\n"
                    results += f"   Will remove: {segment['remove_start']:.1f}s - {segment['remove_end']:.1f}s\n"
                    results += f"   Will keep: {segment['keep_start']:.1f}s - {segment['keep_end']:.1f}s\n\n"
            
            self.results_area.setPlainText(results)
        
        self.close_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
    
    def show_error(self, error_message):
        """Display error message"""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText("Error occurred!")
        
        self.results_area.setPlainText(f"Error: {error_message}")
        
        self.close_btn.setEnabled(True)
    
    def copy_results(self):
        """Copy results to clipboard"""
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.results_area.toPlainText())
        
        # Show brief confirmation
        original_text = self.copy_btn.text()
        self.copy_btn.setText("Copied!")
        QTimer.singleShot(1000, lambda: self.copy_btn.setText(original_text))

class SpeechRecognitionManager(QObject):
    """Manager for speech recognition functionality"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.repeated_word_segments = []  # Store detected repeated word segments
    
    def show_transcription_dialog(self, video_path):
        """Show transcription dialog"""
        dialog = SpeechRecognitionDialog(self.parent_app, video_path, 'transcription')
        return dialog.exec_()
    
    def show_repeated_words_dialog(self, video_path):
        """Show repeated words detection dialog"""
        dialog = SpeechRecognitionDialog(self.parent_app, video_path, 'repeated_words')
        return dialog.exec_()
    
    def detect_repeated_words_for_preview(self, video_path):
        """Detect repeated words and return segments for preview/processing"""
        try:
            # Create a thread to detect repeated words
            thread = SpeechRecognitionThread(video_path, 'repeated_words')
            
            # Run synchronously for this use case
            thread.run()
            
            # Convert to the format expected by the timeline/processing system
            repeated_parts = []
            for segment in self.repeated_word_segments:
                repeated_parts.append({
                    'start': segment['remove_start'],
                    'end': segment['remove_end'],
                    'type': 'repeated_word',
                    'description': f"Repeated: {segment.get('word', segment.get('phrase', 'Unknown'))}"
                })
            
            return repeated_parts
            
        except Exception as e:
            print(f"Error detecting repeated words: {e}")
            return []

def integrate_speech_recognition(app):
    """Integrate speech recognition with the main application"""
    if not hasattr(app, 'speech_recognition_manager'):
        app.speech_recognition_manager = SpeechRecognitionManager(app)
    return app.speech_recognition_manager