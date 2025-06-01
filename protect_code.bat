@echo off
echo ===============================================
echo    Silent Cutter Code Protection Tool
echo ===============================================
echo.

echo 📦 Installing protection dependencies...
pip install pyinstaller pyarmor cython nuitka cryptography

echo.
echo 🔒 Running code protection...
python setup_protection.py

echo.
echo ✅ Protection process complete!
echo.
echo 📁 Check the following directories:
echo    - obfuscated/    : Simple obfuscated code
echo    - protected/     : PyArmor protected code (if available)
echo    - dist/          : Standalone executable
echo.

pause 