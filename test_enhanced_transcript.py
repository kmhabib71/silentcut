#!/usr/bin/env python3
"""
Test script for enhanced transcript features
Tests real-time highlighting and repeated word detection
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from features.enhanced_transcript import EnhancedTranscriptWidget, RepeatedWordAnalyzer
    from features.repeated_word_integration import RepeatedWordPreviewDialog
    print("✅ Enhanced transcript components imported successfully")
except ImportError as e:
    print(f"❌ Failed to import enhanced transcript components: {e}")
    sys.exit(1)

class TestEnhancedTranscriptApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Transcript Test")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create main widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        load_transcript_btn = QPushButton("📝 Load Test Transcript")
        load_transcript_btn.clicked.connect(self.load_test_transcript)
        
        simulate_playback_btn = QPushButton("▶️ Simulate Playback")
        simulate_playback_btn.clicked.connect(self.simulate_playback)
        
        analyze_repeated_btn = QPushButton("🔍 Analyze Repeated Words")
        analyze_repeated_btn.clicked.connect(self.analyze_repeated_words)
        
        controls_layout.addWidget(load_transcript_btn)
        controls_layout.addWidget(simulate_playback_btn)
        controls_layout.addWidget(analyze_repeated_btn)
        controls_layout.addStretch()
        
        # Create splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Create mock video widget
        video_widget = QWidget()
        video_widget.setStyleSheet("background-color: #2d3748; border: 1px solid #4a5568;")
        video_widget.setMinimumHeight(200)
        
        # Create enhanced transcript widget
        self.transcript_widget = EnhancedTranscriptWidget()
        
        # Add to splitter
        splitter.addWidget(video_widget)
        splitter.addWidget(self.transcript_widget)
        
        # Set splitter sizes
        splitter.setSizes([300, 500])
        
        layout.addLayout(controls_layout)
        layout.addWidget(splitter)
        self.setCentralWidget(main_widget)
        
        # Connect signals
        self.transcript_widget.seek_requested.connect(self.on_seek_requested)
        self.transcript_widget.repeated_words_detected.connect(self.on_repeated_words_detected)
        
        # Playback simulation
        self.current_time = 0.0
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.update_playback_time)
        
    def load_test_transcript(self):
        """Load test transcript with repeated words"""
        mock_transcript = [
            {'id': 0, 'word': 'Hello', 'start': 0.0, 'end': 0.5, 'confidence': 0.9},
            {'id': 1, 'word': 'everyone', 'start': 0.5, 'end': 1.0, 'confidence': 0.8},
            {'id': 2, 'word': 'welcome', 'start': 1.0, 'end': 1.5, 'confidence': 0.9},
            {'id': 3, 'word': 'to', 'start': 1.5, 'end': 1.7, 'confidence': 0.95},
            {'id': 4, 'word': 'this', 'start': 1.7, 'end': 2.0, 'confidence': 0.9},
            {'id': 5, 'word': 'amazing', 'start': 2.0, 'end': 2.5, 'confidence': 0.85},
            {'id': 6, 'word': 'video', 'start': 2.5, 'end': 3.0, 'confidence': 0.9},
            {'id': 7, 'word': 'tutorial', 'start': 3.0, 'end': 3.8, 'confidence': 0.88},
            
            # Repeated section 1
            {'id': 8, 'word': 'this', 'start': 4.0, 'end': 4.3, 'confidence': 0.9},
            {'id': 9, 'word': 'is', 'start': 4.3, 'end': 4.5, 'confidence': 0.95},
            {'id': 10, 'word': 'amazing', 'start': 4.5, 'end': 5.0, 'confidence': 0.85},
            {'id': 11, 'word': 'content', 'start': 5.0, 'end': 5.5, 'confidence': 0.9},
            
            # More content
            {'id': 12, 'word': 'we', 'start': 6.0, 'end': 6.2, 'confidence': 0.9},
            {'id': 13, 'word': 'will', 'start': 6.2, 'end': 6.5, 'confidence': 0.9},
            {'id': 14, 'word': 'learn', 'start': 6.5, 'end': 7.0, 'confidence': 0.9},
            {'id': 15, 'word': 'about', 'start': 7.0, 'end': 7.3, 'confidence': 0.9},
            {'id': 16, 'word': 'video', 'start': 7.3, 'end': 7.8, 'confidence': 0.9},
            {'id': 17, 'word': 'editing', 'start': 7.8, 'end': 8.5, 'confidence': 0.9},
            
            # Repeated section 2 (same as section 1)
            {'id': 18, 'word': 'this', 'start': 9.0, 'end': 9.3, 'confidence': 0.9},
            {'id': 19, 'word': 'is', 'start': 9.3, 'end': 9.5, 'confidence': 0.95},
            {'id': 20, 'word': 'amazing', 'start': 9.5, 'end': 10.0, 'confidence': 0.85},
            {'id': 21, 'word': 'content', 'start': 10.0, 'end': 10.5, 'confidence': 0.9},
            
            # More unique content
            {'id': 22, 'word': 'let', 'start': 11.0, 'end': 11.2, 'confidence': 0.9},
            {'id': 23, 'word': 'me', 'start': 11.2, 'end': 11.4, 'confidence': 0.9},
            {'id': 24, 'word': 'show', 'start': 11.4, 'end': 11.8, 'confidence': 0.9},
            {'id': 25, 'word': 'you', 'start': 11.8, 'end': 12.0, 'confidence': 0.9},
            {'id': 26, 'word': 'the', 'start': 12.0, 'end': 12.2, 'confidence': 0.9},
            {'id': 27, 'word': 'features', 'start': 12.2, 'end': 12.8, 'confidence': 0.9},
            
            # Repeated section 3 (same again)
            {'id': 28, 'word': 'this', 'start': 13.0, 'end': 13.3, 'confidence': 0.9},
            {'id': 29, 'word': 'is', 'start': 13.3, 'end': 13.5, 'confidence': 0.95},
            {'id': 30, 'word': 'amazing', 'start': 13.5, 'end': 14.0, 'confidence': 0.85},
            {'id': 31, 'word': 'content', 'start': 14.0, 'end': 14.5, 'confidence': 0.9},
            
            # Final content
            {'id': 32, 'word': 'thank', 'start': 15.0, 'end': 15.3, 'confidence': 0.9},
            {'id': 33, 'word': 'you', 'start': 15.3, 'end': 15.6, 'confidence': 0.9},
            {'id': 34, 'word': 'for', 'start': 15.6, 'end': 15.8, 'confidence': 0.9},
            {'id': 35, 'word': 'watching', 'start': 15.8, 'end': 16.5, 'confidence': 0.9},
        ]
        
        # Simulate transcript ready
        self.transcript_widget.on_transcript_ready(mock_transcript)
        print("✅ Test transcript loaded with repeated phrases")
        
    def simulate_playback(self):
        """Simulate video playback for real-time highlighting"""
        if self.playback_timer.isActive():
            self.playback_timer.stop()
            print("⏸️ Playback stopped")
        else:
            self.current_time = 0.0
            self.playback_timer.start(100)  # Update every 100ms
            print("▶️ Playback started - watch real-time highlighting!")
            
    def update_playback_time(self):
        """Update playback time for real-time highlighting"""
        self.current_time += 0.1  # Advance by 100ms
        
        # Update transcript highlighting
        self.transcript_widget.update_current_time(self.current_time)
        
        # Stop at end of transcript
        if self.current_time > 17.0:
            self.playback_timer.stop()
            print("⏹️ Playback finished")
            
    def analyze_repeated_words(self):
        """Test repeated word analysis"""
        if not self.transcript_widget.transcript_data:
            print("⚠️  Load transcript first")
            return
            
        self.transcript_widget.analyze_repeated_words()
        print("🔍 Analyzing repeated words...")
        
    def on_seek_requested(self, seek_time):
        """Handle seek request from transcript"""
        self.current_time = seek_time
        print(f"🎯 Seek requested to: {seek_time:.2f}s")
        
    def on_repeated_words_detected(self, analysis_result):
        """Handle repeated words detection"""
        print(f"🔍 Repeated words analysis complete!")
        print(f"  • Found {len(analysis_result['repeated_words'])} repeated words")
        print(f"  • Found {len(analysis_result['repeated_phrases'])} repeated phrases")
        print(f"  • Potential time savings: {analysis_result['total_repeated_time']:.1f}s")
        
        # Show preview dialog
        try:
            dialog = RepeatedWordPreviewDialog(analysis_result, self)
            dialog.segments_selected.connect(self.on_segments_selected)
            dialog.show()
        except Exception as e:
            print(f"❌ Failed to show preview dialog: {e}")
            
    def on_segments_selected(self, segments):
        """Handle segment selection for preview"""
        total_time = sum(seg['duration'] for seg in segments)
        print(f"🎬 Preview: {len(segments)} segments selected, {total_time:.1f}s total")

def main():
    app = QApplication(sys.argv)
    
    # Set dark theme
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1a202c;
            color: #e2e8f0;
        }
        QWidget {
            background-color: #1a202c;
            color: #e2e8f0;
        }
        QPushButton {
            background-color: #4a5568;
            color: white;
            padding: 8px 16px;
            font-weight: 600;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover {
            background-color: #2d3748;
        }
    """)
    
    window = TestEnhancedTranscriptApp()
    window.show()
    
    print("🚀 Enhanced Transcript Test Application started")
    print("💡 Test Instructions:")
    print("  1. Click 'Load Test Transcript' to load sample data with repeated phrases")
    print("  2. Click 'Simulate Playback' to see real-time word highlighting")
    print("  3. Click 'Analyze Repeated Words' to test repeated word detection")
    print("  4. Click on any word in the transcript to test seeking")
    print("  5. Use checkboxes to toggle highlighting and auto-scroll features")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 