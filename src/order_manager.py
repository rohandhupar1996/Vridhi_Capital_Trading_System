"""
Order Management Module
"""

import time
import logging
import concurrent.futures
from typing import Tuple, Dict, List
from config import CONFIG

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order placement and verification"""
    
    def __init__(self, client):
        """
        Initialize Order Manager
        
        Args:
            client: OpenAlgoClient instance
        """
        self.client = client
        self.config = CONFIG
    
    def wait_for_order_completion(self, order_id: str, max_wait: int = None) -> bool:
        """
        Poll order status until completion or timeout
        
        Args:
            order_id: Order ID to check
            max_wait: Maximum seconds to wait
        
        Returns:
            True if order completed successfully, False otherwise
        """
        max_wait = max_wait or self.config['max_order_wait']
        start_time = time.time()
        poll_count = 0
        
        while (time.time() - start_time) < max_wait:
            try:
                response = self.client.get_order_status(
                    order_id=order_id,
                    strategy=self.config['strategy_name']
                )
                
                poll_count += 1
                
                if response['status'] == 'success':
                    order_status = response['data']['order_status'].lower()
                    
                    logger.debug(f"Order {order_id} status: {order_status} (poll #{poll_count})")
                    
                    if order_status == 'complete':
                        logger.info(f"✅ Order {order_id} completed successfully")
                        return True
                        
                    elif order_status in ['rejected', 'cancelled']:
                        logger.error(f"❌ Order {order_id} failed with status: {order_status}")
                        return False
                else:
                    logger.warning(f"⚠️ Failed to get status for order {order_id}: {response}")
                
                time.sleep(self.config['order_poll_interval'])
                
            except Exception as e:
                logger.error(f"❌ Exception checking order {order_id}: {str(e)}")
                time.sleep(self.config['order_poll_interval'])
        
        logger.error(f"❌ Order {order_id} TIMEOUT after {max_wait}s ({poll_count} polls)")
        return False
    
    def place_order(self, offset: str, option_type: str, action: str, expiry: str) -> Tuple[bool, Dict]:
        """
        Place a single option order
        
        Args:
            offset: ATM, OTM20, etc.
            option_type: CE or PE
            action: BUY or SELL
            expiry: Expiry date
        
        Returns:
            (success: bool, response: dict)
        """
        try:
            logger.info(f"📤 Placing order: {action} {offset} {option_type}")
            
            response = self.client.place_options_order(
                strategy=self.config['strategy_name'],
                underlying=self.config['underlying'],
                exchange=self.config['exchange'],
                expiry_date=expiry,
                offset=offset,
                option_type=option_type,
                action=action,
                quantity=self.config['lot_size'],
                pricetype="MARKET",
                product=self.config['product']
            )
            
            logger.info(f"📥 Order response: {response}")
            
            if response.get('status') != 'success':
                logger.error(f"❌ Order placement failed: {response}")
                return False, response
            
            order_id = response.get('orderid')
            if not order_id:
                logger.error(f"❌ No order ID in response: {response}")
                return False, response
            
            # Add order details to response for tracking
            response['order_details'] = {
                'offset': offset,
                'option_type': option_type,
                'action': action,
                'symbol': response.get('symbol', 'Unknown')
            }
            
            return True, response
            
        except Exception as e:
            logger.error(f"❌ Exception placing order: {str(e)}")
            return False, {"status": "error", "message": str(e)}
    
    def place_and_verify_order(self, offset: str, option_type: str, action: str, expiry: str) -> Tuple[bool, Dict]:
        """
        Place order and wait for completion
        
        Returns:
            (success: bool, response: dict)
        """
        success, response = self.place_order(offset, option_type, action, expiry)
        
        if not success:
            return False, response
        
        order_id = response.get('orderid')
        
        # Wait for order completion
        completed = self.wait_for_order_completion(order_id)
        
        response['verified'] = completed
        
        return completed, response
    
    def execute_buy_orders_parallel(self, buy_orders: List[Dict], expiry: str) -> Tuple[bool, List[Dict]]:
        """
        Execute multiple BUY orders in parallel
        
        Args:
            buy_orders: List of dicts with 'offset', 'option_type', 'action'
            expiry: Expiry date
        
        Returns:
            (all_success: bool, results: list of response dicts)
        """
        logger.info("=" * 70)
        logger.info(f"🚀 EXECUTING {len(buy_orders)} BUY ORDERS IN PARALLEL")
        logger.info("=" * 70)
        
        results = []
        
        # Execute all BUY orders in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(buy_orders)) as executor:
            # Submit all orders
            futures = {}
            for order in buy_orders:
                future = executor.submit(
                    self.place_and_verify_order,
                    order['offset'],
                    order['option_type'],
                    order['action'],
                    expiry
                )
                futures[future] = f"BUY_{order['offset']}_{order['option_type']}"
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                order_name = futures[future]
                try:
                    success, response = future.result()
                    results.append({
                        'order_name': order_name,
                        'success': success,
                        'response': response
                    })
                    
                    if success:
                        logger.info(f"✅ {order_name} completed successfully")
                    else:
                        logger.error(f"❌ {order_name} FAILED")
                        
                except Exception as e:
                    logger.error(f"❌ {order_name} exception: {str(e)}")
                    results.append({
                        'order_name': order_name,
                        'success': False,
                        'response': {'status': 'error', 'message': str(e)}
                    })
        
        # Check if ALL BUY orders succeeded
        all_success = all(r['success'] for r in results)
        
        logger.info("=" * 70)
        if all_success:
            logger.info(f"✅ ALL {len(buy_orders)} BUY ORDERS COMPLETED SUCCESSFULLY")
        else:
            failed = [r['order_name'] for r in results if not r['success']]
            logger.error(f"❌ {len(failed)} BUY ORDER(S) FAILED: {failed}")
        logger.info("=" * 70)
        
        return all_success, results

