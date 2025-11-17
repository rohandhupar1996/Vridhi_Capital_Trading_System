"""
Utilities to fetch current month BankNifty futures symbol and token from Zerodha
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Tuple

from ..logging import ComponentLogger


def get_current_month_futures_symbol(kite) -> Optional[str]:
    """
    Get current month BankNifty futures trading symbol from Zerodha.
    
    Args:
        kite: Authenticated KiteConnect instance
        
    Returns:
        Trading symbol (e.g., "BANKNIFTY25NOVFUT") or None if not found
    """
    try:
        instruments = kite.instruments("NFO")
        
        # Find BankNifty futures contracts
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Filter for BankNifty FUT contracts in current month
        futures_contracts = []
        for inst in instruments:
            if (inst.get('name') == 'BANKNIFTY' and 
                inst.get('instrument_type') == 'FUT' and
                inst.get('exchange') == 'NFO'):
                expiry = inst.get('expiry')
                if expiry:
                    try:
                        exp_date = datetime.strptime(expiry, '%Y-%m-%d')
                        # Check if it's in current month
                        if exp_date.month == current_month and exp_date.year == current_year:
                            futures_contracts.append({
                                'symbol': inst.get('tradingsymbol'),
                                'expiry': exp_date,
                                'token': inst.get('instrument_token')
                            })
                    except (ValueError, TypeError):
                        continue
        
        if not futures_contracts:
            return None
        
        # Get the nearest expiry (current month contract)
        nearest = min(futures_contracts, key=lambda x: x['expiry'])
        return nearest['symbol']
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_futures_utils").error(
            f"Error getting futures symbol: {e}", exc_info=True
        )
        return None


def get_current_month_futures_token(kite) -> Optional[int]:
    """
    Get current month BankNifty futures instrument token from Zerodha.
    
    Args:
        kite: Authenticated KiteConnect instance
        
    Returns:
        Instrument token (int) or None if not found
    """
    try:
        instruments = kite.instruments("NFO")
        
        # Find BankNifty futures contracts
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Filter for BankNifty FUT contracts in current month
        futures_contracts = []
        for inst in instruments:
            if (inst.get('name') == 'BANKNIFTY' and 
                inst.get('instrument_type') == 'FUT' and
                inst.get('exchange') == 'NFO'):
                expiry = inst.get('expiry')
                if expiry:
                    try:
                        exp_date = datetime.strptime(expiry, '%Y-%m-%d')
                        # Check if it's in current month
                        if exp_date.month == current_month and exp_date.year == current_year:
                            futures_contracts.append({
                                'symbol': inst.get('tradingsymbol'),
                                'expiry': exp_date,
                                'token': inst.get('instrument_token')
                            })
                    except (ValueError, TypeError):
                        continue
        
        if not futures_contracts:
            return None
        
        # Get the nearest expiry (current month contract)
        nearest = min(futures_contracts, key=lambda x: x['expiry'])
        return nearest['token']
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_futures_utils").error(
            f"Error getting futures token: {e}", exc_info=True
        )
        return None


def get_current_month_futures_symbol_and_token(kite) -> Tuple[Optional[str], Optional[int]]:
    """
    Get both current month BankNifty futures symbol and token from Zerodha.
    Gets the nearest expiry contract (current month or next available).
    
    Args:
        kite: Authenticated KiteConnect instance
        
    Returns:
        Tuple of (symbol, token) or (None, None) if not found
    """
    try:
        instruments = kite.instruments("NFO")
        
        # Find BankNifty futures contracts
        now = datetime.now()
        
        # Filter for BankNifty FUT contracts (get all active contracts)
        futures_contracts = []
        logger = ComponentLogger.get_logger("zerodha_futures_utils")
        
        # Debug: count total BankNifty contracts
        banknifty_count = 0
        for inst in instruments:
            if inst.get('name') == 'BANKNIFTY':
                banknifty_count += 1
        
        logger.debug(f"Total BANKNIFTY instruments found: {banknifty_count}")
        
        for inst in instruments:
            if (inst.get('name') == 'BANKNIFTY' and 
                inst.get('instrument_type') == 'FUT' and
                inst.get('exchange') == 'NFO'):
                expiry = inst.get('expiry')
                if expiry:
                    try:
                        # Handle different expiry formats
                        exp_date = None
                        if isinstance(expiry, str):
                            exp_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                        elif isinstance(expiry, datetime):
                            exp_date = expiry.date()
                        elif isinstance(expiry, date):
                            exp_date = expiry
                        else:
                            continue
                        
                        # Only include contracts that haven't expired yet (compare dates, not datetime)
                        today = now.date()
                        if exp_date > today:
                            futures_contracts.append({
                                'symbol': inst.get('tradingsymbol'),
                                'expiry': exp_date,
                                'token': inst.get('instrument_token')
                            })
                            logger.debug(f"Found active contract: {inst.get('tradingsymbol')}, expiry: {exp_date}")
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Skipping contract with invalid expiry: {expiry}, error: {e}")
                        continue
        
        if not futures_contracts:
            # Try to find any FUT contract (even if expired) for debugging
            fut_contracts = [inst for inst in instruments 
                           if inst.get('name') == 'BANKNIFTY' and 
                           inst.get('instrument_type') == 'FUT' and
                           inst.get('exchange') == 'NFO']
            
            logger.error(
                f"No active BankNifty futures contracts found. Current date: {now.date()}, "
                f"Total BANKNIFTY instruments: {banknifty_count}, FUT contracts found: {len(fut_contracts)}"
            )
            if fut_contracts:
                sample = fut_contracts[0]
                logger.debug(f"Sample FUT contract: {sample.get('tradingsymbol')}, expiry: {sample.get('expiry')}, type: {type(sample.get('expiry'))}")
            return None, None
        
        # Get the nearest expiry (current month contract or next available)
        nearest = min(futures_contracts, key=lambda x: x['expiry'])
        logger.info(
            f"Found nearest futures contract",
            symbol=nearest['symbol'],
            expiry=nearest['expiry'].strftime('%Y-%m-%d') if isinstance(nearest['expiry'], date) else str(nearest['expiry']),
            token=nearest['token']
        )
        return nearest['symbol'], nearest['token']
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_futures_utils").error(
            f"Error getting futures symbol and token: {e}", exc_info=True
        )
        return None, None

