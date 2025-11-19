"""
Comprehensive Test Runner - ALL Scenarios
Runs ALL test files systematically with detailed logging for each component.

Test Phases:
1. Phase 1: Data Management & State Persistence (3 test files)
2. Phase 2: ML System Core (4 test files)
3. Phase 3: Exit Strategies (2 test files)
4. Phase 4: OMS Components (5 test files)
5. Phase 5: Integration Testing (2 test files)
6. Phase 6: Gap Protection & Recovery (2 test files)
7. Phase 7: End-to-End Integration (1 test file)
8. Phase 8: Live Zerodha API Testing (1 test file)

Total: 20 test files, ~150+ test scenarios

All logs saved to: logs/test_<component>_YYYYMMDD_HHMMSS.log
"""

from __future__ import annotations

import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def run_test_file(test_file: str, log_file: str, extra_args: List[str] = None) -> Tuple[bool, str]:
    """
    Run a single test file and capture output
    
    Args:
        test_file: Path to test file
        log_file: Path to log file
        extra_args: Additional command line arguments (e.g., request_token)
        
    Returns:
        Tuple of (success, output)
    """
    test_path = PROJECT_ROOT / "scripts" / test_file
    
    if not test_path.exists():
        return False, f"Test file not found: {test_file}"
    
    print(f"\n{'='*70}")
    print(f"Running: {test_file}")
    print(f"{'='*70}")
    print(f"Log file: {log_file}")
    if extra_args:
        print(f"Extra args: {extra_args}")
    print()
    
    try:
        # Build command
        cmd = [sys.executable, str(test_path)]
        if extra_args:
            cmd.extend(extra_args)
        
        # Run test with logging
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout per test
        )
        
        # Write to log file
        log_path = PROJECT_ROOT / "logs" / log_file
        log_path.parent.mkdir(exist_ok=True)
        
        with open(log_path, 'w') as f:
            f.write(f"Test: {test_file}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"{'='*70}\n\n")
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
            f.write(f"\n\nReturn Code: {result.returncode}\n")
        
        # Print summary
        if result.returncode == 0:
            print(f"✅ PASS: {test_file}")
            print(f"   Log saved: {log_file}")
            return True, result.stdout
        else:
            print(f"❌ FAIL: {test_file} (return code: {result.returncode})")
            print(f"   Log saved: {log_file}")
            print(f"   Check log for details")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        error_msg = f"Test timed out after 10 minutes: {test_file}"
        print(f"⏱️  TIMEOUT: {test_file}")
        
        # Write timeout to log
        log_path = PROJECT_ROOT / "logs" / log_file
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, 'w') as f:
            f.write(f"Test: {test_file}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"ERROR: {error_msg}\n")
        
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Error running test: {e}"
        print(f"❌ ERROR: {test_file} - {error_msg}")
        return False, error_msg


def main(request_token: str = None):
    """Run all test files systematically"""
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST RUNNER - ALL SCENARIOS")
    print("="*70)
    print()
    print("This will run ALL test files from ALL phases:")
    print("  - Phase 1: Data Management & State Persistence (3 files)")
    print("  - Phase 2: ML System Core (4 files)")
    print("  - Phase 3: Exit Strategies (2 files)")
    print("  - Phase 4: OMS Components (5 files)")
    print("  - Phase 5: Integration Testing (2 files)")
    print("  - Phase 6: Gap Protection & Recovery (2 files)")
    print("  - Phase 7: End-to-End Integration (1 file)")
    print("  - Phase 8: Live Zerodha API Testing (1 file)")
    print()
    print("Total: 20 test files, ~150+ test scenarios")
    print()
    print("All logs will be saved to: logs/test_<component>_YYYYMMDD_HHMMSS.log")
    if request_token:
        print(f"\n⚠️  Using provided request token for live API tests")
    print()
    
    # Test file inventory
    test_files = {
        "Phase 1: Data Management & State Persistence": [
            ("test_trading_state_manager.py", "test_trading_state_manager"),
            ("test_live_data_manager.py", "test_live_data_manager"),
            ("test_zerodha_futures_utils.py", "test_zerodha_futures_utils"),
        ],
        "Phase 2: ML System Core": [
            ("test_ml_extensions.py", "test_ml_extensions"),
            ("test_volume_profile.py", "test_volume_profile"),
            ("test_lorentzian_classifier.py", "test_lorentzian_classifier"),
            ("test_trading_system.py", "test_trading_system"),
        ],
        "Phase 3: Exit Strategies": [
            ("test_exit_strategies.py", "test_exit_strategies"),
            ("test_volume_exit.py", "test_volume_exit"),
        ],
        "Phase 4: OMS Components": [
            ("test_option_chain_manager.py", "test_option_chain_manager"),
            ("test_margin_calculator.py", "test_margin_calculator"),
            ("test_order_manager.py", "test_order_manager"),
            ("test_running_signal_executor.py", "test_running_signal_executor"),
            ("test_websocket_price_feed.py", "test_websocket_price_feed"),
        ],
        "Phase 5: Integration Testing": [
            ("test_integration_complete_flow.py", "test_integration_complete_flow"),
            ("test_integration_state_persistence.py", "test_integration_state_persistence"),
        ],
        "Phase 6: Gap Protection & Recovery": [
            ("test_gap_detection.py", "test_gap_detection"),
            ("test_recovery_scenarios.py", "test_recovery_scenarios"),
        ],
        "Phase 7: End-to-End Integration": [
            ("test_end_to_end_integration.py", "test_end_to_end_integration"),
        ],
        "Phase 8: Live Zerodha API Testing": [
            ("test_live_zerodha_api.py", "live_api_test"),
        ],
    }
    
    # Results tracking
    results: Dict[str, List[Tuple[str, bool, str]]] = {}
    total_tests = 0
    total_passed = 0
    total_failed = 0
    
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Run all test files
    for phase_name, tests in test_files.items():
        print(f"\n{'='*70}")
        print(f"{phase_name}")
        print(f"{'='*70}")
        
        phase_results = []
        
        for test_file, log_prefix in tests:
            total_tests += 1
            log_file = f"{log_prefix}_{timestamp}.log"
            
            # Pass request_token for live API test
            extra_args = None
            if test_file == "test_live_zerodha_api.py" and request_token:
                extra_args = [request_token]
            
            success, output = run_test_file(test_file, log_file, extra_args=extra_args)
            
            if success:
                total_passed += 1
            else:
                total_failed += 1
            
            phase_results.append((test_file, success, output))
            
            # Small delay between tests
            time.sleep(1)
        
        results[phase_name] = phase_results
    
    # Generate summary report
    elapsed_time = time.time() - start_time
    
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST SUMMARY")
    print("="*70)
    print()
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed} ✅")
    print(f"Failed: {total_failed} ❌")
    print(f"Success Rate: {(total_passed/total_tests*100):.1f}%")
    print(f"Total Time: {elapsed_time/60:.1f} minutes")
    print()
    
    # Phase-by-phase summary
    print("Phase-by-Phase Results:")
    print("-" * 70)
    
    for phase_name, phase_results in results.items():
        phase_passed = sum(1 for _, success, _ in phase_results if success)
        phase_total = len(phase_results)
        
        status = "✅" if phase_passed == phase_total else "⚠️"
        print(f"{status} {phase_name}: {phase_passed}/{phase_total} passed")
        
        for test_file, success, _ in phase_results:
            test_status = "✅" if success else "❌"
            print(f"   {test_status} {test_file}")
    
    print()
    print("-" * 70)
    
    # Save summary to file
    summary_file = PROJECT_ROOT / "logs" / f"test_summary_{timestamp}.log"
    with open(summary_file, 'w') as f:
        f.write("COMPREHENSIVE TEST SUMMARY\n")
        f.write("="*70 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Total Tests: {total_tests}\n")
        f.write(f"Passed: {total_passed}\n")
        f.write(f"Failed: {total_failed}\n")
        f.write(f"Success Rate: {(total_passed/total_tests*100):.1f}%\n")
        f.write(f"Total Time: {elapsed_time/60:.1f} minutes\n\n")
        
        f.write("Phase-by-Phase Results:\n")
        f.write("-" * 70 + "\n")
        
        for phase_name, phase_results in results.items():
            phase_passed = sum(1 for _, success, _ in phase_results if success)
            phase_total = len(phase_results)
            
            status = "✅" if phase_passed == phase_total else "⚠️"
            f.write(f"{status} {phase_name}: {phase_passed}/{phase_total} passed\n")
            
            for test_file, success, output in phase_results:
                test_status = "✅" if success else "❌"
                f.write(f"   {test_status} {test_file}\n")
                if not success:
                    f.write(f"      Error: {output[:200]}...\n")
    
    print(f"\n📄 Summary saved to: {summary_file}")
    
    # Final status
    print("\n" + "="*70)
    if total_failed == 0:
        print("🎉 ALL TESTS PASSED!")
        print("✅ System is fully verified and ready for live trading")
    elif total_passed >= total_tests * 0.8:
        print("⚠️  MOST TESTS PASSED")
        print(f"   {total_failed} test(s) failed - Review and fix before live trading")
    else:
        print("❌ MULTIPLE TESTS FAILED")
        print(f"   {total_failed} test(s) failed - Please review and fix issues")
    print("="*70)
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    import sys as sys_module
    # Check for request token as command line argument
    request_token = sys_module.argv[1] if len(sys_module.argv) > 1 else None
    
    try:
        sys.exit(main(request_token=request_token))
    except KeyboardInterrupt:
        print("\n\n⚠️  Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

