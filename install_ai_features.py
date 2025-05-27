#!/usr/bin/env python3
"""
AI Features Installation Script for Silence Cutter
Installs and configures AI audio analysis dependencies
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} failed: {str(e)}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def install_dependencies():
    """Install required dependencies"""
    print("\n🚀 Installing AI Audio Analysis Dependencies...")
    
    # Core dependencies
    core_deps = [
        "torch>=1.9.0",
        "torchaudio>=0.9.0", 
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "librosa>=0.9.0",
        "scikit-learn>=1.0.0",
        "soundfile>=0.10.0",
        "resampy>=0.2.2",
        "audioread>=2.1.9",
        "numba>=0.56.0"
    ]
    
    # Optional performance dependencies
    optional_deps = [
        "onnxruntime>=1.10.0",
        "matplotlib>=3.5.0",
        "seaborn>=0.11.0"
    ]
    
    success = True
    
    # Install core dependencies
    for dep in core_deps:
        if not run_command(f"pip install {dep}", f"Installing {dep.split('>=')[0]}"):
            success = False
    
    # Install optional dependencies (non-critical)
    for dep in optional_deps:
        run_command(f"pip install {dep}", f"Installing {dep.split('>=')[0]} (optional)")
    
    return success

def verify_installation():
    """Verify that all components are working"""
    print("\n🔍 Verifying AI Installation...")
    
    # Test imports
    test_modules = [
        ("torch", "PyTorch"),
        ("torchaudio", "TorchAudio"),
        ("numpy", "NumPy"),
        ("scipy", "SciPy"),
        ("librosa", "Librosa"),
        ("sklearn", "Scikit-learn"),
        ("soundfile", "SoundFile"),
        ("numba", "Numba")
    ]
    
    success = True
    for module, name in test_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {name} imported successfully")
        except ImportError as e:
            print(f"❌ {name} import failed: {e}")
            success = False
    
    # Test AI audio analysis
    try:
        sys.path.append(str(Path(__file__).parent / "ai_audio_analysis"))
        from ai_audio_analysis import IntelligentAudioProcessor
        processor = IntelligentAudioProcessor()
        print("✅ AI Audio Analysis initialized successfully")
    except Exception as e:
        print(f"❌ AI Audio Analysis initialization failed: {e}")
        success = False
    
    return success

def setup_gpu_support():
    """Check and setup GPU support if available"""
    print("\n🎮 Checking GPU Support...")
    
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            print(f"✅ CUDA GPU detected: {gpu_name} ({gpu_count} device(s))")
            print("🚀 GPU acceleration will be available for AI processing")
            return True
        else:
            print("ℹ️  No CUDA GPU detected - using CPU processing")
            print("💡 For better performance, consider using a CUDA-compatible GPU")
            return False
    except Exception as e:
        print(f"⚠️  GPU check failed: {e}")
        return False

def create_config_file():
    """Create AI configuration file"""
    print("\n📝 Creating AI Configuration...")
    
    config_content = """# AI Audio Analysis Configuration
# This file contains settings for the AI-powered features

[ai_settings]
# Enable AI features (True/False)
enabled = True

# Performance profile (real-time, balanced, quality, batch)
performance_profile = balanced

# GPU acceleration (auto, enabled, disabled)
gpu_acceleration = auto

# Confidence threshold for AI decisions (0.0 - 1.0)
confidence_threshold = 0.7

[detection_features]
# Enable filler word detection
filler_words = True

# Enable repeated content detection
repeated_content = True

# Enable speaker change detection
speaker_changes = True

# Preserve dramatic pauses
dramatic_pauses = True

[audio_enhancement]
# Enable automatic audio enhancement
enabled = False

# Noise reduction
noise_reduction = True

# Hiss removal
hiss_removal = True

# Electrical hum removal
hum_removal = True

# Speech clarity optimization
speech_clarity = True
"""
    
    try:
        config_path = Path(__file__).parent / "ai_audio_analysis" / "config.ini"
        config_path.parent.mkdir(exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(config_content)
        print(f"✅ Configuration file created: {config_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create configuration file: {e}")
        return False

def main():
    """Main installation process"""
    print("🤖 AI Audio Analysis Installation for Silence Cutter")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Installation failed. Please check the errors above.")
        sys.exit(1)
    
    # Verify installation
    if not verify_installation():
        print("\n❌ Verification failed. Some components may not be working correctly.")
        sys.exit(1)
    
    # Setup GPU support
    gpu_available = setup_gpu_support()
    
    # Create configuration
    create_config_file()
    
    # Final success message
    print("\n" + "=" * 60)
    print("🎉 AI Features Installation Complete!")
    print("\n📋 Installation Summary:")
    print("✅ Core AI dependencies installed")
    print("✅ Audio processing libraries ready")
    print("✅ Machine learning models available")
    if gpu_available:
        print("✅ GPU acceleration enabled")
    else:
        print("ℹ️  CPU processing mode (still fast!)")
    
    print("\n🚀 Next Steps:")
    print("1. Restart Silence Cutter application")
    print("2. Look for the '🤖 AI Pro' tab in the interface")
    print("3. Load a video/audio file and try AI-powered analysis")
    print("4. Enjoy next-level audio processing!")
    
    print("\n💡 Pro Tips:")
    print("• Use 'Balanced' profile for best speed/quality ratio")
    print("• Enable GPU acceleration for 5-10x faster processing")
    print("• Try different confidence thresholds for fine-tuning")
    print("• Audio enhancement works great for podcasts and interviews")

if __name__ == "__main__":
    main() 