#!/usr/bin/env python3
"""
Test script to verify usage validation works correctly
"""

try:
    from features.api_communication import api_client
    API_COMMUNICATION_AVAILABLE = True
    print("✅ API communication module loaded successfully")
except ImportError as e:
    print(f"⚠️ API communication not available: {e}")
    API_COMMUNICATION_AVAILABLE = False

def test_usage_validation():
    print("🧪 Testing Usage Validation")
    print("=" * 50)
    
    if not API_COMMUNICATION_AVAILABLE:
        print("❌ API communication not available - cannot test")
        return False
    
    # Test with a 5 minute file (should fail if usage is over 60 minutes)
    test_duration = 5.0
    print(f"📹 Testing with {test_duration} minute file...")
    
    try:
        validation_result = api_client.validate_file_usage(
            file_duration_minutes=test_duration
        )
        
        print(f"📊 Validation Result:")
        print(f"   Allowed: {validation_result.get('allowed', False)}")
        print(f"   Message: {validation_result.get('message', 'No message')}")
        print(f"   Remaining: {validation_result.get('remainingMinutes', 0)} minutes")
        
        if not validation_result.get('allowed', False):
            print("✅ PASS: Usage validation correctly blocked processing")
            print("🚫 User should see upgrade message when clicking Export button")
            return True
        else:
            print("❌ FAIL: Usage validation should have blocked processing")
            return False
            
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        return False

def check_current_usage():
    print("\n📊 Current Usage Status")
    print("=" * 30)
    
    if not API_COMMUNICATION_AVAILABLE:
        print("❌ API communication not available")
        return
    
    try:
        # Get current usage from offline tracker
        usage = api_client.offline_tracker.get_session_usage(api_client.session_id)
        print(f"💾 Local Usage:")
        print(f"   Session ID: {api_client.session_id[:16]}...")
        print(f"   Total Minutes: {usage['total_minutes_used']}")
        print(f"   Files Processed: {usage['files_processed']}")
        
        if usage['total_minutes_used'] > 60:
            print("🚨 Usage exceeds free limit of 60 minutes!")
        else:
            print("✅ Usage within free limit")
            
    except Exception as e:
        print(f"❌ Error checking usage: {e}")

if __name__ == "__main__":
    check_current_usage()
    test_usage_validation() 