"""
PHASE 6, BLOCK 6.1: INTEGRATION TESTING - GAP DETECTION

Tests the complete gap detection integration:
- Gap calculation (futures_today_open - futures_previous_close)
- Gap detection for LONG (gap down adverse, gap up favorable)
- Gap detection for SHORT (gap up adverse, gap down favorable)
- Immediate exit on adverse gap (LONG + gap down, SHORT + gap up)
- Normal trading on favorable gap (LONG + gap up, SHORT + gap down)
- Gap threshold (300 points default)
- Futures previous close loading (from saved state)

Real Trading Flow:
1. At 9:15 AM: Load futures_previous_close from saved state
2. On first tick: Calculate gap (futures_today_open - futures_previous_close)
3. If position exists: Check if gap is adverse
4. If adverse gap > threshold: Exit immediately (stop loss)
5. If favorable gap: Continue normally (exit on 4-bar or volume)

Note: Tests use MOCK components for complete flow testing
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock
import pytz

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.protection.gap_detector import (
    GapDetector, GapResult, DEFAULT_GAP_THRESHOLD
)
from src.trading_system.data.zerodha_candle_aggregator import RunningCandle
from src.trading_system.oms.order_manager import PositionType
from src.trading_system.data.trading_state_manager import TradingStateManager
from scripts.test_websocket_price_feed import create_mock_order_manager

KOLKATA_TZ = pytz.timezone('Asia/Kolkata')


def create_running_candle(open_price: float, high: float = None, low: float = None, 
                          close: float = None, timestamp: datetime = None) -> RunningCandle:
    """Create a mock running candle for testing"""
    if timestamp is None:
        timestamp = datetime(2025, 11, 20, 9, 15, 0, tzinfo=KOLKATA_TZ)
    if high is None:
        high = open_price + 50
    if low is None:
        low = open_price - 50
    if close is None:
        close = open_price + 20
    
    return RunningCandle(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
        tick_count=1
    )


def test_gap_calculation():
    """Test 1: Gap Calculation"""
    print("=" * 70)
    print("TEST 1: Gap Calculation")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap calculation:")
    print(f"   Expected: Gap = futures_today_open - futures_previous_close")
    
    # Initialize gap detector
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    
    # Test case 1: Gap up
    futures_previous_close = 57000.0
    futures_today_open = 57200.0
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.NONE  # No position, but gap is still calculated
    )
    
    expected_gap_points = 200.0
    expected_gap_percent = (200.0 / 57000.0) * 100
    
    if abs(result.gap_points - expected_gap_points) < 0.01:
        print(f"   ✅ Gap calculation correct (gap up): {result.gap_points:.2f} points ({result.gap_percent:.2f}%)")
    else:
        print(f"   ❌ Gap calculation incorrect: {result.gap_points:.2f} (expected {expected_gap_points:.2f})")
        return False
    
    # Test case 2: Gap down
    futures_today_open = 56800.0
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.NONE  # No position, but gap is still calculated
    )
    
    expected_gap_points = -200.0
    expected_gap_percent = (-200.0 / 57000.0) * 100
    
    if abs(result.gap_points - expected_gap_points) < 0.01:
        print(f"   ✅ Gap calculation correct (gap down): {result.gap_points:.2f} points ({result.gap_percent:.2f}%)")
        return True
    else:
        print(f"   ❌ Gap calculation incorrect: {result.gap_points:.2f} (expected {expected_gap_points:.2f})")
        return False


def test_gap_detection_long_adverse():
    """Test 2: Gap Detection for LONG - Adverse Gap Down"""
    print("=" * 70)
    print("TEST 2: Gap Detection for LONG - Adverse Gap Down")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap detection for LONG position:")
    print(f"   Scenario: LONG position + Gap DOWN (adverse)")
    print(f"   Expected: Exit immediately if gap > threshold (300 points)")
    
    # Initialize gap detector
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    
    # Test case 1: Large gap down (exceeds threshold) - should exit
    futures_previous_close = 57000.0
    futures_today_open = 56600.0  # Gap down 400 points (exceeds 300 threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.LONG
    )
    
    if result.should_exit and result.is_adverse and result.exit_price == futures_today_open:
        print(f"   ✅ Adverse gap detected: {result.gap_points:.2f} points down")
        print(f"      Should exit: {result.should_exit}")
        print(f"      Exit price: {result.exit_price:.2f}")
    else:
        print(f"   ❌ Adverse gap not detected correctly")
        print(f"      Gap points: {result.gap_points:.2f}")
        print(f"      Should exit: {result.should_exit} (expected True)")
        print(f"      Is adverse: {result.is_adverse} (expected True)")
        return False
    
    # Test case 2: Small gap down (below threshold) - should continue
    futures_today_open = 56800.0  # Gap down 200 points (below 300 threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.LONG
    )
    
    if not result.should_exit:
        print(f"   ✅ Small gap down (below threshold): {result.gap_points:.2f} points")
        print(f"      Should exit: {result.should_exit} (correct - continue normally)")
        return True
    else:
        print(f"   ❌ Small gap down incorrectly triggers exit")
        print(f"      Gap points: {result.gap_points:.2f}")
        print(f"      Should exit: {result.should_exit} (expected False)")
        return False


def test_gap_detection_long_favorable():
    """Test 3: Gap Detection for LONG - Favorable Gap Up"""
    print("=" * 70)
    print("TEST 3: Gap Detection for LONG - Favorable Gap Up")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap detection for LONG position:")
    print(f"   Scenario: LONG position + Gap UP (favorable)")
    print(f"   Expected: Continue normally (exit on 4-bar or volume)")
    
    # Initialize gap detector
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    
    # Test case: Large gap up (favorable) - should continue
    futures_previous_close = 57000.0
    futures_today_open = 57500.0  # Gap up 500 points (favorable for LONG)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.LONG
    )
    
    if not result.should_exit and not result.is_adverse:
        print(f"   ✅ Favorable gap up detected: {result.gap_points:.2f} points up")
        print(f"      Should exit: {result.should_exit} (correct - continue normally)")
        print(f"      Is adverse: {result.is_adverse} (correct - not adverse)")
        return True
    else:
        print(f"   ❌ Favorable gap incorrectly triggers exit")
        print(f"      Gap points: {result.gap_points:.2f}")
        print(f"      Should exit: {result.should_exit} (expected False)")
        print(f"      Is adverse: {result.is_adverse} (expected False)")
        return False


def test_gap_detection_short_adverse():
    """Test 4: Gap Detection for SHORT - Adverse Gap Up"""
    print("=" * 70)
    print("TEST 4: Gap Detection for SHORT - Adverse Gap Up")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap detection for SHORT position:")
    print(f"   Scenario: SHORT position + Gap UP (adverse)")
    print(f"   Expected: Exit immediately if gap > threshold (300 points)")
    
    # Initialize gap detector
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    
    # Test case 1: Large gap up (exceeds threshold) - should exit
    futures_previous_close = 57000.0
    futures_today_open = 57400.0  # Gap up 400 points (exceeds 300 threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.SHORT
    )
    
    if result.should_exit and result.is_adverse and result.exit_price == futures_today_open:
        print(f"   ✅ Adverse gap detected: {result.gap_points:.2f} points up")
        print(f"      Should exit: {result.should_exit}")
        print(f"      Exit price: {result.exit_price:.2f}")
    else:
        print(f"   ❌ Adverse gap not detected correctly")
        print(f"      Gap points: {result.gap_points:.2f}")
        print(f"      Should exit: {result.should_exit} (expected True)")
        print(f"      Is adverse: {result.is_adverse} (expected True)")
        return False
    
    # Test case 2: Small gap up (below threshold) - should continue
    futures_today_open = 57200.0  # Gap up 200 points (below 300 threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.SHORT
    )
    
    if not result.should_exit:
        print(f"   ✅ Small gap up (below threshold): {result.gap_points:.2f} points")
        print(f"      Should exit: {result.should_exit} (correct - continue normally)")
        return True
    else:
        print(f"   ❌ Small gap up incorrectly triggers exit")
        print(f"      Gap points: {result.gap_points:.2f}")
        print(f"      Should exit: {result.should_exit} (expected False)")
        return False


def test_gap_detection_short_favorable():
    """Test 5: Gap Detection for SHORT - Favorable Gap Down"""
    print("=" * 70)
    print("TEST 5: Gap Detection for SHORT - Favorable Gap Down")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap detection for SHORT position:")
    print(f"   Scenario: SHORT position + Gap DOWN (favorable)")
    print(f"   Expected: Continue normally (exit on 4-bar or volume)")
    
    # Initialize gap detector
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    
    # Test case: Large gap down (favorable) - should continue
    futures_previous_close = 57000.0
    futures_today_open = 56500.0  # Gap down 500 points (favorable for SHORT)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.SHORT
    )
    
    if not result.should_exit and not result.is_adverse:
        print(f"   ✅ Favorable gap down detected: {result.gap_points:.2f} points down")
        print(f"      Should exit: {result.should_exit} (correct - continue normally)")
        print(f"      Is adverse: {result.is_adverse} (correct - not adverse)")
        return True
    else:
        print(f"   ❌ Favorable gap incorrectly triggers exit")
        print(f"      Gap points: {result.gap_points:.2f}")
        print(f"      Should exit: {result.should_exit} (expected False)")
        print(f"      Is adverse: {result.is_adverse} (expected False)")
        return False


def test_gap_threshold():
    """Test 6: Gap Threshold"""
    print("=" * 70)
    print("TEST 6: Gap Threshold")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap threshold (300 points default):")
    print(f"   Expected: Exit only if gap exceeds threshold")
    
    # Initialize gap detector with custom threshold
    custom_threshold = 500.0
    gap_detector = GapDetector(gap_threshold=custom_threshold)
    
    futures_previous_close = 57000.0
    
    # Test case 1: Gap exactly at threshold (should not exit - threshold is "exceeds")
    futures_today_open = 56500.0  # Gap down 500 points (exactly at threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.LONG
    )
    
    # Gap exactly at threshold should NOT exit (exceeds means >, not >=)
    if result.should_exit:
        print(f"   ❌ Gap at threshold incorrectly triggers exit")
        print(f"      Gap points: {result.gap_points:.2f}, Threshold: {custom_threshold}")
        return False
    
    print(f"   ✅ Gap at threshold ({custom_threshold} points): No exit (correct)")
    
    # Test case 2: Gap exceeds threshold (should exit)
    futures_today_open = 56499.0  # Gap down 501 points (exceeds 500 threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.LONG
    )
    
    if result.should_exit:
        print(f"   ✅ Gap exceeds threshold ({abs(result.gap_points):.2f} > {custom_threshold}): Exit triggered")
        return True
    else:
        print(f"   ❌ Gap exceeding threshold does not trigger exit")
        print(f"      Gap points: {result.gap_points:.2f}, Threshold: {custom_threshold}")
        return False


def test_futures_previous_close_loading():
    """Test 7: Futures Previous Close Loading from Saved State"""
    print("=" * 70)
    print("TEST 7: Futures Previous Close Loading from Saved State")
    print("=" * 70)
    
    print(f"\n🔧 Testing futures_previous_close loading from saved state:")
    print(f"   Expected: Load futures_previous_close from saved state at 9:15 AM")
    
    import tempfile
    import os
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Initialize state manager
        state_manager = TradingStateManager(db_path=db_path)
        
        # Save state with futures_previous_close
        futures_previous_close = 57000.0
        state = {
            'futures_previous_close': futures_previous_close,
            'last_long_exit_bar': -1,
            'last_short_exit_bar': -1,
            'position': None,
            'ml_features': {},
            'ml_indicators': {},
            'ml_predictions': [],
            'ml_signals': [],
            'historical_data': [],
            'last_processed_timestamp': datetime(2025, 11, 19, 15, 30, 0, tzinfo=KOLKATA_TZ).isoformat(),
            'data_source': 'zerodha'
        }
        
        state_manager.save_daily_state(state)
        print(f"   ✅ State saved with futures_previous_close: {futures_previous_close:.2f}")
        
        # Load state at 9:15 AM next day
        loaded_state = state_manager.load_saved_state()
        
        if loaded_state is None:
            print(f"   ❌ Failed to load saved state")
            return False
        
        loaded_futures_previous_close = loaded_state.get('futures_previous_close')
        
        if loaded_futures_previous_close == futures_previous_close:
            print(f"   ✅ Futures previous close loaded correctly: {loaded_futures_previous_close:.2f}")
            
            # Test gap calculation with loaded value
            gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
            futures_today_open = 56600.0  # Gap down 400 points
            running_candle = create_running_candle(open_price=futures_today_open)
            
            result = gap_detector.check_gap(
                running_candle=running_candle,
                futures_previous_close=loaded_futures_previous_close,
                position_type=PositionType.LONG
            )
            
            if result.should_exit and result.gap_points == -400.0:
                print(f"   ✅ Gap calculation using loaded futures_previous_close: {result.gap_points:.2f} points")
                return True
            else:
                print(f"   ❌ Gap calculation incorrect with loaded value")
                return False
        else:
            print(f"   ❌ Futures previous close not loaded correctly")
            print(f"      Expected: {futures_previous_close:.2f}, Got: {loaded_futures_previous_close}")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_gap_exit_integration():
    """Test 8: Gap Exit Integration with OMS"""
    print("=" * 70)
    print("TEST 8: Gap Exit Integration with OMS")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap exit integration with OMS:")
    print(f"   Expected: Adverse gap → GapDetector → OrderManager.exit_position()")
    
    # Initialize components
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    oms = create_mock_order_manager(futures_token=260105)
    
    # Enter LONG position
    oms.position.position_type = PositionType.LONG
    oms.position.entry_price = 57100.0
    oms.position.entry_time = datetime.now()
    
    print(f"   ✅ Position entered: {oms.position.position_type.value} at {oms.position.entry_price:.2f}")
    
    # Simulate adverse gap down (exceeds threshold)
    futures_previous_close = 57000.0
    futures_today_open = 56600.0  # Gap down 400 points (exceeds 300 threshold)
    running_candle = create_running_candle(open_price=futures_today_open)
    
    # Check gap
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=oms.position.position_type
    )
    
    if result.should_exit:
        # Exit position (exit_position() doesn't accept exit_price parameter)
        oms.exit_position()
        
        # Verify position cleared
        pos_status = oms.get_position_status()
        
        if pos_status['position_type'] == 'NONE':
            print(f"   ✅ Gap exit executed: Position cleared")
            print(f"      Gap: {result.gap_points:.2f} points down")
            print(f"      Exit price: {result.exit_price:.2f}")
            return True
        else:
            print(f"   ❌ Position not cleared after gap exit")
            return False
    else:
        print(f"   ❌ Gap exit not triggered (should be True)")
        return False


def test_no_position_gap_check():
    """Test 9: No Position Gap Check"""
    print("=" * 70)
    print("TEST 9: No Position Gap Check")
    print("=" * 70)
    
    print(f"\n🔧 Testing gap check when no position exists:")
    print(f"   Expected: No exit (no position to exit)")
    
    # Initialize gap detector
    gap_detector = GapDetector(gap_threshold=DEFAULT_GAP_THRESHOLD)
    
    futures_previous_close = 57000.0
    futures_today_open = 56600.0  # Large gap down
    running_candle = create_running_candle(open_price=futures_today_open)
    
    # Check gap with no position
    result = gap_detector.check_gap(
        running_candle=running_candle,
        futures_previous_close=futures_previous_close,
        position_type=PositionType.NONE
    )
    
    expected_gap_points = -400.0  # Gap down 400 points
    
    if not result.should_exit and abs(result.gap_points - expected_gap_points) < 0.01:
        print(f"   ✅ No position: Gap calculated but no exit (correct)")
        print(f"      Should exit: {result.should_exit} (expected False)")
        print(f"      Gap points: {result.gap_points:.2f} (calculated correctly)")
        return True
    else:
        print(f"   ❌ Gap calculation incorrect when no position")
        print(f"      Should exit: {result.should_exit} (expected False)")
        print(f"      Gap points: {result.gap_points:.2f} (expected {expected_gap_points:.2f})")
        return False


def main():
    """Run all gap detection tests"""
    print("\n" + "=" * 70)
    print("PHASE 6, BLOCK 6.1: INTEGRATION TESTING - GAP DETECTION")
    print("=" * 70)
    print()
    
    tests = [
        ("Gap Calculation", test_gap_calculation),
        ("Gap Detection for LONG - Adverse Gap Down", test_gap_detection_long_adverse),
        ("Gap Detection for LONG - Favorable Gap Up", test_gap_detection_long_favorable),
        ("Gap Detection for SHORT - Adverse Gap Up", test_gap_detection_short_adverse),
        ("Gap Detection for SHORT - Favorable Gap Down", test_gap_detection_short_favorable),
        ("Gap Threshold", test_gap_threshold),
        ("Futures Previous Close Loading", test_futures_previous_close_loading),
        ("Gap Exit Integration with OMS", test_gap_exit_integration),
        ("No Position Gap Check", test_no_position_gap_check),
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
        print("Block 6.1: Gap Detection - VERIFIED ✅")
        print("=" * 70)
        print()
        print("✅ Gap calculation (futures_today_open - futures_previous_close)")
        print("✅ Gap detection for LONG (gap down adverse, gap up favorable)")
        print("✅ Gap detection for SHORT (gap up adverse, gap down favorable)")
        print("✅ Immediate exit on adverse gap (LONG + gap down, SHORT + gap up)")
        print("✅ Normal trading on favorable gap (LONG + gap up, SHORT + gap down)")
        print("✅ Gap threshold (300 points default)")
        print("✅ Futures previous close loading (from saved state)")
        print("✅ Gap exit integration with OMS")
        print("✅ No position gap check (skipped)")
        print()
        print("⚠️  NOTE: Tests use MOCK components for complete flow testing")
        print("   Real integration requires:")
        print("   - Futures previous close from saved state at 9:15 AM")
        print("   - Running candle open price from first tick")
        print("   - Position type from OMS")
        print()
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

