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

def get_req():
    #url = 'https://www.hebcal.com/hebcal/?i=on&b=28&m=50&v=1&cfg=json&maj=on&year=now&month=10&c=on&geo=pos&latitude=32.26&longitude=34.905&tzid=Asia/Jerusalem'
    url = 'https://www.hebcal.com/hebcal/?i=on&b=28&m=50&v=1&cfg=json&maj=on&year=2020&c=on&geo=pos&latitude=32.26&longitude=34.905&tzid=Asia/Jerusalem'
    r = requests.get(url)
    s=r.text
    return s

HEBCAL_URL ='https://www.hebcal.com/hebcal/?i=on&b=28&m=50&v=1&cfg=json&maj=on&year={}&c=on&geo=pos&latitude={}&longitude={}&tzid={}'

class TimeRec:
        def __init__(self):
            self.s = None # start time, date object 
            self.e = None # end time, date object 
            self.help = "" # string 
            self.normal =False  # is it normal friday/sat
        
        def update(self):
            if self.s.weekday() == 4 and self.e.weekday() ==5 and len(self.help)==0:
                self.normal = True 

        def __str__(self):
            n=" "
            if self.normal:
                n="n"
            s = "[{} : {}] {},{:20} {}".format(self.s.date(),self.e.date(),n,self.help,self.e-self.s)
            return s

def convToDateObject(s):
    if len(s) > 19:
        s=s[:19]
    o = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
    return o


class CalandarDb:

        def __init__(self):
            self.list = []
            self.state = "off" 
            self.latitude = 0
            self.longitude = 0
            self.tz = ""
        
        def set_cord(self,lat,long):
            self.latitude = lat
            self.longitude = long
        
        def set_tz(self,mtz):
            self.tz = mtz

        def load(self):
            year = datetime.date.today().year
            s = self._load_year(year)
            s.extend(self._load_year(year+1))
            self._process(s)

        def _load_year(self,year):
            url = HEBCAL_URL.format(year,self.latitude,self.longitude,self.tz)
            r = requests.get(url)
            y = json.loads(r.text)
            return y['items']

        def _update_list(self,now):
            drop =0
            for o in self.list:
                if now > o.e:
                    drop +=1
                elif now < o.s:
                    break;
                else:
                   self.state ="on"
            if drop > 0:
               self.list = self.list[drop:]  


        def _process(self,items):
            self.list =[]
            state = "s"
            for o in items:
                c = o['category']
                if state == "s":
                    if c == "candles" : 
                        d  = convToDateObject(o['date'])
                        last = TimeRec()
                        last.s =d 
                        state = "e"
                elif state == "e" :
                    ischanukah = False  # there is a bug on chanuka 
                    if c ==  "holiday":
                        last.help = o['title']
                        if "Chanukah" in o['title']:
                            ischanukah = True 
                    if c == "havdalah" or ischanukah : 
                        d  = convToDateObject(o['date'])
                        last.e = d 
                        last.update()
                        self.list.append(last)
                        last = None
                        state = "s"

        def _dump(self):
            cnt =0            
            for o in self.list:
                cnt+=1
                print(" {:02d} : {} ".format(cnt,o))       
        
        def save_to_file(self,filename):
            with open(filename, 'wb') as config_dictionary_file:
               pickle.dump(self.list, config_dictionary_file)
        
        def load_from_file(self,filename):
            with open(filename, 'rb') as config_dictionary_file:
               self.list = pickle.load(config_dictionary_file)



def test3 ():
    c = CalandarDb()
    c.set_cord(32.26,34.905)
    c.set_tz("Asia/Jerusalem")
    c.load()
    c.save_to_file("c.data")
    #c1 = CalandarDb()
    #c1.load_from_file("c.data")
    c._dump()
    #61 : [2021-02-05 : 2021-02-06] n,                     1 day, 1:19:00 
    now = datetime.datetime.now()
    print(now)
    #now1 = convToDateObject("2021-02-06T18:07:00+02:00")
    c._update_list(now)
    print("========\n")
    print(" state {} \n".format(c.state))
    c._dump()






def test2 ():
    s = get_req()
    l=[]
    #s = '{"location":{"tzid":"Asia/Jerusalem","title":"32.26, 34.905, Asia/Jerusalem","geo":"pos","longitude":"34.905","latitude":"32.26"},"longitude":"34.905","date":"2019-10-08T09:44:37-00:00","latitude":"32.26","title":"Hebcal September 2019 32.26, 34.905, Asia/Jerusalem","items":[{"title":"Candle lighting: 6:30pm","hebrew":"הדלקת נרות","category":"candles","date":"2019-09-06T18:30:00+03:00"},{"date":"2019-09-07T19:47:00+03:00","category":"havdalah","hebrew":"הבדלה - 50 דקות","title":"Havdalah (50 min): 7:47pm"},{"category":"candles","date":"2019-09-13T18:21:00+03:00","hebrew":"הדלקת נרות","title":"Candle lighting: 6:21pm"},{"title":"Havdalah (50 min): 7:38pm","hebrew":"הבדלה - 50 דקות","category":"havdalah","date":"2019-09-14T19:38:00+03:00"},{"hebrew":"הדלקת נרות","title":"Candle lighting: 6:12pm","category":"candles","date":"2019-09-20T18:12:00+03:00"},{"title":"Havdalah (50 min): 7:28pm","hebrew":"הבדלה - 50 דקות","date":"2019-09-21T19:28:00+03:00","category":"havdalah"},{"date":"2019-09-27T18:02:00+03:00","category":"candles","hebrew":"הדלקת נרות","title":"Candle lighting: 6:02pm"},{"hebrew":"הבדלה - 50 דקות","title":"Havdalah (50 min): 7:19pm","category":"havdalah","date":"2019-09-28T19:19:00+03:00"},{"hebrew":"ערב ראש השנה","title":"Erev Rosh Hashana","link":"https://www.hebcal.com/holidays/rosh-hashana","date":"2019-09-29","category":"holiday","memo":"The Jewish New Year"},{"date":"2019-09-29T18:00:00+03:00","category":"candles","hebrew":"הדלקת נרות","title":"Candle lighting: 6:00pm"},{"category":"holiday","date":"2019-09-30","memo":"The Jewish New Year","hebrew":"ראש השנה 5780","title":"Rosh Hashana 5780","link":"https://www.hebcal.com/holidays/rosh-hashana","yomtov":true},{"title":"Candle lighting: 7:16pm","hebrew":"הדלקת נרות","date":"2019-09-30T19:16:00+03:00","category":"candles"}],"link":"https://www.hebcal.com/hebcal/?i=on;b=28;m=50;v=1;maj=on;year=2019;month=9;c=on;geo=pos;latitude=32.26;longitude=34.905;tzid=Asia%2FJerusalem"}'
    #s= '{"title":"Hebcal October 2020 32.26, 34.905, Asia/Jerusalem","link":"https://www.hebcal.com/hebcal/?i=on&b=28&m=50&v=1&maj=on&year=2020&month=10&c=on&geo=pos&latitude=32.26&longitude=34.905&tzid=Asia%2FJerusalem","longitude":"34.905","items":[{"hebrew":"ערב סוכות","category":"holiday","memo":"Feast of Tabernacles","title":"Erev Sukkot","date":"2020-10-02","link":"https://www.hebcal.com/holidays/sukkot"},{"date":"2020-10-02T17:55:00+03:00","title":"Candle lighting: 5:55pm","category":"candles","hebrew":"הדלקת נרות"},{"link":"https://www.hebcal.com/holidays/sukkot","subcat":"major","title":"Sukkot I","hebrew":"סוכות יום א׳","category":"holiday","date":"2020-10-03","memo":"Feast of Tabernacles","yomtov":true},{"category":"havdalah","hebrew":"הבדלה - 50 דקות","title":"Havdalah (50 min): 7:12pm","date":"2020-10-03T19:12:00+03:00"},{"hebrew":"סוכות יום ב׳ (חול המועד)","category":"holiday","memo":"Feast of Tabernacles","title":"Sukkot II (CH''M)","date":"2020-10-04","link":"https://www.hebcal.com/holidays/sukkot","subcat":"major"},{"title":"Sukkot III (CH''M)","memo":"Feast of Tabernacles","category":"holiday","hebrew":"סוכות יום ג׳ (חול המועד)","link":"https://www.hebcal.com/holidays/sukkot","subcat":"major","date":"2020-10-05"},{"subcat":"major","link":"https://www.hebcal.com/holidays/sukkot","date":"2020-10-06","title":"Sukkot IV (CH''M)","memo":"Feast of Tabernacles","category":"holiday","hebrew":"סוכות יום ד׳ (חול המועד)"},{"date":"2020-10-07","subcat":"major","link":"https://www.hebcal.com/holidays/sukkot","category":"holiday","hebrew":"סוכות יום ה׳ (חול המועד)","title":"Sukkot V (CH''M)","memo":"Feast of Tabernacles"},{"date":"2020-10-08","subcat":"major","link":"https://www.hebcal.com/holidays/sukkot","category":"holiday","hebrew":"סוכות יום ו׳ (חול המועד)","title":"Sukkot VI (CH''M)","memo":"Feast of Tabernacles"},{"category":"holiday","hebrew":"סוכות יום ז׳ (הושענא רבה)","title":"Sukkot VII (Hoshana Raba)","memo":"Feast of Tabernacles","date":"2020-10-09","link":"https://www.hebcal.com/holidays/sukkot","subcat":"major"},{"date":"2020-10-09T17:46:00+03:00","hebrew":"הדלקת נרות","category":"candles","title":"Candle lighting: 5:46pm"},{"date":"2020-10-10","yomtov":true,"memo":"Eighth Day of Assembly","subcat":"major","link":"https://www.hebcal.com/holidays/shmini-atzeret","hebrew":"שמיני עצרת","category":"holiday","title":"Shmini Atzeret"},{"date":"2020-10-10T19:03:00+03:00","hebrew":"הבדלה - 50 דקות","category":"havdalah","title":"Havdalah (50 min): 7:03pm"},{"title":"Candle lighting: 5:38pm","hebrew":"הדלקת נרות","category":"candles","date":"2020-10-16T17:38:00+03:00"},{"date":"2020-10-17T18:55:00+03:00","hebrew":"הבדלה - 50 דקות","category":"havdalah","title":"Havdalah (50 min): 6:55pm"},{"date":"2020-10-23T17:30:00+03:00","category":"candles","hebrew":"הדלקת נרות","title":"Candle lighting: 5:30pm"},{"title":"Havdalah (50 min): 6:47pm","hebrew":"הבדלה - 50 דקות","category":"havdalah","date":"2020-10-24T18:47:00+03:00"},{"date":"2020-10-30T16:23:00+02:00","hebrew":"הדלקת נרות","category":"candles","title":"Candle lighting: 4:23pm"},{"date":"2020-10-31T17:40:00+02:00","category":"havdalah","hebrew":"הבדלה - 50 דקות","title":"Havdalah (50 min): 5:40pm"}],"date":"2020-07-01T05:43:00-00:00","latitude":"32.26","location":{"geo":"pos","latitude":"32.26","longitude":"34.905","tzid":"Asia/Jerusalem","title":"32.26, 34.905, Asia/Jerusalem"}}'
    y = json.loads(s)
    state = "s"
    #pprint.pprint(y)
    for o in y["items"]:
        c = o['category']
        if state == "s":
           if c == "candles" : 
               d  = convToDateObject(o['date'])
               last = TimeRec()
               last.s =d 
               state = "e"
        elif state == "e" :
            ischanukah = False  # there is a bug on chanuka 
            if c ==  "holiday":
               last.help = o['title']
               if "Chanukah" in o['title']:
                   ischanukah = True 
            if c == "havdalah" or ischanukah  : 
               d  = convToDateObject(o['date'])
               last.e = d 
               last.update()
               l.append(last)
               last = None
               state = "s"
            if c == "candles": 
               print(" == skip :",str(o))
    cnt =0            
    for o in l:
       cnt+=1
       print(" {:02d} : {} ".format(cnt,o))       

                

def is_date_betwean(s,e,m):
    so =convToDateObject(s)
    eo =convToDateObject(e)
    mo =convToDateObject(m)
    if mo>=so and mo<=eo:
        return True
    return False     

def test4():
    print(is_date_betwean("2020-05-20T20:31:00+03:00",
    "2020-05-21T20:31:00+03:00","2020-05-21T20:32:00+03:00"))



#for t in range(0,120):
#   f=t/10.0
#   print(temp.calc_heat_index_celsius(16.0+f, 70.0),16+f,)
#main()


def test():
    #s="2020-07-03T20:31:00+03:00"
    s="2020-05-20T17:31:00+03:00"
    e="2020-05-22T20:31:00+03:00"
    so =convToDateObject(s)
    eo =convToDateObject(e)
    l=[]
    delta = eo - so
    today = datetime.date.today()
    now  = datetime.datetime.now()
    days = delta.days  + 1
    st = datetime.time(6, 0, 0)
    et = datetime.time(10, 0, 0)

    for d in range(days):
        cday = today + datetime.timedelta( days = d )
        print(" ==> day {} {} \n".format(d,cday))
        se = datetime.datetime.combine(cday, st)
        ee = datetime.datetime.combine(cday, et)
        #print(" event {}  {} \n".format(se,ee))
        if now < se:
            print("before: {} {}  \n".format(se,ee))
            #to = Object()
            #to.se = se
            #to.ee = ee
            #l.append(to)
        elif now < ee:
            #to = Object()
            #to.se = now
            #to.ee = ee
            #l.append(to)
            dt = ee - now
            if dt.total_seconds() > 60*10:
                print("middle: {} {}  \n".format(now,ee))
        else:
            print("skip  \n")
    return 


    runtime = datetime.time(16, 0, 0)
    today = datetime.date.today()
    print(today)
    print(type(today))
    a = today + datetime.timedelta( days=1 )
    print( a )

    event = datetime.datetime.combine(today, runtime)
    print(event)
    print(type(event))
    print(runtime)
    print(type(runtime))
    
    return 

    s="2020-01-03T16:19:00+02:00"
    #try 
    if len(s)>19:
        s=s[:19]
    print(s)    
    o = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
    #o = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
    #except 

    #print(o)
    #print(o.strftime("%a - %H:%M"))
    #s1="2020-06-30T20:31:00+03:00"
    #o1 = datetime.datetime.strptime(s1, '%Y-%m-%dT%H:%M:%S%z')
    #d = o1 - o
    #if d > datetime.timedelta(days=1):
    #    print(" hey")
    #print(d)

    #print('Date:', o.date().year)
    #print('Time:', o.time())
    #print(o.weekday())

#test()
#test3()
#main()
#print("sd")

def test_schedule():
    #test1 ()
    ad=MyApp();
    with open("_test_.yaml", 'r') as stream:
        d=yaml.load(stream)
        sc=d['hello_world']['schedule'];

    #pprint.pprint(sc)
    #return 

    tmps = temp_sensor.HeaterSensor(ad,d['hello_world']['heater']);
    sch = schedule.Schedule(ad,sc,tmps.on_schedule_event,None)
    print(str(sch));
    #d=datetime.now()
    d=datetime.datetime(2018,7,18,20,00,0)
    ad.set_now(d)
    sch.init ()
    sch.saturday_cb("a", {"state" : "pre",
                          "start" : "2020-07-03T19:19:00",
                          "end"   : "2020-07-04T20:19:00"
                          },None)
    sch.saturday_cb("a", {"state" : "off"
                          },None)



test_schedule()
