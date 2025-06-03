#!/usr/bin/env python3
"""
Simple script to clear offline data for Silence Cutter
"""

import os
import sqlite3
from pathlib import Path

def clear_data():
    """Clear all offline data"""
    # Database location
    db_path = Path.home() / ".silence_cutter" / "usage.db"
    
    print("🧹 Clearing Silence Cutter Offline Data")
    print("=" * 40)
    print(f"📍 Database: {db_path}")
    
    if not db_path.exists():
        print("✅ No database found - already clean!")
        return
    
    try:
        # Connect and get stats
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get total minutes before clearing
        try:
            cursor.execute("SELECT SUM(total_minutes_used) FROM usage_sessions")
            total_minutes = cursor.fetchone()[0] or 0
            print(f"📊 Current total minutes: {total_minutes:.1f}")
        except:
            print("📊 Could not read current stats")
        
        # Clear all tables
        tables = ['processed_files', 'usage_sessions', 'device_info']
        
        for table in tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
                count = cursor.rowcount
                print(f"   ✅ Cleared {table}: {count} records")
            except Exception as e:
                print(f"   ⚠️ Could not clear {table}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Database cleared!")
        print(f"✅ Application will start fresh on next run")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def delete_file():
    """Delete the entire database file"""
    db_path = Path.home() / ".silence_cutter" / "usage.db"
    
    print("🗑️ Deleting Silence Cutter Database File")
    print("=" * 40)
    print(f"📍 Database: {db_path}")
    
    if not db_path.exists():
        print("✅ No database file found!")
        return
    
    try:
        os.remove(db_path)
        print("✅ Database file deleted!")
        
        # Remove directory if empty
        if db_path.parent.exists() and not any(db_path.parent.iterdir()):
            db_path.parent.rmdir()
            print("✅ Empty directory removed")
            
    except Exception as e:
        print(f"❌ Error deleting file: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--delete":
        delete_file()
    else:
        clear_data()
        
    print(f"\n💡 Usage:")
    print(f"   python simple_clear.py        # Clear data")
    print(f"   python simple_clear.py --delete # Delete file") 