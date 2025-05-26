#!/usr/bin/env python3

# Read the file
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Fix line 2647 - the else statement needs to be aligned with its corresponding if
# Looking at the context, the if statement is at line 2644 with 8 spaces
# So the else should also have 8 spaces, not 8 spaces
if len(lines) > 2646:  # Line 2647 is index 2646
    if lines[2646].strip() == 'else:':
        lines[2646] = '        else:\n'  # 8 spaces to match the if statement
        print("Fixed line 2647: else statement indentation")

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Simple indentation fix completed") 