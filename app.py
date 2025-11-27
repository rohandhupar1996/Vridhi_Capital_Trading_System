#!/usr/bin/env python3
"""
BankNifty Trading System - Main Application
"""

import logging
from src.openalgo_client import OpenAlgoClient
from src.order_manager import OrderManager
from src.position_executor import PositionExecutor
from src.telegram_notifier import TelegramNotifier
from src.webhook_handler import WebhookHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main application entry point"""
    try:
        # Initialize components
        logger.info("Initializing trading system components...")
        
        # 1. OpenAlgo Client
        openalgo_client = OpenAlgoClient()
        
        # 2. Order Manager
        order_manager = OrderManager(openalgo_client)
        
        # 3. Telegram Notifier
        telegram_notifier = TelegramNotifier(openalgo_client)
        
        # 4. Position Executor
        position_executor = PositionExecutor(order_manager, telegram_notifier)
        
        # 5. Webhook Handler
        webhook_handler = WebhookHandler(openalgo_client, position_executor, telegram_notifier)
        
        # Run the server
        webhook_handler.run()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}", exc_info=True)


if __name__ == '__main__':
    main()

