"""
Manual Cutting Feature for Silence Cutter
Allows users to manually select and cut regions from the timeline.

Usage:
- Shift + Click: Start/End manual selection (marks region between playhead and click)
- Ctrl + X: Cut the selected manual region
- Manual cuts are treated like silence regions in preview and final output
"""

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPen, QBrush
from PyQt5.QtWidgets import QMessageBox
import copy


class ManualCuttingManager(QObject):
    """Manages manual cutting functionality"""
    
    # Signals
    manual_cut_added = pyqtSignal(dict)  # Emitted when a new manual cut is added
    manual_cut_removed = pyqtSignal(dict)  # Emitted when a manual cut is removed
    manual_cuts_changed = pyqtSignal(list)  # Emitted when manual cuts list changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Manual cuts storage - list of dicts with same format as silent_parts
        self.manual_cuts = []
        self.manual_cut_ranges = []  # List of (start_ms, end_ms) tuples
        
        # Selection state
        self.selection_start_time = None  # Time when Shift+Click started selection
        self.is_selecting = False
        self.current_playhead_position = 0.0
        
        # Visual settings for manual cuts
        self.manual_cut_color = QColor(255, 100, 100, 120)  # Red with transparency
        self.manual_cut_border_color = QColor(200, 50, 50, 200)  # Darker red border
        self.selection_preview_color = QColor(255, 150, 150, 80)  # Light red for preview
        
    def start_selection(self, playhead_position):
        """Start manual selection at current playhead position"""
        self.selection_start_time = playhead_position
        self.is_selecting = True
        print(f"🎯 Manual cutting: Started selection at {playhead_position:.3f}s")
        
    def preview_selection(self, current_position):
        """Preview the selection area (for visual feedback)"""
        if not self.is_selecting or self.selection_start_time is None:
            return None
            
        start_time = min(self.selection_start_time, current_position)
        end_time = max(self.selection_start_time, current_position)
        
        # Minimum selection of 0.1 seconds
        if end_time - start_time < 0.1:
            return None
            
        return {
            'start': start_time,
            'end': end_time,
            'duration_ms': int((end_time - start_time) * 1000)
        }
        
    def complete_selection(self, end_position):
        """Complete manual selection and create a manual cut"""
        if not self.is_selecting or self.selection_start_time is None:
            return False
            
        start_time = min(self.selection_start_time, end_position)
        end_time = max(self.selection_start_time, end_position)
        
        # Minimum cut duration of 0.1 seconds
        if end_time - start_time < 0.1:
            print(f"⚠️  Manual cutting: Selection too short ({end_time - start_time:.3f}s), minimum 0.1s required")
            self.cancel_selection()
            return False
            
        # Create manual cut
        manual_cut = {
            'start': start_time,
            'end': end_time,
            'duration_ms': int((end_time - start_time) * 1000),
            'selected': True,  # Manual cuts are selected by default
            'type': 'manual_cut',  # Distinguish from silence regions
            'id': len(self.manual_cuts)  # Simple ID system
        }
        
        # Add to storage
        self.manual_cuts.append(manual_cut)
        self.manual_cut_ranges.append((int(start_time * 1000), int(end_time * 1000)))
        
        print(f"✂️  Manual cutting: Created cut from {start_time:.3f}s to {end_time:.3f}s ({manual_cut['duration_ms']}ms)")
        
        # Reset selection state
        self.is_selecting = False
        self.selection_start_time = None
        
        # Emit signals
        self.manual_cut_added.emit(manual_cut)
        self.manual_cuts_changed.emit(self.manual_cuts)
        
        return True
        
    def cancel_selection(self):
        """Cancel current selection"""
        self.is_selecting = False
        self.selection_start_time = None
        print("❌ Manual cutting: Selection cancelled")
        
    def cut_selected_regions(self):
        """Cut (remove) all selected manual cut regions"""
        if not self.manual_cuts:
            return False
            
        # Find selected manual cuts
        selected_cuts = [cut for cut in self.manual_cuts if cut.get('selected', False)]
        
        if not selected_cuts:
            print("⚠️  Manual cutting: No manual cuts selected for cutting")
            return False
            
        # Remove selected cuts
        removed_cuts = []
        # Work backwards to avoid index issues
        for i in range(len(self.manual_cuts) - 1, -1, -1):
            cut = self.manual_cuts[i]
            if cut.get('selected', False):
                removed_cut = self.manual_cuts.pop(i)
                
                # Also remove from ranges
                if i < len(self.manual_cut_ranges):
                    self.manual_cut_ranges.pop(i)
                    
                removed_cuts.append(removed_cut)
                print(f"✂️  Manual cutting: Removed cut {removed_cut['start']:.3f}s - {removed_cut['end']:.3f}s")
                
                # Emit removal signal
                self.manual_cut_removed.emit(removed_cut)
        
        # Update IDs for remaining cuts
        for i, cut in enumerate(self.manual_cuts):
            cut['id'] = i
            
        # Emit changes signal
        self.manual_cuts_changed.emit(self.manual_cuts)
        
        print(f"✂️  Manual cutting: Removed {len(removed_cuts)} manual cuts")
        return len(removed_cuts) > 0
        
    def toggle_cut_selection(self, cut_index):
        """Toggle selection state of a manual cut"""
        if 0 <= cut_index < len(self.manual_cuts):
            self.manual_cuts[cut_index]['selected'] = not self.manual_cuts[cut_index]['selected']
            print(f"🎯 Manual cutting: Toggled cut {cut_index} selection to {self.manual_cuts[cut_index]['selected']}")
            return True
        return False
        
    def select_all_cuts(self):
        """Select all manual cuts"""
        for cut in self.manual_cuts:
            cut['selected'] = True
        print(f"🎯 Manual cutting: Selected all {len(self.manual_cuts)} manual cuts")
        self.manual_cuts_changed.emit(self.manual_cuts)
        
    def deselect_all_cuts(self):
        """Deselect all manual cuts"""
        for cut in self.manual_cuts:
            cut['selected'] = False
        print(f"🎯 Manual cutting: Deselected all manual cuts")
        self.manual_cuts_changed.emit(self.manual_cuts)
        
    def clear_all_cuts(self):
        """Clear all manual cuts"""
        if self.manual_cuts:
            print(f"🗑️  Manual cutting: Clearing {len(self.manual_cuts)} manual cuts")
            self.manual_cuts.clear()
            self.manual_cut_ranges.clear()
            self.manual_cuts_changed.emit(self.manual_cuts)
            
    def get_combined_cuts_for_processing(self, silent_parts=None):
        """
        Combine manual cuts with silence regions for processing.
        Returns a list suitable for video processing.
        """
        combined_cuts = []
        
        # Add manual cuts (only selected ones)
        for cut in self.manual_cuts:
            if cut.get('selected', False):
                combined_cuts.append({
                    'start': cut['start'],
                    'end': cut['end'],
                    'duration_ms': cut['duration_ms'],
                    'selected': True,
                    'type': 'manual_cut'
                })
                
        # Add silence regions if provided
        if silent_parts:
            for part in silent_parts:
                if part.get('selected', False):
                    combined_cuts.append({
                        'start': part['start'],
                        'end': part['end'],
                        'duration_ms': part['duration_ms'],
                        'selected': True,
                        'type': 'silence'
                    })
                    
        # Sort by start time
        combined_cuts.sort(key=lambda x: x['start'])
        
        print(f"🔄 Manual cutting: Combined {len([c for c in combined_cuts if c['type'] == 'manual_cut'])} manual cuts + {len([c for c in combined_cuts if c['type'] == 'silence'])} silence regions")
        
        return combined_cuts
        
    def get_combined_ranges_for_processing(self, silent_ranges=None):
        """
        Combine manual cut ranges with silence ranges for processing.
        Returns a list of (start_ms, end_ms) tuples.
        """
        combined_ranges = []
        
        # Add manual cut ranges (only selected ones)
        for i, cut in enumerate(self.manual_cuts):
            if cut.get('selected', False) and i < len(self.manual_cut_ranges):
                combined_ranges.append(self.manual_cut_ranges[i])
                
        # Add silence ranges if provided
        if silent_ranges:
            for i, part in enumerate(silent_ranges):
                # Assuming silent_ranges corresponds to silent_parts
                # We need to check if the corresponding silent part is selected
                # This requires access to silent_parts, so we'll handle this in the integration
                combined_ranges.append(part)
                
        # Sort by start time
        combined_ranges.sort(key=lambda x: x[0])
        
        return combined_ranges
        
    def find_cut_at_position(self, position, tolerance=0.1):
        """Find manual cut at given position with tolerance"""
        for i, cut in enumerate(self.manual_cuts):
            if cut['start'] - tolerance <= position <= cut['end'] + tolerance:
                return i
        return None
        
    def get_cut_info(self, cut_index):
        """Get information about a specific manual cut"""
        if 0 <= cut_index < len(self.manual_cuts):
            return self.manual_cuts[cut_index].copy()
        return None
        
    def format_time(self, seconds):
        """Format time for display"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:06.3f}"
        
    def get_stats(self):
        """Get statistics about manual cuts"""
        total_cuts = len(self.manual_cuts)
        selected_cuts = len([cut for cut in self.manual_cuts if cut.get('selected', False)])
        total_duration = sum(cut['duration_ms'] for cut in self.manual_cuts if cut.get('selected', False)) / 1000.0
        
        return {
            'total_cuts': total_cuts,
            'selected_cuts': selected_cuts,
            'total_duration_seconds': total_duration,
            'total_duration_formatted': self.format_time(total_duration)
        }


class ManualCuttingIntegration:
    """Integration helper for adding manual cutting to existing timeline and video player"""
    
    @staticmethod
    def integrate_with_timeline(timeline_widget, manual_cutting_manager):
        """Integrate manual cutting with TimelineWidget"""
        
        # Store reference to manual cutting manager
        timeline_widget.manual_cutting_manager = manual_cutting_manager
        
        # Store original methods
        timeline_widget._original_mousePressEvent = timeline_widget.mousePressEvent
        timeline_widget._original_keyPressEvent = timeline_widget.keyPressEvent
        timeline_widget._original_paintEvent = timeline_widget.paintEvent
        
        def enhanced_mousePressEvent(event):
            """Enhanced mouse press event with manual cutting support"""
            if event.button() == Qt.LeftButton and event.modifiers() == Qt.ShiftModifier:
                # Shift + Click for manual cutting (single click creates selection)
                if timeline_widget.duration_seconds > 0:
                    # Calculate timeline area
                    from PyQt5.QtCore import QRectF
                    timeline_rect = QRectF(
                        timeline_widget.margin,
                        (timeline_widget.height() - timeline_widget.timeline_height) / 2,
                        timeline_widget.width() - 2 * timeline_widget.margin,
                        timeline_widget.timeline_height
                    )
                    
                    if timeline_rect.contains(event.x(), event.y()):
                        click_time = timeline_widget.x_to_time(event.x(), timeline_rect)
                        playhead_time = timeline_widget.current_position
                        
                        # Create manual cut in single click (between playhead and click)
                        start_time = min(playhead_time, click_time)
                        end_time = max(playhead_time, click_time)
                        
                        # Check for any overlapping cuts in the entire new selection area
                        overlapping_cuts = []
                        for i, cut in enumerate(manual_cutting_manager.manual_cuts):
                            # Check if cuts overlap with new selection
                            if not (cut['end'] <= start_time or cut['start'] >= end_time):
                                overlapping_cuts.append(i)
                        
                        # Remove all overlapping cuts
                        if overlapping_cuts:
                            # Remove in reverse order to maintain indices
                            for i in reversed(overlapping_cuts):
                                removed_cut = manual_cutting_manager.manual_cuts.pop(i)
                                if i < len(manual_cutting_manager.manual_cut_ranges):
                                    manual_cutting_manager.manual_cut_ranges.pop(i)
                                print(f"🔄 Removed overlapping manual cut: {removed_cut['start']:.3f}s - {removed_cut['end']:.3f}s")
                            
                            # Update IDs for remaining cuts
                            for i, cut in enumerate(manual_cutting_manager.manual_cuts):
                                cut['id'] = i
                        
                        # Create new manual cut directly
                        if end_time - start_time >= 0.1:  # Minimum duration check
                            manual_cut = {
                                'start': start_time,
                                'end': end_time,
                                'duration_ms': int((end_time - start_time) * 1000),
                                'selected': True,
                                'type': 'manual_cut',
                                'id': len(manual_cutting_manager.manual_cuts)
                            }
                            
                            manual_cutting_manager.manual_cuts.append(manual_cut)
                            manual_cutting_manager.manual_cut_ranges.append((int(start_time * 1000), int(end_time * 1000)))
                            
                            print(f"✂️  Manual cut created: {start_time:.3f}s - {end_time:.3f}s")
                            
                            # Emit signals
                            manual_cutting_manager.manual_cut_added.emit(manual_cut)
                            manual_cutting_manager.manual_cuts_changed.emit(manual_cutting_manager.manual_cuts)
                            
                            timeline_widget.update()  # Redraw timeline
                            
                            # Trigger export button update
                            if hasattr(timeline_widget, 'parent') and hasattr(timeline_widget.parent(), 'parent'):
                                main_app = timeline_widget.parent().parent()
                                if hasattr(main_app, 'update_export_button_state'):
                                    main_app.update_export_button_state()
                        else:
                            print("⚠️  Manual cutting: Selection too short (minimum 0.1 seconds)")
                        
                        event.accept()
                        return
            elif event.button() == Qt.LeftButton and event.modifiers() == Qt.NoModifier:
                # Check for double-click to deselect manual cuts
                if hasattr(timeline_widget, '_last_click_time') and hasattr(timeline_widget, '_last_click_pos'):
                    import time
                    current_time = time.time()
                    if (current_time - timeline_widget._last_click_time < 0.5 and 
                        abs(event.x() - timeline_widget._last_click_pos) < 10):
                        # This is a double-click
                        from PyQt5.QtCore import QRectF
                        timeline_rect = QRectF(
                            timeline_widget.margin,
                            (timeline_widget.height() - timeline_widget.timeline_height) / 2,
                            timeline_widget.width() - 2 * timeline_widget.margin,
                            timeline_widget.timeline_height
                        )
                        
                        if timeline_rect.contains(event.x(), event.y()):
                            click_time = timeline_widget.x_to_time(event.x(), timeline_rect)
                            cut_index = manual_cutting_manager.find_cut_at_position(click_time, tolerance=0.5)
                            if cut_index is not None:
                                # Completely remove the cut
                                removed_cut = manual_cutting_manager.manual_cuts.pop(cut_index)
                                if cut_index < len(manual_cutting_manager.manual_cut_ranges):
                                    manual_cutting_manager.manual_cut_ranges.pop(cut_index)
                                
                                # Update IDs for remaining cuts
                                for i, cut in enumerate(manual_cutting_manager.manual_cuts):
                                    cut['id'] = i
                                
                                print(f"🗑️  Removed manual cut: {removed_cut['start']:.3f}s - {removed_cut['end']:.3f}s")
                                
                                # Emit signals
                                manual_cutting_manager.manual_cut_removed.emit(removed_cut)
                                manual_cutting_manager.manual_cuts_changed.emit(manual_cutting_manager.manual_cuts)
                                
                                timeline_widget.update()
                                
                                # Update preview mode to reflect removed cut
                                # Find the main application and video player
                                main_app = None
                                video_player = None
                                parent = timeline_widget.parent()
                                
                                # Find main application
                                while parent:
                                    if hasattr(parent, 'video_player') and hasattr(parent, 'silent_parts'):
                                        main_app = parent
                                        video_player = parent.video_player
                                        break
                                    parent = parent.parent()
                                
                                if main_app and video_player:
                                    # Get combined cuts for preview (silence + remaining manual cuts)
                                    combined_cuts = manual_cutting_manager.get_combined_cuts_for_processing(getattr(main_app, 'silent_parts', []))
                                    
                                    # Update main app's silent_parts with combined cuts
                                    main_app.silent_parts = combined_cuts
                                    
                                    # Update video player's silent_parts
                                    video_player.silent_parts = combined_cuts
                                    
                                    # Update timeline's silent_parts for proper preview
                                    timeline_widget.silent_parts = combined_cuts
                                    
                                    if combined_cuts:
                                        # Enable preview mode with combined cuts
                                        if hasattr(video_player, 'enable_preview_mode'):
                                            video_player.enable_preview_mode()
                                        elif hasattr(video_player, 'set_preview_mode'):
                                            video_player.set_preview_mode(True, combined_cuts)
                                        
                                        # Update timeline preview mode
                                        if hasattr(timeline_widget, 'set_preview_mode'):
                                            timeline_widget.set_preview_mode(True, combined_cuts)
                                    else:
                                        # No cuts left, disable preview mode
                                        if hasattr(video_player, 'set_preview_mode'):
                                            video_player.set_preview_mode(False)
                                        if hasattr(timeline_widget, 'set_preview_mode'):
                                            timeline_widget.set_preview_mode(False)
                                    
                                    print(f"🔄 Preview updated after removal: {len(combined_cuts)} total cuts")
                                
                                # Update export button
                                if hasattr(timeline_widget, 'parent') and hasattr(timeline_widget.parent(), 'parent'):
                                    main_app = timeline_widget.parent().parent()
                                    if hasattr(main_app, 'update_export_button_state'):
                                        main_app.update_export_button_state()
                                
                                event.accept()
                                return
                
                # Store click info for double-click detection
                import time
                timeline_widget._last_click_time = time.time()
                timeline_widget._last_click_pos = event.x()
            
            # Call original method for other cases
            timeline_widget._original_mousePressEvent(event)
            
        def enhanced_keyPressEvent(event):
            """Enhanced key press event with manual cutting support"""
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_X:
                # Ctrl + X for cutting selected regions
                if manual_cutting_manager.cut_selected_regions():
                    timeline_widget.update()  # Redraw timeline
                    
                    # Update preview mode to reflect removed cuts
                    # Find the main application and video player
                    main_app = None
                    video_player = None
                    parent = timeline_widget.parent()
                    
                    # Find main application
                    while parent:
                        if hasattr(parent, 'video_player') and hasattr(parent, 'silent_parts'):
                            main_app = parent
                            video_player = parent.video_player
                            break
                        parent = parent.parent()
                    
                    if main_app and video_player:
                        # Get combined cuts for preview (silence + remaining manual cuts)
                        combined_cuts = manual_cutting_manager.get_combined_cuts_for_processing(getattr(main_app, 'silent_parts', []))
                        
                        # Update main app's silent_parts with combined cuts
                        main_app.silent_parts = combined_cuts
                        
                        # Update video player's silent_parts
                        video_player.silent_parts = combined_cuts
                        
                        # Update timeline's silent_parts for proper preview
                        timeline_widget.silent_parts = combined_cuts
                        
                        if combined_cuts:
                            # Enable preview mode with combined cuts
                            if hasattr(video_player, 'enable_preview_mode'):
                                video_player.enable_preview_mode()
                            elif hasattr(video_player, 'set_preview_mode'):
                                video_player.set_preview_mode(True, combined_cuts)
                            
                            # Update timeline preview mode
                            if hasattr(timeline_widget, 'set_preview_mode'):
                                timeline_widget.set_preview_mode(True, combined_cuts)
                        else:
                            # No cuts left, disable preview mode
                            if hasattr(video_player, 'set_preview_mode'):
                                video_player.set_preview_mode(False)
                            if hasattr(timeline_widget, 'set_preview_mode'):
                                timeline_widget.set_preview_mode(False)
                        
                        print(f"🔄 Preview mode updated: {len(combined_cuts)} total cuts (silence + manual)")
                    
                    # Update export button state
                    if hasattr(timeline_widget, 'parent') and hasattr(timeline_widget.parent(), 'parent'):
                        main_app = timeline_widget.parent().parent()
                        if hasattr(main_app, 'update_export_button_state'):
                            main_app.update_export_button_state()
                            
                    print("✂️  Manual cuts removed and preview updated")
                event.accept()
                return
                
            # Call original method for other cases
            timeline_widget._original_keyPressEvent(event)
            
        def enhanced_paintEvent(event):
            """Enhanced paint event with manual cutting visualization"""
            # Call original paint method first
            timeline_widget._original_paintEvent(event)
            
            # Then draw manual cuts
            if hasattr(timeline_widget, 'manual_cutting_manager'):
                ManualCuttingIntegration.draw_manual_cuts(timeline_widget, event)
                
        # Replace methods
        timeline_widget.mousePressEvent = enhanced_mousePressEvent
        timeline_widget.keyPressEvent = enhanced_keyPressEvent
        timeline_widget.paintEvent = enhanced_paintEvent
        
        # Connect signals
        manual_cutting_manager.manual_cuts_changed.connect(timeline_widget.update)
        
        # Connect signal to update preview when manual cuts are added
        def update_preview_on_manual_cut_change():
            """Update preview mode when manual cuts change"""
            # Find the main application and video player
            main_app = None
            video_player = None
            parent = timeline_widget.parent()
            
            # Find main application
            while parent:
                if hasattr(parent, 'video_player') and hasattr(parent, 'silent_parts'):
                    main_app = parent
                    video_player = parent.video_player
                    break
                parent = parent.parent()
                
            if main_app and video_player:
                # Get combined cuts for preview (silence + manual cuts)
                combined_cuts = manual_cutting_manager.get_combined_cuts_for_processing(getattr(main_app, 'silent_parts', []))
                
                # Update main app's silent_parts with combined cuts
                main_app.silent_parts = combined_cuts
                
                # Update video player's silent_parts
                video_player.silent_parts = combined_cuts
                
                # Update timeline's silent_parts for proper preview
                timeline_widget.silent_parts = combined_cuts
                
                if combined_cuts:
                    # Enable preview mode with combined cuts
                    if hasattr(video_player, 'enable_preview_mode'):
                        video_player.enable_preview_mode()
                    elif hasattr(video_player, 'set_preview_mode'):
                        video_player.set_preview_mode(True, combined_cuts)
                    
                    # Update timeline preview mode
                    if hasattr(timeline_widget, 'set_preview_mode'):
                        timeline_widget.set_preview_mode(True, combined_cuts)
                    print(f"🔄 Preview updated: {len(combined_cuts)} total cuts (silence + manual)")
                else:
                    # No cuts, disable preview
                    if hasattr(video_player, 'set_preview_mode'):
                        video_player.set_preview_mode(False)
                    if hasattr(timeline_widget, 'set_preview_mode'):
                        timeline_widget.set_preview_mode(False)
                    
        # Connect the signals
        manual_cutting_manager.manual_cut_added.connect(update_preview_on_manual_cut_change)
        manual_cutting_manager.manual_cuts_changed.connect(update_preview_on_manual_cut_change)
        
        print("✅ Manual cutting integrated with timeline widget")
        
    @staticmethod
    def draw_manual_cuts(timeline_widget, paint_event):
        """Draw manual cuts on the timeline"""
        if not hasattr(timeline_widget, 'manual_cutting_manager'):
            return
            
        manager = timeline_widget.manual_cutting_manager
        
        if not manager.manual_cuts:
            return
            
        from PyQt5.QtGui import QPainter
        from PyQt5.QtCore import QRectF
        
        painter = QPainter(timeline_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate timeline area
        timeline_rect = QRectF(
            timeline_widget.margin,
            (timeline_widget.height() - timeline_widget.timeline_height) / 2,
            timeline_widget.width() - 2 * timeline_widget.margin,
            timeline_widget.timeline_height
        )
        
        # Draw existing manual cuts
        for i, cut in enumerate(manager.manual_cuts):
            start_x = timeline_widget.time_to_x(cut['start'], timeline_rect)
            end_x = timeline_widget.time_to_x(cut['end'], timeline_rect)
            
            # Skip if not visible
            if end_x < timeline_rect.left() or start_x > timeline_rect.right():
                continue
                
            # Clamp to visible area
            start_x = max(start_x, timeline_rect.left())
            end_x = min(end_x, timeline_rect.right())
            
            # Set colors based on selection
            if cut.get('selected', False):
                fill_color = manager.manual_cut_color
                border_color = manager.manual_cut_border_color
            else:
                fill_color = QColor(manager.manual_cut_color.red(), 
                                  manager.manual_cut_color.green(), 
                                  manager.manual_cut_color.blue(), 60)
                border_color = QColor(manager.manual_cut_border_color.red(), 
                                    manager.manual_cut_border_color.green(), 
                                    manager.manual_cut_border_color.blue(), 100)
            
            # Draw manual cut region
            cut_rect = QRectF(start_x, timeline_rect.top(), end_x - start_x, timeline_rect.height())
            painter.fillRect(cut_rect, QBrush(fill_color))
            painter.setPen(QPen(border_color, 2))
            painter.drawRect(cut_rect)
            
            # Draw "M" indicator for manual cuts
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(cut_rect, Qt.AlignCenter, "M")
            
        # No longer need selection preview since we create cuts directly
                
        painter.end()
        
    @staticmethod
    def integrate_with_video_player(video_player, manual_cutting_manager):
        """Integrate manual cutting with InteractiveVideoPlayer"""
        
        # Store reference
        video_player.manual_cutting_manager = manual_cutting_manager
        
        # Store original methods
        video_player._original_keyPressEvent = video_player.keyPressEvent
        
        def enhanced_keyPressEvent(event):
            """Enhanced key press event for video player"""
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_X:
                # Ctrl + X for cutting selected regions
                if manual_cutting_manager.cut_selected_regions():
                    # Update timeline if available
                    if hasattr(video_player, 'timeline') and video_player.timeline:
                        video_player.timeline.update()
                event.accept()
                return
                
            # Call original method for other cases
            video_player._original_keyPressEvent(event)
            
        # Replace method
        video_player.keyPressEvent = enhanced_keyPressEvent
        
        print("✅ Manual cutting integrated with video player")
        
    @staticmethod
    def integrate_with_processing(processing_thread_class, manual_cutting_manager):
        """Integrate manual cutting with video processing"""
        
        # Store original run method
        original_run = processing_thread_class.run
        
        def enhanced_run(self):
            """Enhanced run method that includes manual cuts"""
            # Get manual cuts and combine with silence regions
            if hasattr(self, 'silent_parts'):
                combined_cuts = manual_cutting_manager.get_combined_cuts_for_processing(self.silent_parts)
                
                # Update silent_parts to include manual cuts
                self.silent_parts = combined_cuts
                
                print(f"🔄 Processing: Including {len([c for c in combined_cuts if c.get('type') == 'manual_cut'])} manual cuts in processing")
            
            # Call original run method
            return original_run(self)
            
        # Replace run method
        processing_thread_class.run = enhanced_run
        
        print("✅ Manual cutting integrated with processing") 