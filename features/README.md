# Manual Cutting Feature

This feature adds manual cutting functionality to the Silence Cutter application, allowing users to manually select and cut specific regions from their videos/audio files.

## Features

- **Manual Selection**: Use Shift + Click to select regions between the playhead and click position
- **Visual Feedback**: Selected regions are highlighted in red with an "M" indicator
- **Cut Selected Regions**: Use Ctrl + X to cut (remove) selected manual regions
- **Integration with Silence Detection**: Manual cuts work alongside automatically detected silence regions
- **Preview Support**: Manual cuts are included in preview mode and final output

## Recent Fixes (Latest Version)

### ✅ Fixed Issues:

1. **Single Shift+Click**: Now creates manual cuts with just one Shift+Click (no two-click requirement)
2. **Double-Click Removal**: Double-click on manual cuts to completely remove them
3. **Ctrl+X Functionality**: Now properly removes manual cuts from timeline and updates preview
4. **Export Button**: Now activates when manual cuts are selected
5. **Preview Integration**: Manual cuts now properly affect audio/video preview playback
6. **Timeline Visualization**: Manual cuts are properly displayed and removed from timeline
7. **Overlapping Cuts**: Shift+Click removes ALL overlapping cuts and creates new extended selection
8. **Extended Area Selection**: Properly handles extended selections without double layering

### 🎯 How It Works Now:

- **Shift+Click**: Single click creates manual cut between playhead and click position
- **Extended Selection**: Shift+Click removes any overlapping cuts and creates new extended area
- **Double-Click**: Completely removes manual cuts from timeline
- **Ctrl+X**: Removes selected manual cuts and updates preview immediately
- **Preview Mode**: Manual cuts are skipped during playback just like silence regions
- **Export**: Manual cuts are included in final video processing

## How to Use

### 1. Creating Manual Cuts

1. **Load a video/audio file** in the Silence Cutter application
2. **Position the playhead** where you want to start your cut by clicking on the timeline
3. **Hold Shift and click** on the timeline where you want to end your cut
   - **Single click**: Creates manual cut immediately between playhead and click position
   - The region will be highlighted in red with an "M" indicator
   - **Replacing cuts**: Shift+Click on existing cut area replaces it with new cut
4. **Repeat** to create multiple manual cuts as needed

### 2. Managing Manual Cuts

- **Remove**: Double-click on manual cut regions to completely remove them
- **Cut Selected Regions**: Press **Ctrl + X** to remove all selected manual cuts
- **Visual Indicators**:
  - **Bright red**: Selected manual cuts (will be removed in output)
  - **Faded red**: Unselected manual cuts (will be kept in output)
  - **"M" label**: Distinguishes manual cuts from silence regions

### 3. Processing with Manual Cuts

1. **Select regions** you want to remove (both silence regions and manual cuts)
2. **Click "Export Processed Media"** to process your file
3. The output will have all selected regions (silence + manual cuts) removed
4. Manual cuts are processed in the same way as silence regions

## Keyboard Shortcuts

| Shortcut          | Action                           |
| ----------------- | -------------------------------- |
| **Shift + Click** | Create manual cut (single click) |
| **Double Click**  | Remove manual cut completely     |
| **Ctrl + X**      | Remove selected manual cuts      |

## Technical Details

### File Structure

- `features/manual_cutting.py` - Core manual cutting functionality
- `features/__init__.py` - Package initialization
- Integration code added to main `silence_cutter.py`

### Classes

- **ManualCuttingManager**: Manages manual cuts, selection state, and processing
- **ManualCuttingIntegration**: Handles integration with existing timeline and video player

### Integration Points

1. **Timeline Widget**: Enhanced mouse and keyboard event handling
2. **Video Player**: Keyboard shortcut support
3. **Processing Threads**: Automatic inclusion of manual cuts in video processing
4. **Preview Mode**: Manual cuts are included in preview playback

## Compatibility

- Works with both video and audio files
- Compatible with existing silence detection
- Maintains all existing functionality
- Graceful fallback if feature is not available

## Troubleshooting

### Manual Cutting Not Working

1. **Check Console Output**: Look for "✅ Manual cutting feature loaded successfully"
2. **Verify Integration**: Should see "✅ Manual cutting integrated with timeline and video player"
3. **File Loading**: Make sure a video/audio file is loaded before trying to create cuts

### Selection Issues

- **Minimum Duration**: Manual cuts must be at least 0.1 seconds long
- **Timeline Focus**: Make sure the timeline widget has focus when using shortcuts
- **Playhead Position**: Ensure the playhead is positioned before starting selection

### Processing Issues

- Manual cuts are automatically included in processing
- Check that manual cuts are selected (bright red) before processing
- Manual cuts are sorted by start time and processed with silence regions

## Future Enhancements

Potential improvements for future versions:

- **Drag to Create**: Click and drag to create manual cuts
- **Precise Editing**: Numeric input for exact cut times
- **Cut Presets**: Save and load common cut patterns
- **Undo/Redo**: Enhanced undo system for manual cuts
- **Export Cuts**: Save manual cut data for reuse

## Support

If you encounter issues with the manual cutting feature:

1. Check the console output for error messages
2. Verify that the `features` directory is in the same location as `silence_cutter.py`
3. Ensure all dependencies are installed
4. Try restarting the application

The manual cutting feature is designed to be non-intrusive - if it fails to load, the application will continue to work normally with just the automatic silence detection.
