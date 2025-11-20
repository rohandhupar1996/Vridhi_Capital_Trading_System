"""
Utilities to fetch current month BankNifty futures symbol and token from Zerodha

Contract Rollover Logic:
- Bank Nifty monthly expiry: Get from option chain (BANKNIFTY CE/PE options) - SOURCE OF TRUTH
- Options and Futures expire on SAME DATE
- Use option chain data to get actual expiry date (NOT hardcoded day of week)
- Proactively switch to next contract AFTER expiry (next day after expiry)
- Example: Nov expiry on Nov 25 (from option chain), switch to DEC on Nov 26
- NO hardcoded Tuesday/Thursday - expiry date from option chain is authoritative
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
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


def get_monthly_expiry_from_option_chain(kite) -> Optional[date]:
    """
    Get monthly expiry date from BANKNIFTY option chain (SOURCE OF TRUTH).
    Monthly options and futures expire on SAME DATE.
    This gets the ACTUAL expiry date from option chain, NOT hardcoded day of week.
    
    IMPORTANT: Returns the CURRENT MONTH expiry date, even if it has passed.
    This is needed for rollover logic: if today > expiry, switch to next contract.
    Example: On Nov 26, still returns Nov 25 expiry (to detect rollover needed).
    
    Args:
        kite: Authenticated KiteConnect instance
        
    Returns:
        Current month expiry date from option chain or None if not found
    """
    try:
        instruments = kite.instruments("NFO")
        today = datetime.now().date()
        expiry_dates = set()
        
        # Get expiry dates from BANKNIFTY options (CE/PE)
        for inst in instruments:
            if (inst.get('name') == 'BANKNIFTY' and 
                inst.get('instrument_type') in ['CE', 'PE'] and
                inst.get('exchange') == 'NFO'):
                expiry = inst.get('expiry')
                if expiry:
                    try:
                        if isinstance(expiry, str):
                            exp_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                        elif isinstance(expiry, datetime):
                            exp_date = expiry.date()
                        elif isinstance(expiry, date):
                            exp_date = expiry
                        else:
                            continue
                        
                        # Include ALL expiry dates (including expired ones for rollover detection)
                        # Limit to last 2 months to get current month expiry
                        two_months_ago = today - timedelta(days=60)
                        if exp_date >= two_months_ago:
                            expiry_dates.add(exp_date)
                    except (ValueError, TypeError):
                        continue
        
        if expiry_dates:
            # Get the expiry date that's closest to today (could be current month or just passed)
            # This helps detect rollover: if today > nearest_expiry, switch to next contract
            nearest_expiry = min(expiry_dates, key=lambda x: abs((x - today).days))
            logger = ComponentLogger.get_logger("zerodha_futures_utils")
            
            days_diff = (nearest_expiry - today).days
            status = "PASSED" if days_diff < 0 else "UPCOMING" if days_diff > 0 else "TODAY"
            
            logger.info(
                f"Monthly expiry from option chain: {nearest_expiry} ({status})",
                expiry_date=nearest_expiry.isoformat(),
                days_difference=days_diff,
                today=today.isoformat()
            )
            return nearest_expiry
        
        return None
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_futures_utils").error(
            f"Error getting expiry from option chain: {e}", exc_info=True
        )
        return None


def get_futures_symbol_with_rollover(kite) -> Tuple[Optional[str], Optional[int], Optional[date]]:
    """
    Get BankNifty futures symbol and token with proactive contract rollover.
    
    Rollover Logic:
    - Gets expiry date from option chain (source of truth)
    - If today is AFTER expiry date, switch to next contract
    - Example: Nov expiry on Nov 25, on Nov 26 switch to DEC contract
    - Uses option chain to get actual expiry date (NOT hardcoded day of week)
    
    Args:
        kite: Authenticated KiteConnect instance
        
    Returns:
        Tuple of (symbol, token, expiry_date) or (None, None, None) if not found
    """
    try:
        # Get expiry date from option chain (source of truth)
        expiry_date = get_monthly_expiry_from_option_chain(kite)
        if not expiry_date:
            # If can't get expiry, fall back to current month
            symbol, token = get_current_month_futures_symbol_and_token(kite)
            return symbol, token, None
        
        today = datetime.now().date()
        logger = ComponentLogger.get_logger("zerodha_futures_utils")
        
        # Get all active futures contracts
        instruments = kite.instruments("NFO")
        futures_contracts = []
        
        for inst in instruments:
            if (inst.get('name') == 'BANKNIFTY' and 
                inst.get('instrument_type') == 'FUT' and
                inst.get('exchange') == 'NFO'):
                expiry = inst.get('expiry')
                if expiry:
                    try:
                        if isinstance(expiry, str):
                            exp_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                        elif isinstance(expiry, datetime):
                            exp_date = expiry.date()
                        elif isinstance(expiry, date):
                            exp_date = expiry
                        else:
                            continue
                        
                        # Only include non-expired contracts
                        if exp_date > today:
                            futures_contracts.append({
                                'symbol': inst.get('tradingsymbol'),
                                'expiry': exp_date,
                                'token': inst.get('instrument_token')
                            })
                    except (ValueError, TypeError):
                        continue
        
        if not futures_contracts:
            logger.error("No active futures contracts found for rollover")
            return None, None, expiry_date
        
        # Rollover Logic:
        # - If today is AFTER expiry date, get NEXT contract (December)
        # - If today is ON or BEFORE expiry date, get CURRENT contract (November)
        # Example: Nov expiry on Nov 25, on Nov 26 switch to DEC
        if today > expiry_date:
            # Expiry has passed (today is Nov 26, expiry was Nov 25), get next contract (December)
            next_contracts = [c for c in futures_contracts if c['expiry'] > expiry_date]
            if next_contracts:
                nearest_next = min(next_contracts, key=lambda x: x['expiry'])
                logger.info(
                    f"Rollover: Expiry passed ({expiry_date.isoformat()}), switching to next contract",
                    new_symbol=nearest_next['symbol'],
                    new_expiry=nearest_next['expiry'].isoformat(),
                    today=today.isoformat()
                )
                return nearest_next['symbol'], nearest_next['token'], expiry_date
        else:
            # Before or on expiry (today is Nov 25 or earlier), get current contract (November)
            current_contracts = [c for c in futures_contracts if c['expiry'] == expiry_date]
            if current_contracts:
                current = current_contracts[0]
                logger.info(
                    f"Current contract (expiry: {expiry_date.isoformat()})",
                    symbol=current['symbol'],
                    days_until_expiry=(expiry_date - today).days if expiry_date > today else 0,
                    today=today.isoformat()
                )
                return current['symbol'], current['token'], expiry_date
        
        # If no exact match found, get nearest contract (should not happen normally)
        nearest = min(futures_contracts, key=lambda x: x['expiry'])
        logger.warning(
            f"No exact contract match, using nearest contract",
            symbol=nearest['symbol'],
            expiry=nearest['expiry'].isoformat(),
            option_chain_expiry=expiry_date.isoformat() if expiry_date else "UNKNOWN"
        )
        return nearest['symbol'], nearest['token'], expiry_date
        
    except Exception as e:
        ComponentLogger.get_logger("zerodha_futures_utils").error(
            f"Error getting futures with rollover: {e}", exc_info=True
        )
        return None, None, None


def get_current_month_futures_symbol_and_token(kite) -> Tuple[Optional[str], Optional[int]]:
    """
    Get both current month BankNifty futures symbol and token from Zerodha.
    Gets the nearest expiry contract (current month or next available).
    
    IMPORTANT: For contract rollover, use get_futures_symbol_with_rollover() instead,
    which proactively switches to next contract after expiry based on option chain.
    
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

