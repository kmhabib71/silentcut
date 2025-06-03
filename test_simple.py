import requests

def test_ping_endpoint():
    try:
        print("Testing GET /api/ping...")
        response = requests.get("http://localhost:3000/api/ping", timeout=10)
        print(f"GET Status: {response.status_code}")
        print(f"GET Response: {response.text}")
        
        print("\nTesting POST /api/ping...")
        response = requests.post("http://localhost:3000/api/ping", 
                                json={"test": "data"}, timeout=10)
        print(f"POST Status: {response.status_code}")
        print(f"POST Response: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing ping endpoint...")
    success = test_ping_endpoint()
    print(f"Success: {success}") 