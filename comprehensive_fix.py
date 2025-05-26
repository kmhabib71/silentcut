#!/usr/bin/env python3

# Read the file line by line
with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Fix all indentation issues
for i, line in enumerate(lines):
    line_num = i + 1
    
    # Fix the specific problematic lines
    if line_num == 2711 and 'return click_time_seconds' in line:
        lines[i] = '        return click_time_seconds\n'
        print(f"Fixed line {line_num}: return statement indentation")
    
    # Fix any other excessive indentation issues
    if line.startswith('            return ') and 'click_time_seconds' in line:
        lines[i] = '        return click_time_seconds\n'
        print(f"Fixed line {line_num}: return statement indentation")

# Write the corrected content back
with open('silence_cutter.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Comprehensive indentation fix completed") 