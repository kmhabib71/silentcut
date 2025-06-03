#!/usr/bin/env python3
"""
Test script to verify legacy record_usage parameter compatibility
This simulates how silence_cutter.py calls the API
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

def test_legacy_usage():
    """Test the legacy record_usage call format"""
    
    if not API_COMMUNICATION_AVAILABLE:
        return False
    
    print("🧪 Testing legacy record_usage call format...")
    print("=" * 50)
    
    # Initialize API client
    api_client = SaaSAPIClient()
    
    # Simulate how silence_cutter.py calls record_usage
    video_path = "C:/test/video.mp4"
    duration_minutes = 3.2
    processing_type = "silence_removal"
    
    print(f"📁 Simulating legacy call:")
    print(f"   File Path: {video_path}")
    print(f"   Duration: {duration_minutes} minutes")
    print(f"   Type: {processing_type}")
    
    try:
        # This is how silence_cutter.py calls it
        success = api_client.record_usage(
            file_path=video_path,
            duration_minutes=duration_minutes,
            processing_type=processing_type
        )
        
        if success:
            print(f"✅ Legacy call successful!")
            
            # Check updated stats
            stats = api_client.get_session_stats()
            print(f"📊 Updated session stats:")
            print(f"   Total Minutes: {stats['total_minutes_used']}")
            print(f"   Files Processed: {stats['files_processed']}")
            
            return True
        else:
            print(f"❌ Legacy call failed")
            return False
            
    except Exception as e:
        print(f"❌ Legacy call error: {e}")
        return False

if __name__ == "__main__":
    success = test_legacy_usage()
    
    if success:
        print(f"\n🎉 Legacy compatibility test PASSED!")
        print(f"✅ silence_cutter.py will work correctly")
    else:
        print(f"\n💥 Legacy compatibility test FAILED!")
        print(f"❌ silence_cutter.py needs updating") 