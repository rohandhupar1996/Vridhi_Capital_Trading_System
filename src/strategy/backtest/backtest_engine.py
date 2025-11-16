"""
Clean Single Timeframe Backtest Engine
15min only, DEFAULT exit mode (4 bars)
"""

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ExitMode(Enum):
    DEFAULT = "default"


@dataclass
class BacktestConfig:
    db_path: str = "data/banknifty_data.db"
    timeframe: str = '15min'
    lookback_bars: int = 3000
    
    neighbors_count: int = 5
    max_bars_back: int = 3000
    use_kernel_filter: bool = True
    use_volatility_filter: bool = True
    use_regime_filter: bool = True
    enable_reentry: bool = True
    
    default_exit_bars: int = 4
    track_drawdown: bool = True
    
    initial_capital: float = 100000.0
    start_bar: int = 200
    save_trades: bool = True
    verbose: bool = True


@dataclass
class Trade:
    entry_bar: int
    entry_time: datetime
    entry_price: float
    direction: int
    
    exit_bar: Optional[int] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    bars_held: int = 0
    
    pnl_pct: float = 0.0
    max_favorable_pct: float = 0.0
    max_adverse_pct: float = 0.0


class ExitStrategyManager:
    def __init__(self, config: BacktestConfig):
        self.config = config
    
    def check_exit(self, trade: Trade, current_bar: int) -> Tuple[bool, str]:
        """Check if trade should exit after N bars"""
        bars_held = current_bar - trade.entry_bar
        if bars_held >= self.config.default_exit_bars:
            return True, f"{self.config.default_exit_bars}_bars"
        return False, ""


class MetricsCalculator:
    @staticmethod
    def calculate_all_metrics(trades: List[Trade], initial_capital: float) -> Dict:
        if len(trades) == 0:
            return MetricsCalculator._empty_metrics(initial_capital)
        
        df = pd.DataFrame([{
            'pnl_pct': t.pnl_pct,
            'direction': 'LONG' if t.direction == 1 else 'SHORT',
            'exit_reason': t.exit_reason,
            'bars_held': t.bars_held,
            'mfe': t.max_favorable_pct,
            'mae': t.max_adverse_pct
        } for t in trades])
        
        total_trades = len(df)
        winners = df[df['pnl_pct'] > 0]
        losers = df[df['pnl_pct'] <= 0]
        
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
        total_win = winners['pnl_pct'].sum() if len(winners) > 0 else 0
        total_loss = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
        profit_factor = (total_win / total_loss) if total_loss > 0 else float('inf')
        
        total_return = df['pnl_pct'].sum()
        avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
        avg_loss = losers['pnl_pct'].mean() if len(losers) > 0 else 0
        
        # Equity curve
        equity_curve = [initial_capital]
        for pnl in df['pnl_pct']:
            equity_curve.append(equity_curve[-1] * (1 + pnl/100))
        
        # Drawdown
        max_equity = initial_capital
        max_drawdown = 0
        drawdown_duration = 0
        current_dd_duration = 0
        max_dd_duration = 0
        
        for eq in equity_curve:
            if eq > max_equity:
                max_equity = eq
                if current_dd_duration > max_dd_duration:
                    max_dd_duration = current_dd_duration
                current_dd_duration = 0
            else:
                current_dd_duration += 1
            
            drawdown = (max_equity - eq) / max_equity * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        final_equity = equity_curve[-1]
        returns = df['pnl_pct'].values
        sharpe_ratio = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
        
        # Streaks
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for pnl in df['pnl_pct']:
            if pnl > 0:
                current_streak = current_streak + 1 if current_streak > 0 else 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                current_streak = current_streak - 1 if current_streak < 0 else -1
                max_loss_streak = max(max_loss_streak, abs(current_streak))
        
        # MFE/MAE stats
        avg_mfe = df['mfe'].mean()
        avg_mae = df['mae'].mean()
        avg_win_mfe = winners['mfe'].mean() if len(winners) > 0 else 0
        avg_win_mae = winners['mae'].mean() if len(winners) > 0 else 0
        avg_loss_mfe = losers['mfe'].mean() if len(losers) > 0 else 0
        avg_loss_mae = losers['mae'].mean() if len(losers) > 0 else 0
        
        # Best/Worst trades
        best_trade = df['pnl_pct'].max()
        worst_trade = df['pnl_pct'].min()
        
        # Long/Short breakdown
        longs = df[df['direction'] == 'LONG']
        shorts = df[df['direction'] == 'SHORT']
        
        long_win_rate = (len(longs[longs['pnl_pct'] > 0]) / len(longs) * 100) if len(longs) > 0 else 0
        short_win_rate = (len(shorts[shorts['pnl_pct'] > 0]) / len(shorts) * 100) if len(shorts) > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'max_dd_duration': max_dd_duration,
            'final_equity': final_equity,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe_ratio': sharpe_ratio,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'avg_mfe': avg_mfe,
            'avg_mae': avg_mae,
            'avg_win_mfe': avg_win_mfe,
            'avg_win_mae': avg_win_mae,
            'avg_loss_mfe': avg_loss_mfe,
            'avg_loss_mae': avg_loss_mae,
            'total_longs': len(longs),
            'total_shorts': len(shorts),
            'long_win_rate': long_win_rate,
            'short_win_rate': short_win_rate,
            'equity_curve': equity_curve
        }
    
    @staticmethod
    def _empty_metrics(initial_capital: float) -> Dict:
        return {
            'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
            'win_rate': 0, 'profit_factor': 0, 'total_return': 0,
            'max_drawdown': 0, 'max_dd_duration': 0, 'final_equity': initial_capital,
            'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0,
            'best_trade': 0, 'worst_trade': 0,
            'max_win_streak': 0, 'max_loss_streak': 0,
            'avg_mfe': 0, 'avg_mae': 0,
            'avg_win_mfe': 0, 'avg_win_mae': 0,
            'avg_loss_mfe': 0, 'avg_loss_mae': 0,
            'total_longs': 0, 'total_shorts': 0,
            'long_win_rate': 0, 'short_win_rate': 0,
            'equity_curve': [initial_capital]
        }


class MasterBacktester:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.exit_manager = ExitStrategyManager(config)
        self.metrics_calc = MetricsCalculator()
        
        self.system = None
        self.data = None
        self.current_trade: Optional[Trade] = None
        self.trades: List[Trade] = []
    
    def load_data(self) -> bool:
        try:
            conn = sqlite3.connect(self.config.db_path)
            
            self.data = pd.read_sql_query(f"""
                SELECT timestamp, open, high, low, close, volume
                FROM ohlcv WHERE timeframe = '{self.config.timeframe}'
                ORDER BY timestamp DESC LIMIT {self.config.lookback_bars}
            """, conn)
            
            self.data = self.data.iloc[::-1].reset_index(drop=True)
            self.data['timestamp'] = pd.to_datetime(
                self.data['timestamp'], unit='s'
            ).dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
            
            conn.close()
            
            if self.config.verbose:
                print(f"\n✅ Data loaded: {len(self.data)} bars\n")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def initialize_system(self):
        import sys
        from pathlib import Path
        
        core_path = Path(__file__).parent.parent / 'core'
        if str(core_path.parent) not in sys.path:
            sys.path.insert(0, str(core_path.parent))
        
        from core.trading_system import TradingSettings, LorentzianTradingSystem
        
        ml_settings = TradingSettings(
            neighbors_count=self.config.neighbors_count,
            max_bars_back=self.config.max_bars_back,
            use_kernel_filter=self.config.use_kernel_filter,
            use_volatility_filter=self.config.use_volatility_filter,
            use_regime_filter=self.config.use_regime_filter,
            enable_reentry=self.config.enable_reentry
        )
        
        self.system = LorentzianTradingSystem(ml_settings)
    
    def run(self) -> Dict:
        print(f"{'='*70}")
        print(f"SINGLE TIMEFRAME BACKTEST - 15MIN")
        print(f"{'='*70}\n")
        
        if not self.load_data():
            return None
        
        self.initialize_system()
        
        results = self.system.generate_signals(
            self.data['high'].values,
            self.data['low'].values,
            self.data['close'].values,
            start_bar=self.config.start_bar
        )
        
        for bar in range(self.config.start_bar, len(self.data)):
            if self.current_trade and self.config.track_drawdown:
                self._update_trade_drawdown(bar)
            
            if self.current_trade:
                should_exit, reason = self.exit_manager.check_exit(self.current_trade, bar)
                if should_exit:
                    self._exit_trade(bar, reason)
                    continue
            
            if not self.current_trade:
                if results['start_long'][bar]:
                    self._enter_trade(bar, 1)
                elif results['start_short'][bar]:
                    self._enter_trade(bar, -1)
        
        if self.current_trade:
            self._exit_trade(len(self.data)-1, "end_of_data")
        
        metrics = self.metrics_calc.calculate_all_metrics(self.trades, self.config.initial_capital)
        
        if self.config.verbose:
            self._print_results(metrics)
        
        if self.config.save_trades and len(self.trades) > 0:
            self._save_trades()
        
        return {'trades': self.trades, 'metrics': metrics, 'config': self.config}
    
    def _enter_trade(self, bar: int, direction: int):
        h = self.data.loc[bar, 'high']
        l = self.data.loc[bar, 'low']
        c = self.data.loc[bar, 'close']
        entry_price = (h + l + c) / 3
        
        self.current_trade = Trade(
            entry_bar=bar,
            entry_time=self.data.loc[bar, 'timestamp'],
            entry_price=entry_price,#self.data.loc[bar, 'close'],
            direction=direction
        )
    
    def _exit_trade(self, bar: int, reason: str):
        if not self.current_trade:
            return
        
        self.current_trade.exit_bar = bar
        self.current_trade.exit_time = self.data.loc[bar, 'timestamp']
        self.current_trade.exit_price = self.data.loc[bar, 'close']
        self.current_trade.exit_reason = reason
        self.current_trade.bars_held = bar - self.current_trade.entry_bar
        
        if self.current_trade.direction == 1:
            pnl = (self.current_trade.exit_price - self.current_trade.entry_price) / self.current_trade.entry_price * 100
        else:
            pnl = (self.current_trade.entry_price - self.current_trade.exit_price) / self.current_trade.entry_price * 100
        
        self.current_trade.pnl_pct = pnl
        
        if self.config.track_drawdown:
            self._update_trade_drawdown(bar)
        
        self.trades.append(self.current_trade)
        self.current_trade = None
    
    def _update_trade_drawdown(self, bar: int):
        if not self.current_trade:
            return
        
        current_price = self.data.loc[bar, 'close']
        entry_price = self.current_trade.entry_price
        
        if self.current_trade.direction == 1:
            favorable_pct = (current_price - entry_price) / entry_price * 100
            adverse_pct = (entry_price - current_price) / entry_price * 100
        else:
            favorable_pct = (entry_price - current_price) / entry_price * 100
            adverse_pct = (current_price - entry_price) / entry_price * 100
        
        self.current_trade.max_favorable_pct = max(self.current_trade.max_favorable_pct, favorable_pct)
        self.current_trade.max_adverse_pct = max(self.current_trade.max_adverse_pct, adverse_pct)
    
    def _print_results(self, metrics: Dict):
        print(f"\n{'='*70}")
        print("BACKTEST RESULTS")
        print(f"{'='*70}\n")
        
        print(f"📊 PERFORMANCE:")
        print(f"  Total Trades:      {metrics['total_trades']}")
        print(f"  Win Rate:          {metrics['win_rate']:.2f}%")
        print(f"  Profit Factor:     {metrics['profit_factor']:.2f}")
        print(f"  Total Return:      {metrics['total_return']:.2f}%")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
        
        print(f"\n💰 RETURNS:")
        print(f"  Avg Win:           {metrics['avg_win']:.2f}%")
        print(f"  Avg Loss:          {metrics['avg_loss']:.2f}%")
        print(f"  Best Trade:        {metrics['best_trade']:.2f}%")
        print(f"  Worst Trade:       {metrics['worst_trade']:.2f}%")
        print(f"  Final Equity:      ${metrics['final_equity']:,.2f}")
        
        print(f"\n📉 DRAWDOWN:")
        print(f"  Max Drawdown:      {metrics['max_drawdown']:.2f}%")
        print(f"  DD Duration:       {metrics['max_dd_duration']} trades")
        
        print(f"\n🔥 STREAKS:")
        print(f"  Max Win Streak:    {metrics['max_win_streak']}")
        print(f"  Max Loss Streak:   {metrics['max_loss_streak']}")
        
        print(f"\n💥 MFE/MAE ANALYSIS:")
        print(f"  Avg MFE:           {metrics['avg_mfe']:.2f}%")
        print(f"  Avg MAE:           {metrics['avg_mae']:.2f}%")
        print(f"  Winners MFE:       {metrics['avg_win_mfe']:.2f}%")
        print(f"  Winners MAE:       {metrics['avg_win_mae']:.2f}%")
        print(f"  Losers MFE:        {metrics['avg_loss_mfe']:.2f}%")
        print(f"  Losers MAE:        {metrics['avg_loss_mae']:.2f}%")
        
        print(f"\n📈 DIRECTION BREAKDOWN:")
        print(f"  Total LONG:        {metrics['total_longs']} ({metrics['long_win_rate']:.1f}% win)")
        print(f"  Total SHORT:       {metrics['total_shorts']} ({metrics['short_win_rate']:.1f}% win)\n")
    
    def _save_trades(self):
        trade_data = []
        for t in self.trades:
            trade_data.append({
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'direction': 'LONG' if t.direction == 1 else 'SHORT',
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'pnl_pct': t.pnl_pct,
                'bars_held': t.bars_held,
                'exit_reason': t.exit_reason,
                'max_favorable_pct': t.max_favorable_pct,
                'max_adverse_pct': t.max_adverse_pct
            })
        
        df = pd.DataFrame(trade_data)
        df.to_csv('trades_Single_TF_default.csv', index=False)
        print(f"💾 Saved: trades_Single_TF_default.csv\n")