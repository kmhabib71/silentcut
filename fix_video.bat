@echo off
setlocal enabledelayedexpansion

echo Video Fixer for Silence Cutter
echo ------------------------------
echo.

if "%~1"=="" (
    echo Please drag and drop a video file onto this batch file.
    echo Usage: fix_video.bat [video_file]
    echo.
    pause
    exit /b 1
)

set "input_file=%~1"
set "output_file=%~dp1fixed_%~nx1"

echo Input: %input_file%
echo Output: %output_file%
echo.
echo Creating a clean copy of the video with standard parameters...
echo This may take a few minutes depending on the size of the video.
echo.

:: Check if FFmpeg exists in PATH
where ffmpeg >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FFmpeg not found in PATH. Checking standard locations...
    
    if exist "C:\ffmpeg\bin\ffmpeg.exe" (
        set "ffmpeg_cmd=C:\ffmpeg\bin\ffmpeg.exe"
    ) else if exist "%~dp0ffmpeg.exe" (
        set "ffmpeg_cmd=%~dp0ffmpeg.exe"
    ) else (
        echo FFmpeg not found. Please install FFmpeg first.
        echo You can run reinstall_ffmpeg.bat to install FFmpeg.
        pause
        exit /b 1
    )
) else (
    set "ffmpeg_cmd=ffmpeg"
)

echo Using FFmpeg: !ffmpeg_cmd!
echo.

:: Run FFmpeg with standard parameters for maximum compatibility
"!ffmpeg_cmd!" -i "%input_file%" -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k -pix_fmt yuv420p -movflags +faststart -y "%output_file%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Failed to convert the video. There might be an issue with the input file.
    echo Please check the FFmpeg error messages above.
) else (
    echo.
    echo Video conversion completed successfully!
    echo.
    echo The fixed video has been saved to:
    echo %output_file%
    echo.
    echo You can now use this video with the Silence Cutter app.
)

echo.
pause 