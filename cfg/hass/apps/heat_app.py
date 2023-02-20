import appdaemon.plugins.hass.hassapi as hass
import datetime
from pprint import pprint
import ada.schedule 
import ada.temp_sensor
import ada.temp

HEBCAL_EVENT = "hebcal.event"
EVENTM_EVENT = "eventm.event"
TASMOTA_EVENT = "tasmota.event"

ALARM_WATER_ISSUES = 23

class SimpleSwitch(hass.Hass):

    def initialize(self):
        self.log("start simple-switch {0}".format(str(self.args)));
        self.ss = ada.temp_sensor.SimpleSwitch(self,self.args['switch']);
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.ss.on_schedule_event,None)
        self.sch.init()

class ShuttersApp(hass.Hass):

    def initialize(self):
        self.log("start ShuttersApp")
        self.shutter = self.args["switch"]
        self.enabled = self.args["enable"]
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.on_schedule_event,None)
        self.old_state = None
        self.sch.init()

    def on_schedule_event(self, kwargs):
        if self.enabled:
            if kwargs['state'] == "on":
                if self.is_on() == False:
                    self.old_state = False
                    self.s_turn_on()
                    self.log("shutter in close state")
                else:
                    self.old_state = None
            elif kwargs['state'] == "off":
                if self.old_state == False:
                    self.old_state = None
                    self.log("shutter in open state")
                    self.s_turn_off()

    def s_turn_on(self):
        self.turn_on(self.shutter)

    def s_turn_off(self):
        self.turn_off(self.shutter)

    def is_on(self):
        if self.get_state(self.shutter) == "on":
            return True
        else:
            return False

class HeatApp(hass.Hass):

    def initialize(self):
        self.log("start Heat App")
        self.heater = ada.temp_sensor.HeaterSensor(self,self.args['heater']);
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.heater.on_schedule_event,None)
        self.sch.init()


class CalcHeatIndexApp(hass.Hass):

    def initialize(self):
        self.log("start Calc App ")
        self.update_state ()
        self.listen_state(self.do_check_temperator, self.args["temp"])
        self.listen_state(self.do_check_temperator, self.args["hum"])

    def get_float(self,name,def_val):
        res = def_val
        try:
          val=self.get_state(self.args[name])
          if val is not None:
               res=float(val)
        except (ValueError,TypeError):
          pass;
        return(res)
              
    def update_state (self):
        self.temp = self.get_float("temp",25.0)
        self.hum  = self.get_float("hum",50.0)
        self.calc_result = ada.temp.calc_heat_index_celsius(self.temp, self.hum)
        #self.log(" CALC_T {}, (t:h) {}:{}, res:{}".format(self.args["temp"],self.temp,self.hum,self.calc_result))
        self.set_state(self.args["out"],state = "{0:.1f}".format(self.calc_result))

    def do_check_temperator (self,entity, attribute, old, new, kwargs):
        self.update_state ()


class CTestDays(hass.Hass):

    def initialize(self):
        self.log("start CTestDays");
        self.run_daily(self._cb_event, 
                       self.parse_time("13:36:00"), 
                       constrain_days=ada.schedule.day_of_week(6),
                       a="1",b="2")

        self.run_daily(self._cb_event, 
                       self.parse_time("13:37:00"), 
                       constrain_days=ada.schedule.day_of_week(1),
                       a="3",b="4")

    def _cb_event(self,kwargs):
        """ kwargs include 
           rule=rule
           state=on/off 
        """
        self.log(" event {0} ".format(kwargs))



class SimpleTimerOff(hass.Hass):

    def initialize(self):
        self.log("SimpleTimerOff");
        self.listen_state(self.do_button_change, self.args["input_start"])
        self.handle = None

    def get_timer_time (self):
        r=float(self.get_state(self.args["input_time"]))
        return (int(r))

    def do_turn_off(self):
        self.handle=None
        self.turn_off(self.args["input_start"])
        for sw in self.args["switchs"]:
            self.log(" try to turn off {0}".format(sw));
            if self.get_state(sw)=="on":
               self.log(" state was on, turn off {0}".format(sw));
               self.turn_off(sw)

    def do_button_change (self,entity, attribute, old, new, kwargs):
        if (new == "on") and (self.handle == None):
            self.log("start timer for {0} minutes for {1} switch ".format(self.get_timer_time(),self.args["switchs"]) );
            sec= self.get_timer_time()*60;
            self.handle = self.run_in(self._cb_event, sec)
        else:
            if (new == "off") and (self.handle != None): 
               self.log("stop timer ")
               self.cancel_timer(self.handle)
               self.handle = None

    def _cb_event(self,kargs):
        self.do_turn_off()


class TrackerNotification(hass.Hass):

    def initialize(self):
      self.notify("start TrackerNotification")
      self.listen_state(self.do_tracer_change, 'device_tracker')

    def do_tracer_change (self,entity, attribute, old, new, kwargs):
        if old != new:
            entity = entity.split('.')[1]
            t=datetime.datetime.now().strftime("%H:%M:%S")
            notify_msg=" {3} tracker *{0}*  *{1}* to *{2}* ".format(entity,old,new,t)
            self.log(notify_msg);
            self.notify(notify_msg)

class CPolicer:
    def __init__(self,events_per_hour,queue_size):
        self.max_queue_size = queue_size
        self.queue_size =queue_size
        self.events_per_sec = events_per_hour/(60.0*60.0)
        self.last_time = datetime.datetime.now()
        self.missed_events =0;

    def add_event (self):
        now =datetime.datetime.now()
        dtime = now - self.last_time 
        self.last_time = now
        dadd =float(dtime.seconds) * self.events_per_sec
        self.queue_size += dadd
        if self.queue_size > self.max_queue_size:
            self.queue_size = self.max_queue_size;

        if self.queue_size>1.0:
            self.queue_size -=1.0;
            me=self.missed_events
            self.missed_events=0;
            return(True,me);
        else:
            self.missed_events+=1;
            return(False,self.missed_events);

DOORBELL = 10

class HassBase(hass.Hass):

    GATEWAY_ID ='light.gateway_light_7c49eb193b55'

    def call_alarm (self,rind_id):
        try:
           self.call_service('xiaomi_aqara/play_ringtone', gw_mac= "7C:49:EB:19:3B:55",ringtone_id= rind_id)
        except Exception as e:
            self.log(str(s))


    def retry_turn_on (self,kwargs):
        if self.cnt>10:
            self.set_light(False)
            return;
        self.cnt += 1
        self.toggle_light()
        self.run_in(self.retry_turn_on, 1)

    def blink_light (self):
        self.cnt=0;
        self.toggle_light()
        self.run_in(self.retry_turn_on, 1,)

    def toggle_light(self):
        self.toggle(HassBase.GATEWAY_ID)

    def set_light(self,enable):
        if enable:
           self.turn_on(HassBase.GATEWAY_ID)
        else:
           self.turn_off(HassBase.GATEWAY_ID)

    def set_door_bell (self):
        self.blink_light()
        self.call_alarm(DOORBELL)

    def alert_sms (self,msg):
        try:
           self.call_service('notify/clicksend', message = msg)
        except Exception as e:
            self.log(str(msg))

    def alert_tts (self,msg):
        try:
          self.call_service('notify/clicksend_tts', message = msg)
        except Exception as e:
            self.log(str(msg))

        try:
            self.call_service('notify/clicksend_tts2', message = msg)
        except Exception as e:
            self.log(str(msg))
    
    def my_notify (self,msg):
        t=datetime.datetime.now().strftime("%H:%M:%S")
        n_msg = t +' ' + msg
        self.log(n_msg)
        self.notify(n_msg)


    def is_state_valid (self,state):
        if state in ['on','off']:
            return True
        else:
            return False

    def are_states_valid(self,new,old):
        if self.is_state_valid(new) and self.is_state_valid(old):
            return True
        else:
            return False

    def read_ent_as_float(self,name,def_val=0.0):
        res=def_val;
        try:
          val=self.get_state(name)
          if val is not None:
               res=float(val)
        except (ValueError,TypeError):
          pass;
        return(res)

    def remove_var_prefix (self,entity):
        a = entity.split(".")
        assert(len(a)==2)
        assert(a[0]=='variable')
        return (a[1])
        
    def var_set (self,entity,val):
       var = self.remove_var_prefix(entity) 
       self.call_service('variable/set_variable', variable=var,value=val)
       
    def var_inc (self,entity,value):
       val = self.read_ent_as_float(entity)
       val += value
       var = self.remove_var_prefix(entity) 
       self.call_service('variable/set_variable', variable=var,value="{:.1f}".format(val))

    def var_dec (self,entity,value):
       val = self.read_ent_as_float(entity)
       val -= value
       var = self.remove_var_prefix(entity) 
       self.call_service('variable/set_variable', variable=var,value="{:.1f}".format(val))



class AlarmNotification(HassBase):

    def initialize(self):
      self.home=self.get_state('group.device_tracker')
      self.filter =[]
      for alarm_id in (0,9,10,11,12,13,16):
          self.filter.append('binary_sensor.alarm{0}'.format(alarm_id))

                
      self.external_alarms =['motion_sensor_158d0002b48209',
                             'motion_sensor_158d0002b75328',     
                             'motion_sensor_158d0002b75423',     
                             'motion_sensor_158d0002b7d400',     
                             'motion_sensor_158d0002b7d548',     
                             'motion_sensor_158d0002b7f8b4',     
                             'motion_sensor_158d0002b85a33',
                             'motion_sensor_158d0002c7165a']

      for device_id in self.external_alarms:
           self.listen_state(self.do_state_change, 'binary_sensor.{0}'.format(device_id))

      self.policer = CPolicer(2,20)
      self.notify("start Alarm tracker state {0}".format(self.home))
      self.listen_state(self.do_home_change, 'group.device_tracker')
      for device_id in range(0,17):
           self.listen_state(self.do_state_change, 'binary_sensor.alarm{0}'.format(device_id))

      self.external_sensors =[]
      #self.external_sensors =['smoke_sensor_158d00024e008a',
      #                        'smoke_sensor_158d000287ae79',
      #                        'water_leak_sensor_158d000256cd9d',
      #                        'water_leak_sensor_158d00023385f2',
      #                        'water_leak_sensor_158d000256ce72',
      #                        'water_leak_sensor_158d000256ce93',
      #                        'water_leak_sensor_158d000256cede',
      #                        'water_leak_sensor_158d00027049bb']
      #for device_id in self.external_sensors:
      #     self.listen_state(self.do_state_change, 'binary_sensor.{0}'.format(device_id))

    def do_home_change (self,entity, attribute, old, new, kwargs):
        if (old != new) and (new != self.home):
          self.home = new
          self.log('change group to {0} from {1}'.format(new,old));
          t=datetime.datetime.now().strftime("%H:%M:%S")
          if new=='home':
              self.fire_event("at_home", enable="on")
              self.notify(' {0} alarm stop to track'.format(t))
          else:
              self.fire_event("at_home", enable="off")
              self.notify(' {0} alarm start to track'.format(t))

    def do_state_change (self,entity, attribute, old, new, kwargs):

        if not self.are_states_valid(old, new):
            return

        en = entity.split('.')[1]

        skip_home_check = False
        if en in self.external_sensors:
            skip_home_check =True

        if self.home!='home' or skip_home_check:
            if old != new:
               if entity in self.filter:
                   return;
               r=self.policer.add_event()
               t=datetime.datetime.now().strftime("%H:%M:%S")
               fn=self.friendly_name(entity)
               notify_msg=" {} alarm  *{}* triggered {} to *{}* ".format(t,fn,old,new)
               self.log(notify_msg);
               if r[0]:
                   if r[1]>0:
                       notify_msg=" {} alarm *{}* triggered, missed {} ".format(t,fn,r[1])
                   else:
                       notify_msg=" {} alarm *{}* triggered {} to *{}* ".format(t,fn,old,new)
                   self.notify(notify_msg)
                   if skip_home_check:
                      if old == 'off' and new == 'on':
                         self.call_alarm (1)
                         self.notify("Call Alarm 1")


def norm_dw (dweek):
    m=[2,3,4,5,6,7,1]
    return m[dweek]


class PowerDownNotification(HassBase):

    def initialize(self):
        self.listen_event(self.event_cb, TASMOTA_EVENT)

    def event_cb(self, event_name, data, kwargs):
        if data['state'] == 'power_up':
            eid = data['entity_id'].replace(".", " ")
            eid = eid.replace("_", " ")
            msg = " Power up {} ".format(eid)
            self.my_notify(msg)


class SabbathEvent(hass.Hass):
    def initialize(self):
        self.run_in(self.calc_cb_sabbath, 60)
        self.is_sabbath =False

    def calc_cb_sabbath (self,kwargs):
        try:
            self.is_sabbath =self.calc_sabbath()
            self.log("start Sabbath manager {0}".format(self.is_sabbath));
            dtime_sec=(60 * 60)
            self.run_at_sunset(self.friday_cb,  offset=-dtime_sec)
            self.run_at_sunset(self.saturday_cb, offset=((dtime_sec*3)/4))
            if self.is_sabbath:
               self.friday_cb(kwargs={})
        except Exception as e:
            self.log("try again to get  Sabbath");
            self.run_in(self.calc_cb_sabbath, 60)

    def friday_cb(self,kwargs):
        d_now = self.get_now_day()
        if d_now != 6:
            return;

        self.is_sabbath = True
        msg="Sabbath is on"
        self.notify(msg)
        self.log(msg)
        self.fire_event("sabbath_day", enable="on")

    def saturday_cb(self,kwargs):
        d_now = self.get_now_day()
        if d_now != 7:
            return;
        self.is_sabbath = False
        msg="Sabbath is off"
        self.notify(msg)
        self.log(msg)
        self.fire_event("sabbath_day", enable="off")

    def get_now_day (self):
        """ return days from 1 - sunday to 7-saturday """
        now = self.get_now()
        return (norm_dw(now.weekday()))

    def calc_sabbath(self):
        d_now = self.get_now_day()
        ts_now =self.get_now_ts()
        dtime_sec = 60*60
        if self.sun_down():
            if d_now == 6:
                 return True
            return False
        else:
            ts_sunset = self.sunset().timestamp()
            if d_now == 6:
              #friday 
               if (ts_now > (ts_sunset -dtime_sec)):
                 return True
            if d_now == 7:
               if (ts_now < (ts_sunset + (dtime_sec*3/4))):
                return True
            return False


class SabbathEventTest(hass.Hass):

    def initialize(self):
        self.listen_event(self.saturday_cb, "sabbath_day")

    def saturday_cb(self, event_name, data, kwargs):
        self.log(" fired {0} {1} {2} ".format(event_name, data, kwargs))
    

class OutdoorLampWithPir(HassBase):

    def initialize(self):
        self.cfg_slamp = self.args["switch"]
        self.cfg_pir   = self.args["sensor"]
        self.auto_pir_on = True 
        self.disable_pir =False  
        self.listen_state(self.do_pir_change, self.cfg_pir)
        self.handle =None
        self.is_sabbath =False
        self.turn_off(self.cfg_slamp)
        if "delay" in self.args:
           self.cfg_delay_sec = (self.args["delay"])*60
        else:
           self.cfg_delay_sec = 15*60

        if "disable_auto_on" in self.args:
            self.auto_pir_on = not self.args["disable_auto_on"]

        self.listen_event(self.sabbath_cb, HEBCAL_EVENT)
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.on_schedule_event,None)
        self.sch.init()


    def sabbath_cb(self, event_name, data, kwargs):
        if data['state'] == 'pre':
            self.is_sabbath = True
        elif data['state']=='off':
            self.is_sabbath = False

    def on_schedule_event (self,kwargs):
        self.stop_timer()
        if kwargs['state'] == "on":
            self.log('turn lamp ')
            self.turn_lamp_on()
            self.disable_pir = True 
        elif kwargs['state']=="off":
            self.log('turn lamp off ')
            self.turn_lamp_off ()
            self.disable_pir = False 

    def stop_timer(self):
        if self.handle:
           self.cancel_timer(self.handle)
           self.handle = None

    def  turn_lamp_on_timer(self,time_sec):
        if self.auto_pir_on:
           self.turn_on(self.cfg_slamp)
        self.stop_timer()
        self.handle = self.run_in(self.timer_turn_lamp_off, time_sec)
 
    def timer_turn_lamp_off (self,kargs):
        self.turn_off(self.cfg_slamp)
        self.handle = None

    def turn_lamp_off (self):
         self.stop_timer()
         self.turn_off(self.cfg_slamp)

    def turn_lamp_on(self):
        self.stop_timer()
        self.turn_on(self.cfg_slamp)

    def is_lamp_on (self):
        if self.get_state(self.cfg_slamp)=="on":
            return True
        else:
            return False

    def do_pir_change (self,entity, attribute, old, new, kwargs):
        if not self.are_states_valid(old, new):
            return
        if self.disable_pir:
            return 
        if old != new:
            if self.sun_down() and (self.is_sabbath == False):
                self.turn_lamp_on_timer(self.cfg_delay_sec)

#do somthing before sabbath
class SabbathHandler(HassBase):

    def initialize(self):
        self.listen_event(self.saturday_cb, HEBCAL_EVENT)

    def saturday_cb(self, event_name, data, kwargs):
        
        if data['state'] == 'pre':
            self.call_alarm(20)
            self.turn_on('switch.alarm_s0')
        elif data['state'] == 'on':
            self.call_alarm(26)
            self.turn_off('switch.tv')
        elif data['state'] == 'off':
            self.call_alarm(21)
            self.turn_off('switch.alarm_s0')


class GatewayRingtone(HassBase):

    def initialize(self):
        self.log("GatewayRingtone");
        self.listen_state(self.do_button_change, 'input_boolean.gateway_sound_enable')

    def get_ringtone (self):
        r=float(self.get_state('input_number.gateway_sound_id'))
        return (int(r))


    def do_button_change (self,entity, attribute, old, new, kwargs):
        if old != new:
            if new == "on":
                self.call_alarm (self.get_ringtone ())



class GatewayWakeup(HassBase):

    def initialize(self):
        self.log("Wakeup");
        self.run_daily(self._cb_event, 
                       self.parse_time("06:00:00"), 
                       constrain_days="sun,mon,tue,wed,thu")


    def _cb_event(self,kwargs):
        self.call_alarm (20)


class AutoTurnAVR130(hass.Hass):
    """ Harman Kardon is turn on wating for power on, this classs wait for power on and send IR """

    def initialize(self):
      self.notify("start auto_avr_130_on")
      self.listen_state(self.do_tracer_change, 'device_tracker.tv_ir')
      self.listen_state(self.do_switch_change, 'switch.tv')
      self.cnt=0

    def do_switch_change (self,entity, attribute, old, new, kwargs):
        if old != new:
            entity = entity.split('.')[1]
            if new == 'on':
                self.cnt=0
                self.run_in(self.retry_turn_on, 1)

    def do_tracer_change (self,entity, attribute, old, new, kwargs):
        if old != new:
            entity = entity.split('.')[1]
            if new == 'home':
                self.cnt=0
                self.run_in(self.retry_turn_on, 1)

    def retry_turn_on (self,kwargs):
        if self.cnt>10:
            return;
        self.cnt += 1
        self.call_service('media_player/turn_on', entity_id="media_player.main")
        self.run_in(self.retry_turn_on, 1)


class HomeButtonClick(HassBase):
    """ Click Button home """
    def initialize(self):
      self.listen_event(self.change_state, "xiaomi_aqara.click")

    def change_state(self, event_name, data, kwargs):
        en = 'binary_sensor.switch_158d0001e7a286'
        if 'entity_id' in data:
            if data['entity_id']==en:
                msg=" click {}   ".format(str(data))
                self.log(msg)
                self.notify(' Doorbell on  ..')
                self.set_door_bell()

class Room0ButtonClick(HassBase):
    """ Click Button Room0 """
    def initialize(self):
      self.listen_event(self.change_state, "xiaomi_aqara.click")

    def change_state(self, event_name, data, kwargs):
        en = 'binary_sensor.switch_158d0001ef644c'
        if 'entity_id' in data:
            if data['entity_id']==en:
                msg=" click Room 0{}   ".format(str(data))
                self.log(msg)
                if 'click_type' in data:
                    ct = data['click_type']
                    if ct == 'single':
                        self.toggle('group.shutter_r0')
                    elif ct == 'double':
                        self.toggle('group.lamps_r0')
                    elif ct == 'long_click_press':
                        self.turn_off('group.shutter_r0')
                        self.turn_off('group.lamps_r0')
                    elif ct == 'hold':
                        pass



class AlarmNotificationHighPriorty(HassBase):

    def initialize(self):
      return 
      # need to fix this
      self.external_alarms =['alarm14','alarm15']
      for device_id in self.external_alarms:
           self.listen_state(self.do_state_change, 'binary_sensor.{0}'.format(device_id))
      self.policer = CPolicer(2,20)

    def do_state_change (self,entity, attribute, old, new, kwargs):

       if not self.are_states_valid(old, new):
           return

       en = entity.split('.')[1]
       siren = False
       if old != new:
          if old == 'on' and new=='off':
              siren = True

          r=self.policer.add_event()
          t=datetime.datetime.now().strftime("%H:%M:%S")
          fn=self.friendly_name(entity)
          notify_msg=" {} alarm  *{}* triggered {} to *{}* ".format(t,fn,old,new)
          if r[0]:
              if r[1]>0:
                  notify_msg="HIGH {} alarm *{}* triggered, missed {} ".format(t,fn,r[1])
              else:
                  notify_msg="HIGH {} alarm *{}* triggered {} to *{}* ".format(t,fn,old,new)
              self.notify(notify_msg)
              if siren:
                #self.call_alarm (2)
                self.notify("Call Alarm 2")



class CBoilerAutomation(HassBase):
    # input_automation
    # input_temp_min
    # input_temp_max
    # temp
    # switch
    # sensor_eff_power
    # sensor_eff_solar

    TIME_INTERVAL = 60
    WATCHDOG_MIN  = (120*2)
    WATCHDOG_TICKS = (WATCHDOG_MIN*60)/TIME_INTERVAL
    WATCHDOG_MAX_TEMP = 100.0
    

    def initialize(self):
        self.log("Start Boiler app ");
        self.start_time = None
        self.stop_time = None
        self.cnt=0;
        self.state ='off'
        self.sabbath = False
        self.last_temp =None
        self.force_power_enable (False) # force power off 
        self.watchdog_disabled = False
        self.policer = CPolicer(2,2)
        self.temp = self.get_float("temp",60.0)
        self.run_in(self.check_temp, CBoilerAutomation.TIME_INTERVAL)
        self.listen_state(self.do_power_change, self.args["switch"])
        self.listen_event(self.saturday_cb, HEBCAL_EVENT)
        self.listen_state(self.do_input_change, self.args["input_automation"])
        try: 
           self.run_at_sunset(self.notify_temp,  offset=-(2*60*60))
        except Exception as e:
           pass

    def notify_temp(self,kwargs):
        msg= "Boiler at {} c".format(self.get_float("temp",60.0))
        self.my_notify(msg);

    def saturday_cb(self, event_name, data, kwargs):
        if data['state'] == 'pre':
            self.sabbath = True
            self.force_power_enable(False)
        elif data['state'] == 'off':
            self.sabbath = False

    def do_input_change(self,entity, attribute, old, new, kwargs):
        if old != new:
            if new == 'on':
                self.cnt=0; #reset WD by user 
                self.watchdog_disabled = False

    def do_power_change(self,entity, attribute, old, new, kwargs):
        if old != new:
            if new == 'on':
                self.start_time = datetime.datetime.now()
                self.last_temp = self.temp
                if self.state == 'on':
                    msg = 'Boiler is ON {:.1f}'.format(self.temp)
                else:
                    msg = 'Boiler is ON by user {:.1f}'.format(self.temp)
                self.log(msg);
            else:
                if new == 'off':
                    self.update_bolier_stop()
                else:
                    pass; # handled by other APP
                    #self.my_notify('ERROR Bolier state is {}'.format(new));


    def update_bolier_stop(self):
        
        if self.state == 'off':
            device='auto'
        else:
            device='user'

        delta_temp = 0.0
        if ( isinstance(self.last_temp,float) and 
             isinstance(self.temp,float) ):
             delta_temp = self.temp - self.last_temp

        total_sec=0;
        if self.start_time:
            d = datetime.datetime.now() - self.start_time
            if (d.total_seconds()>0):
               total_sec = d.total_seconds()

        eff_c_hours =0.0
        if total_sec>0.0:
            eff_c_hours = 3600.0 * delta_temp /total_sec;

        minuts = int(total_sec/60.0)
        msg = "Boiler OFF by {}  t: {}m, d-t: {:.1f}, eff {:.1f} C/h".format(
                        device,
                        minuts,
                        delta_temp,
                        eff_c_hours)
                    
        self.log(msg);
        self.set_state(self.args["sensor_eff_power"],state = "{:.1f}".format(eff_c_hours))


    def is_app_enabled(self):
        if self.get_state(self.args["input_automation"])=="on":
            return True
        else:
            return False

    # main tick 
    def check_temp(self,kwargs):
        if (not self.sabbath) and self.is_app_enabled():
            self.update_state()
        else:
            self.temp = self.get_float("temp",60.0)
            self.watchdog()
            
        self.run_in(self.check_temp, CBoilerAutomation.TIME_INTERVAL)


    def get_float(self,name,def_val):
        res=def_val;
        try:
          res=float(self.get_state(self.args[name]))
        except (ValueError,TypeError):
          pass;
        return(res)


        
    def watchdog(self):
        #WD each min
        if self.sabbath:
            if self.is_turn_on():
               self.force_power_enable(False)
           
        if self.temp > CBoilerAutomation.WATCHDOG_MAX_TEMP:
            r = self.policer.add_event()
            if r[0]:
                msg= "Bolier ERROR temperator is HIGH {:.1f}".format(self.temp)
                self.force_power_enable(False) # try to force the power off, maybe there is 
                self.my_notify(msg)
            return True

        if self.watchdog_disabled:
            if self.is_turn_on():
               self.force_power_enable (False)
            if self.cnt>0:
               self.cnt -=1
            if self.cnt == 0:
                self.watchdog_disabled = False
            return True


        if self.is_turn_on():
            self.cnt += 1
        else:
            self.cnt =0

        # a two hour
        ticks = CBoilerAutomation.WATCHDOG_TICKS
        if self.cnt >= ticks:
            msg = " ERROR somthing wrong with boiler ON for {} min".format(CBoilerAutomation.WATCHDOG_MIN)
            self.log(msg);
            self.my_notify(msg);
            self.watchdog_disabled = True
        return False
            

    def update_state (self):
        self.temp = self.get_float("temp",60.0)
        low = self.get_float("input_temp_min",30.0)
        high  = self.get_float("input_temp_max",40.0)

        uv=0.0;
        if "input_uv" in self.args:
           uv = self.get_float("input_uv",0.0)
           
        #self.log(" boiler c:{} m:{} x:{} ".format(self.temp,low,high))

        if self.watchdog():
            return; # somthing wrong 

        if self.temp < low:
            if uv < 5.0:
               self.start()
        else:
            if self.temp > high:
                self.stop()

    def is_turn_on (self):
        if self.get_state(self.args["switch"])=="on":
            return True
        else:
            return False

    def force_power_enable (self,enable):
        if enable:
            self.turn_on(self.args["switch"])
        else:
            self.turn_off(self.args["switch"])

    def start(self):
        if self.is_turn_on():
            return;
        self.state = "on"
        self.force_power_enable(True)


    def stop (self):
        if not self.is_turn_on():
            return;
        self.state = "off"
        self.force_power_enable(False)



# handle the events at home, not at home ! more than 5 ticks

class CWaterMonitor(HassBase):
    # sensor_water_total: read from this sensor
    # sensor_water_leak_detector: name of the sensor to update leaks
    # sensor_water_bursts: the name of the sensor to update the total water
    # watchdog_duration_min: maximum duration in minutes for a burst of water 
    # watchdog_leakage_ticks: number of ticks when not at home
    # max_day: max litters for a day 

    TIME_INTERVAL = 120 # timer every 120 sec
    
    def initialize(self):
        self.log("start water monitor app ");
        self.at_home = True
        self.leak_ticks =0
        self.policer = CPolicer(100,60)
        self.run_in(self.water_timer, CWaterMonitor.TIME_INTERVAL)
        self.listen_state(self.do_water_change, self.args["sensor_water_total"])
        self.start_time = None
        self.state = 'off'
        self.total_water =0
        self.cur_water_counter = None
        self.start_water_count = None
        self.ticks =0
        self.wd =0
        self.switch_cnt=0;
        self.burst_was_reported = False
        self.total_water_was_reported = False
        self.listen_event(self.home_cb, "at_home")
        try:
            self.run_at_sunset(self.notify_water_usage,  offset=-(0))
        except Exception as e:
            pass


    def notify_water_usage(self,kwargs):

        if self.total_water > self.args["max_day"] :
            self.police_notify(" WARNING total water {} is high im a single day ".format(self.total_water))
        msg= "water usage {} l".format(self.total_water)
        self.total_water =0
        self.police_notify(msg);


    def is_taps_opened (self):
        taps = self.args['taps_switchs']
        for tap in taps:
            if self.get_state(tap)=="on":
                return True
        return False

    def get_water_counter(self):
          try:
            res=int(self.get_state(self.args['sensor_water_total']))
            return (res);
          except (ValueError,TypeError):
            return (-1)

    def is_int (self,value):
        try:
          res=int(value)
          return True
        except (ValueError,TypeError):
          return False

    def do_water_flow (self,new_counter):
        self.cur_water_counter = new_counter

        taps_opened = False
        max_burst = self.args["max_burst_l0"]

        if self.is_taps_opened():
            self.switch_cnt = 5;
            taps_opened = True
        else:
            if self.switch_cnt > 0 :
                self.switch_cnt -= 1;
                taps_opened = True

        if taps_opened:
            max_burst = self.args["max_burst_l1"]

        self.wd = 1;
        if self.state == 'off':
            self.state = 'on'
            self.ticks =0
            self.start_time = datetime.datetime.now() 
            self.start_water_count = self.cur_water_counter
            self.burst_was_reported =False
            #self.police_notify("->water START count {}".format(self.start_water_count))
        else:
            #self.police_notify("->water ON new count {}".format(self.cur_water_counter))
            d_water = self.cur_water_counter - self.start_water_count
            if (not self.at_home) and (not taps_opened):
                if d_water>50:
                   msg = " water is on when you not at home {} litters".format(d_water)
                   self.police_notify(msg)
                   if not self.burst_was_reported:
                      self.burst_was_reported = True
                      self.fire_event(EVENTM_EVENT, state = "on", type="water", msg = msg,callmsg= msg)
            
            if d_water > max_burst :
                msg = " WARNING total water {} is high in a single burst {} ".format(d_water,max_burst)
                self.police_notify(msg)
                if not self.burst_was_reported:
                    self.burst_was_reported = True
                    self.fire_event(EVENTM_EVENT, state="on", type="water", msg = msg,callmsg= msg)



    def set_sensor(self,name,value):
        self.set_state(self.args[name],state = "{}".format(value))
        self.set_state(self.args[name],state = "{}".format(0))

    def  do_water_timeout(self):
        if self.burst_was_reported:
            self.burst_was_reported = False
            self.police_notify(" WARNING water burst end")
            self.fire_event(EVENTM_EVENT, state="off",type="water")
        
        if self.total_water_was_reported:
            self.total_water_was_reported = False 
            self.police_notify(" WARNING water burst end")
            self.fire_event(EVENTM_EVENT, state="off",type="water-total")

        self.state = 'off'
        self.ticks =0
            
        d = datetime.datetime.now() - self.start_time
        d_water = self.cur_water_counter - self.start_water_count + 1
        self.total_water += d_water
        #self.police_notify("->water STOP burst {} cur : {}".format(d_water,self.cur_water_counter))

        if d_water ==0:
            self.police_notify("ERROR burst of zero litter !! not possible !")
        self.set_sensor("sensor_water_bursts",d_water)

        if not self.at_home:
            if d_water == 1:
                self.set_sensor("sensor_water_leak_detector",d_water)
                self.leak_ticks +=1
                if self.leak_ticks > self.args["watchdog_leakage_ticks"]:
                   self.police_notify(" leakage warning, {} of 1 liter reported".format(self.leak_ticks))
                   self.leak_ticks =0
            else:
                self.police_notify(" leakage {} liters while not at home reported".format(d_water))


    # main tick 
    def water_timer(self,kwargs):
        # try to read it if we are in "on"
        if self.state == 'on':
          new = self.get_water_counter()
          if self.cur_water_counter is not None and  new > self.cur_water_counter:
              self.do_water_flow (new)

        #self.police_notify("->water (timer) state {},  wd {}, ticks {}, ".format(self.state,self.wd,self.ticks))
        if self.wd:
           self.ticks += 1
           self.wd=0
        else:
           if self.state == 'on':
              self.do_water_timeout()

        if self.ticks > (self.args["watchdog_duration_min"]*60/CWaterMonitor.TIME_INTERVAL):
            if not self.total_water_was_reported:
                self.total_water_was_reported = True 
                msg = "ERROR running for more than {} min ".format(self.args["watchdog_duration_min"])
                self.fire_event(EVENTM_EVENT, state="on", type = "water-total", msg = msg,callmsg= msg)

        self.run_in(self.water_timer, CWaterMonitor.TIME_INTERVAL)


    def police_notify(self,msg):
        r = self.policer.add_event()
        if r[0]:
            self.my_notify("Water "+msg)

    def do_water_change(self,entity, attribute, old, new, kwargs):

        # check that both are int (new,old) else don't do anything 
        if self.is_int(new) and self.is_int(old):
           int_old = int(old); # convert both 
           int_new = int(new); # convert both
           if int_new > int_old:
              self.do_water_flow(int_new)
           else:
              if int_old > int_new:
                msg = "ERROR new {} reading is lower than old {} reading " .format(int_new,int_old)
                self.police_notify(msg)
        else:
            pass; # not needed, will be handled by another app for disconnect/connect wifi issues  
            #msg = "ERROR new {} or old {} state is not int " .format(new,old)
            #self.police_notify(msg)

    def home_cb(self, event_name, data, kwargs):
        if data['enable']=='on':
            self.at_home = True
        else:
            self.leak_ticks =0
            self.at_home = False



class CFollowState(hass.Hass):
    """ folow the state of a diffrent object """
    #input: 
    #output: 
    def initialize(self):
        self.log(" start folow app ");
        self.listen_state(self.do_state_change, self.args["input"])
        # sync with the state
        if self.get_state(self.args["input"])=="on":
            self.turn_on(self.args["output"])
        else:
            self.turn_off(self.args["output"])

    def do_state_change (self,entity, attribute, old, new, kwargs):
        if old != new:
            if new == "on":
                self.turn_on(self.args["output"])
            else:
                if new == 'off':
                    self.turn_off(self.args["output"])


class CCube(hass.Hass):
    """ magic cube mii """
    #input: 
    #output: 
    def initialize(self):
        self.log("setup cube app")
        self.listen_event(self.change_state, "xiaomi_aqara.cube_action")

    def change_state(self, event_name, data, kwargs):
        msg=" cube {}   ".format(str(data))
        self.log(msg)
        if 'action_type' in data:
            at=data['action_type']
            if at=='flip90':
                self.toggle('light.light1');
            elif at=='move':
                pass
            elif at=='flip180':
                self.toggle('switch.ac1');
                pass
            elif at=='tap_twice':
                self.toggle('switch.tv');
            elif at=='swing':
                pass
            elif at=='shake_air':
                pass
            elif at=='rotate':
                val=float(data['action_value'])
                if val>0:
                   self.call_service('media_player/volume_up', entity_id="media_player.main")
                else:
                   self.call_service('media_player/volume_down', entity_id="media_player.main")
                pass
            elif at=='free_fall':
                pass
            elif at=='alert':
                pass




class CMiiButton(HassBase):
    """ magic button mii """
    #input: 
    #output: 
    def initialize(self):
        self.listen_event(self.change_state, "xiaomi_aqara.click")

    def change_state(self, event_name, data, kwargs):
        msg=" click {}   ".format(str(data))
        self.log(msg)

class CWBIrrigation(HassBase):
    """  """
    #input: 
    #output: 
    def initialize(self):
        self.log("start irrigation app");
        self.h ={}
        self.init_all_taps()
          

    
    def init_all_taps(self):
        hours = self.args["m_temp_hours"]
        tmean = self.args["m_temp_celsius"]
        self.max_ev_week = 7.0 * hours * (0.46 * tmean + 8.13)
        for tap in self.args["taps"]:
             self.turn_off(tap["switch"])
             self.register_call_backs(tap)
             self.listen_state(self.do_button_change,tap["switch"],tap=tap)
             self.h[tap["name"]] = None

    def do_button_change (self,entity, attribute, old, new, kwargs):
        tap = kwargs['tap']
        h = self.h[tap["name"]] 
        if old != new: 
            if h is None:
            # manual start 
                if new == "on":
                    duration_sec = float(self.get_state(tap["manual_duration"]))*60.0
                    self.log("turn on by user {} {} min ".format(tap["name"],int(duration_sec/60.0)))
                    self.start_tap(tap, int(duration_sec) , "manual",False)
            else:
                if new == "off":
                    # turn off by user 
                    self.log("turn off by user {} ".format(tap["name"]))
                    kwargs={}
                    kwargs['tap']=tap
                    kwargs['clear_queue']=False
                    self.time_cb_event_stop(kwargs)
                

    def register_call_backs(self,tap):
        start_time = self.parse_time(tap["stime"])
        start_days = tap["days"]
        days = []
        for day in start_days: 
            days.append(ada.schedule.day_of_week(day))
        days=str(days)[1:-1].replace("'", "").replace(" ","")    
        self.log("irrigation init {} {} {} ".format(tap["name"],days,start_time))
        self.run_daily(self.time_cb_event, 
            start_time, 
            constrain_days = days,
            tap=tap)

    def time_cb_event_stop_verify(self,kwargs):
        tap = kwargs['tap']
        if self.get_state(tap["switch"]) == "on":
           self.turn_off(tap["switch"])
           self.my_notify ("ERROR can't stop tap {}".format(tap["name"]))
           self.run_in(self.time_cb_event_stop_verify, 5,tap=tap)

    def time_cb_event_stop(self,kwargs):
        tap = kwargs['tap']

        state = self.get_state(tap["switch"])
        if state == 'off':
           self.log(" irrigation stop but already off {} ".format(tap["name"]))
        
        self.log(" irrigation stop for {} {}".format(tap["name"],state))
        self.turn_off(tap["switch"])
        
        if self.get_state(tap["switch"]) == "on":
           self.run_in(self.time_cb_event_stop_verify, 5,tap=tap)

        if self.is_water_sensor_defined():
           self.inc_sensor( tap["water_sensor"],
                         self.read_water_sensor () - tap["start"])
                         
        if kwargs['clear_queue']:
           self.reset_queue (tap)
        self.h[tap["name"]] = None   

    def is_water_sensor_defined (self):
       if "water_sensor" in self.args:
          return True
       else:
          return False

                  
    def read_water_sensor (self):
       if self.is_water_sensor_defined():
           return float(self.get_state(self.args["water_sensor"]))
       else:
           return 0.0 # not supported     

    def reset_queue (self,tap):
       self.call_service('wb_irrigation/set_value', entity_id=tap["queue_sensor"],value="0.0")
    
    def inc_sensor (self,sensor,val):
        self.var_inc (sensor,val)

    def start_tap (self,tap,duration_sec,desc,clear_queue):
        duration_min = int(duration_sec/60.0)
        msg = "irrigation time tap {} {} {} min".format(tap["name"],desc,duration_min)
        self.var_inc (tap["time_sensor"],duration_min)
        if "tap_open" in self.args["notify"]:
           self.my_notify(msg)

        h = self.h[tap["name"]] 

        if h:
           self.cancel_timer(h)
           self.h[tap["name"]] = None 

        self.h[tap["name"]] = self.run_in(self.time_cb_event_stop, 
                        duration_sec, 
                        tap=tap,clear_queue=clear_queue)

        tap["start"] = self.read_water_sensor ()
        self.turn_on(tap["switch"])
    
    
    def time_cb_event(self,kwargs):
        if self.get_state(self.args["enabled"]) != "on":
            self.log(" irrigation is disabled ")
            return;
           
        tap = kwargs['tap']
        self.log(" irrigation event for {}".format(tap["name"]))
        
        # calculate the irrigation time 
        queue = float(self.get_state(tap["queue_sensor"]))
        if queue > 0.0:
           self.log(" irrigation nothing to do queue: {} ".format(queue))
           return;

        duration_min = self.read_ent_as_float(tap["m_week_duration_min"])
        
        irrigation_time_min =  (-queue) *  duration_min / self.max_ev_week
        if irrigation_time_min < 0.2:
           self.log(" irrigation  queue is small  {} ".format(queue))
           return; 

        if irrigation_time_min > duration_min:
           self.my_notify(" ERROR irrigation time is high {} min ".format(irrigation_time_min))
           irrigation_time_min = duration_min

        self.start_tap(tap, irrigation_time_min * 60, "timer",True)
            


class CTrackerNeta(HassBase):
    """ enable/disable dummy tracker """
    #input: 
    #output: 
    def initialize(self):
        self.tracker="variable.tracker_neta"
        self.listen_state(self.do_button_change, 'input_boolean.tracker_neta_enabled')
        self.handle = None

    def get_timer_time (self):
        return 60*60*8

    def do_turn_off(self):
        self.handle=None
        self.var_set(self.tracker,"not_home")

    def do_turn_on(self):
        self.var_set(self.tracker,"home")

    def do_button_change (self,entity, attribute, old, new, kwargs):
        if new == "on":
            self.do_turn_on()
            sec = self.get_timer_time();
            self.handle = self.run_in(self._cb_event, sec)
        else:
            self.do_turn_off()
            if self.handle: 
               self.cancel_timer(self.handle)
         
    def _cb_event(self,kargs):
        self.do_turn_off()


EVENTM_TIMER_SEC = 20
EVENTM_TIMERS_CNT = 10

# this is an event manager 
# listen to important events and require user - feedback to stop it
class EventManager(HassBase):

    def initialize(self):
      self.notify("start EventManager")
      self.listen_event(self.event_cb, EVENTM_EVENT)
      self.listen_state(self.do_input_change, self.args['inputd'])
      self.listen_state(self.do_trigger_change, self.args['inputt'])
      self.state = "off"
      self.cnt = 0
      self.data = None
      self.handle = None 
      self.types ={} # types of events 
      self.cfg_input = self.args['inputd']
      self.cfg_vcurrent = self.args['vcurrent']
      self.cfg_vlast = self.args['vlast']

    def do_input_change (self,entity, attribute, old, new, kwargs):
        if old != new and new == "on":
            self.stop_alarm(True,False)
    
    def do_trigger_change (self,entity, attribute, old, new, kwargs):
        if old != new:
            if new == "on":
               self.fire_event(EVENTM_EVENT, state="on", type="fire", msg ="fire in basement", 
                                callmsg="fire in basement")
            else:
               self.fire_event(EVENTM_EVENT, state="off",type="fire")

    def event_cb(self, event_name, data, kwargs):
        if data['state'] == 'on':
            if self.state == "on":
                self.cnt = 0 # restart the timer
                self.data = data # replace the data 
                self.types[data['type']] = 1
            else:
                self.start_alarm(data)
    
        elif data['state'] == 'off':
            if 'type' in data:
                 if data['type'] in self.types:
                    del self.types[data['type']] 
                    if len(self.types)==0:
                        self.stop_alarm(False,True)

    def stop_alarm(self,byuser,byevent):
        if self.state == "off":
            return 
        self.types = {}
        self.state = "off"
        msg = ""
        if byuser or byevent:
           self.stop_timer()
           if byevent:
              msg = "EventM stop by event {}".format(self.cnt)
           else:   
              msg = "EventM stop by user {}".format(self.cnt)
        else:
           msg = "EventM giving up {}".format(self.cnt)

        self.turn_off(self.cfg_input)
        self.cnt =0
        self.my_notify(msg)
        self.alert_sms (msg)
        self.call_alarm(ALARM_WATER_ISSUES)
        self.var_set(self.cfg_vlast,self.data['type']+":"+self.data['msg'])
        self.var_set(self.cfg_vcurrent,"off")

    def do_signal(self):
        msg= "EventM  {} {} ".format(self.data['type'],self.data['msg'])
        self.my_notify(msg)
        self.alert_sms (msg)
        self.var_set(self.cfg_vcurrent,str(self.cnt)+":"+self.data['type']+":"+self.data['msg'])
        if "callmsg" in self.data:
            self.alert_tts (self.data['callmsg'])

    def start_alarm(self,data):
        self.types[data['type']] = 1
        self.cnt =0
        self.state = "on"
        self.data = data
        self.do_signal()
        self.start_timer()

    def start_timer(self):
        self.handle = self.run_in(self._cb_event, EVENTM_TIMER_SEC)

    def stop_timer(self):
        if self.handle:
           self.cancel_timer(self.handle)

    def _cb_event(self,kargs):
        self.cnt += 1
        if self.cnt > EVENTM_TIMERS_CNT:
           self.stop_alarm(False,False)
           return 
        self.do_signal()   
        self.start_timer()


class AlarmNotificationHigh(HassBase):

    def initialize(self):
                
      self.notify("start High Alarm notification ")

      #smoke  
      self.smoke_external_sensors = ['smoke_sensor_158d00024e008a',
                                     'smoke_sensor_158d000287ae79']

      for device_id in self.smoke_external_sensors:
           self.listen_state(self.do_smoke_state_change, 'binary_sensor.{0}'.format(device_id))

      # water  
      self.water_external_sensors =[
                              'water_leak_sensor_158d000256cd9d',
                              'water_leak_sensor_158d00023385f2',
                              'water_leak_sensor_158d000256ce72',
                              'water_leak_sensor_158d000256ce93',
                              'water_leak_sensor_158d000256cede',
                              'water_leak_sensor_158d00027049bb']

      for device_id in self.water_external_sensors:
           self.listen_state(self.do_water_state_change, 'binary_sensor.{0}'.format(device_id))

      self.all = []  
      self.all.extend(self.smoke_external_sensors)
      self.all.extend(self.water_external_sensors)


    def check_end(self):
        for device_id in self.all:
            s = 'binary_sensor.{0}'.format(device_id)
            if self.get_state(s) == "on":
                return True 
        return False         

    def do_water_state_change (self,entity, attribute, old, new, kwargs):
        fn = self.friendly_name(entity)
        if old != new:
            if new == "on":
               msg=" water {} triggered ".format(fn)
               self.fire_event(EVENTM_EVENT, state="on", type=fn, msg=msg, callmsg=msg)
            else:   
               self.fire_event(EVENTM_EVENT, state="off", type=fn)


    def do_smoke_state_change (self,entity, attribute, old, new, kwargs):
        fn = self.friendly_name(entity)
        if old != new:
            if new == "on":
               msg=" smoke {} triggered ".format(fn)
               self.fire_event(EVENTM_EVENT, state="on", type=fn, msg=msg, callmsg=msg)
            else:
               self.fire_event(EVENTM_EVENT, state="off", type=fn)



class LightApp(HassBase):

    def initialize(self):
        self.log("start LightApp")
        self.light = self.args["light"]
        self.switch = self.args["switch"]
        self.timer_handle = None
        self.flag_restart_timer = False 
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.on_schedule_event,None)
        self.sch.init()


    def _cb_event(self,kargs):
        self.timer_handle = None
        self.restart_timer()

    def tick(self):
        light = self.read_light_lux()
        if self.is_on():
            if light > 950:
                self.s_turn_off()
                self.log("turn off the light")
        else:
            if light < 700:
                self.log("turn on the light")
                self.s_turn_on()

    def restart_timer(self):
        self.tick()
        if self.timer_handle==None:
            if self.flag_restart_timer:
                self.log(" restart timer ")
                self.timer_handle = self.run_in(self._cb_event, 30*60)
            else:
                self.log(" race condition - timer is not restarted ")


    def stop_timer(self):
        if self.timer_handle:
            self.cancel_timer(self.timer_handle)
            self.timer_handle = None 

    def on_schedule_event(self, kwargs):
        if kwargs['state'] == "on":
            self.log(" start timer ")
            self.flag_restart_timer = True 
            self.restart_timer()
        elif kwargs['state'] == "off":
            self.log(" stop timer ")
            self.flag_restart_timer = False 
            self.stop_timer()

    def is_int (self,value):
        try:
          res=int(value)
          return True
        except (ValueError,TypeError):
          return False

    def read_light_lux(self):
        light = self.get_state(self.light)
        if self.is_int(light):
            return int(light)
        else:
            return 1000    

    def s_turn_on(self):
        self.turn_on(self.switch)

    def s_turn_off(self):
        self.turn_off(self.switch)

    def is_on(self):
        if self.get_state(self.switch) == "on":
            return True
        else:
            return False
