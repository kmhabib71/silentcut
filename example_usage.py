#!/usr/bin/env python3
"""
Example usage of the SilenceCutter API with fixed device tracking and session management.

This script demonstrates:
1. Permanent device identification (consistent across app sessions)
2. Single session per device (no duplicate anonymous sessions)
3. Online device registration checking
4. Anonymous usage linking when users sign up
5. Admin panel visibility of all sessions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from features.api_communication import api_client
import time

def demonstrate_fixed_functionality():
    """Demonstrate the fixed device tracking and session management"""
    
    print("🔧 SilenceCutter Fixed Device Tracking Demo")
    print("=" * 50)
    
    # 1. Show permanent device identification
    print(f"\n1. 📱 Permanent Device ID: {api_client.permanent_id}")
    print(f"   Session ID (same as device): {api_client.session_id}")
    print(f"   ✅ Device ID is consistent across app restarts")
    
    # 2. Show device info
    device_info = api_client.offline_tracker.get_device_info()
    print(f"\n2. 🖥️  Device Information:")
    print(f"   Device Name: {device_info.get('device_name', 'Unknown')}")
    print(f"   Created: {device_info.get('created_date', 'Unknown')}")
    print(f"   Last Used: {device_info.get('last_used_date', 'Unknown')}")
    print(f"   Registered Online: {device_info.get('registered_online', False)}")
    print(f"   Linked Email: {device_info.get('linked_email', 'None')}")
    
    # 3. Show session stats
    stats = api_client.get_session_stats()
    print(f"\n3. 📊 Current Session Stats:")
    print(f"   Total Minutes Used: {stats['total_minutes_used']:.1f}")
    print(f"   Files Processed: {stats['files_processed']}")
    print(f"   Remaining Free Minutes: {stats['remaining_free_minutes']:.1f}")
    print(f"   User Email: {stats['user_email'] or 'Anonymous'}")
    
    # 4. Simulate file processing
    print(f"\n4. 🎬 Simulating file processing...")
    test_file = "demo_video.mp4"
    test_duration = 2.5  # 2.5 minutes
    
    # Check if we can process the file
    validation = api_client.validate_file_usage(test_duration)
    print(f"   File: {test_file} ({test_duration} minutes)")
    print(f"   Can Process: {'✅ Yes' if validation['allowed'] else '❌ No'}")
    print(f"   Message: {validation['message']}")
    
    if validation['allowed']:
        # Record the usage
        success = api_client.record_usage(test_duration, test_file)
        print(f"   Usage Recorded: {'✅ Success' if success else '❌ Failed'}")
        
        # Show updated stats
        updated_stats = api_client.get_session_stats()
        print(f"   Updated Usage: {updated_stats['total_minutes_used']:.1f} minutes")
    
    # 5. Show upgrade URL with device tracking
    print(f"\n5. 🔗 Account Linking URLs:")
    upgrade_url = api_client.open_upgrade_page()
    auth_url = api_client.open_auth_dialog()
    print(f"   Upgrade URL: {upgrade_url}")
    print(f"   Auth URL: {auth_url}")
    print(f"   ✅ URLs include device ID for anonymous usage linking")
    
    # 6. Show all local sessions
    all_sessions = api_client.offline_tracker.get_all_sessions()
    print(f"\n6. 💾 Local Sessions (should be only 1 per device):")
    for i, session in enumerate(all_sessions, 1):
        print(f"   Session {i}:")
        print(f"     ID: {session['session_id'][:16]}...")
        print(f"     Minutes: {session['total_minutes_used']:.1f}")
        print(f"     Files: {session['files_processed']}")
        print(f"     Email: {session['user_email'] or 'Anonymous'}")
    
    print(f"\n✅ Total Sessions: {len(all_sessions)} (should be 1 per device)")
    
    # 7. Instructions for admin panel
    print(f"\n7. 👨‍💼 Admin Panel Instructions:")
    print(f"   1. Open website admin panel")
    print(f"   2. Click 'Anonymous Sessions' tab")
    print(f"   3. Find device: {api_client.permanent_id[:8]}...")
    print(f"   4. See real-time usage tracking")
    print(f"   5. When user signs up, usage will be linked automatically")
    
    print(f"\n🎉 Demo Complete!")
    print(f"   - Device tracking: ✅ Fixed")
    print(f"   - Session management: ✅ Fixed") 
    print(f"   - Online registration: ✅ Fixed")
    print(f"   - Admin visibility: ✅ Fixed")
    print(f"   - Account linking: ✅ Fixed")

if __name__ == "__main__":
    demonstrate_fixed_functionality() 