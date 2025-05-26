#!/usr/bin/env python3
import re

# Read the file
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Fix the specific indentation issues
# Fix line 674: too many spaces before "if pixmap is None:"
content = re.sub(
    r'(\s+if self\.buffer_enabled:\s+pixmap = self\.frame_buffer\.get\(self\.current_frame\)\s+)\s+if pixmap is None:',
    r'\1\n                    if pixmap is None:',
    content,
    flags=re.MULTILINE
)

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed indentation issues in silence_cutter.py") 