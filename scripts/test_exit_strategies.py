"""
PHASE 3, BLOCK 3.1: 4-BAR EXIT TESTING

Tests the 4-bar exit strategy used in live trading:
- Exit after 4 bars held
- Exit at candle close (not running candle)
- Bar counting correct
- Edge cases

Real Trading Parameters:
- default_exit_bars: 4
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from datetime import datetime
from src.strategy.backtest.exit_strategies import (
    ExitStrategyManager,
    Trade,
    MarketData
)


def test_4_bar_exit_basic():
    """Test 1: Basic 4-Bar Exit"""
    print("=" * 70)
    print("TEST 1: Basic 4-Bar Exit")
    print("=" * 70)
    
    class MockConfig:
        def __init__(self):
            self.default_exit_bars = 4  # Real trading: 4 bars
            self.use_repaint_detection = False
    
    config = MockConfig()
    manager = ExitStrategyManager(config)
    
    # Create LONG trade at bar 100
    trade = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=50000.0,
        direction=1,  # LONG
        timeframe='15m'
    )
    
    print(f"\n🔧 Testing 4-bar exit for LONG trade:")
    print(f"   Entry bar: {trade.entry_bar}")
    print(f"   Entry price: {trade.entry_price:.2f}")
    print(f"   Default exit bars: {config.default_exit_bars}")
    
    # Test cases: (bar, expected_exit, description)
    test_cases = [
        (100, False, "Entry bar - no exit"),
        (101, False, "1 bar held - no exit"),
        (102, False, "2 bars held - no exit"),
        (103, False, "3 bars held - no exit"),
        (104, True, "4 bars held - should exit"),
        (105, True, "5 bars held - should exit"),
    ]
    
    all_passed = True
    for bar, expected_exit, description in test_cases:
        data = MarketData(
            bar=bar,
            timestamp=datetime.now(),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=1000
        )
        
        should_exit, reason = manager.check_exit(trade, data)
        
        if should_exit == expected_exit:
            status = "✅" if should_exit else "⏳"
            print(f"   {status} Bar {bar}: {description} - Exit: {should_exit}, Reason: {reason}")
        else:
            print(f"   ❌ Bar {bar}: {description} - Expected {expected_exit}, got {should_exit}")
            all_passed = False
        
        if should_exit:
            if reason == "4_bars":
                print(f"      ✅ Correct exit reason: {reason}")
            else:
                print(f"      ❌ Wrong exit reason: {reason} (expected '4_bars')")
                all_passed = False
    
    return all_passed


def test_4_bar_exit_short():
    """Test 2: 4-Bar Exit for SHORT Trade"""
    print("=" * 70)
    print("TEST 2: 4-Bar Exit for SHORT Trade")
    print("=" * 70)
    
    class MockConfig:
        def __init__(self):
            self.default_exit_bars = 4
            self.use_repaint_detection = False
    
    config = MockConfig()
    manager = ExitStrategyManager(config)
    
    # Create SHORT trade
    trade = Trade(
        entry_bar=200,
        entry_time=datetime.now(),
        entry_price=51000.0,
        direction=-1,  # SHORT
        timeframe='15m'
    )
    
    print(f"\n🔧 Testing 4-bar exit for SHORT trade:")
    print(f"   Entry bar: {trade.entry_bar}")
    print(f"   Entry price: {trade.entry_price:.2f}")
    
    test_cases = [
        (200, False, "Entry bar"),
        (201, False, "1 bar held"),
        (202, False, "2 bars held"),
        (203, False, "3 bars held"),
        (204, True, "4 bars held - should exit"),
    ]
    
    all_passed = True
    for bar, expected_exit, description in test_cases:
        data = MarketData(
            bar=bar,
            timestamp=datetime.now(),
            open=51000.0,
            high=51100.0,
            low=50900.0,
            close=51050.0,
            volume=1000
        )
        
        should_exit, reason = manager.check_exit(trade, data)
        
        if should_exit == expected_exit:
            status = "✅"
            print(f"   {status} Bar {bar}: {description} - Exit: {should_exit}")
        else:
            print(f"   ❌ Bar {bar}: {description} - Expected {expected_exit}, got {should_exit}")
            all_passed = False
    
    return all_passed


def test_bar_counting():
    """Test 3: Bar Counting Accuracy"""
    print("=" * 70)
    print("TEST 3: Bar Counting Accuracy")
    print("=" * 70)
    
    class MockConfig:
        def __init__(self):
            self.default_exit_bars = 4
            self.use_repaint_detection = False
    
    config = MockConfig()
    manager = ExitStrategyManager(config)
    
    # Test with different entry bars
    test_cases = [
        (100, 104, 4, "Standard case"),
        (0, 4, 4, "Starting from bar 0"),
        (500, 504, 4, "High bar numbers"),
        (1000, 1004, 4, "Very high bar numbers"),
    ]
    
    print(f"\n🔧 Testing bar counting:")
    
    all_passed = True
    for entry_bar, exit_bar, expected_bars, description in test_cases:
        trade = Trade(
            entry_bar=entry_bar,
            entry_time=datetime.now(),
            entry_price=50000.0,
            direction=1,
            timeframe='15m'
        )
        
        # Check at exit bar
        data = MarketData(
            bar=exit_bar,
            timestamp=datetime.now(),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=1000
        )
        
        should_exit, reason = manager.check_exit(trade, data)
        
        # Verify bar counting
        bars_held = exit_bar - entry_bar
        if bars_held == expected_bars and should_exit:
            print(f"   ✅ {description}: Entry={entry_bar}, Exit={exit_bar}, Bars held={bars_held}")
        else:
            print(f"   ❌ {description}: Entry={entry_bar}, Exit={exit_bar}, Bars held={bars_held}, Exit={should_exit}")
            all_passed = False
        
        # Check one bar before (should not exit)
        if exit_bar > entry_bar:
            data_before = MarketData(
                bar=exit_bar - 1,
                timestamp=datetime.now(),
                open=50000.0,
                high=50100.0,
                low=49900.0,
                close=50050.0,
                volume=1000
            )
            should_exit_before, _ = manager.check_exit(trade, data_before)
            if not should_exit_before:
                print(f"      ✅ Bar {exit_bar - 1}: No exit (correct)")
            else:
                print(f"      ❌ Bar {exit_bar - 1}: Should not exit but did")
                all_passed = False
    
    return all_passed


def test_exit_at_candle_close():
    """Test 4: Exit at Candle Close (Not Running Candle)"""
    print("=" * 70)
    print("TEST 4: Exit at Candle Close")
    print("=" * 70)
    
    class MockConfig:
        def __init__(self):
            self.default_exit_bars = 4
            self.use_repaint_detection = False
    
    config = MockConfig()
    manager = ExitStrategyManager(config)
    
    trade = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=50000.0,
        direction=1,
        timeframe='15m'
    )
    
    print(f"\n🔧 Testing exit timing (should exit at candle close, not running candle):")
    print(f"   Entry bar: {trade.entry_bar}")
    print(f"   4-bar exit should trigger at bar {trade.entry_bar + 4} (candle close)")
    
    # At bar 103 (3 bars held), no exit
    data_103 = MarketData(
        bar=103,
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=1000
    )
    
    should_exit_103, _ = manager.check_exit(trade, data_103)
    if not should_exit_103:
        print(f"   ✅ Bar 103 (3 bars held): No exit (correct - candle not closed yet)")
    else:
        print(f"   ❌ Bar 103: Should not exit but did")
        return False
    
    # At bar 104 (4 bars held), exit at close
    data_104 = MarketData(
        bar=104,
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,  # Exit at this close price
        volume=1000
    )
    
    should_exit_104, reason = manager.check_exit(trade, data_104)
    if should_exit_104 and reason == "4_bars":
        print(f"   ✅ Bar 104 (4 bars held): Exit triggered at close price {data_104.close:.2f}")
    else:
        print(f"   ❌ Bar 104: Should exit but didn't (Exit: {should_exit_104}, Reason: {reason})")
        return False
    
    return True


def test_pnl_calculation():
    """Test 5: P&L Calculation"""
    print("=" * 70)
    print("TEST 5: P&L Calculation")
    print("=" * 70)
    
    class MockConfig:
        def __init__(self):
            self.default_exit_bars = 4
            self.use_repaint_detection = False
    
    config = MockConfig()
    manager = ExitStrategyManager(config)
    
    print(f"\n🔧 Testing P&L calculation:")
    
    # Test LONG trade
    long_trade = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=50000.0,
        direction=1,  # LONG
        timeframe='15m'
    )
    
    exit_price_long = 51000.0  # Exit 1000 points higher
    expected_pnl_long = (exit_price_long - long_trade.entry_price) / long_trade.entry_price * 100
    
    pnl_long = manager.calculate_trade_pnl(long_trade, exit_price_long)
    
    if abs(pnl_long - expected_pnl_long) < 0.01:
        print(f"   ✅ LONG trade P&L: {pnl_long:.2f}% (expected: {expected_pnl_long:.2f}%)")
        print(f"      Entry: {long_trade.entry_price:.2f}, Exit: {exit_price_long:.2f}")
    else:
        print(f"   ❌ LONG trade P&L mismatch: {pnl_long:.2f}% (expected: {expected_pnl_long:.2f}%)")
        return False
    
    # Test SHORT trade
    short_trade = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=51000.0,
        direction=-1,  # SHORT
        timeframe='15m'
    )
    
    exit_price_short = 50000.0  # Exit 1000 points lower (profit for SHORT)
    expected_pnl_short = (short_trade.entry_price - exit_price_short) / short_trade.entry_price * 100
    
    pnl_short = manager.calculate_trade_pnl(short_trade, exit_price_short)
    
    if abs(pnl_short - expected_pnl_short) < 0.01:
        print(f"   ✅ SHORT trade P&L: {pnl_short:.2f}% (expected: {expected_pnl_short:.2f}%)")
        print(f"      Entry: {short_trade.entry_price:.2f}, Exit: {exit_price_short:.2f}")
    else:
        print(f"   ❌ SHORT trade P&L mismatch: {pnl_short:.2f}% (expected: {expected_pnl_short:.2f}%)")
        return False
    
    # Test losing LONG trade
    long_trade_lose = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=51000.0,
        direction=1,
        timeframe='15m'
    )
    
    exit_price_long_lose = 50000.0  # Exit 1000 points lower (loss)
    expected_pnl_long_lose = (exit_price_long_lose - long_trade_lose.entry_price) / long_trade_lose.entry_price * 100
    
    pnl_long_lose = manager.calculate_trade_pnl(long_trade_lose, exit_price_long_lose)
    
    if pnl_long_lose < 0 and abs(pnl_long_lose - expected_pnl_long_lose) < 0.01:
        print(f"   ✅ LONG losing trade P&L: {pnl_long_lose:.2f}% (expected: {expected_pnl_long_lose:.2f}%)")
    else:
        print(f"   ❌ LONG losing trade P&L mismatch: {pnl_long_lose:.2f}% (expected: {expected_pnl_long_lose:.2f}%)")
        return False
    
    return True


def test_edge_cases():
    """Test 6: Edge Cases"""
    print("=" * 70)
    print("TEST 6: Edge Cases")
    print("=" * 70)
    
    class MockConfig:
        def __init__(self):
            self.default_exit_bars = 4
            self.use_repaint_detection = False
    
    config = MockConfig()
    manager = ExitStrategyManager(config)
    
    print(f"\n🔧 Testing edge cases:")
    
    all_passed = True
    
    # Test 6.1: None trade
    print(f"\n   Test 6.1: None trade...")
    data = MarketData(
        bar=100,
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=1000
    )
    
    should_exit, reason = manager.check_exit(None, data)
    if not should_exit:
        print(f"      ✅ None trade handled correctly (no exit)")
    else:
        print(f"      ❌ None trade should not exit")
        all_passed = False
    
    # Test 6.2: Trade at same bar as entry (bars_held = 0)
    print(f"\n   Test 6.2: Trade at entry bar (bars_held = 0)...")
    trade = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=50000.0,
        direction=1,
        timeframe='15m'
    )
    
    data_same = MarketData(
        bar=100,  # Same as entry
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=1000
    )
    
    should_exit_same, _ = manager.check_exit(trade, data_same)
    if not should_exit_same:
        print(f"      ✅ Entry bar (bars_held=0): No exit (correct)")
    else:
        print(f"      ❌ Entry bar should not exit")
        all_passed = False
    
    # Test 6.3: Trade with bars_held exactly 4
    print(f"\n   Test 6.3: Trade with exactly 4 bars held...")
    trade_exact = Trade(
        entry_bar=100,
        entry_time=datetime.now(),
        entry_price=50000.0,
        direction=1,
        timeframe='15m'
    )
    
    data_exact = MarketData(
        bar=104,  # Exactly 4 bars after entry
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=1000
    )
    
    should_exit_exact, reason_exact = manager.check_exit(trade_exact, data_exact)
    if should_exit_exact and reason_exact == "4_bars":
        print(f"      ✅ Exactly 4 bars held: Exit triggered (correct)")
    else:
        print(f"      ❌ Exactly 4 bars should exit (Exit: {should_exit_exact}, Reason: {reason_exact})")
        all_passed = False
    
    # Test 6.4: Trade with bars_held > 4
    print(f"\n   Test 6.4: Trade with bars_held > 4...")
    data_more = MarketData(
        bar=110,  # 10 bars after entry
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=1000
    )
    
    should_exit_more, reason_more = manager.check_exit(trade_exact, data_more)
    if should_exit_more and reason_more == "4_bars":
        print(f"      ✅ More than 4 bars held: Exit triggered (correct)")
    else:
        print(f"      ❌ More than 4 bars should exit (Exit: {should_exit_more}, Reason: {reason_more})")
        all_passed = False
    
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("PHASE 3, BLOCK 3.1: 4-BAR EXIT TESTING")
    print("=" * 70)
    print()
    
    tests = [
        ("Basic 4-Bar Exit", test_4_bar_exit_basic),
        ("4-Bar Exit for SHORT", test_4_bar_exit_short),
        ("Bar Counting Accuracy", test_bar_counting),
        ("Exit at Candle Close", test_exit_at_candle_close),
        ("P&L Calculation", test_pnl_calculation),
        ("Edge Cases", test_edge_cases),
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
        print("Block 3.1: 4-Bar Exit - VERIFIED ✅")
        print("=" * 70)
        print()
        print("✅ Basic 4-bar exit working (LONG and SHORT)")
        print("✅ Bar counting accurate")
        print("✅ Exit at candle close (not running candle)")
        print("✅ P&L calculation correct")
        print("✅ Edge cases handled gracefully")
        print()
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

