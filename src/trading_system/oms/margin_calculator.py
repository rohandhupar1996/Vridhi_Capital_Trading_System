"""
Margin Calculator for BankNifty Options Trading
Calculates margin requirements for LONG and SHORT strategies
"""

from typing import Dict, Optional
from datetime import datetime
from ..logging import ComponentLogger


class MarginCalculator:
    """
    Calculates margin requirements for BankNifty options strategies
    """
    
    def __init__(self, kite, logger: Optional[ComponentLogger] = None, option_chain_manager=None):
        self.kite = kite
        self.logger = logger or ComponentLogger.get_logger("margin_calculator")
        self.option_chain_manager = option_chain_manager  # For getting correct option symbols
        
        # Cache for margin calculations
        self._margin_cache: Dict[str, float] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_validity_seconds = 300  # 5 minutes
        
    def calculate_long_margin(
        self,
        atm_strike: int,
        hedge_strike: int,
        lot_size: int,
        futures_price: float
    ) -> Dict[str, float]:
        """
        Calculate margin requirement for LONG strategy using Zerodha's actual margin API:
        - SELL ATM PUT (PE) - uses actual SPAN + Exposure margin
        - BUY ATM CALL (CE) - premium cost
        - BUY 20 legs away PUT (PE) - premium cost
        
        Args:
            atm_strike: ATM strike price (calculated from FUTURES price, not spot)
            hedge_strike: 20 legs away strike (ATM - 2000)
            lot_size: Number of lots
            futures_price: Current BankNifty FUTURES contract price (NOT spot/cash)
            
        Returns:
            Dictionary with margin breakdown
        """
        try:
            # Get actual option symbols with expiry from option chain manager
            if self.option_chain_manager:
                # Use option chain manager to get correct symbols with expiry
                atm_ce_symbol = self.option_chain_manager.get_option_symbol(atm_strike, "CE")
                atm_pe_symbol = self.option_chain_manager.get_option_symbol(atm_strike, "PE")
                hedge_pe_symbol = self.option_chain_manager.get_option_symbol(hedge_strike, "PE")
                
                if not atm_ce_symbol or not atm_pe_symbol or not hedge_pe_symbol:
                    self.logger.warning("Could not get option symbols from option chain manager")
                    # Fallback to simplified calculation
                    return self._fallback_long_margin(atm_strike, hedge_strike, lot_size, futures_price)
            else:
                # Fallback: construct symbols (will likely fail for margin API)
                from datetime import datetime
                now = datetime.now()
                month_map = {1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
                            7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'}
                month = month_map[now.month]
                day = str(now.day).zfill(2)
                year_suffix = str(now.year)[2:]
                expiry_str = f"{day}{month}"
                
                atm_ce_symbol = f"BANKNIFTY{expiry_str}{year_suffix}{atm_strike}CE"
                atm_pe_symbol = f"BANKNIFTY{expiry_str}{year_suffix}{atm_strike}PE"
                hedge_pe_symbol = f"BANKNIFTY{expiry_str}{year_suffix}{hedge_strike}PE"
            
            if not atm_ce_symbol or not atm_pe_symbol or not hedge_pe_symbol:
                self.logger.error("Could not get option symbols")
                return self._fallback_long_margin(atm_strike, hedge_strike, lot_size, futures_price)
            
            # Get quotes for premium calculation
            quotes = self.kite.quote([
                f"NFO:{atm_ce_symbol}",
                f"NFO:{atm_pe_symbol}",
                f"NFO:{hedge_pe_symbol}"
            ])
            
            atm_ce_quote = quotes.get(f"NFO:{atm_ce_symbol}", {})
            atm_pe_quote = quotes.get(f"NFO:{atm_pe_symbol}", {})
            hedge_pe_quote = quotes.get(f"NFO:{hedge_pe_symbol}", {})
            
            # Get LTP or mid price for premium calculation
            atm_ce_price = atm_ce_quote.get('last_price', 0) or (
                (atm_ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2
                if atm_ce_quote.get('depth') else 0
            )
            
            atm_pe_price = atm_pe_quote.get('last_price', 0) or (
                (atm_pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2
                if atm_pe_quote.get('depth') else 0
            )
            
            hedge_pe_price = hedge_pe_quote.get('last_price', 0) or (
                (hedge_pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 hedge_pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2
                if hedge_pe_quote.get('depth') else 0
            )
            
            quantity = lot_size * 35  # 35 units per lot
            
            # Use BASKET MARGINS API to get actual margin with spread benefit
            # This calculates margin for all 3 legs together, considering hedging
            total_margin = 0
            sell_pe_margin = 0
            sell_pe_span = 0
            sell_pe_exposure = 0
            buy_ce_cost = 0
            buy_hedge_pe_cost = 0
            initial_margin = 0
            final_margin = 0
            
            try:
                # Build order params for all 3 legs (basket/spread order)
                basket_orders = [
                    {
                        "exchange": "NFO",
                        "tradingsymbol": atm_pe_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_SELL,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    },
                    {
                        "exchange": "NFO",
                        "tradingsymbol": atm_ce_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_BUY,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    },
                    {
                        "exchange": "NFO",
                        "tradingsymbol": hedge_pe_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_BUY,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    }
                ]
                
                # Get basket margins (considers spread benefit)
                basket_margins = self.kite.basket_order_margins(basket_orders, consider_positions=True)
                
                # Response structure: { 'initial': {...}, 'final': {...}, 'orders': [...] }
                # No 'status' or 'data' wrapper - returns data directly
                data = basket_margins if basket_margins else {}
                
                if data and (data.get('final') or data.get('initial')):
                    # Get final margin (with spread benefit) - this is the actual margin needed
                    final_data = data.get('final', {})
                    final_margin = final_data.get('total', 0)
                    
                    # Get initial margin (sum of individual margins, without spread benefit)
                    initial_data = data.get('initial', {})
                    initial_margin = initial_data.get('total', 0)
                    
                    # Get individual order margins for breakdown
                    orders_margin = data.get('orders', [])
                    
                    # Extract individual leg margins
                    for order_margin in orders_margin:
                        symbol = order_margin.get('tradingsymbol', '')
                        if atm_pe_symbol in symbol:
                            # SELL PE leg
                            sell_pe_span = order_margin.get('span', 0)
                            sell_pe_exposure = order_margin.get('exposure', 0)
                            sell_pe_margin = order_margin.get('total', 0)
                        elif atm_ce_symbol in symbol:
                            # BUY CE leg (premium cost)
                            buy_ce_cost = order_margin.get('option_premium', 0) or order_margin.get('total', 0)
                        elif hedge_pe_symbol in symbol:
                            # BUY Hedge PE leg (premium cost)
                            buy_hedge_pe_cost = order_margin.get('option_premium', 0) or order_margin.get('total', 0)
                    
                    # Use final margin (with spread benefit) as total margin
                    total_margin = final_margin
                    
                    self.logger.info(
                        f"Basket margin calculated from Zerodha API",
                        initial_margin=initial_margin,
                        final_margin=final_margin,
                        spread_benefit=initial_margin - final_margin,
                        sell_pe_span=sell_pe_span,
                        sell_pe_exposure=sell_pe_exposure,
                        sell_pe_margin=sell_pe_margin,
                        buy_ce_cost=buy_ce_cost,
                        buy_hedge_pe_cost=buy_hedge_pe_cost
                    )
                    
            except Exception as e:
                self.logger.warning(f"Could not get basket margins from Zerodha API: {e}", exc_info=True)
                # Fallback: Try individual order margins
                try:
                    # Try individual order margins API
                    sell_pe_order = [{
                        "exchange": "NFO",
                        "tradingsymbol": atm_pe_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_SELL,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    }]
                    
                    margins = self.kite.order_margins(sell_pe_order)
                    if margins and len(margins) > 0:
                        margin_data = margins[0]
                        sell_pe_span = margin_data.get('span', 0)
                        sell_pe_exposure = margin_data.get('exposure', 0)
                        sell_pe_margin = margin_data.get('total', 0)
                except Exception as e2:
                    self.logger.warning(f"Could not get individual margins either: {e2}")
                    # Fallback to simplified calculation
                    span_margin_per_lot = futures_price * 0.15
                    exposure_margin = futures_price * 0.05
                    sell_pe_margin = (span_margin_per_lot + exposure_margin + atm_pe_price) * lot_size
                
                # BUY costs (premium paid)
                buy_ce_cost = atm_ce_price * quantity if atm_ce_price > 0 else 0
                buy_hedge_pe_cost = hedge_pe_price * quantity if hedge_pe_price > 0 else 0
                
                total_margin = sell_pe_margin + buy_ce_cost + buy_hedge_pe_cost
                initial_margin = total_margin
                final_margin = total_margin  # No spread benefit in fallback
                self.logger.warning(f"Using fallback margin calculation (no spread benefit)")
            
            result = {
                'total_margin': total_margin,
                'initial_margin': initial_margin,  # Sum of individual margins
                'final_margin': final_margin,  # Actual margin with spread benefit
                'sell_pe_margin': sell_pe_margin,
                'sell_pe_span': sell_pe_span,
                'sell_pe_exposure': sell_pe_exposure,
                'buy_ce_cost': buy_ce_cost,
                'buy_hedge_pe_cost': buy_hedge_pe_cost,
                'atm_ce_price': atm_ce_price,
                'atm_pe_price': atm_pe_price,
                'hedge_pe_price': hedge_pe_price,
                'uses_actual_api': final_margin > 0 or sell_pe_span > 0  # True if we got actual margin from API
            }
            
            self.logger.info(
                f"LONG margin calculated",
                total_margin=total_margin,
                initial_margin=initial_margin,
                final_margin=final_margin,
                spread_benefit=(initial_margin - final_margin) if initial_margin > 0 else 0,
                sell_pe_margin=sell_pe_margin,
                buy_ce_cost=buy_ce_cost,
                buy_hedge_pe_cost=buy_hedge_pe_cost,
                lot_size=lot_size,
                atm_strike=atm_strike,
                uses_basket_api=(final_margin > 0)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating LONG margin: {e}", exc_info=True)
            # Return fallback calculation
            return self._fallback_long_margin(atm_strike, hedge_strike, lot_size, futures_price)
    
    def calculate_short_margin(
        self,
        atm_strike: int,
        hedge_strike: int,
        lot_size: int,
        futures_price: float
    ) -> Dict[str, float]:
        """
        Calculate margin requirement for SHORT strategy using Zerodha's actual margin API:
        - SELL ATM CALL (CE) - uses actual SPAN + Exposure margin
        - BUY ATM PUT (PE) - premium cost
        - BUY 20 legs away CALL (CE) - premium cost
        
        Args:
            atm_strike: ATM strike price (calculated from FUTURES price, not spot)
            hedge_strike: 20 legs away strike (ATM + 2000)
            lot_size: Number of lots
            futures_price: Current BankNifty FUTURES contract price (NOT spot/cash)
            
        Returns:
            Dictionary with margin breakdown
        """
        try:
            # Get actual option symbols with expiry from option chain manager
            if self.option_chain_manager:
                # Use option chain manager to get correct symbols with expiry
                atm_ce_symbol = self.option_chain_manager.get_option_symbol(atm_strike, "CE")
                atm_pe_symbol = self.option_chain_manager.get_option_symbol(atm_strike, "PE")
                hedge_ce_symbol = self.option_chain_manager.get_option_symbol(hedge_strike, "CE")
                
                if not atm_ce_symbol or not atm_pe_symbol or not hedge_ce_symbol:
                    self.logger.warning("Could not get option symbols from option chain manager")
                    # Fallback to simplified calculation
                    return self._fallback_short_margin(atm_strike, hedge_strike, lot_size, futures_price)
            else:
                # Fallback: construct symbols (will likely fail for margin API)
                from datetime import datetime
                now = datetime.now()
                month_map = {1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
                            7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'}
                month = month_map[now.month]
                day = str(now.day).zfill(2)
                year_suffix = str(now.year)[2:]
                expiry_str = f"{day}{month}"
                
                atm_ce_symbol = f"BANKNIFTY{expiry_str}{year_suffix}{atm_strike}CE"
                atm_pe_symbol = f"BANKNIFTY{expiry_str}{year_suffix}{atm_strike}PE"
                hedge_ce_symbol = f"BANKNIFTY{expiry_str}{year_suffix}{hedge_strike}CE"
            
            if not atm_ce_symbol or not atm_pe_symbol or not hedge_ce_symbol:
                self.logger.error("Could not get option symbols")
                return self._fallback_short_margin(atm_strike, hedge_strike, lot_size, futures_price)
            
            # Get quotes for premium calculation
            quotes = self.kite.quote([
                f"NFO:{atm_ce_symbol}",
                f"NFO:{atm_pe_symbol}",
                f"NFO:{hedge_ce_symbol}"
            ])
            
            atm_ce_quote = quotes.get(f"NFO:{atm_ce_symbol}", {})
            atm_pe_quote = quotes.get(f"NFO:{atm_pe_symbol}", {})
            hedge_ce_quote = quotes.get(f"NFO:{hedge_ce_symbol}", {})
            
            # Get LTP or mid price for premium calculation
            atm_ce_price = atm_ce_quote.get('last_price', 0) or (
                (atm_ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2
                if atm_ce_quote.get('depth') else 0
            )
            
            atm_pe_price = atm_pe_quote.get('last_price', 0) or (
                (atm_pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2
                if atm_pe_quote.get('depth') else 0
            )
            
            hedge_ce_price = hedge_ce_quote.get('last_price', 0) or (
                (hedge_ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 hedge_ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2
                if hedge_ce_quote.get('depth') else 0
            )
            
            quantity = lot_size * 35  # 35 units per lot
            
            # For SHORT strategy, try basket API first to get spread benefit
            # If basket API returns valid total, use it. Otherwise, fall back to individual order_margins
            total_margin = 0
            sell_ce_margin = 0
            sell_ce_span = 0
            sell_ce_exposure = 0
            buy_pe_cost = 0
            buy_hedge_ce_cost = 0
            initial_margin = 0
            final_margin = 0
            
            try:
                # Step 1: Try basket API first to get margin with spread benefit
                basket_orders = [
                    {
                        "exchange": "NFO",
                        "tradingsymbol": atm_ce_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_SELL,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    },
                    {
                        "exchange": "NFO",
                        "tradingsymbol": atm_pe_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_BUY,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    },
                    {
                        "exchange": "NFO",
                        "tradingsymbol": hedge_ce_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_BUY,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    }
                ]
                
                basket_margins = self.kite.basket_order_margins(basket_orders)
                
                # Calculate BUY premium costs for breakdown
                buy_pe_cost = atm_pe_price * quantity if atm_pe_price > 0 else 0
                buy_hedge_ce_cost = hedge_ce_price * quantity if hedge_ce_price > 0 else 0
                
                if basket_margins and isinstance(basket_margins, dict):
                    # Basket API response structure: {'initial': {...}, 'final': {...}, 'orders': [...], 'charges': {...}}
                    # Use 'final' total if available, otherwise use 'initial' total
                    basket_final = basket_margins.get('final', {})
                    basket_initial = basket_margins.get('initial', {})
                    basket_total = basket_final.get('total', 0) if isinstance(basket_final, dict) else 0
                    basket_initial_total = basket_initial.get('total', 0) if isinstance(basket_initial, dict) else 0
                    
                    # If final total is 0 but initial total exists, use initial (no spread benefit)
                    if basket_total == 0 and basket_initial_total > 0:
                        basket_total = basket_initial_total
                    
                    # Debug: Log basket API response
                    self.logger.info(
                        f"Basket API response for SHORT strategy",
                        basket_final_total=basket_final.get('total', 0) if isinstance(basket_final, dict) else 0,
                        basket_initial_total=basket_initial_total,
                        basket_total_used=basket_total,
                        basket_margins_keys=list(basket_margins.keys()) if basket_margins else []
                    )
                    
                    # Get individual SELL CE margin for breakdown
                    try:
                        sell_ce_order = [{
                            "exchange": "NFO",
                            "tradingsymbol": atm_ce_symbol,
                            "transaction_type": self.kite.TRANSACTION_TYPE_SELL,
                            "variety": self.kite.VARIETY_REGULAR,
                            "product": self.kite.PRODUCT_NRML,
                            "order_type": self.kite.ORDER_TYPE_MARKET,
                            "quantity": quantity,
                            "price": 0,
                            "trigger_price": 0
                        }]
                        margins = self.kite.order_margins(sell_ce_order)
                        if margins and len(margins) > 0:
                            margin_data = margins[0]
                            sell_ce_span = margin_data.get('span', 0)
                            sell_ce_exposure = margin_data.get('exposure', 0)
                            sell_ce_margin = margin_data.get('total', 0)
                    except:
                        pass
                    
                    # Calculate initial margin (sum of individual components)
                    initial_margin = sell_ce_margin + buy_pe_cost + buy_hedge_ce_cost
                    
                    # Use basket total if it's reasonable (not 0 and not too high)
                    # Basket API gives us the actual margin with spread benefit
                    # Accept basket total if it's between 1% and 200% of initial margin
                    if basket_total > 0 and basket_total >= initial_margin * 0.01 and basket_total <= initial_margin * 2:
                        # Basket API returned valid margin with spread benefit
                        final_margin = basket_total
                        total_margin = basket_total
                        self.logger.info(
                            f"SHORT margin calculated (using basket API with spread benefit)",
                            initial_margin=initial_margin,
                            final_margin=final_margin,
                            spread_benefit=(initial_margin - final_margin) if initial_margin > 0 else 0,
                            sell_ce_span=sell_ce_span,
                            sell_ce_exposure=sell_ce_exposure,
                            sell_ce_margin=sell_ce_margin,
                            buy_pe_cost=buy_pe_cost,
                            buy_hedge_ce_cost=buy_hedge_ce_cost
                        )
                    else:
                        # Basket API returned 0 or invalid value, use individual order_margins
                        # This means no spread benefit (or basket API issue)
                        if sell_ce_margin > 0:
                            final_margin = initial_margin
                            total_margin = initial_margin
                        else:
                            # Even individual margin failed, use fallback
                            raise Exception("Both basket and individual margins failed")
                        
                        self.logger.info(
                            f"SHORT margin calculated (using individual order_margins, no spread benefit)",
                            initial_margin=initial_margin,
                            final_margin=final_margin,
                            spread_benefit=0,
                            sell_ce_span=sell_ce_span,
                            sell_ce_exposure=sell_ce_exposure,
                            sell_ce_margin=sell_ce_margin,
                            buy_pe_cost=buy_pe_cost,
                            buy_hedge_ce_cost=buy_hedge_ce_cost
                        )
                else:
                    # Basket API failed, use individual order_margins
                    raise Exception("Basket API returned invalid response")
                    
            except Exception as e:
                self.logger.warning(f"Error with basket API, trying individual order_margins: {e}")
                # Fallback: Use individual order_margins API
                try:
                    sell_ce_order = [{
                        "exchange": "NFO",
                        "tradingsymbol": atm_ce_symbol,
                        "transaction_type": self.kite.TRANSACTION_TYPE_SELL,
                        "variety": self.kite.VARIETY_REGULAR,
                        "product": self.kite.PRODUCT_NRML,
                        "order_type": self.kite.ORDER_TYPE_MARKET,
                        "quantity": quantity,
                        "price": 0,
                        "trigger_price": 0
                    }]
                    
                    margins = self.kite.order_margins(sell_ce_order)
                    if margins and len(margins) > 0:
                        margin_data = margins[0]
                        sell_ce_span = margin_data.get('span', 0)
                        sell_ce_exposure = margin_data.get('exposure', 0)
                        sell_ce_margin = margin_data.get('total', 0)
                        
                        buy_pe_cost = atm_pe_price * quantity if atm_pe_price > 0 else 0
                        buy_hedge_ce_cost = hedge_ce_price * quantity if hedge_ce_price > 0 else 0
                        
                        initial_margin = sell_ce_margin + buy_pe_cost + buy_hedge_ce_cost
                        final_margin = initial_margin
                        total_margin = final_margin
                        
                        self.logger.info(
                            f"SHORT margin calculated (fallback: individual order_margins)",
                            initial_margin=initial_margin,
                            final_margin=final_margin,
                            spread_benefit=0,
                            sell_ce_span=sell_ce_span,
                            sell_ce_exposure=sell_ce_exposure,
                            sell_ce_margin=sell_ce_margin,
                            buy_pe_cost=buy_pe_cost,
                            buy_hedge_ce_cost=buy_hedge_ce_cost
                        )
                    else:
                        raise Exception("Individual order_margins returned empty")
                except Exception as e2:
                    self.logger.error(f"All margin calculation methods failed: {e2}")
                    # Final fallback: Simplified calculation
                    span_margin_per_lot = futures_price * 0.15
                    exposure_margin = futures_price * 0.05
                    sell_ce_margin = (span_margin_per_lot + exposure_margin + atm_ce_price) * lot_size
                    sell_ce_span = span_margin_per_lot * lot_size
                    sell_ce_exposure = exposure_margin * lot_size
                    
                    buy_pe_cost = atm_pe_price * quantity if atm_pe_price > 0 else 0
                    buy_hedge_ce_cost = hedge_ce_price * quantity if hedge_ce_price > 0 else 0
                    
                    total_margin = sell_ce_margin + buy_pe_cost + buy_hedge_ce_cost
                    initial_margin = total_margin
                    final_margin = total_margin
                    self.logger.warning(f"Using simplified fallback margin calculation")
            
            result = {
                'total_margin': total_margin,
                'initial_margin': initial_margin,  # Sum of individual margins
                'final_margin': final_margin,  # Actual margin with spread benefit
                'sell_ce_margin': sell_ce_margin,
                'sell_ce_span': sell_ce_span,
                'sell_ce_exposure': sell_ce_exposure,
                'buy_pe_cost': buy_pe_cost,
                'buy_hedge_ce_cost': buy_hedge_ce_cost,
                'atm_ce_price': atm_ce_price,
                'atm_pe_price': atm_pe_price,
                'hedge_ce_price': hedge_ce_price,
                'uses_actual_api': final_margin > 0 or sell_ce_span > 0  # True if we got actual margin from API
            }
            
            self.logger.info(
                f"SHORT margin calculated",
                total_margin=total_margin,
                initial_margin=initial_margin,
                final_margin=final_margin,
                spread_benefit=(initial_margin - final_margin) if initial_margin > 0 else 0,
                sell_ce_margin=sell_ce_margin,
                buy_pe_cost=buy_pe_cost,
                buy_hedge_ce_cost=buy_hedge_ce_cost,
                lot_size=lot_size,
                atm_strike=atm_strike,
                uses_basket_api=(final_margin > 0)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating SHORT margin: {e}", exc_info=True)
            # Return fallback calculation
            return self._fallback_short_margin(atm_strike, hedge_strike, lot_size, futures_price)
    
    def check_available_margin(self) -> float:
        """
        Check available margin from broker
        
        Returns:
            Available margin amount
        """
        try:
            margins = self.kite.margins()
            available = margins.get('equity', {}).get('available', {}).get('live_balance', 0)
            
            # If equity not available, try commodity
            if available == 0:
                available = margins.get('commodity', {}).get('available', {}).get('live_balance', 0)
            
            self.logger.debug(f"Available margin: {available}")
            return float(available)
            
        except Exception as e:
            self.logger.error(f"Error checking available margin: {e}", exc_info=True)
            return 0.0
    
    def pre_calculate_daily_margins(
        self,
        futures_price: float,
        lot_size: int = 8
    ) -> Dict[str, Dict[str, float]]:
        """
        Pre-calculate margin requirements for the day
        Useful for early morning signal preparation
        
        Args:
            futures_price: Current futures price
            lot_size: Number of lots
            
        Returns:
            Dictionary with LONG and SHORT margin requirements
        """
        atm_strike = self._calculate_atm_strike(futures_price)
        hedge_strike_long = atm_strike - 2000  # 20 legs away for LONG
        hedge_strike_short = atm_strike + 2000  # 20 legs away for SHORT
        
        long_margin = self.calculate_long_margin(
            atm_strike, hedge_strike_long, lot_size, futures_price
        )
        
        short_margin = self.calculate_short_margin(
            atm_strike, hedge_strike_short, lot_size, futures_price
        )
        
        return {
            'long': long_margin,
            'short': short_margin
        }
    
    def _fallback_long_margin(
        self,
        atm_strike: int,
        hedge_strike: int,
        lot_size: int,
        futures_price: float
    ) -> Dict[str, float]:
        """Fallback margin calculation using simplified formula"""
        # Simplified calculation (conservative estimate)
        span_margin_per_lot = futures_price * 0.15  # ~15% of futures price as SPAN
        exposure_margin = futures_price * 0.05  # ~5% exposure margin
        
        # Rough estimate for PE price (will be fetched later)
        estimated_pe_price = futures_price * 0.004  # Rough estimate: ~0.4% of futures
        
        # SELL ATM PE margin requirement (simplified)
        sell_pe_margin = (span_margin_per_lot + exposure_margin + estimated_pe_price) * lot_size
        
        # BUY costs (rough estimates - actual will be fetched)
        estimated_ce_price = futures_price * 0.004  # Rough estimate
        estimated_hedge_pe_price = futures_price * 0.003  # Rough estimate
        
        buy_ce_cost = estimated_ce_price * lot_size * 35
        buy_hedge_pe_cost = estimated_hedge_pe_price * lot_size * 35
        
        total_margin = sell_pe_margin + buy_ce_cost + buy_hedge_pe_cost
        
        return {
            'total_margin': total_margin,
            'sell_pe_margin': sell_pe_margin,
            'sell_pe_span': span_margin_per_lot * lot_size,
            'sell_pe_exposure': exposure_margin * lot_size,
            'buy_ce_cost': buy_ce_cost,
            'buy_hedge_pe_cost': buy_hedge_pe_cost,
            'atm_ce_price': estimated_ce_price,
            'atm_pe_price': estimated_pe_price,
            'hedge_pe_price': estimated_hedge_pe_price,
            'uses_actual_api': False
        }
    
    def _fallback_short_margin(
        self,
        atm_strike: int,
        hedge_strike: int,
        lot_size: int,
        futures_price: float
    ) -> Dict[str, float]:
        """Fallback margin calculation using simplified formula"""
        # Simplified calculation (conservative estimate)
        span_margin_per_lot = futures_price * 0.15  # ~15% of futures price as SPAN
        exposure_margin = futures_price * 0.05  # ~5% exposure margin
        
        # Rough estimate for CE price (will be fetched later)
        estimated_ce_price = futures_price * 0.004  # Rough estimate: ~0.4% of futures
        
        # SELL ATM CE margin requirement (simplified)
        sell_ce_margin = (span_margin_per_lot + exposure_margin + estimated_ce_price) * lot_size
        
        # BUY costs (rough estimates - actual will be fetched)
        estimated_pe_price = futures_price * 0.004  # Rough estimate
        estimated_hedge_ce_price = futures_price * 0.003  # Rough estimate
        
        buy_pe_cost = estimated_pe_price * lot_size * 35
        buy_hedge_ce_cost = estimated_hedge_ce_price * lot_size * 35
        
        total_margin = sell_ce_margin + buy_pe_cost + buy_hedge_ce_cost
        
        return {
            'total_margin': total_margin,
            'sell_ce_margin': sell_ce_margin,
            'sell_ce_span': span_margin_per_lot * lot_size,
            'sell_ce_exposure': exposure_margin * lot_size,
            'buy_pe_cost': buy_pe_cost,
            'buy_hedge_ce_cost': buy_hedge_ce_cost,
            'atm_ce_price': estimated_ce_price,
            'atm_pe_price': estimated_pe_price,
            'hedge_ce_price': estimated_hedge_ce_price,
            'initial_margin': total_margin,
            'final_margin': total_margin,
            'uses_actual_api': False
        }
    
    def _calculate_atm_strike(self, futures_price: float) -> int:
        """Calculate ATM strike based on futures price"""
        # BankNifty strikes are 100 points apart
        return int(round(futures_price / 100) * 100)

