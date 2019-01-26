import os
import util
import yaml
import datetime
from pprint import pprint
import schedule 
import temp_sensor
import re
import temp

def test1 ():
  t1=datetime.time(17, 21,12)
  print(t1.hour);
  print(t1.minute);
  print(t1.second);
  


def test2 ():
    print("hey");
    print(util.expand_range_string("1-4,6-7"))
    #print(utility.build_date_from_constraint('2017-02-29'))
    d=util.parse_time_string("17:02:00");
    d2=util.parse_time_string("17:03:12");
    print(d);
    print(d2);

def test3 ():
    #test1 ()
    with open("_test.__yaml", 'r') as stream:
        d=yaml.load(stream)
        sc=d['hello_world']['schedule'];

    pprint(sc);
    sch = schedule.Schedule.load_cfg(sc)
    print(str(sch));
    print(sch.rules[0].constraints['weekdays'])
    i=sch.unfold()
    for x in i:
        print(x);

def my_dtime2sec(day:int,time: datetime.time):
    r = (day-1)*60*60*24 + time.hour*24*60 + time.minute*60+ time.second
    return(r)

class AppDaemonStub:

    def __init__(self):
        self.now = None
        pass;

    def set_now (self, now: datetime.time = None):
        self.now  = now


    def listen_state(self,  cb, entity, **kwargs):
        print(" listen_state "+str(kwargs));

    def cancel_listen_state(self, handle):
        print(" cancel_listen_state : "+str(handle));


    def run_daily(self, callback, start, **kwargs):
        print("run_daily :" +"time :"+str(start)+" kargs"+str(kwargs));

    def get_now(self):
        return self.now

    def get_now_ts(self):
        return self.now

    def now_is_between(self, start_time_str, end_time_str, name=None):
        return True

    def sunset(self):
        return datetime.datetime.fromtimestamp(self.calc_sun("next_setting"))

    def sunrise(self):
        return datetime.datetime.fromtimestamp(self.calc_sun("next_rising"))

    def get_state(self, entity=None, **kwargs):
        #print(" get state {0} {1} ".format(entity_id,kwargs))
        print(" get state "+str(entity));
        return True

    def turn_on(self, entity_id, **kwargs):
        print("turn_on "+str(entity_id));

    def turn_off(self, entity_id, **kwargs):
        print("turn_off "+str(entity_id));

    def set_state(self, entity_id, **kwargs):
        print(" set state {0} {1} ".format(entity_id,kwargs))

    def notify(self,msg):
        print(">>NOTIFY<< : "+msg);

    def parse_time(self,time_str,name=None ) :
        parsed_time = None
        parts = re.search('^(\d+):(\d+):(\d+)', time_str)
        if parts:
            parsed_time = datetime.time(
                int(parts.group(1)), int(parts.group(2)), int(parts.group(3))
            )
        else:
            if time_str == "sunrise":
                parsed_time = self.sunrise().time()
            elif time_str == "sunset":
                parsed_time = self.sunset().time()
            else:
                parts = re.search(
                    '^sunrise\s*([+-])\s*(\d+):(\d+):(\d+)', time_str
                )
                if parts:
                    if parts.group(1) == "+":
                        parsed_time = (self.sunrise() + datetime.timedelta(
                            hours=int(parts.group(2)), minutes=int(parts.group(3)),
                            seconds=int(parts.group(4))
                        )).time()
                    else:
                        parsed_time = (self.sunrise() - datetime.timedelta(
                            hours=int(parts.group(2)), minutes=int(parts.group(3)),
                            seconds=int(parts.group(4))
                        )).time()
                else:
                    parts = re.search(
                        '^sunset\s*([+-])\s*(\d+):(\d+):(\d+)', time_str
                    )
                    if parts:
                        if parts.group(1) == "+":
                            parsed_time = (self.sunset() + datetime.timedelta(
                                hours=int(parts.group(2)),
                                minutes=int(parts.group(3)),
                                seconds=int(parts.group(4))
                            )).time()
                        else:
                            parsed_time = (self.sunset() - datetime.timedelta(
                                hours=int(parts.group(2)),
                                minutes=int(parts.group(3)),
                                seconds=int(parts.group(4))
                            )).time()
        if parsed_time is None:
            if name is not None:
                raise ValueError(
                    "{}: invalid time string: {}".format(name, time_str))
            else:
                raise ValueError("invalid time string: {}".format(time_str))
        return parsed_time
    


class MyApp(AppDaemonStub):

    def __init__(self):
        pass;

    def on_schd_event (self,kwargs):
        print(" ==>on_event :"+ str(kwargs))


def test4 ():
    #test1 ()
    ad=MyApp();
    with open("_test.__yaml", 'r') as stream:
        d=yaml.load(stream)
        sc=d['hello_world']['schedule'];

    pprint(sc);
    tmps = temp_sensor.HeaterSensor(ad,d['hello_world']['heater']);
    sch = schedule.Schedule(ad,sc,tmps.on_schedule_event,None)
    print(str(sch));
    #d=datetime.now()
    d=datetime.datetime(2018,7,18,20,00,0)
    ad.set_now(d)
    sch.init ()


import temp

def test5():
    for t in range(20,42,1) :
        for hum  in range(50,90,5):
           s=" {0}-{1} : {2}".format(t,hum,temp.calc_heat_index_celsius(t, hum) )
           print(s)

import time;
def test7():
    t=datetime.datetime.now().strftime("%H:%M:%S")
    print(t)

def main ():
    test7 ()
    



    

for t in range(0,120):
   f=t/10.0
   print(temp.calc_heat_index_celsius(16.0+f, 70.0),16+f,)




#main();
