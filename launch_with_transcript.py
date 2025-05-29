#!/usr/bin/env python3
"""
Enhanced Silence Cutter with Transcript Integration
Launcher script that adds transcript functionality to the main application
"""

import sys
import os
from PyQt5.QtWidgets import QApplication

# Import the main application
from silence_cutter import SilenceCutterApp

# Import transcript integration
try:
    from transcript_integration import integrate_transcript_widget, add_transcript_button, load_transcript_for_video
    TRANSCRIPT_AVAILABLE = True
    print("✅ Transcript integration available")
except ImportError as e:
    print(f"⚠️  Transcript integration not available: {e}")
    TRANSCRIPT_AVAILABLE = False

class EnhancedSilenceCutterApp(SilenceCutterApp):
    """Enhanced version of SilenceCutterApp with transcript integration"""
    
    def __init__(self):
        super().__init__()
        
        # Add transcript integration after UI is set up
        if TRANSCRIPT_AVAILABLE:
            self.setup_transcript_integration()
    
    def setup_transcript_integration(self):
        """Set up transcript integration"""
        try:
            # Integrate transcript widget into the splitter
            if integrate_transcript_widget(self):
                print("✅ Transcript widget integrated into UI")
                
                # Add transcript button to the left panel
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
                            print("✅ Transcript button added to UI")
                        else:
                            # Fallback: add at the end
                            left_panel_layout.addWidget(transcript_btn)
                            print("✅ Transcript button added to UI (fallback position)")
            
        except Exception as e:
            print(f"❌ Failed to set up transcript integration: {e}")
    
    def select_video(self):
        """Override select_video to add transcript loading"""
        # Call parent method
        super().select_video()
        
        # Add transcript loading if video was selected
        if hasattr(self, 'video_path') and self.video_path and TRANSCRIPT_AVAILABLE:
            # Store current video path for transcript button
            self.current_video_path = self.video_path
            
            # Enable transcript features
            try:
                from transcript_integration import enable_transcript_features
                enable_transcript_features(self)
            except:
                pass

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Enhanced Media Silence Cutter")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("SilenceCutter")
    
    # Create and show the enhanced application
    window = EnhancedSilenceCutterApp()
    window.show()
    
    print("🚀 Enhanced Silence Cutter with Transcript Integration started")
    print("📝 Features available:")
    print("  • Silence detection and removal")
    print("  • Manual cutting tools")
    print("  • Batch processing")
    if TRANSCRIPT_AVAILABLE:
        print("  • Live transcript with clickable words")
        print("  • Fast transcript generation")
        print("  • Timeline-synchronized transcript highlighting")
    else:
        print("  • Transcript features (not available)")
    
    # Run the application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 