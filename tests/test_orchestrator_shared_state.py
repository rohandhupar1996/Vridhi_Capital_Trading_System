"""
Unit tests for Shared State
"""

import unittest
import json
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

import sys
from pathlib import Path as PathType

PROJECT_ROOT = PathType(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trading_system.orchestrator.shared_state import SharedState, SystemState


class TestSharedState(unittest.TestCase):
    """Test Shared State functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.shared_state = SharedState(checkpoint_dir=Path(self.temp_dir))
    
    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir)
    
    def test_get_set(self):
        """Test get and set operations"""
        self.shared_state.set("futures_ltp", 51000.0)
        value = self.shared_state.get("futures_ltp")
        self.assertEqual(value, 51000.0)
    
    def test_update_state(self):
        """Test atomic state update"""
        self.shared_state.update_state(
            futures_ltp=51000.0,
            websocket_connected=True
        )
        
        self.assertEqual(self.shared_state.get("futures_ltp"), 51000.0)
        self.assertEqual(self.shared_state.get("websocket_connected"), True)
    
    def test_get_state_snapshot(self):
        """Test getting complete state snapshot"""
        self.shared_state.set("futures_ltp", 51000.0)
        self.shared_state.set("websocket_connected", True)
        
        snapshot = self.shared_state.get_state()
        self.assertIsInstance(snapshot, SystemState)
        self.assertEqual(snapshot.futures_ltp, 51000.0)
        self.assertEqual(snapshot.websocket_connected, True)
    
    def test_checkpoint_restore(self):
        """Test checkpoint and restore"""
        self.shared_state.set("futures_ltp", 51000.0)
        self.shared_state.set("websocket_connected", True)
        
        # Checkpoint
        self.shared_state.checkpoint("test")
        
        # Create new state and restore
        new_state = SharedState(checkpoint_dir=Path(self.temp_dir))
        restored = new_state.restore("test")
        
        self.assertTrue(restored)
        self.assertEqual(new_state.get("futures_ltp"), 51000.0)
        self.assertEqual(new_state.get("websocket_connected"), True)


if __name__ == '__main__':
    unittest.main()

