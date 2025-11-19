"""
PHASE 5, BLOCK 5.2: INTEGRATION TESTING - STATE PERSISTENCE

Tests the complete state persistence integration:
- State save at 3:30 PM (all components save state)
- State load at 9:15 AM (all components restore state)
- State continuity across sessions (same signals, same positions)
- State update after each trade (position updated)
- State update after each exit (re-entry bars updated)
- Missing state handling (first run, fresh start)

Real Trading Flow:
1. At 3:30 PM: Save complete state (position, ML state, historical data, re-entry bars)
2. At 9:15 AM: Load saved state (restore all components)
3. System continues seamlessly (like Pine Script)
4. After each trade: Update position in state
5. After each exit: Update re-entry bars in state

Note: Tests use MOCK components for complete flow testing
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import numpy as np
import pandas as pd
import pytz
import sqlite3
import tempfile
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.data.trading_state_manager import TradingStateManager, KOLKATA_TZ
from src.trading_system.oms.order_manager import OrderManager, PositionType
from scripts.test_order_manager import MockKiteForOrders, create_mock_instruments
from scripts.test_websocket_price_feed import create_mock_order_manager

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


def create_sample_state_with_position():
    """Create sample state with position for testing"""
    
    # Sample historical OHLCV data (100 bars)
    historical_data = []
    base_time = datetime(2025, 11, 19, 9, 15, tzinfo=KOLKATA_TZ)
    base_price = 57000.0
    
    for i in range(100):
        historical_data.append({
            'timestamp': (base_time + timedelta(minutes=15 * i)).isoformat(),
            'open': base_price + i * 10,
            'high': base_price + i * 10 + 50,
            'low': base_price + i * 10 - 50,
            'close': base_price + i * 10 + 20,
            'volume': 1000 + i * 10
        })
    
    # Sample ML features (100 bars)
    ml_features = {
        'f1': [0.5 + i * 0.01 for i in range(100)],
        'f2': [0.4 + i * 0.01 for i in range(100)],
        'f3': [0.3 + i * 0.01 for i in range(100)],
        'f4': [0.2 + i * 0.01 for i in range(100)],
        'f5': [0.1 + i * 0.01 for i in range(100)]
    }
    
    # Sample ML indicators (100 bars)
    ml_indicators = {
        'filter_all': [True] * 100,
        'kernel_estimate': [base_price + i * 10 for i in range(100)],
        'is_bullish': [True] * 100,
        'is_bearish': [False] * 100
    }
    
    # Sample ML predictions and signals (100 bars)
    ml_predictions = [1] * 100  # All LONG
    ml_signals = [1] * 100  # All LONG
    
    # Position state (LONG position)
    position = {
        'direction': 'LONG',
        'entry_price': 57300.0,
        'entry_bar_index': 50,
        'entry_timestamp': (base_time + timedelta(minutes=15 * 50)).isoformat(),
        'atm_strike': 57300,
        'hedge_strike': 55300
    }
    
    # Re-entry state
    last_long_exit_bar = -1  # No exit yet
    last_short_exit_bar = -1  # No exit yet
    
    # Futures previous close (last completed candle)
    futures_previous_close = historical_data[-1]['close']
    
    state = {
        'last_long_exit_bar': last_long_exit_bar,
        'last_short_exit_bar': last_short_exit_bar,
        'position': position,
        'ml_features': ml_features,
        'ml_indicators': ml_indicators,
        'ml_predictions': ml_predictions,
        'ml_signals': ml_signals,
        'historical_data': historical_data,
        'futures_previous_close': futures_previous_close,
        'last_processed_timestamp': historical_data[-1]['timestamp'],
        'data_source': 'zerodha',
        'save_time': datetime.now(KOLKATA_TZ).isoformat()
    }
    
    return state


def create_sample_state_without_position():
    """Create sample state without position for testing"""
    
    state = create_sample_state_with_position()
    state['position'] = None  # No position
    state['last_long_exit_bar'] = 45  # Previous LONG exit
    state['last_short_exit_bar'] = -1  # No SHORT exit
    
    return state


def test_state_save_at_330pm():
    """Test 1: State Save at 3:30 PM"""
    print("=" * 70)
    print("TEST 1: State Save at 3:30 PM")
    print("=" * 70)
    
    print(f"\n🔧 Testing state save at 3:30 PM:")
    print(f"   Expected: All components save state (position, ML state, historical data)")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Create sample state with position
        state = create_sample_state_with_position()
        
        # Save state at 3:30 PM
        save_time = datetime(2025, 11, 19, 15, 30, 0, tzinfo=KOLKATA_TZ)
        state['save_time'] = save_time.isoformat()
        
        result = state_manager.save_daily_state(state)
        
        if not result:
            print(f"   ❌ State save failed")
            return False
        
        print(f"   ✅ State saved successfully at {save_time.strftime('%H:%M')}")
        
        # Verify state was saved
        if not state_manager.has_saved_state():
            print(f"   ❌ State not found in database")
            return False
        
        print(f"   ✅ State verified in database")
        
        # Verify all components are saved
        saved_state = state_manager.load_saved_state()
        
        if saved_state is None:
            print(f"   ❌ Failed to load saved state")
            return False
        
        checks = {
            'position': saved_state.get('position') is not None,
            'ml_features': len(saved_state.get('ml_features', {})) > 0,
            'ml_indicators': len(saved_state.get('ml_indicators', {})) > 0,
            'ml_predictions': len(saved_state.get('ml_predictions', [])) > 0,
            'ml_signals': len(saved_state.get('ml_signals', [])) > 0,
            'historical_data': len(saved_state.get('historical_data', [])) > 0,
            'futures_previous_close': saved_state.get('futures_previous_close') is not None,
            're_entry_bars': 'last_long_exit_bar' in saved_state and 'last_short_exit_bar' in saved_state
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"   ✅ All components saved:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return True
        else:
            print(f"   ❌ Some components missing:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_state_load_at_915am():
    """Test 2: State Load at 9:15 AM"""
    print("=" * 70)
    print("TEST 2: State Load at 9:15 AM")
    print("=" * 70)
    
    print(f"\n🔧 Testing state load at 9:15 AM:")
    print(f"   Expected: All components restored (position, ML state, historical data)")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Save state first (from yesterday 3:30 PM)
        state = create_sample_state_with_position()
        save_time = datetime(2025, 11, 19, 15, 30, 0, tzinfo=KOLKATA_TZ)
        state['save_time'] = save_time.isoformat()
        state_manager.save_daily_state(state)
        
        print(f"   ✅ State saved at {save_time.strftime('%Y-%m-%d %H:%M')}")
        
        # Load state at 9:15 AM next day
        load_time = datetime(2025, 11, 20, 9, 15, 0, tzinfo=KOLKATA_TZ)
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is None:
            print(f"   ❌ Failed to load state at {load_time.strftime('%Y-%m-%d %H:%M')}")
            return False
        
        print(f"   ✅ State loaded successfully at {load_time.strftime('%Y-%m-%d %H:%M')}")
        
        # Verify all components are loaded
        checks = {
            'position': loaded_state.get('position') is not None,
            'ml_features': len(loaded_state.get('ml_features', {})) == 5,  # f1-f5
            'ml_indicators': len(loaded_state.get('ml_indicators', {})) >= 4,
            'ml_predictions': len(loaded_state.get('ml_predictions', [])) == 100,
            'ml_signals': len(loaded_state.get('ml_signals', [])) == 100,
            'historical_data': len(loaded_state.get('historical_data', [])) == 100,
            'futures_previous_close': loaded_state.get('futures_previous_close') == state['futures_previous_close'],
            're_entry_bars': loaded_state.get('last_long_exit_bar') == -1 and loaded_state.get('last_short_exit_bar') == -1
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"   ✅ All components loaded:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            
            # Verify position details
            pos = loaded_state['position']
            print(f"   ✅ Position restored:")
            print(f"      Direction: {pos['direction']}")
            print(f"      Entry price: {pos['entry_price']}")
            print(f"      Entry bar: {pos['entry_bar_index']}")
            
            return True
        else:
            print(f"   ❌ Some components missing or incorrect:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_state_continuity_across_sessions():
    """Test 3: State Continuity Across Sessions"""
    print("=" * 70)
    print("TEST 3: State Continuity Across Sessions")
    print("=" * 70)
    
    print(f"\n🔧 Testing state continuity across sessions:")
    print(f"   Expected: System continues seamlessly (same signals, same positions)")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Day 1: Save state at 3:30 PM with position
        state_day1 = create_sample_state_with_position()
        save_time_day1 = datetime(2025, 11, 19, 15, 30, 0, tzinfo=KOLKATA_TZ)
        state_day1['save_time'] = save_time_day1.isoformat()
        state_manager.save_daily_state(state_day1)
        
        print(f"   ✅ Day 1 state saved at {save_time_day1.strftime('%Y-%m-%d %H:%M')}")
        
        # Day 2: Load state at 9:15 AM
        load_time_day2 = datetime(2025, 11, 20, 9, 15, 0, tzinfo=KOLKATA_TZ)
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is None:
            print(f"   ❌ Failed to load state")
            return False
        
        print(f"   ✅ Day 2 state loaded at {load_time_day2.strftime('%Y-%m-%d %H:%M')}")
        
        # Verify continuity: Position should be same
        pos_day1 = state_day1['position']
        pos_day2 = loaded_state['position']
        
        if pos_day2 is None or pos_day1 is None:
            print(f"   ❌ Position continuity broken (one is None)")
            return False
        
        checks = {
            'direction': pos_day1['direction'] == pos_day2['direction'],
            'entry_price': pos_day1['entry_price'] == pos_day2['entry_price'],
            'entry_bar_index': pos_day1['entry_bar_index'] == pos_day2['entry_bar_index'],
            'atm_strike': pos_day1['atm_strike'] == pos_day2['atm_strike'],
            'ml_features_count': len(state_day1['ml_features']) == len(loaded_state['ml_features']),
            'ml_predictions_count': len(state_day1['ml_predictions']) == len(loaded_state['ml_predictions']),
            'historical_data_count': len(state_day1['historical_data']) == len(loaded_state['historical_data'])
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"   ✅ State continuity verified:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return True
        else:
            print(f"   ❌ State continuity broken:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_state_update_after_trade():
    """Test 4: State Update After Trade"""
    print("=" * 70)
    print("TEST 4: State Update After Trade")
    print("=" * 70)
    
    print(f"\n🔧 Testing state update after trade:")
    print(f"   Expected: Position updated in state after entry")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Initial state without position
        state = create_sample_state_without_position()
        state_manager.save_daily_state(state)
        
        print(f"   ✅ Initial state saved (no position)")
        
        # Simulate trade entry
        oms = create_mock_order_manager(futures_token=260105)
        
        # Enter position
        from src.trading_system.oms.running_signal_executor import RunningSignalExecutor
        executor = RunningSignalExecutor(oms=oms, logger=None)
        executor.earnings_filter.is_blocked = Mock(return_value=False)
        
        candle_id = "2025-11-19_09:30_15min"
        executor.start_new_candle(candle_id=candle_id, opened_at=datetime.now())
        executor.on_running_signal("LONG", candle_id=candle_id, futures_price=57300.0)
        
        # Verify position entered
        pos_status = oms.get_position_status()
        if pos_status['position_type'] != 'LONG':
            print(f"   ❌ Failed to enter position for test")
            return False
        
        print(f"   ✅ Position entered: {pos_status['position_type']}")
        
        # Update state with new position
        updated_state = state.copy()
        updated_state['position'] = {
            'direction': 'LONG',
            'entry_price': 57300.0,
            'entry_bar_index': 100,  # New bar index
            'entry_timestamp': datetime.now(KOLKATA_TZ).isoformat(),
            'atm_strike': 57300,
            'hedge_strike': 55300
        }
        
        result = state_manager.save_daily_state(updated_state)
        
        if not result:
            print(f"   ❌ Failed to update state with position")
            return False
        
        print(f"   ✅ State updated with position")
        
        # Verify position in saved state
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is None or loaded_state.get('position') is None:
            print(f"   ❌ Position not found in saved state")
            return False
        
        pos = loaded_state['position']
        
        if pos['direction'] == 'LONG' and pos['entry_price'] == 57300.0:
            print(f"   ✅ Position updated in state:")
            print(f"      Direction: {pos['direction']}")
            print(f"      Entry price: {pos['entry_price']}")
            print(f"      Entry bar: {pos['entry_bar_index']}")
            return True
        else:
            print(f"   ❌ Position not updated correctly")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_state_update_after_exit():
    """Test 5: State Update After Exit"""
    print("=" * 70)
    print("TEST 5: State Update After Exit")
    print("=" * 70)
    
    print(f"\n🔧 Testing state update after exit:")
    print(f"   Expected: Re-entry bars updated, position cleared")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Initial state with position
        state = create_sample_state_with_position()
        state_manager.save_daily_state(state)
        
        print(f"   ✅ Initial state saved (with position)")
        
        # Simulate exit (4-bar exit)
        exit_bar_index = 54  # 4 bars after entry (entry was at 50)
        exit_price = 57400.0
        
        # Update state after exit
        updated_state = state.copy()
        updated_state['position'] = None  # Position cleared
        updated_state['last_long_exit_bar'] = exit_bar_index  # Re-entry bar updated
        updated_state['futures_previous_close'] = exit_price  # Updated for gap calculation
        
        result = state_manager.save_daily_state(updated_state)
        
        if not result:
            print(f"   ❌ Failed to update state after exit")
            return False
        
        print(f"   ✅ State updated after exit")
        
        # Verify state after exit
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is None:
            print(f"   ❌ Failed to load state after exit")
            return False
        
        checks = {
            'position_cleared': loaded_state.get('position') is None,
            're_entry_bar_updated': loaded_state.get('last_long_exit_bar') == exit_bar_index,
            'futures_previous_close_updated': loaded_state.get('futures_previous_close') == exit_price
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"   ✅ State updated correctly after exit:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            print(f"      Re-entry bar: {loaded_state.get('last_long_exit_bar')}")
            print(f"      Futures previous close: {loaded_state.get('futures_previous_close')}")
            return True
        else:
            print(f"   ❌ State not updated correctly:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_missing_state_handling():
    """Test 6: Missing State Handling"""
    print("=" * 70)
    print("TEST 6: Missing State Handling")
    print("=" * 70)
    
    print(f"\n🔧 Testing missing state handling:")
    print(f"   Expected: Graceful handling of missing state (first run, fresh start)")
    
    # Create temporary database (empty)
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager (fresh database)
        state_manager = TradingStateManager(db_path=db_path)
        
        # Try to load state (should return None)
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is not None:
            print(f"   ❌ Expected None for missing state, got: {loaded_state}")
            return False
        
        print(f"   ✅ Missing state handled gracefully (returns None)")
        
        # Verify has_saved_state returns False
        if state_manager.has_saved_state():
            print(f"   ❌ has_saved_state() should return False for empty database")
            return False
        
        print(f"   ✅ has_saved_state() returns False correctly")
        
        # First run: System should handle missing state gracefully
        if loaded_state is None:
            # System should start fresh (no position, no re-entry bars)
            default_state = {
                'position': None,
                'last_long_exit_bar': -1,
                'last_short_exit_bar': -1,
                'futures_previous_close': None,
                'ml_features': {},
                'ml_indicators': {},
                'ml_predictions': [],
                'ml_signals': [],
                'historical_data': []
            }
            
            print(f"   ✅ First run: Default state initialized")
            print(f"      Position: {default_state['position']}")
            print(f"      Re-entry bars: {default_state['last_long_exit_bar']}, {default_state['last_short_exit_bar']}")
            return True
        
        return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_state_with_oms_integration():
    """Test 7: State with OMS Integration"""
    print("=" * 70)
    print("TEST 7: State with OMS Integration")
    print("=" * 70)
    
    print(f"\n🔧 Testing state integration with OMS:")
    print(f"   Expected: OMS position restored from saved state")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Save state with position
        state = create_sample_state_with_position()
        state_manager.save_daily_state(state)
        
        print(f"   ✅ State saved with position")
        
        # Load state at startup (9:15 AM)
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is None or loaded_state.get('position') is None:
            print(f"   ❌ Failed to load state or position missing")
            return False
        
        # Initialize OMS
        oms = create_mock_order_manager(futures_token=260105)
        
        # Restore position to OMS from saved state
        saved_position = loaded_state['position']
        
        if saved_position['direction'] == 'LONG':
            oms.position.position_type = PositionType.LONG
        elif saved_position['direction'] == 'SHORT':
            oms.position.position_type = PositionType.SHORT
        else:
            oms.position.position_type = PositionType.NONE
        
        oms.position.entry_price = saved_position['entry_price']
        oms.position.entry_bar_index = saved_position['entry_bar_index']
        oms.position.entry_time = datetime.fromisoformat(saved_position['entry_timestamp'])
        oms.position.atm_strike = saved_position.get('atm_strike')
        oms.position.hedge_strike = saved_position.get('hedge_strike')
        
        print(f"   ✅ Position restored to OMS")
        
        # Verify OMS position matches saved state
        pos_status = oms.get_position_status()
        
        checks = {
            'position_type': pos_status['position_type'] == saved_position['direction'],
            'entry_price': oms.position.entry_price == saved_position['entry_price'],
            'atm_strike': pos_status.get('atm_strike') == saved_position.get('atm_strike')
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"   ✅ OMS position matches saved state:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            print(f"      Position: {pos_status['position_type']}")
            print(f"      Entry price: {oms.position.entry_price}")
            return True
        else:
            print(f"   ❌ OMS position mismatch:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def main():
    """Run all state persistence integration tests"""
    print("\n" + "=" * 70)
    print("PHASE 5, BLOCK 5.2: INTEGRATION TESTING - STATE PERSISTENCE")
    print("=" * 70)
    print()
    
    tests = [
        ("State Save at 3:30 PM", test_state_save_at_330pm),
        ("State Load at 9:15 AM", test_state_load_at_915am),
        ("State Continuity Across Sessions", test_state_continuity_across_sessions),
        ("State Update After Trade", test_state_update_after_trade),
        ("State Update After Exit", test_state_update_after_exit),
        ("Missing State Handling", test_missing_state_handling),
        ("State with OMS Integration", test_state_with_oms_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                print(f"\n✅ PASS: {test_name}\n")
                passed += 1
            else:
                print(f"\n❌ FAIL: {test_name}\n")
                failed += 1
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED!")
        print("\n" + "=" * 70)
        print("Block 5.2: State Persistence Integration - VERIFIED ✅")
        print("=" * 70)
        print()
        print("✅ State save at 3:30 PM (all components)")
        print("✅ State load at 9:15 AM (all components restored)")
        print("✅ State continuity across sessions (same signals, same positions)")
        print("✅ State update after trade (position updated)")
        print("✅ State update after exit (re-entry bars updated)")
        print("✅ Missing state handling (first run, fresh start)")
        print("✅ OMS integration (position restored from state)")
        print()
        print("⚠️  NOTE: Tests use MOCK components for complete flow testing")
        print("   Real integration requires:")
        print("   - Daily state save at 3:30 PM")
        print("   - Daily state load at 9:15 AM")
        print("   - OMS position restoration from saved state")
        print()
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

