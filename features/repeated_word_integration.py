#!/usr/bin/env python3
"""
Repeated Word Integration Module
Connects enhanced transcript with existing repeated word detection functionality
"""

import os
import sys
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QCheckBox, QProgressBar
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont

class RepeatedWordPreviewDialog(QDialog):
    """Dialog to preview and select repeated words for removal"""

    segments_selected = pyqtSignal(list)  # Emits selected segments for removal

    def __init__(self, analysis_result, parent=None):
        super().__init__(parent)
        self.analysis_result = analysis_result
        self.selected_segments = []
        self.setup_ui()
        self.populate_list()

    def setup_ui(self):
        """Set up the preview dialog UI"""
        self.setWindowTitle("Repeated Words & Phrases Preview")
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout()

        # Header
        header_label = QLabel("🔍 Repeated Words & Phrases Detection")
        header_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 600;
                color: #f9fafb;
                padding: 12px;
                background-color: #1f2937;
                border-radius: 8px;
                margin-bottom: 8px;
            }
        """)

        # Statistics
        repeated_count = len(self.analysis_result['repeated_words'])
        phrase_count = len(self.analysis_result['repeated_phrases'])
        total_time = self.analysis_result['total_repeated_time']

        stats_label = QLabel(
            f"Found {repeated_count} repeated words and {phrase_count} repeated phrases. "
            f"Total potential time savings: {total_time:.1f} seconds"
        )
        stats_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #d1d5db;
                padding: 8px;
                background-color: #374151;
                border-radius: 6px;
                margin-bottom: 8px;
            }
        """)

        # Instructions
        instructions_label = QLabel(
            "Select the repeated words/phrases you want to remove. "
            "The first occurrence of each will be kept, subsequent ones will be removed."
        )
        instructions_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #9ca3af;
                padding: 8px;
                margin-bottom: 8px;
            }
        """)

        # List widget for repeated items
        self.items_list = QListWidget()
        self.items_list.setStyleSheet("""
            QListWidget {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 8px;
                color: #f9fafb;
                font-size: 14px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #374151;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #374151;
            }
            QListWidget::item:selected {
                background-color: #8b5cf6;
                color: white;
            }
        """)

        # Control buttons
        controls_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 8px 16px;
                font-weight: 600;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        select_all_btn.clicked.connect(self.select_all_items)

        select_none_btn = QPushButton("Select None")
        select_none_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                padding: 8px 16px;
                font-weight: 600;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        select_none_btn.clicked.connect(self.select_no_items)

        controls_layout.addWidget(select_all_btn)
        controls_layout.addWidget(select_none_btn)
        controls_layout.addStretch()

        # Action buttons
        action_layout = QHBoxLayout()

        preview_btn = QPushButton("🎬 Preview Removal")
        preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                padding: 12px 20px;
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
        """)
        preview_btn.clicked.connect(self.preview_removal)

        apply_btn = QPushButton("✂️ Apply Removal")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                padding: 12px 20px;
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
        """)
        apply_btn.clicked.connect(self.apply_removal)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                padding: 12px 20px;
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        action_layout.addWidget(preview_btn)
        action_layout.addWidget(apply_btn)
        action_layout.addStretch()
        action_layout.addWidget(cancel_btn)

        # Add all widgets to layout
        layout.addWidget(header_label)
        layout.addWidget(stats_label)
        layout.addWidget(instructions_label)
        layout.addWidget(self.items_list, 1)
        layout.addLayout(controls_layout)
        layout.addLayout(action_layout)

        self.setLayout(layout)

    def populate_list(self):
        """Populate the list with repeated words and phrases"""
        # Sort candidates by potential time savings
        candidates = sorted(
            self.analysis_result['removal_candidates'],
            key=lambda x: x['duration'] * x['count'],
            reverse=True
        )

        for candidate in candidates:
            if candidate['count'] > 2:  # Only show significantly repeated items
                # Create list item
                item_text = f"{candidate['text']} ({candidate['type']})"
                detail_text = f"Repeated {candidate['count']} times • {candidate['duration']:.1f}s each • Total savings: {candidate['duration'] * (candidate['count'] - 1):.1f}s"

                item = QListWidgetItem()
                item.setText(f"{item_text}\n{detail_text}")
                item.setData(Qt.UserRole, candidate)
                item.setCheckState(Qt.Unchecked)

                # Color code by type
                if candidate['type'] == 'word':
                    item.setBackground(Qt.darkBlue)
                else:
                    item.setBackground(Qt.darkGreen)

                self.items_list.addItem(item)

    def select_all_items(self):
        """Select all items in the list"""
        for i in range(self.items_list.count()):
            item = self.items_list.item(i)
            item.setCheckState(Qt.Checked)

    def select_no_items(self):
        """Deselect all items in the list"""
        for i in range(self.items_list.count()):
            item = self.items_list.item(i)
            item.setCheckState(Qt.Unchecked)

    def get_selected_segments(self):
        """Get segments for selected repeated words/phrases"""
        segments = []

        for i in range(self.items_list.count()):
            item = self.items_list.item(i)
            if item.checkState() == Qt.Checked:
                candidate = item.data(Qt.UserRole)

                # Create segment for removal (skip first occurrence)
                segments.append({
                    'start': candidate['start'],
                    'end': candidate['end'],
                    'type': 'repeated_word',
                    'text': candidate['text'],
                    'duration': candidate['duration'],
                    'selected': True
                })

        return segments

    def preview_removal(self):
        """Preview the removal (similar to silence detection preview)"""
        segments = self.get_selected_segments()
        if not segments:
            return

        # Emit segments for preview
        self.segments_selected.emit(segments)

    def apply_removal(self):
        """Apply the removal and close dialog"""
        segments = self.get_selected_segments()
        if not segments:
            self.reject()
            return

        self.selected_segments = segments
        self.accept()

def integrate_repeated_words_with_app(app_instance):
    """Integrate repeated word detection with the main application"""

    def on_repeated_words_detected(analysis_result):
        """Handle repeated words detection from transcript"""
        try:
            # Show preview dialog
            dialog = RepeatedWordPreviewDialog(analysis_result, app_instance)

            # Connect preview signal to existing preview functionality
            if hasattr(app_instance, 'apply_repeated_words_preview'):
                dialog.segments_selected.connect(
                    lambda segments: app_instance.apply_repeated_words_preview(segments)
                )

            # Show dialog
            if dialog.exec_() == QDialog.Accepted:
                segments = dialog.selected_segments
                if segments:
                    # Apply removal using existing functionality
                    if hasattr(app_instance, 'apply_repeated_words_removal'):
                        app_instance.apply_repeated_words_removal(segments)
                    else:
                        pass

        except Exception as e:
            print(f"❌ Failed to handle repeated words detection: {e}")

    # Store the handler function
    app_instance.on_repeated_words_detected = on_repeated_words_detected


def add_repeated_words_to_silence_segments(silence_segments, repeated_word_segments):
    """Combine silence segments with repeated word segments for unified processing"""
    combined_segments = []

    # Add silence segments
    for segment in silence_segments:
        combined_segments.append({
            'start': segment['start'],
            'end': segment['end'],
            'type': 'silence',
            'duration': segment['end'] - segment['start'],
            'selected': segment.get('selected', False)
        })

    # Add repeated word segments
    for segment in repeated_word_segments:
        combined_segments.append({
            'start': segment['start'],
            'end': segment['end'],
            'type': 'repeated_word',
            'text': segment.get('text', ''),
            'duration': segment['duration'],
            'selected': segment.get('selected', False)
        })

    # Sort by start time
    combined_segments.sort(key=lambda x: x['start'])

    return combined_segments

# Export main functions
__all__ = ['RepeatedWordPreviewDialog', 'integrate_repeated_words_with_app', 'add_repeated_words_to_silence_segments']
