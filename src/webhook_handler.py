"""
Webhook Handler Module
"""

import logging
from flask import Flask, request, jsonify
from datetime import datetime
from config import CONFIG, SERVER_CONFIG

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles webhook endpoints"""
    
    def __init__(self, openalgo_client, position_executor, telegram_notifier=None):
        """
        Initialize Webhook Handler
        
        Args:
            openalgo_client: OpenAlgoClient instance
            position_executor: PositionExecutor instance
            telegram_notifier: TelegramNotifier instance (optional)
        """
        self.client = openalgo_client
        self.executor = position_executor
        self.telegram = telegram_notifier
        self.app = Flask(__name__)
        self._register_routes()
    
    def _register_routes(self):
        """Register all Flask routes"""
        
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """
            Main webhook endpoint for TradingView alerts
            
            Expected JSON:
            {
                "signal": "LONG" | "SHORT" | "EXIT" | "NONE"
            }
            """
            try:
                data = request.get_json()
                logger.info("=" * 70)
                logger.info(f"📨 WEBHOOK RECEIVED: {data}")
                logger.info("=" * 70)
                
                signal = data.get('signal', '').upper()
                
                # Validate signal
                if signal not in ['LONG', 'SHORT', 'EXIT', 'NONE']:
                    logger.error(f"❌ Invalid signal: {signal}")
                    return jsonify({
                        "status": "error",
                        "message": f"Invalid signal '{signal}'. Must be LONG, SHORT, EXIT, or NONE"
                    }), 400
                
                # Handle EXIT/NONE signals
                if signal in ['EXIT', 'NONE']:
                    result = self.executor.close_all_positions(CONFIG['strategy_name'])
                    return jsonify(result), 200
                
                # Get nearest expiry
                expiry = self.client.get_nearest_expiry()
                if not expiry:
                    logger.error("❌ Failed to fetch expiry date")
                    return jsonify({
                        "status": "error",
                        "message": "Failed to fetch BankNifty expiry date"
                    }), 500
                
                # Execute position based on signal
                if signal == 'LONG':
                    result = self.executor.execute_long_position(expiry)
                elif signal == 'SHORT':
                    result = self.executor.execute_short_position(expiry)
                
                return jsonify(result), 200
                
            except Exception as e:
                logger.error(f"❌ Webhook error: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            return jsonify({
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "config": CONFIG
            }), 200
        
        @self.app.route('/positions', methods=['GET'])
        def get_positions():
            """Get current open positions"""
            response = self.client.get_positions()
            return jsonify(response), 200
        
        @self.app.route('/orderbook', methods=['GET'])
        def get_orderbook():
            """Get order book"""
            response = self.client.get_orderbook()
            return jsonify(response), 200
        
        @self.app.route('/close', methods=['POST'])
        def close_positions():
            """Manually close all positions"""
            result = self.executor.close_all_positions(CONFIG['strategy_name'])
            return jsonify(result), 200
        
        @self.app.route('/test/long', methods=['POST'])
        def test_long():
            """Test LONG position execution"""
            expiry = self.client.get_nearest_expiry()
            if not expiry:
                return jsonify({"status": "error", "message": "Failed to fetch expiry"}), 500
            
            result = self.executor.execute_long_position(expiry)
            return jsonify(result), 200
        
        @self.app.route('/test/short', methods=['POST'])
        def test_short():
            """Test SHORT position execution"""
            expiry = self.client.get_nearest_expiry()
            if not expiry:
                return jsonify({"status": "error", "message": "Failed to fetch expiry"}), 500
            
            result = self.executor.execute_short_position(expiry)
            return jsonify(result), 200
        
        @self.app.route('/pnl', methods=['GET'])
        def get_pnl():
            """Manually trigger P&L report to Telegram"""
            if self.telegram:
                self.telegram.send_pnl_update()
                return jsonify({"status": "success", "message": "P&L sent to Telegram"}), 200
            else:
                return jsonify({"status": "error", "message": "Telegram not configured"}), 400
    
    def run(self, host=None, port=None, debug=None):
        """Run the Flask server"""
        host = host or SERVER_CONFIG['host']
        port = port or SERVER_CONFIG['port']
        debug = debug or SERVER_CONFIG['debug']
        
        logger.info("=" * 70)
        logger.info("🚀 BANKNIFTY TRADING SYSTEM STARTING")
        logger.info("=" * 70)
        logger.info(f"Configuration: {CONFIG}")
        logger.info("=" * 70)
        logger.info("Endpoints:")
        logger.info("  POST /webhook          - TradingView webhook")
        logger.info("  GET  /health           - Health check")
        logger.info("  GET  /positions        - Current positions")
        logger.info("  GET  /orderbook        - Order book")
        logger.info("  GET  /pnl              - Send P&L to Telegram")
        logger.info("  POST /close            - Close all positions")
        logger.info("  POST /test/long        - Test LONG execution")
        logger.info("  POST /test/short       - Test SHORT execution")
        logger.info("=" * 70)
        
        self.app.run(host=host, port=port, debug=debug)

