#!/usr/bin/env python3

try:
    import ast
    with open('silence_cutter.py', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Try to parse the file
    ast.parse(content)
    print("✅ SUCCESS: No syntax errors found!")
    
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
    print(f"   Line {e.lineno}: {e.text}")
    print(f"   Error: {e.msg}")
    
except Exception as e:
    print(f"❌ OTHER ERROR: {e}") 