"""
Example usage of Order Management System (OMS)
Shows how to integrate OMS with trading signals
"""

from typing import Optional
from ..broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials
from ..logging import ComponentLogger
from .order_manager import OrderManager


def initialize_oms() -> Optional[OrderManager]:
    """
    Initialize OMS with Zerodha connection
    
    Returns:
        OrderManager instance if successful, None otherwise
    """
    # OMS configuration (can be customized)
    oms_config = {
        'lot_size': 8,
        'hedge_legs': 20,
    }
    
    # Initialize logger
    logger = ComponentLogger.get_logger("oms_example")
    
    # Initialize Zerodha authentication
    # Note: In production, load credentials from secure storage
    credentials = ZerodhaCredentials(
        api_key="your_api_key",  # Load from environment or secure storage
        api_secret="your_api_secret"
    )
    
    authenticator = ZerodhaAuthenticator(
        credentials=credentials,
        logger=ComponentLogger.get_logger("zerodha_auth")
    )
    
    # Login
    if not authenticator.login():
        logger.error("Failed to authenticate with Zerodha")
        return None
    
    kite = authenticator.get_kite_instance()
    if not kite:
        logger.error("Failed to get Kite instance")
        return None
    
    # Initialize OMS
    oms = OrderManager(
        kite=kite,
        lot_size=oms_config.get('lot_size', 8),
        hedge_legs=oms_config.get('hedge_legs', 20),
        logger=ComponentLogger.get_logger("order_manager")
    )
    
    logger.info("OMS initialized successfully")
    return oms


def handle_trading_signal(oms: OrderManager, signal_type: str, futures_price: float):
    """
    Handle trading signal from strategy
    
    Args:
        oms: OrderManager instance
        signal_type: 'LONG', 'SHORT', 'EXIT', or 'SL'
        futures_price: Current futures price
    """
    logger = ComponentLogger.get_logger("signal_handler")
    
    # Update futures price in OMS
    oms.futures_ltp = futures_price
    
    # Pre-calculate margins for fast execution (optional, but recommended)
    # This can be done before market opens or when futures price is available
    if oms._pre_calculated_margins is None:
        logger.info("Pre-calculating margins for fast execution")
        oms.pre_calculate_margins()
    
    if signal_type == 'LONG':
        logger.info("Received LONG signal")
        
        # Check if position already exists
        if oms.position.position_type.value != 'NONE':
            logger.warning("Position already exists, ignoring signal")
            return
        
        # Enter LONG position
        # Use fast_execution=True if margins were pre-calculated
        success = oms.enter_long(fast_execution=True)
        
        if success:
            logger.info("LONG position entered successfully")
        else:
            logger.error("Failed to enter LONG position")
    
    elif signal_type == 'SHORT':
        logger.info("Received SHORT signal")
        
        if oms.position.position_type.value != 'NONE':
            logger.warning("Position already exists, ignoring signal")
            return
        
        # Enter SHORT position
        success = oms.enter_short(fast_execution=True)
        
        if success:
            logger.info("SHORT position entered successfully")
        else:
            logger.error("Failed to enter SHORT position")
    
    elif signal_type == 'EXIT':
        logger.info("Received EXIT signal")
        
        # Exit all positions
        success = oms.exit_position()
        
        if success:
            logger.info("Position exited successfully")
        else:
            logger.error("Failed to exit position")
    
    elif signal_type == 'SL':
        logger.warning("Received STOP LOSS signal")
        
        # Execute stop loss
        success = oms.execute_stop_loss()
        
        if success:
            logger.info("Stop loss executed successfully")
        else:
            logger.error("Failed to execute stop loss")
    
    else:
        logger.warning(f"Unknown signal type: {signal_type}")


def example_early_morning_setup(oms: OrderManager, futures_price: float):
    """
    Example setup for early morning (9:15 AM) signal handling
    Pre-calculates margins to enable fast execution
    
    Args:
        oms: OrderManager instance
        futures_price: Current futures price
    """
    logger = ComponentLogger.get_logger("early_morning_setup")
    
    logger.info("Setting up OMS for early morning trading")
    
    # Update futures price
    oms.futures_ltp = futures_price
    
    # Pre-calculate margins for both LONG and SHORT
    # This takes 1-2 seconds but enables instant execution when signal arrives
    logger.info("Pre-calculating margins (this may take 1-2 seconds)...")
    success = oms.pre_calculate_margins()
    
    if success:
        logger.info("✅ Margins pre-calculated - ready for fast execution")
        logger.info(f"LONG margin: {oms._pre_calculated_margins['long']['total_margin']:.2f}")
        logger.info(f"SHORT margin: {oms._pre_calculated_margins['short']['total_margin']:.2f}")
    else:
        logger.warning("⚠️ Failed to pre-calculate margins - will calculate on-the-fly")
    
    # Check available margin
    available = oms.margin_calc.check_available_margin()
    logger.info(f"Available margin: {available:.2f}")


def example_tick_handler(oms: OrderManager, tick: dict):
    """
    Handle tick data from WebSocket or data feed
    Updates futures price in OMS
    
    Args:
        oms: OrderManager instance
        tick: Tick data dictionary with instrument_token and last_price
    """
    # Update futures price if this is futures tick
    oms.update_futures_price(tick)


# Example integration with trading system
if __name__ == "__main__":
    # Initialize OMS
    oms = initialize_oms()
    
    if not oms:
        print("Failed to initialize OMS")
        exit(1)
    
    # Example: Early morning setup (9:15 AM)
    # Get futures price from market data
    futures_price = 50000.0  # Example price
    example_early_morning_setup(oms, futures_price)
    
    # Example: Handle LONG signal
    handle_trading_signal(oms, 'LONG', futures_price)
    
    # Example: Handle EXIT signal
    # handle_trading_signal(oms, 'EXIT', futures_price)
    
    # Example: Handle STOP LOSS signal
    # handle_trading_signal(oms, 'SL', futures_price)
    
    # Get position status
    status = oms.get_position_status()
    print(f"Position Status: {status}")

