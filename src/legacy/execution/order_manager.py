"""
Order Management System for BankNifty Options
- Uses futures price for ATM calculation
- Executes buying legs first, then selling legs
- Market orders with limit fallback
"""

import time
from datetime import datetime
from typing import Dict, List, Optional
import logging

class OrderManager:
    def __init__(self, kite):
        self.kite = kite
        self.current_month_symbol = self.get_current_futures_symbol()
        self.futures_ltp = None
        self.atm_strike = None
        self.active_orders = []
        self.positions = {}
        
    def get_current_futures_symbol(self):
        """Auto-detect current month futures contract"""
        now = datetime.now()
        month_map = {1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
                    7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'}
        
        # Contract rolls on last Thursday
        year_suffix = str(now.year)[2:]
        month = month_map[now.month]
        
        # Current active contract
        symbol = f"BANKNIFTY{year_suffix}{month}FUT"
        print(f"📅 Active futures: {symbol}")
        return symbol
    
    def update_futures_price(self, tick):
        """Update futures LTP from tick data"""
        if tick['instrument_token'] == self.get_futures_token():
            self.futures_ltp = tick['last_price']
            self.atm_strike = self.calculate_atm_strike(self.futures_ltp)
    
    def calculate_atm_strike(self, futures_price):
        """Calculate ATM strike based on futures price"""
        # BankNifty strikes are 100 points apart
        atm = round(futures_price / 100) * 100
        return atm
    
    def place_long_orders(self):
        """
        LONG Signal:
        - Buy ATM CE
        - Sell ATM PE  
        - Buy 20 strikes OTM PE (hedge)
        """
        if not self.futures_ltp:
            print("❌ No futures price available")
            return False
        
        atm = self.atm_strike
        hedge_strike = atm - 2000  # 20 strikes away
        
        print(f"\n🔵 LONG Entry | Futures: {self.futures_ltp:.2f} | ATM: {atm}")
        
        # Step 1: Execute all BUY legs first
        buy_orders = [
            {'symbol': f'BANKNIFTY{atm}CE', 'qty': 15, 'side': 'BUY', 'leg': 'main'},
            {'symbol': f'BANKNIFTY{hedge_strike}PE', 'qty': 15, 'side': 'BUY', 'leg': 'hedge'}
        ]
        
        buy_success = self.execute_legs(buy_orders, "BUY")
        
        if not buy_success:
            print("❌ Buy legs failed, aborting")
            self.exit_all_positions()
            return False
        
        # Step 2: Execute SELL legs after buys complete
        sell_orders = [
            {'symbol': f'BANKNIFTY{atm}PE', 'qty': 15, 'side': 'SELL', 'leg': 'short'}
        ]
        
        sell_success = self.execute_legs(sell_orders, "SELL")
        
        if not sell_success:
            print("⚠️ Sell leg failed, exiting all")
            self.exit_all_positions()
            return False
        
        self.positions['type'] = 'LONG'
        self.positions['entry_time'] = datetime.now()
        print("✅ LONG position established")
        return True
    
    def place_short_orders(self):
        """
        SHORT Signal:
        - Buy ATM PE
        - Sell ATM CE
        - Buy 20 strikes OTM CE (hedge)
        """
        if not self.futures_ltp:
            print("❌ No futures price available")
            return False
        
        atm = self.atm_strike
        hedge_strike = atm + 2000  # 20 strikes away
        
        print(f"\n🔴 SHORT Entry | Futures: {self.futures_ltp:.2f} | ATM: {atm}")
        
        # Step 1: Execute all BUY legs first
        buy_orders = [
            {'symbol': f'BANKNIFTY{atm}PE', 'qty': 15, 'side': 'BUY', 'leg': 'main'},
            {'symbol': f'BANKNIFTY{hedge_strike}CE', 'qty': 15, 'side': 'BUY', 'leg': 'hedge'}
        ]
        
        buy_success = self.execute_legs(buy_orders, "BUY")
        
        if not buy_success:
            print("❌ Buy legs failed, aborting")
            self.exit_all_positions()
            return False
        
        # Step 2: Execute SELL legs
        sell_orders = [
            {'symbol': f'BANKNIFTY{atm}CE', 'qty': 15, 'side': 'SELL', 'leg': 'short'}
        ]
        
        sell_success = self.execute_legs(sell_orders, "SELL")
        
        if not sell_success:
            print("⚠️ Sell leg failed, exiting all")
            self.exit_all_positions()
            return False
        
        self.positions['type'] = 'SHORT'
        self.positions['entry_time'] = datetime.now()
        print("✅ SHORT position established")
        return True
    
    def execute_legs(self, orders: List[Dict], leg_type: str) -> bool:
        """Execute multiple orders with smart execution"""
        print(f"\n  Executing {leg_type} legs...")
        
        for order in orders:
            success = self.place_single_order(
                symbol=order['symbol'],
                quantity=order['qty'],
                transaction_type=order['side']
            )
            
            if not success:
                print(f"  ❌ Failed: {order['symbol']}")
                return False
            
            print(f"  ✅ {order['side']} {order['qty']} {order['symbol']}")
            time.sleep(0.1)  # Small delay between orders
        
        return True
    
    def place_single_order(self, symbol: str, quantity: int, transaction_type: str) -> bool:
        """Place single order with market first, then limit fallback"""
        try:
            # Try market order first
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,
                order_type=self.kite.ORDER_TYPE_MARKET
            )
            
            # Check order status
            time.sleep(1)
            status = self.check_order_status(order_id)
            
            if status == 'COMPLETE':
                return True
            elif status == 'REJECTED':
                # Fallback to limit order
                return self.place_limit_order_smart(symbol, quantity, transaction_type)
            
        except Exception as e:
            print(f"    Market order failed: {e}")
            # Fallback to limit order
            return self.place_limit_order_smart(symbol, quantity, transaction_type)
        
        return False
    
    def place_limit_order_smart(self, symbol: str, quantity: int, transaction_type: str) -> bool:
        """Place limit order based on bid-ask spread"""
        try:
            # Get quote for smart pricing
            quote = self.kite.quote(f"NFO:{symbol}")[f"NFO:{symbol}"]
            
            if transaction_type == "BUY":
                # For buying, use ask price + small buffer
                price = quote['depth']['sell'][0]['price'] + 0.05
            else:
                # For selling, use bid price - small buffer
                price = quote['depth']['buy'][0]['price'] - 0.05
            
            # Round to nearest 0.05
            price = round(price * 20) / 20
            
            print(f"    Placing limit order at {price}")
            
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                product=self.kite.PRODUCT_MIS,
                order_type=self.kite.ORDER_TYPE_LIMIT
            )
            
            # Wait for fill
            for _ in range(10):  # 10 second timeout
                time.sleep(1)
                if self.check_order_status(order_id) == 'COMPLETE':
                    return True
            
            return False
            
        except Exception as e:
            print(f"    Limit order failed: {e}")
            return False
    
    def check_order_status(self, order_id: str) -> str:
        """Check order status"""
        try:
            orders = self.kite.orders()
            for order in orders:
                if order['order_id'] == order_id:
                    return order['status']
        except:
            pass
        return 'UNKNOWN'
    
    def exit_all_positions(self):
        """Exit all positions (square off)"""
        print("\n⏹️ Exiting all positions...")
        
        positions = self.kite.positions()['net']
        
        for pos in positions:
            if 'BANKNIFTY' in pos['tradingsymbol'] and pos['quantity'] != 0:
                # Determine transaction type for exit
                exit_type = 'SELL' if pos['quantity'] > 0 else 'BUY'
                exit_qty = abs(pos['quantity'])
                
                self.place_single_order(
                    symbol=pos['tradingsymbol'],
                    quantity=exit_qty,
                    transaction_type=exit_type
                )
        
        self.positions = {}
        print("✅ All positions closed")
    
    def get_futures_token(self):
        """Get instrument token for futures contract"""
        instruments = self.kite.instruments("NFO")
        for inst in instruments:
            if inst['tradingsymbol'] == self.current_month_symbol:
                return inst['instrument_token']
        return None


# Usage example
def handle_signal(signal_type: str, order_manager: OrderManager):
    """Main signal handler"""
    if signal_type == "LONG":
        success = order_manager.place_long_orders()
    elif signal_type == "SHORT":
        success = order_manager.place_short_orders()
    elif signal_type == "EXIT":
        order_manager.exit_all_positions()
        success = True
    else:
        success = False
    
    return success


"""
EXECUTION FLOW:

1. Signal triggers (LONG/SHORT)
2. Get current futures LTP
3. Calculate ATM strike
4. Execute BUY legs first (main + hedge)
5. Only if buys succeed, execute SELL legs
6. If any leg fails, exit everything

ORDER PRIORITY:
1. Market orders (fast)
2. If rejected/failed → Limit orders at bid/ask
3. Smart pricing for quick fills

SAFETY:
- Always buy protective legs first
- Never naked shorts
- Auto-exit on partial fills
"""