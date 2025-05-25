@echo off
echo Video Silence Cutter - Direct Processing

if "%~1"=="" (
    echo No video file specified.
    echo Usage: process_video.bat [video_file_path]
    echo Example: process_video.bat "C:\Videos\my_video.mp4"
    exit /b 1
)

echo Processing video: %1
powershell -Command "Start-Process 'python' -ArgumentList 'silence_cutter.py', '%~1' -Verb RunAs"

echo.
echo Video processing started. The application will open with your video loaded. 