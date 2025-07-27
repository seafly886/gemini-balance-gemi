#!/usr/bin/env python3
"""
Test script for API endpoints
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"
AUTH_TOKEN = "test_token_123"

def test_api_endpoints():
    """Test the key usage mode API endpoints"""
    print("=== Testing API Endpoints ===\n")
    
    # Test GET usage mode status
    print("1. Testing GET /api/keys/usage-mode")
    try:
        response = requests.get(
            f"{BASE_URL}/api/keys/usage-mode",
            cookies={"auth_token": AUTH_TOKEN}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Current mode: {data.get('usage_mode')}")
            print(f"   Threshold: {data.get('usage_threshold')}")
            print(f"   Current key: {data.get('current_fixed_key', 'N/A')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test POST to switch to fixed mode
    print("\n2. Testing POST /api/keys/usage-mode (switch to fixed)")
    try:
        response = requests.post(
            f"{BASE_URL}/api/keys/usage-mode",
            cookies={"auth_token": AUTH_TOKEN},
            headers={"Content-Type": "application/json"},
            data=json.dumps({"mode": "fixed", "threshold": 5})
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Message: {data.get('message')}")
            if 'status' in data:
                status = data['status']
                print(f"   New mode: {status.get('usage_mode')}")
                print(f"   New threshold: {status.get('usage_threshold')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test POST to switch back to polling mode
    print("\n3. Testing POST /api/keys/usage-mode (switch to polling)")
    try:
        response = requests.post(
            f"{BASE_URL}/api/keys/usage-mode",
            cookies={"auth_token": AUTH_TOKEN},
            headers={"Content-Type": "application/json"},
            data=json.dumps({"mode": "polling"})
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Message: {data.get('message')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test reset usage counts
    print("\n4. Testing POST /api/keys/reset-usage-counts")
    try:
        response = requests.post(
            f"{BASE_URL}/api/keys/reset-usage-counts",
            cookies={"auth_token": AUTH_TOKEN}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Message: {data.get('message')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n=== API endpoint tests completed! ===")

if __name__ == "__main__":
    test_api_endpoints()
