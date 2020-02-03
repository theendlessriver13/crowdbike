# -*- coding: utf-8 -*-
"""
Program <crowdbike.py> to read and record GPS data, air temperature and humidity
using Adafruit's Ultimate GPS and a DHT22 temperature sensor while riding
on a bike.

First established at:
  University of Freiburg
  Environmental Meteology
  Version 1.2
  Written by Heinz Christen Mar 2018 
  Modified by Andreas Christen Apr 2018 
  https://github.com/achristen/Meteobike

Modified Jan 2019:
  Ruhr-University Bochum
  Urban Climatology Group
  Jonas Kittner
  added a nova PM-sensor to the kit
  made a non-GUI version to run in background

Using the class GpsPoller
written by Dan Mandle http://dan.mandle.me September 2012 License: GPL 2.0
"""
import numpy as np
import pandas as pd
import os
import time
import adafruit_dht
import board
import threading
import datetime
import json
from   gps     import gps, WATCH_ENABLE
from   FUN     import get_ip, read_dht22, pm_sensor

# __load confing file__
with open('config.json', 'r') as config:
  config = json.load(config)

# __user parameters__
raspberryid = config['user']['bike_nr'] # number of your pi
studentname = config['user']['studentname']

# __calibration params__
temperature_cal_a1 = 1.00100 # enter the calibration coefficient slope for temperature
temperature_cal_a0 = 0.00000 # enter the calibration coefficient offset for temperature

vappress_cal_a1    = 1.00000 # enter the calibration coefficient slope for vapour pressure
vappress_cal_a0    = 0.00000 # enter the calibration coefficient offset for vapour pressure

logfile_path = config['user']['logfile_path']
if not os.path.exists(logfile_path):
  os.makedirs(logfile_path)
logfile = logfile_path + raspberryid + "-" + studentname + "-" + time.strftime("%Y-%m-%d.csv")

# initialze datframe to append to
columnnames = ['ID','Record','Raspberry_Time','GPS_Time','Altitude','Latitude','Longitude','Temperature','TemperatureRaw','RelHumidity','RelHumidityRaw','VapourPressure','VapourPressureRaw','PM10','PM2.5']
df = pd.DataFrame(columns=columnnames)
# check if file is already there
if not os.path.exists(logfile):
  df.to_csv(logfile, index=False)

# __global variables___
gpsd          = None
pm_status     = config['user']['pm_sensor']
sampling_rate = config['user']['sampling_rate']

class GpsPoller(threading.Thread):
  def __init__(self):
    threading.Thread.__init__(self)
    global gpsd # bring it in scope
    gpsd               = gps(mode=WATCH_ENABLE) #starting the stream of info
    self.current_value = None
    self.running       = True # setting the thread running to true
  def run(self):
    global gpsd
    while gpsp.running:
      gpsd.next() # this will continue to loop and grab EACH set of gpsd info to clear the buffer
      

gpsp         = GpsPoller() # create thread
gpsp.start()
dht22_sensor = adafruit_dht.DHT22(board.D4)
nova_pm = pm_sensor(dev='/dev/ttyUSB0')
counter = 0

while True:
  now = datetime.datetime.utcnow()
  # get sensor readings from DHT-sensor
  try:
    readings = read_dht22(dht22_sensor)
  except:
    dht22_humidity = np.nan
    dht22_temperature = np.nan
    
  dht22_humidity = readings['humidity']
  dht22_temperature = readings['temperature']
    
  # calculate temperature with sensor calibration values TODO: Ckeck if everything is correct or all of this is actually needed
  dht22_temperature_raw      = round(dht22_temperature, 5)
  dht22_temperature_calib    = round(dht22_temperature * temperature_cal_a1 + temperature_cal_a0, 3)
  dht22_temperature          = dht22_temperature_calib

  saturation_vappress_ucalib = 0.6113*np.exp((2501000.0/461.5)*((1.0/273.15) - (1.0/(dht22_temperature_raw + 273.15))))
  saturation_vappress_calib  = 0.6113*np.exp((2501000.0/461.5)* ((1.0/273.15) - (1.0/(dht22_temperature_calib + 273.15))))
  dht22_vappress             = (dht22_humidity/100.0)*saturation_vappress_ucalib
  dht22_vappress_raw         = round(dht22_vappress, 3)
  dht22_vappress_calib       = round(dht22_vappress * vappress_cal_a1 + vappress_cal_a0, 3)
  dht22_vappress             = dht22_vappress_calib

  dht22_humidity_raw         = round(dht22_humidity, 5)
  dht22_humidity             = round(100 * (dht22_vappress_calib/saturation_vappress_calib), 5)

  # read pm-sensor takes max 1 sec
  if pm_status == True:
    pm    = nova_pm.read_pm()
    pm2_5 = pm['PM2_5']
    pm10  = pm['PM10']
  else:
    pm2_5 = np.nan
    pm10  = np.nan
  
  # correct humidity reading TODO: seems kinda bad style to hardcode this
  if dht22_humidity > 100:
    dht22_humidity = 100
  
  # Get GPS position
  gps_time      = gpsd.utc
  gps_altitude  = gpsd.fix.altitude
  gps_latitude  = gpsd.fix.latitude
  gps_longitude = gpsd.fix.longitude
  f_mode        = int(gpsd.fix.mode) # store number of sats
  has_fix       = False # assume no fix

  # build readings
  readings = pd.DataFrame([{
    'ID': raspberryid,
    'Record': counter,
    'Raspberry_Time': now.strftime('%Y-%m-%d %H:%M:%S'),
    'GPS_Time': gps_time,
    'Altitude': gps_altitude,
    'Latitude': gps_latitude,
    'Longitude': gps_longitude,
    'Temperature': dht22_temperature,
    'TemperatureRaw': dht22_temperature_raw,
    'RelHumidity': dht22_humidity,
    'RelHumidityRaw': dht22_humidity_raw,
    'VapourPressure': dht22_vappress,
    'VapourPressureRaw': dht22_vappress_raw,
    'PM10': pm10,
    'PM2.5': pm2_5,
    }])

  # __readings to file___
  readings.to_csv(logfile, mode='a', header=False, index=False)

  finish = datetime.datetime.utcnow()
  runtime = finish - now
  offset = runtime.total_seconds()

  if offset > sampling_rate:
    offset = sampling_rate
  counter += 1

  time.sleep(sampling_rate - offset)