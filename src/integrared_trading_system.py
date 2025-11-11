"""
Integrated Trading System with Order Management
Connects signals → orders → logging
"""

from datetime import datetime
from order_management_system import OrderManager
import json
import logging

class IntegratedTradingSystem:
    def __init__(self, kite):
        self.kite = kite
        self.order_manager = OrderManager(kite)
        
        # State tracking
        self.in_trade = False
        self.position_type = None  # LONG/SHORT
        self.entry_timeframe = None  # 15min/1hour
        self.entry_time = None
        self.bars_held = 0
        
        # Daily tracking
        self.daily_trades = []
        self.daily_pnl = 0
        
    def on_tick(self, ws, ticks):
        """Main tick handler"""
        for tick in ticks:
            # Update futures price for ATM calculation
            if 'FUT' in tick.get('instrument_token', ''):
                self.order_manager.update_futures_price(tick)
            
            # Process for signals
            self.process_tick(tick)
    
    def process_tick(self, tick):
        """Process tick for signal generation"""
        # Update candles and calculate signals
        signal_15min = self.calculate_signal_15min(tick)
        signal_1hour = self.calculate_signal_1hour(tick)
        
        # Entry logic
        if not self.in_trade:
            if signal_15min > 5:
                self.enter_trade('LONG', '15min')
            elif signal_15min < -5:
                self.enter_trade('SHORT', '15min')
            elif signal_1hour > 5:
                self.enter_trade('LONG', '1hour')
            elif signal_1hour < -5:
                self.enter_trade('SHORT', '1hour')
        
        # Exit logic (bars held)
        else:
            self.check_exit_conditions()
    
    def enter_trade(self, direction: str, timeframe: str):
        """Execute entry with order management"""
        print(f"\n{'='*60}")
        print(f"📍 Signal: {direction} on {timeframe} @ {datetime.now().strftime('%H:%M:%S')}")
        
        # Place orders through order manager
        if direction == 'LONG':
            success = self.order_manager.place_long_orders()
        else:
            success = self.order_manager.place_short_orders()
        
        if success:
            self.in_trade = True
            self.position_type = direction
            self.entry_timeframe = timeframe
            self.entry_time = datetime.now()
            self.bars_held = 0
            
            # Log trade entry
            self.log_trade_entry(direction, timeframe)
            
            # Save state
            self.save_state()
            
            print(f"✅ {direction} position active")
        else:
            print(f"❌ Failed to enter {direction}")
    
    def check_exit_conditions(self):
        """Check if exit conditions met"""
        # Exit after 4 bars
        if self.bars_held >= 4:
            self.exit_trade('bars_completed')
        
        # Could add other exit conditions (stop loss, target, etc)
    
    def on_candle_close(self, timeframe: str):
        """Handle candle close events"""
        if self.in_trade and self.entry_timeframe == timeframe:
            self.bars_held += 1
            print(f"📊 Bars held: {self.bars_held}/4")
            
            if self.bars_held >= 4:
                self.exit_trade('bars_completed')
    
    def exit_trade(self, reason: str):
        """Execute exit with order management"""
        print(f"\n🏁 Exiting {self.position_type} - Reason: {reason}")
        
        # Get P&L before exit
        pnl = self.calculate_pnl()
        
        # Execute exit orders
        self.order_manager.exit_all_positions()
        
        # Log trade exit
        self.log_trade_exit(pnl, reason)
        
        # Reset state
        self.in_trade = False
        self.position_type = None
        self.entry_timeframe = None
        self.bars_held = 0
        
        # Update daily P&L
        self.daily_pnl += pnl
        
        # Save state
        self.save_state()
        
        print(f"💰 Trade P&L: {pnl:+.2f}")
        print(f"📈 Daily P&L: {self.daily_pnl:+.2f}")
    
    def calculate_pnl(self):
        """Calculate current P&L from positions"""
        try:
            positions = self.kite.positions()['net']
            total_pnl = 0
            
            for pos in positions:
                if 'BANKNIFTY' in pos['tradingsymbol']:
                    pnl = pos['pnl']
                    total_pnl += pnl
            
            return total_pnl
        except:
            return 0
    
    def log_trade_entry(self, direction: str, timeframe: str):
        """Log trade entry to daily file"""
        trade = {
            'entry_time': datetime.now().isoformat(),
            'direction': direction,
            'timeframe': timeframe,
            'futures_price': self.order_manager.futures_ltp,
            'atm_strike': self.order_manager.atm_strike
        }
        
        self.daily_trades.append(trade)
        self.save_daily_log()
    
    def log_trade_exit(self, pnl: float, reason: str):
        """Log trade exit"""
        if self.daily_trades:
            self.daily_trades[-1].update({
                'exit_time': datetime.now().isoformat(),
                'exit_reason': reason,
                'pnl': pnl,
                'bars_held': self.bars_held
            })
            
            self.save_daily_log()
    
    def save_daily_log(self):
        """Save daily trades to JSON"""
        date = datetime.now().strftime('%Y-%m-%d')
        filename = f"logs/trades_{date}.json"
        
        log_data = {
            'date': date,
            'trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'total_trades': len(self.daily_trades),
            'winning_trades': sum(1 for t in self.daily_trades if t.get('pnl', 0) > 0),
            'losing_trades': sum(1 for t in self.daily_trades if t.get('pnl', 0) < 0)
        }
        
        with open(filename, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    def save_state(self):
        """Save current state for recovery"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'in_trade': self.in_trade,
            'position_type': self.position_type,
            'entry_timeframe': self.entry_timeframe,
            'bars_held': self.bars_held,
            'daily_pnl': self.daily_pnl,
            'futures_ltp': self.order_manager.futures_ltp,
            'atm_strike': self.order_manager.atm_strike
        }
        
        with open('data/state/trading_state.json', 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load saved state on restart"""
        try:
            with open('data/state/trading_state.json', 'r') as f:
                state = json.load(f)
            
            self.in_trade = state['in_trade']
            self.position_type = state['position_type']
            self.entry_timeframe = state['entry_timeframe']
            self.bars_held = state['bars_held']
            self.daily_pnl = state['daily_pnl']
            
            print(f"📂 State loaded: In trade={self.in_trade}, Bars={self.bars_held}")
            
            # Verify with Zerodha
            self.verify_position_with_zerodha()
            
        except FileNotFoundError:
            print("📂 No saved state, starting fresh")
    
    def verify_position_with_zerodha(self):
        """Verify our state matches Zerodha"""
        positions = self.kite.positions()['net']
        has_position = any(
            'BANKNIFTY' in p['tradingsymbol'] and p['quantity'] != 0 
            for p in positions
        )
        
        if has_position and not self.in_trade:
            print("⚠️ Zerodha has position but we don't! Syncing...")
            # Need to figure out position type from actual positions
            
        elif not has_position and self.in_trade:
            print("⚠️ We think we're in trade but Zerodha says no! Resetting...")
            self.in_trade = False
            self.save_state()


# Daily log output example:
"""
logs/trades_2024-11-08.json:
{
  "date": "2024-11-08",
  "trades": [
    {
      "entry_time": "2024-11-08T09:45:00",
      "direction": "LONG",
      "timeframe": "15min",
      "futures_price": 51250.50,
      "atm_strike": 51300,
      "exit_time": "2024-11-08T10:45:00",
      "exit_reason": "bars_completed",
      "pnl": 1250.00,
      "bars_held": 4
    }
  ],
  "daily_pnl": 1250.00,
  "total_trades": 1,
  "winning_trades": 1,
  "losing_trades": 0
}
"""