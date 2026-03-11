"""
This module implements the HumiditySwitchSensor class for humidity-based switch control.
"""

import datetime

HEBCAL_EVENT = "hebcal.event"


def state_to_bool(state: str):
    """Convert state string to boolean."""
    return True if state == "on" else False


class HumiditySwitchSensor:
    """Control a switch based on humidity sensor readings with hysteresis.
    
    Features:
    - 4-state machine: DISABLED, MONITORING, RUNNING, COOLDOWN
    - Hysteresis control (separate start/stop thresholds)
    - Maximum runtime protection with cooldown period
    - Schedule integration (disable during specific time windows)
    - Sabbath support (disable during Shabbat)
    - Sensor validation (range, staleness, availability)
    - Optional notifications when max runtime is reached
    
    Example configuration:
        humidity_switch:
            switch: switch.bathroom_dehumidifier
            sensor: sensor.bathroom_humidity
            base_sensor: sensor.room_humidity for baseline 
            input_start: 65.0              # Start when humidity > 65%
            input_stop: 60.0               # Stop when humidity <= 60%
            max_time_minutes: 120          # Max 2 hours continuous run
            cooldown_minutes: 180          # 3 hour cooldown after max runtime
            enable: input_boolean.dehumidifier_enable
            sensor_max_age_minutes: 10     # Optional (default: 10)
            notify_service: notify/telegram  # Optional
    """
    
    # States
    DISABLED = 0
    MONITORING = 1
    RUNNING = 2
    COOLDOWN = 3
    
    # Default values
    DEFAULT_SENSOR_MAX_AGE_MINUTES = 10
    DEFAULT_COOLDOWN_MINUTES = 180  # 3 hours
    
    def __init__(self, ad, cfg: dict):
        """Initialize the humidity switch sensor.
        
        Args:
            ad: AppDaemon instance
            cfg: Configuration dictionary
        """
        self.ad = ad
        self.cfg = cfg
        
        # State tracking
        self.state = HumiditySwitchSensor.DISABLED
        self.sabbath = False
        
        # Handles for listeners and timers
        self.sensor_handle = None
        self.max_runtime_handle = None
        self.cooldown_handle = None
        self.base_sensor_handle = None
        
        
        # Runtime tracking
        self.start_time = None
        
        # Configuration validation
        input_start = float(cfg.get("input_start", 65.0))
        input_stop = float(cfg.get("input_stop", 60.0))
        
        if input_start <= input_stop:
            raise ValueError(
                f"Hysteresis validation failed: input_start ({input_start}) must be > input_stop ({input_stop})"
            )
        
        # Configuration parameters
        self.input_start = input_start
        self.input_stop = input_stop
        self.max_time_minutes = int(cfg.get("max_time_minutes", 120))
        self.cooldown_minutes = int(cfg.get("cooldown_minutes", self.DEFAULT_COOLDOWN_MINUTES))
        self.sensor_max_age_minutes = int(
            cfg.get("sensor_max_age_minutes", self.DEFAULT_SENSOR_MAX_AGE_MINUTES)
        )        
        self.base_sensor_value = self.get_float("base_sensor",50.0)
        if not self.base_sensor_handle:
            self.base_sensor_handle = self.ad.listen_state(
                self.on_base_sensor_change, 
                self.cfg["base_sensor"]
            )

        # Optional notification service
        self.notify_service = cfg.get("notify_service", None)
        
        # Register Sabbath event listener
        self.ad.listen_event(self.on_sabbath_event, HEBCAL_EVENT)
        
        # Listen to enable switch changes
        self.ad.listen_state(self.on_enable_change, self.cfg["enable"])
        
        self.notify(
            f"Initialized: start={self.input_start}%, stop={self.input_stop}%, "
            f"max={self.max_time_minutes}min, cooldown={self.cooldown_minutes}min"
        )
        
        # Note: State will be set by init_state() which is called after schedule.init()

    def get_float(self,name,def_val):
        res = def_val
        try:
          val=self.ad.get_state(self.cfg[name])
          if val is not None:
               res=float(val)
        except (ValueError,TypeError):
          pass;
        return(res)

    def init_state(self):
        """Initialize state after schedule setup.
        
        This is called by the wrapper after schedule.init() completes.
        It ensures we start in the correct state based on current conditions.
        
        Note: If schedule.init() already called on_schedule_event and transitioned
        us to MONITORING or kept us DISABLED, we don't need to do anything.
        """
        # Only act if we're still in initial DISABLED state
        if self.state != HumiditySwitchSensor.DISABLED:
            self.notify(f"Already transitioned from DISABLED by schedule, current state OK")
            return
        
        enable_state = self.ad.get_state(self.cfg["enable"])
        self.notify(f"Still in DISABLED after schedule init - sabbath={self.sabbath}, enable={enable_state}")
        
        if self.sabbath:
            self.notify("Sabbath active at startup, staying DISABLED")
            return
        
        if not state_to_bool(enable_state):
            self.notify("Enable switch is OFF at startup, staying DISABLED")
            return
        
        # If we get here, conditions are good to start monitoring
        # This means schedule.init() didn't call us (empty schedule or disable_startup=true)
        self.notify("No active schedule and conditions OK, transitioning to MONITORING")
        self._transition_to_monitoring()
    
    def is_enabled(self) -> bool:
        """Check if automation should be active.
        
        Returns False if schedule is active OR sabbath is active.
        """
        s = self.ad.get_state(self.cfg["enable"])
        return bool(state_to_bool(s)) and not self.sabbath
    
    def is_turn_on(self) -> bool:
        """Check if switch is currently on."""
        if self.ad.get_state(self.cfg["switch"]) == "on":
            return True
        else:
            return False
    
    def notify(self, msg):
        """Log message with context."""
        t = datetime.datetime.now().strftime("%H:%M:%S")
        sw = self.cfg["switch"]
        state_names = ["DISABLED", "MONITORING", "RUNNING", "COOLDOWN"]
        state_name = state_names[self.state]
        log_msg = f"[humidity], {t}, {sw}, state={state_name}, {msg}"
        self.ad.log(log_msg)
    
    def notify_user(self, msg):
        """Send notification to user (if notification service configured)."""
        t = datetime.datetime.now().strftime("%H:%M:%S")
        sw = self.cfg["switch"]
        notify_msg = f"Humidity: {sw}, {msg}"
        self.ad.notify(notify_msg)
        if self.notify_service:
            try:
                self.ad.call_service(self.notify_service, message=notify_msg)
            except Exception as e:
                self.notify(f"Failed to send notification: {e}")
    
    def _is_sensor_valid(self, value) -> tuple:
        """Validate sensor reading.
        
        Returns:
            (is_valid: bool, humidity_value: float or None)
        """
        # Check for unavailable/unknown states
        if value is None or value in ["unavailable", "unknown", "none", "None"]:
            return (False, None)
        
        # Try to convert to float
        try:
            humidity = float(value)
        except (ValueError, TypeError):
            return (False, None)
        
        # Check valid range (0-100%)
        if humidity < 0.0 or humidity > 100.0:
            return (False, None)
        
        return (True, humidity)
    
    def on_schedule_event(self, kwargs):
        """Handle schedule start/end events."""
        if kwargs["state"] == "on":
            # Schedule started - disable automation
            self.notify("Schedule active, disabling")
            self._transition_to_disabled()
        elif kwargs["state"] == "off":
            # Schedule ended - enable automation if conditions allow
            enable_state = self.ad.get_state(self.cfg["enable"])
            self.notify(f"Schedule inactive - sabbath={self.sabbath}, enable={enable_state}")
            
            if self.sabbath:
                self.notify("Sabbath active, staying disabled")
            elif not state_to_bool(enable_state):
                self.notify("Enable switch is OFF, staying disabled")
            else:
                self.notify("Starting monitoring")
                self._transition_to_monitoring()
    
    def on_sabbath_event(self, event_name, data, kwargs):
        """Handle Sabbath (Shabbat) events."""
        if data["state"] == "pre":
            # Sabbath starting - force disable
            self.sabbath = True
            self.notify("Sabbath starting, forcing disable")
            self._transition_to_disabled()
        elif data["state"] == "off":
            # Sabbath ending - enable if schedule allows
            self.sabbath = False
            if self.is_enabled():
                self.notify("Sabbath ended, resuming monitoring")
                self._transition_to_monitoring()
            else:
                self.notify("Sabbath ended but schedule/enable prevents monitoring")
    
    def on_enable_change(self, entity, attribute, old, new, kwargs):
        """Handle enable switch changes."""
        if old != new:
            self.notify(f"Enable switch changed from {old} to {new}")
            
            if new == "on":
                # Enable switch turned ON - start monitoring if conditions allow
                if self.state == HumiditySwitchSensor.DISABLED and not self.sabbath:
                    # We're disabled but not due to sabbath, likely due to enable switch
                    # Need to check if schedule is currently active
                    # For now, we'll just transition to monitoring and let schedule handle it
                    self.notify("Enable switch ON, attempting to start monitoring")
                    self._transition_to_monitoring()
            else:
                # Enable switch turned OFF - force disable
                if self.state != HumiditySwitchSensor.DISABLED:
                    self.notify("Enable switch OFF, forcing disable")
                    self._transition_to_disabled()
    
    
    def on_base_sensor_change(self, entity, attribute, old, new, kwargs):
        is_valid, humidity = self._is_sensor_valid(new)

        if not is_valid:
            self.notify(f"Invalid base sensor reading : {new}, continuing in current state")
            return
        self.base_sensor_value = humidity # will taken next calculation of on_sensor_change, this change is very slow, no need to update the monitor 
        

    def on_sensor_change(self, entity, attribute, old, new, kwargs):
        """Handle sensor state changes."""
        # Validate sensor value
        is_valid, humidity = self._is_sensor_valid(new)
        
        if not is_valid:
            self.notify(f"Invalid sensor reading: {new}, continuing in current state")
            return
        
        # State-dependent threshold logic
        if self.state == HumiditySwitchSensor.MONITORING:
            # Check start threshold
            if humidity > self.input_start and humidity > (self.base_sensor_value *0.9): # to verify that it is not just hot , like very hot day outside
                if self.is_enabled():
                    self.notify(f"Humidity {humidity:.1f}%  > start threshold {self.input_start}%, Base {self.base_sensor_value:.1f}% ")
                    self._transition_to_running()
                else:
                    self.notify(f"Humidity {humidity:.1f}% > start threshold but disabled by schedule/sabbath")
            else:
                # Log periodic status (only occasionally to avoid spam)
                pass  # Stay in MONITORING state
        
        elif self.state == HumiditySwitchSensor.RUNNING:
            # Check stop threshold
            if humidity <= self.input_stop or humidity <= (self.base_sensor_value *1.2):
                runtime_min = (datetime.datetime.now() - self.start_time).total_seconds() / 60
                self.notify(
                    f"Humidity {humidity:.1f}% <= stop threshold {self.input_stop}%,  base {self.base_sensor_value}% "
                    f"stopping after {runtime_min:.1f} min"
                )
                self._transition_to_monitoring()
            else:
                # Still above stop threshold, continue running
                pass
    
    def _transition_to_disabled(self):
        """Transition to DISABLED state."""
        # Cancel all listeners and timers
        if self.sensor_handle:
            self.ad.cancel_listen_state(self.sensor_handle)
            self.sensor_handle = None
        
        if self.max_runtime_handle:
            self.ad.cancel_timer(self.max_runtime_handle)
            self.max_runtime_handle = None
        
        if self.cooldown_handle:
            self.ad.cancel_timer(self.cooldown_handle)
            self.cooldown_handle = None
        
        # Turn off switch
        if self.is_turn_on():
            self.ad.turn_off(self.cfg["switch"])
        
        self.state = HumiditySwitchSensor.DISABLED
        self.notify("Transitioned to DISABLED")
    
    def _transition_to_monitoring(self):
        """Transition to MONITORING state."""
        # Cancel any active timers
        if self.max_runtime_handle:
            self.ad.cancel_timer(self.max_runtime_handle)
            self.max_runtime_handle = None
        
        if self.cooldown_handle:
            self.ad.cancel_timer(self.cooldown_handle)
            self.cooldown_handle = None
        
        # Ensure switch is off
        if self.is_turn_on():
            self.ad.turn_off(self.cfg["switch"])
        
        # Register sensor listener
        if not self.sensor_handle:
            self.sensor_handle = self.ad.listen_state(
                self.on_sensor_change, 
                self.cfg["sensor"]
            )
        
        self.state = HumiditySwitchSensor.MONITORING
        self.notify("Transitioned to MONITORING")
        
        # Check current sensor value immediately
        current_value = self.ad.get_state(self.cfg["sensor"])
        self.on_sensor_change(self.cfg["sensor"], None, None, current_value, None)
    
    def _transition_to_running(self):
        """Transition to RUNNING state."""
        # Turn on switch
        if not self.is_turn_on():
            self.ad.turn_on(self.cfg["switch"])
        
        # Record start time
        self.start_time = datetime.datetime.now()
        
        # Start max runtime timer
        if self.max_runtime_handle:
            self.ad.cancel_timer(self.max_runtime_handle)
        
        self.max_runtime_handle = self.ad.run_in(
            self._on_max_runtime, 
            self.max_time_minutes * 60
        )
        
        # Keep sensor listener active (already registered)
        
        self.state = HumiditySwitchSensor.RUNNING
        
        # Read current humidity for logging
        current_value = self.ad.get_state(self.cfg["sensor"])
        is_valid, humidity = self._is_sensor_valid(current_value)
        humidity_str = f"{humidity:.1f}%" if is_valid else "unknown"
        
        self.notify(
            f"Transitioned to RUNNING, humidity: {humidity_str}, "
            f"start: {self.input_start}%, stop: {self.input_stop}%, "
            f"max runtime: {self.max_time_minutes} min"
        )
    
    def _transition_to_cooldown(self):
        """Transition to COOLDOWN state."""
        # Cancel sensor listener
        if self.sensor_handle:
            self.ad.cancel_listen_state(self.sensor_handle)
            self.sensor_handle = None
        
        # Cancel max runtime timer (safety)
        if self.max_runtime_handle:
            self.ad.cancel_timer(self.max_runtime_handle)
            self.max_runtime_handle = None
        
        # Turn off switch
        if self.is_turn_on():
            self.ad.turn_off(self.cfg["switch"])
        
        # Calculate actual runtime
        if self.start_time:
            runtime_min = (datetime.datetime.now() - self.start_time).total_seconds() / 60
        else:
            runtime_min = 0
        
        # Start cooldown timer
        if self.cooldown_handle:
            self.ad.cancel_timer(self.cooldown_handle)
        
        self.cooldown_handle = self.ad.run_in(
            self._on_cooldown_complete, 
            self.cooldown_minutes * 60
        )
        
        self.state = HumiditySwitchSensor.COOLDOWN
        self.notify(
            f"Transitioned to COOLDOWN for {self.cooldown_minutes} min, "
            f"total runtime: {runtime_min:.1f} min"
        )
    
    def _on_max_runtime(self, kwargs):
        """Timer callback when max runtime is reached."""
        self.max_runtime_handle = None
        
        # Read current humidity
        current_value = self.ad.get_state(self.cfg["sensor"])
        is_valid, humidity = self._is_sensor_valid(current_value)
        humidity_str = f"{humidity:.1f}%" if is_valid else "unknown"
        
        msg = (
            f"Maximum runtime reached ({self.max_time_minutes} min) but humidity "
            f"is still {humidity_str} (target: {self.input_stop}%). Device may not be working properly."
        )
        
        self.notify(msg)
        
        # Send notification if configured
        if self.notify_service:
            self.notify_user(f"⚠️ {msg}")
        
        # Transition to cooldown
        self._transition_to_cooldown()
    
    def _on_cooldown_complete(self, kwargs):
        """Timer callback when cooldown period is complete."""
        self.cooldown_handle = None
        
        self.notify("Cooldown complete")
        
        # Resume monitoring if enabled
        if self.is_enabled():
            self._transition_to_monitoring()
        else:
            self.notify("Cooldown complete but automation disabled, staying in DISABLED state")
            self.state = HumiditySwitchSensor.DISABLED
