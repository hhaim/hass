import os
import util
import yaml
import datetime
from pprint import pprint
import schedule 
import temp_sensor
import re
import temp
import requests 
#from requests import get
import urllib
import json
import pprint
import pickle
 

STATE_ON = 1

STATE_OFF = 0 

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

    def run_at(self, callback, start, **kwargs):
        print("run_at :" +"datetime :"+str(start)+" kargs"+str(kwargs))

    def run_daily(self, callback, start, **kwargs):
        print("run_daily :" +"time :"+str(start)+" kargs"+str(kwargs))

    def listen_event(self, callback, a):
        print("listen_event \n")

    def log(self, msg):
        print("=>log %s \n".format(msg))

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
        parts = re.search(r'^(\d+):(\d+):(\d+)', time_str)
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
                    r'^sunrise\s*([+-])\s*(\d+):(\d+):(\d+)', time_str
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
                        r'^sunset\s*([+-])\s*(\d+):(\d+):(\d+)', time_str
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


HEBCAL_URL = 'https://www.hebcal.com/hebcal/?i=on&b=28&m=50&v=1&cfg=json&maj=on&year={}&c=on&geo=pos&latitude={}&longitude={}&tzid={}'

# to be compatiable with python 3.6,%z can't be used 
def convToDateObject(s):
    if len(s) == 10: # in case of Hannukah bug we don't have the time so set it to high 
        s+="T20:00:00"
    if len(s) > 19:
        s=s[:19]
    o = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
    return o

class TimeRec:
        def __init__(self):
            self.s = None  # start time, date object 
            self.e = None  # end time, date object 
            self.help = ""  # string 
            self.normal = False  # is it normal friday/sat
        
        def update(self):
            if self.s.weekday() == 4 and self.e.weekday() ==5 and len(self.help) == 0:
                self.normal = True 

        def __str__(self):
            n=" "
            if self.normal:
                n="n"
            s = "[{} : {}] {},{:20} {}".format(self.s,self.e,n,self.help,self.e-self.s)
            return s

class CalandarDb:
        
        def __init__(self):
            self.list = []
            self.state = STATE_OFF
            self.latitude = 0
            self.longitude = 0
            self.tz = ""
            self.tindex = 0
        
        def set_cord(self, lat, long):
            self.latitude = lat
            self.longitude = long
        
        def set_tz(self, mtz):
            self.tz = mtz

        def loadExample(self):

            t = TimeRec()
            t.s = convToDateObject("2020-07-03T11:07:00+03:00")
            t.e = convToDateObject("2020-07-03T11:08:00+03:00")
            t.normal = True
            t.help = ""
            self.list.append(t)


        def get_head(self):
            return self.list[self.tindex]
        
        def inc_head(self):
            self.tindex += 1
        
        def get_size(self):
            return len(self.list) - self.tindex

        def need_to_reread(self):

            if self.get_size() < 10:
                return True
            return False     

        def load(self):
            year = datetime.date.today().year
            s = self._load_year(year)
            s.extend(self._load_year(year+1))
            self._process(s)
            self.dump_log()

        def _load_year(self, year):
            url = HEBCAL_URL.format(year, self.latitude, 
                                    self.longitude, 
                                    self.tz)
            r = requests.get(url)
            y = json.loads(r.text)
            return y['items']

        def _update_list(self, now):
            drop = 0
            for o in self.list:
                if now >= o.e:
                    drop += 1
                elif now < o.s:
                    break
                else:
                    self.state = STATE_ON
            if drop > 0:
                self.list = self.list[drop:]
            if self.state == STATE_ON:
                self.list[0].s = now + datetime.timedelta(minutes=2)


        def _process(self, items):
            self.list = []
            state = "s"
            for o in items:
                c = o['category']

                if state == "s":
                    if c == "candles": 
                        d = convToDateObject(o['date'])
                        last = TimeRec()
                        last.s = d 
                        state = "e"
                elif state == "e":
                    if c == "holiday":
                        last.help = o['title']
                    if c == "havdalah": 
                        d = convToDateObject(o['date'])
                        last.e = d 
                        last.update()
                        self.list.append(last)
                        last = None
                        state = "s"

        def dump_log(self):
            cnt = 0            
            for o in self.list:
                cnt += 1
                print("Error hebcal {:02d} : {}: ".format(cnt, o))

        def _dump(self):
            cnt = 0            
            for o in self.list:
                cnt += 1
                print(" {:02d} : {} ".format(cnt, o))       
        
        def save_to_file(self, filename):
            with open(filename, 'wb') as config_dictionary_file:
               pickle.dump(self.list, config_dictionary_file)
        
        def load_from_file(self, filename):
            with open(filename, 'rb') as config_dictionary_file:
               self.list = pickle.load(config_dictionary_file)




db = CalandarDb()
db.set_cord(32.26,34.905)
db.set_tz('Asia/Jerusalem')
db.load()
#now = datetime.datetime.now()
d11 = datetime.datetime.strptime('2021-09-8T21:13:00', '%Y-%m-%dT%H:%M:%S')
now = datetime.datetime.now()
#print(now - d11)
dt =d11 - now 
if dt < datetime.timedelta(minutes=10):
    print("yes")
if dt < datetime.timedelta(minutes=0):
    print("minus ")

print(dt)

print(now)
db._update_list(now)
#print("---")
#db.dump_log()


