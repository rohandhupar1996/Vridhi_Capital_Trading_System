"""
Orchestrated Live Trading System
Multi-agent system with orchestrator, event bus, and all agents
"""

from __future__ import annotations

import sys
import time
import signal
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

from src.trading_system.config import AppConfig
from src.trading_system.logging import ComponentLogger, setup_logging
from src.trading_system.broker.zerodha_auth import ZerodhaAuthenticator, ZerodhaCredentials

# Orchestrator components
from src.trading_system.orchestrator.orchestrator import Orchestrator
from src.trading_system.orchestrator.event_bus import get_event_bus
from src.trading_system.orchestrator.shared_state import get_shared_state
from src.trading_system.orchestrator.observability import get_metrics, get_audit_trail

# Agents
from src.trading_system.orchestrator.agents.auth_agent import AuthConnectionAgent
from src.trading_system.orchestrator.agents.market_data_agent import MarketDataAgent
from src.trading_system.orchestrator.agents.signal_agent import SignalAgent
from src.trading_system.orchestrator.agents.risk_policy_agent import RiskPolicyAgent
from src.trading_system.orchestrator.agents.oms_execution_agent import OMSExecutionAgent
from src.trading_system.orchestrator.agents.health_agent import HealthRecoveryAgent

# OMS components
from src.trading_system.oms.order_manager import OrderManager
from src.trading_system.oms.running_signal_executor import RunningSignalExecutor
from src.trading_system.oms.dynamic_timeframe import DynamicTimeframeController, DynamicTimeframeConfig
from src.trading_system.oms.earnings_filter import EarningsSeasonFilter, EarningsFilterConfig

# Global for graceful shutdown
running = True
orchestrator = None
agents = {}


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running, orchestrator, agents
    print("\n\n⚠️  Shutdown signal received. Stopping system...")
    running = False
    
    # Stop all agents
    for agent in agents.values():
        if hasattr(agent, 'stop'):
            agent.stop()
    
    if orchestrator:
        orchestrator.stop()
    
    print("✅ System stopped gracefully")
    sys.exit(0)


def main():
    """Main orchestrated trading system"""
    global running, orchestrator, agents
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup logging
    setup_logging("logs")
    main_logger = ComponentLogger.get_logger("orchestrated_trading")
    
    print("\n" + "="*70)
    print("ORCHESTRATED LIVE TRADING SYSTEM")
    print("="*70 + "\n")
    
    # Load configuration
    app_config = AppConfig()
    
    # Load credentials
    env_path = PROJECT_ROOT / "configs" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        main_logger.info(f"Loaded credentials from {env_path}")
    
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ ZERODHA_API_KEY or ZERODHA_API_SECRET not found")
        return False
    
    # Initialize orchestrator
    print("🧠 Initializing Orchestrator...")
    orchestrator = Orchestrator(logger=ComponentLogger.get_logger("orchestrator"))
    orchestrator.start()
    
    # Initialize shared state
    shared_state = get_shared_state()
    
    # Initialize metrics and audit
    metrics = get_metrics()
    audit = get_audit_trail()
    
    # Initialize Auth/Connection Agent
    print("🔐 Initializing Auth/Connection Agent...")
    credentials = ZerodhaCredentials(api_key=api_key, api_secret=api_secret)
    auth_agent = AuthConnectionAgent(
        credentials=credentials,
        token_file="configs/zerodha_tokens.json",
        orchestrator=orchestrator,
        logger=ComponentLogger.get_logger("auth_agent")
    )
    auth_agent.start()
    agents['auth'] = auth_agent
    orchestrator.register_agent("auth", auth_agent)
    
    # Authenticate
    if not auth_agent.authenticator.login(auto_open_browser=False):
        print("❌ Authentication failed")
        return False
    
    kite = auth_agent.authenticator.get_kite()
    if not kite:
        print("❌ Failed to get Kite instance")
        return False
    
    profile = kite.profile()
    print(f"✅ Authenticated as: {profile.get('user_name', 'N/A')}")
    
    # Initialize OMS
    print("📦 Initializing OMS...")
    oms_config = app_config.oms if hasattr(app_config, 'oms') else {}
    lot_size = oms_config.get('lot_size', 8)
    
    oms = OrderManager(
        kite=kite,
        lot_size=lot_size,
        hedge_legs=oms_config.get('hedge_legs', 20),
        logger=ComponentLogger.get_logger("order_manager"),
        dry_run=False
    )
    
    futures_token = oms._get_futures_token()
    if not futures_token:
        print("❌ Failed to get futures token")
        return False
    
    # Initialize Market Data Agent
    print("📡 Initializing Market Data Agent...")
    market_data_agent = MarketDataAgent(
        kite=kite,
        futures_token=futures_token,
        order_manager=oms,
        orchestrator=orchestrator,
        logger=ComponentLogger.get_logger("market_data_agent")
    )
    market_data_agent.start()
    agents['market_data'] = market_data_agent
    orchestrator.register_agent("market_data", market_data_agent)
    
    # Initialize Risk/Policy Agent
    print("🛡️  Initializing Risk/Policy Agent...")
    risk_agent = RiskPolicyAgent(
        orchestrator=orchestrator,
        max_lots=lot_size,
        logger=ComponentLogger.get_logger("risk_agent")
    )
    risk_agent.start()
    agents['risk'] = risk_agent
    orchestrator.register_agent("risk", risk_agent)
    
    # Initialize OMS Execution Agent
    print("⚡ Initializing OMS/Execution Agent...")
    oms_agent = OMSExecutionAgent(
        order_manager=oms,
        orchestrator=orchestrator,
        logger=ComponentLogger.get_logger("oms_agent")
    )
    oms_agent.start()
    agents['oms'] = oms_agent
    orchestrator.register_agent("oms", oms_agent)
    
    # Initialize Signal Executor and Signal Agent
    print("🎯 Initializing Signal Agent...")
    timeframe_config = DynamicTimeframeConfig(
        base_timeframe="15min",
        expiry_day_timeframe="5min",
        enable_expiry_switch=True
    )
    timeframe_controller = DynamicTimeframeController(timeframe_config)
    
    earnings_config = EarningsFilterConfig(
        use_filter=app_config.earnings_filter.get('use_filter', True) if hasattr(app_config, 'earnings_filter') else True,
        block_first_days_blue=app_config.earnings_filter.get('block_first_days_blue', 15) if hasattr(app_config, 'earnings_filter') else 15,
        block_after_yellow=app_config.earnings_filter.get('block_after_yellow', 15) if hasattr(app_config, 'earnings_filter') else 15
    )
    earnings_filter = EarningsSeasonFilter(earnings_config)
    
    signal_executor = RunningSignalExecutor(
        order_manager=oms,
        timeframe_controller=timeframe_controller,
        earnings_filter=earnings_filter,
        logger=ComponentLogger.get_logger("signal_executor")
    )
    
    signal_agent = SignalAgent(
        signal_executor=signal_executor,
        timeframe_controller=timeframe_controller,
        earnings_filter=earnings_filter,
        orchestrator=orchestrator,
        logger=ComponentLogger.get_logger("signal_agent")
    )
    signal_agent.start()
    agents['signal'] = signal_agent
    orchestrator.register_agent("signal", signal_agent)
    
    # Initialize Health/Recovery Agent
    print("💚 Initializing Health/Recovery Agent...")
    health_agent = HealthRecoveryAgent(
        orchestrator=orchestrator,
        logger=ComponentLogger.get_logger("health_agent")
    )
    health_agent.start()
    agents['health'] = health_agent
    orchestrator.register_agent("health", health_agent)
    
    # Pre-calculate margins
    print("\n💰 Pre-calculating margins...")
    if oms.futures_ltp and oms.futures_ltp > 0:
        oms.pre_calculate_margins()
        shared_state.set("pre_calculated_margins", oms._pre_calculated_margins)
        print("✅ Margins pre-calculated")
    
    # Main loop
    print("\n" + "="*70)
    print("🚀 ORCHESTRATED TRADING SYSTEM STARTED")
    print("="*70)
    print("\n⚠️  Press Ctrl+C to stop\n")
    
    try:
        while running:
            # Monitor connections
            auth_agent.monitor()
            
            # Check stream health
            market_data_agent.check_stream_health()
            
            # Monitor health
            health_agent.monitor()
            
            # Register heartbeats
            for agent_name, agent in agents.items():
                health_agent.register_heartbeat(agent_name)
            
            # Signal generation integration point
            # TODO: Integrate your ML model here to generate signals
            # Example:
            #   current_price = shared_state.get("futures_ltp")
            #   if current_price:
            #       signal = signal_agent.generate_signal({"price": current_price})
            #       if signal != "NONE":
            #           candle_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_15min"
            #           signal_agent.process_signal(signal, candle_id, current_price)
            
            # Checkpoint state periodically
            if int(time.time()) % 60 == 0:  # Every minute
                shared_state.checkpoint()
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\n🛑 Stopping system...")
        for agent in agents.values():
            if hasattr(agent, 'stop'):
                agent.stop()
        if orchestrator:
            orchestrator.stop()
        print("✅ System stopped")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

