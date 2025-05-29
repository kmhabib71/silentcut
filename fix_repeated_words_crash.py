#!/usr/bin/env python3
"""
Script to fix the repeated words detection crash
"""

def fix_repeated_words_crash():
    with open('transcript_integration.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the repeated_segments.append section
    old_append = """                            repeated_segments.append({
                                'start': float(occurrence['start']),
                                'end': float(occurrence['end']),
                                'type': 'repeated_word'
                            })"""
    
    new_append = """                            repeated_segments.append({
                                'start': float(occurrence['start']),
                                'end': float(occurrence['end']),
                                'type': 'repeated_word',
                                'selected': True,  # Add required 'selected' field
                                'word': word  # Add word for reference
                            })"""
    
    content = content.replace(old_append, new_append)
    
    with open('transcript_integration.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed repeated words crash - added 'selected' field")

if __name__ == "__main__":
    fix_repeated_words_crash() 