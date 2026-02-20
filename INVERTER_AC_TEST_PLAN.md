# Inverter AC Application - Test Plan

## Overview

This document provides step-by-step testing instructions for the new `InverterAcApp` implementation that automatically selects heat/cool mode based on dual sensor readings.

## Prerequisites

1. Home Assistant with AppDaemon running
2. A climate entity configured (e.g., `climate.ac1`)
3. Two heat index sensors configured:
   - Inside sensor (e.g., `variable.heat_index0`)
   - Outside sensor (e.g., `variable.heat_index_outside0`)
4. Input boolean for manual control (e.g., `input_boolean.ac1_input`)
5. Input boolean for enable switch (e.g., `input_boolean.heat_app_enable`)

## Test Configuration

Add this configuration to `apps.yaml` (uncomment the example):

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

## Test Cases

### Test 1: Both Sensors Agree - Cooling Needed

**Setup:**
1. Enable switch: ON (`input_boolean.heat_app_enable = on`)
2. Manually start: OFF
3. Time: Within schedule window (11:30-17:00)

**Steps:**
1. Set inside sensor to 28.0°C: `variable.heat_index0 = 28.0`
2. Set outside sensor to 52.0°C: `variable.heat_index_outside0 = 52.0`
3. Wait for sensor state changes to propagate

**Expected Results:**
- Log: `[InverterAC] ... COOLING NEEDED: inside=28.0 > 27.5, outside=52.0 > 27.5`
- Log: `[InverterAC] ... Started COOL mode at 24.0°C`
- Climate entity state: `hvac_mode = cool`, `temperature = 24.0`
- State: `RUNNING_COOL`
- Sensor monitoring: Stopped (unsubscribed)

### Test 2: Both Sensors Agree - Heating Needed

**Setup:**
1. Enable switch: ON
2. Manually start: OFF
3. Time: Within schedule window

**Steps:**
1. Set inside sensor to 20.0°C: `variable.heat_index0 = 20.0`
2. Set outside sensor to 5.0°C: `variable.heat_index_outside0 = 5.0`
3. Wait for sensor state changes

**Expected Results:**
- Log: `[InverterAC] ... HEATING NEEDED: inside=20.0 < 22.0, outside=5.0 < 22.0`
- Log: `[InverterAC] ... Started HEAT mode at 26.0°C`
- Climate entity state: `hvac_mode = heat`, `temperature = 26.0`
- State: `RUNNING_HEAT`
- Sensor monitoring: Stopped

### Test 3: Sensors Disagree - Inside Hot, Outside Cold

**Setup:**
1. Enable switch: ON
2. Manually start: OFF
3. Time: Within schedule window

**Steps:**
1. Set inside sensor to 28.0°C
2. Set outside sensor to 10.0°C (cold)
3. Wait for sensor state changes

**Expected Results:**
- Log: `[InverterAC] ... No action needed: inside=28.0 (22.0-27.5), outside=10.0`
- State: `MONITORING` (continues monitoring)
- AC: Not started
- Sensor monitoring: Active

### Test 4: Sensors in Acceptable Range

**Setup:**
1. Enable switch: ON
2. Manually start: OFF
3. Time: Within schedule window

**Steps:**
1. Set inside sensor to 25.0°C (between 22.0 and 27.5)
2. Set outside sensor to 30.0°C
3. Wait for sensor state changes

**Expected Results:**
- Log: `[InverterAC] ... No action needed: inside=25.0 (22.0-27.5), outside=30.0`
- State: `MONITORING`
- AC: Not started

### Test 5: Schedule End While Running

**Setup:**
1. AC running in COOL mode (from Test 1)
2. Time: Approaching schedule end (17:00)

**Steps:**
1. Wait for schedule end time

**Expected Results:**
- Log: `[InverterAC] ... Schedule ended, stopping AC`
- Log: `[InverterAC] ... AC stopped`
- Climate entity: `hvac_mode = off`
- State: `DISABLED`
- Input boolean: Turned OFF automatically

### Test 6: Stale Inside Sensor

**Setup:**
1. Enable switch: ON
2. Time: Within schedule window
3. Inside sensor: Last updated > 10 minutes ago

**Steps:**
1. Set outside sensor to 52.0°C (fresh)
2. Inside sensor remains stale (don't update it)
3. Wait for sensor state changes

**Expected Results:**
- Log: `[InverterAC] ... WARNING: Stale sensor data: variable.heat_index0 (15.3 min) (max: 10 min). Skipping decision cycle.`
- State: `MONITORING` (continues monitoring)
- AC: Not started

### Test 7: Stale Outside Sensor

**Setup:**
1. Enable switch: ON
2. Time: Within schedule window
3. Outside sensor: Last updated > 10 minutes ago

**Steps:**
1. Set inside sensor to 28.0°C (fresh)
2. Outside sensor remains stale
3. Wait for sensor state changes

**Expected Results:**
- Log: `[InverterAC] ... WARNING: Stale sensor data: variable.heat_index_outside0 (20.1 min) (max: 10 min). Skipping decision cycle.`
- State: `MONITORING`
- AC: Not started

### Test 8: Sensor Recovery from Stale State

**Setup:**
1. Previously stale sensor (Test 6 or 7)
2. Enable switch: ON
3. Time: Within schedule window

**Steps:**
1. Update inside sensor to 28.0°C (now fresh)
2. Update outside sensor to 52.0°C (now fresh)
3. Wait for sensor state changes

**Expected Results:**
- No more stale sensor warnings
- Log: `[InverterAC] ... COOLING NEEDED: inside=28.0 > 27.5, outside=52.0 > 27.5`
- AC starts normally in COOL mode

### Test 9: Enable Switch OFF at Schedule Start

**Setup:**
1. Enable switch: OFF (`input_boolean.heat_app_enable = off`)
2. Time: Just before schedule start (11:29:59)

**Steps:**
1. Wait for schedule start time (11:30:00)

**Expected Results:**
- Log: `[InverterAC] ... Schedule started but enable=OFF, staying DISABLED`
- State: `DISABLED`
- Sensor monitoring: Not started
- AC: Not started

### Test 10: Input ON Outside Schedule, Enable ON

**Setup:**
1. Enable switch: ON
2. Time: Outside schedule window (e.g., 10:00)
3. Input boolean: OFF

**Steps:**
1. Toggle input boolean ON: `input_boolean.ac1_input = on`
2. Set sensors to trigger cooling (inside=28°C, outside=52°C)

**Expected Results:**
- Log: `[InverterAC] ... Manual start: loading mode a`
- State: `MONITORING`
- Sensor monitoring: Active
- Eventually transitions to `RUNNING_COOL` when sensors checked

### Test 11: Input ON Outside Schedule, Enable OFF

**Setup:**
1. Enable switch: OFF
2. Time: Outside schedule window
3. Input boolean: OFF

**Steps:**
1. Toggle input boolean ON

**Expected Results:**
- Log: `[InverterAC] ... Manual start ignored: enable switch is OFF`
- State: `DISABLED`
- AC: Not started

### Test 12: Input OFF During Schedule (Emergency Stop)

**Setup:**
1. AC running in COOL mode
2. Time: Within schedule window
3. Enable switch: ON

**Steps:**
1. Toggle input boolean OFF: `input_boolean.ac1_input = off`

**Expected Results:**
- Log: `[InverterAC] ... Manual stop requested`
- Log: `[InverterAC] ... AC stopped`
- Climate entity: `hvac_mode = off`
- State: `DISABLED`
- Sensor monitoring: Stopped

## Verification Checklist

After running all tests, verify:

- [ ] Cooling mode activated correctly when both sensors hot
- [ ] Heating mode activated correctly when both sensors cold
- [ ] No action taken when sensors disagree
- [ ] No action taken when sensors in acceptable range
- [ ] Schedule end stops AC properly
- [ ] Stale sensor detection works (inside and outside)
- [ ] System recovers when stale sensors become fresh
- [ ] Enable switch OFF at schedule start prevents monitoring
- [ ] Manual start works outside schedule (with enable ON)
- [ ] Manual start ignored when enable OFF
- [ ] Emergency stop (input OFF) works during operation

## Log Monitoring

Watch AppDaemon logs for these key messages:

```bash
tail -f /path/to/appdaemon/logs/inverter_ac_living_room.log
```

Key log patterns to look for:
- `[InverterAC] ... Schedule started, enable=ON, entering MONITORING`
- `[InverterAC] ... COOLING NEEDED: ...`
- `[InverterAC] ... HEATING NEEDED: ...`
- `[InverterAC] ... WARNING: Stale sensor data: ...`
- `[InverterAC] ... Started COOL/HEAT mode at ...`
- `[InverterAC] ... AC stopped`

## Troubleshooting

### AC Not Starting
1. Check enable switch is ON
2. Verify sensors are updating (not stale)
3. Confirm sensor values meet thresholds
4. Check AppDaemon logs for error messages

### Unexpected Mode Selection
1. Verify sensor values
2. Check mode configuration (min_i, max_i values)
3. Ensure both sensors agree on direction

### Stale Sensor Warnings
1. Check sensor update frequency
2. Adjust `sensor_max_age_minutes` if needed
3. Verify Home Assistant sensor integration is working

## Success Criteria

The implementation is successful if:

1. ✅ All 12 test cases pass
2. ✅ No Python syntax errors
3. ✅ Logs show correct state transitions
4. ✅ Climate entity controlled correctly (mode + temperature)
5. ✅ Sensor staleness detection works
6. ✅ Manual override (input switch) works as expected
7. ✅ Enable switch behavior is read-only at schedule start
8. ✅ Schedule integration works correctly
9. ✅ No interference with existing HeatApp configurations

## Notes

- The new `InverterAcApp` runs independently from existing `HeatApp` instances
- Both classes can coexist and control different AC units
- The schedule module remains completely unchanged
- Existing configurations continue to work without modification
