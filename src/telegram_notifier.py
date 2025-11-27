"""
Telegram Notification Module
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List
from config import TELEGRAM_CONFIG

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles Telegram notifications via OpenAlgo"""
    
    def __init__(self, openalgo_client):
        """
        Initialize Telegram Notifier
        
        Args:
            openalgo_client: OpenAlgoClient instance
        """
        self.client = openalgo_client
        self.config = TELEGRAM_CONFIG
        self.pnl_thread = None
        
        if self.config['enabled']:
            logger.info("✅ Telegram notifications enabled")
            if self.config['send_pnl_updates']:
                self._start_pnl_updates()
        else:
            logger.info("⚠️ Telegram notifications disabled")
    
    def send_message(self, message: str) -> bool:
        """
        Send a message to Telegram
        
        Args:
            message: Message text to send
            
        Returns:
            True if successful, False otherwise
        """
        if not self.config['enabled']:
            logger.debug("Telegram disabled - message not sent")
            return False
        
        try:
            response = self.client.client.telegram(
                username=self.config['username'],
                message=message
            )
            
            if response.get('status') == 'success':
                logger.info(f"✅ Telegram message sent")
                return True
            else:
                logger.warning(f"⚠️ Telegram send failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Telegram error: {str(e)}")
            return False
    
    def send_signal_alert(self, signal: str, expiry: str):
        """
        Send alert when LONG/SHORT signal is received
        
        Args:
            signal: LONG or SHORT
            expiry: Expiry date
        """
        if not self.config['send_signal_alerts']:
            return
        
        emoji = "🟢" if signal == "LONG" else "🔴"
        message = f"{emoji} {signal} Signal Received!\n📅 Expiry: {expiry}"
        self.send_message(message)
    
    def send_execution_success(self, signal: str, expiry: str, buy_results: List[Dict], 
                               sell_response: Dict, execution_time: float):
        """
        Send alert when position is successfully executed
        
        Args:
            signal: LONG or SHORT
            expiry: Expiry date
            buy_results: List of BUY order results
            sell_response: SELL order response
            execution_time: Execution time in seconds
        """
        if not self.config['send_execution_alerts']:
            return
        
        emoji = "🎯" if signal == "LONG" else "🎯"
        
        # Extract symbols from results
        buy_symbols = []
        for result in buy_results:
            symbol = result.get('response', {}).get('symbol', 'Unknown')
            buy_symbols.append(symbol)
        
        sell_symbol = sell_response.get('symbol', 'Unknown')
        
        message = f"""
{emoji} {signal} Position COMPLETE!
━━━━━━━━━━━━━━━━━━
⏱ Execution: {execution_time:.2f}s
📅 Expiry: {expiry}

📥 BUY Orders:
{chr(10).join([f"  • {sym}" for sym in buy_symbols])}

📤 SELL Order:
  • {sell_symbol}

💰 Check /pnl for P&L
        """
        
        self.send_message(message.strip())
    
    def send_execution_failure(self, signal: str, reason: str):
        """
        Send alert when position execution fails
        
        Args:
            signal: LONG or SHORT
            reason: Failure reason
        """
        if not self.config['send_execution_alerts']:
            return
        
        message = f"""
❌ {signal} Position FAILED!
━━━━━━━━━━━━━━━━━━
Reason: {reason}

⚠️ Check your positions immediately!
        """
        
        self.send_message(message.strip())
    
    def send_partial_execution(self, signal: str, buy_results: List[Dict]):
        """
        Send alert when position is partially executed (BUYs done, SELL failed)
        
        Args:
            signal: LONG or SHORT
            buy_results: List of BUY order results
        """
        if not self.config['send_execution_alerts']:
            return
        
        buy_symbols = []
        for result in buy_results:
            symbol = result.get('response', {}).get('symbol', 'Unknown')
            buy_symbols.append(symbol)
        
        message = f"""
⚠️ {signal} Position INCOMPLETE!
━━━━━━━━━━━━━━━━━━
BUY orders completed:
{chr(10).join([f"  • {sym}" for sym in buy_symbols])}

❌ SELL order FAILED!

🚨 URGENT: You have unhedged BUY positions!
Check your positions immediately!
        """
        
        self.send_message(message.strip())
    
    def send_exit_alert(self):
        """Send alert when all positions are closed"""
        if not self.config['send_execution_alerts']:
            return
        
        message = "🔴 EXIT Signal - Closing all positions..."
        self.send_message(message)
    
    def send_pnl_update(self):
        """Send current P&L to Telegram"""
        if not self.config['send_pnl_updates']:
            return
        
        try:
            # Get positions
            positions = self.client.get_positions()
            
            if positions.get('status') != 'success':
                logger.warning("Failed to fetch positions for P&L update")
                return
            
            position_data = positions.get('data', [])
            
            if not position_data:
                message = """
📊 Current Positions P&L
━━━━━━━━━━━━━━━━━━
No open positions
💰 Total P&L: ₹0.00
                """
                self.send_message(message.strip())
                return
            
            total_pnl = 0
            position_details = []
            
            for pos in position_data:
                symbol = pos.get('symbol', 'Unknown')
                pnl = float(pos.get('pnl', 0))
                total_pnl += pnl
                
                # Format with emoji based on profit/loss
                emoji = "🟢" if pnl >= 0 else "🔴"
                position_details.append(f"{emoji} {symbol}: ₹{pnl:.2f}")
            
            # Overall emoji
            overall_emoji = "💚" if total_pnl >= 0 else "❤️"
            
            message = f"""
📊 Current Positions P&L
━━━━━━━━━━━━━━━━━━
{chr(10).join(position_details)}
━━━━━━━━━━━━━━━━━━
{overall_emoji} Total P&L: ₹{total_pnl:.2f}
🕐 {datetime.now().strftime('%I:%M %p')}
            """
            
            self.send_message(message.strip())
            
        except Exception as e:
            logger.error(f"❌ Error sending P&L update: {str(e)}")
    
    def _is_market_hours(self) -> bool:
        """Check if current time is within market hours (9:15 AM - 3:30 PM)"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Market opens at 9:15 AM
        if hour == 9 and minute < 15:
            return False
        
        # Market closes at 3:30 PM
        if hour > 15 or (hour == 15 and minute > 30):
            return False
        
        # Between 9:15 AM and 3:30 PM
        return 9 <= hour <= 15
    
    def _periodic_pnl_updates(self):
        """Background thread for periodic P&L updates"""
        logger.info("🔄 P&L update thread started")
        
        while True:
            try:
                # Check if we should send update
                if self.config['market_hours_only']:
                    if self._is_market_hours():
                        self.send_pnl_update()
                    else:
                        logger.debug("Outside market hours - skipping P&L update")
                else:
                    self.send_pnl_update()
                
                # Sleep for configured interval
                time.sleep(self.config['pnl_update_interval'])
                
            except Exception as e:
                logger.error(f"❌ Error in P&L update thread: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _start_pnl_updates(self):
        """Start background thread for periodic P&L updates"""
        if self.pnl_thread is not None:
            logger.warning("P&L update thread already running")
            return
        
        self.pnl_thread = threading.Thread(
            target=self._periodic_pnl_updates,
            daemon=True,
            name="PnL-Update-Thread"
        )
        self.pnl_thread.start()
        logger.info("✅ P&L update thread started")
    
    def stop_pnl_updates(self):
        """Stop P&L update thread (if needed for cleanup)"""
        # Since it's a daemon thread, it will stop when main program exits
        logger.info("P&L update thread will stop with main program")

