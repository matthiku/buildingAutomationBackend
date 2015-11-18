#!/usr/bin/env python3
# -*- coding: utf-8 -*-  

#===============================================================================+
#                                                                               |
#                           readTFsensors.py                                    |
#                                                                               |
#-------------------------------------------------------------------------------+
#                                                                               |
# PURPOSE:  waits for changes on all Tinkerforge-attached temp sensors and      |
#           the Dual Relay switch status and records it into a local database   |
#                                                                               |
# CALLER:   a shell script (/root/readTFsensors.sh), started on each reboot     |
#           by CRON, runs an endless loop which calls this Python script        |
#           (unless there is an error)                                          |
#                                                                               |
# OUTPUT:   mySQL db (local), table sensors                                     |
#                                                                               |
#-------------------------------------------------------------------------------+
# (c) 2015 Matthias Kuhs                                                        |
#===============================================================================+
# Description:                                                                  |
#                                                                               |
#                                                                               |
#                                                                               |


# IP address (and port) of computer to which TF modules are physically connected to
HOST = "localhost"
PORT = 4223

# TF modules ID number
HW_ID = 'bSC'
FR_ID = '6Jm'
MAIN_ID = 'bTh'


from tinkerforge.ip_connection        import IPConnection
from tinkerforge.bricklet_temperature import Temperature
from tinkerforge.bricklet_dual_relay  import DualRelay

import pymysql

import datetime
import signal
import time
import sys
import os
import subprocess
import traceback

from libFunctions import getMySQLconn
from libFunctions import broadcast


#-----------------------------------------------------------------------------------
# handle keyboard interrupts
#-----------------------------------------------------------------------------------
def signal_handler(signal, frame):
    lclConn.commit()
    localSQL.close()
    print('You pressed Ctrl+C! Program gracefully ended.')
    sys.exit(0)
    
# configure the above function as the signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)



# determine host OS ('win32' or 'linux2')
onWindows = False
onLinux   = False
if sys.platform     == 'win32':
    onWindows        = True
if sys.platform[:5] == 'linux':
    onLinux          = True


logDir = ".\\Logfiles\\"

 
    
#------------------------------------------------------------------------
#                                   Logging 
#------------------------------------------------------------------------
import logging
#import logging.config
#logging.config.fileConfig('logging.conf')
global Logger
Logger = logging.getLogger("buildingControl")    # create logger obj with a name of this module
if len(sys.argv) > 1:
    Logger.setLevel(logging.DEBUG) 
    print("Debugging is active!")
else:
    Logger.setLevel(logging.INFO)
    print("No debugging active!")

now = datetime.datetime.now()           # determine log file name
logName = "buildingControlLog.txt";
if onLinux: logDir = "./Logfiles/";

file_log_handler = logging.FileHandler( os.path.join(logDir, logName) ) 
Logger.addHandler(file_log_handler)

stderr_log_handler = logging.StreamHandler()    # log to the console as well
Logger.addHandler(stderr_log_handler)

formatter = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s: %(message)s')
file_log_handler.setFormatter(formatter)
stderr_log_handler.setFormatter(formatter)




# connect to the (local) mySQL DB on the Raspi
lclConn  = getMySQLconn()
if lclConn == -1: sys.exit(-1)     # failed to connect to local mySQL DB!
localSQL = lclConn.cursor()

#------------------------------------------------------------------------
# get last modify date of this script
#------------------------------------------------------------------------
scriptChangeDate = os.path.getmtime(__file__)


def getTmStmp():
    now = datetime.datetime.now()
    tms = now.strftime("%Y-%m-%d %H:%M:%S")
    return str(tms) + " " + str(round( datetime.datetime.timestamp( now )) )

# record the data into the database
def writeToDB(hw,fr,mn):
    now = datetime.datetime.now()        
    timestamp = round( datetime.datetime.timestamp( now )) 
    # get newest record from DB
    sql = "SELECT * FROM `sensors` ORDER BY computertime DESC LIMIT 1; "
    count = localSQL.execute(sql)
    if count>0:
          last = localSQL.fetchone()
    else: last = (0,0,0,0)
    lastTime = last[0]
    # check if old values equals new values
    diff = abs( float(last[1])-float(hw) + float(last[2])-float(fr) + float(last[3])-float(mn) )
    if diff < 0.1: 
        Logger.debug("Write to DB skipped since no values changed: (OLD)" + str(last) + " (NEW)" + hw + ', ' + fr + ', ' + mn )
        return    
    # create SQL statement
    # minimum time resolution is one second,
    # so if there's already a record for the same second, we replace the values
    if lastTime == timestamp:
        tempSQL = "UPDATE `sensors` SET `heatwater`=" + hw + ", `frontroom`=" + fr + ", `mainroom`=" + mn + \
            " WHERE `computertime`=" + str(timestamp) + "; "
    else: 
        tempSQL = "INSERT INTO `sensors` () VALUES (" + str(timestamp) +", "+ hw +", "+ fr +", "+ mn +");"
    # execute SQL statement
    try:    count=localSQL.execute(tempSQL)
    except: Logger.exception("Unable to write sensor values to local DB!")    
    Logger.debug(str(count) + " records written to DB by: "+tempSQL)

def writeSensFile(which, value, hw, fr, mn):
    # if it's still the initial value, return
    if value == 0: return
    # create file name for value logging file
    logFn = "temp"+which+".log" 
    # get previous data from logging file
    try:    oldData = open(os.path.join(logDir,logFn),"r").readline().split(',')
    except: oldData = ('0, last update: ' + getTmStmp()).split(',')
    oldVal = oldData[0]
    oldTimestamp = oldData[1].split()[4]
    # calculate value change and time span since last writing into log file
    valDiff = round(abs(float(oldVal) - value),2)
    timeDiff = int( getTmStmp().split()[2] ) - int(oldTimestamp)
    Logger.debug(which + ": old value: " + oldVal + " New value: " + str(value) + " timeDiff: " + str(timeDiff) )
    # do nothing if there is no change from previous reading!
    # allow writing the same value only every 5 minutes
    if valDiff < 0.1 and timeDiff < 300: 
        Logger.debug(which + ": Not updating since value change is too small: " + str(valDiff) )
        return    
    # write a file (named after the sensor location) containing the last reading and a timestamp
    open( os.path.join(logDir,logFn), "w" ).write( str(value) + ", last update: " + getTmStmp() )
    # write values to local mySQL DB
    writeToDB( str(round(hw,1)), str(round(fr,1)), str(round(mn,1) ) )
    
 
# unless something goes wrong ....
exitCode=0    


# This class will use any Temperature Bricklets that
# are connected to the computer and record the temperature to the DB.
#
# The program should stay stable if Bricks are connected/disconnected,
# if the Brick Daemon is restarted or if a Wi-Fi/RS485 connection is lost.
# It will also keep working if you exchange the Master or one of the
# Bricklets by a new one of the same type.
#
# If a Brick or Bricklet loses its state (e.g. callback configuration)
# while the connection was lost, it will automatically be reconfigured accordingly.
class readTFsensors:

    def __init__(self):
        self.tmpHW = None
        self.tmpFR = None
        self.tmpMain = None
        self.tmpHWval = 0
        self.tmpFRval = 0
        self.tmpMainval = 0

        # Create IP Connection
        self.ipcon = IPConnection() 

        # Register IP Connection callbacks
        self.ipcon.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)
        self.ipcon.register_callback(IPConnection.CALLBACK_CONNECTED, self.cb_connected)

        # Connect to brickd, will trigger cb_connected
        self.ipcon.connect( HOST, PORT ) 

        self.ipcon.enumerate()
        
        # wait until all values are being received
        Logger.debug('waiting for all sensors to send values ...')
        while self.tmpHWval==0 or self.tmpFRval==0 or self.tmpMainval==0:
            now = round( datetime.datetime.timestamp(datetime.datetime.now()) ) 
            Logger.debug( str(now) + ' (HW, FR, main) ' + str(self.tmpHWval)+', '+str(self.tmpFRval)+', '+str(self.tmpMainval) )
            time.sleep(15)               # wait 15 seconds
        Logger.debug( 'all sensors found: (HW, FR, main)' + str(self.tmpHWval)+', '+str(self.tmpFRval)+', '+str(self.tmpMainval) )    
        
        # loop to check if source code was changed, 
        # then exit the python program in order to get it restarted by the shell script
        while True:
            time.sleep(120)               # wait 2 minutes
            # check if script source code has changed
            newScrChgDate = os.path.getmtime(__file__)
            if ( scriptChangeDate != newScrChgDate ):
                Logger.info("Source code changed, (ending script). Old: "+str(scriptChangeDate) + ", New: " + str(newScrChgDate) )
                sys.exit(9)  # means 'reload and restart'
                
            # check if debugging is requested
            if os.path.isfile('debug_off'):
                Logger.setLevel(logging.INFO) 
                
            # check if debugging is requested
            if os.path.isfile('debug_on'):
                Logger.setLevel(logging.DEBUG) 
                
        
    # Callback updates temperature 
    # - for heatwater temperature
    def cb_tempHW(self, temperature):   
        self.tmpHWval = temperature/100.0
        writeSensFile("HW", self.tmpHWval, self.tmpHWval, self.tmpFRval, self.tmpMainval)
    # - for front room temperature
    def cb_tempFR( self, temperature):
        self.tmpFRval  = temperature/100.0
        writeSensFile("FR", self.tmpFRval, self.tmpHWval, self.tmpFRval, self.tmpMainval)
    # - for main room temperature
    def cb_tempMain(self, temperature):
        self.tmpMainval = temperature/100.0
        writeSensFile("Main", self.tmpMainval, self.tmpHWval, self.tmpFRval, self.tmpMainval)


    # Callback handles device connections and configures possibly lost 
    # configuration of lcd and temperature callbacks, backlight etc.
    def cb_enumerate(self, uid, connected_uid, position, hardware_version, firmware_version, device_identifier, enumeration_type):
        if enumeration_type == IPConnection.ENUMERATION_TYPE_CONNECTED or \
           enumeration_type == IPConnection.ENUMERATION_TYPE_AVAILABLE:
                
            # Enumeration is for Temperature Bricklets
            if device_identifier == Temperature.DEVICE_IDENTIFIER:
                # Create individual temperature device objects for each sensor
                if uid==HW_ID:
                    self.tmpHW = Temperature(uid, self.ipcon) 
                    self.tmpHWval = self.tmpHW.get_temperature()/100.0    # read initial value
                    writeSensFile("HW", self.tmpHWval, self.tmpHWval, self.tmpFRval, self.tmpMainval)
                    self.tmpHW.register_callback( self.tmpHW.CALLBACK_TEMPERATURE, self.cb_tempHW )
                    self.tmpHW.set_temperature_callback_period(500)
                elif uid==FR_ID:
                    self.tmpFR = Temperature(uid, self.ipcon) 
                    self.tmpFRval = self.tmpFR.get_temperature()/100.0    # read initial value
                    writeSensFile("FR", self.tmpFRval, self.tmpHWval, self.tmpFRval, self.tmpMainval)
                    self.tmpFR.register_callback( self.tmpFR.CALLBACK_TEMPERATURE, self.cb_tempFR )
                    self.tmpFR.set_temperature_callback_period(500)
                elif uid==MAIN_ID:
                    self.tmpMain = Temperature(uid, self.ipcon) 
                    self.tmpMainval = self.tmpMain.get_temperature()/100.0    # read initial value
                    writeSensFile("Main", self.tmpMainval, self.tmpHWval, self.tmpFRval, self.tmpMainval)
                    self.tmpMain.register_callback( self.tmpMain.CALLBACK_TEMPERATURE, self.cb_tempMain )
                    self.tmpMain.set_temperature_callback_period(500)

    # Callback handles reconnection of IP Connection
    def cb_connected(self, connected_reason):
        # Enumerate devices again. If we reconnected, the Bricks/Bricklets
        # may have been offline and the configuration may be lost.
        # In this case we don't care for the reason of the connection
        self.ipcon.enumerate()
        

if __name__ == "__main__":


    myPID = str(os.getpid())
    txt = __file__ + ' started and PID is: ' + myPID 
    Logger.info( txt )
    broadcast( txt )
    # write PID to pid log file
    PIDfname = os.path.join( logDir, "PID_"+os.path.basename(__file__)+".log" )
    open( PIDfname, "w" ).write( "PID "+myPID+" started "+getTmStmp() )
        
    
    readTFsensors()

    
    Logger.info('Exit code is '+str(exitCode)+', ending script .... ' + __file__)
    
# since program ends here, we can delete the PID file
os.remove( PIDfname )  

# ============= FIN ==============
sys.exit(exitCode)
