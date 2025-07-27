#!/usr/bin/env python3
"""
Test script for Key Usage Mode functionality
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.service.key.key_manager import KeyManager
from app.config.config import settings

async def test_key_usage_mode():
    """Test the key usage mode functionality"""
    print("=== Testing Key Usage Mode Functionality ===\n")
    
    # Test data
    test_api_keys = ["AIzaSyTest1234567890", "AIzaSyTest0987654321", "AIzaSyTest1111111111"]
    test_vertex_keys = ["vertex_test_key_1", "vertex_test_key_2"]
    
    # Create KeyManager instance
    key_manager = KeyManager(test_api_keys, test_vertex_keys)
    
    print("1. Testing initial state:")
    print(f"   Usage mode: {await key_manager.get_usage_mode()}")
    print(f"   Usage threshold: {await key_manager.get_usage_threshold()}")
    
    # Test polling mode (default)
    print("\n2. Testing polling mode:")
    await key_manager.set_usage_mode("polling")
    
    keys_used = []
    for i in range(6):  # Test more than the number of keys
        key = await key_manager.get_next_key()
        keys_used.append(key)
        usage_count = await key_manager.get_key_usage_count(key)
        print(f"   Iteration {i+1}: Key={key[-8:]}, Usage count={usage_count}")
    
    print(f"   Keys used in order: {[k[-8:] for k in keys_used]}")
    
    # Test fixed mode
    print("\n3. Testing fixed mode:")
    await key_manager.reset_usage_counts()
    await key_manager.set_usage_mode("fixed")
    await key_manager.set_usage_threshold(3)  # Low threshold for testing
    
    keys_used_fixed = []
    for i in range(8):  # Test switching behavior
        key = await key_manager.get_next_key()
        keys_used_fixed.append(key)
        usage_count = await key_manager.get_key_usage_count(key)
        print(f"   Iteration {i+1}: Key={key[-8:]}, Usage count={usage_count}")
    
    print(f"   Keys used in order: {[k[-8:] for k in keys_used_fixed]}")
    
    # Test status information
    print("\n4. Testing status information:")
    status = await key_manager.get_usage_mode_status()
    print(f"   Current mode: {status['usage_mode']}")
    print(f"   Current threshold: {status['usage_threshold']}")
    print(f"   Current fixed key: {status['current_fixed_key'][-8:] if status['current_fixed_key'] else 'None'}")
    print(f"   Current key usage: {status['current_key_usage']}")
    
    # Test key status with usage counts
    print("\n5. Testing key status with usage counts:")
    keys_status = await key_manager.get_keys_by_status()
    print("   Valid keys:")
    for key, info in keys_status['valid_keys'].items():
        if isinstance(info, dict):
            print(f"     {key[-8:]}: fail_count={info['fail_count']}, usage_count={info['usage_count']}")
        else:
            print(f"     {key[-8:]}: fail_count={info}")
    
    print("\n=== All tests completed successfully! ===")

if __name__ == "__main__":
    asyncio.run(test_key_usage_mode())
