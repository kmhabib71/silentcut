#!/usr/bin/env python3
"""
Fast Transcript Widget with Timeline Integration
Provides real-time transcript display with clickable words for video seeking
"""

import os
import sys
import time
import threading
import tempfile
import subprocess
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QFrame, QPushButton, QProgressBar,
                             QTextEdit, QSplitter, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QCursor, QTextCursor, QTextCharFormat

# Import the fast transcript generator
try:
    from features.fast_transcript import FastTranscriptGenerator
    FAST_TRANSCRIPT_AVAILABLE = True
except ImportError:
    FAST_TRANSCRIPT_AVAILABLE = False
    print("⚠️  Fast transcript generator not available")

class TranscriptWidget(QWidget):
    """Enhanced transcript widget with fast generation and timeline sync"""
    
    seek_requested = pyqtSignal(float)  # Emitted when user clicks on a word
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.transcript_data = []
        self.current_time = 0.0
        self.current_word_index = -1
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the transcript widget UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📝 Live Transcript")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #f9fafb;
                padding: 4px 0px;
            }
        """)
        
        # Speed indicator
        self.speed_label = QLabel("⚡ Fast Mode")
        self.speed_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #10b981;
                background-color: #064e3b;
                padding: 2px 8px;
                border-radius: 4px;
            }
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.speed_label)
        
        # Progress bar for transcript generation
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #374151;
                text-align: center;
                color: white;
                font-weight: 500;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #8b5cf6;
                border-radius: 4px;
            }
        """)
        
        # Status label
        self.status_label = QLabel("Ready to generate transcript")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #9ca3af;
                padding: 2px 0px;
            }
        """)
        
        # Transcript display area
        self.transcript_area = QScrollArea()
        self.transcript_area.setWidgetResizable(True)
        self.transcript_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.transcript_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.transcript_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #374151;
                border-radius: 8px;
                background-color: #1f2937;
            }
            QScrollBar:vertical {
                background-color: #374151;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #6b7280;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #9ca3af;
            }
        """)
        
        # Transcript content widget
        self.transcript_content = QWidget()
        self.transcript_layout = QVBoxLayout(self.transcript_content)
        self.transcript_layout.setContentsMargins(12, 12, 12, 12)
        self.transcript_layout.setSpacing(4)
        
        # Default message
        self.default_label = QLabel("Click 'Generate Transcript' to start")
        self.default_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
                text-align: center;
                padding: 20px;
            }
        """)
        self.transcript_layout.addWidget(self.default_label)
        
        self.transcript_area.setWidget(self.transcript_content)
        
        # Add widgets to main layout
        layout.addLayout(header_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.transcript_area, 1)
        
        self.setLayout(layout)
        
        # Set minimum size
        self.setMinimumHeight(200)
        
    def load_transcript(self, video_path):
        """Load transcript for the given video using fast generation"""
        if not FAST_TRANSCRIPT_AVAILABLE:
            self.status_label.setText("Fast transcript generator not available")
            return
        
        self.video_path = video_path
        self.status_label.setText("Generating transcript...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Clear existing transcript
        self.clear_transcript()
        
        # Start fast transcript generation
        self.transcript_generator = FastTranscriptGenerator(video_path)
        self.transcript_generator.progress_updated.connect(self.on_progress_updated)
        self.transcript_generator.transcript_ready.connect(self.on_transcript_ready)
        self.transcript_generator.error_occurred.connect(self.on_error_occurred)
        self.transcript_generator.start()
        
    def on_progress_updated(self, progress, status):
        """Handle progress updates from transcript generation"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)
        
    def on_transcript_ready(self, transcript_data):
        """Handle completed transcript"""
        self.transcript_data = transcript_data
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Transcript ready ({len(transcript_data)} words)")
        
        # Display transcript
        self.display_transcript()
        
    def on_error_occurred(self, error_message):
        """Handle transcript generation errors"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error_message}")
        
    def clear_transcript(self):
        """Clear the transcript display"""
        # Remove all widgets except the default label
        for i in reversed(range(self.transcript_layout.count())):
            item = self.transcript_layout.itemAt(i)
            if item and item.widget() and item.widget() != self.default_label:
                item.widget().deleteLater()
        
        # Show default label
        self.default_label.setVisible(True)
        
    def display_transcript(self):
        """Display the transcript with clickable words"""
        # Hide default label
        self.default_label.setVisible(False)
        
        # Create word widgets
        current_line = QHBoxLayout()
        current_line.setSpacing(4)
        words_in_line = 0
        max_words_per_line = 12
        
        for word_data in self.transcript_data:
            word_widget = self.create_word_widget(word_data)
            current_line.addWidget(word_widget)
            words_in_line += 1
            
            # Start new line after certain number of words
            if words_in_line >= max_words_per_line:
                line_widget = QWidget()
                line_widget.setLayout(current_line)
                self.transcript_layout.addWidget(line_widget)
                
                current_line = QHBoxLayout()
                current_line.setSpacing(4)
                words_in_line = 0
        
        # Add remaining words
        if words_in_line > 0:
            current_line.addStretch()
            line_widget = QWidget()
            line_widget.setLayout(current_line)
            self.transcript_layout.addWidget(line_widget)
        
        # Add stretch at the end
        self.transcript_layout.addStretch()
        
    def create_word_widget(self, word_data):
        """Create a clickable word widget"""
        word_label = QLabel(word_data['word'])
        word_label.setStyleSheet("""
            QLabel {
                color: #d1d5db;
                font-size: 14px;
                padding: 4px 6px;
                border-radius: 4px;
                background-color: transparent;
            }
            QLabel:hover {
                background-color: #374151;
                color: #f9fafb;
                cursor: pointer;
            }
        """)
        
        # Store word data
        word_label.word_data = word_data
        
        # Make clickable
        word_label.mousePressEvent = lambda event, wd=word_data: self.on_word_clicked(wd)
        word_label.setCursor(QCursor(Qt.PointingHandCursor))
        
        return word_label
        
    def on_word_clicked(self, word_data):
        """Handle word click - seek to that time"""
        seek_time = word_data['start']
        self.seek_requested.emit(seek_time)
        print(f"🎯 Seeking to word '{word_data['word']}' at {seek_time:.2f}s")
        
    def update_current_time(self, time_seconds):
        """Update current playback time and highlight current word"""
        self.current_time = time_seconds
        
        # Find current word
        current_word_index = -1
        for i, word_data in enumerate(self.transcript_data):
            if word_data['start'] <= time_seconds <= word_data['end']:
                current_word_index = i
                break
        
        # Update highlighting if word changed
        if current_word_index != self.current_word_index:
            self.update_word_highlighting(current_word_index)
            self.current_word_index = current_word_index
            
    def update_word_highlighting(self, current_word_index):
        """Update word highlighting based on current playback position"""
        # Find all word labels and update their styles
        for i in range(self.transcript_layout.count()):
            item = self.transcript_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'layout') and widget.layout():
                    # This is a line widget
                    line_layout = widget.layout()
                    for j in range(line_layout.count()):
                        line_item = line_layout.itemAt(j)
                        if line_item and line_item.widget():
                            word_widget = line_item.widget()
                            if hasattr(word_widget, 'word_data'):
                                word_id = word_widget.word_data['id']
                                
                                if word_id == current_word_index:
                                    # Highlight current word
                                    word_widget.setStyleSheet("""
                                        QLabel {
                                            color: #ffffff;
                                            font-size: 14px;
                                            font-weight: 600;
                                            padding: 4px 6px;
                                            border-radius: 4px;
                                            background-color: #8b5cf6;
                                        }
                                        QLabel:hover {
                                            background-color: #7c3aed;
                                            cursor: pointer;
                                        }
                                    """)
                                else:
                                    # Normal word style
                                    word_widget.setStyleSheet("""
                                        QLabel {
                                            color: #d1d5db;
                                            font-size: 14px;
                                            padding: 4px 6px;
                                            border-radius: 4px;
                                            background-color: transparent;
                                        }
                                        QLabel:hover {
                                            background-color: #374151;
                                            color: #f9fafb;
                                            cursor: pointer;
                                        }
                                    """)

def integrate_transcript_with_timeline(timeline_widget, transcript_widget):
    """Integrate transcript widget with timeline for synchronized highlighting"""
    if hasattr(timeline_widget, 'position_changed'):
        timeline_widget.position_changed.connect(transcript_widget.update_current_time)
        print("✅ Transcript synchronized with timeline")
    else:
        print("⚠️  Timeline position signal not available")

# Export main classes
__all__ = ['TranscriptWidget', 'integrate_transcript_with_timeline'] 