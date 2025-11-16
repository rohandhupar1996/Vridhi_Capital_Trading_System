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
    
    def __init__(self, kite, logger: Optional[ComponentLogger] = None):
        self.kite = kite
        self.logger = logger or ComponentLogger.get_logger("margin_calculator")
        
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
        Calculate margin requirement for LONG strategy:
        - SELL ATM PUT (PE)
        - BUY ATM CALL (CE)
        - BUY 20 legs away PUT (PE) for margin
        
        Args:
            atm_strike: ATM strike price (calculated from FUTURES price, not spot)
            hedge_strike: 20 legs away strike (ATM - 2000)
            lot_size: Number of lots
            futures_price: Current BankNifty FUTURES contract price (NOT spot/cash)
            
        Returns:
            Dictionary with margin breakdown
        """
        try:
            # Get option prices
            atm_ce_symbol = f"BANKNIFTY{atm_strike}CE"
            atm_pe_symbol = f"BANKNIFTY{atm_strike}PE"
            hedge_pe_symbol = f"BANKNIFTY{hedge_strike}PE"
            
            # Get quotes
            quotes = self.kite.quote([
                f"NFO:{atm_ce_symbol}",
                f"NFO:{atm_pe_symbol}",
                f"NFO:{hedge_pe_symbol}"
            ])
            
            atm_ce_quote = quotes.get(f"NFO:{atm_ce_symbol}", {})
            atm_pe_quote = quotes.get(f"NFO:{atm_pe_symbol}", {})
            hedge_pe_quote = quotes.get(f"NFO:{hedge_pe_symbol}", {})
            
            # Get LTP or mid price
            atm_ce_price = atm_ce_quote.get('last_price', 
                (atm_ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2)
            
            atm_pe_price = atm_pe_quote.get('last_price',
                (atm_pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2)
            
            hedge_pe_price = hedge_pe_quote.get('last_price',
                (hedge_pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 hedge_pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2)
            
            # Calculate margin (simplified - actual margin depends on broker SPAN)
            # SELL ATM PE margin (naked short put margin)
            # BUY ATM CE cost
            # BUY hedge PE cost
            
            # Approximate margin calculation
            # For short options, margin is typically: SPAN + Exposure + Premium
            # For long options, it's just the premium paid
            
            # Simplified calculation (should use actual SPAN margin API if available)
            span_margin_per_lot = futures_price * 0.15  # ~15% of futures price as SPAN
            exposure_margin = futures_price * 0.05  # ~5% exposure margin
            
            # SELL ATM PE margin requirement
            sell_pe_margin = (span_margin_per_lot + exposure_margin + atm_pe_price) * lot_size
            
            # BUY costs
            buy_ce_cost = atm_ce_price * lot_size * 15  # 15 units per lot
            buy_hedge_pe_cost = hedge_pe_price * lot_size * 15
            
            total_margin = sell_pe_margin + buy_ce_cost + buy_hedge_pe_cost
            
            result = {
                'total_margin': total_margin,
                'sell_pe_margin': sell_pe_margin,
                'buy_ce_cost': buy_ce_cost,
                'buy_hedge_pe_cost': buy_hedge_pe_cost,
                'atm_ce_price': atm_ce_price,
                'atm_pe_price': atm_pe_price,
                'hedge_pe_price': hedge_pe_price
            }
            
            self.logger.debug(
                f"LONG margin calculated",
                total_margin=total_margin,
                lot_size=lot_size,
                atm_strike=atm_strike
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating LONG margin: {e}", exc_info=True)
            # Return conservative estimate
            return {
                'total_margin': futures_price * 0.25 * lot_size * 15,  # 25% of futures per lot
                'sell_pe_margin': 0,
                'buy_ce_cost': 0,
                'buy_hedge_pe_cost': 0,
                'atm_ce_price': 0,
                'atm_pe_price': 0,
                'hedge_pe_price': 0
            }
    
    def calculate_short_margin(
        self,
        atm_strike: int,
        hedge_strike: int,
        lot_size: int,
        futures_price: float
    ) -> Dict[str, float]:
        """
        Calculate margin requirement for SHORT strategy:
        - SELL ATM CALL (CE)
        - BUY ATM PUT (PE)
        - BUY 20 legs away CALL (CE) for margin
        
        Args:
            atm_strike: ATM strike price (calculated from FUTURES price, not spot)
            hedge_strike: 20 legs away strike (ATM + 2000)
            lot_size: Number of lots
            futures_price: Current BankNifty FUTURES contract price (NOT spot/cash)
            
        Returns:
            Dictionary with margin breakdown
        """
        try:
            # Get option prices
            atm_ce_symbol = f"BANKNIFTY{atm_strike}CE"
            atm_pe_symbol = f"BANKNIFTY{atm_strike}PE"
            hedge_ce_symbol = f"BANKNIFTY{hedge_strike}CE"
            
            # Get quotes
            quotes = self.kite.quote([
                f"NFO:{atm_ce_symbol}",
                f"NFO:{atm_pe_symbol}",
                f"NFO:{hedge_ce_symbol}"
            ])
            
            atm_ce_quote = quotes.get(f"NFO:{atm_ce_symbol}", {})
            atm_pe_quote = quotes.get(f"NFO:{atm_pe_symbol}", {})
            hedge_ce_quote = quotes.get(f"NFO:{hedge_ce_symbol}", {})
            
            # Get LTP or mid price
            atm_ce_price = atm_ce_quote.get('last_price',
                (atm_ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2)
            
            atm_pe_price = atm_pe_quote.get('last_price',
                (atm_pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 atm_pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2)
            
            hedge_ce_price = hedge_ce_quote.get('last_price',
                (hedge_ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) +
                 hedge_ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)) / 2)
            
            # Calculate margin
            span_margin_per_lot = futures_price * 0.15
            exposure_margin = futures_price * 0.05
            
            # SELL ATM CE margin requirement
            sell_ce_margin = (span_margin_per_lot + exposure_margin + atm_ce_price) * lot_size
            
            # BUY costs
            buy_pe_cost = atm_pe_price * lot_size * 15
            buy_hedge_ce_cost = hedge_ce_price * lot_size * 15
            
            total_margin = sell_ce_margin + buy_pe_cost + buy_hedge_ce_cost
            
            result = {
                'total_margin': total_margin,
                'sell_ce_margin': sell_ce_margin,
                'buy_pe_cost': buy_pe_cost,
                'buy_hedge_ce_cost': buy_hedge_ce_cost,
                'atm_ce_price': atm_ce_price,
                'atm_pe_price': atm_pe_price,
                'hedge_ce_price': hedge_ce_price
            }
            
            self.logger.debug(
                f"SHORT margin calculated",
                total_margin=total_margin,
                lot_size=lot_size,
                atm_strike=atm_strike
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating SHORT margin: {e}", exc_info=True)
            # Return conservative estimate
            return {
                'total_margin': futures_price * 0.25 * lot_size * 15,
                'sell_ce_margin': 0,
                'buy_pe_cost': 0,
                'buy_hedge_ce_cost': 0,
                'atm_ce_price': 0,
                'atm_pe_price': 0,
                'hedge_ce_price': 0
            }
    
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
    
    def _calculate_atm_strike(self, futures_price: float) -> int:
        """Calculate ATM strike based on futures price"""
        # BankNifty strikes are 100 points apart
        return int(round(futures_price / 100) * 100)

