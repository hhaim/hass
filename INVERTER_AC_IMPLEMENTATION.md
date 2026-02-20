# Inverter AC Application - Implementation Summary

## Overview

Successfully implemented a new AppDaemon application (`InverterAcApp`) that intelligently controls inverter air conditioners by automatically selecting heat or cool mode based on dual heat index sensor readings (inside and outside).

## What Was Implemented

### 1. New Class: `InverterAcSensor` (cfg/hass/apps/ada/temp_sensor.py)

A complete state machine implementation with the following features:

**State Machine:**
- `DISABLED` (0): Outside schedule or disabled
- `MONITORING` (1): Inside schedule, listening to sensors
- `RUNNING_COOL` (2): AC running in cool mode
- `RUNNING_HEAT` (3): AC running in heat mode

**Key Features:**
- ✅ Automatic mode selection (heat/cool) based on dual sensor agreement
- ✅ Sensor staleness detection (configurable max age, default 10 minutes)
- ✅ Climate entity control with atomic operations (mode + temperature in one call)
- ✅ Schedule integration (start/stop on schedule events)
- ✅ Manual override via input switch
- ✅ Enable switch validation (read-only at schedule start)
- ✅ Comprehensive logging with timestamps and state tracking

**Decision Logic:**
1. **First**: Check sensor staleness → Skip if stale
2. **Second**: Check cooling condition (both sensors > max_i) → Start COOL
3. **Third**: Check heating condition (both sensors < min_i) → Start HEAT
4. **Otherwise**: Continue monitoring (sensors disagree or in range)

### 2. New Class: `InverterAcApp` (cfg/hass/apps/heat_app.py)

Simple wrapper class that:
- Instantiates `InverterAcSensor` with configuration
- Creates and initializes schedule integration
- Follows same pattern as existing `HeatApp` class

### 3. Example Configuration (cfg/hass/apps/apps.yaml)

Added commented-out example configuration showing:
- New `climate_entity` parameter (replaces `switch`)
- New `dest` parameter for target temperatures
- Automatic mode selection (no fixed `mode` field)
- Dual sensor configuration
- Optional `sensor_max_age_minutes` parameter
- Default mode for manual override

## Key Differences from Existing HeatApp

| Aspect | HeatApp (HeaterSensor) | InverterAcApp (InverterAcSensor) |
|--------|------------------------|----------------------------------|
| Mode selection | Fixed in config (heat OR cool) | **Automatic** (runtime decision) |
| Control mechanism | Switch entity (on/off) | **Climate entity** (mode + temp) |
| Stop condition | Temperature threshold reached | **Only at schedule end** |
| Destination temp | Not used | **Sent to AC** as target |
| Sensor requirement | Single sensor OK | **Both sensors must agree** |
| Staleness check | Not implemented | **Configurable detection** |

## Files Modified

1. **cfg/hass/apps/ada/temp_sensor.py**
   - Added `InverterAcSensor` class (285 lines)
   - No changes to existing classes

2. **cfg/hass/apps/heat_app.py**
   - Added `InverterAcApp` class (8 lines)
   - No changes to existing classes

3. **cfg/hass/apps/apps.yaml**
   - Added commented example configuration
   - No changes to existing configurations

## Files NOT Modified

- ✅ `ada/schedule.py` - Schedule module remains completely untouched
- ✅ Existing `HeaterSensor` class - No changes
- ✅ Existing `HeatApp` class - No changes
- ✅ All other existing applications

## Backward Compatibility

- ✅ Existing `HeatApp` configurations continue to work
- ✅ Both old and new classes can coexist
- ✅ Users can migrate gradually by updating YAML config
- ✅ No breaking changes to any existing functionality

## Configuration Schema

```yaml
inverter_ac_living_room:
  module: heat_app
  class: InverterAcApp
  schedule:
    - { mode: a, start: { t: "11:30:00", d: 0}, end: { t: "17:00:00", d: 0} }
  
  ac:
    climate_entity: climate.ac1          # Climate entity (not switch!)
    input: input_boolean.ac1_input
    sensor_inside: variable.heat_index0
    sensor_outside: variable.heat_index_outside0
    enable: input_boolean.heat_app_enable
    sensor_max_age_minutes: 10           # Optional: default is 10
    default: a                           # Default mode for manual start
    modes:
      a:
        cool: { min_o: 50.0, min_i: 26.5, max_i: 27.5, dest: 24.0 }
        heat: { min_o: 1.0, min_i: 22.0, max_i: 24.0, dest: 26.0 }
```

**New Parameters:**
- `climate_entity`: Climate entity ID (replaces `switch`)
- `dest`: Target temperature for AC in each mode
- `sensor_max_age_minutes`: Maximum age for sensor data (optional)
- `default`: Default mode preset for manual input override

**Removed Parameters:**
- `mode`: No longer needed (automatically selected)

## State Transitions

```
[*] --> DISABLED

DISABLED --> MONITORING: Schedule Start AND enable=ON
DISABLED --> DISABLED: Schedule Start BUT enable=OFF

MONITORING --> RUNNING_COOL: Both sensors > max_i
MONITORING --> RUNNING_HEAT: Both sensors < min_i
MONITORING --> MONITORING: Sensors disagree or in range
MONITORING --> DISABLED: Input OFF (manual stop)

RUNNING_COOL --> DISABLED: Schedule End
RUNNING_COOL --> DISABLED: Input OFF (manual stop)
RUNNING_HEAT --> DISABLED: Schedule End
RUNNING_HEAT --> DISABLED: Input OFF (manual stop)

DISABLED --> MONITORING: Input ON AND enable=ON (manual start)

DISABLED --> [*]
```

## Testing

A comprehensive test plan has been created: `INVERTER_AC_TEST_PLAN.md`

**Test coverage:**
- ✅ Both sensors agree - cooling needed
- ✅ Both sensors agree - heating needed
- ✅ Sensors disagree - inside hot, outside cold
- ✅ Sensors in acceptable range
- ✅ Schedule end while running
- ✅ Stale inside sensor
- ✅ Stale outside sensor
- ✅ Sensor recovery from stale state
- ✅ Enable switch OFF at schedule start
- ✅ Input ON outside schedule, enable ON
- ✅ Input ON outside schedule, enable OFF
- ✅ Input OFF during schedule (emergency stop)

## Code Quality

- ✅ Python syntax validated (py_compile)
- ✅ No new linter errors introduced
- ✅ Comprehensive docstrings
- ✅ Clear logging with context
- ✅ Error handling for sensor failures
- ✅ Following existing code patterns and style

## Usage Instructions

1. **Enable the new configuration:**
   - Edit `cfg/hass/apps/apps.yaml`
   - Uncomment the `inverter_ac_living_room` example
   - Update entity IDs to match your setup
   - Adjust temperature thresholds as needed

2. **Restart AppDaemon:**
   ```bash
   systemctl restart appdaemon
   # or
   supervisorctl restart appdaemon
   ```

3. **Monitor logs:**
   ```bash
   tail -f /path/to/appdaemon/logs/appdaemon.log | grep InverterAC
   ```

4. **Test manually:**
   - Set enable switch ON
   - Adjust sensor values via Home Assistant UI
   - Watch climate entity state changes
   - Verify logs show correct decisions

## Benefits

1. **Intelligent**: Automatically chooses optimal mode based on conditions
2. **Safe**: Sensor staleness detection prevents bad decisions
3. **Flexible**: Easy to configure thresholds and schedules
4. **Reliable**: Atomic climate operations prevent race conditions
5. **Observable**: Comprehensive logging for debugging
6. **Compatible**: Works alongside existing HeatApp configurations

## Next Steps

1. Test with real hardware (climate entity + sensors)
2. Monitor behavior over 24-hour cycle
3. Fine-tune temperature thresholds based on comfort
4. Add more mode presets (b, c) if needed
5. Consider adding notification integration for important events

## Support

For issues or questions:
1. Check AppDaemon logs for error messages
2. Refer to `INVERTER_AC_TEST_PLAN.md` for testing guidance
3. Verify sensor values are updating correctly
4. Ensure climate entity supports heat/cool/off modes

## Credits

Implementation follows the architecture and patterns established in the existing `HeatApp` and `HeaterSensor` classes, maintaining consistency with the codebase while adding new capabilities for inverter AC control.
