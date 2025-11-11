"""
Performance Metrics Calculator
All backtest metrics in one place
"""

import numpy as np
import pandas as pd
from typing import Dict, List
from exit_strategies import Trade


class MetricsCalculator:
    """Calculate all performance metrics"""
    
    @staticmethod
    def calculate_all_metrics(trades: List[Trade], initial_capital: float) -> Dict:
        """
        Calculate comprehensive performance metrics
        
        Returns dict with all metrics
        """
        if not trades:
            return MetricsCalculator._empty_metrics(initial_capital)
        
        # Convert to DataFrame for easier calculations
        trades_df = MetricsCalculator._trades_to_dataframe(trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl_pct'] > 0])
        losing_trades = len(trades_df[trades_df['pnl_pct'] <= 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl_pct = trades_df['pnl_pct'].sum()
        avg_win = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl_pct'] <= 0]['pnl_pct'].mean() if losing_trades > 0 else 0
        
        # Profit factor
        gross_profit = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct'].sum()
        gross_loss = abs(trades_df[trades_df['pnl_pct'] <= 0]['pnl_pct'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        
        # Equity curve and drawdown
        equity_curve = MetricsCalculator._calculate_equity_curve(trades_df, initial_capital)
        max_drawdown = MetricsCalculator._calculate_max_drawdown(equity_curve)
        
        # Returns
        final_equity = equity_curve[-1] if len(equity_curve) > 0 else initial_capital
        total_return = ((final_equity - initial_capital) / initial_capital) * 100
        
        # Sharpe ratio (assuming 252 trading days)
        returns = trades_df['pnl_pct'].values
        sharpe_ratio = MetricsCalculator._calculate_sharpe(returns)
        
        # MFE/MAE metrics (if available)
        mfe_mae_metrics = MetricsCalculator._calculate_mfe_mae_metrics(trades_df)
        
        # Timeframe breakdown
        tf_metrics = MetricsCalculator._calculate_timeframe_metrics(trades_df)
        
        # Exit reason breakdown
        exit_metrics = MetricsCalculator._calculate_exit_metrics(trades_df)
        
        # Combine all metrics
        metrics = {
            # Basic
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            
            # P&L
            'total_return': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            
            # Drawdown
            'max_drawdown': max_drawdown,
            
            # Equity
            'initial_capital': initial_capital,
            'final_equity': final_equity,
            'equity_curve': equity_curve,
            
            # Trade stats
            'avg_bars_held': trades_df['bars_held'].mean(),
            'max_bars_held': trades_df['bars_held'].max(),
            'min_bars_held': trades_df['bars_held'].min(),
        }
        
        # Add optional metrics
        metrics.update(mfe_mae_metrics)
        metrics.update(tf_metrics)
        metrics.update(exit_metrics)
        
        return metrics
    
    @staticmethod
    def _trades_to_dataframe(trades: List[Trade]) -> pd.DataFrame:
        """Convert list of Trade objects to DataFrame"""
        data = []
        for trade in trades:
            data.append({
                'entry_bar': trade.entry_bar,
                'exit_bar': trade.exit_bar,
                'direction': trade.direction,
                'timeframe': trade.timeframe,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'pnl_pct': trade.pnl_pct,
                'bars_held': trade.bars_held,
                'exit_reason': trade.exit_reason,
                'max_favorable_pct': trade.max_favorable_pct,
                'max_adverse_pct': trade.max_adverse_pct,
            })
        return pd.DataFrame(data)
    
    @staticmethod
    def _calculate_equity_curve(trades_df: pd.DataFrame, initial_capital: float) -> np.ndarray:
        """Calculate equity curve"""
        equity = initial_capital
        equity_curve = [equity]
        
        for pnl_pct in trades_df['pnl_pct'].values:
            equity = equity * (1 + pnl_pct / 100)
            equity_curve.append(equity)
        
        return np.array(equity_curve)
    
    @staticmethod
    def _calculate_max_drawdown(equity_curve: np.ndarray) -> float:
        """Calculate maximum drawdown percentage"""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    @staticmethod
    def _calculate_sharpe(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming ~252 trading days, ~17 trades/day for 15min)
        sharpe = (mean_return - risk_free_rate) / std_return
        sharpe_annualized = sharpe * np.sqrt(252 * 17)
        
        return sharpe_annualized
    
    @staticmethod
    def _calculate_mfe_mae_metrics(trades_df: pd.DataFrame) -> Dict:
        """Calculate MFE/MAE metrics if available"""
        metrics = {}
        
        if 'max_favorable_pct' in trades_df.columns and 'max_adverse_pct' in trades_df.columns:
            metrics['avg_mfe'] = trades_df['max_favorable_pct'].mean()
            metrics['avg_mae'] = trades_df['max_adverse_pct'].mean()
            
            winners = trades_df[trades_df['pnl_pct'] > 0]
            losers = trades_df[trades_df['pnl_pct'] <= 0]
            
            metrics['avg_win_mae'] = winners['max_adverse_pct'].mean() if len(winners) > 0 else 0
            metrics['avg_loss_mae'] = losers['max_adverse_pct'].mean() if len(losers) > 0 else 0
        
        return metrics
    
    @staticmethod
    def _calculate_timeframe_metrics(trades_df: pd.DataFrame) -> Dict:
        """Calculate metrics per timeframe"""
        metrics = {}
        
        if 'timeframe' in trades_df.columns:
            tf_counts = trades_df['timeframe'].value_counts()
            for tf, count in tf_counts.items():
                metrics[f'trades_{tf}'] = count
        
        return metrics
    
    @staticmethod
    def _calculate_exit_metrics(trades_df: pd.DataFrame) -> Dict:
        """Calculate metrics per exit reason"""
        metrics = {}
        
        if 'exit_reason' in trades_df.columns:
            exit_counts = trades_df['exit_reason'].value_counts()
            for reason, count in exit_counts.items():
                metrics[f'exits_{reason}'] = count
        
        return metrics
    
    @staticmethod
    def _empty_metrics(initial_capital: float) -> Dict:
        """Return empty metrics dict"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_return': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'initial_capital': initial_capital,
            'final_equity': initial_capital,
            'equity_curve': np.array([initial_capital]),
            'avg_bars_held': 0.0,
            'max_bars_held': 0,
            'min_bars_held': 0,
        }
    
    @staticmethod
    def print_metrics(metrics: Dict, config_name: str = ""):
        """Pretty print metrics"""
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS{': ' + config_name if config_name else ''}")
        print(f"{'='*70}\n")
        
        print(f"📊 PERFORMANCE:")
        print(f"  Total Trades:      {metrics['total_trades']}")
        print(f"  Winning Trades:    {metrics['winning_trades']}")
        print(f"  Losing Trades:     {metrics['losing_trades']}")
        print(f"  Win Rate:          {metrics['win_rate']:.2f}%")
        print(f"  Profit Factor:     {metrics['profit_factor']:.2f}")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
        
        print(f"\n💰 RETURNS:")
        print(f"  Total Return:      {metrics['total_return']:.2f}%")
        print(f"  Max Drawdown:      {metrics['max_drawdown']:.2f}%")
        print(f"  Initial Capital:   ${metrics['initial_capital']:,.0f}")
        print(f"  Final Equity:      ${metrics['final_equity']:,.0f}")
        
        print(f"\n📈 AVERAGE TRADE:")
        print(f"  Avg Win:           {metrics['avg_win']:.2f}%")
        print(f"  Avg Loss:          {metrics['avg_loss']:.2f}%")
        if metrics['avg_loss'] != 0:
            print(f"  Avg Win/Loss:      {metrics['avg_win']/abs(metrics['avg_loss']):.2f}x")
        
        print(f"\n⏱️  TRADE DURATION:")
        print(f"  Avg Bars Held:     {metrics['avg_bars_held']:.1f}")
        print(f"  Max Bars Held:     {metrics['max_bars_held']}")
        print(f"  Min Bars Held:     {metrics['min_bars_held']}")
        
        # MFE/MAE if available
        if 'avg_mfe' in metrics:
            print(f"\n💥 DRAWDOWN ANALYSIS:")
            print(f"  Avg MFE (Max Favorable):  {metrics['avg_mfe']:.2f}%")
            print(f"  Avg MAE (Max Adverse):    {metrics['avg_mae']:.2f}%")
            if 'avg_win_mae' in metrics:
                print(f"  Avg MAE on Winners:       {metrics['avg_win_mae']:.2f}%")
                print(f"  Avg MAE on Losers:        {metrics['avg_loss_mae']:.2f}%")
        
        # Timeframe breakdown if available
        tf_keys = [k for k in metrics.keys() if k.startswith('trades_')]
        if tf_keys:
            print(f"\n🕐 TIMEFRAME BREAKDOWN:")
            for key in tf_keys:
                tf = key.replace('trades_', '')
                print(f"  {tf:8s} trades:     {metrics[key]}")
        
        # Exit reason breakdown if available
        exit_keys = [k for k in metrics.keys() if k.startswith('exits_')]
        if exit_keys:
            print(f"\n🚪 EXIT BREAKDOWN:")
            for key in exit_keys:
                reason = key.replace('exits_', '')
                print(f"  {reason:15s}:    {metrics[key]}")
        
        print(f"\n{'='*70}\n")


# ==== TESTING ====

if __name__ == "__main__":
    from datetime import datetime
    
    print("\n" + "="*70)
    print("TESTING METRICS CALCULATOR")
    print("="*70)
    
    # Create sample trades
    trades = [
        Trade(100, datetime.now(), 50000, 1, '15m', 104, datetime.now(), 50500, '4_bars', 4, 1.0, 1.2, -0.3),
        Trade(110, datetime.now(), 51000, -1, '15m', 112, datetime.now(), 50800, 'volume_node', 2, 0.39, 0.5, -0.1),
        Trade(120, datetime.now(), 50500, 1, '1h', 124, datetime.now(), 50200, '4_bars', 4, -0.59, 0.2, -0.8),
        Trade(130, datetime.now(), 50000, -1, '15m', 134, datetime.now(), 49500, '4_bars', 4, 1.0, 1.1, -0.2),
        Trade(140, datetime.now(), 49800, 1, '15m', 144, datetime.now(), 50300, '4_bars', 4, 1.0, 1.3, -0.1),
    ]
    
    # Calculate metrics
    calc = MetricsCalculator()
    metrics = calc.calculate_all_metrics(trades, initial_capital=100000)
    
    # Print results
    calc.print_metrics(metrics, "Sample Backtest")
    
    print("✅ Metrics calculator ready!")