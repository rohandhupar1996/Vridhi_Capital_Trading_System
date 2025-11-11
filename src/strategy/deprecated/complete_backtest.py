"""
Complete Backtest Engine - Volume Exit for SHORT only
Integrates: ML signals + Volume nodes + Dual timeframe + Repaint detection
"""

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from dual_timeframe import DualTimeframeSystem, Signal
from volume_nodes import VolumeNodeDetector
from repaint_detector import RepaintDetector
from trading_system import TradingSettings


@dataclass
class Trade:
    entry_bar: int
    entry_time: datetime
    entry_price: float
    direction: int  # 1=long, -1=short
    timeframe: str  # '15m' or '1h'
    volume_nodes: List[float] = None  # Peak prices at entry
    exit_bar: Optional[int] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    bars_held: int = 0
    pnl_pct: float = 0.0
    
    # Drawdown tracking
    max_favorable_pct: float = 0.0  # Max profit during trade
    max_adverse_pct: float = 0.0    # Max drawdown during trade


class CompleteBacktester:
    """Full backtest with all features"""
    
    def __init__(self, settings: TradingSettings):
        self.dual_system = DualTimeframeSystem(settings)
        self.volume_detector = VolumeNodeDetector(lookback=360, num_rows=100)
        self.repaint_detector = RepaintDetector()
        
        self.current_trade: Optional[Trade] = None
        self.trades: List[Trade] = []
        
        self.data_15m = None
        self.data_1h = None
    
    def load_data(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame):
        """Load data and pre-calculate signals"""
        self.dual_system.load_data(df_15m, df_1h)
        self.data_15m = self.dual_system.data_15m
        self.data_1h = self.dual_system.data_1h
    
    def check_volume_node_exit(self, bar_15m: int) -> bool:
        """
        Check if price crosses volume node
        Volume exit ONLY for SHORT trades (long uses default 4-bar)
        """
        if not self.current_trade or self.current_trade.timeframe != '15m':
            return False
        
        # Volume exit only for SHORT trades
        if self.current_trade.direction == 1:  # Long trade
            return False
        
        if not self.current_trade.volume_nodes:
            return False
        
        # Current price (high/low of bar)
        current_high = self.data_15m.high[bar_15m]
        current_low = self.data_15m.low[bar_15m]
        
        # Short trade: exit if price touches node below entry
        for node_price in self.current_trade.volume_nodes:
            if node_price < self.current_trade.entry_price:
                if current_low <= node_price or current_high >= node_price:
                    return True
        
        return False
    
    def check_default_exit(self, bar_15m: int, bar_1h: int) -> bool:
        """Check 4-bar exit rule"""
        if not self.current_trade:
            return False
        
        if self.current_trade.timeframe == '15m':
            bars_held = bar_15m - self.current_trade.entry_bar
            return bars_held >= 4
        else:  # 1h
            bar_1h_entry = self.dual_system.find_1h_bar_for_time(
                self.current_trade.entry_time
            )
            bars_held = bar_1h - bar_1h_entry
            return bars_held >= 4
    
    def update_trade_drawdown(self, bar_15m: int):
        """Update max favorable and adverse excursion for current trade"""
        if not self.current_trade:
            return
        
        current_high = self.data_15m.high[bar_15m]
        current_low = self.data_15m.low[bar_15m]
        entry = self.current_trade.entry_price
        
        if self.current_trade.direction == 1:  # Long
            # Max favorable = highest high
            favorable_pct = (current_high - entry) / entry * 100
            self.current_trade.max_favorable_pct = max(
                self.current_trade.max_favorable_pct, favorable_pct
            )
            # Max adverse = lowest low
            adverse_pct = (current_low - entry) / entry * 100
            self.current_trade.max_adverse_pct = min(
                self.current_trade.max_adverse_pct, adverse_pct
            )
        else:  # Short
            # Max favorable = lowest low
            favorable_pct = (entry - current_low) / entry * 100
            self.current_trade.max_favorable_pct = max(
                self.current_trade.max_favorable_pct, favorable_pct
            )
            # Max adverse = highest high
            adverse_pct = (entry - current_high) / entry * 100
            self.current_trade.max_adverse_pct = min(
                self.current_trade.max_adverse_pct, adverse_pct
            )
    
    def exit_trade(self, bar_15m: int, reason: str):
        """Close current trade"""
        if not self.current_trade:
            return
        
        self.current_trade.exit_bar = bar_15m
        self.current_trade.exit_time = self.data_15m.timestamp[bar_15m]
        self.current_trade.exit_price = self.data_15m.close[bar_15m]
        self.current_trade.exit_reason = reason
        self.current_trade.bars_held = bar_15m - self.current_trade.entry_bar
        
        # Calculate P&L
        if self.current_trade.direction == 1:  # Long
            pnl = (self.current_trade.exit_price - self.current_trade.entry_price) / self.current_trade.entry_price * 100
        else:  # Short
            pnl = (self.current_trade.entry_price - self.current_trade.exit_price) / self.current_trade.entry_price * 100
        
        self.current_trade.pnl_pct = pnl
        
        # Update final drawdown
        self.update_trade_drawdown(bar_15m)
        
        self.trades.append(self.current_trade)
        self.current_trade = None
        self.repaint_detector.reset()
    
    def run(self) -> Dict:
        """Run complete backtest"""
        print(f"\n{'='*70}")
        print("RUNNING COMPLETE BACKTEST")
        print(f"{'='*70}\n")
        
        n_bars = len(self.data_15m.timestamp)
        
        for bar_15m in range(200, n_bars):
            bar_1h = self.dual_system.find_1h_bar_for_time(
                self.data_15m.timestamp[bar_15m]
            )
            
            # Update drawdown for current trade
            if self.current_trade:
                self.update_trade_drawdown(bar_15m)
            
            # Check exits first
            if self.current_trade:
                # Volume node exit (SHORT ONLY)
                if self.check_volume_node_exit(bar_15m):
                    self.exit_trade(bar_15m, "volume_node")
                    continue
                
                # Default 4-bar exit
                if self.check_default_exit(bar_15m, bar_1h):
                    self.exit_trade(bar_15m, "4_bars")
                    continue
            
            # Check entries (if not in trade)
            if not self.current_trade:
                has_conf, signal, tf = self.dual_system.check_confluence_window(bar_15m)
                
                if signal and (has_conf or tf == '15m'):
                    # Get volume nodes at entry
                    peaks = self.volume_detector.update(
                        self.data_15m.high[:bar_15m+1],
                        self.data_15m.low[:bar_15m+1],
                        self.data_15m.volume[:bar_15m+1],
                        self.data_15m.close[:bar_15m+1]
                    )
                    
                    self.current_trade = Trade(
                        entry_bar=bar_15m,
                        entry_time=self.data_15m.timestamp[bar_15m],
                        entry_price=self.data_15m.close[bar_15m],
                        direction=signal.direction,
                        timeframe=tf,
                        volume_nodes=peaks.copy() if peaks else []
                    )
        
        # Calculate metrics
        results = self.calculate_metrics()
        return results
    
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics including drawdown"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_return': 0,
                'max_drawdown': 0,
                'avg_mae': 0,
                'avg_mfe': 0
            }
        
        trades_df = pd.DataFrame([
            {
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'direction': 'LONG' if t.direction == 1 else 'SHORT',
                'timeframe': t.timeframe,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'volume_nodes': ','.join([f'{p:.2f}' for p in t.volume_nodes]) if t.volume_nodes else '',
                'num_nodes': len(t.volume_nodes) if t.volume_nodes else 0,
                'pnl_pct': t.pnl_pct,
                'bars_held': t.bars_held,
                'exit_reason': t.exit_reason,
                'max_favorable_pct': t.max_favorable_pct,
                'max_adverse_pct': t.max_adverse_pct
            }
            for t in self.trades
        ])
        
        wins = trades_df[trades_df['pnl_pct'] > 0]
        losses = trades_df[trades_df['pnl_pct'] < 0]
        
        total_wins = wins['pnl_pct'].sum() if len(wins) > 0 else 0
        total_losses = abs(losses['pnl_pct'].sum()) if len(losses) > 0 else 0
        
        # Calculate equity curve and max drawdown
        equity = 100000  # Starting capital
        equity_curve = [equity]
        peak = equity
        max_dd = 0
        
        for pnl_pct in trades_df['pnl_pct']:
            equity = equity * (1 + pnl_pct / 100)
            equity_curve.append(equity)
            
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        metrics = {
            'total_trades': len(trades_df),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(trades_df) * 100 if len(trades_df) > 0 else 0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
            'total_return': trades_df['pnl_pct'].sum(),
            'avg_win': wins['pnl_pct'].mean() if len(wins) > 0 else 0,
            'avg_loss': losses['pnl_pct'].mean() if len(losses) > 0 else 0,
            'trades_15m': len(trades_df[trades_df['timeframe'] == '15m']),
            'trades_1h': len(trades_df[trades_df['timeframe'] == '1h']),
            'exits_volume': len(trades_df[trades_df['exit_reason'] == 'volume_node']),
            'exits_4bars': len(trades_df[trades_df['exit_reason'] == '4_bars']),
            'exits_repaint': len(trades_df[trades_df['exit_reason'].str.contains('repaint')]),
            'max_drawdown': max_dd,
            'avg_mfe': trades_df['max_favorable_pct'].mean(),
            'avg_mae': abs(trades_df['max_adverse_pct'].mean()),
            'final_equity': equity
        }
        
        return {
            'metrics': metrics,
            'trades': trades_df
        }


# ==================== MAIN ====================

if __name__ == "__main__":
    DB_PATH = "/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db"
    
    print("COMPLETE BACKTEST ENGINE - VOLUME EXIT FOR SHORT ONLY")
    print("="*70)
    
    # Load data
    conn = sqlite3.connect(DB_PATH)
    
    df_15m = pd.read_sql_query("""
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv WHERE timeframe = '15min'
        ORDER BY timestamp DESC LIMIT 3000
    """, conn)
    
    df_1h = pd.read_sql_query("""
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv WHERE timeframe = '1hour'
        ORDER BY timestamp DESC LIMIT 750
    """, conn)
    
    conn.close()
    
    df_15m = df_15m.iloc[::-1].reset_index(drop=True)
    df_1h = df_1h.iloc[::-1].reset_index(drop=True)
    
    print(f"\nData loaded: {len(df_15m)} bars 15min, {len(df_1h)} bars 1hr")
    
    if len(df_1h) < 100:
        print(f"⚠️  ERROR: Not enough 1hr data ({len(df_1h)} bars)")
        print("   Check your database or timeframe name")
        exit(1)
    
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    
    # Run backtest
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=2000,
        use_kernel_filter=True,
        use_volatility_filter=True,
        use_regime_filter=True,
        enable_reentry=True,
        reentry_window_start=3,
        reentry_window_end=50
    )
    
    backtester = CompleteBacktester(settings)
    backtester.load_data(df_15m, df_1h)
    results = backtester.run()
    
    # Print results
    m = results['metrics']
    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}\n")
    print(f"Total Trades:     {m['total_trades']}")
    print(f"Win Rate:         {m['win_rate']:.2f}%")
    print(f"Profit Factor:    {m['profit_factor']:.2f}")
    print(f"Total Return:     {m['total_return']:.2f}%")
    print(f"Max Drawdown:     {m['max_drawdown']:.2f}%")
    print(f"Final Equity:     ${m['final_equity']:,.2f}")
    print(f"\nAvg MFE:          {m['avg_mfe']:.2f}%")
    print(f"Avg MAE:          {m['avg_mae']:.2f}%")
    print(f"\n15min trades:     {m['trades_15m']}")
    print(f"1hr trades:       {m['trades_1h']}")
    print(f"\nVolume exits:     {m['exits_volume']} (SHORT only)")
    print(f"4-bar exits:      {m['exits_4bars']}")
    print(f"Repaint exits:    {m['exits_repaint']}")
    
    # Save
    results['trades'].to_csv('complete_backtest_trades.csv', index=False)
    print(f"\n💾 Saved: complete_backtest_trades.csv")