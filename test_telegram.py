#!/usr/bin/env python3
"""
Test Telegram Notifications
"""

import sys
import time
from src.openalgo_client import OpenAlgoClient
from src.telegram_notifier import TelegramNotifier

def test_telegram():
    """Test all Telegram notification functions"""
    print("=" * 70)
    print("📱 TESTING TELEGRAM NOTIFICATIONS")
    print("=" * 70)
    
    try:
        # Initialize client
        print("\n1️⃣ Initializing OpenAlgo client...")
        client = OpenAlgoClient()
        print(f"   ✅ Client initialized")
        
        # Initialize Telegram notifier
        print("\n2️⃣ Initializing Telegram notifier...")
        telegram = TelegramNotifier(client)
        print(f"   ✅ Telegram notifier initialized")
        print(f"   Username: {telegram.config['username']}")
        print(f"   Enabled: {telegram.config['enabled']}")
        
        if not telegram.config['enabled']:
            print("\n❌ Telegram is DISABLED in config.py")
            print("   Set 'enabled': True in TELEGRAM_CONFIG")
            return False
        
        # Test 1: Simple message
        print("\n3️⃣ Testing simple message...")
        success = telegram.send_message("🧪 Test Message - System is working!")
        if success:
            print("   ✅ Simple message sent successfully")
        else:
            print("   ❌ Failed to send simple message")
            return False
        
        time.sleep(2)
        
        # Test 2: Signal alert (LONG)
        print("\n4️⃣ Testing LONG signal alert...")
        telegram.send_signal_alert("LONG", "30-DEC-25")
        print("   ✅ LONG signal alert sent")
        
        time.sleep(2)
        
        # Test 3: Signal alert (SHORT)
        print("\n5️⃣ Testing SHORT signal alert...")
        telegram.send_signal_alert("SHORT", "30-DEC-25")
        print("   ✅ SHORT signal alert sent")
        
        time.sleep(2)
        
        # Test 4: Execution success alert
        print("\n6️⃣ Testing execution success alert...")
        mock_buy_results = [
            {
                'order_name': 'BUY_ATM_CE',
                'success': True,
                'response': {
                    'symbol': 'BANKNIFTY30DEC2551000CE',
                    'orderid': 'TEST123'
                }
            },
            {
                'order_name': 'BUY_OTM20_PE',
                'success': True,
                'response': {
                    'symbol': 'BANKNIFTY30DEC2550000PE',
                    'orderid': 'TEST124'
                }
            }
        ]
        mock_sell_response = {
            'symbol': 'BANKNIFTY30DEC2551000PE',
            'orderid': 'TEST125'
        }
        telegram.send_execution_success("LONG", "30-DEC-25", mock_buy_results, mock_sell_response, 4.23)
        print("   ✅ Execution success alert sent")
        
        time.sleep(2)
        
        # Test 5: Failure alert
        print("\n7️⃣ Testing failure alert...")
        telegram.send_execution_failure("SHORT", "BUY orders rejected by broker")
        print("   ✅ Failure alert sent")
        
        time.sleep(2)
        
        # Test 6: Partial execution alert
        print("\n8️⃣ Testing partial execution alert...")
        telegram.send_partial_execution("LONG", mock_buy_results)
        print("   ✅ Partial execution alert sent")
        
        time.sleep(2)
        
        # Test 7: Exit alert
        print("\n9️⃣ Testing exit alert...")
        telegram.send_exit_alert()
        print("   ✅ Exit alert sent")
        
        time.sleep(2)
        
        # Test 8: P&L update
        print("\n🔟 Testing P&L update...")
        telegram.send_pnl_update()
        print("   ✅ P&L update sent")
        
        print("\n" + "=" * 70)
        print("✅ ALL TELEGRAM TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\n📱 Check your Telegram bot for all the messages!")
        print("   You should have received 9 different messages.")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TELEGRAM TEST FAILED")
        print(f"Error: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_telegram()
    sys.exit(0 if success else 1)

