#!/usr/bin/env python3
"""
Enhanced Transcript Widget with Real-time Highlighting and Repeated Word Detection
Extends the basic transcript functionality with advanced features
"""

import os
import sys
import time
import threading
from collections import Counter, defaultdict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QFrame, QPushButton, QProgressBar,
                             QTextEdit, QSplitter, QCheckBox, QSpinBox, QSlider)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QCursor, QTextCursor, QTextCharFormat

# Import the base transcript widget
try:
    from features.transcript_widget import TranscriptWidget
    from features.fast_transcript import FastTranscriptGenerator
    TRANSCRIPT_BASE_AVAILABLE = True
except ImportError:
    TRANSCRIPT_BASE_AVAILABLE = False

class RepeatedWordAnalyzer(QThread):
    """Analyze transcript for repeated words and phrases"""
    
    analysis_complete = pyqtSignal(dict)  # Emits analysis results
    progress_updated = pyqtSignal(int, str)
    
    def __init__(self, transcript_data):
        super().__init__()
        self.transcript_data = transcript_data
        
    def run(self):
        """Analyze transcript for repeated words and patterns"""
        try:
            self.progress_updated.emit(10, "Analyzing word frequency...")
            
            # Count word frequencies
            word_counts = Counter()
            word_positions = defaultdict(list)
            
            for word_data in self.transcript_data:
                word = word_data['word'].lower().strip('.,!?;:"')
                if len(word) > 2:  # Skip very short words
                    word_counts[word] += 1
                    word_positions[word].append(word_data)
            
            self.progress_updated.emit(30, "Finding repeated patterns...")
            
            # Find repeated words (appearing more than threshold)
            repeated_threshold = max(2, len(self.transcript_data) // 100)  # Dynamic threshold
            repeated_words = {word: count for word, count in word_counts.items() 
                            if count >= repeated_threshold}
            
            self.progress_updated.emit(50, "Analyzing phrase patterns...")
            
            # Find repeated phrases (2-3 word combinations)
            phrase_counts = Counter()
            phrase_positions = defaultdict(list)
            
            for i in range(len(self.transcript_data) - 1):
                # 2-word phrases
                if i < len(self.transcript_data) - 1:
                    phrase = f"{self.transcript_data[i]['word']} {self.transcript_data[i+1]['word']}"
                    phrase = phrase.lower().strip('.,!?;:"')
                    phrase_counts[phrase] += 1
                    phrase_positions[phrase].append((self.transcript_data[i], self.transcript_data[i+1]))
                
                # 3-word phrases
                if i < len(self.transcript_data) - 2:
                    phrase = f"{self.transcript_data[i]['word']} {self.transcript_data[i+1]['word']} {self.transcript_data[i+2]['word']}"
                    phrase = phrase.lower().strip('.,!?;:"')
                    phrase_counts[phrase] += 1
                    phrase_positions[phrase].append((self.transcript_data[i], self.transcript_data[i+1], self.transcript_data[i+2]))
            
            self.progress_updated.emit(70, "Identifying removal candidates...")
            
            # Find phrases that should be considered for removal
            phrase_threshold = max(2, len(self.transcript_data) // 200)
            repeated_phrases = {phrase: count for phrase, count in phrase_counts.items() 
                              if count >= phrase_threshold and len(phrase.split()) > 1}
            
            self.progress_updated.emit(90, "Calculating time savings...")
            
            # Calculate potential time savings
            total_repeated_time = 0
            removal_candidates = []
            
            # Process repeated words
            for word, count in repeated_words.items():
                if count > 2:  # Only consider words repeated more than twice
                    positions = word_positions[word]
                    # Skip first occurrence, calculate time for others
                    for pos in positions[1:]:  # Skip first occurrence
                        duration = pos['end'] - pos['start']
                        total_repeated_time += duration
                        removal_candidates.append({
                            'type': 'word',
                            'text': word,
                            'start': pos['start'],
                            'end': pos['end'],
                            'duration': duration,
                            'count': count
                        })
            
            # Process repeated phrases
            for phrase, count in repeated_phrases.items():
                if count > 1:  # Consider phrases repeated more than once
                    positions = phrase_positions[phrase]
                    for pos_group in positions[1:]:  # Skip first occurrence
                        start_time = pos_group[0]['start']
                        end_time = pos_group[-1]['end']
                        duration = end_time - start_time
                        total_repeated_time += duration
                        removal_candidates.append({
                            'type': 'phrase',
                            'text': phrase,
                            'start': start_time,
                            'end': end_time,
                            'duration': duration,
                            'count': count
                        })
            
            # Sort by potential time savings
            removal_candidates.sort(key=lambda x: x['duration'] * x['count'], reverse=True)
            
            self.progress_updated.emit(100, "Analysis complete")
            
            analysis_result = {
                'repeated_words': repeated_words,
                'repeated_phrases': repeated_phrases,
                'removal_candidates': removal_candidates,
                'total_repeated_time': total_repeated_time,
                'word_positions': dict(word_positions),
                'phrase_positions': dict(phrase_positions)
            }
            
            self.analysis_complete.emit(analysis_result)
            
        except Exception as e:
            print(f"❌ Repeated word analysis failed: {e}")

class EnhancedTranscriptWidget(TranscriptWidget):
    """Enhanced transcript widget with real-time highlighting and repeated word detection"""
    
    repeated_words_detected = pyqtSignal(dict)  # Emits repeated word analysis
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repeated_word_analysis = None
        self.highlight_repeated = True
        self.auto_scroll = True
        self.setup_enhanced_ui()
        
        # Real-time highlighting timer
        self.highlight_timer = QTimer()
        self.highlight_timer.timeout.connect(self.update_realtime_highlighting)
        self.highlight_timer.start(100)  # Update every 100ms for smooth highlighting
        
    def setup_enhanced_ui(self):
        """Add enhanced UI controls"""
        # Insert controls after the header
        controls_layout = QHBoxLayout()
        
        # Repeated word detection button
        self.analyze_btn = QPushButton("🔍 Analyze Repeated Words")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        self.analyze_btn.clicked.connect(self.analyze_repeated_words)
        
        # Highlight repeated words toggle
        self.highlight_checkbox = QCheckBox("Highlight Repeated")
        self.highlight_checkbox.setChecked(True)
        self.highlight_checkbox.setStyleSheet("""
            QCheckBox {
                color: #d1d5db;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #374151;
                border: 1px solid #6b7280;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #8b5cf6;
                border: 1px solid #8b5cf6;
                border-radius: 3px;
            }
        """)
        self.highlight_checkbox.toggled.connect(self.toggle_repeated_highlighting)
        
        # Auto-scroll toggle
        self.autoscroll_checkbox = QCheckBox("Auto-scroll")
        self.autoscroll_checkbox.setChecked(True)
        self.autoscroll_checkbox.setStyleSheet("""
            QCheckBox {
                color: #d1d5db;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #374151;
                border: 1px solid #6b7280;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #10b981;
                border: 1px solid #10b981;
                border-radius: 3px;
            }
        """)
        self.autoscroll_checkbox.toggled.connect(self.toggle_auto_scroll)
        
        controls_layout.addWidget(self.analyze_btn)
        controls_layout.addWidget(self.highlight_checkbox)
        controls_layout.addWidget(self.autoscroll_checkbox)
        controls_layout.addStretch()
        
        # Insert controls into the main layout
        main_layout = self.layout()
        main_layout.insertLayout(2, controls_layout)  # Insert after header and progress bar
        
    def on_transcript_ready(self, transcript_data):
        """Override to enable analysis button when transcript is ready"""
        super().on_transcript_ready(transcript_data)
        self.analyze_btn.setEnabled(True)
        
    def analyze_repeated_words(self):
        """Start repeated word analysis"""
        if not self.transcript_data:
            return
            
        self.analyze_btn.setEnabled(False)
        self.status_label.setText("Analyzing repeated words...")
        
        # Start analysis thread
        self.analyzer = RepeatedWordAnalyzer(self.transcript_data)
        self.analyzer.progress_updated.connect(self.on_analysis_progress)
        self.analyzer.analysis_complete.connect(self.on_analysis_complete)
        self.analyzer.start()
        
    def on_analysis_progress(self, progress, status):
        """Handle analysis progress updates"""
        self.status_label.setText(status)
        
    def on_analysis_complete(self, analysis_result):
        """Handle completed repeated word analysis"""
        self.repeated_word_analysis = analysis_result
        self.analyze_btn.setEnabled(True)
        
        repeated_count = len(analysis_result['repeated_words'])
        phrase_count = len(analysis_result['repeated_phrases'])
        time_savings = analysis_result['total_repeated_time']
        
        self.status_label.setText(
            f"Found {repeated_count} repeated words, {phrase_count} phrases. "
            f"Potential savings: {time_savings:.1f}s"
        )
        
        # Emit signal for integration with main app
        self.repeated_words_detected.emit(analysis_result)
        
        # Update display with repeated word highlighting
        if self.highlight_repeated:
            self.update_repeated_word_display()
            
    def update_repeated_word_display(self):
        """Update display to highlight repeated words"""
        if not self.repeated_word_analysis:
            return
            
        # Re-display transcript with repeated word highlighting
        self.display_transcript()
        
    def create_word_widget(self, word_data):
        """Override to add repeated word highlighting"""
        word_widget = super().create_word_widget(word_data)
        
        # Check if this word is repeated
        if self.repeated_word_analysis and self.highlight_repeated:
            word_lower = word_data['word'].lower().strip('.,!?;:"')
            if word_lower in self.repeated_word_analysis['repeated_words']:
                count = self.repeated_word_analysis['repeated_words'][word_lower]
                if count > 2:
                    # Highlight repeated words
                    word_widget.setStyleSheet("""
                        QLabel {
                            color: #fbbf24;
                            font-size: 14px;
                            padding: 4px 6px;
                            border-radius: 4px;
                            background-color: #451a03;
                            border: 1px solid #f59e0b;
                        }
                        QLabel:hover {
                            background-color: #78350f;
                            color: #fcd34d;
                            cursor: pointer;
                        }
                    """)
                    word_widget.setToolTip(f"Repeated {count} times")
        
        return word_widget
        
    def update_realtime_highlighting(self):
        """Update real-time word highlighting during playback"""
        if not self.transcript_data:
            return
            
        # Find current word based on current time
        current_word_index = -1
        for i, word_data in enumerate(self.transcript_data):
            if word_data['start'] <= self.current_time <= word_data['end']:
                current_word_index = i
                break
        
        # Update highlighting if word changed
        if current_word_index != self.current_word_index:
            self.update_word_highlighting(current_word_index)
            self.current_word_index = current_word_index
            
            # Auto-scroll to current word
            if self.auto_scroll and current_word_index >= 0:
                self.scroll_to_current_word(current_word_index)
                
    def scroll_to_current_word(self, word_index):
        """Scroll to make the current word visible"""
        try:
            # Calculate which line the word is on
            words_per_line = 12  # Same as in display_transcript
            line_index = word_index // words_per_line
            
            # Scroll to that line
            scroll_area = self.transcript_area
            content_height = self.transcript_content.height()
            visible_height = scroll_area.height()
            
            if content_height > visible_height:
                # Calculate scroll position
                line_height = content_height / ((len(self.transcript_data) // words_per_line) + 1)
                scroll_position = int(line_index * line_height)
                
                # Center the current line
                scroll_position = max(0, scroll_position - visible_height // 2)
                
                scroll_area.verticalScrollBar().setValue(scroll_position)
                
        except Exception as e:
            pass  # Fail silently for scroll errors
            
    def toggle_repeated_highlighting(self, enabled):
        """Toggle repeated word highlighting"""
        self.highlight_repeated = enabled
        if self.repeated_word_analysis:
            self.display_transcript()  # Refresh display
            
    def toggle_auto_scroll(self, enabled):
        """Toggle auto-scroll functionality"""
        self.auto_scroll = enabled
        
    def get_repeated_word_segments(self):
        """Get segments for repeated word removal (compatible with silence detection)"""
        if not self.repeated_word_analysis:
            return []
            
        segments = []
        for candidate in self.repeated_word_analysis['removal_candidates']:
            if candidate['count'] > 2:  # Only include frequently repeated items
                segments.append({
                    'start': candidate['start'],
                    'end': candidate['end'],
                    'type': 'repeated_word',
                    'text': candidate['text'],
                    'duration': candidate['duration'],
                    'selected': False  # Default to not selected
                })
                
        return segments

def integrate_enhanced_transcript_with_app(app_instance):
    """Integrate enhanced transcript with the main application"""
    try:
        # Replace basic transcript widget with enhanced version
        if hasattr(app_instance, 'transcript_widget'):
            # Remove old widget
            old_widget = app_instance.transcript_widget
            splitter = old_widget.parent()
            
            # Create enhanced widget
            enhanced_widget = EnhancedTranscriptWidget()
            enhanced_widget.setMinimumHeight(150)
            enhanced_widget.setMaximumHeight(300)
            
            # Replace in splitter
            splitter_layout = splitter.layout() if hasattr(splitter, 'layout') else None
            if hasattr(splitter, 'replaceWidget'):
                splitter.replaceWidget(old_widget, enhanced_widget)
            else:
                # Manual replacement
                index = splitter.indexOf(old_widget)
                splitter.insertWidget(index, enhanced_widget)
                old_widget.deleteLater()
            
            # Update reference
            app_instance.transcript_widget = enhanced_widget
            
            # Connect repeated word detection to main app
            enhanced_widget.repeated_words_detected.connect(
                lambda analysis: app_instance.on_repeated_words_detected(analysis)
            )
            
            return True
            
    except Exception as e:
        print(f"❌ Failed to integrate enhanced transcript: {e}")
        return False

# Export main classes
__all__ = ['EnhancedTranscriptWidget', 'RepeatedWordAnalyzer', 'integrate_enhanced_transcript_with_app'] 