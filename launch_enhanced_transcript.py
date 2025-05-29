#!/usr/bin/env python3
"""
Enhanced Silence Cutter with Advanced Transcript Features
Launcher script with real-time word highlighting and repeated word detection
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer

# Import the main application
from silence_cutter import SilenceCutterApp

# Import enhanced transcript features
try:
    from features.enhanced_transcript import EnhancedTranscriptWidget, integrate_enhanced_transcript_with_app
    from features.repeated_word_integration import integrate_repeated_words_with_app
    from transcript_integration import add_transcript_button, enable_transcript_features, disable_transcript_features
    ENHANCED_TRANSCRIPT_AVAILABLE = True
    print("✅ Enhanced transcript features available")
except ImportError as e:
    print(f"⚠️  Enhanced transcript features not available: {e}")
    ENHANCED_TRANSCRIPT_AVAILABLE = False

class AdvancedSilenceCutterApp(SilenceCutterApp):
    """Advanced version with enhanced transcript and repeated word detection"""
    
    def __init__(self):
        super().__init__()
        
        # Add enhanced transcript integration after UI is set up
        if ENHANCED_TRANSCRIPT_AVAILABLE:
            self.setup_enhanced_transcript()
    
    def setup_enhanced_transcript(self):
        """Set up enhanced transcript integration"""
        try:
            # Create enhanced transcript widget
            self.enhanced_transcript_widget = EnhancedTranscriptWidget()
            self.enhanced_transcript_widget.setMinimumHeight(150)
            self.enhanced_transcript_widget.setMaximumHeight(350)
            
            # Connect transcript seeking to video player
            def on_transcript_seek(seek_time):
                """Handle seek request from transcript"""
                if hasattr(self.video_player, 'seek_to_position'):
                    self.video_player.seek_to_position(seek_time, from_timeline=False)
                    print(f"🎯 Transcript seek to {seek_time:.2f}s")
            
            self.enhanced_transcript_widget.seek_requested.connect(on_transcript_seek)
            
            # Connect timeline position updates to transcript for real-time highlighting
            def on_timeline_position_changed(position_seconds):
                """Update transcript highlighting based on timeline position"""
                self.enhanced_transcript_widget.update_current_time(position_seconds)
            
            if hasattr(self.video_player, 'timeline_widget') and hasattr(self.video_player.timeline_widget, 'position_changed'):
                self.video_player.timeline_widget.position_changed.connect(on_timeline_position_changed)
                print("✅ Real-time transcript highlighting connected")
            
            # Add enhanced transcript to splitter
            self.video_timeline_splitter.addWidget(self.enhanced_transcript_widget)
            
            # Update splitter sizes (35% video, 30% timeline, 35% transcript)
            self.video_timeline_splitter.setSizes([350, 300, 350])
            self.video_timeline_splitter.setCollapsible(2, True)  # Allow transcript to collapse
            
            # Store reference
            self.transcript_widget = self.enhanced_transcript_widget
            
            # Set up repeated word integration
            integrate_repeated_words_with_app(self)
            
            # Add transcript button to the UI
            transcript_btn = add_transcript_button(self)
            if transcript_btn:
                # Find the detect button and add transcript button after it
                left_panel_layout = self.detect_btn.parent().layout()
                if left_panel_layout:
                    # Insert transcript button after detect button
                    detect_btn_index = -1
                    for i in range(left_panel_layout.count()):
                        item = left_panel_layout.itemAt(i)
                        if item and item.widget() == self.detect_btn:
                            detect_btn_index = i
                            break
                    
                    if detect_btn_index >= 0:
                        left_panel_layout.insertWidget(detect_btn_index + 1, transcript_btn)
                        print("✅ Enhanced transcript button added to UI")
                    else:
                        # Fallback: add at the end
                        left_panel_layout.addWidget(transcript_btn)
                        print("✅ Enhanced transcript button added to UI (fallback position)")
            
            print("✅ Enhanced transcript widget integrated successfully")
            
        except Exception as e:
            print(f"❌ Failed to set up enhanced transcript: {e}")
    
    def select_video(self):
        """Override select_video to add enhanced transcript loading"""
        # Call parent method
        super().select_video()
        
        # Add transcript loading if video was selected
        if hasattr(self, 'video_path') and self.video_path and ENHANCED_TRANSCRIPT_AVAILABLE:
            # Store current video path for transcript button
            self.current_video_path = self.video_path
            
            # Enable transcript features
            try:
                enable_transcript_features(self)
                print(f"🎬 Video loaded: {os.path.basename(self.video_path)}")
                print("📝 Enhanced transcript features enabled")
            except Exception as e:
                print(f"⚠️  Failed to enable transcript features: {e}")
    
    def on_repeated_words_detected(self, analysis_result):
        """Handle repeated words detection from enhanced transcript"""
        try:
            from features.repeated_word_integration import RepeatedWordPreviewDialog
            
            # Show preview dialog
            dialog = RepeatedWordPreviewDialog(analysis_result, self)
            
            # Connect preview signal to existing preview functionality
            if hasattr(self, 'apply_repeated_words_preview'):
                dialog.segments_selected.connect(self.apply_repeated_words_preview)
            else:
                # Create a simple preview handler
                def simple_preview(segments):
                    total_time = sum(seg['duration'] for seg in segments)
                    QMessageBox.information(
                        self, 
                        "Repeated Words Preview",
                        f"Would remove {len(segments)} repeated segments.\n"
                        f"Total time savings: {total_time:.1f} seconds"
                    )
                dialog.segments_selected.connect(simple_preview)
            
            # Show dialog
            result = dialog.exec_()
            if result == dialog.Accepted:
                segments = dialog.selected_segments
                if segments:
                    print(f"✂️ User selected {len(segments)} repeated segments for removal")
                    # Here you could integrate with existing removal functionality
                    
        except Exception as e:
            print(f"❌ Failed to handle repeated words detection: {e}")
    
    def closeEvent(self, event):
        """Override close event to clean up transcript resources"""
        try:
            # Stop transcript highlighting timer
            if hasattr(self, 'enhanced_transcript_widget'):
                if hasattr(self.enhanced_transcript_widget, 'highlight_timer'):
                    self.enhanced_transcript_widget.highlight_timer.stop()
                    
            # Call parent close event
            super().closeEvent(event)
            
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
            event.accept()

def show_feature_overview():
    """Show an overview of available features"""
    features = [
        "🎬 Video silence detection and removal",
        "✂️ Manual cutting tools with precision timeline",
        "📦 Batch processing for multiple files",
        "🔄 Undo/redo functionality"
    ]
    
    if ENHANCED_TRANSCRIPT_AVAILABLE:
        features.extend([
            "📝 Fast transcript generation (multiple methods)",
            "🎯 Clickable words for precise video seeking",
            "✨ Real-time word highlighting during playback",
            "🔍 Repeated word/phrase detection and removal",
            "📊 Smart analysis with time savings calculation",
            "🎨 Modern UI with dark theme and smooth animations"
        ])
    else:
        features.append("📝 Transcript features (not available - missing dependencies)")
    
    return features

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Advanced Media Silence Cutter")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("SilenceCutter")
    
    # Set global dark theme
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1a202c;
            color: #e2e8f0;
        }
        QWidget {
            background-color: #1a202c;
            color: #e2e8f0;
        }
        QDialog {
            background-color: #1a202c;
            color: #e2e8f0;
        }
    """)
    
    # Create and show the advanced application
    window = AdvancedSilenceCutterApp()
    window.show()
    
    print("🚀 Advanced Silence Cutter with Enhanced Transcript Features started")
    print("=" * 70)
    
    features = show_feature_overview()
    for feature in features:
        print(f"  {feature}")
    
    print("=" * 70)
    
    if ENHANCED_TRANSCRIPT_AVAILABLE:
        print("💡 Usage Tips:")
        print("  • Load a video and click 'Generate Transcript' for real-time features")
        print("  • Words highlight automatically as video plays")
        print("  • Click any word to jump to that moment in the video")
        print("  • Use 'Analyze Repeated Words' to find and remove repetitive content")
        print("  • Toggle 'Auto-scroll' to follow playback in transcript")
        print("  • Combine silence removal with repeated word removal for maximum efficiency")
    else:
        print("⚠️  Install transcript dependencies for enhanced features:")
        print("  pip install faster-whisper openai-whisper vosk")
    
    print("=" * 70)
    
    # Run the application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 