import appdaemon.plugins.hass.hassapi as hass
import datetime

#
# Hello World App
#
# Args:
#

class HelloWorld(hass.Hass):

    def initialize(self):
        self.cnt=1;
        self.log("hey this is me"+str(self.args));
        self.log("Hello from AppDaemon")
        self.log("You are now ready to run Apps!")
        self.log(self.get_now());
        self.log(self.args);
        self.notify("my message2")
        #self.run_every(self.sunrise_cb, self.get_now(), 2)
        #self.listen_state(self.presence_on, "switch.ac1",old = "off", new = "on")
        #self.run_in(self.my_turn_off, 1,param=[12,13])

        #state = self.get_state(entity='sun.sun')
        #self.log("State "+state)
        #self.log(str(self.__dict__))
        #status = self.set_state("switch.ac1", state = "on");
        #self.log("State "+status)
        #self.delay(1)
        #status = self.set_state("default","switch.ac1", state = "off");

    def presence_on(self, entity, attribute, old, new, kwargs):
        #self.log("turn on,start timer {0} - {1}-{2}".format(attribute, old, new));
        self.run_in(self.my_turn_off, 5)
        #self.run_every(self.sunrise_cb, self.get_now(), 2)

    def my_turn_off(self, kwargs ):
        self.log("dargs------" +str(kwargs));
        #self.turn_off("switch.ac1")


    def sunrise_cb(self, kwargs):
       self.log("cb1 --- "+str(self.cnt)+ str(kwargs));
       a=self.get_state("switch.ac1")
       t=self.get_state("sensor.temperature")
       self.log("state --- "+str(a)+' '+str(t));
       self.cnt=self.cnt+1
       #if (self.cnt % 2)==0:
       #    self.turn_on("switch.ac1")
       #else:
       #    self.turn_off("switch.ac1")



    def before_sunset_cb(self, kwargs):
       self.turn_off("switch.ac1")

