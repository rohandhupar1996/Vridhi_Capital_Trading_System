"""
Unit tests for Event Bus
"""

import unittest
from datetime import datetime
from unittest.mock import Mock

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.orchestrator.event_bus import EventBus, Event, EventType, EventPriority


class TestEventBus(unittest.TestCase):
    """Test Event Bus functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.event_bus = EventBus()
        self.handler_calls = []
    
    def test_subscribe_and_publish(self):
        """Test event subscription and publishing"""
        def handler(event: Event):
            self.handler_calls.append(event)
        
        self.event_bus.subscribe(EventType.AUTH_SUCCESS, handler)
        
        event = Event(
            event_type=EventType.AUTH_SUCCESS,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="test",
            data={"test": "data"}
        )
        
        self.event_bus.publish(event)
        
        self.assertEqual(len(self.handler_calls), 1)
        self.assertEqual(self.handler_calls[0].event_type, EventType.AUTH_SUCCESS)
    
    def test_event_history(self):
        """Test event history tracking"""
        event = Event(
            event_type=EventType.TICK_RECEIVED,
            priority=EventPriority.NORMAL,
            timestamp=datetime.now(),
            source="test",
            data={}
        )
        
        self.event_bus.publish(event)
        
        history = self.event_bus.get_event_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].event_type, EventType.TICK_RECEIVED)
    
    def test_event_history_filtered(self):
        """Test filtered event history"""
        event1 = Event(
            event_type=EventType.TICK_RECEIVED,
            priority=EventPriority.NORMAL,
            timestamp=datetime.now(),
            source="test",
            data={}
        )
        event2 = Event(
            event_type=EventType.AUTH_SUCCESS,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            source="test",
            data={}
        )
        
        self.event_bus.publish(event1)
        self.event_bus.publish(event2)
        
        tick_history = self.event_bus.get_event_history(EventType.TICK_RECEIVED)
        self.assertEqual(len(tick_history), 1)
        self.assertEqual(tick_history[0].event_type, EventType.TICK_RECEIVED)


if __name__ == '__main__':
    unittest.main()

