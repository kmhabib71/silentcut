#!/usr/bin/env python3
"""
Test script for new admin features:
1. Database control (set usage to 58 minutes for testing)
2. User blocking functionality
3. Subscription plan management
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:3000/api"
ADMIN_ENDPOINTS = {
    "database_control": f"{BASE_URL}/admin/database-control",
    "block_user": f"{BASE_URL}/admin/block-user", 
    "subscription_plans": f"{BASE_URL}/admin/subscription-plans",
    "anonymous_sessions": f"{BASE_URL}/admin/anonymous-sessions"
}

def test_database_control():
    """Test database control functionality"""
    print("🗄️ Testing Database Control")
    print("=" * 40)
    
    # Get current session data first
    try:
        response = requests.get(ADMIN_ENDPOINTS["anonymous_sessions"])
        if response.status_code == 200:
            data = response.json()
            sessions = data.get("anonymousSessions", [])
            
            if sessions:
                session = sessions[0]
                session_id = session["sessionId"]
                permanent_id = session.get("permanentId", session_id)
                
                print(f"📊 Found session: {session_id[:16]}...")
                print(f"   Current usage: {session['totalMinutesUsed']} minutes")
                
                # Test 1: Set usage to 58 minutes (near free limit)
                print(f"\n🎯 Setting usage to 58 minutes...")
                payload = {
                    "action": "setUsage",
                    "sessionId": session_id,
                    "permanentId": permanent_id,
                    "newUsage": 58
                }
                
                response = requests.post(ADMIN_ENDPOINTS["database_control"], json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ {result['message']}")
                    print(f"📈 New usage: {result['totalMinutesUsed']} minutes")
                else:
                    print(f"❌ Failed: {response.status_code} - {response.text}")
                
                # Test 2: Add 5 more minutes to test over-limit
                print(f"\n🎯 Adding 5 minutes (should exceed free limit)...")
                payload = {
                    "action": "addTestUsage",
                    "sessionId": session_id,
                    "permanentId": permanent_id,
                    "newUsage": 5
                }
                
                response = requests.post(ADMIN_ENDPOINTS["database_control"], json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ {result['message']}")
                    print(f"📈 Total usage now: {result['totalMinutesUsed']} minutes")
                    
                    if result['totalMinutesUsed'] > 60:
                        print(f"🚨 Usage exceeded free limit of 60 minutes!")
                else:
                    print(f"❌ Failed: {response.status_code} - {response.text}")
                
                return True
            else:
                print("❌ No anonymous sessions found")
                return False
        else:
            print(f"❌ Failed to get sessions: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_blocking_functionality():
    """Test user/session blocking functionality"""
    print("\n🚫 Testing Blocking Functionality")
    print("=" * 40)
    
    try:
        # Get anonymous sessions to block
        response = requests.get(ADMIN_ENDPOINTS["anonymous_sessions"])
        if response.status_code == 200:
            data = response.json()
            sessions = data.get("anonymousSessions", [])
            
            if sessions:
                session = sessions[0]
                session_id = session["sessionId"]
                
                print(f"🎯 Testing block on session: {session_id[:16]}...")
                
                # Test blocking
                payload = {
                    "action": "block",
                    "targetId": session_id,
                    "targetType": "anonymous",
                    "reason": "Testing blocking functionality",
                    "duration": 24,  # 24 hours
                    "adminId": "test_admin"
                }
                
                response = requests.post(ADMIN_ENDPOINTS["block_user"], json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ {result['message']}")
                    print(f"🚫 Blocked until: {result.get('blockedUntil', 'Permanent')}")
                    print(f"📝 Reason: {result['reason']}")
                    
                    # Test unblocking
                    print(f"\n🔓 Testing unblock...")
                    payload = {
                        "action": "unblock",
                        "targetId": session_id,
                        "targetType": "anonymous",
                        "adminId": "test_admin"
                    }
                    
                    response = requests.post(ADMIN_ENDPOINTS["block_user"], json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"✅ {result['message']}")
                        return True
                    else:
                        print(f"❌ Unblock failed: {response.status_code}")
                        return False
                else:
                    print(f"❌ Block failed: {response.status_code} - {response.text}")
                    return False
            else:
                print("❌ No sessions to test blocking")
                return False
        else:
            print(f"❌ Failed to get sessions: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_subscription_plans():
    """Test subscription plan management"""
    print("\n💳 Testing Subscription Plans")
    print("=" * 40)
    
    try:
        # Get subscription plan information
        response = requests.get(ADMIN_ENDPOINTS["subscription_plans"])
        
        if response.status_code == 200:
            data = response.json()
            plans = data.get("plans", {})
            
            print("📋 Available Plans:")
            for plan_id, plan_info in plans.items():
                print(f"   {plan_info['name']}: ${plan_info['price']}")
                print(f"   - {plan_info['monthlyMinutes']} minutes/month")
                print(f"   - Features: {', '.join(plan_info['features'])}")
                print()
            
            stats = data.get("statistics", [])
            print("📊 Current Statistics:")
            for stat in stats:
                plan_name = stat['_id'] or 'Unknown'
                print(f"   {plan_name}: {stat['count']} users, ${stat['totalRevenue']} revenue")
            
            print(f"\n📈 Total Users: {data.get('totalUsers', 0)}")
            print(f"🔥 Active Subscriptions: {data.get('activeSubscriptions', 0)}")
            
            return True
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Admin Features Test Suite")
    print("=" * 50)
    
    results = []
    
    # Test 1: Database Control
    results.append(("Database Control", test_database_control()))
    
    # Test 2: Blocking Functionality  
    results.append(("Blocking Functionality", test_blocking_functionality()))
    
    # Test 3: Subscription Plans
    results.append(("Subscription Plans", test_subscription_plans()))
    
    # Summary
    print("\n📋 Test Results Summary")
    print("=" * 30)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All admin features working correctly!")
    else:
        print("⚠️ Some features need attention")

if __name__ == "__main__":
    main() 