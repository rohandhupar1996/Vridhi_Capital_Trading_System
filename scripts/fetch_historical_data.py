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

from tvDatafeed import Interval

from src.trading_system.config import AppConfig, DataStoreConfig
from src.trading_system.data import HistoricalDataCollector, TimeframeRequest


def _resolve_credentials(config: DataStoreConfig) -> HistoricalDataCollector:
    """Ensure credentials are available and return a collector instance."""
    collector = HistoricalDataCollector(config)

    if config.tv_username and config.tv_password:
        print(f"✅ Using credentials for: {config.tv_username}")
        return collector

    if not sys.stdin.isatty():
        print("⚠️  TradingView credentials not found; proceeding with no-login session.")
        config.tv_username = None
        config.tv_password = None
        return collector

    print("⚠️  TradingView credentials not found in environment.")
    username = input("    Username (leave blank for no-login): ").strip()
    password = ""
    if username:
        password = getpass.getpass("    Password: ")
    config.tv_username = username or None
    config.tv_password = password or None
    return collector


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

    collector = _resolve_credentials(data_config)
    collector.setup_database()
    print(f"📁 Database location: {app_config.resolve_path(data_config.db_path)}")

    if not collector.connect_tradingview():
        print("\n⚠️  Running in no-login mode; data coverage may be limited.")

    print("\n🔄 Starting data collection...")
    print("    This will take approximately 30-60 seconds...")

    requests = [
        TimeframeRequest("5min", Interval.in_5_minute, 10_000),
        TimeframeRequest("15min", Interval.in_15_minute, 10_000),
        TimeframeRequest("1hour", Interval.in_1_hour, 10_000),
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