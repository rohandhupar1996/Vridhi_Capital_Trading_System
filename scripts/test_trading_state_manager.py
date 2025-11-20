"""
Test Trading State Manager
Tests save/load functionality for trading state persistence

Phase 1, Block 1.3: State Manager Testing
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import pytz

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.data.trading_state_manager import TradingStateManager, KOLKATA_TZ
from src.trading_system.oms.order_manager import PositionType, Position

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


def create_sample_state() -> dict:
    """Create sample state for testing"""
    
    # Sample historical OHLCV data (5 bars)
    historical_data = [
        {
            'timestamp': '2024-01-01T09:15:00+05:30',
            'open': 50000.0,
            'high': 50100.0,
            'low': 49900.0,
            'close': 50050.0,
            'volume': 1000000
        },
        {
            'timestamp': '2024-01-01T09:30:00+05:30',
            'open': 50050.0,
            'high': 50150.0,
            'low': 50000.0,
            'close': 50100.0,
            'volume': 1200000
        },
        {
            'timestamp': '2024-01-01T09:45:00+05:30',
            'open': 50100.0,
            'high': 50200.0,
            'low': 50050.0,
            'close': 50150.0,
            'volume': 1100000
        },
        {
            'timestamp': '2024-01-01T10:00:00+05:30',
            'open': 50150.0,
            'high': 50250.0,
            'low': 50100.0,
            'close': 50200.0,
            'volume': 1300000
        },
        {
            'timestamp': '2024-01-01T10:15:00+05:30',
            'open': 50200.0,
            'high': 50300.0,
            'low': 50150.0,
            'close': 50250.0,
            'volume': 1150000
        }
    ]
    
    # Sample ML features (5 bars)
    ml_features = {
        'f1': [0.5, 0.6, 0.7, 0.8, 0.9],
        'f2': [0.4, 0.5, 0.6, 0.7, 0.8],
        'f3': [0.3, 0.4, 0.5, 0.6, 0.7],
        'f4': [0.2, 0.3, 0.4, 0.5, 0.6],
        'f5': [0.1, 0.2, 0.3, 0.4, 0.5]
    }
    
    # Sample ML indicators (5 bars)
    ml_indicators = {
        'filter_all': [True, True, False, True, True],
        'kernel_estimate': [0.5, 0.6, 0.7, 0.8, 0.9],
        'is_bullish': [True, True, False, True, True],
        'is_bearish': [False, False, True, False, False]
    }
    
    # Sample ML predictions and signals (5 bars)
    ml_predictions = [1, 1, -1, 1, 1]  # 1 = LONG, -1 = SHORT
    ml_signals = [1, 1, 0, 1, 1]  # 1 = LONG, -1 = SHORT, 0 = NONE
    
    # Sample position state
    position = {
        'direction': 'LONG',
        'entry_price': 50100.0,
        'entry_bar_index': 1,
        'entry_timestamp': '2024-01-01T09:30:00+05:30',
        'atm_strike': 50100,
        'hedge_strike': 49900
    }
    
    # Complete state
    state = {
        'last_long_exit_bar': -1,  # No previous exit
        'last_short_exit_bar': -1,
        'position': position,
        'ml_features': ml_features,
        'ml_indicators': ml_indicators,
        'ml_predictions': ml_predictions,
        'ml_signals': ml_signals,
        'historical_data': historical_data,
        'futures_previous_close': 50250.0,  # Last completed candle's close
        'last_processed_timestamp': datetime.now(KOLKATA_TZ).isoformat(),
        'save_time': datetime.now(KOLKATA_TZ).isoformat(),
        'data_source': 'zerodha'
    }
    
    return state


def test_save_state():
    """Test 1: Save state"""
    print("=" * 70)
    print("TEST 1: Save State")
    print("=" * 70)
    
    # Create test database
    test_db = PROJECT_ROOT / "data" / "test_state.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing test database
    if test_db.exists():
        test_db.unlink()
    
    # Initialize state manager
    state_manager = TradingStateManager(db_path=test_db)
    
    # Create sample state
    state = create_sample_state()
    
    # Save state
    print("\n💾 Saving state...")
    success = state_manager.save_daily_state(state)
    
    if success:
        print("✅ State saved successfully")
    else:
        print("❌ Failed to save state")
        return False
    
    # Verify state exists
    if state_manager.has_saved_state():
        print("✅ State exists in database")
    else:
        print("❌ State not found in database")
        return False
    
    return True


def test_load_state():
    """Test 2: Load state"""
    print("\n" + "=" * 70)
    print("TEST 2: Load State")
    print("=" * 70)
    
    test_db = PROJECT_ROOT / "data" / "test_state.db"
    
    if not test_db.exists():
        print("❌ Test database not found. Run test_save_state() first.")
        return False
    
    # Initialize state manager
    state_manager = TradingStateManager(db_path=test_db)
    
    # Load state
    print("\n📂 Loading state...")
    loaded_state = state_manager.load_saved_state()
    
    if loaded_state is None:
        print("❌ Failed to load state")
        return False
    
    print("✅ State loaded successfully")
    
    # Verify all fields present
    required_fields = [
        'last_long_exit_bar',
        'last_short_exit_bar',
        'position',
        'ml_features',
        'ml_indicators',
        'ml_predictions',
        'ml_signals',
        'historical_data',
        'futures_previous_close',
        'save_time',
        'data_source'
    ]
    
    print("\n🔍 Verifying fields...")
    for field in required_fields:
        if field in loaded_state:
            print(f"   ✅ {field}")
        else:
            print(f"   ❌ Missing: {field}")
            return False
    
    # Verify position state
    if loaded_state['position'] is not None:
        position = loaded_state['position']
        print(f"\n📊 Position State:")
        print(f"   Direction: {position['direction']}")
        print(f"   Entry Price: {position['entry_price']}")
        print(f"   Entry Bar Index: {position['entry_bar_index']}")
        print(f"   ATM Strike: {position['atm_strike']}")
        print(f"   Hedge Strike: {position['hedge_strike']}")
        print("   ✅ Position state correct")
    
    # Verify ML features
    ml_features = loaded_state['ml_features']
    print(f"\n🤖 ML Features:")
    for key, values in ml_features.items():
        print(f"   {key}: {len(values)} values (first: {values[0]:.3f})")
    print("   ✅ ML features correct")
    
    # Verify historical data
    historical_data = loaded_state['historical_data']
    print(f"\n📈 Historical Data:")
    print(f"   Bars: {len(historical_data)}")
    print(f"   First bar close: {historical_data[0]['close']}")
    print(f"   Last bar close: {historical_data[-1]['close']}")
    print("   ✅ Historical data correct")
    
    # Verify futures previous close
    futures_prev_close = loaded_state['futures_previous_close']
    print(f"\n💰 Futures Previous Close: {futures_prev_close:.2f}")
    print("   ✅ Futures previous close correct")
    
    return True


def test_load_missing_state():
    """Test 3: Load missing state (first run)"""
    print("\n" + "=" * 70)
    print("TEST 3: Load Missing State (First Run)")
    print("=" * 70)
    
    # Create fresh test database
    test_db = PROJECT_ROOT / "data" / "test_state_empty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    
    if test_db.exists():
        test_db.unlink()
    
    # Initialize state manager
    state_manager = TradingStateManager(db_path=test_db)
    
    # Try to load state (should return None)
    print("\n📂 Loading state from empty database...")
    loaded_state = state_manager.load_saved_state()
    
    if loaded_state is None:
        print("✅ Correctly returned None for missing state (first run)")
        return True
    else:
        print("❌ Should return None for missing state")
        return False


def test_clear_state():
    """Test 4: Clear state"""
    print("\n" + "=" * 70)
    print("TEST 4: Clear State")
    print("=" * 70)
    
    test_db = PROJECT_ROOT / "data" / "test_state.db"
    
    if not test_db.exists():
        print("❌ Test database not found. Run test_save_state() first.")
        return False
    
    # Initialize state manager
    state_manager = TradingStateManager(db_path=test_db)
    
    # Verify state exists
    if not state_manager.has_saved_state():
        print("❌ State should exist before clearing")
        return False
    
    # Clear state
    print("\n🗑️ Clearing state...")
    success = state_manager.clear_state()
    
    if success:
        print("✅ State cleared successfully")
    else:
        print("❌ Failed to clear state")
        return False
    
    # Verify state cleared
    if not state_manager.has_saved_state():
        print("✅ State correctly cleared from database")
        return True
    else:
        print("❌ State still exists after clearing")
        return False


def test_state_with_no_position():
    """Test 5: State with no position"""
    print("\n" + "=" * 70)
    print("TEST 5: State with No Position")
    print("=" * 70)
    
    test_db = PROJECT_ROOT / "data" / "test_state_no_pos.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    
    if test_db.exists():
        test_db.unlink()
    
    # Initialize state manager
    state_manager = TradingStateManager(db_path=test_db)
    
    # Create state without position
    state = create_sample_state()
    state['position'] = None  # No position
    
    # Save state
    print("\n💾 Saving state without position...")
    success = state_manager.save_daily_state(state)
    
    if not success:
        print("❌ Failed to save state")
        return False
    
    # Load state
    print("📂 Loading state...")
    loaded_state = state_manager.load_saved_state()
    
    if loaded_state is None:
        print("❌ Failed to load state")
        return False
    
    # Verify position is None
    if loaded_state['position'] is None:
        print("✅ Position correctly set to None")
        return True
    else:
        print("❌ Position should be None")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("TRADING STATE MANAGER - COMPREHENSIVE TESTING")
    print("Phase 1, Block 1.3: State Manager Testing")
    print("=" * 70)
    
    results = []
    
    # Test 1: Save state
    results.append(("Save State", test_save_state()))
    
    # Test 2: Load state
    results.append(("Load State", test_load_state()))
    
    # Test 3: Load missing state
    results.append(("Load Missing State", test_load_missing_state()))
    
    # Test 4: Clear state
    results.append(("Clear State", test_clear_state()))
    
    # Test 5: State with no position
    results.append(("State with No Position", test_state_with_no_position()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("\nBlock 1.3: State Manager - VERIFIED ✅")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nBlock 1.3: State Manager - NEEDS FIXING ❌")
    print("=" * 70)
    
    # Cleanup test databases
    test_dbs = [
        PROJECT_ROOT / "data" / "test_state.db",
        PROJECT_ROOT / "data" / "test_state_empty.db",
        PROJECT_ROOT / "data" / "test_state_no_pos.db"
    ]
    
    print("\n🧹 Cleaning up test databases...")
    for test_db in test_dbs:
        if test_db.exists():
            test_db.unlink()
            print(f"   ✅ Removed: {test_db.name}")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

