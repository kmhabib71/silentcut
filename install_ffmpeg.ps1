# Script to download and install FFmpeg on Windows
Write-Host "Starting FFmpeg installation..." -ForegroundColor Cyan

# Get the current directory (handles spaces in paths)
$currentDir = Get-Location

# Create a temporary directory in the user's temp folder to avoid path issues
$tempDir = Join-Path $env:TEMP "ffmpeg_temp"
if (Test-Path $tempDir) {
    Remove-Item -Path $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
Write-Host "Created temporary directory at: $tempDir" -ForegroundColor Green

# Download FFmpeg
Write-Host "Downloading FFmpeg from gyan.dev..." -ForegroundColor Cyan
$url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$output = Join-Path $tempDir "ffmpeg.zip"
try {
    Invoke-WebRequest -Uri $url -OutFile $output
    Write-Host "Download complete." -ForegroundColor Green
} catch {
    Write-Host "Failed to download FFmpeg. Error: $_" -ForegroundColor Red
    exit 1
}

# Extract FFmpeg
Write-Host "Extracting FFmpeg..." -ForegroundColor Cyan
try {
    Expand-Archive -Path $output -DestinationPath $tempDir -Force
    # Find the extracted folder (usually has version number in the name)
    $extractedFolder = Get-ChildItem -Path $tempDir -Directory | Where-Object { $_.Name -match "ffmpeg" } | Select-Object -First 1
    Write-Host "Extracted to: $($extractedFolder.FullName)" -ForegroundColor Green
} catch {
    Write-Host "Failed to extract FFmpeg. Error: $_" -ForegroundColor Red
    exit 1
}

# Create destination directory
$ffmpegDir = "C:\ffmpeg"
if (!(Test-Path $ffmpegDir)) {
    try {
        New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
        Write-Host "Created directory: $ffmpegDir" -ForegroundColor Green
    } catch {
        Write-Host "Failed to create directory: $ffmpegDir. Error: $_" -ForegroundColor Red
        exit 1
    }
}

# Create bin directory if it doesn't exist
$binDir = Join-Path $ffmpegDir "bin"
if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    Write-Host "Created bin directory: $binDir" -ForegroundColor Green
}

# Move files to C:\ffmpeg
Write-Host "Installing FFmpeg to $ffmpegDir..." -ForegroundColor Cyan
try {
    # First check if bin folder exists in the extracted content
    $extractedBinFolder = Get-ChildItem -Path $extractedFolder.FullName -Directory -Recurse | Where-Object { $_.Name -eq "bin" } | Select-Object -First 1
    
    if ($extractedBinFolder) {
        Write-Host "Found bin folder: $($extractedBinFolder.FullName)" -ForegroundColor Green
        Copy-Item -Path (Join-Path $extractedBinFolder.FullName "*") -Destination $binDir -Recurse -Force -ErrorAction Stop
        Write-Host "Copied FFmpeg files to $binDir" -ForegroundColor Green
    } else {
        # Look for the executables in the extracted folder
        $ffmpegExe = Get-ChildItem -Path $extractedFolder.FullName -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
        
        if ($ffmpegExe) {
            $executableDir = $ffmpegExe.Directory
            Write-Host "Found FFmpeg executable in: $($executableDir.FullName)" -ForegroundColor Green
            Copy-Item -Path (Join-Path $executableDir.FullName "*") -Destination $binDir -Force -ErrorAction Stop
            Write-Host "Copied FFmpeg files to $binDir" -ForegroundColor Green
        } else {
            # Just copy everything to the bin folder
            Write-Host "No bin folder or executables found, copying all files to bin..." -ForegroundColor Yellow
            Copy-Item -Path (Join-Path $extractedFolder.FullName "*") -Destination $binDir -Recurse -Force -ErrorAction Stop
            Write-Host "Copied FFmpeg files to $binDir" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "Failed to copy FFmpeg files. Error: $_" -ForegroundColor Red
    exit 1
}

# Add FFmpeg to PATH
Write-Host "Adding FFmpeg to system PATH..." -ForegroundColor Cyan
try {
    # Add to PATH environment variable for the current user
    $userPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::User)
    if ($userPath -notlike "*$binDir*") {
        [Environment]::SetEnvironmentVariable("PATH", "$userPath;$binDir", [EnvironmentVariableTarget]::User)
        Write-Host "Added FFmpeg to user PATH: $binDir" -ForegroundColor Green
    } else {
        Write-Host "FFmpeg already in user PATH" -ForegroundColor Yellow
    }
    
    # Also update the current session PATH
    $env:PATH = "$env:PATH;$binDir"
} catch {
    Write-Host "Failed to add FFmpeg to PATH. Error: $_" -ForegroundColor Red
    exit 1
}

# Clean up
Write-Host "Cleaning up temporary files..." -ForegroundColor Cyan
try {
    Remove-Item -Path $tempDir -Recurse -Force
    Write-Host "Temporary files removed." -ForegroundColor Green
} catch {
    Write-Host "Failed to clean up temporary files. Error: $_" -ForegroundColor Yellow
}

# Verify installation
Write-Host "Verifying FFmpeg installation..." -ForegroundColor Cyan
try {
    # Ensure the current session PATH is updated
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::User)
    
    # Try to run ffmpeg from the PATH
    $ffmpegVersion = & "ffmpeg" -version
    
    if ($ffmpegVersion) {
        Write-Host "FFmpeg installed successfully!" -ForegroundColor Green
        Write-Host "FFmpeg version:" -ForegroundColor Cyan
        Write-Host $ffmpegVersion -ForegroundColor White
    } else {
        # Try direct path if PATH execution fails
        $ffmpegVersion = & "$binDir\ffmpeg.exe" -version
        if ($ffmpegVersion) {
            Write-Host "FFmpeg installed successfully!" -ForegroundColor Green
            Write-Host "FFmpeg version:" -ForegroundColor Cyan
            Write-Host $ffmpegVersion -ForegroundColor White
            Write-Host "Note: You may need to restart your terminal or computer for PATH changes to take effect." -ForegroundColor Yellow
        } else {
            Write-Host "FFmpeg installation could not be verified." -ForegroundColor Red
        }
    }
} catch {
    Write-Host "Failed to verify FFmpeg installation. Error: $_" -ForegroundColor Red
    Write-Host "You may need to restart your terminal or computer for PATH changes to take effect." -ForegroundColor Yellow
}

Write-Host "`nFFmpeg installation complete. You can now use FFmpeg from any terminal window." -ForegroundColor Green
Write-Host "After restarting your terminal, you can verify the installation by typing 'ffmpeg -version'" -ForegroundColor Green 