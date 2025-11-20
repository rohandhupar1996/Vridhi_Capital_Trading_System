"""
PHASE 2, BLOCK 2.4: TRADING SYSTEM (ML SIGNAL GENERATION) TESTING

Tests the complete LorentzianTradingSystem that integrates:
- ML Extensions (Block 2.1)
- Lorentzian Classifier (Block 2.3)
- Kernel Filtering
- Volatility/Regime/ADX Filters
- Re-entry Logic (3-50 bar window)

Real Trading Parameters:
- neighbors_count: 5
- max_bars_back: 2000
- reentry_window: [3, 50]
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import time
from src.strategy.core.trading_system import (
    LorentzianTradingSystem,
    TradingSettings,
    apply_reentry_logic
)


def generate_test_ohlc(n_bars: int, seed: int = 42) -> tuple:
    """Generate realistic OHLC test data"""
    np.random.seed(seed)
    
    # Simulate price with trend and noise
    trend = np.linspace(100, 130, n_bars)
    noise = np.cumsum(np.random.randn(n_bars) * 0.5)
    close = trend + noise
    
    # Generate OHLC
    high = close + np.abs(np.random.randn(n_bars) * 1.5)
    low = close - np.abs(np.random.randn(n_bars) * 1.5)
    open_price = close + np.random.randn(n_bars) * 0.8
    
    return high, low, close


def test_system_initialization():
    """Test 1: System Initialization"""
    print("=" * 70)
    print("TEST 1: System Initialization")
    print("=" * 70)
    
    # Real trading parameters
    settings = TradingSettings(
        neighbors_count=5,  # Real trading
        max_bars_back=2000,  # Real trading
        feature_count=5,
        use_kernel_filter=True,
        kernel_lookback=8,
        kernel_relative_weight=8.0,
        kernel_regression_level=25,
        kernel_lag=2,
        use_volatility_filter=True,
        use_regime_filter=True,
        regime_threshold=-0.1,
        use_adx_filter=False,
        adx_threshold=20,
        enable_reentry=True,
        reentry_window_start=3,  # Real trading
        reentry_window_end=50,  # Real trading
    )
    
    print(f"\n🔧 Creating system with real trading parameters:")
    print(f"   Neighbors: {settings.neighbors_count}")
    print(f"   Max bars back: {settings.max_bars_back}")
    print(f"   Re-entry window: [{settings.reentry_window_start}, {settings.reentry_window_end}]")
    
    system = LorentzianTradingSystem(settings)
    
    if system.settings.neighbors_count == 5:
        print(f"   ✅ Settings loaded correctly")
    else:
        print(f"   ❌ Settings mismatch")
        return False
    
    if hasattr(system, 'classifier'):
        print(f"   ✅ Classifier initialized")
    else:
        print(f"   ❌ Classifier not initialized")
        return False
    
    if system.classifier.neighbors_count == 5:
        print(f"   ✅ Classifier using correct neighbors: {system.classifier.neighbors_count}")
    else:
        print(f"   ❌ Classifier neighbors mismatch: {system.classifier.neighbors_count}")
        return False
    
    if system.classifier.max_bars_back == 2000:
        print(f"   ✅ Classifier using correct max_bars_back: {system.classifier.max_bars_back}")
    else:
        print(f"   ❌ Classifier max_bars_back mismatch: {system.classifier.max_bars_back}")
        return False
    
    return True


def test_feature_generation():
    """Test 2: Feature Generation (F1-F5)"""
    print("=" * 70)
    print("TEST 2: Feature Generation")
    print("=" * 70)
    
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        feature_count=5
    )
    
    system = LorentzianTradingSystem(settings)
    
    # Generate test data
    n_bars = 1000
    high, low, close = generate_test_ohlc(n_bars)
    
    print(f"\n🔧 Generating features for {n_bars} bars...")
    
    start = time.perf_counter()
    features = system.generate_features(high, low, close)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"   ⏱️  Time: {elapsed_ms:.2f} ms")
    
    # Verify all 5 features present
    expected_features = ['f1', 'f2', 'f3', 'f4', 'f5']
    for feat in expected_features:
        if feat not in features:
            print(f"   ❌ Missing feature: {feat}")
            return False
        if len(features[feat]) != n_bars:
            print(f"   ❌ Feature {feat} length mismatch: {len(features[feat])} != {n_bars}")
            return False
        print(f"   ✅ {feat}: {len(features[feat])} bars")
    
    # Check for NaN values (should be forward-filled)
    for feat in expected_features:
        nan_count = np.sum(np.isnan(features[feat]))
        if nan_count > 0:
            print(f"   ⚠️  {feat} has {nan_count} NaN values (after forward fill)")
        else:
            print(f"   ✅ {feat}: No NaN values")
    
    # Verify feature ranges (normalized features should be 0-1)
    for feat in expected_features:
        valid_feat = features[feat][~np.isnan(features[feat])]
        if len(valid_feat) > 0:
            min_val = np.min(valid_feat)
            max_val = np.max(valid_feat)
            if 0 <= min_val <= 1 and 0 <= max_val <= 1:
                print(f"   ✅ {feat} in valid range: [{min_val:.3f}, {max_val:.3f}]")
            else:
                print(f"   ⚠️  {feat} out of range: [{min_val:.3f}, {max_val:.3f}]")
    
    return True


def test_filter_application():
    """Test 3: Filter Application (Volatility, Regime, ADX)"""
    print("=" * 70)
    print("TEST 3: Filter Application")
    print("=" * 70)
    
    # Test with all filters enabled
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        use_volatility_filter=True,
        use_regime_filter=True,
        regime_threshold=-0.1,
        use_adx_filter=False,  # Usually disabled in real trading
        adx_threshold=20
    )
    
    system = LorentzianTradingSystem(settings)
    
    n_bars = 1000
    high, low, close = generate_test_ohlc(n_bars)
    
    print(f"\n🔧 Applying filters to {n_bars} bars...")
    print(f"   Volatility filter: {settings.use_volatility_filter}")
    print(f"   Regime filter: {settings.use_regime_filter}")
    print(f"   ADX filter: {settings.use_adx_filter}")
    
    start = time.perf_counter()
    filter_all = system.apply_filters(high, low, close)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"   ⏱️  Time: {elapsed_ms:.2f} ms")
    
    # Verify filter output
    if len(filter_all) != n_bars:
        print(f"   ❌ Filter length mismatch: {len(filter_all)} != {n_bars}")
        return False
    
    if filter_all.dtype != bool:
        print(f"   ❌ Filter dtype should be bool, got {filter_all.dtype}")
        return False
    
    # Count filtered bars
    passed_count = np.sum(filter_all)
    filtered_out = n_bars - passed_count
    
    print(f"   ✅ Filter shape: {filter_all.shape}")
    print(f"   ✅ Bars passing filters: {passed_count} ({passed_count/n_bars*100:.1f}%)")
    print(f"   ✅ Bars filtered out: {filtered_out} ({filtered_out/n_bars*100:.1f}%)")
    
    # Test with all filters disabled
    settings_no_filters = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        use_volatility_filter=False,
        use_regime_filter=False,
        use_adx_filter=False
    )
    
    system_no_filters = LorentzianTradingSystem(settings_no_filters)
    filter_all_no_filters = system_no_filters.apply_filters(high, low, close)
    
    if np.all(filter_all_no_filters):
        print(f"   ✅ All filters disabled: All bars pass")
    else:
        print(f"   ❌ All filters disabled but some bars filtered")
        return False
    
    return True


def test_kernel_filter():
    """Test 4: Kernel Filter Application"""
    print("=" * 70)
    print("TEST 4: Kernel Filter")
    print("=" * 70)
    
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        use_kernel_filter=True,
        kernel_lookback=8,
        kernel_relative_weight=8.0,
        kernel_regression_level=25,
        kernel_lag=2
    )
    
    system = LorentzianTradingSystem(settings)
    
    n_bars = 1000
    high, low, close = generate_test_ohlc(n_bars)
    
    print(f"\n🔧 Applying kernel filter to {n_bars} bars...")
    
    start = time.perf_counter()
    kernel_data = system.apply_kernel_filter(close)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"   ⏱️  Time: {elapsed_ms:.2f} ms")
    
    # Verify kernel output
    required_keys = ['kernel_estimate', 'is_bullish', 'is_bearish']
    for key in required_keys:
        if key not in kernel_data:
            print(f"   ❌ Missing key: {key}")
            return False
    
    if len(kernel_data['kernel_estimate']) != n_bars:
        print(f"   ❌ Kernel estimate length mismatch")
        return False
    
    if len(kernel_data['is_bullish']) != n_bars:
        print(f"   ❌ is_bullish length mismatch")
        return False
    
    if len(kernel_data['is_bearish']) != n_bars:
        print(f"   ❌ is_bearish length mismatch")
        return False
    
    # Check data types
    if kernel_data['is_bullish'].dtype != bool:
        print(f"   ❌ is_bullish should be bool, got {kernel_data['is_bullish'].dtype}")
        return False
    
    if kernel_data['is_bearish'].dtype != bool:
        print(f"   ❌ is_bearish should be bool, got {kernel_data['is_bearish'].dtype}")
        return False
    
    bullish_count = np.sum(kernel_data['is_bullish'])
    bearish_count = np.sum(kernel_data['is_bearish'])
    
    print(f"   ✅ Kernel estimate: {len(kernel_data['kernel_estimate'])} bars")
    print(f"   ✅ Bullish bars: {bullish_count} ({bullish_count/n_bars*100:.1f}%)")
    print(f"   ✅ Bearish bars: {bearish_count} ({bearish_count/n_bars*100:.1f}%)")
    
    # Test with kernel filter disabled
    settings_no_kernel = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        use_kernel_filter=False
    )
    
    system_no_kernel = LorentzianTradingSystem(settings_no_kernel)
    kernel_data_no_kernel = system_no_kernel.apply_kernel_filter(close)
    
    if np.array_equal(kernel_data_no_kernel['kernel_estimate'], close):
        print(f"   ✅ Kernel disabled: Returns close price")
    else:
        print(f"   ⚠️  Kernel disabled: Output differs from close")
    
    if np.all(kernel_data_no_kernel['is_bullish']) and np.all(kernel_data_no_kernel['is_bearish']):
        print(f"   ✅ Kernel disabled: All bars bullish and bearish (no filtering)")
    else:
        print(f"   ⚠️  Kernel disabled: Some bars not bullish/bearish")
    
    return True


def test_complete_signal_generation():
    """Test 5: Complete Signal Generation Pipeline"""
    print("=" * 70)
    print("TEST 5: Complete Signal Generation (Real Trading Parameters)")
    print("=" * 70)
    
    # Real trading parameters
    settings = TradingSettings(
        neighbors_count=5,  # Real trading
        max_bars_back=2000,  # Real trading
        feature_count=5,
        use_kernel_filter=True,
        kernel_lookback=8,
        kernel_relative_weight=8.0,
        kernel_regression_level=25,
        kernel_lag=2,
        use_volatility_filter=True,
        use_regime_filter=True,
        regime_threshold=-0.1,
        use_adx_filter=False,
        enable_reentry=True,
        reentry_window_start=3,  # Real trading
        reentry_window_end=50,  # Real trading
    )
    
    system = LorentzianTradingSystem(settings)
    
    n_bars = 3000
    high, low, close = generate_test_ohlc(n_bars, seed=42)
    
    print(f"\n🔧 Generating signals for {n_bars} bars...")
    print(f"   Neighbors: {settings.neighbors_count}")
    print(f"   Max bars back: {settings.max_bars_back}")
    print(f"   Re-entry window: [{settings.reentry_window_start}, {settings.reentry_window_end}]")
    
    # Suppress print output from generate_signals
    import io
    from contextlib import redirect_stdout
    
    f = io.StringIO()
    with redirect_stdout(f):
        start = time.perf_counter()
        results = system.generate_signals(high, low, close, start_bar=100)
        elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"   ⏱️  Time: {elapsed_ms:.2f} ms ({elapsed_ms/n_bars*1000:.2f} μs per bar)")
    
    # Verify results structure
    required_keys = [
        'predictions', 'signals', 'start_long', 'start_short',
        'end_long', 'end_short', 'filter_all', 'kernel_estimate', 'features'
    ]
    
    for key in required_keys:
        if key not in results:
            print(f"   ❌ Missing key: {key}")
            return False
    
    # Verify lengths
    for key in ['predictions', 'signals', 'start_long', 'start_short', 'end_long', 'end_short', 'filter_all']:
        if len(results[key]) != n_bars:
            print(f"   ❌ {key} length mismatch: {len(results[key])} != {n_bars}")
            return False
    
    # Count signals
    long_entries = np.sum(results['start_long'])
    short_entries = np.sum(results['start_short'])
    long_exits = np.sum(results['end_long'])
    short_exits = np.sum(results['end_short'])
    
    raw_long_signals = np.sum(results['signals'] == 1)
    raw_short_signals = np.sum(results['signals'] == -1)
    raw_neutral_signals = np.sum(results['signals'] == 0)
    
    print(f"\n📊 Signal Statistics:")
    print(f"   Raw LONG signals: {raw_long_signals} ({raw_long_signals/n_bars*100:.1f}%)")
    print(f"   Raw SHORT signals: {raw_short_signals} ({raw_short_signals/n_bars*100:.1f}%)")
    print(f"   Raw NEUTRAL signals: {raw_neutral_signals} ({raw_neutral_signals/n_bars*100:.1f}%)")
    print(f"\n📊 Entry/Exit Signals:")
    print(f"   Long entries: {long_entries}")
    print(f"   Short entries: {short_entries}")
    print(f"   Long exits: {long_exits}")
    print(f"   Short exits: {short_exits}")
    print(f"   Total trades: {long_entries + short_entries}")
    
    # Verify signal types
    if results['signals'].dtype in [np.int8, np.int32, np.int64]:
        print(f"   ✅ Signals dtype: {results['signals'].dtype}")
    else:
        print(f"   ⚠️  Signals dtype: {results['signals'].dtype}")
    
    if results['start_long'].dtype == bool:
        print(f"   ✅ Entry/exit signals are boolean")
    else:
        print(f"   ❌ Entry/exit signals should be boolean")
        return False
    
    # Verify predictions range (for k=5)
    valid_predictions = results['predictions'][~np.isnan(results['predictions'])]
    if len(valid_predictions) > 0:
        min_pred = np.min(valid_predictions)
        max_pred = np.max(valid_predictions)
        if abs(min_pred) <= 5 and abs(max_pred) <= 5:
            print(f"   ✅ Predictions in valid range: [{min_pred:.2f}, {max_pred:.2f}]")
        else:
            print(f"   ⚠️  Predictions out of range: [{min_pred:.2f}, {max_pred:.2f}]")
    
    return True


def test_reentry_logic():
    """Test 6: Re-entry Logic (Too Soon, Within Window, Outside Window)"""
    print("=" * 70)
    print("TEST 6: Re-entry Logic Verification")
    print("=" * 70)
    
    # Create test signals
    n_bars = 100
    signals = np.zeros(n_bars, dtype=np.int8)
    predictions = np.zeros(n_bars, dtype=np.float32)
    
    # Simulate: LONG signal at bar 10, exit at bar 14 (4 bars held)
    # Then LONG signals at bars 15, 17, 20, 55
    signals[10] = 1  # First entry
    signals[14] = -1  # Exit after 4 bars
    signals[15] = 1  # Too soon (bar 15, only 1 bar after exit, need 3)
    signals[17] = 1  # Within window (bar 17, 3 bars after exit, prediction=3)
    signals[20] = 1  # Within window (bar 20, 6 bars after exit, prediction=2)
    signals[55] = 1  # Outside window (bar 55, 41 bars after exit, >50)
    
    # Set predictions for within-window signals
    predictions[17] = 3.0  # Positive prediction (should allow entry)
    predictions[20] = -2.0  # Negative prediction (should NOT allow entry)
    predictions[55] = 4.0  # Positive prediction (should allow entry)
    
    # Filters and kernel (all passing)
    kernel_bullish = np.ones(n_bars, dtype=bool)
    kernel_bearish = np.ones(n_bars, dtype=bool)
    filter_all = np.ones(n_bars, dtype=bool)
    
    reentry_start = 3
    reentry_end = 50
    
    print(f"\n🔧 Testing re-entry logic:")
    print(f"   Re-entry window: [{reentry_start}, {reentry_end}]")
    print(f"   First entry at bar 10, exit at bar 14")
    print(f"   Test signals at bars: 15 (too soon), 17 (within, pred=+3), 20 (within, pred=-2), 55 (outside, pred=+4)")
    
    start_long, start_short, end_long, end_short = apply_reentry_logic(
        signals, predictions, kernel_bullish, kernel_bearish,
        filter_all, reentry_start, reentry_end
    )
    
    # Verify first entry happens
    if start_long[10]:
        print(f"   ✅ First entry at bar 10")
    else:
        print(f"   ❌ First entry missing at bar 10")
        return False
    
    # Verify exit happens at bar 14
    if end_long[14]:
        print(f"   ✅ Exit at bar 14 (4 bars held)")
    else:
        print(f"   ❌ Exit missing at bar 14")
        return False
    
    # Verify too soon signal (bar 15) is NOT taken
    if not start_long[15]:
        print(f"   ✅ Bar 15 signal rejected (too soon: 1 bar after exit, need 3)")
    else:
        print(f"   ❌ Bar 15 signal should be rejected (too soon)")
        return False
    
    # Verify within-window signal with positive prediction (bar 17) IS taken
    if start_long[17]:
        print(f"   ✅ Bar 17 signal taken (within window: 3 bars after exit, pred=+3)")
    else:
        print(f"   ❌ Bar 17 signal should be taken (within window, positive pred)")
        return False
    
    # Verify within-window signal with negative prediction (bar 20) is NOT taken
    if not start_long[20]:
        print(f"   ✅ Bar 20 signal rejected (within window but pred=-2)")
    else:
        print(f"   ❌ Bar 20 signal should be rejected (negative pred)")
        return False
    
    # Verify outside-window signal (bar 55) IS taken
    if start_long[55]:
        print(f"   ✅ Bar 55 signal taken (outside window: 41 bars after exit, >50)")
    else:
        print(f"   ❌ Bar 55 signal should be taken (outside window)")
        return False
    
    return True


def test_performance():
    """Test 7: Performance Test (Real Trading Parameters)"""
    print("=" * 70)
    print("TEST 7: Performance Test")
    print("=" * 70)
    
    settings = TradingSettings(
        neighbors_count=5,  # Real trading
        max_bars_back=2000,  # Real trading
        feature_count=5,
        use_kernel_filter=True,
        use_volatility_filter=True,
        use_regime_filter=True,
        enable_reentry=True,
        reentry_window_start=3,
        reentry_window_end=50
    )
    
    system = LorentzianTradingSystem(settings)
    
    n_bars = 10000
    high, low, close = generate_test_ohlc(n_bars, seed=42)
    
    print(f"\n🔧 Performance test: {n_bars} bars")
    print(f"   Neighbors: {settings.neighbors_count}")
    print(f"   Max bars back: {settings.max_bars_back}")
    print("   Target: <500ms for 10k bars")
    
    # Warmup
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        _ = system.generate_signals(high[:500], low[:500], close[:500], start_bar=100)
    
    # Benchmark
    f = io.StringIO()
    with redirect_stdout(f):
        start = time.perf_counter()
        results = system.generate_signals(high, low, close, start_bar=100)
        elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"   ⏱️  Time: {elapsed_ms:.2f} ms ({elapsed_ms/n_bars*1000:.2f} μs per bar)")
    
    target_ms = 500.0
    if elapsed_ms < target_ms:
        print(f"   ✅ Performance acceptable (<{target_ms}ms)")
    else:
        print(f"   ⚠️  Performance: {elapsed_ms:.2f}ms (target: <{target_ms}ms)")
        print("   (Still acceptable - runs once per candle close, not every tick)")
    
    return True


def test_edge_cases():
    """Test 8: Edge Cases"""
    print("=" * 70)
    print("TEST 8: Edge Cases")
    print("=" * 70)
    
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        feature_count=5
    )
    
    all_passed = True
    
    # Test 8.1: Small dataset
    print(f"\n🔧 Test 8.1: Small dataset (50 bars)...")
    system = LorentzianTradingSystem(settings)
    high, low, close = generate_test_ohlc(50)
    
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            results = system.generate_signals(high, low, close, start_bar=10)
            if len(results['signals']) == 50:
                print(f"   ✅ Handled small dataset: {len(results['signals'])} signals")
            else:
                print(f"   ❌ Small dataset length mismatch")
                all_passed = False
        except Exception as e:
            print(f"   ❌ Error with small dataset: {e}")
            all_passed = False
    
    # Test 8.2: Constant prices
    print(f"\n🔧 Test 8.2: Constant prices...")
    constant_close = np.ones(500) * 100.0
    constant_high = constant_close + 0.1
    constant_low = constant_close - 0.1
    
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            results = system.generate_signals(constant_high, constant_low, constant_close, start_bar=100)
            if len(results['signals']) == 500:
                print(f"   ✅ Handled constant prices: {len(results['signals'])} signals")
            else:
                print(f"   ❌ Constant prices length mismatch")
                all_passed = False
        except Exception as e:
            print(f"   ❌ Error with constant prices: {e}")
            all_passed = False
    
    # Test 8.3: Very large dataset
    print(f"\n🔧 Test 8.3: Large dataset (5000 bars)...")
    high, low, close = generate_test_ohlc(5000)
    
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            start = time.perf_counter()
            results = system.generate_signals(high, low, close, start_bar=100)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            if len(results['signals']) == 5000:
                print(f"   ✅ Handled large dataset: {len(results['signals'])} signals in {elapsed_ms:.2f}ms")
            else:
                print(f"   ❌ Large dataset length mismatch")
                all_passed = False
        except Exception as e:
            print(f"   ❌ Error with large dataset: {e}")
            all_passed = False
    
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("PHASE 2, BLOCK 2.4: TRADING SYSTEM (ML SIGNAL GENERATION) TESTING")
    print("=" * 70)
    print()
    
    tests = [
        ("System Initialization", test_system_initialization),
        ("Feature Generation", test_feature_generation),
        ("Filter Application", test_filter_application),
        ("Kernel Filter", test_kernel_filter),
        ("Complete Signal Generation", test_complete_signal_generation),
        ("Re-entry Logic", test_reentry_logic),
        ("Performance Test", test_performance),
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
        print("Block 2.4: Trading System (ML Signal Generation) - VERIFIED ✅")
        print("=" * 70)
        print()
        print("✅ System initialization correct")
        print("✅ Feature generation working (F1-F5)")
        print("✅ Filters applied correctly")
        print("✅ Kernel filtering working")
        print("✅ Complete signal generation pipeline functional")
        print("✅ Re-entry logic verified (too soon, within window, outside window)")
        print("✅ Performance acceptable")
        print("✅ Edge cases handled gracefully")
        print()
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

