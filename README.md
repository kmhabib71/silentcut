# Silent Cut Complete

Advanced audio/video cutting and editing application with AI-powered features and automated distribution.

## 🚀 Features

- **Advanced Audio/Video Cutting**: Precision cutting tools for multimedia files
- **Batch Processing**: Process multiple files simultaneously
- **AI-Powered Audio Analysis**: Intelligent audio processing and optimization
- **Transcript Integration**: Advanced transcript processing and editing
- **Manual Cutting Tools**: Fine-grained control for precise editing
- **Real-time Preview**: Live preview of edits before processing
- **Multiple Format Support**: Wide range of audio and video formats

## 📦 Installation

### For Users

1. Go to the [Releases](../../releases) page
2. Download the latest `SilentCutComplete_*_Windows.zip`
3. Extract the ZIP file to your desired location
4. Run `Launch_SilentCut.bat` or the executable directly

### System Requirements

- Windows 10 (64-bit) or higher
- 8GB RAM recommended
- 2GB free disk space
- .NET Framework 4.7.2 or higher

## 🛠️ Development

### Project Structure

```
silent-cut-complete/
├── .github/workflows/     # GitHub Actions for automated builds
├── features/             # Core application modules
├── silence_cutter.py     # Main application file
├── transcript_integration.py  # Transcript processing
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Dependencies

- PyQt5 - GUI framework
- MoviePy - Video processing
- OpenCV - Computer vision and image processing
- NumPy - Numerical computing
- Matplotlib - Plotting and visualization
- Pydub - Audio processing

### Local Development Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd silent-cut-complete

# Install dependencies
pip install -r requirements.txt

# Run the application
python silence_cutter.py
```

## 🔄 Automated Builds

This project uses GitHub Actions for automated building and distribution:

- **Simple Build**: Quick testing builds on every push
- **Standard Release**: Full production builds with protection
- **Secure Release**: Enhanced security builds with integrity verification

### Creating a Release

```bash
# Create and push a version tag
git tag v1.0.0
git push origin v1.0.0
```

The GitHub Actions workflow will automatically:

1. Build the application with PyInstaller/Nuitka
2. Apply source code protection
3. Generate checksums and verification tools
4. Create a GitHub release with downloadable packages

## 📋 Features Overview

### Core Modules

- **Batch Processing** (`features/batch_processing.py`) - Multi-file processing
- **Manual Cutting** (`features/manual_cutting.py`) - Precision editing tools
- **AI Audio Integration** (`features/ai_audio_integration.py`) - AI-powered processing
- **Transcript Widget** (`features/transcript_widget.py`) - Transcript editing interface
- **Speech Recognition** (`features/speech_recognition.py`) - Audio-to-text conversion

### Advanced Features

- **Resolution Optimizer** - Automatic video quality optimization
- **Enhanced Transcript** - Advanced transcript processing
- **Fast Transcript** - Quick transcript generation
- **Repeated Word Integration** - Smart duplicate detection and removal

## 🔒 Security

- Source code protection with PyArmor obfuscation
- Integrity verification with SHA256 checksums
- Tamper detection mechanisms
- Secure distribution packaging

## 📞 Support

- **Issues**: [GitHub Issues](../../issues)
- **Documentation**: [GitHub Wiki](../../wiki)
- **Discussions**: [GitHub Discussions](../../discussions)

## 📄 License

This project is licensed under the terms specified in the LICENSE file.
Unauthorized reverse engineering or modification is prohibited.

---

Built with ❤️ using Python and GitHub Actions
