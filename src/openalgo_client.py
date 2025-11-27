"""
OpenAlgo Client Wrapper
"""

from openalgo import api
import logging
from config import OPENALGO_CONFIG

logger = logging.getLogger(__name__)


class OpenAlgoClient:
    """Wrapper for OpenAlgo API client"""
    
    def __init__(self, api_key: str = None, host: str = None):
        """Initialize OpenAlgo client"""
        self.api_key = api_key or OPENALGO_CONFIG['api_key']
        self.host = host or OPENALGO_CONFIG['host']
        
        self.client = api(
            api_key=self.api_key,
            host=self.host
        )
        
        logger.info(f"OpenAlgo client initialized: {self.host}")
    
    def get_nearest_expiry(self, symbol: str = "BANKNIFTY") -> str:
        """
        Fetch nearest expiry date
        
        Args:
            symbol: Underlying symbol
            
        Returns:
            Expiry date string (e.g., '28NOV25') or None
        """
        try:
            response = self.client.expiry(
                symbol=symbol,
                exchange="NFO",
                instrumenttype="options"
            )
            
            if response['status'] == 'success' and response['data']:
                nearest_expiry = response['data'][0]
                logger.info(f"✅ Nearest expiry: {nearest_expiry}")
                return nearest_expiry
            else:
                logger.error(f"❌ Failed to fetch expiry: {response}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception fetching expiry: {str(e)}")
            return None
    
    def get_order_status(self, order_id: str, strategy: str) -> dict:
        """Get order status"""
        try:
            return self.client.orderstatus(
                order_id=order_id,
                strategy=strategy
            )
        except Exception as e:
            logger.error(f"❌ Exception getting order status: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def place_options_order(self, **kwargs) -> dict:
        """Place options order"""
        try:
            return self.client.optionsorder(**kwargs)
        except Exception as e:
            logger.error(f"❌ Exception placing order: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def close_position(self, strategy: str) -> dict:
        """Close all positions for strategy"""
        try:
            return self.client.closeposition(strategy=strategy)
        except Exception as e:
            logger.error(f"❌ Exception closing positions: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_positions(self) -> dict:
        """Get position book"""
        try:
            return self.client.positionbook()
        except Exception as e:
            logger.error(f"❌ Exception fetching positions: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_orderbook(self) -> dict:
        """Get order book"""
        try:
            return self.client.orderbook()
        except Exception as e:
            logger.error(f"❌ Exception fetching orderbook: {str(e)}")
            return {"status": "error", "message": str(e)}

