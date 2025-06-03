#!/usr/bin/env python3
"""
Manual database editor for Silence Cutter usage tracking
Allows setting specific usage values for testing
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

class DatabaseEditor:
    def __init__(self):
        self.db_path = Path.home() / ".silence_cutter" / "usage.db"
        
    def connect(self):
        """Connect to the database"""
        if not self.db_path.exists():
            print("❌ Database not found. Run the app first to create it.")
            return None
        return sqlite3.connect(self.db_path)
    
    def show_current_data(self):
        """Show current database contents"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("🗄️ Current Database Contents")
        print("=" * 50)
        
        # Device info
        cursor.execute("SELECT * FROM device_info")
        devices = cursor.fetchall()
        print(f"\n📱 Devices ({len(devices)}):")
        for device in devices:
            print(f"   ID: {device[1]}")
            print(f"   Name: {device[6] if len(device) > 6 else 'Unknown'}")
            print(f"   Registered: {'Yes' if len(device) > 7 and device[7] else 'No'}")
        
        # Usage sessions
        cursor.execute("SELECT * FROM usage_sessions")
        sessions = cursor.fetchall()
        print(f"\n📊 Sessions ({len(sessions)}):")
        for session in sessions:
            print(f"   Session ID: {session[0]}")
            print(f"   Total Minutes: {session[2]:.1f}")
            print(f"   Files Processed: {session[3]}")
            print(f"   Last Used: {session[5] if len(session) > 5 else 'Unknown'}")
        
        # Files
        cursor.execute("SELECT COUNT(*), SUM(duration_minutes) FROM processed_files")
        file_stats = cursor.fetchone()
        print(f"\n📁 Files: {file_stats[0]} total, {file_stats[1]:.1f} total minutes")
        
        conn.close()
    
    def set_usage_minutes(self, target_minutes):
        """Set the total usage to a specific number of minutes"""
        conn = self.connect()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        try:
            # Get the current session
            cursor.execute("SELECT session_id, permanent_id FROM usage_sessions LIMIT 1")
            session_data = cursor.fetchone()
            
            if not session_data:
                print("❌ No session found. Run the app first.")
                conn.close()
                return False
            
            session_id, permanent_id = session_data
            
            print(f"🎯 Setting usage to {target_minutes} minutes...")
            
            # Update the session with new total
            cursor.execute("""
                UPDATE usage_sessions 
                SET total_minutes_used = ?, 
                    last_use_date = ?
                WHERE session_id = ?
            """, (target_minutes, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session_id))
            
            # Clear existing files and add a test file with the target duration
            cursor.execute("DELETE FROM processed_files WHERE session_id = ?", (session_id,))
            
            cursor.execute("""
                INSERT INTO processed_files 
                (session_id, permanent_id, file_name, duration_minutes, processed_date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id, 
                permanent_id, 
                f"test_file_for_{target_minutes}min.mp4", 
                target_minutes, 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            # Update files processed count
            cursor.execute("""
                UPDATE usage_sessions 
                SET files_processed = 1
                WHERE session_id = ?
            """, (session_id,))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Usage set to {target_minutes} minutes")
            print(f"📁 Added test file: test_file_for_{target_minutes}min.mp4")
            return True
            
        except Exception as e:
            print(f"❌ Error setting usage: {e}")
            conn.close()
            return False
    
    def add_test_files(self, file_count, minutes_each):
        """Add multiple test files"""
        conn = self.connect()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        try:
            # Get session info
            cursor.execute("SELECT session_id, permanent_id, total_minutes_used, files_processed FROM usage_sessions LIMIT 1")
            session_data = cursor.fetchone()
            
            if not session_data:
                print("❌ No session found.")
                conn.close()
                return False
            
            session_id, permanent_id, current_minutes, current_files = session_data
            
            # Add new files
            total_new_minutes = file_count * minutes_each
            for i in range(file_count):
                cursor.execute("""
                    INSERT INTO processed_files 
                    (session_id, permanent_id, file_name, duration_minutes, processed_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id, 
                    permanent_id, 
                    f"test_file_{i+1}_{minutes_each}min.mp4", 
                    minutes_each, 
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            
            # Update session totals
            new_total_minutes = current_minutes + total_new_minutes
            new_total_files = current_files + file_count
            
            cursor.execute("""
                UPDATE usage_sessions 
                SET total_minutes_used = ?, 
                    files_processed = ?,
                    last_use_date = ?
                WHERE session_id = ?
            """, (new_total_minutes, new_total_files, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session_id))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Added {file_count} files ({minutes_each} min each)")
            print(f"📊 New total: {new_total_minutes} minutes, {new_total_files} files")
            return True
            
        except Exception as e:
            print(f"❌ Error adding files: {e}")
            conn.close()
            return False

def main():
    editor = DatabaseEditor()
    
    print("🛠️ Silence Cutter Database Editor")
    print("=" * 40)
    
    while True:
        print("\n📋 Options:")
        print("1. Show current data")
        print("2. Set total usage to specific minutes")
        print("3. Add test files")
        print("4. Set to 58 minutes (test free limit)")
        print("5. Set to 65 minutes (test over limit)")
        print("6. Reset to 0 minutes")
        print("0. Exit")
        
        choice = input("\nSelect option (0-6): ").strip()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
        elif choice == "1":
            editor.show_current_data()
        elif choice == "2":
            try:
                minutes = float(input("Enter total minutes: "))
                editor.set_usage_minutes(minutes)
            except ValueError:
                print("❌ Invalid number")
        elif choice == "3":
            try:
                count = int(input("Number of files: "))
                minutes = float(input("Minutes per file: "))
                editor.add_test_files(count, minutes)
            except ValueError:
                print("❌ Invalid numbers")
        elif choice == "4":
            editor.set_usage_minutes(58.0)
            print("🎯 Set to 58 minutes - 2 minutes below free limit")
        elif choice == "5":
            editor.set_usage_minutes(65.0)
            print("🎯 Set to 65 minutes - 5 minutes over free limit")
        elif choice == "6":
            editor.set_usage_minutes(0.0)
            print("🎯 Reset to 0 minutes")
        else:
            print("❌ Invalid option")

if __name__ == "__main__":
    main() 