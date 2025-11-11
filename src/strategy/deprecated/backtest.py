"""
Backtest & Verification Module
Tests complete system against known scenarios and calculates performance
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import time

from trading_system import LorentzianTradingSystem, TradingSettings


class Backtester:
    """Backtest trading system and calculate performance metrics"""
    
    def __init__(self, system: LorentzianTradingSystem):
        self.system = system
        self.trades = []
        self.equity_curve = []
    
    def run_backtest(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                    initial_capital: float = 100000) -> Dict:
        """
        Run complete backtest and return results
        """
        print(f"\n{'='*70}")
        print(f"BACKTESTING ON {len(close)} BARS")
        print(f"{'='*70}\n")
        
        # Generate signals
        results = self.system.generate_signals(high, low, close, start_bar=100)
        
        # Calculate trades and P&L
        trades_data = self._calculate_trades(
            close, high, low,
            results['start_long'], results['start_short'],
            results['end_long'], results['end_short']
        )
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades_data, initial_capital)
        
        return {
            'results': results,
            'trades': trades_data,
            'metrics': metrics
        }
    
    def _calculate_trades(self, close: np.ndarray, high: np.ndarray, low: np.ndarray,
                         start_long: np.ndarray, start_short: np.ndarray,
                         end_long: np.ndarray, end_short: np.ndarray) -> pd.DataFrame:
        """Calculate all trades with entry/exit prices"""
        
        trades = []
        current_position = None
        entry_price = 0
        entry_bar = 0
        
        for i in range(len(close)):
            # Check for exits first
            if current_position == 'long' and end_long[i]:
                exit_price = close[i]
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                trades.append({
                    'type': 'long',
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'bars_held': i - entry_bar,
                    'pnl_pct': pnl_pct
                })
                current_position = None
            
            elif current_position == 'short' and end_short[i]:
                exit_price = close[i]
                pnl_pct = (entry_price - exit_price) / entry_price * 100
                trades.append({
                    'type': 'short',
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'bars_held': i - entry_bar,
                    'pnl_pct': pnl_pct
                })
                current_position = None
            
            # Check for entries
            if current_position is None:
                if start_long[i]:
                    current_position = 'long'
                    entry_price = close[i]
                    entry_bar = i
                elif start_short[i]:
                    current_position = 'short'
                    entry_price = close[i]
                    entry_bar = i
        
        return pd.DataFrame(trades) if trades else pd.DataFrame()
    
    def _calculate_metrics(self, trades_df: pd.DataFrame, initial_capital: float) -> Dict:
        """Calculate performance metrics"""
        
        if trades_df.empty:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'total_return': 0,
                'final_equity': initial_capital
            }
        
        wins = trades_df[trades_df['pnl_pct'] > 0]
        losses = trades_df[trades_df['pnl_pct'] < 0]
        
        win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0
        
        total_wins = wins['pnl_pct'].sum() if len(wins) > 0 else 0
        total_losses = abs(losses['pnl_pct'].sum()) if len(losses) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        avg_win = wins['pnl_pct'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl_pct'].mean() if len(losses) > 0 else 0
        
        # Calculate equity curve and max drawdown
        equity = initial_capital
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
        
        total_return = (equity - initial_capital) / initial_capital * 100
        
        # Sharpe ratio (simplified)
        returns = trades_df['pnl_pct'].values
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if len(returns) > 1 else 0
        
        return {
            'total_trades': len(trades_df),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': win_rate * 100,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'total_return': total_return,
            'final_equity': equity
        }
    
    def print_results(self, backtest_results: Dict):
        """Print formatted backtest results"""
        
        metrics = backtest_results['metrics']
        trades_df = backtest_results['trades']
        
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*70}\n")
        
        print(f"📊 OVERALL PERFORMANCE:")
        print(f"  Total Trades:      {metrics['total_trades']}")
        print(f"  Winning Trades:    {metrics['winning_trades']}")
        print(f"  Losing Trades:     {metrics['losing_trades']}")
        print(f"  Win Rate:          {metrics['win_rate']:.2f}%")
        print(f"  Profit Factor:     {metrics['profit_factor']:.2f}")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:      {metrics['max_drawdown']:.2f}%")
        print(f"  Total Return:      {metrics['total_return']:.2f}%")
        print(f"  Final Equity:      ${metrics['final_equity']:.2f}")
        
        print(f"\n📈 AVERAGE TRADE:")
        print(f"  Avg Win:           {metrics['avg_win']:.2f}%")
        print(f"  Avg Loss:          {metrics['avg_loss']:.2f}%")
        print(f"  Avg Win/Loss:      {metrics['avg_win']/abs(metrics['avg_loss']):.2f}x" if metrics['avg_loss'] != 0 else "  Avg Win/Loss:      N/A")
        
        if not trades_df.empty:
            print(f"\n🎯 LAST 10 TRADES:")
            for idx, trade in trades_df.tail(10).iterrows():
                result = "✅ WIN" if trade['pnl_pct'] > 0 else "❌ LOSS"
                print(f"  {trade['type'].upper():5s} | {result} | "
                      f"Entry: {trade['entry_price']:.2f} → Exit: {trade['exit_price']:.2f} | "
                      f"P&L: {trade['pnl_pct']:+.2f}% | Held: {trade['bars_held']} bars")


def verify_system_logic():
    """Verify system components work correctly"""
    
    print(f"\n{'='*70}")
    print(f"SYSTEM LOGIC VERIFICATION")
    print(f"{'='*70}\n")
    
    # Test 1: Simple trending data
    print("TEST 1: Uptrend Detection")
    print("-" * 70)
    
    n = 500
    np.random.seed(123)
    
    # Strong uptrend
    trend_up = np.linspace(100, 150, n)
    noise = np.random.randn(n) * 1
    close = trend_up + noise
    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    
    settings = TradingSettings(
        neighbors_count=5,
        max_bars_back=300,
        use_kernel_filter=True,
        use_volatility_filter=True,
        use_regime_filter=True,
        enable_reentry=True,
        reentry_window_start=3,
        reentry_window_end=8
    )
    
    system = LorentzianTradingSystem(settings)
    backtester = Backtester(system)
    
    results = backtester.run_backtest(high, low, close)
    backtester.print_results(results)
    
    # Test 2: Downtrend
    print(f"\n\nTEST 2: Downtrend Detection")
    print("-" * 70)
    
    trend_down = np.linspace(150, 100, n)
    close = trend_down + noise
    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    
    results = backtester.run_backtest(high, low, close)
    backtester.print_results(results)
    
    # Test 3: Choppy sideways
    print(f"\n\nTEST 3: Sideways/Choppy Market")
    print("-" * 70)
    
    close = 125 + np.random.randn(n) * 5
    high = close + np.abs(np.random.randn(n) * 1)
    low = close - np.abs(np.random.randn(n) * 1)
    
    results = backtester.run_backtest(high, low, close)
    backtester.print_results(results)


if __name__ == "__main__":
    verify_system_logic()
    
    print(f"\n\n{'='*70}")
    print(f"✅ VERIFICATION COMPLETE")
    print(f"{'='*70}\n")