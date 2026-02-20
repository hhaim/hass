"""
Unit tests for HumiditySwitchSensor class.

Run with: python3 test_humidity_sensor.py
"""

import sys
import os
import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import AppDaemonStub directly instead of from test module
import re

class AppDaemonStub:
    """Stub for AppDaemon API for testing."""
    
    def __init__(self):
        self.now = None
        self.state_dict = {}
        self.timers = []
        self.listeners = []
    
    def set_now(self, now: datetime.time = None):
        self.now = now
    
    def listen_state(self, cb, entity, **kwargs):
        handle = len(self.listeners)
        self.listeners.append((handle, cb, entity, kwargs))
        return handle
    
    def cancel_listen_state(self, handle):
        self.listeners = [(h, cb, e, k) for h, cb, e, k in self.listeners if h != handle]
    
    def run_in(self, callback, seconds, **kwargs):
        handle = len(self.timers)
        self.timers.append((handle, callback, seconds, kwargs))
        return handle
    
    def cancel_timer(self, handle):
        self.timers = [(h, cb, s, k) for h, cb, s, k in self.timers if h != handle]
    
    def listen_event(self, callback, event_name):
        pass
    
    def log(self, msg):
        # Suppress logs during testing
        pass
    
    def get_now(self):
        return self.now
    
    def get_state(self, entity=None, **kwargs):
        return self.state_dict.get(entity, "off")
    
    def turn_on(self, entity_id, **kwargs):
        self.state_dict[entity_id] = "on"
    
    def turn_off(self, entity_id, **kwargs):
        self.state_dict[entity_id] = "off"
    
    def set_state(self, entity_id, **kwargs):
        pass
    
    def notify(self, msg):
        pass
    
    def call_service(self, service, **kwargs):
        pass
    
    def parse_time(self, time_str, name=None):
        parsed_time = None
        parts = re.search(r'^(\d+):(\d+):(\d+)', time_str)
        if parts:
            parsed_time = datetime.time(
                int(parts.group(1)), int(parts.group(2)), int(parts.group(3))
            )
        if parsed_time is None:
            raise ValueError(f"invalid time string: {time_str}")
        return parsed_time


from humidity_sensor import HumiditySwitchSensor

# Test configuration
TEST_CFG = {
    "switch": "switch.test_dehumidifier",
    "sensor": "sensor.test_humidity",
    "enable": "input_boolean.test_enable",
    "input_start": 65.0,
    "input_stop": 60.0,
    "max_time_minutes": 5,  # Short for testing
    "cooldown_minutes": 6,  # Short for testing
    "sensor_max_age_minutes": 10,
    "notify_service": "notify/telegram"
}


class TestHumiditySwitchSensor:
    """Test suite for HumiditySwitchSensor."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
    
    def test_initialization(self):
        """Test basic initialization."""
        print("\n=== Test: Initialization ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        assert sensor.state == HumiditySwitchSensor.DISABLED, "Should start in DISABLED state"
        assert sensor.sabbath == False, "Sabbath should be False initially"
        assert sensor.input_start == 65.0, "input_start should be 65.0"
        assert sensor.input_stop == 60.0, "input_stop should be 60.0"
        assert sensor.sensor_handle is None, "No sensor listener initially"
        assert sensor.max_runtime_handle is None, "No max runtime timer initially"
        assert sensor.cooldown_handle is None, "No cooldown timer initially"
        
        print("✓ Initialization test passed")
        self.passed += 1
    
    def test_hysteresis_validation(self):
        """Test that hysteresis validation works."""
        print("\n=== Test: Hysteresis Validation ===")
        ad = AppDaemonStub()
        
        # Test invalid config (start <= stop)
        bad_cfg = TEST_CFG.copy()
        bad_cfg["input_start"] = 60.0
        bad_cfg["input_stop"] = 65.0
        
        try:
            sensor = HumiditySwitchSensor(ad, bad_cfg)
            print("✗ Should have raised ValueError for invalid hysteresis")
            self.failed += 1
        except ValueError as e:
            if "Hysteresis validation failed" in str(e):
                print("✓ Hysteresis validation test passed")
                self.passed += 1
            else:
                print(f"✗ Wrong error message: {e}")
                self.failed += 1
    
    def test_sensor_validation(self):
        """Test sensor value validation."""
        print("\n=== Test: Sensor Validation ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Valid values
        is_valid, value = sensor._is_sensor_valid("45.5")
        assert is_valid and value == 45.5, "Valid numeric string should pass"
        
        is_valid, value = sensor._is_sensor_valid(67.2)
        assert is_valid and value == 67.2, "Valid float should pass"
        
        # Invalid values
        is_valid, value = sensor._is_sensor_valid(None)
        assert not is_valid, "None should fail"
        
        is_valid, value = sensor._is_sensor_valid("unavailable")
        assert not is_valid, "unavailable should fail"
        
        is_valid, value = sensor._is_sensor_valid("unknown")
        assert not is_valid, "unknown should fail"
        
        is_valid, value = sensor._is_sensor_valid(-10)
        assert not is_valid, "Negative value should fail"
        
        is_valid, value = sensor._is_sensor_valid(150)
        assert not is_valid, "Value > 100 should fail"
        
        print("✓ Sensor validation test passed")
        self.passed += 1
    
    def test_state_transition_to_monitoring(self):
        """Test transition from DISABLED to MONITORING."""
        print("\n=== Test: Transition to MONITORING ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Mock enable switch to return "on"
        ad.get_state = lambda entity: "on" if entity == TEST_CFG["enable"] else "50.0"
        
        # Should be DISABLED initially
        assert sensor.state == HumiditySwitchSensor.DISABLED
        
        # Transition to monitoring
        sensor._transition_to_monitoring()
        
        assert sensor.state == HumiditySwitchSensor.MONITORING, "Should be in MONITORING state"
        assert sensor.sensor_handle is not None, "Sensor listener should be registered"
        
        print("✓ Transition to MONITORING test passed")
        self.passed += 1
    
    def test_state_transition_to_running(self):
        """Test transition from MONITORING to RUNNING."""
        print("\n=== Test: Transition to RUNNING ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Mock methods
        ad.get_state = lambda entity: "on" if entity == TEST_CFG["enable"] else "70.0"
        turned_on = []
        ad.turn_on = lambda entity: turned_on.append(entity)
        
        # Start in MONITORING
        sensor._transition_to_monitoring()
        
        # Transition to RUNNING
        sensor._transition_to_running()
        
        assert sensor.state == HumiditySwitchSensor.RUNNING, "Should be in RUNNING state"
        assert sensor.start_time is not None, "Start time should be recorded"
        assert sensor.max_runtime_handle is not None, "Max runtime timer should be set"
        assert TEST_CFG["switch"] in turned_on, "Switch should be turned on"
        
        print("✓ Transition to RUNNING test passed")
        self.passed += 1
    
    def test_hysteresis_logic(self):
        """Test hysteresis prevents rapid cycling."""
        print("\n=== Test: Hysteresis Logic ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Set up state dict
        ad.state_dict[TEST_CFG["enable"]] = "on"
        ad.state_dict[TEST_CFG["sensor"]] = "62.0"
        ad.state_dict[TEST_CFG["switch"]] = "off"
        
        # Track turn on/off calls
        turned_on = []
        turned_off = []
        original_turn_on = ad.turn_on
        original_turn_off = ad.turn_off
        
        def mock_turn_on(entity):
            turned_on.append(entity)
            original_turn_on(entity)
        
        def mock_turn_off(entity):
            turned_off.append(entity)
            original_turn_off(entity)
        
        ad.turn_on = mock_turn_on
        ad.turn_off = mock_turn_off
        
        # Start in MONITORING
        sensor._transition_to_monitoring()
        turned_on.clear()
        turned_off.clear()
        
        # Humidity at 62% (between stop=60% and start=65%)
        # Should stay in MONITORING, not start
        ad.state_dict[TEST_CFG["sensor"]] = "62.0"
        sensor.on_sensor_change(TEST_CFG["sensor"], None, "50.0", "62.0", None)
        
        assert sensor.state == HumiditySwitchSensor.MONITORING, "Should stay in MONITORING"
        assert len(turned_on) == 0, "Should not turn on in hysteresis band"
        
        # Humidity rises to 66% (above start=65%)
        # Should start
        ad.state_dict[TEST_CFG["sensor"]] = "66.0"
        sensor.on_sensor_change(TEST_CFG["sensor"], None, "62.0", "66.0", None)
        
        assert sensor.state == HumiditySwitchSensor.RUNNING, "Should transition to RUNNING"
        assert len(turned_on) > 0, "Should turn on above start threshold"
        assert ad.state_dict[TEST_CFG["switch"]] == "on", "Switch should be on"
        
        turned_on.clear()
        turned_off.clear()
        
        # Now humidity drops to 63% (between stop=60% and start=65%)
        # Should stay in RUNNING (hysteresis prevents stopping)
        ad.state_dict[TEST_CFG["sensor"]] = "63.0"
        sensor.on_sensor_change(TEST_CFG["sensor"], None, "66.0", "63.0", None)
        
        assert sensor.state == HumiditySwitchSensor.RUNNING, "Should stay in RUNNING in hysteresis band"
        assert len(turned_off) == 0, "Should not turn off in hysteresis band"
        assert ad.state_dict[TEST_CFG["switch"]] == "on", "Switch should still be on"
        
        # Humidity drops to 59% (below stop=60%)
        # Should stop (transition_to_monitoring turns off switch)
        ad.state_dict[TEST_CFG["sensor"]] = "59.0"
        sensor.on_sensor_change(TEST_CFG["sensor"], None, "63.0", "59.0", None)
        
        assert sensor.state == HumiditySwitchSensor.MONITORING, "Should transition to MONITORING"
        assert ad.state_dict[TEST_CFG["switch"]] == "off", "Switch should be off after transition"
        
        print("✓ Hysteresis logic test passed")
        self.passed += 1
    
    def test_sabbath_event_handling(self):
        """Test Sabbath event handling."""
        print("\n=== Test: Sabbath Event Handling ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Set up state dict
        ad.state_dict[TEST_CFG["enable"]] = "on"
        ad.state_dict[TEST_CFG["sensor"]] = "50.0"
        ad.state_dict[TEST_CFG["switch"]] = "off"
        
        # Track turn off calls
        turned_off = []
        original_turn_off = ad.turn_off
        
        def mock_turn_off(entity):
            turned_off.append(entity)
            original_turn_off(entity)
        
        ad.turn_off = mock_turn_off
        
        # Start in MONITORING
        sensor._transition_to_monitoring()
        
        assert sensor.sabbath == False, "Sabbath should be False initially"
        assert sensor.state == HumiditySwitchSensor.MONITORING
        
        # Sabbath starts
        sensor.on_sabbath_event("hebcal.event", {"state": "pre"}, None)
        
        assert sensor.sabbath == True, "Sabbath should be True"
        assert sensor.state == HumiditySwitchSensor.DISABLED, "Should transition to DISABLED"
        assert ad.state_dict[TEST_CFG["switch"]] == "off", "Switch should be off"
        
        # Sabbath ends
        sensor.on_sabbath_event("hebcal.event", {"state": "off"}, None)
        
        assert sensor.sabbath == False, "Sabbath should be False"
        # Note: State transition depends on is_enabled(), which depends on enable switch
        # Since enable is "on", should transition to MONITORING
        assert sensor.state == HumiditySwitchSensor.MONITORING, "Should transition to MONITORING after Sabbath"
        
        print("✓ Sabbath event handling test passed")
        self.passed += 1
    
    def test_schedule_event_handling(self):
        """Test schedule event handling."""
        print("\n=== Test: Schedule Event Handling ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Set up state dict
        ad.state_dict[TEST_CFG["enable"]] = "on"
        ad.state_dict[TEST_CFG["sensor"]] = "50.0"
        ad.state_dict[TEST_CFG["switch"]] = "off"
        
        # Start in MONITORING
        sensor._transition_to_monitoring()
        assert sensor.state == HumiditySwitchSensor.MONITORING
        
        # Schedule starts (disable time window)
        sensor.on_schedule_event({"state": "on"})
        
        assert sensor.state == HumiditySwitchSensor.DISABLED, "Should transition to DISABLED"
        
        # Schedule ends (enable time window)
        sensor.on_schedule_event({"state": "off"})
        
        assert sensor.state == HumiditySwitchSensor.MONITORING, "Should transition to MONITORING"
        
        print("✓ Schedule event handling test passed")
        self.passed += 1
    
    def test_max_runtime_transition(self):
        """Test max runtime timer triggers cooldown."""
        print("\n=== Test: Max Runtime Transition ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Set up state dict
        ad.state_dict[TEST_CFG["enable"]] = "on"
        ad.state_dict[TEST_CFG["sensor"]] = "70.0"
        ad.state_dict[TEST_CFG["switch"]] = "off"
        
        # Start in RUNNING
        sensor._transition_to_monitoring()
        sensor._transition_to_running()
        
        assert sensor.state == HumiditySwitchSensor.RUNNING
        assert sensor.max_runtime_handle is not None
        
        # Simulate max runtime timer firing
        sensor._on_max_runtime(None)
        
        assert sensor.state == HumiditySwitchSensor.COOLDOWN, "Should transition to COOLDOWN"
        assert sensor.max_runtime_handle is None, "Max runtime handle should be cleared"
        assert sensor.cooldown_handle is not None, "Cooldown timer should be set"
        assert ad.state_dict[TEST_CFG["switch"]] == "off", "Switch should be off"
        
        print("✓ Max runtime transition test passed")
        self.passed += 1
    
    def test_cooldown_complete(self):
        """Test cooldown completion transitions to monitoring."""
        print("\n=== Test: Cooldown Complete ===")
        ad = AppDaemonStub()
        sensor = HumiditySwitchSensor(ad, TEST_CFG)
        
        # Set up state dict
        ad.state_dict[TEST_CFG["enable"]] = "on"
        ad.state_dict[TEST_CFG["sensor"]] = "50.0"
        ad.state_dict[TEST_CFG["switch"]] = "off"
        
        # Start in COOLDOWN
        sensor._transition_to_monitoring()
        sensor._transition_to_running()
        sensor._transition_to_cooldown()
        
        assert sensor.state == HumiditySwitchSensor.COOLDOWN
        assert sensor.cooldown_handle is not None
        
        # Simulate cooldown timer firing
        sensor._on_cooldown_complete(None)
        
        assert sensor.state == HumiditySwitchSensor.MONITORING, "Should transition to MONITORING"
        assert sensor.cooldown_handle is None, "Cooldown handle should be cleared"
        
        print("✓ Cooldown complete test passed")
        self.passed += 1
    
    def run_all_tests(self):
        """Run all tests and report results."""
        print("\n" + "="*60)
        print("Running HumiditySwitchSensor Unit Tests")
        print("="*60)
        
        try:
            self.test_initialization()
            self.test_hysteresis_validation()
            self.test_sensor_validation()
            self.test_state_transition_to_monitoring()
            self.test_state_transition_to_running()
            self.test_hysteresis_logic()
            self.test_sabbath_event_handling()
            self.test_schedule_event_handling()
            self.test_max_runtime_transition()
            self.test_cooldown_complete()
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
        
        print("\n" + "="*60)
        print(f"Test Results: {self.passed} passed, {self.failed} failed")
        print("="*60)
        
        return self.failed == 0


if __name__ == "__main__":
    tester = TestHumiditySwitchSensor()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
