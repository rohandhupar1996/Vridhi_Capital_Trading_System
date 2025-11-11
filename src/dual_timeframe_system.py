"""
COMPLETE BANKNIFTY DUAL TIMEFRAME TRADING SYSTEM
Lorentzian Classification + Volume Node Exits + AlgoTest Integration

ENTRY LOGIC:
1. 15min LONG + 1hour LONG (same candle) → LONG on 1-HOUR (default exit only)
2. 15min LONG alone → LONG on 15-MIN (default OR volume node exit)
3. 15min SHORT → SHORT on 15-MIN (default OR volume node exit)

EXIT LOGIC (All timeframes):
1. REPAINT: Signal disappears on entry candle → EXIT IMMEDIATELY
2. DEFAULT: 4 bars held → EXIT
3. VOLUME NODE: Price crosses node → EXIT (15min only, not for 1hour longs)
"""

import time
import requests
from src.signals.lorentzian_system import LorentzianSignalGenerator
from src.volume.volume_nodes import VolumeNodeDetector


class DualTimeframeTradingSystem:
    def __init__(self, algotest_url, db_path="data/banknifty_data.db"):
        """
        Initialize dual timeframe trading system
        """
        self.algotest_url = algotest_url
        
        # Initialize both timeframes
        self.signal_15min = LorentzianSignalGenerator(db_path)
        self.signal_1hour = LorentzianSignalGenerator(db_path)
        
        # Volume detector (for 15min trades)
        self.volume_detector = VolumeNodeDetector(
            n_rows=100,
            detection_percent=0.09,
            lookback=360
        )
        
        # Trade state
        self.in_trade = False
        self.entry_price = 0
        self.entry_direction = 0  # 1=long, -1=short
        self.trade_timeframe = None  # '15min' or '1hour'
        self.target_price = 0
        self.stop_loss = 0
        self.volume_node_target = None
        
        print("="*80)
        print("✅ DUAL TIMEFRAME TRADING SYSTEM INITIALIZED")
        print("="*80)
        print("\n📊 ENTRY RULES:")
        print("   1. 15min LONG + 1hour LONG (same candle) → LONG on 1-HOUR")
        print("   2. 15min LONG alone → LONG on 15-MIN")
        print("   3. 15min SHORT → SHORT on 15-MIN")
        print("\n🚪 EXIT RULES:")
        print("   → REPAINT: Signal disappears → EXIT immediately (all)")
        print("   → DEFAULT: 4 bars held → EXIT (all)")
        print("   → VOLUME NODE: Price crosses → EXIT (15min only)")
        print("="*80)
    
    def send_to_algotest(self, action, direction=None, entry=None, target=None, 
                        sl=None, exit_price=None, reason=None):
        """Send HTTP request to AlgoTest"""
        try:
            if action == 'entry':
                url = (f"{self.algotest_url}?action=entry&direction={direction}"
                       f"&entry={entry:.2f}&target={target:.2f}&sl={sl:.2f}")
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
    
    def check_both_timeframes_long(self):
        """
        Check if BOTH 15min and 1hour show LONG signal on same candle
        Returns: True if both align
        """
        # Both must have entry signal AND both must be long
        both_entry = (self.signal_15min.in_position and 
                     self.signal_1hour.in_position)
        
        both_long = (self.signal_15min.entry_direction == 1 and 
                    self.signal_1hour.entry_direction == 1)
        
        # Check if they entered on same bar (both just entered)
        both_just_entered = (self.signal_15min.bars_held == 0 and 
                            self.signal_1hour.bars_held == 0)
        
        return both_entry and both_long and both_just_entered
    
    def process_candle(self, new_candle_15min=None, new_candle_1hour=None):
        """
        Process new candles - main logic
        """
        start_time = time.time()
        
        # ==========================================
        # STEP 1: GENERATE SIGNALS ON BOTH TIMEFRAMES
        # ==========================================
        
        result_15min = self.signal_15min.generate_signal(new_candle_15min)
        result_1hour = self.signal_1hour.generate_signal(new_candle_1hour)
        
        signal_15min = result_15min['signal']
        signal_1hour = result_1hour['signal']
        entry_15min = result_15min['entry']
        entry_1hour = result_1hour['entry']
        exit_15min = result_15min['exit']
        exit_1hour = result_1hour['exit']
        
        current_price = result_15min['current_price']
        
        # ==========================================
        # STEP 2: CALCULATE VOLUME NODES (for 15min trades)
        # ==========================================
        
        volume_result = self.volume_detector.calculate(self.signal_15min.df)
        
        # ==========================================
        # STEP 3: CHECK EXITS FIRST (if in trade)
        # ==========================================
        
        if self.in_trade:
            should_exit = False
            exit_reason_final = None
            
            # EXIT LOGIC depends on trade timeframe
            if self.trade_timeframe == '1hour':
                # 1-HOUR LONG EXITS:
                
                # 1. REPAINT (signal disappeared on entry candle)
                if exit_1hour and result_1hour['exit_reason'] == 'repaint':
                    should_exit = True
                    exit_reason_final = 'repaint_1hour'
                
                # 2. DEFAULT (4 bars = 4 hours held)
                elif exit_1hour and result_1hour['exit_reason'] == 'bars_held':
                    should_exit = True
                    exit_reason_final = 'default_1hour'
            
            elif self.trade_timeframe == '15min':
                # 15-MIN (LONG or SHORT) EXITS:
                
                # 1. REPAINT (signal disappeared on entry candle)
                if exit_15min and result_15min['exit_reason'] == 'repaint':
                    should_exit = True
                    exit_reason_final = 'repaint_15min'
                
                # 2. DEFAULT (4 bars = 1 hour held)
                elif exit_15min and result_15min['exit_reason'] == 'bars_held':
                    should_exit = True
                    exit_reason_final = 'default_15min'
                
                # 3. VOLUME NODE (only for 15min trades)
                elif self.volume_node_target:
                    if self.entry_direction == 1:  # Long
                        if current_price >= self.volume_node_target:
                            should_exit = True
                            exit_reason_final = 'volume_node_long'
                    elif self.entry_direction == -1:  # Short
                        if current_price <= self.volume_node_target:
                            should_exit = True
                            exit_reason_final = 'volume_node_short'
            
            # Execute exit
            if should_exit:
                self.send_to_algotest(
                    action='exit',
                    exit_price=current_price,
                    reason=exit_reason_final
                )
                
                pnl = (current_price - self.entry_price) * self.entry_direction
                pnl_pct = (pnl / self.entry_price) * 100
                
                print(f"\n{'='*80}")
                print(f"💰 TRADE CLOSED")
                print(f"{'='*80}")
                print(f"   Direction: {'LONG' if self.entry_direction == 1 else 'SHORT'}")
                print(f"   Timeframe: {self.trade_timeframe}")
                print(f"   Entry: {self.entry_price:.2f}")
                print(f"   Exit: {current_price:.2f}")
                print(f"   P&L: {pnl_pct:+.2f}%")
                print(f"   Reason: {exit_reason_final}")
                print(f"{'='*80}")
                
                self.in_trade = False
                self.volume_node_target = None
                self.trade_timeframe = None
        
        # ==========================================
        # STEP 4: CHECK FOR NEW ENTRIES (if not in trade)
        # ==========================================
        
        if not self.in_trade:
            
            # ================================================
            # ENTRY CASE 1: 15min LONG + 1hour LONG (UPGRADE!)
            # ================================================
            if entry_15min and signal_15min == 1 and entry_1hour and signal_1hour == 1:
                # Both timeframes show LONG on same candle → Trade on 1-HOUR
                
                self.in_trade = True
                self.entry_direction = 1  # Long
                self.entry_price = current_price
                self.trade_timeframe = '1hour'
                self.volume_node_target = None  # NO volume node for 1hour longs
                
                # Simple targets for 1hour long
                self.stop_loss = current_price * 0.99  # 1% below
                self.target_price = current_price * 1.02  # 2% above
                
                print(f"\n{'='*80}")
                print(f"🟢🟢 LONG ENTRY (1-HOUR TIMEFRAME - BOTH TFs ALIGNED)")
                print(f"{'='*80}")
                print(f"   15min: LONG ✅")
                print(f"   1hour: LONG ✅")
                print(f"   Entry: {self.entry_price:.2f}")
                print(f"   Target: {self.target_price:.2f}")
                print(f"   SL: {self.stop_loss:.2f}")
                print(f"   Exit Strategy: DEFAULT ONLY (4 x 1-hour bars)")
                print(f"{'='*80}")
                
                self.send_to_algotest(
                    action='entry',
                    direction='LONG',
                    entry=self.entry_price,
                    target=self.target_price,
                    sl=self.stop_loss
                )
            
            # ================================================
            # ENTRY CASE 2: 15min LONG (standalone)
            # ================================================
            elif entry_15min and signal_15min == 1:
                # Only 15min shows LONG → Trade on 15-MIN with volume nodes
                
                self.in_trade = True
                self.entry_direction = 1  # Long
                self.entry_price = current_price
                self.trade_timeframe = '15min'
                
                # Get volume node target
                self.volume_node_target = self.volume_detector.get_exit_target(
                    self.entry_direction,
                    current_price
                )
                
                # Set targets
                support = volume_result.get('nearest_support')
                self.stop_loss = support if support else current_price * 0.99
                self.target_price = (self.volume_node_target if self.volume_node_target 
                                    else current_price * 1.02)
                
                print(f"\n{'='*80}")
                print(f"🟢 LONG ENTRY (15-MIN TIMEFRAME)")
                print(f"{'='*80}")
                print(f"   15min: LONG ✅")
                print(f"   1hour: {signal_1hour} (not aligned)")
                print(f"   Entry: {self.entry_price:.2f}")
                print(f"   Target: {self.target_price:.2f}")
                print(f"   SL: {self.stop_loss:.2f}")
                print(f"   Volume Node: {self.volume_node_target:.2f if self.volume_node_target else 'None'}")
                print(f"   Exit Strategy: DEFAULT or VOLUME NODE (first hit)")
                print(f"{'='*80}")
                
                self.send_to_algotest(
                    action='entry',
                    direction='LONG',
                    entry=self.entry_price,
                    target=self.target_price,
                    sl=self.stop_loss
                )
            
            # ================================================
            # ENTRY CASE 3: 15min SHORT (always standalone)
            # ================================================
            elif entry_15min and signal_15min == -1:
                # 15min shows SHORT → Trade on 15-MIN with volume nodes
                
                self.in_trade = True
                self.entry_direction = -1  # Short
                self.entry_price = current_price
                self.trade_timeframe = '15min'
                
                # Get volume node target
                self.volume_node_target = self.volume_detector.get_exit_target(
                    self.entry_direction,
                    current_price
                )
                
                # Set targets
                resistance = volume_result.get('nearest_resistance')
                self.stop_loss = resistance if resistance else current_price * 1.01
                self.target_price = (self.volume_node_target if self.volume_node_target 
                                    else current_price * 0.98)
                
                print(f"\n{'='*80}")
                print(f"🔴 SHORT ENTRY (15-MIN TIMEFRAME)")
                print(f"{'='*80}")
                print(f"   15min: SHORT ✅")
                print(f"   Entry: {self.entry_price:.2f}")
                print(f"   Target: {self.target_price:.2f}")
                print(f"   SL: {self.stop_loss:.2f}")
                print(f"   Volume Node: {self.volume_node_target:.2f if self.volume_node_target else 'None'}")
                print(f"   Exit Strategy: DEFAULT or VOLUME NODE (first hit)")
                print(f"{'='*80}")
                
                self.send_to_algotest(
                    action='entry',
                    direction='SHORT',
                    entry=self.entry_price,
                    target=self.target_price,
                    sl=self.stop_loss
                )
        
        # Calculate processing time
        process_time = (time.time() - start_time) * 1000
        
        return {
            'signal_15min': signal_15min,
            'signal_1hour': signal_1hour,
            'in_trade': self.in_trade,
            'trade_timeframe': self.trade_timeframe,
            'current_price': current_price,
            'process_time_ms': process_time
        }


# ==========================================
# MAIN EXECUTION
# ==========================================

def run_system():
    """Run the complete dual timeframe system"""
    print("\n" + "="*80)
    print("🚀 BANKNIFTY DUAL TIMEFRAME TRADING SYSTEM")
    print("="*80)
    
    # Configuration
    ALGOTEST_URL = "https://your-algotest-url.com/api"  # ← UPDATE THIS
    
    # Initialize system
    system = DualTimeframeTradingSystem(algotest_url=ALGOTEST_URL)
    
    # Load data for both timeframes
    print("\n📊 Loading historical data...")
    system.signal_15min.load_data(timeframe='15min', n_bars=2000)
    system.signal_1hour.load_data(timeframe='1hour', n_bars=2000)
    
    print("\n✅ System ready!")
    print("\n🔄 Simulating last 50 candles...")
    print("-" * 80)
    
    # Simulate
    df_15min = system.signal_15min.df
    df_1hour = system.signal_1hour.df
    
    for i in range(len(df_15min) - 50, len(df_15min)):
        # Set data to this point
        system.signal_15min.df = df_15min.iloc[:i+1].copy()
        
        # Find corresponding 1hour candle
        current_time_15min = df_15min.iloc[i]['timestamp']
        df_1hour_subset = df_1hour[df_1hour['timestamp'] <= current_time_15min]
        system.signal_1hour.df = df_1hour_subset.copy()
        
        # Process
        result = system.process_candle()
        
        # Print status
        if i % 10 == 0 or result['in_trade']:
            timestamp = df_15min.iloc[i]['timestamp']
            price = result['current_price']
            status = f"{'📊 IN TRADE' if result['in_trade'] else '⏸️  WAITING'}"
            if result['in_trade']:
                status += f" ({result['trade_timeframe']})"
            
            print(f"{timestamp} | {price:>8.2f} | {status}")
    
    print("-" * 80)
    print("\n✅ Simulation complete!")


if __name__ == "__main__":
    run_system()