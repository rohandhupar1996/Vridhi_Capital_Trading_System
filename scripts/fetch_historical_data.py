"""
BankNifty Historical Data Fetcher
Fetches OHLCV data from TradingView and stores in SQLite database
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

# Ensure project root and src/ directory are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from typing import Optional

import pandas as pd
from tvDatafeed import Interval

from src.trading_system.config import AppConfig, DataStoreConfig
from src.trading_system.data import HistoricalDataCollector, TimeframeRequest


def _resolve_credentials(config: DataStoreConfig) -> tuple[HistoricalDataCollector, Optional[str], Optional[str]]:
    """Get credentials from .env file or prompt user."""
    collector = HistoricalDataCollector(config)

    if config.tv_username and config.tv_password:
        return collector, config.tv_username, config.tv_password

    if not sys.stdin.isatty():
        print("⚠️  TradingView credentials not found; proceeding with no-login session.")
        return collector, None, None

    print("⚠️  TradingView credentials not found in configs/.env")
    username = input("\n    Username (press Enter to skip): ").strip()
    password = ""
    if username:
        password = getpass.getpass("    Password: ")
    config.tv_username = username or None
    config.tv_password = password or None
    return collector, username or None, password or None


def _print_collection_summary(results: list[tuple[str, bool]]) -> None:
    print(f"\n{'='*60}")
    print("📋 COLLECTION SUMMARY")
    print(f"{'='*60}")
    success_count = sum(1 for _, success in results if success)
    for tf_name, success in results:
        status = "✅ Success" if success else "❌ Failed"
        print(f"{tf_name:<10} {status}")
    print(f"\nCompleted: {success_count}/{len(results)}")


def _print_db_stats(collector: HistoricalDataCollector, db_path: os.PathLike) -> None:
    stats = collector.statistics()
    print(f"\n{'='*60}")
    print("📊 DATABASE STATISTICS")
    print(f"{'='*60}")
    print(stats.to_string(index=False))

    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"\nDatabase size: {size_mb:.2f} MB")
        print(f"Database location: {os.path.abspath(db_path)}")


def main() -> None:
    print("=" * 60)
    print("🚀 BANKNIFTY HISTORICAL DATA COLLECTOR")
    print("=" * 60)
    print()

    app_config = AppConfig()
    data_config = app_config.data

    collector, username, password = _resolve_credentials(data_config)
    collector.setup_database()
    print(f"📁 Database location: {app_config.resolve_path(data_config.db_path)}")

    # Try login - if it fails, ask for manual credentials
    if not collector.connect_tradingview(username=username, password=password):
        if sys.stdin.isatty() and username and password:
            print("\n⚠️  Login failed with provided credentials.")
            retry = input("    Enter credentials manually? (y/n): ").strip().lower()
            if retry == 'y':
                username = input("    Username: ").strip()
                password = getpass.getpass("    Password: ")
                if username and password:
                    print("\n🔐 Retrying login with manual credentials...")
                    collector.connect_tradingview(username=username, password=password)
        
        print("\n⚠️  Running in no-login mode; data coverage may be limited.")

    print("\n🔄 Starting data collection...")
    print("    This will take approximately 30-60 seconds...")

    # Only fetch 15min data (system requirement)
    requests = [
        TimeframeRequest("15min", Interval.in_15_minute, 6000),
    ]

    results = collector.fetch_timeframes(
        symbol="BANKNIFTY1!",
        exchange="NSE",
        requests=requests,
        overwrite=True,
    )

    _print_collection_summary(results)

    if any(success for _, success in results):
        _print_db_stats(collector, app_config.resolve_path(data_config.db_path))
        
        # Validate data completeness
        print(f"\n{'='*60}")
        print("🔍 DATA COMPLETENESS VALIDATION")
        print(f"{'='*60}")
        symbol = "BANKNIFTY1!"
        all_valid = True
        
        for req in requests:
            validation = collector.validate_data_completeness(
                symbol=symbol,
                timeframe=req.name,
                expected_bars=req.bars
            )
            
            status_icon = "✅" if validation["valid"] else "⚠️"
            print(f"\n{status_icon} {req.name.upper()}:")
            print(f"   Expected bars: {validation['expected_bars']}")
            print(f"   Received bars: {validation['received_bars']}")
            print(f"   Completeness: {validation['completeness_percent']:.1f}%")
            print(f"   Date range: {validation['earliest_date'].date()} to {validation['latest_date'].date()}")
            print(f"   Latest date is up-to-date: {'✅ Yes' if validation['is_up_to_date'] else '❌ No'}")
            print(f"   Gaps detected: {validation['gaps_count']}")
            
            if not validation["valid"]:
                all_valid = False
                if validation['completeness_percent'] < 90:
                    print(f"   ⚠️  Warning: Received less than 90% of requested bars!")
                if not validation['is_up_to_date']:
                    days_behind = (pd.Timestamp.now().normalize() - validation['latest_date'].normalize()).days
                    print(f"   ⚠️  Warning: Data is {days_behind} day(s) behind current date!")
                if validation['gaps_count'] > 0:
                    print(f"   ⚠️  Warning: {validation['gaps_count']} gap(s) found in time series!")
        
        if all_valid:
            print(f"\n{'='*60}")
            print("✅ ALL DATA VALIDATION CHECKS PASSED!")
            print(f"{'='*60}")
        else:
            print(f"\n{'='*60}")
            print("⚠️  SOME DATA VALIDATION CHECKS FAILED")
            print("   Please review warnings above")
            print(f"{'='*60}")
    else:
        print("\n⚠️  No data collected. Please check errors above.")

    collector.close()

    print("\n" + "=" * 60)
    if any(success for _, success in results):
        print("✨ DATA COLLECTION COMPLETE!")
        print("=" * 60)
        print("\n📌 Next steps:")
        print("   1. Open DBeaver")
        print("   2. Connect to SQLite database")
        print(f"   3. Browse to: {app_config.resolve_path(data_config.db_path)}")
        print("   4. View the 'ohlcv' table")
    else:
        print("❌ DATA COLLECTION FAILED")
        print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}")
        raise