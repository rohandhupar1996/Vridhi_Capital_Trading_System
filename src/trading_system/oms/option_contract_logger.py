"""
Option Contract Execution Logger
Logs all CE/PE option contracts executed in JSON format for audit and analysis
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from ..logging import ComponentLogger


@dataclass
class OptionContractLog:
    """Single option contract execution log entry"""
    timestamp: str
    trade_type: str  # "ENTRY_LONG", "ENTRY_SHORT", "EXIT", "SL"
    symbol: str
    option_type: str  # "CE" or "PE"
    strike: int
    expiry: str  # e.g., "25NOV"
    leg_type: str  # "main", "hedge", "short"
    transaction_type: str  # "BUY" or "SELL"
    quantity: int
    average_price: float
    order_id: Optional[str] = None
    status: str = "PENDING"  # "PENDING", "COMPLETE", "REJECTED", etc.
    futures_price: Optional[float] = None
    atm_strike: Optional[int] = None
    notes: Optional[str] = None


class OptionContractLogger:
    """
    Logs all option contract executions to JSON file
    Maintains a running log of all CE/PE contracts traded
    """
    
    def __init__(
        self,
        log_file: Path | str = "logs/option_contracts.json",
        logger: Optional[ComponentLogger] = None
    ):
        self.log_file = Path(log_file)
        self.logger = logger or ComponentLogger.get_logger("option_contract_logger")
        
        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing logs
        self.logs: List[Dict] = self._load_logs()
    
    def _load_logs(self) -> List[Dict]:
        """Load existing logs from file"""
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            self.logger.error(f"Error loading logs: {e}")
            return []
    
    def _save_logs(self) -> None:
        """Save logs to file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(self.logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving logs: {e}")
    
    def log_contract(
        self,
        trade_type: str,
        symbol: str,
        option_type: str,
        strike: int,
        expiry: str,
        leg_type: str,
        transaction_type: str,
        quantity: int,
        average_price: float = 0.0,
        order_id: Optional[str] = None,
        status: str = "PENDING",
        futures_price: Optional[float] = None,
        atm_strike: Optional[int] = None,
        notes: Optional[str] = None
    ) -> None:
        """
        Log an option contract execution
        
        Args:
            trade_type: "ENTRY_LONG", "ENTRY_SHORT", "EXIT", "SL"
            symbol: Full option symbol (e.g., "BANKNIFTY25NOV59100CE")
            option_type: "CE" or "PE"
            strike: Strike price
            expiry: Expiry string (e.g., "25NOV")
            leg_type: "main", "hedge", "short"
            transaction_type: "BUY" or "SELL"
            quantity: Number of units
            average_price: Average execution price
            order_id: Zerodha order ID
            status: Order status
            futures_price: Futures price at execution
            atm_strike: ATM strike used
            notes: Additional notes
        """
        log_entry = OptionContractLog(
            timestamp=datetime.now().isoformat(),
            trade_type=trade_type,
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            leg_type=leg_type,
            transaction_type=transaction_type,
            quantity=quantity,
            average_price=average_price,
            order_id=order_id,
            status=status,
            futures_price=futures_price,
            atm_strike=atm_strike,
            notes=notes
        )
        
        # Convert to dict and append
        log_dict = asdict(log_entry)
        self.logs.append(log_dict)
        
        # Save to file
        self._save_logs()
        
        self.logger.info(
            f"Logged option contract: {symbol}",
            trade_type=trade_type,
            leg_type=leg_type,
            transaction_type=transaction_type,
            quantity=quantity,
            status=status
        )
    
    def log_leg_execution(
        self,
        trade_type: str,
        leg: Dict,
        futures_price: Optional[float] = None,
        atm_strike: Optional[int] = None,
        expiry: Optional[str] = None
    ) -> None:
        """
        Log an order leg execution
        
        Args:
            trade_type: "ENTRY_LONG", "ENTRY_SHORT", "EXIT", "SL"
            leg: OrderLeg dict with symbol, quantity, transaction_type, leg_type, etc.
            futures_price: Futures price at execution
            atm_strike: ATM strike used
            expiry: Expiry string (if not extractable from symbol)
        """
        symbol = leg.get('symbol', '')
        
        # Extract expiry, strike, option_type from symbol
        # Format: BANKNIFTY25NOV2559000CE
        if not expiry:
            # Try to extract from symbol
            # BANKNIFTY25NOV2559000CE -> expiry = 25NOV
            if 'BANKNIFTY' in symbol:
                parts = symbol.replace('BANKNIFTY', '')
                # Find expiry (DDMMM format)
                expiry = None
                month_map = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                            'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                for month in month_map:
                    if month in parts:
                        idx = parts.find(month)
                        expiry = parts[idx-2:idx+3] if idx >= 2 else None
                        break
        
        # Extract strike and option type
        option_type = "CE" if symbol.endswith("CE") else "PE" if symbol.endswith("PE") else "UNKNOWN"
        
        # Extract strike (before CE/PE)
        strike = 0
        if option_type != "UNKNOWN":
            strike_str = symbol.replace("BANKNIFTY", "").replace(expiry or "", "").replace(option_type, "")
            # Remove year suffix (2 digits)
            if len(strike_str) > 2:
                strike_str = strike_str[2:]  # Remove year suffix
            try:
                strike = int(strike_str)
            except ValueError:
                pass
        
        self.log_contract(
            trade_type=trade_type,
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            expiry=expiry or "UNKNOWN",
            leg_type=leg.get('leg_type', 'unknown'),
            transaction_type=leg.get('transaction_type', 'UNKNOWN'),
            quantity=leg.get('quantity', 0),
            average_price=leg.get('average_price', 0.0),
            order_id=leg.get('order_id'),
            status=leg.get('status', 'PENDING').value if hasattr(leg.get('status', ''), 'value') else str(leg.get('status', 'PENDING')),
            futures_price=futures_price,
            atm_strike=atm_strike,
            notes=leg.get('notes')
        )
    
    def get_today_logs(self) -> List[Dict]:
        """Get all logs from today"""
        today = datetime.now().date().isoformat()
        return [
            log for log in self.logs
            if log.get('timestamp', '').startswith(today)
        ]
    
    def get_contracts_by_trade(self, trade_type: str) -> List[Dict]:
        """Get all contracts for a specific trade type"""
        return [
            log for log in self.logs
            if log.get('trade_type') == trade_type
        ]
    
    def get_summary(self) -> Dict:
        """Get summary statistics"""
        if not self.logs:
            return {
                "total_contracts": 0,
                "by_type": {},
                "by_trade_type": {},
                "total_quantity": 0
            }
        
        summary = {
            "total_contracts": len(self.logs),
            "by_type": {"CE": 0, "PE": 0},
            "by_trade_type": {},
            "total_quantity": 0,
            "by_leg_type": {"main": 0, "hedge": 0, "short": 0}
        }
        
        for log in self.logs:
            option_type = log.get('option_type', '')
            if option_type in summary['by_type']:
                summary['by_type'][option_type] += 1
            
            trade_type = log.get('trade_type', '')
            summary['by_trade_type'][trade_type] = summary['by_trade_type'].get(trade_type, 0) + 1
            
            leg_type = log.get('leg_type', '')
            if leg_type in summary['by_leg_type']:
                summary['by_leg_type'][leg_type] += 1
            
            summary['total_quantity'] += log.get('quantity', 0)
        
        return summary

