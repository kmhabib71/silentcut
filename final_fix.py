#!/usr/bin/env python3

# Read the file
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Fix the specific indentation issues in the convert_click_position_to_original_time method
fixes = [
    # Fix the return statements that are not properly indented
    ('        if not self.preview_mode or not hasattr(self, \'preview_timeline_duration\'):\n            # Normal mode: click time is already in original timeline\n        return click_time_seconds',
     '        if not self.preview_mode or not hasattr(self, \'preview_timeline_duration\'):\n            # Normal mode: click time is already in original timeline\n            return click_time_seconds'),
    
    ('        if not self.silent_parts:\n        return click_time_seconds',
     '        if not self.silent_parts:\n            return click_time_seconds'),
    
    ('        if not selected_silent_parts:\n        return click_time_seconds',
     '        if not selected_silent_parts:\n            return click_time_seconds'),
]

for old, new in fixes:
    content = content.replace(old, new)

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Final indentation fix completed") 