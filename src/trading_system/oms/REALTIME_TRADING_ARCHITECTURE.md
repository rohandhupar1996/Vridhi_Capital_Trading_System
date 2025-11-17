# Real-Time Trading Architecture & Rate Limits

## Overview

This document explains how the system handles real-time trading with Zerodha's API rate limits and WebSocket feeds.

## Zerodha API Rate Limits

Based on Zerodha's official documentation:

| Endpoint Type | Rate Limit | Use Case |
|--------------|------------|----------|
| **Quote** | 1 req/second | Getting LTP (Last Traded Price) for single instruments |
| **Historical Candle** | 3 req/second | Fetching historical OHLCV data |
| **Order Placement** | 10 req/second | Placing/modifying/cancelling orders |
| **Other Endpoints** | 10 req/second | All other API calls (positions, margins, etc.) |

## Real-Time Trading Architecture

### How Real-Time Prices Work

**For Live Trading, Zerodha provides TWO mechanisms:**

#### 1. **WebSocket Feed (Recommended for Real-Time)**
- ⚠️ **Requires Zerodha Connect subscription (₹500/month)** - Free Personal API does NOT include WebSocket
- **No rate limits** - WebSocket is a persistent connection
- **Tick-by-tick updates** - Prices update in real-time as trades happen
- **Multiple instruments** - Can subscribe to multiple symbols simultaneously
- **Low latency** - Updates arrive within milliseconds
- **Official support** - KiteTicker class in `kiteconnect` library

**How it works:**
```
Client ←→ WebSocket Connection ←→ Zerodha Tick Server
         (Persistent, no rate limit)
```

#### 2. **HTTP REST API (For Order Placement & Occasional Quotes)**
- **Rate limited** - Must respect the limits above
- **On-demand** - Only called when needed
- **Used for** - Order placement, position checks, margin queries

### Real-Time Trading Flow

```
┌─────────────────────────────────────────────────────────┐
│                    LIVE TRADING SYSTEM                  │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                         │
        ▼                                         ▼
┌───────────────┐                      ┌──────────────────┐
│ WebSocket     │                      │ HTTP REST API    │
│ Feed          │                      │ (Rate Limited)   │
├───────────────┤                      ├──────────────────┤
│ • Live prices │                      │ • Place orders   │
│ • Tick data   │                      │ • Check margins  │
│ • No rate     │                      │ • Get positions   │
│   limit       │                      │ • 10 req/sec max │
└───────────────┘                      └──────────────────┘
        │                                         │
        └───────────────────┬───────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  Trading System       │
                │  • Signal Generation  │
                │  • OMS Execution      │
                │  • Position Mgmt       │
                └───────────────────────┘
```

## How Many Requests Per Second Do We Need?

### For Price Updates (WebSocket - No Limit)
- **WebSocket subscription**: Subscribe once to BankNifty futures + options
- **Updates arrive automatically**: No polling needed
- **Rate limit**: **0 requests/second** (WebSocket doesn't count)

### For Order Placement (HTTP API - 10 req/sec)
- **Entry order**: 3 legs × 1 order = 3 requests
  - BUY ATM CALL (CE)
  - BUY 20-legs PUT (PE) 
  - SELL ATM PUT (PE)
- **Exit order**: 3 legs × 1 order = 3 requests
- **Sequential lot reduction**: If margin issue, retry with smaller lots
  - Worst case: 4 attempts (8→4→2→1) = 12 requests total
- **Rate limit**: **10 req/second** is sufficient for normal trading

### Typical Trading Day Request Pattern

```
Scenario: Signal appears at 9:15 AM

1. WebSocket already providing live prices (0 API calls)
2. Entry order placement:
   - BUY legs (2 orders): ~0.2 seconds
   - SELL leg (1 order): ~0.1 seconds
   - Total: 3 API calls in ~0.3 seconds ✅ (well under 10/sec)

3. Exit order (4 bars later):
   - Exit all 3 legs: 3 API calls in ~0.3 seconds ✅

4. Worst case (margin issue):
   - Sequential reduction: 4 attempts × 3 orders = 12 calls
   - Spread over ~1-2 seconds ✅ (still under 10/sec)
```

## Will Trades Be in Sync with Real-Time Prices?

### ✅ YES - Here's Why:

1. **WebSocket Feed Provides Real-Time Prices**
   - Prices update tick-by-tick as trades happen
   - No polling delay - updates arrive immediately
   - System receives price updates in real-time

2. **Order Placement is Fast**
   - MARKET orders execute immediately at current price
   - Rate limit of 10 req/sec allows all 3 legs in < 0.5 seconds
   - Total execution time: ~0.5-1 second from signal to filled

3. **Signal Generation is Real-Time**
   - System processes WebSocket ticks as they arrive
   - Signals generated on running candles (not waiting for close)
   - Immediate execution when signal appears

### Example Timeline (Real-Time Trading)

```
09:15:00.000 - WebSocket receives tick: BankNifty Futures = 51,000
09:15:00.100 - Signal generated: LONG
09:15:00.200 - OMS calculates: ATM = 51,000, Hedge = 49,000
09:15:00.300 - Place BUY order #1: BANKNIFTY51000CE (rate limiter: wait 0.1s)
09:15:00.400 - Place BUY order #2: BANKNIFTY49000PE (rate limiter: wait 0.1s)
09:15:00.500 - Place SELL order #3: BANKNIFTY51000PE (rate limiter: wait 0.1s)
09:15:00.600 - All orders filled at current market prices ✅
```

**Total time: ~0.6 seconds from signal to filled position**

## Rate Limiter Implementation

The system includes a `RateLimiter` class that:
- Tracks last call time per endpoint type
- Automatically waits if needed before making API calls
- Thread-safe for concurrent operations
- Prevents rate limit violations

**Usage in OrderManager:**
```python
# Before placing order
rate_limiter = get_rate_limiter()
rate_limiter.wait_if_needed(EndpointType.ORDER)  # Ensures 10 req/sec max
order_id = self.kite.place_order(...)
```

## Recommendations for Live Trading

1. **Use WebSocket for Prices**
   - Subscribe to BankNifty futures tick feed
   - No rate limit concerns
   - Real-time price updates

2. **Respect HTTP API Limits**
   - Rate limiter is already implemented
   - Sequential lot reduction may need slight delays
   - Monitor for rate limit errors

3. **Order Execution Strategy**
   - BUY orders first (to ensure margin available)
   - Then SELL orders
   - All within 0.5-1 second window

4. **Error Handling**
   - If rate limit hit, wait and retry
   - Sequential lot reduction handles margin issues
   - Partial fills are acceptable on SELL side

## Summary

- **Price Updates**: WebSocket (no rate limit, real-time) - **See `websocket_price_feed.py` for implementation**
- **Order Placement**: HTTP API (10 req/sec, sufficient for our needs)
- **Execution Speed**: ~0.5-1 second from signal to filled
- **Sync with Prices**: ✅ Yes - WebSocket provides real-time prices, orders execute at current market price

## Implementation

### Current State:
- **Simulation/Backtesting**: Uses HTTP API (`kite.quote()`) - Request-based, rate limited to 1 req/sec
- **Live Trading**: Should use WebSocket - Push-based, no rate limits, real-time

### WebSocket Implementation:
See `websocket_price_feed.py` for the WebSocket price feed implementation. It:
- Connects to Zerodha tick feed
- Subscribes to BankNifty futures contract
- Automatically updates `OrderManager.futures_ltp` with every tick
- No rate limits - prices arrive instantly as trades happen

### How Prices Work:
1. **Simulation**: We request prices → `kite.quote()` → Rate limited (1/sec) → Not real-time
2. **Live Trading**: Zerodha pushes prices → WebSocket → No rate limit → Real-time ✅

The system is designed to work efficiently within Zerodha's rate limits while maintaining real-time price synchronization through WebSocket feeds.

