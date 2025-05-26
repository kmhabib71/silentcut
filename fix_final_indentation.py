#!/usr/bin/env python3

# Read the file
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Fix the specific lines that need to be inside the try block
# Lines 5343-5348 need to be indented to be inside the try block (12 spaces instead of 8)
lines[5342] = '            \n'  # Line 5343: proper indentation for inside try block
lines[5343] = '            # Clean up video player resources\n'  # Line 5344
lines[5344] = '            if hasattr(self, "video_player"):\n'  # Line 5345
lines[5345] = '                self.video_player.cleanup_fallback_resources()\n'  # Line 5346
lines[5346] = '                \n'  # Line 5347
lines[5347] = '            # Clean up circular buffers and caches\n'  # Line 5348
lines[5348] = '            self.cleanup_buffers()\n'  # Line 5349

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed final try-except block indentation") 