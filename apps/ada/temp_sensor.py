"""
This module implements the Schedule and Rule classes.
"""

import typing as T  # pylint: disable=unused-import

import collections
import datetime
import util

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

    def do_cool (self,it,ot):
        if self.state == HeaterSensor.WAIT_FOR_HEAT:
            if (it > self.c_max_i):
                self.turn_on()
                self.state = HeaterSensor.WAIT_FOR_COOL
            else:
                if self.is_turn_on (): # it was turn on by user 
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
            # the state should be turn off 
            if self.is_turn_on (): # by user 
                self.state = HeaterSensor.WAIT_FOR_COOL 
            else:    
                if (it < self.c_min_i):
                    self.turn_on()
                    self.state = HeaterSensor.WAIT_FOR_COOL
        else:
            if self.state == HeaterSensor.WAIT_FOR_COOL:
                    if not self.is_turn_on () : # by user 
                        self.state = HeaterSensor.WAIT_FOR_HEAT
                    else:    
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

        








