import appdaemon.plugins.hass.hassapi as hass
import datetime
from pprint import pprint
import ada.schedule 
import ada.temp_sensor
import ada.temp


ALARM_WATER_ISSUES = 23

class SimpleSwitch(hass.Hass):

    def initialize(self):
        self.log("start simple-switch {0}".format(str(self.args)));
        self.ss = ada.temp_sensor.SimpleSwitch(self,self.args['switch']);
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.ss.on_schedule_event,None)
        self.sch.init()


class HeatApp(hass.Hass):

    def initialize(self):
        self.log("start Heat App {0}".format(str(self.args)));
        self.heater = ada.temp_sensor.HeaterSensor(self,self.args['heater']);
        self.sch = ada.schedule.Schedule(self,
                                     self.args['schedule'],
                                     self.heater.on_schedule_event,None)
        self.sch.init()


class CalcHeatIndexApp(hass.Hass):

    def initialize(self):
        self.log("start Calc App {0}".format(str(self.args)));
        self.update_state ()
        self.listen_state(self.do_check_temperator, self.args["temp"])
        self.listen_state(self.do_check_temperator, self.args["hum"])

    def get_float(self,name,def_val):
        res=def_val;
        try:
          val=self.get_state(self.args[name])
          if val is not None:
               res=float(val)
        except ValueError:
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
        if new == "on":
            self.log("start timer for {0} minutes for {1} switch ".format(self.get_timer_time(),self.args["switchs"]) );
            sec= self.get_timer_time()*60;
            self.handle = self.run_in(self._cb_event, sec)
        else:
            if self.handle: 
               self.log("stop timer ");
               self.cancel_timer(self.handle)

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
        self.call_service('xiaomi_aqara/play_ringtone', gw_mac= "7C:49:EB:19:3B:55",ringtone_id= rind_id)

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
        self.blink_light();
        self.call_alarm(DOORBELL)


    def my_notify (self,msg):
        t=datetime.datetime.now().strftime("%H:%M:%S")
        n_msg = t +' ' + msg
        self.log(n_msg);
        self.notify(n_msg);


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

      self.external_sensors =['smoke_sensor_158d00024e008a',
                              'smoke_sensor_158d000287ae79',
                              'water_leak_sensor_158d000256cd9d',
                              'water_leak_sensor_158d00023385f2',
                              'water_leak_sensor_158d000256ce72',
                              'water_leak_sensor_158d000256ce93',
                              'water_leak_sensor_158d000256cede',
                              'water_leak_sensor_158d00027049bb']
      for device_id in self.external_sensors:
           self.listen_state(self.do_state_change, 'binary_sensor.{0}'.format(device_id))


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
        if "delay" in self.args:
           self.cfg_delay_sec = (self.args["delay"])*60
        else:
           self.cfg_delay_sec = 15*60
        if "sat_delay" in self.args:
              self.cfg_sat_delay_sec = (self.args["sat_delay"])*60
        else:
              self.cfg_sat_delay_sec = 4*60*60

        self.listen_state(self.do_pir_change, self.cfg_pir)
        self.handle =None
        self.listen_event(self.sabbath_cb, "sabbath_day")
        self.is_sabbath =False
        self.turn_off(self.cfg_slamp)


    def sabbath_cb(self, event_name, data, kwargs):
        if data['enable']=='on':
            self.is_sabbath = True
            self.log('turn lamp due to friday night ');
            self.turn_lamp_on(self.cfg_sat_delay_sec)
        else:
            self.is_sabbath = False

    def  turn_lamp_on(self,time_sec):
        if self.handle:
           self.cancel_timer(self.handle)
        self.handle = self.run_in(self.turn_lamp_off, time_sec)
        self.turn_on(self.cfg_slamp)

    def turn_lamp_off (self,kargs):
        self.turn_off(self.cfg_slamp)
        self.handle=None

    def is_lamp_on (self):
        if self.get_state(self.cfg_slamp)=="on":
            return True
        else:
            return False

    def do_pir_change (self,entity, attribute, old, new, kwargs):

        if not self.are_states_valid(old, new):
            return

        if old != new:
            if self.sun_down() and (self.is_sabbath == False):
                self.turn_lamp_on(self.cfg_delay_sec)

#do somthing before sabbath
class SabbathHandler(HassBase):

    def initialize(self):
        self.listen_event(self.saturday_cb, "sabbath_day")

    def saturday_cb(self, event_name, data, kwargs):
        if data['enable']=='on':
            self.call_alarm(20)
            self.turn_on('switch.alarms0')
        else:
            self.call_alarm(21)
            self.turn_off('switch.alarms0')



class GatewayRingtone(HassBase):

    def initialize(self):
        self.log("GatewayRingtone");
        self.listen_state(self.do_button_change, 'input_boolean.gateway_sound_enable')

    def get_ringtone (self):
        r=float(self.get_state('input_number.gateway_sound_id'))
        return (int(r))


    def do_button_change (self,entity, attribute, old, new, kwargs):
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
      self.listen_event(self.change_state, "click")

    def change_state(self, event_name, data, kwargs):
        en = 'binary_sensor.switch_158d0001e7a286'
        if 'entity_id' in data:
            if data['entity_id']==en:
                msg=" click {}   ".format(str(data))
                self.log(msg)
                self.notify(' Doorbell on  ..')
                self.set_door_bell()

class AlarmNotificationHighPriorty(HassBase):

    def initialize(self):
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
    WATCHDOG_MAX_TEMP = 85.0
    

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
        self.listen_event(self.saturday_cb, "sabbath_day")
        self.run_at_sunset(self.notify_temp,  offset=-(2*60*60))
        self.listen_state(self.do_input_change, self.args["input_automation"])

    def notify_temp(self,kwargs):
        msg= "Boiler at {} c".format(self.get_float("temp",60.0))
        self.my_notify(msg);

    def saturday_cb(self, event_name, data, kwargs):
        if data['enable']=='on':
            self.sabbath = True
            self.force_power_enable(False)
        else:
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
                self.my_notify(msg);
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
                    
        self.my_notify(msg);
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
        except ValueError:
          pass;
        return(res)


        
    def watchdog(self):
        #WD each min
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
        #self.log(" boiler c:{} m:{} x:{} ".format(self.temp,low,high));

        if self.watchdog():
            return; # somthing wrong 

        if self.temp < low:
            self.start();
        else:
            if self.temp > high:
                self.stop();

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
        self.burst_was_reported =False
        self.run_at_sunset(self.notify_water_usage,  offset=-(0))
        self.listen_event(self.home_cb, "at_home")
        self.at_home = True
        self.leak_ticks =0

    def notify_water_usage(self,kwargs):

        if self.total_water > self.args["max_day"] :
            self.police_notify(" WARNING total water {} is high im a single day ".format(self.total_water))
        msg= "water usage {} l".format(self.total_water)
        self.total_water =0
        self.police_notify(msg);


    def get_water_counter(self):
          try:
            res=int(self.get_state(self.args['sensor_water_total']))
            return (res);
          except ValueError:
            return (-1)

    def is_int (self,value):
        try:
          res=int(value)
          return True
        except ValueError:
          return False

    def do_water_flow (self,new_counter):
        self.cur_water_counter = new_counter
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
            if not self.at_home:
                if d_water>50:
                   self.police_notify(" water is on when you not at home {} litters".format(d_water))

            if d_water > self.args["max_burst"] :
                self.police_notify(" WARNING total water {} is high in a single burst".format(d_water))
                self.burst_was_reported =True
                self.call_alarm(ALARM_WATER_ISSUES)

    def set_sensor(self,name,value):
        self.set_state(self.args[name],state = "{}".format(value))
        self.set_state(self.args[name],state = "{}".format(0))

    def  do_water_timeout(self):
        if self.burst_was_reported:
            self.burst_was_reported = False
            self.police_notify(" WARNING water burst end")
        self.state = 'off'
        self.ticks =0
        d = datetime.datetime.now() - self.start_time
        d_water = self.cur_water_counter - self.start_water_count + 1
        self.total_water += d_water
        #self.police_notify("->water STOP burst {} cur : {}".format(d_water,self.cur_water_counter))

        if d_water ==0:
            self.police_notify("ERORR burst of zero litter !! not possible !")
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
            self.police_notify("ERORR running for more than {} min ".format(self.args["watchdog_duration_min"]) )
            self.call_alarm(ALARM_WATER_ISSUES)

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
        self.listen_event(self.change_state, "cube_action")

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




class CMiiButton(hass.Hass):
    """ magic button mii """
    #input: 
    #output: 
    def initialize(self):
        self.listen_event(self.change_state, "click")

    def change_state(self, event_name, data, kwargs):
        msg=" click {}   ".format(str(data))
        self.log(msg)


