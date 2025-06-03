import requests
import json
import time

def test_record_usage_api():
    """Test the record-usage API endpoint directly"""
    
    url = "http://localhost:3000/api/record-usage"
    
    payload = {
        'sessionId': '2b61c9e79c106d9a',
        'permanentId': '2b61c9e79c106d9a',
        'fileDuration': 2.5,
        'fileName': 'test_video.mp4',
        'userId': None,
        'timestamp': int(time.time()),
        'offlineUsage': {
            'total_minutes_used': 7.5,
            'files_processed': 3,
            'first_use_date': '2025-06-03T19:42:58.000Z'
        },
        'deviceInfo': {
            'device_name': 'FARJANA',
            'machine_id': 'test-machine-id',
            'registered_online': True,
            'linked_email': None
        }
    }
    
    print(f"🧪 Testing API endpoint: {url}")
    print(f"📤 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"📥 Response Data: {json.dumps(response_data, indent=2)}")
        except:
            print(f"📥 Response Text: {response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

if __name__ == "__main__":
    print("🔬 API Endpoint Test")
    print("=" * 50)
    
    success = test_record_usage_api()
    
    if success:
        print("\n✅ API test passed!")
    else:
        print("\n❌ API test failed!") 