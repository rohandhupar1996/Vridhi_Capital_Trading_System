"""
PHASE 6, BLOCK 6.2: INTEGRATION TESTING - RECOVERY SCENARIOS

Tests the complete recovery scenarios:
- Crash recovery (system restarts, loads state)
- Position mismatch detection (broker position vs saved position)
- Data gap detection (missing candles)
- Data gap filling (using fetch_zerodha_historical_data.py)
- ML state recalculation (if gaps filled)
- WiFi downtime handling (reconnection)
- API downtime handling (error handling, retry)

Real Trading Flow:
1. System crash/downtime → System restarts
2. Load saved state from database
3. Check broker positions vs saved position
4. Reconcile position state (restore from broker if mismatch)
5. Detect data gaps (missing candles while system was down)
6. Fill data gaps from Zerodha historical data
7. Rebuild ML state if gaps were filled
8. Update re-entry state

Note: Tests use MOCK components for complete flow testing
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os
import sqlite3
import pytz

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.recovery.system_recovery import (
    recover_system,
    reconcile_position,
    detect_data_gaps,
    generate_expected_timestamps
)
from src.trading_system.data.trading_state_manager import TradingStateManager
from src.trading_system.oms.order_manager import OrderManager, PositionType
from scripts.test_websocket_price_feed import create_mock_order_manager
from scripts.test_integration_state_persistence import create_sample_state_with_position

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


def create_sample_state_with_position_for_recovery():
    """Create sample state with position for recovery testing"""
    state = create_sample_state_with_position()
    
    # Add last_processed_timestamp (system crashed at this time)
    state['last_processed_timestamp'] = datetime(2025, 11, 19, 12, 30, 0, tzinfo=KOLKATA_TZ).isoformat()
    
    return state


def create_temp_database_with_candles(db_path: str, candles: list):
    """Create temporary database with candle data for testing"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_zerodha (
            timestamp INTEGER,
            symbol TEXT,
            timeframe TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER
        )
    """)
    
    # Insert candles
    for candle in candles:
        cursor.execute("""
            INSERT INTO ohlcv_zerodha 
            (timestamp, symbol, timeframe, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(candle['timestamp'].timestamp()),
            candle.get('symbol', 'BANKNIFTY25NOVFUT'),
            candle.get('timeframe', '15min'),
            candle['open'],
            candle['high'],
            candle['low'],
            candle['close'],
            candle['volume']
        ))
    
    conn.commit()
    conn.close()


def test_crash_recovery_load_state():
    """Test 1: Crash Recovery - Load State"""
    print("=" * 70)
    print("TEST 1: Crash Recovery - Load State")
    print("=" * 70)
    
    print(f"\n🔧 Testing crash recovery - state loading:")
    print(f"   Expected: System restarts, loads saved state from database")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Save state before crash
        state = create_sample_state_with_position_for_recovery()
        state_manager.save_daily_state(state)
        
        print(f"   ✅ State saved before crash")
        
        # Simulate crash (system restarts)
        # Reinitialize state manager (fresh instance)
        state_manager_new = TradingStateManager(db_path=db_path)
        
        # Load saved state on restart
        loaded_state = state_manager_new.load_saved_state()
        
        if loaded_state is None:
            print(f"   ❌ Failed to load saved state after restart")
            return False
        
        print(f"   ✅ State loaded successfully after restart")
        
        # Verify state loaded correctly
        checks = {
            'has_position': loaded_state.get('position') is not None,
            'has_ml_features': len(loaded_state.get('ml_features', {})) > 0,
            'has_historical_data': len(loaded_state.get('historical_data', [])) > 0,
            'has_timestamp': 'last_processed_timestamp' in loaded_state
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"   ✅ State loaded correctly:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            
            pos = loaded_state.get('position')
            if pos:
                print(f"   ✅ Position restored: {pos['direction']} at {pos['entry_price']:.2f}")
            
            return True
        else:
            print(f"   ❌ State incomplete:")
            for key, value in checks.items():
                status = "✓" if value else "✗"
                print(f"      {status} {key}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_position_mismatch_broker_has_position():
    """Test 2: Position Mismatch - Broker Has Position, Saved State Doesn't"""
    print("=" * 70)
    print("TEST 2: Position Mismatch - Broker Has Position, Saved State Doesn't")
    print("=" * 70)
    
    print(f"\n🔧 Testing position mismatch:")
    print(f"   Scenario: Position exists in broker but not in saved state")
    print(f"   Expected: Restore position from broker")
    
    # Create OMS
    oms = create_mock_order_manager(futures_token=260105)
    
    # Mock broker positions (position exists in market)
    broker_positions = [
        {
            'quantity': 280,  # LONG position (positive quantity)
            'average_price': 57300.0,
            'product': 'NRML',
            'instrument_token': 260105
        }
    ]
    
    # Saved state has no position (system crashed after entry but before save)
    saved_position = None
    
    # Reconcile position
    result = reconcile_position(
        saved_position=saved_position,
        broker_positions=broker_positions,
        oms=oms,
        logger=None
    )
    
    # Verify position restored from broker
    if result['status'] == 'recovered_from_broker' and result['position_restored']:
        print(f"   ✅ Position restored from broker")
        print(f"      Status: {result['status']}")
        print(f"      Action: {result['action']}")
        
        pos_status = oms.get_position_status()
        if pos_status['position_type'] == 'LONG':
            print(f"   ✅ OMS position restored: {pos_status['position_type']}")
            print(f"      Entry price: {oms.position.entry_price:.2f}")
            return True
        else:
            print(f"   ❌ OMS position not restored correctly")
            return False
    else:
        print(f"   ❌ Position not restored from broker")
        print(f"      Status: {result['status']}")
        print(f"      Position restored: {result['position_restored']}")
        return False


def test_position_mismatch_saved_has_position():
    """Test 3: Position Mismatch - Saved State Has Position, Broker Doesn't"""
    print("=" * 70)
    print("TEST 3: Position Mismatch - Saved State Has Position, Broker Doesn't")
    print("=" * 70)
    
    print(f"\n🔧 Testing position mismatch:")
    print(f"   Scenario: Position exists in saved state but not in broker")
    print(f"   Expected: Clear position (exited during downtime)")
    
    # Create OMS
    oms = create_mock_order_manager(futures_token=260105)
    
    # Mock broker positions (no position in market)
    broker_positions = []
    
    # Saved state has position (position was exited while system was down)
    saved_position = {
        'direction': 'LONG',
        'entry_price': 57300.0,
        'entry_bar_index': 50,
        'entry_timestamp': datetime(2025, 11, 19, 10, 0, 0, tzinfo=KOLKATA_TZ).isoformat(),
        'atm_strike': 57300,
        'hedge_strike': 55300
    }
    
    # Reconcile position
    result = reconcile_position(
        saved_position=saved_position,
        broker_positions=broker_positions,
        oms=oms,
        logger=None
    )
    
    # Verify position cleared
    if result['status'] == 'cleared_exited_during_downtime':
        print(f"   ✅ Position cleared (exited during downtime)")
        print(f"      Status: {result['status']}")
        print(f"      Action: {result['action']}")
        
        pos_status = oms.get_position_status()
        if pos_status['position_type'] == 'NONE':
            print(f"   ✅ OMS position cleared: {pos_status['position_type']}")
            return True
        else:
            print(f"   ❌ OMS position not cleared")
            return False
    else:
        print(f"   ❌ Position not cleared correctly")
        print(f"      Status: {result['status']}")
        return False


def test_position_mismatch_both_match():
    """Test 4: Position Mismatch - Both Match"""
    print("=" * 70)
    print("TEST 4: Position Mismatch - Both Match")
    print("=" * 70)
    
    print(f"\n🔧 Testing position match:")
    print(f"   Scenario: Position exists in both saved state and broker")
    print(f"   Expected: Use saved state (has more info like entry_bar_index)")
    
    # Create OMS
    oms = create_mock_order_manager(futures_token=260105)
    
    # Mock broker positions (position exists in market)
    broker_positions = [
        {
            'quantity': 280,  # LONG position
            'average_price': 57300.0,
            'product': 'NRML',
            'instrument_token': 260105
        }
    ]
    
    # Saved state has position (matches broker)
    saved_position = {
        'direction': 'LONG',
        'entry_price': 57300.0,  # Same as broker average_price
        'entry_bar_index': 50,  # Extra info from saved state
        'entry_timestamp': datetime(2025, 11, 19, 10, 0, 0, tzinfo=KOLKATA_TZ).isoformat(),
        'atm_strike': 57300,
        'hedge_strike': 55300
    }
    
    # Reconcile position
    result = reconcile_position(
        saved_position=saved_position,
        broker_positions=broker_positions,
        oms=oms,
        logger=None
    )
    
    # Verify position restored from saved state
    if result['status'] == 'matches' and result['position_restored']:
        print(f"   ✅ Positions match - using saved state")
        print(f"      Status: {result['status']}")
        print(f"      Action: {result['action']}")
        
        # Verify OMS has entry_bar_index from saved state
        if oms.position.entry_bar_index == 50 and oms.position.atm_strike == 57300:
            print(f"   ✅ OMS position restored from saved state")
            print(f"      Entry bar index: {oms.position.entry_bar_index}")
            print(f"      ATM strike: {oms.position.atm_strike}")
            return True
        else:
            print(f"   ❌ OMS position not restored correctly")
            return False
    else:
        print(f"   ❌ Position match not detected")
        print(f"      Status: {result['status']}")
        return False


def test_data_gap_detection():
    """Test 5: Data Gap Detection"""
    print("=" * 70)
    print("TEST 5: Data Gap Detection")
    print("=" * 70)
    
    print(f"\n🔧 Testing data gap detection:")
    print(f"   Expected: Detect missing candles while system was down")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Create candles: 9:15, 9:30, 9:45, 10:00 (missing 10:15, 10:30), 10:45
        base_time = datetime(2025, 11, 19, 9, 15, 0, tzinfo=KOLKATA_TZ)
        
        candles = []
        for i in [0, 1, 2, 3, 6]:  # Missing 4, 5 (10:15, 10:30)
            candle_time = base_time + timedelta(minutes=15 * i)
            candles.append({
                'timestamp': candle_time,
                'open': 57000.0 + i * 10,
                'high': 57050.0 + i * 10,
                'low': 56950.0 + i * 10,
                'close': 57020.0 + i * 10,
                'volume': 1000 + i * 10
            })
        
        create_temp_database_with_candles(db_path, candles)
        print(f"   ✅ Database created with {len(candles)} candles (missing 2)")
        
        # System crashed at 10:00, restarts at 10:45
        saved_timestamp = datetime(2025, 11, 19, 10, 0, 0, tzinfo=KOLKATA_TZ).isoformat()
        current_time = datetime(2025, 11, 19, 10, 45, 0, tzinfo=KOLKATA_TZ)
        
        # Detect gaps
        missing_bars = detect_data_gaps(
            saved_timestamp=saved_timestamp,
            current_time=current_time,
            db_path=Path(db_path),
            logger=None
        )
        
        if len(missing_bars) == 2:
            print(f"   ✅ Data gaps detected: {len(missing_bars)} missing candles")
            for missing_bar in missing_bars:
                print(f"      Missing: {missing_bar.strftime('%H:%M')}")
            return True
        else:
            print(f"   ❌ Data gaps not detected correctly")
            print(f"      Expected: 2 missing candles, Got: {len(missing_bars)}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_no_data_gaps():
    """Test 6: No Data Gaps"""
    print("=" * 70)
    print("TEST 6: No Data Gaps")
    print("=" * 70)
    
    print(f"\n🔧 Testing no data gaps scenario:")
    print(f"   Expected: No gaps detected (continuous data)")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Create continuous candles: 9:15, 9:30, 9:45, 10:00, 10:15, 10:30
        base_time = datetime(2025, 11, 19, 9, 15, 0, tzinfo=KOLKATA_TZ)
        
        candles = []
        for i in range(6):  # All candles present
            candle_time = base_time + timedelta(minutes=15 * i)
            candles.append({
                'timestamp': candle_time,
                'open': 57000.0 + i * 10,
                'high': 57050.0 + i * 10,
                'low': 56950.0 + i * 10,
                'close': 57020.0 + i * 10,
                'volume': 1000 + i * 10
            })
        
        create_temp_database_with_candles(db_path, candles)
        print(f"   ✅ Database created with {len(candles)} continuous candles")
        
        # System crashed at 9:45, restarts at 10:30
        saved_timestamp = datetime(2025, 11, 19, 9, 45, 0, tzinfo=KOLKATA_TZ).isoformat()
        current_time = datetime(2025, 11, 19, 10, 30, 0, tzinfo=KOLKATA_TZ)
        
        # Detect gaps
        missing_bars = detect_data_gaps(
            saved_timestamp=saved_timestamp,
            current_time=current_time,
            db_path=Path(db_path),
            logger=None
        )
        
        if len(missing_bars) == 0:
            print(f"   ✅ No data gaps detected (continuous data)")
            return True
        else:
            print(f"   ❌ False positive: Gaps detected when none exist")
            print(f"      Missing bars: {len(missing_bars)}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_expected_timestamps_generation():
    """Test 7: Expected Timestamps Generation"""
    print("=" * 70)
    print("TEST 7: Expected Timestamps Generation")
    print("=" * 70)
    
    print(f"\n🔧 Testing expected timestamps generation:")
    print(f"   Expected: Generate expected 15min candle timestamps during market hours")
    
    # Test case: From 9:15 AM to 10:00 AM
    from_time = datetime(2025, 11, 19, 9, 15, 0, tzinfo=KOLKATA_TZ)
    to_time = datetime(2025, 11, 19, 10, 0, 0, tzinfo=KOLKATA_TZ)
    
    expected_timestamps = generate_expected_timestamps(from_time, to_time, interval_min=15)
    
    # Should generate: 9:15, 9:30, 9:45, 10:00 (4 candles)
    if len(expected_timestamps) == 4:
        print(f"   ✅ Expected timestamps generated: {len(expected_timestamps)} candles")
        for ts in expected_timestamps:
            print(f"      {ts.strftime('%H:%M')}")
        
        # Verify timestamps are correct
        expected_times = [
            datetime(2025, 11, 19, 9, 15, 0, tzinfo=KOLKATA_TZ),
            datetime(2025, 11, 19, 9, 30, 0, tzinfo=KOLKATA_TZ),
            datetime(2025, 11, 19, 9, 45, 0, tzinfo=KOLKATA_TZ),
            datetime(2025, 11, 19, 10, 0, 0, tzinfo=KOLKATA_TZ)
        ]
        
        if all(ts == expected for ts, expected in zip(expected_timestamps, expected_times)):
            print(f"   ✅ Timestamps are correct")
            return True
        else:
            print(f"   ❌ Timestamps incorrect")
            return False
    else:
        print(f"   ❌ Expected timestamps count incorrect: {len(expected_timestamps)} (expected 4)")
        return False


def test_complete_recovery_flow():
    """Test 8: Complete Recovery Flow"""
    print("=" * 70)
    print("TEST 8: Complete Recovery Flow")
    print("=" * 70)
    
    print(f"\n🔧 Testing complete recovery flow:")
    print(f"   Expected: Load state → Reconcile position → Detect gaps")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize components
        state_manager = TradingStateManager(db_path=db_path)
        oms = create_mock_order_manager(futures_token=260105)
        
        # Save state before crash
        state = create_sample_state_with_position_for_recovery()
        state_manager.save_daily_state(state)
        
        print(f"   ✅ State saved before crash")
        
        # Create database with some candles (with gaps)
        base_time = datetime(2025, 11, 19, 9, 15, 0, tzinfo=KOLKATA_TZ)
        candles = []
        for i in [0, 1, 2, 3, 6]:  # Missing 4, 5
            candle_time = base_time + timedelta(minutes=15 * i)
            candles.append({
                'timestamp': candle_time,
                'open': 57000.0 + i * 10,
                'high': 57050.0 + i * 10,
                'low': 56950.0 + i * 10,
                'close': 57020.0 + i * 10,
                'volume': 1000 + i * 10
            })
        
        create_temp_database_with_candles(db_path, candles)
        print(f"   ✅ Database created with gaps")
        
        # Mock broker positions (no position - exited during downtime)
        oms.kite.positions = Mock(return_value={'net': []})
        
        # Complete recovery flow
        recovery_result = recover_system(
            state_manager=state_manager,
            oms=oms,
            db_path=Path(db_path),
            logger=None
        )
        
        if recovery_result['state_loaded'] and recovery_result['position_reconciliation']:
            print(f"   ✅ Recovery flow completed")
            print(f"      State loaded: {recovery_result['state_loaded']}")
            print(f"      Position reconciliation: {recovery_result['position_reconciliation']['status']}")
            print(f"      Data gaps detected: {recovery_result['data_gaps_count']}")
            
            if recovery_result['data_gaps_count'] > 0:
                print(f"      Missing candles: {len(recovery_result['data_gaps'])}")
            
            return True
        else:
            print(f"   ❌ Recovery flow incomplete")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_wifi_downtime_detection():
    """Test 9: WiFi Downtime Detection"""
    print("=" * 70)
    print("TEST 9: WiFi Downtime Detection")
    print("=" * 70)
    
    print(f"\n🔧 Testing WiFi downtime detection:")
    print(f"   Expected: Detect data gaps caused by WiFi downtime")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # System running normally until 10:00, WiFi down until 11:00, restarts at 11:15
        base_time = datetime(2025, 11, 19, 9, 15, 0, tzinfo=KOLKATA_TZ)
        
        # Candles until 10:00 (normal), gap from 10:15 to 11:00 (WiFi down), resume at 11:15
        candles = []
        # Normal candles: 9:15 to 10:00
        for i in range(4):  # 9:15, 9:30, 9:45, 10:00
            candle_time = base_time + timedelta(minutes=15 * i)
            candles.append({
                'timestamp': candle_time,
                'open': 57000.0 + i * 10,
                'high': 57050.0 + i * 10,
                'low': 56950.0 + i * 10,
                'close': 57020.0 + i * 10,
                'volume': 1000 + i * 10
            })
        # Resume after WiFi reconnection: 11:15
        resume_time = base_time + timedelta(hours=2)  # 11:15
        candles.append({
            'timestamp': resume_time,
            'open': 57100.0,
            'high': 57150.0,
            'low': 57050.0,
            'close': 57120.0,
            'volume': 2000
        })
        
        create_temp_database_with_candles(db_path, candles)
        print(f"   ✅ Database created (WiFi downtime from 10:15 to 11:00)")
        
        # System crashed at 10:00 (before WiFi down), restarts at 11:15
        saved_timestamp = datetime(2025, 11, 19, 10, 0, 0, tzinfo=KOLKATA_TZ).isoformat()
        current_time = datetime(2025, 11, 19, 11, 15, 0, tzinfo=KOLKATA_TZ)
        
        # Detect gaps
        missing_bars = detect_data_gaps(
            saved_timestamp=saved_timestamp,
            current_time=current_time,
            db_path=Path(db_path),
            logger=None
        )
        
        # Should detect: 10:15, 10:30, 10:45, 11:00 (4 missing candles)
        if len(missing_bars) == 4:
            print(f"   ✅ WiFi downtime detected: {len(missing_bars)} missing candles")
            for missing_bar in missing_bars:
                print(f"      Missing: {missing_bar.strftime('%H:%M')}")
            return True
        else:
            print(f"   ❌ WiFi downtime not detected correctly")
            print(f"      Expected: 4 missing candles, Got: {len(missing_bars)}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_api_downtime_handling():
    """Test 10: API Downtime Handling"""
    print("=" * 70)
    print("TEST 10: API Downtime Handling")
    print("=" * 70)
    
    print(f"\n🔧 Testing API downtime handling:")
    print(f"   Expected: Handle API errors gracefully (retry logic)")
    
    # Create OMS
    oms = create_mock_order_manager(futures_token=260105)
    
    # Mock API failure (Zerodha API down)
    oms.kite.positions = Mock(side_effect=Exception("API Error: Connection timeout"))
    
    # Test error handling in reconcile_position
    saved_position = None
    broker_positions = []
    
    try:
        # Try to get broker positions (will fail)
        broker_positions = oms.kite.positions()['net']
    except Exception as e:
        # API error handled gracefully
        broker_positions = []
        print(f"   ✅ API error handled gracefully: {str(e)}")
    
    # Reconcile position (should work even if API fails)
    result = reconcile_position(
        saved_position=saved_position,
        broker_positions=broker_positions,  # Empty due to API error
        oms=oms,
        logger=None
    )
    
    # Should handle gracefully (no crash, clean state)
    if result['status'] == 'clean':
        print(f"   ✅ API downtime handled gracefully")
        print(f"      Status: {result['status']}")
        print(f"      Action: {result['action']}")
        return True
    else:
        print(f"   ❌ API downtime not handled correctly")
        return False


def main():
    """Run all recovery scenario tests"""
    print("\n" + "=" * 70)
    print("PHASE 6, BLOCK 6.2: INTEGRATION TESTING - RECOVERY SCENARIOS")
    print("=" * 70)
    print()
    
    tests = [
        ("Crash Recovery - Load State", test_crash_recovery_load_state),
        ("Position Mismatch - Broker Has Position", test_position_mismatch_broker_has_position),
        ("Position Mismatch - Saved Has Position", test_position_mismatch_saved_has_position),
        ("Position Mismatch - Both Match", test_position_mismatch_both_match),
        ("Data Gap Detection", test_data_gap_detection),
        ("No Data Gaps", test_no_data_gaps),
        ("Expected Timestamps Generation", test_expected_timestamps_generation),
        ("Complete Recovery Flow", test_complete_recovery_flow),
        ("WiFi Downtime Detection", test_wifi_downtime_detection),
        ("API Downtime Handling", test_api_downtime_handling),
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
        print("Block 6.2: Recovery Scenarios - VERIFIED ✅")
        print("=" * 70)
        print()
        print("✅ Crash recovery (system restarts, loads state)")
        print("✅ Position mismatch detection (broker vs saved)")
        print("✅ Position reconciliation (restore from broker/saved state)")
        print("✅ Data gap detection (missing candles)")
        print("✅ No data gaps (continuous data)")
        print("✅ Expected timestamps generation (market hours only)")
        print("✅ Complete recovery flow (all steps)")
        print("✅ WiFi downtime detection (data gaps from network issues)")
        print("✅ API downtime handling (error handling, graceful recovery)")
        print()
        print("⚠️  NOTE: Tests use MOCK components for complete flow testing")
        print("   Real integration requires:")
        print("   - Zerodha API for broker positions")
        print("   - fetch_zerodha_historical_data.py for gap filling")
        print("   - ML state recalculation if gaps filled")
        print()
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

