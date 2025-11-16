from integrated_system import IntegratedTradingSystem
from kiteconnect import KiteConnect, KiteTicker

# Initialize and run
kite = KiteConnect(api_key="your_key")
system = IntegratedTradingSystem(kite)
system.run()