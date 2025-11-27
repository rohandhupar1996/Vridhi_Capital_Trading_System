"""
Position Execution Module
"""

import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class PositionExecutor:
    """Executes trading positions"""
    
    def __init__(self, order_manager, telegram_notifier=None):
        """
        Initialize Position Executor
        
        Args:
            order_manager: OrderManager instance
            telegram_notifier: TelegramNotifier instance (optional)
        """
        self.order_manager = order_manager
        self.telegram = telegram_notifier
    
    def execute_long_position(self, expiry: str) -> Dict:
        """
        Execute LONG position:
        1. BUY ATM Call (parallel)
        2. BUY OTM20 Put (parallel)
        3. Wait for both to complete
        4. SELL ATM Put (sequential)
        
        Total time: ~3-5 seconds
        """
        try:
            logger.info("=" * 70)
            logger.info("📈 EXECUTING LONG POSITION")
            logger.info(f"Expiry: {expiry}")
            logger.info("=" * 70)
            
            # Send signal alert
            if self.telegram:
                self.telegram.send_signal_alert("LONG", expiry)
            
            start_time = time.time()
            
            # Define BUY orders
            buy_orders = [
                {'offset': 'ATM', 'option_type': 'CE', 'action': 'BUY'},
                {'offset': 'OTM20', 'option_type': 'PE', 'action': 'BUY'}
            ]
            
            # Execute BUY orders in parallel
            all_buys_success, buy_results = self.order_manager.execute_buy_orders_parallel(buy_orders, expiry)
            
            if not all_buys_success:
                logger.error("❌ BUY orders failed! ABORTING LONG position.")
                logger.warning("⚠️ Check your positions - you may have partial BUY orders!")
                
                # Send failure alert
                if self.telegram:
                    self.telegram.send_execution_failure("LONG", "BUY orders failed")
                
                return {
                    "status": "error",
                    "message": "BUY orders failed - position aborted",
                    "signal": "LONG",
                    "expiry": expiry,
                    "buy_orders": buy_results,
                    "execution_time": f"{time.time() - start_time:.2f}s"
                }
            
            # All BUYs successful - safe to SELL
            logger.info("🔒 ALL BUY ORDERS COMPLETED. SAFE TO EXECUTE SELL ORDER.")
            time.sleep(0.5)  # Small buffer
            
            # Execute SELL order
            sell_success, sell_response = self.order_manager.place_and_verify_order('ATM', 'PE', 'SELL', expiry)
            
            if not sell_success:
                logger.error("❌ SELL ATM PE FAILED!")
                logger.warning("⚠️ You have incomplete position - 2 BUYs without SELL hedge")
                
                # Send partial execution alert
                if self.telegram:
                    self.telegram.send_partial_execution("LONG", buy_results)
                
                return {
                    "status": "partial",
                    "message": "SELL ATM PE failed - position incomplete",
                    "signal": "LONG",
                    "expiry": expiry,
                    "buy_orders": buy_results,
                    "sell_order": sell_response,
                    "execution_time": f"{time.time() - start_time:.2f}s"
                }
            
            execution_time = time.time() - start_time
            
            logger.info("=" * 70)
            logger.info(f"✅ LONG POSITION COMPLETED SUCCESSFULLY in {execution_time:.2f}s")
            logger.info("=" * 70)
            
            # Send success alert
            if self.telegram:
                self.telegram.send_execution_success(
                    "LONG", expiry, buy_results, sell_response, execution_time
                )
            
            return {
                "status": "success",
                "signal": "LONG",
                "expiry": expiry,
                "buy_orders": buy_results,
                "sell_order": sell_response,
                "execution_time": f"{execution_time:.2f}s"
            }
            
        except Exception as e:
            logger.error(f"❌ Exception in LONG execution: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "signal": "LONG"
            }
    
    def execute_short_position(self, expiry: str) -> Dict:
        """
        Execute SHORT position:
        1. BUY ATM Put (parallel)
        2. BUY OTM20 Call (parallel)
        3. Wait for both to complete
        4. SELL ATM Call (sequential)
        
        Total time: ~3-5 seconds
        """
        try:
            logger.info("=" * 70)
            logger.info("📉 EXECUTING SHORT POSITION")
            logger.info(f"Expiry: {expiry}")
            logger.info("=" * 70)
            
            # Send signal alert
            if self.telegram:
                self.telegram.send_signal_alert("SHORT", expiry)
            
            start_time = time.time()
            
            # Define BUY orders
            buy_orders = [
                {'offset': 'ATM', 'option_type': 'PE', 'action': 'BUY'},
                {'offset': 'OTM20', 'option_type': 'CE', 'action': 'BUY'}
            ]
            
            # Execute BUY orders in parallel
            all_buys_success, buy_results = self.order_manager.execute_buy_orders_parallel(buy_orders, expiry)
            
            if not all_buys_success:
                logger.error("❌ BUY orders failed! ABORTING SHORT position.")
                logger.warning("⚠️ Check your positions - you may have partial BUY orders!")
                
                # Send failure alert
                if self.telegram:
                    self.telegram.send_execution_failure("SHORT", "BUY orders failed")
                
                return {
                    "status": "error",
                    "message": "BUY orders failed - position aborted",
                    "signal": "SHORT",
                    "expiry": expiry,
                    "buy_orders": buy_results,
                    "execution_time": f"{time.time() - start_time:.2f}s"
                }
            
            # All BUYs successful - safe to SELL
            logger.info("🔒 ALL BUY ORDERS COMPLETED. SAFE TO EXECUTE SELL ORDER.")
            time.sleep(0.5)  # Small buffer
            
            # Execute SELL order
            sell_success, sell_response = self.order_manager.place_and_verify_order('ATM', 'CE', 'SELL', expiry)
            
            if not sell_success:
                logger.error("❌ SELL ATM CE FAILED!")
                logger.warning("⚠️ You have incomplete position - 2 BUYs without SELL hedge")
                
                # Send partial execution alert
                if self.telegram:
                    self.telegram.send_partial_execution("SHORT", buy_results)
                
                return {
                    "status": "partial",
                    "message": "SELL ATM CE failed - position incomplete",
                    "signal": "SHORT",
                    "expiry": expiry,
                    "buy_orders": buy_results,
                    "sell_order": sell_response,
                    "execution_time": f"{time.time() - start_time:.2f}s"
                }
            
            execution_time = time.time() - start_time
            
            logger.info("=" * 70)
            logger.info(f"✅ SHORT POSITION COMPLETED SUCCESSFULLY in {execution_time:.2f}s")
            logger.info("=" * 70)
            
            # Send success alert
            if self.telegram:
                self.telegram.send_execution_success(
                    "SHORT", expiry, buy_results, sell_response, execution_time
                )
            
            return {
                "status": "success",
                "signal": "SHORT",
                "expiry": expiry,
                "buy_orders": buy_results,
                "sell_order": sell_response,
                "execution_time": f"{execution_time:.2f}s"
            }
            
        except Exception as e:
            logger.error(f"❌ Exception in SHORT execution: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "signal": "SHORT"
            }
    
    def close_all_positions(self, strategy: str) -> Dict:
        """Close all open positions for the strategy"""
        try:
            logger.info("🔴 CLOSING ALL POSITIONS")
            
            # Send exit alert
            if self.telegram:
                self.telegram.send_exit_alert()
            
            response = self.order_manager.client.close_position(strategy)
            logger.info(f"Close position response: {response}")
            return response
        except Exception as e:
            logger.error(f"❌ Error closing positions: {str(e)}")
            return {"status": "error", "message": str(e)}

