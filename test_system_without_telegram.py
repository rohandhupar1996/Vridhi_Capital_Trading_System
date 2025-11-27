#!/usr/bin/env python3
"""
Test System Without Telegram (Dry Run)
"""

import sys
from src.openalgo_client import OpenAlgoClient
from src.order_manager import OrderManager
from src.position_executor import PositionExecutor

def test_system():
    """Test system components without Telegram"""
    print("=" * 70)
    print("🧪 TESTING SYSTEM (WITHOUT TELEGRAM)")
    print("=" * 70)
    
    try:
        # Initialize components
        print("\n1️⃣ Initializing OpenAlgo client...")
        client = OpenAlgoClient()
        print("   ✅ Client initialized")
        
        print("\n2️⃣ Initializing Order Manager...")
        order_manager = OrderManager(client)
        print("   ✅ Order Manager initialized")
        
        print("\n3️⃣ Initializing Position Executor (without Telegram)...")
        executor = PositionExecutor(order_manager, telegram_notifier=None)
        print("   ✅ Position Executor initialized")
        print("   ⚠️  Telegram notifications: DISABLED")
        
        print("\n4️⃣ Testing expiry fetch...")
        expiry = client.get_nearest_expiry()
        if expiry:
            print(f"   ✅ Nearest expiry: {expiry}")
        else:
            print("   ❌ Failed to fetch expiry")
            return False
        
        print("\n" + "=" * 70)
        print("✅ SYSTEM COMPONENTS WORKING!")
        print("=" * 70)
        print("\nℹ️  System is ready. To enable Telegram:")
        print("   1. Link your Telegram to OpenAlgo")
        print("   2. Update config.py with correct username")
        print("   3. Run: python test_telegram.py")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_system()
    sys.exit(0 if success else 1)

