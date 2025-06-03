#!/usr/bin/env python3
"""
Script to fix existing incorrect duration data in the database
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'features'))

try:
    from api_communication import SaaSAPIClient
    API_COMMUNICATION_AVAILABLE = True
except ImportError:
    API_COMMUNICATION_AVAILABLE = False
    print("❌ API communication module not available")

def fix_database_duration_data():
    """Check and fix existing duration data in database"""
    
    if not API_COMMUNICATION_AVAILABLE:
        return False
    
    print("🛠️ Checking database for incorrect duration entries...")
    print("=" * 60)
    
    # Initialize API client
    api_client = SaaSAPIClient()
    
    # Get current session stats
    stats = api_client.get_session_stats()
    print(f"📊 Current Database Stats:")
    print(f"   Total Minutes: {stats['total_minutes_used']:.2f}")
    print(f"   Files Processed: {stats['files_processed']}")
    
    # Check if total minutes seems too high
    avg_minutes_per_file = stats['total_minutes_used'] / max(1, stats['files_processed'])
    print(f"   Average per file: {avg_minutes_per_file:.2f} minutes")
    
    if avg_minutes_per_file > 20:  # Suspiciously high average
        print(f"\n⚠️ Average duration per file seems too high!")
        print(f"   This suggests some files may have been recorded with file-size based duration")
        print(f"   instead of actual video duration.")
        
        # Get all sessions to examine the data
        all_sessions = api_client.offline_tracker.get_all_sessions()
        
        suspicious_files = []
        for session in all_sessions:
            files = session.get('files', [])
            for file_data in files:
                duration = file_data.get('duration_minutes', 0)
                if duration > 10:  # Files longer than 10 minutes are suspicious
                    suspicious_files.append({
                        'file_name': file_data.get('file_name', 'unknown'),
                        'duration': duration,
                        'session_id': session.get('session_id')
                    })
        
        if suspicious_files:
            print(f"\n🚨 Found {len(suspicious_files)} suspicious file entries:")
            total_suspicious_minutes = 0
            for file_info in suspicious_files[:10]:  # Show first 10
                print(f"   📁 {file_info['file_name']}: {file_info['duration']:.1f} minutes")
                total_suspicious_minutes += file_info['duration']
            
            if len(suspicious_files) > 10:
                print(f"   ... and {len(suspicious_files) - 10} more files")
                for file_info in suspicious_files[10:]:
                    total_suspicious_minutes += file_info['duration']
            
            print(f"\n📊 Total suspicious duration: {total_suspicious_minutes:.1f} minutes")
            print(f"💡 This likely represents file sizes in MB rather than actual duration")
            
            # Estimate what the corrected total should be
            estimated_correct_total = (stats['total_minutes_used'] - total_suspicious_minutes) + (len(suspicious_files) * 2.0)  # Assume 2 min average
            print(f"📈 Estimated corrected total: {estimated_correct_total:.1f} minutes")
            
        else:
            print(f"\n✅ No obviously suspicious file durations found")
            
    else:
        print(f"\n✅ Average duration per file seems reasonable")
    
    return True

if __name__ == "__main__":
    print("🔧 Database Duration Fix Analysis")
    print("=" * 60)
    
    success = fix_database_duration_data()
    
    if success:
        print(f"\n✅ Analysis complete!")
        print(f"💡 Going forward, the duration correction fix in api_communication.py")
        print(f"   will automatically detect and correct wrong durations from silence_cutter.py")
    else:
        print(f"\n❌ Analysis failed!") 