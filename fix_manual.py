#!/usr/bin/env python3

# Read the file line by line
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Fix specific lines with indentation issues
for i, line in enumerate(lines):
    # Fix line around 674 - remove excessive indentation
    if 'if pixmap is None:' in line and line.count(' ') > 30:
        lines[i] = '                    if pixmap is None:\n'
        print(f"Fixed line {i+1}: excessive indentation")
    
    # Fix any other lines with excessive indentation in the same block
    if i > 670 and i < 690:  # Around the problematic area
        if line.startswith('                                        '):
            # Replace excessive indentation with proper indentation
            content = line.lstrip()
            if content.strip():
                lines[i] = '                        ' + content
                print(f"Fixed line {i+1}: excessive indentation")

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Manual indentation fix completed") 