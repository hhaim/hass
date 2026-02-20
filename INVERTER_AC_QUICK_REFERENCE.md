# Inverter AC Application - Quick Reference

## Implementation Complete ✅

All 5 todos have been completed:
1. ✅ Created `InverterAcSensor` class in `ada/temp_sensor.py`
2. ✅ Implemented dual-sensor decision logic with staleness checks
3. ✅ Created `InverterAcApp` wrapper class in `heat_app.py`
4. ✅ Added example configuration to `apps.yaml`
5. ✅ Created comprehensive test plan and documentation

## Quick Start

### 1. Enable Configuration

Edit `cfg/hass/apps/apps.yaml` and uncomment lines 89-106:

```yaml
inverter_ac_living_room:
  module: heat_app
  class: InverterAcApp
  schedule:
    - { mode: a, start: { t: "11:30:00", d: 0}, end: { t: "17:00:00", d: 0} }
  ac:
    climate_entity: climate.ac1
    input: input_boolean.ac1_input
    sensor_inside: variable.heat_index0
    sensor_outside: variable.heat_index_outside0
    enable: input_boolean.heat_app_enable
    sensor_max_age_minutes: 10
    default: a
    modes:
      a:
        cool: { min_o: 50.0, min_i: 26.5, max_i: 27.5, dest: 24.0 }
        heat: { min_o: 1.0, min_i: 22.0, max_i: 24.0, dest: 26.0 }
```

### 2. Customize Your Configuration

Update these values for your setup:
- `climate_entity`: Your climate entity ID
- `input`: Your input boolean for manual control
- `sensor_inside`: Your inside heat index sensor
- `sensor_outside`: Your outside heat index sensor
- `enable`: Your enable switch
- Temperature thresholds (min_i, max_i, dest) based on comfort
- Schedule times

### 3. Restart AppDaemon

```bash
systemctl restart appdaemon
```

### 4. Monitor Operation

```bash
tail -f /var/log/appdaemon/appdaemon.log | grep InverterAC
```

## Key Behaviors

### Automatic Mode Selection

**COOLING starts when:**
- Inside sensor > max_i (27.5°C)
- AND outside sensor > max_i (27.5°C)
- Sets AC to cool mode at dest temp (24.0°C)

**HEATING starts when:**
- Inside sensor < min_i (22.0°C)
- AND outside sensor < min_i (22.0°C)
- Sets AC to heat mode at dest temp (26.0°C)

**NO ACTION when:**
- Sensors disagree (one hot, one cold)
- Both sensors in acceptable range
- Sensor data is stale (> 10 minutes old)

### Manual Control

**Start outside schedule:**
- Toggle input boolean ON
- Requires enable switch ON
- Uses default mode configuration

**Emergency stop:**
- Toggle input boolean OFF
- Works anytime (schedule or manual)
- Stops AC immediately

### Safety Features

1. **Sensor Staleness Detection:**
   - Checks sensor last_updated timestamp
   - Skips decisions if data > 10 min old
   - Logs warning with sensor name and age

2. **Enable Switch:**
   - Checked at schedule start
   - If OFF, stays DISABLED
   - Read-only during operation

3. **Dual Sensor Agreement:**
   - Both sensors must agree on direction
   - Prevents inappropriate mode switching
   - Example: Won't cool if outside is cold

## Troubleshooting

### Problem: AC Not Starting

**Check:**
1. Enable switch is ON: `input_boolean.heat_app_enable`
2. Inside schedule window or input switch ON
3. Sensors updating (< 10 min old)
4. Sensor values meet thresholds
5. Climate entity available

**View logs:**
```bash
grep "InverterAC" /var/log/appdaemon/appdaemon.log | tail -20
```

### Problem: Wrong Mode Selected

**Check:**
1. Both sensor values
2. Mode configuration thresholds
3. Ensure sensors agree (both hot or both cold)

**Debug:**
- Set sensors manually in Home Assistant
- Watch logs for decision logic
- Verify temperature thresholds

### Problem: Frequent "Stale Sensor" Warnings

**Solutions:**
1. Check sensor update frequency
2. Increase `sensor_max_age_minutes` if sensors update slowly
3. Verify sensor integration working

## Configuration Parameters

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `climate_entity` | string | Climate entity ID |
| `input` | string | Input boolean for manual control |
| `sensor_inside` | string | Inside heat index sensor |
| `sensor_outside` | string | Outside heat index sensor |
| `enable` | string | Enable switch entity |
| `modes` | dict | Mode configurations |

### Optional

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sensor_max_age_minutes` | int | 10 | Max sensor age before stale |
| `default` | string | "a" | Default mode for manual start |

### Mode Configuration

Each mode (a, b, c) requires:

```yaml
cool:
  min_o: 50.0    # Min outside temp for cooling stop
  min_i: 26.5    # Min inside temp for cooling stop
  max_i: 27.5    # Max inside temp to start cooling
  dest: 24.0     # Target temperature for cool mode

heat:
  min_o: 1.0     # Min outside temp for heating start
  min_i: 22.0    # Min inside temp to start heating
  max_i: 24.0    # Max inside temp for heating stop
  dest: 26.0     # Target temperature for heat mode
```

## Log Messages

### Normal Operation

```
[InverterAC] 14:23:10 climate.ac1, Schedule started, enable=ON, entering MONITORING, state=MONITORING
[InverterAC] 14:23:15 climate.ac1, Checking sensors: inside=28.5, outside=52.0, state=MONITORING
[InverterAC] 14:23:15 climate.ac1, COOLING NEEDED: inside=28.5 > 27.5, outside=52.0 > 27.5, state=MONITORING
[InverterAC] 14:23:15 climate.ac1, Started COOL mode at 24.0°C, state=RUNNING_COOL
[InverterAC] 17:00:00 climate.ac1, Schedule ended, stopping AC, state=DISABLED
```

### Stale Sensor Warning

```
[InverterAC] 14:23:15 climate.ac1, WARNING: Stale sensor data: variable.heat_index_outside0 (15.3 min) (max: 10 min). Skipping decision cycle., state=MONITORING
```

### Enable Switch OFF

```
[InverterAC] 14:23:10 climate.ac1, Schedule started but enable=OFF, staying DISABLED, state=DISABLED
```

## Documentation Files

1. **INVERTER_AC_IMPLEMENTATION.md** - Complete implementation summary
2. **INVERTER_AC_TEST_PLAN.md** - Comprehensive test cases (12 tests)
3. **INVERTER_AC_QUICK_REFERENCE.md** - This file

## Support Resources

- Check logs: `/var/log/appdaemon/appdaemon.log`
- Test plan: `INVERTER_AC_TEST_PLAN.md`
- Implementation details: `INVERTER_AC_IMPLEMENTATION.md`
- Source code: `cfg/hass/apps/ada/temp_sensor.py` (line 338+)

## Migration from HeatApp

### Old Configuration (HeatApp)

```yaml
heater_ac1:
  module: heat_app
  class: HeatApp
  heater:
    mode: cool        # Fixed mode
    switch: switch.ac1  # Switch entity
    ...
```

### New Configuration (InverterAcApp)

```yaml
inverter_ac_living_room:
  module: heat_app
  class: InverterAcApp
  ac:
    climate_entity: climate.ac1  # Climate entity
    # No mode field - automatic!
    modes:
      a:
        cool: { ..., dest: 24.0 }  # Target temp added
        heat: { ..., dest: 26.0 }
```

### Key Changes

1. `heater` → `ac` (section rename)
2. `switch` → `climate_entity` (entity type change)
3. No `mode` field (automatic selection)
4. Add `dest` parameter to each mode
5. Add `default` for manual override

## Notes

- Both `HeatApp` and `InverterAcApp` can coexist
- No changes to schedule module
- Backward compatible with existing configs
- Tested with Python syntax validation
- No new linter errors introduced

## Status

✅ **Implementation Complete**
✅ **Syntax Validated**
✅ **Documentation Complete**
✅ **Test Plan Ready**
⏳ **Awaiting Real Hardware Testing**
