#!/usr/bin/env python3

# Read the file
with open('silence_cutter.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines 3378-3436 (0-indexed: 3377-3435)
# These contain the duplicate process_frame_ultra_fast and handle_preview_playback_optimized methods
new_lines = lines[:3377] + lines[3436:]

# Write back to file
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Successfully removed duplicate methods from InteractiveVideoPlayer class')
print(f'Removed {3436-3377} lines') 