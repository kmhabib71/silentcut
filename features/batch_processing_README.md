# Batch Processing Feature

This feature adds comprehensive batch processing functionality to the Silence Cutter application, allowing users to process multiple audio and video files at once with the same silence detection and cutting settings.

## 🔧 Recent Fixes (Latest Version)

### ✅ Critical Issues Resolved:

1. **Silence Detection Integration**: Fixed issue where silence wasn't being removed from output files

   - Now properly captures and passes detected silence regions to processing threads
   - Added signal connections to ensure silence detection results are used
   - Improved error handling for files with no detected silence

2. **UI Visibility**: Fixed tab text visibility issues

   - Added comprehensive dark theme styling for all UI components
   - Tab text now properly visible with contrasting colors
   - Improved button styling with color-coded actions (blue=add, red=remove, green=save, purple=load)

3. **Progress Tracking**: Fixed progress getting stuck at 75%

   - Implemented smooth progress mapping from detection (0-40%) to processing (50-95%)
   - Added real-time progress updates during file processing
   - Connected processing thread progress signals for accurate feedback

4. **Enhanced Error Handling**: Improved error reporting and logging
   - Added detailed console output for debugging
   - Better handling of processing failures
   - Graceful fallback for files with no silence detected

## Features

### 🎯 Core Functionality

- **Multi-file Processing**: Add multiple audio/video files to a batch queue
- **Unified Settings**: Apply the same silence detection settings to all files
- **Sequential Processing**: Process files one by one with progress tracking
- **Format Support**: Supports all major audio and video formats
- **Output Organization**: Flexible output directory and format options

### 📊 Progress Tracking

- **Overall Progress**: Track progress across the entire batch
- **Individual File Progress**: Monitor each file's processing status
- **Real-time Log**: View detailed processing log with success/failure status
- **Visual Status Indicators**: Color-coded file status in the queue

### ⚙️ Advanced Options

- **Save/Load Configurations**: Save batch setups for reuse
- **Output Format Control**: Choose output format (same as input, MP4, MP3, WAV)
- **Custom Output Directory**: Specify where processed files should be saved
- **Parallel Processing**: Option for future parallel processing implementation

## How to Use

### 1. Opening Batch Processing

1. **Launch the main Silence Cutter application**
2. **Click the "Batch Processing" button** in the main interface
   - The button has an orange background and is located with other main controls
3. **The Batch Processing dialog will open** with three tabs: Files, Settings, and Progress

### 2. Adding Files to Process

#### **Files Tab**

- **Add Files**: Click "Add Files" to select individual media files
- **Add Folder**: Click "Add Folder" to add all media files from a directory
- **Remove Selected**: Select files in the list and click "Remove Selected"
- **Clear All**: Remove all files from the batch queue

#### **Supported File Types**

- **Video**: MP4, AVI, MOV, MKV, WMV, FLV, WebM
- **Audio**: MP3, WAV, AAC, FLAC, OGG, M4A, WMA

### 3. Configuring Settings

#### **Settings Tab**

**Silence Detection Settings:**

- **Minimum Silence Duration**: How long silence must be to be detected (100-5000ms)
- **Silence Threshold**: Volume level considered as silence (-80 to 0 dB)
- **Padding**: Extra time to keep around non-silent parts (0-1000ms)

**Output Settings:**

- **Output Directory**: Where to save processed files
  - Leave empty to create a "processed" folder next to source files
  - Or specify a custom directory
- **Output Format**: Choose the format for processed files
  - "Same as input": Keep original format
  - "MP4": Convert all to MP4 video
  - "MP3": Convert all to MP3 audio
  - "WAV": Convert all to WAV audio

**Processing Settings:**

- **Parallel Processing**: Enable for future parallel processing (currently disabled)
- **Max Parallel Jobs**: Number of files to process simultaneously (1-8)

### 4. Processing Files

#### **Starting the Batch**

1. **Switch to Progress Tab** to monitor processing
2. **Click "Start Batch Processing"** to begin
3. **Monitor progress** in real-time:
   - Overall progress bar shows batch completion
   - Current file progress shows individual file status
   - Processing log displays detailed information

#### **During Processing**

- **Current File**: Shows which file is being processed
- **Progress Indicators**: Visual progress for current file and overall batch
- **Live Log**: Real-time updates with success/failure messages
- **Stop Option**: Click "Stop Processing" to halt the batch

#### **After Completion**

- **Summary Dialog**: Shows total files processed, successes, failures, and time taken
- **File Status**: Files in the queue are color-coded:
  - 🟢 **Green**: Successfully processed
  - 🔴 **Red**: Failed to process
  - 🟡 **Yellow**: Currently processing
  - ⚪ **White**: Pending

### 5. Configuration Management

#### **Save Configuration**

- **Save Settings**: Click "Save Config" to save current settings and file list
- **JSON Format**: Configurations are saved as JSON files for easy sharing
- **Reusable**: Load saved configurations for repeated batch operations

#### **Load Configuration**

- **Load Settings**: Click "Load Config" to restore a saved configuration
- **Automatic Setup**: Files and settings are automatically restored
- **Quick Start**: Perfect for regular batch processing workflows

## Output Organization

### Default Behavior

- **Processed Folder**: Creates a "processed" folder next to each source file
- **Naming Convention**: Adds "\_processed" suffix to original filename
- **Format Preservation**: Keeps original format unless specified otherwise

### Custom Output

- **Single Directory**: All processed files go to specified output directory
- **Format Conversion**: Convert all files to chosen format (MP4, MP3, WAV)
- **Organized Structure**: Maintains clear organization of processed files

## Technical Details

### File Processing Pipeline

1. **Silence Detection**: Analyze each file for silent regions
2. **Cut Processing**: Remove detected silent parts
3. **Format Handling**: Apply output format conversion if needed
4. **File Saving**: Save processed file to designated location

### Error Handling

- **Individual File Errors**: Failed files don't stop the entire batch
- **Detailed Logging**: Error messages are logged for troubleshooting
- **Graceful Recovery**: Batch continues with remaining files after errors

### Performance Considerations

- **Sequential Processing**: Files are processed one at a time for stability
- **Memory Management**: Efficient handling of large files and batches
- **Progress Feedback**: Real-time updates without blocking the UI

## Integration with Main Application

### Seamless Integration

- **Non-Intrusive**: Doesn't modify existing functionality
- **Shared Settings**: Uses same silence detection algorithms as main app
- **Consistent UI**: Matches the main application's design and behavior

### Processing Classes

- **Reuses Existing Code**: Leverages main app's processing threads
- **Audio/Video Support**: Automatically detects and processes both file types
- **Same Quality**: Identical output quality to single-file processing

## Troubleshooting

### Common Issues

#### **"No Files" Warning**

- **Cause**: No files added to batch queue
- **Solution**: Add files using "Add Files" or "Add Folder" buttons

#### **"Missing Classes" Warning**

- **Cause**: Processing classes not properly initialized
- **Solution**: Ensure main application is fully loaded before opening batch processing

#### **Files Not Processing**

- **Check File Format**: Ensure files are supported media formats
- **Check Permissions**: Verify read/write permissions for source and output directories
- **Check Disk Space**: Ensure sufficient space for processed files

### Performance Tips

#### **Large Batches**

- **Process in Smaller Groups**: Break very large batches into smaller sets
- **Monitor System Resources**: Watch CPU and memory usage during processing
- **Use SSD Storage**: Faster storage improves processing speed

#### **Output Organization**

- **Use Custom Output Directory**: Centralize processed files for easier management
- **Choose Appropriate Format**: Consider file size vs. quality trade-offs
- **Clean Up Regularly**: Remove old processed files to save space

## Future Enhancements

### Planned Features

- **True Parallel Processing**: Process multiple files simultaneously
- **Advanced Filtering**: Filter files by duration, size, or format
- **Batch Templates**: Pre-configured settings for common use cases
- **Progress Persistence**: Resume interrupted batches
- **Cloud Integration**: Process files from cloud storage

### Customization Options

- **Custom Naming Patterns**: Flexible output file naming
- **Metadata Preservation**: Keep original file metadata
- **Quality Settings**: Fine-tune output quality parameters
- **Notification System**: Email or desktop notifications on completion

## Support and Feedback

### Getting Help

- **Console Output**: Check console for detailed error messages
- **Log Files**: Processing logs provide troubleshooting information
- **File Validation**: Ensure input files are valid and accessible

### Reporting Issues

- **Include Details**: Provide file types, batch size, and error messages
- **System Information**: Include OS and hardware specifications
- **Reproducible Steps**: Describe how to reproduce the issue

The batch processing feature is designed to handle large-scale silence cutting operations efficiently while maintaining the same high quality and reliability as single-file processing.
