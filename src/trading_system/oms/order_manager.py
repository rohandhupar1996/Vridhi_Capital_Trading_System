"""
Order Management System (OMS) for BankNifty Options Trading
Handles entry, exit, SL with margin management and sequential lot reduction
"""

import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from ..logging import ComponentLogger
from .margin_calculator import MarginCalculator


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "PENDING"
    PLACED = "PLACED"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"


class PositionType(Enum):
    """Position type"""
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


@dataclass
class OrderLeg:
    """Represents a single order leg"""
    symbol: str
    quantity: int
    transaction_type: str  # BUY or SELL
    leg_type: str  # main, hedge, short
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    """Current position state"""
    position_type: PositionType = PositionType.NONE
    entry_time: Optional[datetime] = None
    legs: List[OrderLeg] = field(default_factory=list)
    lot_size: int = 0
    atm_strike: int = 0
    hedge_strike: int = 0


class OrderManager:
    """
    Order Management System for BankNifty Options Trading
    
    Features:
    - NRML orders with MARKET type
    - BUY orders first, then SELL orders
    - Margin calculation and management
    - Sequential lot reduction on margin issues
    - Fast execution for early morning signals
    - All-leg exit and SL execution
    """
    
    def __init__(
        self,
        kite,
        lot_size: int = 8,
        hedge_legs: int = 20,
        logger: Optional[ComponentLogger] = None
    ):
        self.kite = kite
        self.lot_size = lot_size
        self.hedge_legs = hedge_legs  # 20 legs away for margin
        self.logger = logger or ComponentLogger.get_logger("order_manager")
        
        # Margin calculator
        self.margin_calc = MarginCalculator(kite, self.logger)
        
        # Position tracking
        self.position = Position()
        
        # Futures contract tracking
        self.futures_symbol = self._get_current_futures_symbol()
        self.futures_ltp: Optional[float] = None
        self.futures_token: Optional[int] = None
        
        # Order tracking
        self.active_orders: List[OrderLeg] = []
        
        # Pre-calculated margins (for fast execution)
        self._pre_calculated_margins: Optional[Dict] = None
        
        self.logger.info(
            f"OMS initialized",
            lot_size=lot_size,
            hedge_legs=hedge_legs,
            futures_symbol=self.futures_symbol
        )
    
    def _get_current_futures_symbol(self) -> str:
        """Get current month BankNifty futures symbol"""
        now = datetime.now()
        month_map = {
            1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR',
            5: 'MAY', 6: 'JUN', 7: 'JUL', 8: 'AUG',
            9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
        }
        
        year_suffix = str(now.year)[2:]
        month = month_map[now.month]
        
        symbol = f"BANKNIFTY{year_suffix}{month}FUT"
        return symbol
    
    def update_futures_price(self, tick: Dict) -> None:
        """
        Update futures LTP from tick data
        ONLY accepts futures contract ticks (not spot/cash)
        """
        if not self.futures_token:
            self.futures_token = self._get_futures_token()
        
        if self.futures_token and tick.get('instrument_token') == self.futures_token:
            price = tick.get('last_price')
            if price and price > 0:
                self.futures_ltp = price
                self.logger.debug(f"Futures price updated: {self.futures_ltp} (from {self.futures_symbol})")
            else:
                self.logger.warning(f"Invalid futures price in tick: {price}")
    
    def get_futures_price_from_broker(self) -> Optional[float]:
        """
        Get current BankNifty futures price directly from broker
        Uses futures contract only (not spot/cash)
        
        Returns:
            Futures LTP if available, None otherwise
        """
        try:
            if not self.futures_token:
                self.futures_token = self._get_futures_token()
            
            if not self.futures_token:
                self.logger.error("Futures token not found")
                return None
            
            # Get quote for futures contract
            quote = self.kite.quote(f"NFO:{self.futures_symbol}")
            futures_data = quote.get(f"NFO:{self.futures_symbol}", {})
            
            # Get LTP from quote
            ltp = futures_data.get('last_price')
            if ltp and ltp > 0:
                self.futures_ltp = ltp
                self.logger.info(f"Futures price fetched from broker: {ltp} ({self.futures_symbol})")
                return ltp
            else:
                self.logger.warning(f"Invalid futures price from broker: {ltp}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching futures price from broker: {e}", exc_info=True)
            return None
    
    def _get_futures_token(self) -> Optional[int]:
        """
        Get instrument token for futures contract
        ONLY searches for FUTURES contracts (symbol ends with 'FUT')
        """
        try:
            instruments = self.kite.instruments("NFO")
            for inst in instruments:
                # Ensure it's a futures contract (ends with FUT)
                if (inst['tradingsymbol'] == self.futures_symbol and 
                    inst['tradingsymbol'].endswith('FUT')):
                    token = inst['instrument_token']
                    self.logger.info(f"Futures token found: {token} for {self.futures_symbol}")
                    return token
            
            self.logger.error(f"Futures contract not found: {self.futures_symbol}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting futures token: {e}", exc_info=True)
        return None
    
    def _calculate_atm_strike(self, futures_price: float) -> int:
        """
        Calculate ATM strike based on BankNifty FUTURES price (not spot/cash)
        
        Args:
            futures_price: Current BankNifty futures contract price
            
        Returns:
            ATM strike price (rounded to nearest 100)
        """
        if not futures_price or futures_price <= 0:
            raise ValueError(f"Invalid futures price: {futures_price}")
        
        # BankNifty strikes are 100 points apart
        atm_strike = int(round(futures_price / 100) * 100)
        self.logger.debug(f"ATM strike calculated: {atm_strike} from futures price: {futures_price}")
        return atm_strike
    
    def pre_calculate_margins(self) -> bool:
        """
        Pre-calculate margin requirements for the day
        Should be called before market opens or when futures price is available
        
        Returns:
            True if calculation successful
        """
        if not self.futures_ltp:
            self.logger.warning("Cannot pre-calculate margins: No futures price")
            return False
        
        try:
            self._pre_calculated_margins = self.margin_calc.pre_calculate_daily_margins(
                self.futures_ltp,
                self.lot_size
            )
            
            self.logger.info(
                "Margins pre-calculated",
                long_margin=self._pre_calculated_margins['long']['total_margin'],
                short_margin=self._pre_calculated_margins['short']['total_margin']
            )
            return True
        except Exception as e:
            self.logger.error(f"Error pre-calculating margins: {e}", exc_info=True)
            return False
    
    def check_margin_availability(self, position_type: str, lot_size: int) -> Tuple[bool, float]:
        """
        Check if sufficient margin is available
        
        Args:
            position_type: 'LONG' or 'SHORT'
            lot_size: Number of lots to check
            
        Returns:
            Tuple of (is_available, required_margin)
        """
        if not self.futures_ltp:
            return False, 0.0
        
        atm_strike = self._calculate_atm_strike(self.futures_ltp)
        
        if position_type == 'LONG':
            hedge_strike = atm_strike - (self.hedge_legs * 100)
            margin_info = self.margin_calc.calculate_long_margin(
                atm_strike, hedge_strike, lot_size, self.futures_ltp
            )
        else:  # SHORT
            hedge_strike = atm_strike + (self.hedge_legs * 100)
            margin_info = self.margin_calc.calculate_short_margin(
                atm_strike, hedge_strike, lot_size, self.futures_ltp
            )
        
        required_margin = margin_info['total_margin']
        available_margin = self.margin_calc.check_available_margin()
        
        is_available = available_margin >= required_margin
        
        self.logger.info(
            f"Margin check: {position_type}",
            required=required_margin,
            available=available_margin,
            sufficient=is_available,
            lot_size=lot_size
        )
        
        return is_available, required_margin
    
    def enter_long(self, fast_execution: bool = False) -> bool:
        """
        Enter LONG position:
        - BUY ATM CALL (CE)
        - SELL ATM PUT (PE)
        - BUY 20 legs away PUT (PE) for margin
        
        Args:
            fast_execution: If True, use pre-calculated margins and skip checks
            
        Returns:
            True if entry successful
        """
        if self.position.position_type != PositionType.NONE:
            self.logger.warning("Position already exists, cannot enter LONG")
            return False
        
        if not self.futures_ltp:
            self.logger.error("Cannot enter LONG: No futures price available")
            # Try to fetch from broker
            self.get_futures_price_from_broker()
            if not self.futures_ltp:
                return False
        
        # Ensure we're using futures price (not spot/cash)
        if not self.futures_ltp or self.futures_ltp <= 0:
            self.logger.error(f"Invalid futures price: {self.futures_ltp}")
            return False
        
        atm_strike = self._calculate_atm_strike(self.futures_ltp)
        hedge_strike = atm_strike - (self.hedge_legs * 100)
        
        self.logger.info(
            f"🔵 LONG Entry initiated",
            futures_price=self.futures_ltp,
            atm_strike=atm_strike,
            hedge_strike=hedge_strike,
            lot_size=self.lot_size
        )
        
        # Check margin if not fast execution
        if not fast_execution:
            margin_ok, _ = self.check_margin_availability('LONG', self.lot_size)
            if not margin_ok:
                self.logger.warning("Insufficient margin for LONG entry")
                return False
        
        # Try with full lot size, reduce if margin issues occur
        current_lot_size = self.lot_size
        success = False
        
        while current_lot_size > 0:
            try:
                # Step 1: Execute all BUY legs first
                buy_legs = [
                    OrderLeg(
                        symbol=f"BANKNIFTY{atm_strike}CE",
                        quantity=current_lot_size * 15,  # 15 units per lot
                        transaction_type="BUY",
                        leg_type="main"
                    ),
                    OrderLeg(
                        symbol=f"BANKNIFTY{hedge_strike}PE",
                        quantity=current_lot_size * 15,
                        transaction_type="BUY",
                        leg_type="hedge"
                    )
                ]
                
                buy_success = self._execute_legs(buy_legs, "BUY")
                
                if not buy_success:
                    self.logger.warning(f"BUY legs failed for lot_size={current_lot_size}")
                    # Exit any partial positions
                    self._exit_partial_positions()
                    # Try with half lot size
                    current_lot_size = current_lot_size // 2
                    continue
                
                # Step 2: Execute SELL leg after buys complete
                sell_legs = [
                    OrderLeg(
                        symbol=f"BANKNIFTY{atm_strike}PE",
                        quantity=current_lot_size * 15,
                        transaction_type="SELL",
                        leg_type="short"
                    )
                ]
                
                sell_success = self._execute_legs(sell_legs, "SELL", allow_partial=True)
                
                if not sell_success:
                    self.logger.warning(f"SELL leg failed for lot_size={current_lot_size}")
                    # If sell fails, we still have buy positions, try to exit
                    # But first try with reduced lot size
                    current_lot_size = current_lot_size // 2
                    if current_lot_size > 0:
                        # Exit current buy positions and retry
                        self._exit_partial_positions()
                        continue
                    else:
                        # Exit everything
                        self._exit_partial_positions()
                        return False
                
                # Success - update position
                self.position.position_type = PositionType.LONG
                self.position.entry_time = datetime.now()
                self.position.lot_size = current_lot_size
                self.position.atm_strike = atm_strike
                self.position.hedge_strike = hedge_strike
                self.position.legs = buy_legs + sell_legs
                
                self.logger.info(
                    f"✅ LONG position established",
                    lot_size=current_lot_size,
                    atm_strike=atm_strike
                )
                
                success = True
                break
                
            except Exception as e:
                self.logger.error(f"Error in LONG entry: {e}", exc_info=True)
                self._exit_partial_positions()
                current_lot_size = current_lot_size // 2
                if current_lot_size == 0:
                    return False
        
        return success
    
    def enter_short(self, fast_execution: bool = False) -> bool:
        """
        Enter SHORT position:
        - BUY ATM PUT (PE)
        - SELL ATM CALL (CE)
        - BUY 20 legs away CALL (CE) for margin
        
        Args:
            fast_execution: If True, use pre-calculated margins and skip checks
            
        Returns:
            True if entry successful
        """
        if self.position.position_type != PositionType.NONE:
            self.logger.warning("Position already exists, cannot enter SHORT")
            return False
        
        if not self.futures_ltp:
            self.logger.error("Cannot enter SHORT: No futures price available")
            # Try to fetch from broker
            self.get_futures_price_from_broker()
            if not self.futures_ltp:
                return False
        
        # Ensure we're using futures price (not spot/cash)
        if not self.futures_ltp or self.futures_ltp <= 0:
            self.logger.error(f"Invalid futures price: {self.futures_ltp}")
            return False
        
        atm_strike = self._calculate_atm_strike(self.futures_ltp)
        hedge_strike = atm_strike + (self.hedge_legs * 100)
        
        self.logger.info(
            f"🔴 SHORT Entry initiated",
            futures_price=self.futures_ltp,
            atm_strike=atm_strike,
            hedge_strike=hedge_strike,
            lot_size=self.lot_size
        )
        
        # Check margin if not fast execution
        if not fast_execution:
            margin_ok, _ = self.check_margin_availability('SHORT', self.lot_size)
            if not margin_ok:
                self.logger.warning("Insufficient margin for SHORT entry")
                return False
        
        # Try with full lot size, reduce if margin issues occur
        current_lot_size = self.lot_size
        success = False
        
        while current_lot_size > 0:
            try:
                # Step 1: Execute all BUY legs first
                buy_legs = [
                    OrderLeg(
                        symbol=f"BANKNIFTY{atm_strike}PE",
                        quantity=current_lot_size * 15,
                        transaction_type="BUY",
                        leg_type="main"
                    ),
                    OrderLeg(
                        symbol=f"BANKNIFTY{hedge_strike}CE",
                        quantity=current_lot_size * 15,
                        transaction_type="BUY",
                        leg_type="hedge"
                    )
                ]
                
                buy_success = self._execute_legs(buy_legs, "BUY")
                
                if not buy_success:
                    self.logger.warning(f"BUY legs failed for lot_size={current_lot_size}")
                    self._exit_partial_positions()
                    current_lot_size = current_lot_size // 2
                    continue
                
                # Step 2: Execute SELL leg after buys complete
                sell_legs = [
                    OrderLeg(
                        symbol=f"BANKNIFTY{atm_strike}CE",
                        quantity=current_lot_size * 15,
                        transaction_type="SELL",
                        leg_type="short"
                    )
                ]
                
                sell_success = self._execute_legs(sell_legs, "SELL", allow_partial=True)
                
                if not sell_success:
                    self.logger.warning(f"SELL leg failed for lot_size={current_lot_size}")
                    current_lot_size = current_lot_size // 2
                    if current_lot_size > 0:
                        self._exit_partial_positions()
                        continue
                    else:
                        self._exit_partial_positions()
                        return False
                
                # Success - update position
                self.position.position_type = PositionType.SHORT
                self.position.entry_time = datetime.now()
                self.position.lot_size = current_lot_size
                self.position.atm_strike = atm_strike
                self.position.hedge_strike = hedge_strike
                self.position.legs = buy_legs + sell_legs
                
                self.logger.info(
                    f"✅ SHORT position established",
                    lot_size=current_lot_size,
                    atm_strike=atm_strike
                )
                
                success = True
                break
                
            except Exception as e:
                self.logger.error(f"Error in SHORT entry: {e}", exc_info=True)
                self._exit_partial_positions()
                current_lot_size = current_lot_size // 2
                if current_lot_size == 0:
                    return False
        
        return success
    
    def exit_position(self) -> bool:
        """
        Exit all positions - all legs executed together
        Uses MARKET orders with NRML
        
        Returns:
            True if exit successful
        """
        if self.position.position_type == PositionType.NONE:
            self.logger.warning("No position to exit")
            return False
        
        self.logger.info(f"⏹️ Exiting {self.position.position_type.value} position")
        
        try:
            # Get all current positions from broker
            positions = self.kite.positions()['net']
            
            exit_legs = []
            
            # Create exit orders for all legs
            for pos in positions:
                if 'BANKNIFTY' in pos['tradingsymbol'] and pos['quantity'] != 0:
                    # Determine exit transaction type
                    exit_type = 'SELL' if pos['quantity'] > 0 else 'BUY'
                    exit_qty = abs(pos['quantity'])
                    
                    exit_leg = OrderLeg(
                        symbol=pos['tradingsymbol'],
                        quantity=exit_qty,
                        transaction_type=exit_type,
                        leg_type="exit"
                    )
                    exit_legs.append(exit_leg)
            
            # Execute all exit legs together
            success = self._execute_legs(exit_legs, "EXIT", execute_together=True)
            
            if success:
                # Reset position
                self.position = Position()
                self.logger.info("✅ All positions exited")
            else:
                self.logger.error("⚠️ Partial exit - some positions may remain")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error exiting position: {e}", exc_info=True)
            return False
    
    def execute_stop_loss(self) -> bool:
        """
        Execute stop loss - same as exit, all legs together
        
        Returns:
            True if SL executed successfully
        """
        self.logger.warning("🛑 Stop Loss triggered")
        return self.exit_position()
    
    def _execute_legs(
        self,
        legs: List[OrderLeg],
        leg_group: str,
        allow_partial: bool = False,
        execute_together: bool = False
    ) -> bool:
        """
        Execute multiple order legs
        
        Args:
            legs: List of OrderLeg objects
            leg_group: Group name for logging (BUY, SELL, EXIT)
            allow_partial: If True, partial fills are acceptable (for SELL legs)
            execute_together: If True, place all orders simultaneously
            
        Returns:
            True if all legs executed successfully
        """
        if not legs:
            return True
        
        self.logger.debug(f"Executing {leg_group} legs: {len(legs)} orders")
        
        if execute_together:
            # Place all orders simultaneously
            order_ids = []
            for leg in legs:
                try:
                    order_id = self._place_market_order(
                        leg.symbol,
                        leg.quantity,
                        leg.transaction_type
                    )
                    if order_id:
                        leg.order_id = order_id
                        leg.status = OrderStatus.PLACED
                        order_ids.append(order_id)
                except Exception as e:
                    self.logger.error(f"Failed to place order for {leg.symbol}: {e}")
                    leg.status = OrderStatus.REJECTED
            
            # Wait for all orders to complete
            time.sleep(1)  # Give orders time to execute
            
            # Check status of all orders
            all_success = True
            for leg in legs:
                if leg.order_id:
                    status = self._check_order_status(leg.order_id)
                    leg.status = status
                    if status == OrderStatus.COMPLETE:
                        # Get filled quantity and price
                        leg.filled_quantity, leg.average_price = self._get_order_details(leg.order_id)
                    elif status == OrderStatus.REJECTED:
                        all_success = False
                        if not allow_partial:
                            break
            
            return all_success if not allow_partial else True
            
        else:
            # Execute sequentially
            for leg in legs:
                try:
                    order_id = self._place_market_order(
                        leg.symbol,
                        leg.quantity,
                        leg.transaction_type
                    )
                    
                    if not order_id:
                        self.logger.error(f"Failed to place order for {leg.symbol}")
                        leg.status = OrderStatus.REJECTED
                        if not allow_partial:
                            return False
                        continue
                    
                    leg.order_id = order_id
                    leg.status = OrderStatus.PLACED
                    
                    # Wait for order to complete
                    time.sleep(0.5)  # Small delay between orders
                    
                    # Check order status
                    status = self._check_order_status(order_id)
                    leg.status = status
                    
                    if status == OrderStatus.COMPLETE:
                        leg.filled_quantity, leg.average_price = self._get_order_details(order_id)
                        self.logger.info(
                            f"✅ {leg.transaction_type} {leg.quantity} {leg.symbol} @ {leg.average_price}"
                        )
                    elif status == OrderStatus.REJECTED:
                        self.logger.error(f"❌ Order rejected: {leg.symbol}")
                        if not allow_partial:
                            return False
                    elif status == OrderStatus.PARTIAL:
                        leg.filled_quantity, leg.average_price = self._get_order_details(order_id)
                        self.logger.warning(
                            f"⚠️ Partial fill: {leg.filled_quantity}/{leg.quantity} {leg.symbol}"
                        )
                        if not allow_partial:
                            return False
                    
                except Exception as e:
                    self.logger.error(f"Error executing leg {leg.symbol}: {e}", exc_info=True)
                    leg.status = OrderStatus.REJECTED
                    if not allow_partial:
                        return False
            
            return True
    
    def _place_market_order(
        self,
        symbol: str,
        quantity: int,
        transaction_type: str
    ) -> Optional[str]:
        """
        Place MARKET order with NRML product
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            transaction_type: BUY or SELL
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=self.kite.PRODUCT_NRML,  # NRML for options
                order_type=self.kite.ORDER_TYPE_MARKET
            )
            
            self.logger.debug(
                f"Order placed: {transaction_type} {quantity} {symbol}",
                order_id=order_id
            )
            
            return str(order_id)
            
        except Exception as e:
            self.logger.error(
                f"Failed to place order: {symbol}",
                error=str(e),
                exc_info=True
            )
            return None
    
    def _check_order_status(self, order_id: str) -> OrderStatus:
        """Check order status from broker"""
        try:
            orders = self.kite.orders()
            for order in orders:
                if str(order['order_id']) == str(order_id):
                    status = order['status']
                    
                    if status == 'COMPLETE':
                        return OrderStatus.COMPLETE
                    elif status == 'REJECTED':
                        return OrderStatus.REJECTED
                    elif status == 'CANCELLED':
                        return OrderStatus.CANCELLED
                    elif status == 'OPEN' or status == 'TRIGGER PENDING':
                        # Check if partially filled
                        if order.get('filled_quantity', 0) > 0:
                            return OrderStatus.PARTIAL
                        return OrderStatus.PLACED
                    else:
                        return OrderStatus.PENDING
        except Exception as e:
            self.logger.error(f"Error checking order status: {e}", exc_info=True)
        
        return OrderStatus.PENDING
    
    def _get_order_details(self, order_id: str) -> Tuple[int, float]:
        """Get filled quantity and average price for an order"""
        try:
            orders = self.kite.orders()
            for order in orders:
                if str(order['order_id']) == str(order_id):
                    filled_qty = order.get('filled_quantity', 0)
                    avg_price = order.get('average_price', 0.0)
                    return int(filled_qty), float(avg_price)
        except Exception as e:
            self.logger.error(f"Error getting order details: {e}", exc_info=True)
        
        return 0, 0.0
    
    def _exit_partial_positions(self) -> None:
        """Exit any partially filled positions"""
        try:
            positions = self.kite.positions()['net']
            for pos in positions:
                if 'BANKNIFTY' in pos['tradingsymbol'] and pos['quantity'] != 0:
                    exit_type = 'SELL' if pos['quantity'] > 0 else 'BUY'
                    exit_qty = abs(pos['quantity'])
                    
                    self._place_market_order(
                        pos['tradingsymbol'],
                        exit_qty,
                        exit_type
                    )
            
            self.logger.info("Exited partial positions")
        except Exception as e:
            self.logger.error(f"Error exiting partial positions: {e}", exc_info=True)
    
    def get_position_status(self) -> Dict:
        """Get current position status"""
        return {
            'position_type': self.position.position_type.value,
            'entry_time': self.position.entry_time.isoformat() if self.position.entry_time else None,
            'lot_size': self.position.lot_size,
            'atm_strike': self.position.atm_strike,
            'hedge_strike': self.position.hedge_strike,
            'num_legs': len(self.position.legs)
        }

