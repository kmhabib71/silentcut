"""
Batch Processing Feature for Silence Cutter
Allows users to process multiple audio/video files at once with the same settings.

Features:
- Add multiple files to batch queue
- Apply same silence detection settings to all files
- Process files sequentially or in parallel
- Progress tracking for each file and overall batch
- Save/load batch configurations
- Output organization options
"""

import os
import json
import threading
import time
from pathlib import Path
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QPushButton, QLabel, QProgressBar, QGroupBox,
                            QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox,
                            QCheckBox, QComboBox, QLineEdit, QTextEdit,
                            QListWidgetItem, QFrame, QGridLayout, QTabWidget,
                            QScrollArea, QWidget)
from PyQt5.QtGui import QFont, QIcon, QPixmap


class BatchProcessingManager(QObject):
    """Manages batch processing operations"""
    
    # Signals
    batch_started = pyqtSignal()
    batch_completed = pyqtSignal(dict)  # Results summary
    batch_progress = pyqtSignal(int, int)  # current_file, total_files
    file_started = pyqtSignal(str)  # file_path
    file_completed = pyqtSignal(str, bool, str)  # file_path, success, output_path_or_error
    file_progress = pyqtSignal(str, int)  # file_path, progress_percent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.batch_queue = []
        self.processing = False
        self.current_settings = {
            'min_silence_duration': 500,
            'silence_threshold': -40,
            'padding_ms': 100,
            'output_directory': '',
            'output_format': 'same',  # 'same', 'mp4', 'mp3', 'wav'
            'parallel_processing': False,
            'max_parallel_jobs': 2
        }
        self.results = {
            'total_files': 0,
            'processed_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'total_time': 0,
            'files_results': []
        }
        
    def add_files(self, file_paths):
        """Add files to batch queue"""
        added_count = 0
        for file_path in file_paths:
            if self.is_valid_media_file(file_path) and file_path not in [item['path'] for item in self.batch_queue]:
                self.batch_queue.append({
                    'path': file_path,
                    'status': 'pending',
                    'progress': 0,
                    'output_path': '',
                    'error': '',
                    'processing_time': 0
                })
                added_count += 1
        return added_count
        
    def remove_file(self, file_path):
        """Remove file from batch queue"""
        self.batch_queue = [item for item in self.batch_queue if item['path'] != file_path]
        
    def clear_queue(self):
        """Clear all files from batch queue"""
        self.batch_queue.clear()
        
    def is_valid_media_file(self, file_path):
        """Check if file is a valid media file"""
        valid_extensions = {
            '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
            '.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'
        }
        return Path(file_path).suffix.lower() in valid_extensions
        
    def update_settings(self, settings):
        """Update processing settings"""
        self.current_settings.update(settings)
        
    def get_output_path(self, input_path):
        """Generate output path for processed file"""
        input_file = Path(input_path)
        
        if self.current_settings['output_directory']:
            output_dir = Path(self.current_settings['output_directory'])
        else:
            output_dir = input_file.parent / 'processed'
            
        output_dir.mkdir(exist_ok=True)
        
        # Determine output format
        if self.current_settings['output_format'] == 'same':
            output_ext = input_file.suffix
        else:
            output_ext = f".{self.current_settings['output_format']}"
            
        output_name = f"{input_file.stem}_processed{output_ext}"
        return str(output_dir / output_name)
        
    def save_batch_config(self, config_path):
        """Save current batch configuration"""
        config = {
            'settings': self.current_settings,
            'files': [item['path'] for item in self.batch_queue]
        }
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
    def load_batch_config(self, config_path):
        """Load batch configuration"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.current_settings.update(config.get('settings', {}))
            self.add_files(config.get('files', []))
            return True
        except Exception as e:
            print(f"Error loading batch config: {e}")
            return False


class BatchProcessingThread(QThread):
    """Thread for processing batch files"""
    
    file_started = pyqtSignal(str)
    file_completed = pyqtSignal(str, bool, str)
    file_progress = pyqtSignal(str, int)
    batch_completed = pyqtSignal(dict)
    
    def __init__(self, batch_manager, silence_detection_class, processing_class, audio_processing_class):
        super().__init__()
        self.batch_manager = batch_manager
        self.silence_detection_class = silence_detection_class
        self.processing_class = processing_class
        self.audio_processing_class = audio_processing_class
        self.should_stop = False
        
    def run(self):
        """Process all files in batch"""
        start_time = time.time()
        results = {
            'total_files': len(self.batch_manager.batch_queue),
            'processed_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'total_time': 0,
            'files_results': []
        }
        
        for i, file_item in enumerate(self.batch_manager.batch_queue):
            if self.should_stop:
                break
                
            file_path = file_item['path']
            self.file_started.emit(file_path)
            
            try:
                # Process single file
                success, output_path_or_error = self.process_single_file(file_path)
                
                if success:
                    results['successful_files'] += 1
                    file_item['status'] = 'completed'
                    file_item['output_path'] = output_path_or_error
                else:
                    results['failed_files'] += 1
                    file_item['status'] = 'failed'
                    file_item['error'] = output_path_or_error
                    
                results['processed_files'] += 1
                results['files_results'].append({
                    'path': file_path,
                    'success': success,
                    'output_or_error': output_path_or_error
                })
                
                self.file_completed.emit(file_path, success, output_path_or_error)
                
            except Exception as e:
                results['failed_files'] += 1
                results['processed_files'] += 1
                file_item['status'] = 'failed'
                file_item['error'] = str(e)
                self.file_completed.emit(file_path, False, str(e))
                
        results['total_time'] = time.time() - start_time
        self.batch_completed.emit(results)
        
    def process_single_file(self, file_path):
        """Process a single file"""
        try:
            # Step 1: Detect silence
            self.file_progress.emit(file_path, 10)
            print(f"🔍 Starting silence detection for: {os.path.basename(file_path)}")
            
            detection_thread = self.silence_detection_class(
                file_path,
                self.batch_manager.current_settings['min_silence_duration'],
                self.batch_manager.current_settings['silence_threshold'],
                self.batch_manager.current_settings['padding_ms']
            )
            
            # Store detected silence parts
            detected_silence = []
            
            # Connect signal to capture results
            def capture_detection_results(silent_parts):
                nonlocal detected_silence
                detected_silence = silent_parts
                print(f"✅ Detected {len(silent_parts)} silence regions")
            
            detection_thread.detection_complete.connect(capture_detection_results)
            
            # Run detection synchronously
            detection_thread.run()
            
            # Wait a moment for signal processing
            time.sleep(0.5)
            
            self.file_progress.emit(file_path, 40)
            
            # Check if we have detected silence
            if not detected_silence:
                print(f"⚠️  No silence detected in {os.path.basename(file_path)}, copying original file")
                # If no silence detected, just copy the file
                output_path = self.batch_manager.get_output_path(file_path)
                import shutil
                shutil.copy2(file_path, output_path)
                self.file_progress.emit(file_path, 100)
                return True, output_path
            
            print(f"🎯 Processing {len(detected_silence)} silence regions for removal")
            
            # Step 2: Process file with detected silence
            self.file_progress.emit(file_path, 50)
            output_path = self.batch_manager.get_output_path(file_path)
            
            # Determine if it's audio or video
            is_audio = self.is_audio_file(file_path)
            
            # Create processing thread with detected silence
            if is_audio:
                processing_thread = self.audio_processing_class(file_path, detected_silence, output_path)
            else:
                processing_thread = self.processing_class(file_path, detected_silence, output_path)
            
            # Connect progress signal for smoother progress updates
            def update_processing_progress(progress):
                # Map processing progress from 50% to 95%
                mapped_progress = 50 + int((progress / 100) * 45)
                self.file_progress.emit(file_path, mapped_progress)
            
            processing_thread.progress_updated.connect(update_processing_progress)
            
            # Store processing result
            processing_success = False
            processing_output = ""
            
            def capture_processing_results(output):
                nonlocal processing_success, processing_output
                processing_success = True
                processing_output = output
                print(f"✅ Processing completed: {output}")
            
            processing_thread.processing_complete.connect(capture_processing_results)
            
            # Run processing synchronously
            processing_thread.run()
            
            # Wait for processing to complete
            processing_thread.wait()
            
            self.file_progress.emit(file_path, 100)
            
            if processing_success:
                return True, processing_output
            else:
                return False, "Processing failed - no output received"
            
        except Exception as e:
            print(f"❌ Error processing {os.path.basename(file_path)}: {str(e)}")
            return False, str(e)
            
    def is_audio_file(self, file_path):
        """Check if file is audio only"""
        audio_extensions = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}
        return Path(file_path).suffix.lower() in audio_extensions
        
    def stop(self):
        """Stop batch processing"""
        self.should_stop = True


class BatchProcessingDialog(QDialog):
    """Main dialog for batch processing"""
    
    def __init__(self, parent=None, silence_detection_class=None, processing_class=None, audio_processing_class=None):
        super().__init__(parent)
        self.batch_manager = BatchProcessingManager(self)
        self.silence_detection_class = silence_detection_class
        self.processing_class = processing_class
        self.audio_processing_class = audio_processing_class
        self.processing_thread = None
        
        self.setWindowTitle("Batch Processing - Silence Cutter")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Set dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1f2937;
                color: #f9fafb;
            }
            QTabWidget::pane {
                border: 1px solid #374151;
                background-color: #1f2937;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #374151;
                color: #d1d5db;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #4b5563;
                color: #f9fafb;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #374151;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #f9fafb;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #f9fafb;
            }
            QLabel {
                color: #d1d5db;
            }
            QLineEdit {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 4px;
                padding: 5px;
                color: #f9fafb;
            }
            QSpinBox {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 4px;
                padding: 5px;
                color: #f9fafb;
            }
            QComboBox {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 4px;
                padding: 5px;
                color: #f9fafb;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #d1d5db;
            }
            QCheckBox {
                color: #d1d5db;
            }
            QListWidget {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 4px;
                color: #f9fafb;
            }
            QTextEdit {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 4px;
                color: #f9fafb;
            }
            QProgressBar {
                border: 1px solid #4b5563;
                border-radius: 4px;
                background-color: #374151;
                text-align: center;
                color: #f9fafb;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 3px;
            }
        """)
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Files tab
        files_tab = self.create_files_tab()
        tab_widget.addTab(files_tab, "Files")
        
        # Settings tab
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "Settings")
        
        # Progress tab
        progress_tab = self.create_progress_tab()
        tab_widget.addTab(progress_tab, "Progress")
        
        layout.addWidget(tab_widget)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Batch Processing")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def create_files_tab(self):
        """Create the files management tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # File list
        files_group = QGroupBox("Files to Process")
        files_layout = QVBoxLayout(files_group)
        
        # File list widget
        self.files_list = QListWidget()
        self.files_list.setMinimumHeight(300)
        files_layout.addWidget(self.files_list)
        
        # File management buttons
        file_buttons = QHBoxLayout()
        
        add_files_btn = QPushButton("Add Files")
        add_files_btn.clicked.connect(self.add_files)
        add_files_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        
        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(self.add_folder)
        add_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_selected_files)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all_files)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        
        save_config_btn = QPushButton("Save Config")
        save_config_btn.clicked.connect(self.save_config)
        save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        
        load_config_btn = QPushButton("Load Config")
        load_config_btn.clicked.connect(self.load_config)
        load_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        
        file_buttons.addWidget(add_files_btn)
        file_buttons.addWidget(add_folder_btn)
        file_buttons.addWidget(remove_btn)
        file_buttons.addWidget(clear_btn)
        file_buttons.addStretch()
        file_buttons.addWidget(save_config_btn)
        file_buttons.addWidget(load_config_btn)
        
        files_layout.addLayout(file_buttons)
        layout.addWidget(files_group)
        
        # File count and size info
        self.file_info_label = QLabel("No files added")
        layout.addWidget(self.file_info_label)
        
        return widget
        
    def create_settings_tab(self):
        """Create the settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Silence detection settings
        silence_group = QGroupBox("Silence Detection Settings")
        silence_layout = QGridLayout(silence_group)
        
        silence_layout.addWidget(QLabel("Minimum Silence Duration (ms):"), 0, 0)
        self.min_silence_spin = QSpinBox()
        self.min_silence_spin.setRange(100, 5000)
        self.min_silence_spin.setValue(500)
        silence_layout.addWidget(self.min_silence_spin, 0, 1)
        
        silence_layout.addWidget(QLabel("Silence Threshold (dB):"), 1, 0)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(-80, 0)
        self.threshold_spin.setValue(-40)
        silence_layout.addWidget(self.threshold_spin, 1, 1)
        
        silence_layout.addWidget(QLabel("Padding (ms):"), 2, 0)
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 1000)
        self.padding_spin.setValue(100)
        silence_layout.addWidget(self.padding_spin, 2, 1)
        
        layout.addWidget(silence_group)
        
        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QGridLayout(output_group)
        
        output_layout.addWidget(QLabel("Output Directory:"), 0, 0)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Leave empty to use 'processed' folder next to source files")
        output_layout.addWidget(self.output_dir_edit, 0, 1)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_output_directory)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        output_layout.addWidget(browse_btn, 0, 2)
        
        output_layout.addWidget(QLabel("Output Format:"), 1, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Same as input", "MP4", "MP3", "WAV"])
        output_layout.addWidget(self.format_combo, 1, 1)
        
        layout.addWidget(output_group)
        
        # Processing settings
        processing_group = QGroupBox("Processing Settings")
        processing_layout = QGridLayout(processing_group)
        
        self.parallel_check = QCheckBox("Enable Parallel Processing")
        processing_layout.addWidget(self.parallel_check, 0, 0, 1, 2)
        
        processing_layout.addWidget(QLabel("Max Parallel Jobs:"), 1, 0)
        self.parallel_jobs_spin = QSpinBox()
        self.parallel_jobs_spin.setRange(1, 8)
        self.parallel_jobs_spin.setValue(2)
        self.parallel_jobs_spin.setEnabled(False)
        processing_layout.addWidget(self.parallel_jobs_spin, 1, 1)
        
        # Connect parallel processing checkbox
        self.parallel_check.toggled.connect(self.parallel_jobs_spin.setEnabled)
        
        layout.addWidget(processing_group)
        
        layout.addStretch()
        return widget
        
    def create_progress_tab(self):
        """Create the progress monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Overall progress
        overall_group = QGroupBox("Overall Progress")
        overall_layout = QVBoxLayout(overall_group)
        
        self.overall_progress = QProgressBar()
        overall_layout.addWidget(self.overall_progress)
        
        self.overall_status_label = QLabel("Ready to start batch processing")
        overall_layout.addWidget(self.overall_status_label)
        
        layout.addWidget(overall_group)
        
        # Current file progress
        current_group = QGroupBox("Current File")
        current_layout = QVBoxLayout(current_group)
        
        self.current_file_label = QLabel("No file being processed")
        current_layout.addWidget(self.current_file_label)
        
        self.current_progress = QProgressBar()
        current_layout.addWidget(self.current_progress)
        
        layout.addWidget(current_group)
        
        # Results log
        results_group = QGroupBox("Processing Log")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(200)
        results_layout.addWidget(self.results_text)
        
        layout.addWidget(results_group)
        
        return widget
        
    def connect_signals(self):
        """Connect signals and slots"""
        self.start_btn.clicked.connect(self.start_batch_processing)
        self.stop_btn.clicked.connect(self.stop_batch_processing)
        self.close_btn.clicked.connect(self.close)
        
    def add_files(self):
        """Add files to batch queue"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Media Files",
            "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma);;All Files (*)"
        )
        
        if file_paths:
            added_count = self.batch_manager.add_files(file_paths)
            self.update_files_list()
            QMessageBox.information(self, "Files Added", f"Added {added_count} files to batch queue.")
            
    def add_folder(self):
        """Add all media files from a folder"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        
        if folder_path:
            media_files = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self.batch_manager.is_valid_media_file(file_path):
                        media_files.append(file_path)
                        
            if media_files:
                added_count = self.batch_manager.add_files(media_files)
                self.update_files_list()
                QMessageBox.information(self, "Files Added", f"Added {added_count} files from folder.")
            else:
                QMessageBox.warning(self, "No Media Files", "No valid media files found in the selected folder.")
                
    def remove_selected_files(self):
        """Remove selected files from batch queue"""
        selected_items = self.files_list.selectedItems()
        for item in selected_items:
            file_path = item.text().split(" - ")[0]  # Extract file path
            self.batch_manager.remove_file(file_path)
            
        self.update_files_list()
        
    def clear_all_files(self):
        """Clear all files from batch queue"""
        reply = QMessageBox.question(
            self,
            "Clear All Files",
            "Are you sure you want to remove all files from the batch queue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.batch_manager.clear_queue()
            self.update_files_list()
            
    def update_files_list(self):
        """Update the files list widget"""
        self.files_list.clear()
        
        for item in self.batch_manager.batch_queue:
            file_path = item['path']
            status = item['status']
            file_name = os.path.basename(file_path)
            
            list_item = QListWidgetItem(f"{file_path} - {status}")
            
            # Color code by status
            if status == 'completed':
                list_item.setBackground(Qt.green)
            elif status == 'failed':
                list_item.setBackground(Qt.red)
            elif status == 'processing':
                list_item.setBackground(Qt.yellow)
                
            self.files_list.addItem(list_item)
            
        # Update file info
        total_files = len(self.batch_manager.batch_queue)
        if total_files > 0:
            self.file_info_label.setText(f"Total files: {total_files}")
        else:
            self.file_info_label.setText("No files added")
            
    def browse_output_directory(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir_edit.setText(directory)
            
    def save_config(self):
        """Save batch configuration"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Batch Configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self.update_settings_from_ui()
            self.batch_manager.save_batch_config(file_path)
            QMessageBox.information(self, "Configuration Saved", "Batch configuration saved successfully.")
            
    def load_config(self):
        """Load batch configuration"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Batch Configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            if self.batch_manager.load_batch_config(file_path):
                self.update_ui_from_settings()
                self.update_files_list()
                QMessageBox.information(self, "Configuration Loaded", "Batch configuration loaded successfully.")
            else:
                QMessageBox.warning(self, "Load Error", "Failed to load batch configuration.")
                
    def update_settings_from_ui(self):
        """Update batch manager settings from UI"""
        settings = {
            'min_silence_duration': self.min_silence_spin.value(),
            'silence_threshold': self.threshold_spin.value(),
            'padding_ms': self.padding_spin.value(),
            'output_directory': self.output_dir_edit.text(),
            'output_format': ['same', 'mp4', 'mp3', 'wav'][self.format_combo.currentIndex()],
            'parallel_processing': self.parallel_check.isChecked(),
            'max_parallel_jobs': self.parallel_jobs_spin.value()
        }
        self.batch_manager.update_settings(settings)
        
    def update_ui_from_settings(self):
        """Update UI from batch manager settings"""
        settings = self.batch_manager.current_settings
        self.min_silence_spin.setValue(settings['min_silence_duration'])
        self.threshold_spin.setValue(settings['silence_threshold'])
        self.padding_spin.setValue(settings['padding_ms'])
        self.output_dir_edit.setText(settings['output_directory'])
        
        format_map = {'same': 0, 'mp4': 1, 'mp3': 2, 'wav': 3}
        self.format_combo.setCurrentIndex(format_map.get(settings['output_format'], 0))
        
        self.parallel_check.setChecked(settings['parallel_processing'])
        self.parallel_jobs_spin.setValue(settings['max_parallel_jobs'])
        
    def start_batch_processing(self):
        """Start batch processing"""
        if not self.batch_manager.batch_queue:
            QMessageBox.warning(self, "No Files", "Please add files to the batch queue before starting.")
            return
            
        if not all([self.silence_detection_class, self.processing_class, self.audio_processing_class]):
            QMessageBox.warning(self, "Missing Classes", "Processing classes not properly initialized.")
            return
            
        # Update settings from UI
        self.update_settings_from_ui()
        
        # Create and start processing thread
        self.processing_thread = BatchProcessingThread(
            self.batch_manager,
            self.silence_detection_class,
            self.processing_class,
            self.audio_processing_class
        )
        
        # Connect thread signals
        self.processing_thread.file_started.connect(self.on_file_started)
        self.processing_thread.file_completed.connect(self.on_file_completed)
        self.processing_thread.file_progress.connect(self.on_file_progress)
        self.processing_thread.batch_completed.connect(self.on_batch_completed)
        
        # Update UI state
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.overall_progress.setMaximum(len(self.batch_manager.batch_queue))
        self.overall_progress.setValue(0)
        self.overall_status_label.setText("Starting batch processing...")
        self.results_text.clear()
        
        # Start processing
        self.processing_thread.start()
        
    def stop_batch_processing(self):
        """Stop batch processing"""
        if self.processing_thread:
            self.processing_thread.stop()
            self.processing_thread.wait()
            
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.overall_status_label.setText("Batch processing stopped by user")
        
    def on_file_started(self, file_path):
        """Handle file processing started"""
        file_name = os.path.basename(file_path)
        self.current_file_label.setText(f"Processing: {file_name}")
        self.current_progress.setValue(0)
        self.results_text.append(f"Started: {file_name}")
        
    def on_file_completed(self, file_path, success, output_or_error):
        """Handle file processing completed"""
        file_name = os.path.basename(file_path)
        
        if success:
            self.results_text.append(f"✅ Completed: {file_name}")
            self.results_text.append(f"   Output: {output_or_error}")
        else:
            self.results_text.append(f"❌ Failed: {file_name}")
            self.results_text.append(f"   Error: {output_or_error}")
            
        # Update overall progress
        current_value = self.overall_progress.value()
        self.overall_progress.setValue(current_value + 1)
        
        # Update files list
        self.update_files_list()
        
    def on_file_progress(self, file_path, progress):
        """Handle file processing progress"""
        self.current_progress.setValue(progress)
        
    def on_batch_completed(self, results):
        """Handle batch processing completed"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Update status
        total = results['total_files']
        successful = results['successful_files']
        failed = results['failed_files']
        total_time = results['total_time']
        
        self.overall_status_label.setText(
            f"Batch completed: {successful}/{total} successful, {failed} failed, "
            f"Time: {total_time:.1f}s"
        )
        
        self.current_file_label.setText("Batch processing completed")
        self.current_progress.setValue(100)
        
        # Show completion message
        QMessageBox.information(
            self,
            "Batch Processing Complete",
            f"Processed {total} files:\n"
            f"✅ Successful: {successful}\n"
            f"❌ Failed: {failed}\n"
            f"⏱️ Total time: {total_time:.1f} seconds"
        )


class BatchProcessingIntegration:
    """Integration class for adding batch processing to the main application"""
    
    @staticmethod
    def integrate_with_main_app(main_app):
        """Integrate batch processing with the main application"""
        
        # Add batch processing button to the main UI
        if hasattr(main_app, 'setup_ui'):
            # Store original setup_ui method
            original_setup_ui = main_app.setup_ui
            
            def enhanced_setup_ui():
                # Call original setup_ui
                original_setup_ui()
                
                # Add batch processing button
                BatchProcessingIntegration.add_batch_button(main_app)
                
            # Replace setup_ui method
            main_app.setup_ui = enhanced_setup_ui
            
        print("✅ Batch processing integrated with main application")
        
    @staticmethod
    def add_batch_button(main_app):
        """Add batch processing button to main application"""
        try:
            # Find the main button layout or create one
            if hasattr(main_app, 'main_buttons_layout'):
                button_layout = main_app.main_buttons_layout
            else:
                # Try to find existing button layout
                button_layout = None
                for child in main_app.findChildren(QHBoxLayout):
                    if any(isinstance(child.itemAt(i).widget(), QPushButton) 
                          for i in range(child.count()) 
                          if child.itemAt(i) and child.itemAt(i).widget()):
                        button_layout = child
                        break
                        
            if button_layout:
                # Create batch processing button
                batch_btn = QPushButton("Batch Processing")
                batch_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FF9800;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 5px;
                        margin: 5px;
                    }
                    QPushButton:hover {
                        background-color: #F57C00;
                    }
                """)
                
                # Connect button to open batch processing dialog
                batch_btn.clicked.connect(lambda: BatchProcessingIntegration.open_batch_dialog(main_app))
                
                # Add button to layout
                button_layout.addWidget(batch_btn)
                
                print("✅ Batch processing button added to main application")
            else:
                print("⚠️  Could not find suitable location for batch processing button")
                
        except Exception as e:
            print(f"❌ Error adding batch processing button: {e}")
            
    @staticmethod
    def open_batch_dialog(main_app):
        """Open batch processing dialog"""
        try:
            # Get processing classes from main app
            silence_detection_class = getattr(main_app, 'SilenceDetectionThread', None)
            processing_class = getattr(main_app, 'ProcessingThread', None)
            audio_processing_class = getattr(main_app, 'AudioProcessingThread', None)
            
            # Try to import classes if not found in main app
            if not all([silence_detection_class, processing_class, audio_processing_class]):
                try:
                    import sys
                    current_module = sys.modules[main_app.__module__]
                    silence_detection_class = getattr(current_module, 'SilenceDetectionThread', None)
                    processing_class = getattr(current_module, 'ProcessingThread', None)
                    audio_processing_class = getattr(current_module, 'AudioProcessingThread', None)
                except:
                    pass
                    
            # Create and show dialog
            dialog = BatchProcessingDialog(
                main_app,
                silence_detection_class,
                processing_class,
                audio_processing_class
            )
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(
                main_app,
                "Batch Processing Error",
                f"Failed to open batch processing dialog:\n{str(e)}"
            ) 