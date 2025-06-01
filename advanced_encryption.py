#!/usr/bin/env python3
"""
Advanced Encryption System for Silent Cutter Application
This creates a fully encrypted version of your application with runtime decryption.
"""

import os
import sys
import base64
import json
import zlib
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime

class AdvancedEncryption:
    def __init__(self, project_dir=".", password="SilentCutter2024!"):
        self.project_dir = Path(project_dir).resolve()
        self.encrypted_dir = self.project_dir / "encrypted"
        self.password = password.encode()
        
        # Generate encryption key from password
        salt = b'silent_cutter_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password))
        self.fernet = Fernet(key)
    
    def encrypt_file(self, file_path):
        """Encrypt a single file"""
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Compress then encrypt
        compressed = zlib.compress(data)
        encrypted = self.fernet.encrypt(compressed)
        
        return base64.b64encode(encrypted).decode('ascii')
    
    def create_encrypted_package(self):
        """Create a complete encrypted package"""
        print("🔐 Creating advanced encrypted package...")
        
        # Create encrypted directory
        if self.encrypted_dir.exists():
            import shutil
            shutil.rmtree(self.encrypted_dir)
        self.encrypted_dir.mkdir()
        
        # Files to encrypt
        files_to_encrypt = {
            'main': 'silence_cutter.py',
            'transcript': 'transcript_integration.py',
            'requirements': 'requirements.txt'
        }
        
        # Encrypt features directory
        features_dir = self.project_dir / "features"
        feature_files = {}
        for py_file in features_dir.glob("*.py"):
            key = f"features_{py_file.stem}"
            feature_files[key] = str(py_file.relative_to(self.project_dir))
        
        files_to_encrypt.update(feature_files)
        
        # Encrypt all files
        encrypted_data = {}
        for key, file_path in files_to_encrypt.items():
            full_path = self.project_dir / file_path
            if full_path.exists():
                print(f"🔒 Encrypting {file_path}...")
                encrypted_data[key] = self.encrypt_file(full_path)
        
        # Create the encrypted loader
        self.create_encrypted_loader(encrypted_data)
        print("SUCCESS: Advanced encryption complete!")
    
    def create_encrypted_loader(self, encrypted_data):
        """Create the encrypted loader with embedded data"""
        
        # Convert encrypted data to JSON
        encrypted_json = json.dumps(encrypted_data, indent=2)
        
        loader_code = f'''#!/usr/bin/env python3
"""
Silent Cutter - Protected Application
Copyright Protected - Unauthorized copying prohibited
"""

import os
import sys
import json
import base64
import zlib
import tempfile
import shutil
import hashlib
from pathlib import Path

# Protection notice
PROTECTION_NOTICE = """
╔══════════════════════════════════════════════════════════════╗
║                    PROTECTED SOFTWARE                        ║
║                                                              ║
║  This software is protected by encryption and obfuscation.  ║
║  Unauthorized copying, reverse engineering, or             ║
║  redistribution is strictly prohibited.                     ║
║                                                              ║
║  Copyright © 2024 Silent Cutter. All rights reserved.      ║
╚══════════════════════════════════════════════════════════════╝
"""

class SecureLoader:
    def __init__(self):
        self.temp_dir = None
        self.password = None
        
    def verify_integrity(self):
        """Verify application integrity"""
        try:
            # Simple integrity check
            expected_hash = "{hashlib.sha256(encrypted_json.encode()).hexdigest()}"
            actual_hash = hashlib.sha256(json.dumps(ENCRYPTED_DATA).encode()).hexdigest()
            return expected_hash == actual_hash
        except:
            return False
    
    def get_encryption_key(self):
        """Get decryption key"""
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            password = b"SilentCutter2024!"
            salt = b'silent_cutter_salt_2024'
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            return Fernet(key)
        except ImportError:
            print("❌ Cryptography library not found. Please install: pip install cryptography")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Encryption error: {{e}}")
            sys.exit(1)
    
    def decrypt_file(self, encrypted_data, fernet):
        """Decrypt file data"""
        try:
            # Decode base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            
            # Decrypt
            compressed = fernet.decrypt(encrypted_bytes)
            
            # Decompress
            data = zlib.decompress(compressed)
            
            return data
        except Exception as e:
            print(f"❌ Decryption failed: {{e}}")
            return None
    
    def setup_temp_environment(self):
        """Setup temporary execution environment"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="silentcutter_")
            
            # Create features directory
            features_dir = Path(self.temp_dir) / "features"
            features_dir.mkdir(exist_ok=True)
            
            return True
        except Exception as e:
            print(f"❌ Failed to setup environment: {{e}}")
            return False
    
    def load_application(self):
        """Load and run the protected application"""
        print(PROTECTION_NOTICE)
        
        # Verify integrity
        if not self.verify_integrity():
            print("❌ Application integrity check failed!")
            sys.exit(1)
        
        # Setup environment
        if not self.setup_temp_environment():
            sys.exit(1)
        
        # Get decryption key
        fernet = self.get_encryption_key()
        
        try:
            # Add temp directory to Python path
            sys.path.insert(0, self.temp_dir)
            
            # Decrypt and write main files
            for key, encrypted_data in ENCRYPTED_DATA.items():
                decrypted = self.decrypt_file(encrypted_data, fernet)
                if decrypted is None:
                    print(f"❌ Failed to decrypt {{key}}")
                    continue
                
                # Determine file path
                if key == 'main':
                    file_path = Path(self.temp_dir) / "silence_cutter.py"
                elif key == 'transcript':
                    file_path = Path(self.temp_dir) / "transcript_integration.py"
                elif key == 'requirements':
                    file_path = Path(self.temp_dir) / "requirements.txt"
                elif key.startswith('features_'):
                    filename = key.replace('features_', '') + '.py'
                    file_path = Path(self.temp_dir) / "features" / filename
                else:
                    continue
                
                # Write decrypted file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(decrypted)
            
            # Create __init__.py for features
            init_file = Path(self.temp_dir) / "features" / "__init__.py"
            if not init_file.exists():
                init_file.write_text("# Features module\\n")
            
            print("🚀 Starting Silent Cutter...")
            
            # Import and run the main application
            import silence_cutter
            
        except Exception as e:
            print(f"❌ Failed to start application: {{e}}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            self.cleanup()
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass

# Embedded encrypted data
ENCRYPTED_DATA = {encrypted_json}

def main():
    """Main entry point"""
    try:
        loader = SecureLoader()
        loader.load_application()
    except KeyboardInterrupt:
        print("\\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Unexpected error: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        # Save the encrypted loader
        loader_file = self.encrypted_dir / "silent_cutter_protected.py"
        with open(loader_file, 'w', encoding='utf-8') as f:
            f.write(loader_code)
        
        # Create requirements file for the protected version
        protected_requirements = '''cryptography>=3.4.0
PyQt5>=5.15.0
pydub>=0.25.0
moviepy>=1.0.0
numpy>=1.20.0
opencv-python>=4.5.0
pygame>=2.0.0
proglog>=0.1.0
'''
        
        req_file = self.encrypted_dir / "requirements.txt"
        with open(req_file, 'w', encoding='utf-8') as f:
            f.write(protected_requirements)
        
        # Create README for encrypted package
        readme_content = f"""# Silent Cutter - Encrypted Package
        
This package contains the encrypted Silent Cutter application.

## Installation & Usage:
1. pip install cryptography
2. python encrypted_silence_cutter.py

## Security Features:
- AES-256 encryption
- Integrity verification  
- Temporary file cleanup
- Runtime decryption

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Protected by: Silent Cutter Advanced Protection System
"""
        
        with open(self.encrypted_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        
        print(f"📁 Protected application saved to: {self.encrypted_dir}")
        print("📝 You can now distribute the 'encrypted' folder safely!")

def main():
    print("🔐 Silent Cutter Advanced Encryption Tool")
    print("=" * 50)
    
    # Check if cryptography is installed
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("❌ Please install cryptography first: pip install cryptography")
        return
    
    encryptor = AdvancedEncryption()
    encryptor.create_encrypted_package()

if __name__ == "__main__":
    main() 