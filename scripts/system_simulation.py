"""
End-to-end system simulation (offline, using historical candles).

Purpose:
- Exercise the full pipeline from login → price feed → signals → OMS/executor
- Use historical data as if it were live candles
- Attempt real orders (expected to be rejected on weekends/closed market), to test:
  - Zerodha login/auth
  - Futures price handling
  - OMS long/short entry/exit (NRML MARKET)
  - Running-candle executor (flicker + reversal)
  - Dynamic timeframe (expiry day 5min override)
  - Earnings filter (blocks entries during configured periods)

NOTE:
- This is a *simulation* script; P&L, strategy quality, and position sizing here
  are NOT meant for live trading decisions.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import os
import sqlite3

import pandas as pd
from dotenv import load_dotenv
from src.trading_system.config import AppConfig
from src.trading_system.logging import setup_logging, ComponentLogger
from src.trading_system.broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials
from src.trading_system.oms import OrderManager
from src.trading_system.oms.running_signal_executor import RunningSignalExecutor
from src.trading_system.oms.dynamic_timeframe import DynamicTimeframeController, DynamicTimeframeConfig
from src.trading_system.oms.earnings_filter import EarningsSeasonFilter, EarningsFilterConfig


def load_simulation_data_from_db(
    db_path: Path, 
    symbol: str, 
    timeframe: str,
    month_filter: Optional[Tuple[int, int]] = None  # (start_month, end_month) e.g., (10, 11) for Oct-Nov
) -> pd.DataFrame:
    """
    Load historical candles from SQLite DB (ohlcv table).
    Uses the data ingested by HistoricalDataCollector.
    
    Args:
        db_path: Path to SQLite database
        symbol: Symbol to load (e.g., "BANKNIFTY1!")
        timeframe: Timeframe (e.g., "15min")
        month_filter: Optional tuple (start_month, end_month) to filter data by month
                     e.g., (10, 11) for October-November only
    """
    conn = sqlite3.connect(db_path)
    
    # Build query with optional month filter
    if month_filter:
        start_month, end_month = month_filter
        query = """
            SELECT timestamp AS datetime, open, high, low, close
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
            AND CAST(strftime('%m', datetime(timestamp, 'unixepoch')) AS INTEGER) >= ?
            AND CAST(strftime('%m', datetime(timestamp, 'unixepoch')) AS INTEGER) <= ?
            ORDER BY timestamp
        """
        params = (symbol, timeframe, start_month, end_month)
    else:
        query = """
            SELECT timestamp AS datetime, open, high, low, close
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp
        """
        params = (symbol, timeframe)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        month_info = f" (months {month_filter[0]}-{month_filter[1]})" if month_filter else ""
        raise ValueError(f"No data found in DB for symbol={symbol}, timeframe={timeframe}{month_info}")

    # Fix timestamp parsing: timestamp is stored as Unix seconds in DB
    df["datetime"] = pd.to_datetime(df["datetime"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    return df[["datetime", "open", "high", "low", "close"]]


def load_simulation_data(csv_path: Path) -> pd.DataFrame:
    """
    Load historical candles from CSV.
    Expected columns:
    - Either a proper datetime column (datetime/timestamp/Date)
    - Or a Unix seconds column named 'time' (TradingView-style)
    """
    df = pd.read_csv(csv_path)
    # Try to infer datetime column
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
    elif "timestamp" in df.columns:
        df["datetime"] = pd.to_datetime(df["timestamp"])
    elif "Date" in df.columns:
        df["datetime"] = pd.to_datetime(df["Date"])
    elif "time" in df.columns:
        # TradingView-style Unix seconds since epoch
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    else:
        raise ValueError("No usable datetime/time column found in CSV")

    df = df.sort_values("datetime").reset_index(drop=True)
    return df[["datetime", "open", "high", "low", "close"]]


def init_kite_and_oms(app_config: AppConfig, logger: ComponentLogger) -> tuple[OrderManager, ZerodhaAuthenticator]:
    """
    Initialize Zerodha authenticator and OrderManager.
    """
    # Load credentials from configs/.env (same as zerodha_login.py)
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded credentials from {env_path}")

    api_key = (
        # From environment
        (os.getenv("ZERODHA_API_KEY") or None)
        # Or from app_config if set there
        or app_config.zerodha.api_key
    )
    api_secret = (
        os.getenv("ZERODHA_API_SECRET") or app_config.zerodha.api_secret
    )

    if not api_key or not api_secret:
        raise RuntimeError(
            "ZERODHA_API_KEY / ZERODHA_API_SECRET not configured. "
            "Set them in configs/.env or AppConfig.zerodha."
        )

    credentials = ZerodhaCredentials(
        api_key=api_key,
        api_secret=api_secret,
    )

    auth_logger = ComponentLogger.get_logger("zerodha_auth")
    authenticator = ZerodhaAuthenticator(
        credentials=credentials,
        token_file="configs/zerodha_tokens.json",
        logger=auth_logger,
    )

    # Try login / reconnect flow
    if not authenticator.login(auto_open_browser=False):
        # If token invalid, user should have run scripts/zerodha_login.py recently.
        auth_logger.warning("Login not yet completed or token invalid. "
                            "Run scripts/zerodha_login.py to obtain a fresh token.")

    # Reconnect if needed
    if not authenticator.reconnect():
        auth_logger.error("Failed to reconnect to Zerodha. Simulation will continue without live broker.")

    kite = authenticator.get_kite_instance()
    if not kite:
        raise RuntimeError("Kite instance unavailable. Cannot simulate orders.")

    # Initialize OMS
    oms_logger = ComponentLogger.get_logger("order_manager")
    oms = OrderManager(
        kite=kite,
        lot_size=app_config.trading.position_size if hasattr(app_config, "trading") else 8,
        hedge_legs=20,
        logger=oms_logger,
        dry_run=False,  # REAL orders - will attempt actual broker calls
    )

    return oms, authenticator


def init_timeframe_and_filters(app_config: AppConfig) -> tuple[DynamicTimeframeController, EarningsSeasonFilter]:
    """
    Initialize dynamic timeframe controller and earnings season filter from config.
    """
    tf_cfg = DynamicTimeframeConfig(
        base_timeframe="15min",
        expiry_day_timeframe="5min",
        enable_expiry_switch=True,
    )
    tf_controller = DynamicTimeframeController(config=tf_cfg)

    ef_node = getattr(app_config, "earnings_filter", None)
    if ef_node:
        ef_cfg = EarningsFilterConfig(
            use_filter=bool(ef_node.get("use_filter", True)),
            block_first_days_blue=int(ef_node.get("block_first_days_blue", 15)),
            block_after_yellow=int(ef_node.get("block_after_yellow", 15)),
        )
    else:
        ef_cfg = EarningsFilterConfig()

    earnings_filter = EarningsSeasonFilter(config=ef_cfg)

    return tf_controller, earnings_filter


def simple_signal_logic(prev_close: float, close: float) -> str:
    """
    Very simple placeholder signal logic for simulation:
    - If close > prev_close → LONG signal
    - If close < prev_close → SHORT signal
    - Else → NONE

    This is NOT the production ML strategy; it is only to drive the OMS/executor.
    """
    if close > prev_close:
        return "LONG"
    if close < prev_close:
        return "SHORT"
    return "NONE"


def run_simulation(
    source: str = "db",
    csv_path: Optional[Path] = None,
    max_candles: Optional[int] = 200,
    sleep_between: float = 120.0,  # 2 minutes (120 seconds) between candles to avoid rate limits
) -> None:
    """
    Run offline simulation over historical candles.

    Args:
        csv_path: Path to CSV with OHLC data.
        max_candles: Limit number of candles for quick testing.
        sleep_between: Sleep between simulated candles (seconds).
    """
    setup_logging("logs")
    main_logger = ComponentLogger.get_logger("system_simulation")

    app_config = AppConfig()

    # Initialize broker + OMS
    main_logger.info("Initializing Kite + OMS for simulation...")
    oms, authenticator = init_kite_and_oms(app_config, main_logger)

    # Initialize dynamic timeframe + earnings filter + executor
    tf_controller, earnings_filter = init_timeframe_and_filters(app_config)
    executor = RunningSignalExecutor(oms=oms, earnings_filter=earnings_filter)

    # Load historical candles (prefer DB)
    if source == "db":
        db_path = app_config.data.db_path
        # Symbol and timeframe should match what you ingested; adjust if needed
        symbol = "BANKNIFTY1!"
        timeframe = "15min"
        # Filter for October (10) and November (11) only
        month_filter = (10, 11)
        main_logger.info(
            "Loading candles from DB",
            db=str(db_path),
            symbol=symbol,
            timeframe=timeframe,
            months=f"{month_filter[0]}-{month_filter[1]}",
        )
        df = load_simulation_data_from_db(db_path, symbol, timeframe, month_filter=month_filter)
    else:
        if csv_path is None:
            raise ValueError("csv_path must be provided when source='csv'")
        main_logger.info("Loading candles from CSV", csv=str(csv_path))
        df = load_simulation_data(csv_path)
    if max_candles:
        df = df.head(max_candles)

    main_logger.info(
        "Starting simulation",
        candles=len(df),
        csv=str(csv_path),
    )

    prev_close: Optional[float] = None

    for idx, row in df.iterrows():
        dt: datetime = row["datetime"].to_pydatetime()
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])

        # Determine effective timeframe (for logging/behavior)
        effective_tf = tf_controller.get_effective_timeframe(dt)

        candle_id = f"{dt.strftime('%Y-%m-%d %H:%M:%S')}_{effective_tf}"

        # Simulate futures price as close (for this test)
        futures_price = c
        oms.futures_ltp = futures_price

        # Pre-calc margins once near start (optional)
        if idx == 0:
            oms.pre_calculate_margins()

        # Generate a simple placeholder signal using price change
        if prev_close is None:
            signal = "NONE"
        else:
            signal = simple_signal_logic(prev_close, c)

        # Running-candle signal (we use final close as proxy for running updates here)
        executor.on_running_signal(signal, candle_id, futures_price)

        # Candle close reconciliation
        executor.on_candle_close(signal, candle_id, futures_price)

        main_logger.info(
            "Sim candle processed",
            candle_time=dt.isoformat(),
            tf=effective_tf,
            signal=signal,
            futures_price=futures_price,
        )

        prev_close = c

        # Small delay to avoid hammering APIs (orders will likely be rejected on Sunday)
        time.sleep(sleep_between)

    main_logger.info("Simulation completed.")


if __name__ == "__main__":
    # Example CSV path: adjust to your environment / data file
    # Prefer DB-driven simulation by default
    try:
        run_simulation(source="db", max_candles=200, sleep_between=120.0)  # 2 minute delay between candles
    except Exception as e:
        print(f"DB simulation failed: {e}")
        default_csv = Path("src/strategy/runners/NSE_DLY_BANKNIFTY1!, 15.csv")
        if default_csv.exists():
            print("Falling back to CSV simulation...")
            run_simulation(source="csv", csv_path=default_csv, max_candles=200, sleep_between=120.0)  # 2 minute delay
        else:
            print(f"Default CSV not found at {default_csv}. Please update path in scripts/system_simulation.py.")


