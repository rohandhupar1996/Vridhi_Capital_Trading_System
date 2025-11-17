# Multi-Agent Orchestrator System

## Overview

Complete multi-agent orchestrator system for robust live trading with:
- Event-driven architecture
- Agent coordination
- Health monitoring and self-healing
- Policy enforcement
- Observability and audit trails

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (Brain)                   │
│  Routes events, enforces policies, approves actions     │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Event Bus    │  │ Shared State │  │ Observability│
│ (Routing)    │  │ (KV Store)   │  │ (Metrics)    │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Auth Agent   │  │ Market Data │  │ Signal Agent │
│              │  │ Agent       │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Risk Agent   │  │ OMS Agent    │  │ Health Agent │
│              │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Components

### 1. Orchestrator (Brain)
- Routes events between agents
- Enforces priorities and SLAs
- Approves actions against hard policies
- Owns global runbook

### 2. Event Bus
- Central event routing system
- Priority queue for event processing
- Event history tracking
- Subscriber pattern

### 3. Shared State
- Thread-safe key-value store
- Stores: prices, positions, flags, health status
- Checkpoint/restore capability
- Persistent state across restarts

### 4. Agents

#### Auth/Connection Agent
- Monitors Wi-Fi, Zerodha API, token validity
- Auto-refreshes tokens with exponential backoff
- Switches to read-only when degraded
- Never blocks OMS if data is stable

#### Market Data Agent
- Subscribes to BN futures only
- Validates tokens/ltp > 0
- Restarts streams on stalls
- Fills gaps from REST API
- Time-skew detection

#### Signal Agent
- Runs models on effective timeframe (expiry switch)
- Running-candle updates
- Applies earnings filter (blocks entries only)
- Flicker cleanup
- Same-candle reversal handling

#### Risk/Policy Agent
- Enforces hard limits (max lots, daily loss)
- NRML/Market enforcement
- Trading windows
- Margin pre-checks
- Sequential lot reduction
- Circuit breakers
- Read-only mode on breach

#### OMS/Execution Agent
- BUY-first then SELL
- Partial-fill handling
- All-legs exit/SL
- Futures-based ATM calc only
- Retries with smart pacing
- Idempotent order ops
- Dedup by client-order-id

#### Health/Recovery Agent
- Heartbeats for all agents
- Detects wedges (no fills, no ticks, high latency)
- Self-heal steps:
  - Reconnect
  - Rotate credentials
  - Restart streams
  - Drain/restart queues
- Rollback/flatten positions on inconsistent state

### 5. Observability
- Structured logs + metrics
- Metrics: auth latency, tick freshness, quote/ltp drift, order reject rates
- Runbooks for common issues
- Audit trail for every action
- Simulation mode on weekends

## Usage

### Run Orchestrated System:
```bash
PYTHONPATH=. python src/trading_system/orchestrator/orchestrated_live_trading.py
```

### Run Simple System (Original):
```bash
PYTHONPATH=. python scripts/live_trading.py
```

## Key Features

1. **Event-Driven**: All communication via event bus
2. **Policy Enforcement**: Hard policies prevent bad trades
3. **Self-Healing**: Automatic recovery from failures
4. **Health Monitoring**: Continuous agent health checks
5. **Audit Trail**: Complete action history
6. **Checkpointing**: Resume after restart
7. **Circuit Breakers**: Stop trading on risk breaches

## Testing

### Unit Tests:
```bash
PYTHONPATH=. python -m pytest tests/ -v
```

### Integration Test:
```bash
PYTHONPATH=. python -m pytest tests/test_live_trading_integration.py -v
```

## Status

✅ **Created:**
- Event Bus
- Shared State
- Orchestrator
- All 6 Agents
- Observability system
- Orchestrated live trading script
- Unit tests framework

⚠️ **Needs Integration:**
- Signal generation logic in Signal Agent
- Complete recovery actions in Health Agent
- Full runbook implementations

