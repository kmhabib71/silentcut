#!/usr/bin/env python3
"""
Script to clear all offline data stored in the silence cutter application
This allows testing the application from scratch
"""

import os
import sqlite3
from pathlib import Path
import sys

def find_database_location():
    """Find where the offline database is stored"""
    db_path = Path.home() / ".silence_cutter" / "usage.db"
    return db_path

def clear_offline_database():
    """Clear all data from the offline database"""
    db_path = find_database_location()
    
    print("🗄️ Silence Cutter - Clear Offline Data")
    print("=" * 50)
    print(f"📍 Database location: {db_path}")
    
    if not db_path.exists():
        print("✅ No database found - already clean!")
        return True
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current data stats before clearing
        cursor.execute("SELECT COUNT(*) FROM device_info")
        device_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM usage_sessions")
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM processed_files")
        file_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total_minutes_used) FROM usage_sessions")
        total_minutes = cursor.fetchone()[0] or 0
        
        print(f"\n📊 Current database contents:")
        print(f"   Devices: {device_count}")
        print(f"   Sessions: {session_count}")
        print(f"   Files processed: {file_count}")
        print(f"   Total minutes: {total_minutes:.1f}")
        
        if device_count == 0 and session_count == 0 and file_count == 0:
            print("✅ Database is already empty!")
            conn.close()
            return True
        
        # Ask for confirmation
        print(f"\n⚠️ This will permanently delete all offline data!")
        confirmation = input("Type 'YES' to confirm deletion: ")
        
        if confirmation != 'YES':
            print("❌ Operation cancelled")
            conn.close()
            return False
        
        # Clear all tables
        print(f"\n🧹 Clearing database tables...")
        
        cursor.execute("DELETE FROM processed_files")
        deleted_files = cursor.rowcount
        print(f"   ✅ Cleared {deleted_files} processed files")
        
        cursor.execute("DELETE FROM usage_sessions")
        deleted_sessions = cursor.rowcount
        print(f"   ✅ Cleared {deleted_sessions} usage sessions")
        
        cursor.execute("DELETE FROM device_info")
        deleted_devices = cursor.rowcount
        print(f"   ✅ Cleared {deleted_devices} device registrations")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Database cleared successfully!")
        print(f"✅ Application will start fresh on next run")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

def delete_database_file():
    """Completely delete the database file"""
    db_path = find_database_location()
    
    if not db_path.exists():
        print("✅ No database file to delete!")
        return True
    
    try:
        os.remove(db_path)
        print(f"🗑️ Database file deleted: {db_path}")
        
        # Also remove the directory if it's empty
        if db_path.parent.exists() and not any(db_path.parent.iterdir()):
            db_path.parent.rmdir()
            print(f"🗑️ Empty directory removed: {db_path.parent}")
        
        return True
    except Exception as e:
        print(f"❌ Error deleting database file: {e}")
        return False

def show_current_data():
    """Show current data in the database without clearing it"""
    db_path = find_database_location()
    
    print("🗄️ Current Offline Data")
    print("=" * 30)
    print(f"📍 Database: {db_path}")
    
    if not db_path.exists():
        print("✅ No database found - application is clean!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Device info
        cursor.execute("SELECT * FROM device_info")
        devices = cursor.fetchall()
        print(f"\n📱 Device Info ({len(devices)} devices):")
        for device in devices:
            print(f"   ID: {device[1][:16]}...")
            print(f"   Name: {device[6] if len(device) > 6 else 'Unknown'}")
            print(f"   Email: {device[5] or 'None'}")
            print(f"   Registered: {device[7] if len(device) > 7 else 'Unknown'}")
        
        # Usage sessions
        cursor.execute("SELECT * FROM usage_sessions")
        sessions = cursor.fetchall()
        print(f"\n📊 Usage Sessions ({len(sessions)} sessions):")
        for session in sessions:
            print(f"   Session: {session[0][:16]}...")
            print(f"   Minutes: {session[2]:.1f}")
            print(f"   Files: {session[3]}")
            print(f"   Last used: {session[5]}")
        
        # Recent files
        cursor.execute("SELECT * FROM processed_files ORDER BY processed_date DESC LIMIT 5")
        files = cursor.fetchall()
        print(f"\n📁 Recent Files (showing 5 of many):")
        for file_info in files:
            duration = file_info[4] if file_info[4] is not None else 0.0
            print(f"   {file_info[3]} ({duration:.1f} min) - {file_info[5]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage offline data for Silence Cutter")
    parser.add_argument("--show", action="store_true", help="Show current data without clearing")
    parser.add_argument("--clear", action="store_true", help="Clear all data from database")
    parser.add_argument("--delete", action="store_true", help="Delete the entire database file")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    
    args = parser.parse_args()
    
    if args.show:
        show_current_data()
    elif args.clear:
        if args.force:
            # Skip confirmation for automated clearing
            db_path = find_database_location()
            if db_path.exists():
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM processed_files")
                cursor.execute("DELETE FROM usage_sessions") 
                cursor.execute("DELETE FROM device_info")
                conn.commit()
                conn.close()
                print("✅ Database cleared (forced)")
            else:
                print("✅ No database to clear")
        else:
            clear_offline_database()
    elif args.delete:
        if args.force or input("Delete entire database file? (y/N): ").lower() == 'y':
            delete_database_file()
        else:
            print("❌ Operation cancelled")
    else:
        # Default: show current data and options
        show_current_data()
        print(f"\n🔧 Options:")
        print(f"   python clear_offline_data.py --show    # Show current data")
        print(f"   python clear_offline_data.py --clear   # Clear all data")
        print(f"   python clear_offline_data.py --delete  # Delete database file")
        print(f"   python clear_offline_data.py --clear --force # Clear without confirmation") 