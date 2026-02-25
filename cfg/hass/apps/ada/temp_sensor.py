"""
This module implements the Schedule and Rule classes.
"""

import typing as T  # pylint: disable=unused-import

import collections
import datetime
from . import util

def state_to_bool (state:str):
   return(True if state=="on" else False)

class SimpleSwitch:
    """ Contorl Heater by 3 params

        example:

         switch: switch.ac1
         enable: switch.user_input

    """
    def __init__(self, ad, cfg: dict):
        self.ad = ad
        self.cfg =cfg
        self.ad.listen_state(self.do_button, self.cfg["enable"])

    def is_enabled (self):
        s=self.ad.get_state(self.cfg["enable"]);
        return bool(state_to_bool(s))

    def do_button(self,entity, attribute, old, new, kwargs):
        msg="button pressed {0} to {1} ".format(old,new)
        self.notify (msg)

    def is_turn_on (self):
        if self.ad.get_state( self.cfg["switch"])=="on":
            return True
        else:
            return False

    def notify (self,msg):
        sw=self.cfg["switch"];
        state='on' if self.is_turn_on() else 'off'
        t=datetime.datetime.now().strftime("%H:%M:%S")
        log_msg="[ss], {0}, {1}, {2}".format(t,sw,msg)
        notify_msg="ss, {0}, {1}, {2}".format(t,sw,msg)
        self.ad.notify(notify_msg)
        self.ad.log(log_msg);

    def turn_on (self):
        if self.is_enabled():
           if self.is_turn_on()==False:
              sw=self.cfg["switch"];
              self.ad.turn_on(sw)
              self.notify("turn on")

    def turn_off (self):
        if self.is_turn_on():
            self.notify ("turn off")
        self.ad.turn_off(self.cfg["switch"])

    def on_schedule_event (self,kwargs):
        if kwargs['state']=="on":
            self.ad.log(" event on" );
            self.turn_on()

        if kwargs['state']=="off":
            self.ad.log(" event off");
            self.turn_off()


class HeaterSensor:
    """ Contorl Heater by 3 params

        example:
         mode: heat or cool 
         switch: switch.ac1
         sensor_inside :  sensor.temperature
         sensor_outside : sensor.temperature
         enable : switch.ac1
         modes :
            a : { min: 25, max: 27} 
      


    """
    # state of the 
    DISABLED = 17  # switch is off, not looking into the temperator
    WAIT_FOR_HEAT=18  # switch is off, wait for heat
    WAIT_FOR_COOL=19  # switch is on, wait for cool

    MODE_HEAT ='heat'
    MODE_COOL ='cool'

    def __init__(self, ad, cfg: dict):
        self.ad=ad
        self.cfg =cfg
        self.c_min_o=None # min_out temperator to stop 
        self.c_max_i=None # max_in temperator to start 
        self.c_min_i=None # min_in temperator to start 
        self.cnt = 0


        self.state = HeaterSensor.DISABLED
        
        self.sensor_inisde_handle=None
        self.sensor_outside_handle=None
        self.ad.listen_state(self.do_button, self.cfg["enable"])
        self.ad.listen_state(self.do_input, self.cfg["input"])
        self.user_input = self.ad.get_state(self.cfg["input"])
        if self.user_input == "on":
            self.do_input(None, None, "off", "on",None)


    def is_enabled (self):
        s=self.ad.get_state(self.cfg["enable"]);
        return bool(state_to_bool(s))

    def get_float(self,name,def_val):
        res=def_val;
        try:
          val=self.ad.get_state(self.cfg[name])
          if val is not None:
               res=float(val)
        except ValueError:
          pass;
        return(res)

    def get_temp_inside (self):
        return self.get_float("sensor_inside",-1.0)

    def get_temp_outside (self):
        return self.get_float("sensor_outside",-1.0)

    def disable_state(self):
        if self.sensor_inisde_handle:
            self.ad.cancel_listen_state(self.sensor_inisde_handle)
            self.sensor_inisde_handle=None

        if self.sensor_outside_handle:
            self.ad.cancel_listen_state(self.sensor_outside_handle)
            self.sensor_outside_handle=None

    def set_process(self,enable):
        if enable:
            if self.is_enabled():
              self.disable_state()
              self.state = HeaterSensor.WAIT_FOR_HEAT
              self.sensor_inisde_handle = self.ad.listen_state(self.do_check_temperator, self.cfg["sensor_inside"])
              self.sensor_outside_handle= self.ad.listen_state(self.do_check_temperator, self.cfg["sensor_outside"])
              self.do_check_temperator(None, None, None, None,None)
        else:
            self.disable_state()
            self.state = HeaterSensor.DISABLED
            self.turn_off()

    def turn_off_input(self):
        sw=self.cfg["input"];
        self.ad.turn_off(sw)

    def do_button(self,entity, attribute, old, new, kwargs):
        msg="turn on by user" if new=="on" else "turn off by user"
        self.notify (msg)

    def do_input(self,entity, attribute, old, new, kwargs):
        msg="input changed by user" if new=="on" else "turn off by user"
        self.notify (msg)
        if new=="on":
            # off->on
            if self.state == HeaterSensor.DISABLED:
                if self.is_enabled():
                    mode=self.cfg["mode"]
                    t=self.cfg["modes"][self.cfg["default"]][mode]
                    self.ad.log(t)
                    self.c_min_i=t["min_i"]
                    self.c_max_i=t["max_i"]
                    self.c_min_o=t["min_o"]
                    self.ad.log(" start process" +str(t));
                    self.set_process(True)
                else:    
                    self.turn_on()
        else:
            # on->off 
            if self.is_enabled():
                if self.state != HeaterSensor.DISABLED:
                    self.c_min_i=None
                    self.c_max_i=None
                    self.c_min_o=None
                    self.ad.log(" stop process");
                    self.set_process(False)
            else:
                    self.turn_off()
    
    def sanity_check(self):
        # check state and switch state are in sync with state else we need to fix this
        # it could be the case in case of a race (we turn it off but MQTT is slow or in case user change it)
        # we need to make sure it 4 times in the wrong place to fix it !
        is_on = self.is_turn_on ()
        if self.state == HeaterSensor.WAIT_FOR_HEAT:
            if is_on :
                self.cnt+=1
                self.ad.log("out of sync state {} turn off {}".format(self.state,self.cnt))
                if self.cnt > 4:
                    self.turn_off ()
                    self.cnt = 0
            else:
                self.cnt = 0  # OK

        elif self.state == HeaterSensor.WAIT_FOR_COOL:
            if is_on == False :
                self.cnt+=1
                self.ad.log("out of sync state {} turn on {}".format(self.state,self.cnt))
                if self.cnt > 4:
                    self.turn_on ()
                    self.cnt = 0
                else:    
                    self.cnt = 0

    def do_cool (self,it,ot):
        if self.state == HeaterSensor.WAIT_FOR_HEAT:
            if (it > self.c_max_i):
                self.turn_on()
                self.state = HeaterSensor.WAIT_FOR_COOL
        else:
            if self.state == HeaterSensor.WAIT_FOR_COOL:
                if ot < self.c_min_o:
                    if it<self.c_min_i:
                        self.state = HeaterSensor.WAIT_FOR_HEAT
                        self.notify ("LOW STATE ")
                        self.turn_off()
            else:
                assert(0); # not possible 

    def do_heat (self,it,ot):
        # the states
        if self.state == HeaterSensor.WAIT_FOR_HEAT:
                if (it < self.c_min_i):
                    self.turn_on()
                    self.state = HeaterSensor.WAIT_FOR_COOL
        else:
            if self.state == HeaterSensor.WAIT_FOR_COOL:
                if it > self.c_max_i:
                    self.state = HeaterSensor.WAIT_FOR_HEAT
                    self.notify ("LOW STATE ")
                    self.turn_off()
            else:
                assert(0); # not possible 


    def do_check_temperator (self,entity, attribute, old, new, kwargs):
        if self.state == HeaterSensor.DISABLED:
            return;
        assert(self.c_min_i!=None)
        assert(self.c_max_i!=None)
        assert(self.c_min_o!=None)

        if not self.is_enabled ():
            self.set_process(False)
            return;

        it = self.get_temp_inside()
        ot = self.get_temp_outside()

        self.ad.log("do_check_temperator in:{0} out:{1} state:{2} min:max({3}:{4}:{5})".format(it,ot,self.state,self.c_min_o,self.c_min_i,self.c_max_i))

        self.sanity_check()
        if (it>0.0) and (ot>0.0):
           if self.is_cool_mode():
              self.do_cool(it,ot)
           else:
              self.do_heat(it,ot)
            

    def is_turn_on (self):
        if self.ad.get_state( self.cfg["switch"])=="on":
            return True
        else:
            return False

    def notify (self,msg):
        it = self.get_temp_inside()
        ot = self.get_temp_outside()
        sw=self.cfg["switch"];
        state='on' if self.is_turn_on() else 'off'
        t=datetime.datetime.now().strftime("%H:%M:%S")
        self.ad.log("{0} Heater {1}, sw:{2}, current_state:{3}, in:{4}, out:{5}, min_o:{6}, min:{7},max:{8} ".format(t,msg,sw,state,it,ot,self.c_min_o,self.c_min_i,self.c_max_i))

    def turn_on (self):
        if self.is_enabled():
           if self.is_turn_on()==False:
              sw=self.cfg["switch"];
              self.ad.turn_on(sw)
              self.notify ("turn on")

    def turn_off (self):
        if self.is_turn_on():
            self.notify ("turn off")
        self.ad.turn_off(self.cfg["switch"])


    def is_cool_mode (self):
        if self.cfg["mode"] == HeaterSensor.MODE_COOL:
            return True
        else:
            return False

    def on_schedule_event (self,kwargs):
        if kwargs['state']=="on":
            mode=self.cfg["mode"]
            t=self.cfg["modes"][kwargs['rule'].mode][mode]
            self.ad.log(t)
            self.c_min_i=t["min_i"]
            self.c_max_i=t["max_i"]
            self.c_min_o=t["min_o"]

            self.ad.log(" start process" +str(t));
            self.set_process(True)

        if kwargs['state']=="off":
            self.c_min_i=None
            self.c_max_i=None
            self.c_min_o=None
            self.ad.log(" stop process");
            self.set_process(False)
            self.turn_off_input()

class InverterAcSensor:
    """ Control Inverter AC with automatic heat/cool mode selection
    
    Example config:
        climate_entity: climate.ac1
        input: input_boolean.ac1_input
        sensor_inside: variable.heat_index0
        sensor_outside: variable.heat_index_outside0
        enable: input_boolean.heat_app_enable
        sensor_max_age_minutes: 10
        modes:
            a:
                cool: { min_o: 50.0, min_i: 26.5, max_i: 27.5, dest: 24.0 }
                heat: { min_o: 1.0, min_i: 22.0, max_i: 24.0, dest: 26.0 }
    """
    
    # State machine constants
    DISABLED = 0
    MONITORING = 1
    RUNNING_COOL = 2
    RUNNING_HEAT = 3
    
    DEFAULT_SENSOR_MAX_AGE_MIN = 10
    
    def __init__(self, ad, cfg: dict):
        self.ad = ad
        self.cfg = cfg
        self.state = InverterAcSensor.DISABLED
        
        # Configuration
        self.climate_entity = cfg["climate_entity"]
        self.sensor_inside = cfg["sensor_inside"]
        self.sensor_outside = cfg["sensor_outside"]
        self.sensor_max_age_minutes = cfg.get("sensor_max_age_minutes", 
                                               InverterAcSensor.DEFAULT_SENSOR_MAX_AGE_MIN)
        
        # Mode configuration (loaded during schedule event)
        self.cool_min_o = None
        self.cool_min_i = None
        self.cool_max_i = None
        self.cool_dest = None
        self.heat_min_o = None
        self.heat_min_i = None
        self.heat_max_i = None
        self.heat_dest = None
        
        # Sensor monitoring handles
        self.sensor_inside_handle = None
        self.sensor_outside_handle = None
        
        # Listen to input switch for manual override
        self.ad.listen_state(self.do_input_change, self.cfg["input"])
        
        # Check if input is already ON at startup (manual override before schedule)
        user_input = self.ad.get_state(self.cfg["input"])
        if user_input == "on":
            self.do_input_change(None, None, "off", "on", None)
    
    def is_enabled(self):
        """Check if enable switch is ON"""
        state = self.ad.get_state(self.cfg["enable"])
        return bool(state_to_bool(state))
    
    def get_float(self, entity_id, def_val):
        """Get float value from entity"""
        res = def_val
        try:
            val = self.ad.get_state(entity_id)
            if val is not None:
                res = float(val)
        except ValueError:
            pass
        return res
    
    def is_sensor_stale(self, entity_id):
        """Check if sensor data is too old"""
        try:
            from dateutil import parser
            state_obj = self.ad.get_state(entity_id, attribute="all")
            
            if state_obj and "last_updated" in state_obj:
                last_updated = parser.parse(state_obj["last_updated"])
                now = self.ad.get_now()
                age_minutes = (now - last_updated).total_seconds() / 60.0
                
                if age_minutes > self.sensor_max_age_minutes:
                    return True, age_minutes
            return False, 0.0
        except Exception as e:
            self.ad.log(f"Error checking sensor staleness for {entity_id}: {e}")
            return True, 999.0  # Treat as stale on error
    
    def set_monitoring(self, enable):
        """Subscribe/unsubscribe from sensor state changes"""
        if enable:
            if self.is_enabled():
                # Unsubscribe first if already subscribed
                if self.sensor_inside_handle:
                    self.ad.cancel_listen_state(self.sensor_inside_handle)
                if self.sensor_outside_handle:
                    self.ad.cancel_listen_state(self.sensor_outside_handle)
                
                # Subscribe to both sensors
                self.state = InverterAcSensor.MONITORING
                self.sensor_inside_handle = self.ad.listen_state(
                    self.do_check_sensors, self.sensor_inside)
                self.sensor_outside_handle = self.ad.listen_state(
                    self.do_check_sensors, self.sensor_outside)
                
                # Do initial check
                self.do_check_sensors(None, None, None, None, None)
        else:
            # Stop monitoring
            if self.sensor_inside_handle:
                self.ad.cancel_listen_state(self.sensor_inside_handle)
                self.sensor_inside_handle = None
            if self.sensor_outside_handle:
                self.ad.cancel_listen_state(self.sensor_outside_handle)
                self.sensor_outside_handle = None
            
            self.stop_ac()
    
    def do_check_sensors(self, entity, attribute, old, new, kwargs):
        """Main decision logic - check sensors and decide heat/cool/nothing"""
        if self.state != InverterAcSensor.MONITORING:
            return
        
        # Check if enable switch is still ON
        if not self.is_enabled():
            self.set_monitoring(False)
            return
        
        # FIRST: Check sensor staleness
        inside_stale, inside_age = self.is_sensor_stale(self.sensor_inside)
        outside_stale, outside_age = self.is_sensor_stale(self.sensor_outside)
        
        if inside_stale or outside_stale:
            stale_sensors = []
            if inside_stale:
                stale_sensors.append(f"{self.sensor_inside} ({inside_age:.1f} min)")
            if outside_stale:
                stale_sensors.append(f"{self.sensor_outside} ({outside_age:.1f} min)")
            
            self.notify(f"WARNING: Stale sensor data: {', '.join(stale_sensors)} "
                       f"(max: {self.sensor_max_age_minutes} min). Skipping decision cycle.")
            return
        
        # Get current sensor values
        heat_index_inside = self.get_float(self.sensor_inside, -1.0)
        heat_index_outside = self.get_float(self.sensor_outside, -1.0)
        
        # Validate sensor readings
        if heat_index_inside <= 0.0 or heat_index_outside <= 0.0:
            self.ad.log(f"Invalid sensor readings: inside={heat_index_inside}, "
                       f"outside={heat_index_outside}")
            return
        
        self.ad.log(f"Checking sensors: inside={heat_index_inside:.1f}, "
                   f"outside={heat_index_outside:.1f}")
        
        # SECOND: Check COOLING (user preference - check first)
        if (heat_index_inside > self.cool_max_i and 
            heat_index_outside > self.cool_max_i):
            self.notify(f"COOLING NEEDED: inside={heat_index_inside:.1f} > {self.cool_max_i}, "
                       f"outside={heat_index_outside:.1f} > {self.cool_max_i}")
            self.start_cooling()
            return
        
        # THIRD: Check HEATING
        if (heat_index_inside < self.heat_min_i and 
            heat_index_outside < self.heat_min_i):
            self.notify(f"HEATING NEEDED: inside={heat_index_inside:.1f} < {self.heat_min_i}, "
                       f"outside={heat_index_outside:.1f} < {self.heat_min_i}")
            self.start_heating()
            return
        
        # Otherwise: sensors disagree or already in acceptable range
        self.ad.log(f"No action needed: inside={heat_index_inside:.1f} "
                   f"({self.heat_min_i}-{self.cool_max_i}), "
                   f"outside={heat_index_outside:.1f}")
    
    def do_input_change(self, entity, attribute, old, new, kwargs):
        """Handle input switch state changes (user manual override)"""
        msg = "input changed by user" if new == "on" else "turn off by user"
        self.notify(msg)
        
        if new == "on":
            # OFF→ON: User wants to start
            if self.state == InverterAcSensor.DISABLED:
                if self.is_enabled():
                    # Load default mode config
                    mode = self.cfg.get("default", "a")
                    self.load_mode_config(mode)
                    self.ad.log(f"Manual start: loading mode {mode}")
                    self.set_monitoring(True)
                else:
                    self.ad.log("Manual start ignored: enable switch is OFF")
        else:
            # ON→OFF: User wants to stop
            if self.state != InverterAcSensor.DISABLED:
                self.ad.log("Manual stop requested")
                self.set_monitoring(False)
    
    def load_mode_config(self, mode_name):
        """Load configuration for a specific mode"""
        cool_config = self.cfg["modes"][mode_name]["cool"]
        heat_config = self.cfg["modes"][mode_name]["heat"]
        
        self.cool_min_o = cool_config["min_o"]
        self.cool_min_i = cool_config["min_i"]
        self.cool_max_i = cool_config["max_i"]
        self.cool_dest = cool_config["dest"]
        
        self.heat_min_o = heat_config["min_o"]
        self.heat_min_i = heat_config["min_i"]
        self.heat_max_i = heat_config["max_i"]
        self.heat_dest = heat_config["dest"]
    
    def start_cooling(self):
        """Start AC in cool mode"""
        self.ad.log(f"Starting AC in COOL mode at {self.cool_dest}°C")
        
        # Set HVAC mode AND temperature in ONE call (atomic operation)
        self.ad.call_service('climate/set_temperature',
                            entity_id=self.climate_entity,
                            temperature=self.cool_dest,
                            hvac_mode='cool')
        
        # Transition to RUNNING_COOL
        self.state = InverterAcSensor.RUNNING_COOL
        
        # Stop monitoring sensors (unsubscribe)
        if self.sensor_inside_handle:
            self.ad.cancel_listen_state(self.sensor_inside_handle)
            self.sensor_inside_handle = None
        if self.sensor_outside_handle:
            self.ad.cancel_listen_state(self.sensor_outside_handle)
            self.sensor_outside_handle = None
        
        self.notify(f"Started COOL mode at {self.cool_dest}°C")
    
    def start_heating(self):
        """Start AC in heat mode"""
        self.ad.log(f"Starting AC in HEAT mode at {self.heat_dest}°C")
        
        # Set HVAC mode AND temperature in ONE call (atomic operation)
        self.ad.call_service('climate/set_temperature',
                            entity_id=self.climate_entity,
                            temperature=self.heat_dest,
                            hvac_mode='heat')
        
        # Transition to RUNNING_HEAT
        self.state = InverterAcSensor.RUNNING_HEAT
        
        # Stop monitoring sensors (unsubscribe)
        if self.sensor_inside_handle:
            self.ad.cancel_listen_state(self.sensor_inside_handle)
            self.sensor_inside_handle = None
        if self.sensor_outside_handle:
            self.ad.cancel_listen_state(self.sensor_outside_handle)
            self.sensor_outside_handle = None
        
        self.notify(f"Started HEAT mode at {self.heat_dest}°C")
    
    def stop_ac(self):
        """Turn off AC"""
        if self.state in [InverterAcSensor.RUNNING_COOL, InverterAcSensor.RUNNING_HEAT]:
            self.ad.log("Stopping AC")
            self.ad.call_service('climate/turn_off',
                                entity_id=self.climate_entity)
            self.notify("AC stopped")
        
        self.state = InverterAcSensor.DISABLED
    
    def turn_off_input(self):
        """Turn off input switch"""
        sw = self.cfg["input"]
        self.ad.turn_off(sw)
    
    def notify(self, msg):
        """Log message with context"""
        t = datetime.datetime.now().strftime("%H:%M:%S")
        state_name = ["DISABLED", "MONITORING", "RUNNING_COOL", "RUNNING_HEAT"][self.state]
        log_msg = f"[InverterAC] {t} {self.climate_entity}, {msg}, state={state_name}"
        self.ad.log(log_msg)
    
    def on_schedule_event(self, kwargs):
        """Handle schedule events (start/stop)"""
        if kwargs['state'] == "on":
            # Schedule started - check if enabled
            if not self.is_enabled():
                self.notify("Schedule started but enable=OFF, staying DISABLED")
                return
            
            # Load mode configuration
            mode = kwargs['rule'].mode
            self.load_mode_config(mode)
            self.ad.log(f"Schedule started with mode {mode}")
            
            # Enter MONITORING state
            self.notify(f"Schedule started, enable=ON, entering MONITORING")
            self.set_monitoring(True)
        
        elif kwargs['state'] == "off":
            # Schedule ended - stop AC and monitoring
            self.notify("Schedule ended, stopping AC")
            self.set_monitoring(False)


        








