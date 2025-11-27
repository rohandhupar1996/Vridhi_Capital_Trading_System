#!/usr/bin/env python3
"""
Test OpenAlgo Connection
"""

import sys
from src.openalgo_client import OpenAlgoClient

def test_connection():
    """Test OpenAlgo API connection"""
    print("=" * 70)
    print("🔍 TESTING OPENALGO CONNECTION")
    print("=" * 70)
    
    try:
        # Initialize client
        print("\n1️⃣ Initializing OpenAlgo client...")
        client = OpenAlgoClient()
        print(f"   ✅ Client initialized")
        print(f"   Host: {client.host}")
        print(f"   API Key: {client.api_key[:10]}...{client.api_key[-10:]}")
        
        # Test 1: Get nearest expiry
        print("\n2️⃣ Testing expiry fetch...")
        expiry = client.get_nearest_expiry("BANKNIFTY")
        if expiry:
            print(f"   ✅ Nearest BankNifty expiry: {expiry}")
        else:
            print(f"   ❌ Failed to fetch expiry")
            return False
        
        # Test 2: Get positions
        print("\n3️⃣ Testing position book fetch...")
        positions = client.get_positions()
        if positions.get('status') == 'success':
            print(f"   ✅ Position book fetched successfully")
            if positions.get('data'):
                print(f"   📊 Current positions: {len(positions['data'])}")
            else:
                print(f"   📊 No open positions")
        else:
            print(f"   ⚠️ Position fetch response: {positions}")
        
        # Test 3: Get orderbook
        print("\n4️⃣ Testing order book fetch...")
        orderbook = client.get_orderbook()
        if orderbook.get('status') == 'success':
            print(f"   ✅ Order book fetched successfully")
            if orderbook.get('data'):
                print(f"   📋 Orders: {len(orderbook['data'])}")
            else:
                print(f"   📋 No orders")
        else:
            print(f"   ⚠️ Orderbook fetch response: {orderbook}")
        
        print("\n" + "=" * 70)
        print("✅ CONNECTION TEST COMPLETED SUCCESSFULLY")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n❌ CONNECTION TEST FAILED")
        print(f"Error: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)

