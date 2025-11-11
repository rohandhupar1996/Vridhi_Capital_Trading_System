"""
Backtest & Verification Module - NO Volume Exits
Tests complete system with drawdown analysis
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
        print(f"BACKTESTING ON {len(close)} BARS - NO VOLUME EXITS")
        print(f"{'='*70}\n")
        
        # Generate signals
        results = self.system.generate_signals(high, low, close, start_bar=100)
        
        # Calculate trades and P&L with drawdown tracking
        trades_data = self._calculate_trades_with_drawdown(
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
    
    def _calculate_trades_with_drawdown(self, close: np.ndarray, high: np.ndarray, low: np.ndarray,
                         start_long: np.ndarray, start_short: np.ndarray,
                         end_long: np.ndarray, end_short: np.ndarray) -> pd.DataFrame:
        """Calculate all trades with entry/exit prices and intra-trade drawdown"""
        
        trades = []
        current_position = None
        entry_price = 0
        entry_bar = 0
        max_favorable = 0
        max_adverse = 0
        
        for i in range(len(close)):
            # Update drawdown for active trade
            if current_position == 'long':
                favorable = (high[i] - entry_price) / entry_price * 100
                max_favorable = max(max_favorable, favorable)
                adverse = (low[i] - entry_price) / entry_price * 100
                max_adverse = min(max_adverse, adverse)
                
            elif current_position == 'short':
                favorable = (entry_price - low[i]) / entry_price * 100
                max_favorable = max(max_favorable, favorable)
                adverse = (entry_price - high[i]) / entry_price * 100
                max_adverse = min(max_adverse, adverse)
            
            # Check for exits first - USE CLOSE PRICE
            if current_position == 'long' and end_long[i]:
                exit_price = close[i]  # Changed from open to close
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                trades.append({
                    'type': 'long',
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'bars_held': i - entry_bar,
                    'pnl_pct': pnl_pct,
                    'max_favorable_pct': max_favorable,
                    'max_adverse_pct': max_adverse,
                    'exit_reason': '4_bars'
                })
                current_position = None
                max_favorable = 0
                max_adverse = 0
            
            elif current_position == 'short' and end_short[i]:
                exit_price = close[i]  # Changed from open to close
                pnl_pct = (entry_price - exit_price) / entry_price * 100
                trades.append({
                    'type': 'short',
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'bars_held': i - entry_bar,
                    'pnl_pct': pnl_pct,
                    'max_favorable_pct': max_favorable,
                    'max_adverse_pct': max_adverse,
                    'exit_reason': '4_bars'
                })
                current_position = None
                max_favorable = 0
                max_adverse = 0
            
            # Check for entries - ENTRY ALWAYS AT CLOSE
            if current_position is None:
                if start_long[i]:
                    current_position = 'long'
                    entry_price = close[i]
                    entry_bar = i
                    max_favorable = 0
                    max_adverse = 0
                elif start_short[i]:
                    current_position = 'short'
                    entry_price = close[i]
                    entry_bar = i
                    max_favorable = 0
                    max_adverse = 0
        
        return pd.DataFrame(trades) if trades else pd.DataFrame()
    
    def _calculate_metrics(self, trades_df: pd.DataFrame, initial_capital: float) -> Dict:
        """Calculate performance metrics including detailed drawdown"""
        
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
                'final_equity': initial_capital,
                'avg_mfe': 0,
                'avg_mae': 0,
                'avg_win_mae': 0,
                'avg_loss_mae': 0
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
        
        # Drawdown analysis
        avg_mfe = trades_df['max_favorable_pct'].mean()
        avg_mae = abs(trades_df['max_adverse_pct'].mean())
        
        # MAE for winners vs losers
        avg_win_mae = abs(wins['max_adverse_pct'].mean()) if len(wins) > 0 else 0
        avg_loss_mae = abs(losses['max_adverse_pct'].mean()) if len(losses) > 0 else 0
        
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
            'final_equity': equity,
            'avg_mfe': avg_mfe,
            'avg_mae': avg_mae,
            'avg_win_mae': avg_win_mae,
            'avg_loss_mae': avg_loss_mae
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
        print(f"  Final Equity:      ${metrics['final_equity']:,.2f}")
        
        print(f"\n📈 AVERAGE TRADE:")
        print(f"  Avg Win:           {metrics['avg_win']:.2f}%")
        print(f"  Avg Loss:          {metrics['avg_loss']:.2f}%")
        print(f"  Avg Win/Loss:      {metrics['avg_win']/abs(metrics['avg_loss']):.2f}x" if metrics['avg_loss'] != 0 else "  Avg Win/Loss:      N/A")
        
        print(f"\n💥 DRAWDOWN ANALYSIS:")
        print(f"  Avg MFE (Max Favorable):  {metrics['avg_mfe']:.2f}%")
        print(f"  Avg MAE (Max Adverse):    {metrics['avg_mae']:.2f}%")
        print(f"  Avg MAE on Winners:       {metrics['avg_win_mae']:.2f}%")
        print(f"  Avg MAE on Losers:        {metrics['avg_loss_mae']:.2f}%")
        
        if not trades_df.empty:
            print(f"\n🎯 LAST 10 TRADES:")
            for idx, trade in trades_df.tail(10).iterrows():
                result = "✅ WIN" if trade['pnl_pct'] > 0 else "❌ LOSS"
                print(f"  {trade['type'].upper():5s} | {result} | "
                      f"Entry: {trade['entry_price']:.2f} → Exit: {trade['exit_price']:.2f} | "
                      f"P&L: {trade['pnl_pct']:+.2f}% | MFE: {trade['max_favorable_pct']:+.2f}% | "
                      f"MAE: {trade['max_adverse_pct']:+.2f}% | Held: {trade['bars_held']} bars")



if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"BACKTEST MODULE - Ready for use")
    print(f"{'='*70}\n")
    print("Import this module in your test script:")
    print("  from backtest_no_volume import Backtester")