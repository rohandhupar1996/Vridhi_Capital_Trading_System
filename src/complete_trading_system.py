"""
COMPLETE BANKNIFTY TRADING SYSTEM
Lorentzian Classification + Volume Node Exits + AlgoTest Integration
"""

import time
import requests
from src.signals.lorentzian_system import LorentzianSignalGenerator
from src.volume.volume_nodes import VolumeNodeDetector


class TradingSystem:
    def __init__(self, algotest_url, db_path="data/banknifty_data.db"):
        """
        Initialize complete trading system
        
        Parameters:
        -----------
        algotest_url : str
            AlgoTest API base URL
        db_path : str
            Path to SQLite database
        """
        self.algotest_url = algotest_url
        
        # Initialize components
        self.signal_generator = LorentzianSignalGenerator(db_path)
        self.volume_detector = VolumeNodeDetector(
            n_rows=100,
            detection_percent=0.09,
            lookback=360
        )
        
        # Trade state
        self.in_trade = False
        self.entry_price = 0
        self.entry_direction = 0  # 1=long, -1=short
        self.target_price = 0
        self.stop_loss = 0
        self.volume_node_target = None
        
        print("✅ Trading System Initialized")
    
    def send_to_algotest(self, action, direction=None, entry=None, target=None, sl=None, exit_price=None, reason=None):
        """
        Send HTTP request to AlgoTest
        
        Parameters:
        -----------
        action : str
            'entry' or 'exit'
        direction : str
            'LONG' or 'SHORT' (for entry)
        entry, target, sl : float
            Prices (for entry)
        exit_price : float
            Exit price (for exit)
        reason : str
            Exit reason (for exit)
        """
        try:
            if action == 'entry':
                url = f"{self.algotest_url}?action=entry&direction={direction}&entry={entry:.2f}&target={target:.2f}&sl={sl:.2f}"
                print(f"\n📤 SENDING {direction} ENTRY TO ALGOTEST")
                print(f"   Entry:  {entry:.2f}")
                print(f"   Target: {target:.2f}")
                print(f"   SL:     {sl:.2f}")
            
            elif action == 'exit':
                url = f"{self.algotest_url}?action=exit&price={exit_price:.2f}&reason={reason}"
                print(f"\n📤 SENDING EXIT TO ALGOTEST")
                print(f"   Exit Price: {exit_price:.2f}")
                print(f"   Reason: {reason}")
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"   ✅ Success!")
                return True
            else:
                print(f"   ❌ Failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    def process_candle(self, new_candle=None):
        """
        Process new candle - main logic
        
        Parameters:
        -----------
        new_candle : dict, optional
            New candle: {'open', 'high', 'low', 'close', 'volume', 'timestamp'}
        
        Returns:
        --------
        dict: Processing result
        """
        start_time = time.time()
        
        # Step 1: Generate Lorentzian signal
        signal_result = self.signal_generator.generate_signal(new_candle)
        
        signal = signal_result['signal']
        entry_signal = signal_result['entry']
        exit_signal = signal_result['exit']
        exit_reason = signal_result['exit_reason']
        current_price = signal_result['current_price']
        
        # Step 2: Calculate volume nodes
        volume_result = self.volume_detector.calculate(self.signal_generator.df)
        
        # Step 3: Check for exits FIRST
        if self.in_trade:
            should_exit = False
            exit_reason_final = None
            
            # EXIT 1: Default (4 bars held)
            if exit_signal and exit_reason == 'bars_held':
                should_exit = True
                exit_reason_final = 'bars_held'
            
            # EXIT 2: Volume node hit
            if self.volume_node_target:
                if self.entry_direction == 1:  # Long
                    if current_price >= self.volume_node_target:
                        should_exit = True
                        exit_reason_final = 'volume_node'
                elif self.entry_direction == -1:  # Short
                    if current_price <= self.volume_node_target:
                        should_exit = True
                        exit_reason_final = 'volume_node'
            
            # EXIT 3: Repaint (signal disappeared on entry candle)
            if exit_signal and exit_reason == 'repaint':
                should_exit = True
                exit_reason_final = 'repaint'
            
            # Execute exit
            if should_exit:
                self.send_to_algotest(
                    action='exit',
                    exit_price=current_price,
                    reason=exit_reason_final
                )
                
                pnl = (current_price - self.entry_price) * self.entry_direction
                pnl_pct = (pnl / self.entry_price) * 100
                
                print(f"\n💰 TRADE CLOSED")
                print(f"   P&L: {pnl_pct:+.2f}%")
                print(f"   Reason: {exit_reason_final}")
                
                self.in_trade = False
                self.volume_node_target = None
        
        # Step 4: Check for new entry
        if entry_signal and not self.in_trade:
            self.entry_direction = signal
            self.entry_price = current_price
            self.in_trade = True
            
            # Get volume node target
            self.volume_node_target = self.volume_detector.get_exit_target(
                self.entry_direction,
                current_price
            )
            
            # Calculate stop loss (simple: opposite volume node or 1% away)
            if self.entry_direction == 1:  # Long
                # SL = nearest support below or 1% below entry
                sl_node = volume_result.get('nearest_support')
                self.stop_loss = sl_node if sl_node else current_price * 0.99
                self.target_price = self.volume_node_target if self.volume_node_target else current_price * 1.02
            else:  # Short
                # SL = nearest resistance above or 1% above entry
                sl_node = volume_result.get('nearest_resistance')
                self.stop_loss = sl_node if sl_node else current_price * 1.01
                self.target_price = self.volume_node_target if self.volume_node_target else current_price * 0.98
            
            # Send to AlgoTest
            self.send_to_algotest(
                action='entry',
                direction='LONG' if self.entry_direction == 1 else 'SHORT',
                entry=self.entry_price,
                target=self.target_price,
                sl=self.stop_loss
            )
        
        # Calculate total processing time
        process_time = (time.time() - start_time) * 1000  # ms
        
        result = {
            'signal': signal,
            'entry': entry_signal,
            'exit': exit_signal if self.in_trade else False,
            'in_trade': self.in_trade,
            'current_price': current_price,
            'volume_node_target': self.volume_node_target,
            'poc_price': volume_result['poc_price'],
            'process_time_ms': process_time
        }
        
        return result


# ==========================================
# MAIN EXECUTION
# ==========================================

def run_system():
    """Run the complete trading system"""
    print("="*80)
    print("🚀 BANKNIFTY TRADING SYSTEM - STARTING")
    print("="*80)
    
    # Configuration
    ALGOTEST_URL = "https://your-algotest-url.com/api"  # ← UPDATE THIS
    TIMEFRAME = '15min'
    
    # Initialize system
    system = TradingSystem(algotest_url=ALGOTEST_URL)
    
    # Load initial data
    print(f"\n📊 Loading historical data ({TIMEFRAME})...")
    system.signal_generator.load_data(timeframe=TIMEFRAME, n_bars=2000)
    
    print("\n✅ System ready!")
    print("\n🔄 Processing last 50 candles (simulation)...")
    print("-" * 80)
    
    # Simulate processing last 50 candles
    df = system.signal_generator.df
    
    for i in range(len(df) - 50, len(df)):
        # Reset to this point in history
        system.signal_generator.df = df.iloc[:i+1].copy()
        
        # Process candle
        result = system.process_candle()
        
        # Print status every 10 candles or on signal
        if i % 10 == 0 or result['entry'] or result['exit']:
            timestamp = df.iloc[i]['timestamp']
            price = result['current_price']
            
            status = ""
            if result['entry']:
                status = f"{'🟢 LONG' if result['signal'] == 1 else '🔴 SHORT'} ENTRY"
            elif result['exit']:
                status = "🚪 EXIT"
            else:
                status = f"{'📊 IN TRADE' if result['in_trade'] else '⏸️  WAITING'}"
            
            print(f"{timestamp} | {price:>8.2f} | {status} | {result['process_time_ms']:.1f}ms")
    
    print("-" * 80)
    print("\n✅ Simulation complete!")
    print("\n📌 NEXT STEPS:")
    print("   1. Update ALGOTEST_URL with your actual API endpoint")
    print("   2. Connect Zerodha WebSocket for live data")
    print("   3. Run during market hours (9:15 AM - 3:30 PM)")


if __name__ == "__main__":
    run_system()