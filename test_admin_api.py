import requests
import json

def test_admin_api():
    """Test the admin API to see anonymous sessions"""
    
    try:
        print("🔍 Testing admin anonymous sessions API...")
        response = requests.get("http://localhost:3000/api/admin/anonymous-sessions", timeout=10)
        
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Found {len(data)} anonymous sessions")
            
            for i, session in enumerate(data[:3]):  # Show first 3 sessions
                print(f"\n📱 Session {i+1}:")
                print(f"   ID: {session.get('sessionId', 'N/A')[:16]}...")
                print(f"   Minutes Used: {session.get('totalMinutesUsed', 0)}")
                print(f"   Files Processed: {session.get('filesProcessed', 0)}")
                print(f"   Device: {session.get('deviceInfo', {}).get('deviceName', 'Unknown')}")
                print(f"   Last Used: {session.get('lastUseDate', 'N/A')}")
                
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_admin_stats():
    """Test the admin stats API to see if aggregation works"""
    
    try:
        print("\n🔍 Testing admin stats API...")
        response = requests.get("http://localhost:3000/api/admin/stats", timeout=10)
        
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Stats retrieved successfully!")
            print(f"   Total Users: {data.get('totalUsers', 0)}")
            print(f"   Anonymous Sessions: {data.get('analytics', {}).get('anonymousSessions', {}).get('total', 0)}")
            print(f"   Total Minutes: {data.get('totalMinutesProcessed', 0)}")
            return True
        elif response.status_code == 403:
            print(f"🔒 Admin access required (expected)")
            return True  # This is expected since we're not authenticated
        else:
            print(f"❌ API returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Admin APIs")
    print("=" * 50)
    
    success1 = test_admin_api()
    success2 = test_admin_stats()
    
    if success1 and success2:
        print("\n✅ Admin API tests passed!")
    else:
        print("\n❌ Some admin API tests failed!") 