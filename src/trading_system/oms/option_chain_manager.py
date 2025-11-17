"""
Option Chain Manager
Fetches and caches current month BankNifty option chain from Zerodha
Provides fast lookup for option contracts without repeated API calls
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..logging import ComponentLogger


@dataclass
class OptionContract:
    """Represents a single option contract"""
    symbol: str
    token: int
    strike: float
    option_type: str  # "CE" or "PE"
    expiry: date
    tradingsymbol: str


class OptionChainManager:
    """
    Manages BankNifty option chain with caching for fast lookups.
    
    Benefits:
    - Fetches option chain once at startup/refresh
    - Fast O(1) lookup by strike + type
    - More reliable than symbol construction
    - Handles expiry transitions automatically
    """
    
    def __init__(
        self,
        kite,
        logger: Optional[ComponentLogger] = None,
        auto_refresh: bool = True
    ):
        self.kite = kite
        self.logger = logger or ComponentLogger.get_logger("option_chain_manager")
        self.auto_refresh = auto_refresh
        
        # Cached option chain
        self.option_chain: Dict[Tuple[date, float, str], OptionContract] = {}
        self.current_expiry: Optional[date] = None
        self.last_refresh: Optional[datetime] = None
        
        # Load option chain on init
        self.refresh_option_chain()
    
    def refresh_option_chain(self) -> bool:
        """
        Fetch and cache current month BankNifty option chain from Zerodha
        
        Returns:
            True if refresh successful
        """
        try:
            self.logger.info("Refreshing option chain from Zerodha...")
            
            # Get all NFO instruments
            instruments = self.kite.instruments("NFO")
            
            # Filter for BankNifty options (CE/PE)
            banknifty_options = [
                inst for inst in instruments
                if inst.get('name') == 'BANKNIFTY' and 
                   inst.get('instrument_type') in ['CE', 'PE']
            ]
            
            self.logger.info(f"Found {len(banknifty_options)} BankNifty option contracts")
            
            # Get current expiry (nearest active expiry)
            today = datetime.now().date()
            expiry_dates = set()
            
            for inst in banknifty_options:
                expiry = inst.get('expiry')
                if expiry:
                    try:
                        if isinstance(expiry, str):
                            exp_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                        elif isinstance(expiry, date):
                            exp_date = expiry
                        elif isinstance(expiry, datetime):
                            exp_date = expiry.date()
                        else:
                            continue
                        
                        if exp_date >= today:
                            expiry_dates.add(exp_date)
                    except Exception:
                        continue
            
            if not expiry_dates:
                self.logger.error("No active expiry dates found")
                return False
            
            # Get current expiry (nearest)
            self.current_expiry = min(expiry_dates)
            self.logger.info(
                f"Current expiry: {self.current_expiry}",
                expiry_date=self.current_expiry.isoformat(),
                days_until_expiry=(self.current_expiry - today).days
            )
            
            # Filter options for current expiry and build lookup dictionary
            self.option_chain = {}
            current_expiry_options = [
                inst for inst in banknifty_options
                if self._expiry_matches(inst.get('expiry'), self.current_expiry)
            ]
            
            self.logger.info(f"Found {len(current_expiry_options)} options for current expiry")
            
            for inst in current_expiry_options:
                expiry = self._parse_expiry(inst.get('expiry'))
                if not expiry:
                    continue
                
                strike = inst.get('strike')
                option_type = inst.get('instrument_type')
                
                if strike and option_type:
                    contract = OptionContract(
                        symbol=inst.get('tradingsymbol', ''),
                        token=inst.get('instrument_token', 0),
                        strike=float(strike),
                        option_type=option_type,
                        expiry=expiry,
                        tradingsymbol=inst.get('tradingsymbol', '')
                    )
                    
                    # Key: (expiry, strike, option_type)
                    key = (expiry, float(strike), option_type)
                    self.option_chain[key] = contract
            
            self.last_refresh = datetime.now()
            self.logger.info(
                f"Option chain cached",
                total_contracts=len(self.option_chain),
                expiry=self.current_expiry.isoformat()
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error refreshing option chain: {e}", exc_info=True)
            return False
    
    def _expiry_matches(self, expiry, target_date: date) -> bool:
        """Check if expiry matches target date"""
        if not expiry:
            return False
        try:
            if isinstance(expiry, str):
                exp_date = datetime.strptime(expiry, '%Y-%m-%d').date()
            elif isinstance(expiry, date):
                exp_date = expiry
            elif isinstance(expiry, datetime):
                exp_date = expiry.date()
            else:
                return False
            return exp_date == target_date
        except Exception:
            return False
    
    def _parse_expiry(self, expiry) -> Optional[date]:
        """Parse expiry to date object"""
        if not expiry:
            return None
        try:
            if isinstance(expiry, str):
                return datetime.strptime(expiry, '%Y-%m-%d').date()
            elif isinstance(expiry, date):
                return expiry
            elif isinstance(expiry, datetime):
                return expiry.date()
        except Exception:
            pass
        return None
    
    def get_option_contract(
        self,
        strike: int | float,
        option_type: str,
        expiry: Optional[date] = None
    ) -> Optional[OptionContract]:
        """
        Get option contract by strike and type.
        
        Args:
            strike: Strike price (e.g., 59100)
            option_type: "CE" or "PE"
            expiry: Optional expiry date (uses current expiry if not provided)
            
        Returns:
            OptionContract if found, None otherwise
        """
        # Use current expiry if not specified
        if expiry is None:
            expiry = self.current_expiry
        
        if expiry is None:
            self.logger.warning("No expiry available, refreshing option chain...")
            self.refresh_option_chain()
            expiry = self.current_expiry
            if expiry is None:
                return None
        
        # Check if we need to refresh (expiry changed)
        if expiry != self.current_expiry and self.auto_refresh:
            self.logger.info(f"Expiry changed, refreshing option chain...")
            self.refresh_option_chain()
            expiry = self.current_expiry
        
        # Lookup in cache
        key = (expiry, float(strike), option_type.upper())
        contract = self.option_chain.get(key)
        
        if contract:
            self.logger.debug(
                f"Found option contract: {contract.symbol}",
                strike=strike,
                option_type=option_type,
                expiry=expiry.isoformat()
            )
            return contract
        
        # Not found - try refreshing once
        if self.auto_refresh and self.last_refresh:
            # Only refresh if last refresh was > 5 minutes ago
            time_since_refresh = (datetime.now() - self.last_refresh).total_seconds()
            if time_since_refresh > 300:  # 5 minutes
                self.logger.warning(f"Option contract not found, refreshing chain...")
                self.refresh_option_chain()
                expiry = self.current_expiry
                if expiry:
                    key = (expiry, float(strike), option_type.upper())
                    contract = self.option_chain.get(key)
        
        if not contract:
            self.logger.warning(
                f"Option contract not found",
                strike=strike,
                option_type=option_type,
                expiry=expiry.isoformat() if expiry else None
            )
        
        return contract
    
    def get_option_symbol(
        self,
        strike: int | float,
        option_type: str,
        expiry: Optional[date] = None
    ) -> Optional[str]:
        """
        Get option trading symbol by strike and type (convenience method)
        
        Args:
            strike: Strike price
            option_type: "CE" or "PE"
            expiry: Optional expiry date
            
        Returns:
            Trading symbol (e.g., "BANKNIFTY25NOV2559100CE") or None
        """
        contract = self.get_option_contract(strike, option_type, expiry)
        return contract.symbol if contract else None
    
    def get_option_token(
        self,
        strike: int | float,
        option_type: str,
        expiry: Optional[date] = None
    ) -> Optional[int]:
        """
        Get option instrument token by strike and type
        
        Args:
            strike: Strike price
            option_type: "CE" or "PE"
            expiry: Optional expiry date
            
        Returns:
            Instrument token or None
        """
        contract = self.get_option_contract(strike, option_type, expiry)
        return contract.token if contract else None
    
    def get_current_expiry(self) -> Optional[date]:
        """Get current expiry date"""
        return self.current_expiry
    
    def get_available_strikes(self, expiry: Optional[date] = None) -> List[float]:
        """Get list of available strikes for current expiry"""
        if expiry is None:
            expiry = self.current_expiry
        
        if expiry is None:
            return []
        
        strikes = set()
        for (exp, strike, _), contract in self.option_chain.items():
            if exp == expiry:
                strikes.add(strike)
        
        return sorted(list(strikes))
    
    def get_contracts_summary(self) -> Dict:
        """Get summary of cached contracts"""
        if not self.option_chain:
            return {
                "total_contracts": 0,
                "expiry": None,
                "ce_count": 0,
                "pe_count": 0,
                "strikes": []
            }
        
        ce_count = sum(1 for (_, _, opt_type), _ in self.option_chain.items() if opt_type == 'CE')
        pe_count = sum(1 for (_, _, opt_type), _ in self.option_chain.items() if opt_type == 'PE')
        strikes = self.get_available_strikes()
        
        return {
            "total_contracts": len(self.option_chain),
            "expiry": self.current_expiry.isoformat() if self.current_expiry else None,
            "ce_count": ce_count,
            "pe_count": pe_count,
            "strikes": len(strikes),
            "strike_range": f"{strikes[0]}-{strikes[-1]}" if strikes else None
        }

