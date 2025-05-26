#!/usr/bin/env python3

# Read the file
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Fix line 5351 to have the proper indented print statement
lines[5350] = '            print(f"Error during cleanup: {e}")\n'

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed except block indentation") 