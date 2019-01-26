#!/usr/bin/env python

#
# See __doc__ for an explanation of what this module does
#
# See __usage__ for an explanation of runtime arguments.
#
# -Christopher Blunck
#

import sys, math

__author__ = 'Christopher Blunck'
__email__ = 'chris@wxnet.org'
__revision__ = '$Revision: 1.6 $'

__doc__ = 'temperature related conversionfunctions'
__usage__ = 'this module should not be run via the command line'



def celsius_to_fahrenheit(c):
    'Degrees Celsius (C) to degrees Fahrenheit (F)'
    return (c * 1.8) + 32.0

def fahrenheit_to_celsius(f):
    'Degrees Fahrenheit (F) to degrees Celsius (C)'
    return (f - 32.0) * 0.555556

def calc_heat_index_celsius(c, hum):
    ''' calculate heat index '''
    f=celsius_to_fahrenheit(c)
    rf=calc_heat_index(f, hum)
    return fahrenheit_to_celsius(rf)


def calc_heat_index_v2(temp, hum):

    return 0.363445176 + 0.988622465 * temp + 4.777114035 * hum - 0.114037667 * \
           temp * hum - 8.50208 * (10 ** -4) * (temp ** 2) - 2.0716198 * \
           (10 ** -2) * (hum ** 2) + 6.87678 * (10 ** -4) * (temp ** 2) * \
           hum + 2.74954 * (10 ** -4) * temp * (hum ** 2) 


def calc_heat_index(temp, hum):
    '''
    calculates the heat index based upon temperature (in F) and humidity.
    http://www.srh.noaa.gov/bmx/tables/heat_index.html

    returns the heat index in degrees F.
    '''
    
    if (temp < 80):
        if temp>69.9:
          return (calc_heat_index_v2(temp, hum))
        else:
           return temp
    else:
        return -42.379 + 2.04901523 * temp + 10.14333127 * hum - 0.22475541 * \
               temp * hum - 6.83783 * (10 ** -3) * (temp ** 2) - 5.481717 * \
               (10 ** -2) * (hum ** 2) + 1.22874 * (10 ** -3) * (temp ** 2) * \
               hum + 8.5282 * (10 ** -4) * temp * (hum ** 2) - 1.99 * \
               (10 ** -6) * (temp ** 2) * (hum ** 2);


def calc_wind_chill(t, windspeed, windspeed10min=None):
    '''
    calculates the wind chill value based upon the temperature (F) and
    wind.

    returns the wind chill in degrees F.
    '''

    w = max(windspeed10min, windspeed)
    return 35.74 + 0.6215 * t - 35.75 * (w ** 0.16) + 0.4275 * t * (w ** 0.16);



