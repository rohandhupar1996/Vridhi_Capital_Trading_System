#!/usr/bin/env python3
"""
Check OpenAlgo User Info
"""

from src.openalgo_client import OpenAlgoClient

def check_user():
    """Check OpenAlgo connection and user info"""
    print("=" * 70)
    print("🔍 CHECKING OPENALGO USER INFO")
    print("=" * 70)
    
    try:
        client = OpenAlgoClient()
        
        # Try to get user profile or any endpoint that shows username
        print("\n📋 Attempting to fetch user information...")
        
        # Check positions (this works and shows we're connected)
        positions = client.get_positions()
        
        if positions.get('status') == 'success':
            print("✅ OpenAlgo connection is working")
            print(f"\nAPI Response: {positions}")
            
            # The username you need is your OpenAlgo login username
            print("\n" + "=" * 70)
            print("ℹ️  IMPORTANT:")
            print("=" * 70)
            print("The 'username' in config.py should be your OpenAlgo")
            print("LOGIN USERNAME (the one you use to login to OpenAlgo),")
            print("NOT the Telegram bot handle (@RDXTRADEBOT).")
            print("\n📝 Steps to link Telegram:")
            print("   1. Login to OpenAlgo web interface")
            print("   2. Go to Settings or Profile section")
            print("   3. Find 'Telegram Integration' or 'Link Telegram'")
            print("   4. Follow the instructions to link your Telegram")
            print("   5. Update config.py with your OpenAlgo login username")
            print("=" * 70)
        else:
            print(f"❌ Error: {positions}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_user()

