#!/usr/bin/env python3
"""
Test script to verify the enhanced loading experience
"""

import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer

# Add the current directory to path to import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from silence_cutter import LoadingOverlay, SilenceCutterApp

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loading Test")
        self.setGeometry(100, 100, 600, 400)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Test button
        test_btn = QPushButton("Test Enhanced Loading")
        test_btn.clicked.connect(self.test_loading)
        layout.addWidget(test_btn)
        
        # Create loading overlay
        self.loading_overlay = None
        
    def test_loading(self):
        """Test the enhanced loading experience"""
        print("🧪 Testing enhanced loading experience...")
        
        # Create and show loading overlay
        if not self.loading_overlay:
            self.loading_overlay = LoadingOverlay(self)
            self.loading_overlay.setFixedSize(self.size())
        
        self.loading_overlay.show_loading("Testing Enhanced Loading...")
        
        # Simulate loading steps
        self.loading_start_time = time.time()
        self.loading_steps_completed = 0
        self.total_loading_steps = 6
        self.estimated_total_time = 10  # 10 second test
        
        # Start step simulation
        self.simulate_step(1)
        
    def simulate_step(self, step):
        """Simulate a loading step"""
        self.loading_steps_completed = step
        
        step_messages = [
            "Initializing video player...",
            "Setting up video player...", 
            "Loading timeline waveform...",
            "Initializing media player...",
            "Setting up enhanced video player...",
            "Video ready!"
        ]
        
        if step <= len(step_messages):
            message = step_messages[step - 1]
            self.update_loading_progress_with_step(message, step)
            
            if step < self.total_loading_steps:
                # Schedule next step
                delay = 1500 if step == 3 else 1000  # Longer delay for waveform step
                QTimer.singleShot(delay, lambda: self.simulate_step(step + 1))
            else:
                # Finish loading
                QTimer.singleShot(800, self.finish_loading)
    
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
            
        print(f"📊 Step {step_number}: {message} ({progress_percent}%)")
    
    def finish_loading(self):
        """Finish the loading test"""
        if self.loading_overlay:
            self.loading_overlay.hide_loading()
        print("✅ Loading test completed!")
        
    def resizeEvent(self, event):
        """Handle window resize to update loading overlay size"""
        super().resizeEvent(event)
        if self.loading_overlay:
            self.loading_overlay.setFixedSize(self.size())

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 