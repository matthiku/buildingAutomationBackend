#!/usr/bin/env python 3﻿.4
#
#===============================================================================+
#                        buildingControl.py                                     |
#-------------------------------------------------------------------------------+
#                                                                               |
# PURPOSE:  monitors power and temperatures, controls heating and               |
#           switches light on motion in main room                              |
#                                                                               |
# ACTION:   In case of problems, reboots the RaspBerryPi in order to reset the  |
#           Tinkerforge sensors and restarting all the processes                |
#                                                                               |
# CALLER:   a shell script (/root/checkProcs.sh), started on each reboot        |
#           by CRON, runs an endless loop which calls this Python script        |
#                                                                               |
#-------------------------------------------------------------------------------+
# (c) 2015 Matthias Kuhs                                                        |
#===============================================================================+
# Description:                                                                  |
#                                                                               |
# (1) read eec's power usage via youLess tool                                   |
# (2) read eec's room temp sensors                                              |
# (3) monitor motion in main room to switch on lighting                         |
#                                                                               |
#    and reports it all via (local and remote) mySQL server                     |
#                                                                               |
#===============================================================================+
# CHANGELOG                                                                     |
#                                                                               |
# 08-JAN-2015 Step 1 above has changed                                          |
#                                                                               |
#-------------------------------------------------------------------------------+
#
# TODO: - Avoid possible flooding with writeApiPowerLog calls
# 
#-------------------------------------------------------------------------------+


#-------------------------------------------------
#          requires Python 3.x 
#-------------------------------------------------
# imports -
# - requests for HTTP etc
# - pymysql for  mySQL connectivity
#-------------------------------------------------
import requests
import pymysql

import time
import signal
import sys
import traceback
import glob
import os
import datetime
import random

# to enable multiprocessing (ftp-upload in background)
from multiprocessing import Process

from tinkerforge.ip_connection            import IPConnection
from tinkerforge.bricklet_lcd_20x4        import LCD20x4
from tinkerforge.bricklet_motion_detector import MotionDetector


# my own functions
from libFunctions import *



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




myPID = str(os.getpid())
txt = __file__ + ' started and PID is: ' + myPID 
Logger.info( txt )
broadcast( txt )
# write PID to pid log file
PIDfname = os.path.join( logDir, "PID_"+os.path.basename(__file__)+".log" )
open( PIDfname, "w" ).write( "PID "+myPID+" started "+getTmStmp() )
    

# Logfile for power profiles
pwrProfileLog = os.path.join(logDir, "powerProfileLog.txt")





#------------------------------------------------------------------------------------------------------
#                                       Constants
#------------------------------------------------------------------------------------------------------

# IDs for tinkerforge sensors
TF_MAINTEMP_UID = 'bTh'     # mainroom temp
TF_FRONTEMP_UID = '6Jm'     # frontroom temp
TF_HEATTEMP_UID = 'bSC'     # heating water temp
TF_LIGHT_UID    = '7dw'     # light sensor

ADMIN  = 'church.ennis@gmail.com'   # recipient of warning/error emails


# for WOL, we need MAC address of AVROOM PC 
#PC_MAC_ADDR = '00:1e:58:3e:eb:30'
PC_MAC_ADDR = '00-19-B9-10-C5-98'


# control file containing a timestamp and the last action (e.g. light on or off)
motionActionFile   = "motionAction.txt"
# control file containing a timestamp of the last motion
motionsFile        = 'lastMotion.txt'

# file that indicates that we're currently uploading a file via FTP
ftpUploadIndicator = "currentlyUploading.txt"

# Path containing the edited Sunday service recording file for upload via FTP
editedRecFilePath  = "Exchange\Audio for Uploading"



# get last modify date of this script
scriptChangeDate = os.path.getmtime(__file__)
myFuncChangeDate = os.path.getmtime('libFunctions.py')






#============================================================================
#
#                              Functions
#
#============================================================================

                        
def signal_handler(signal, frame):
    ''' handle keyboard interrupts '''
    print('Program gracefully ended.')
    sys.exit(0)
# configure the above function as the signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)



''' EVENT management 
    -------------------------- '''
def manageOnlineEvents( ):
    ''' Manage online events DB - check if there are updates or changes '''

    # -------------------------------------------------------------------
    # get all TANs from remote DB and check for modifications
    # -------------------------------------------------------------------
    remEvents = getApiEvents()
    lclTAN    = getCurrentTAN(lclSQLcursor)
    remTAN    = []   # array of all remote TANs
    modified  = False
    for ev in remEvents:
        remTAN.append(ev['seed'])   # add TAN to array
        # check if there is a modification request
        if ev['status'] in ['NEW', "UPDATE", "DELETE"]: 
            modified = True
        # send TAN via email
        if ev['status'] == "TANREQ" : 
            sendEmail(ADMIN, "current TAN is "+str(lclTAN), "current TAN was requested")
            return  # no further action needed in this round...
    # no action needed if there is no remote update
    if not modified: 
        Logger.debug("No updates found on remote Events DB")
        return

    # -------------------------------------------------------------------
    # look for valid TAN in remote DB 
    # -------------------------------------------------------------------
    if not lclTAN in remTAN: 
        notifyAll( "Changes were made to online Events DB but TAN " + \
            str(lclTAN) + " was not found in remote DB: " + str(remTAN) )
        return
    Logger.debug( str(lclTAN) + " - TAN was found in remote DB: " + str(remTAN) )
    
    # get the id of the modified record and set status=OK on remote DB via API
    for ev in remEvents:
        if ev['status'] in ['NEW',"UPDATE", "TANREQ", "DELETE"]:
            newOrUpdatedEvent = ev
            Logger.info("new or updated event found in online DB table: " +  str(ev))
            newStatus = 'OK'
            if ev['status'] == "DELETE" : newStatus = "OLD"
            updateApiEventStatus( ev['id'], newStatus ) # status OK on remote DB
            break     # only process one event at a time!
    
    # -------------------------------------------------------------------
    # modify local DB accordingly
    # -------------------------------------------------------------------
    newTAN = random.randint(10000,99999)
    insertNewEvent( lclSQLcursor, newOrUpdatedEvent, newTAN )
    notifyAll( "Successfully synced remote Events with local DB and new TAN: " + \
        str(newTAN) + "\n" + str(newOrUpdatedEvent), "Events DB synced - new TAN" )



''' POWER monitoring '''
def getPowerProfile( liste ):
    ''' create a profile of the recent power usage changes '''
    profl = {}
    basis = diff = low = liste[0]
    count = index = 0
    for li in liste:
        if abs(basis-li)>5: # disregard changes below 5
            profl[index]=[diff,count]
            index+= 1
            count = 1
            basis = li
        else: count+=1
        diff  = li-low
    profl[index]=[diff,count]
    
    found = "unknown"
    frProb = mlProb = pcProb = 0
    probability = 0

    if len(profl)>2:
    
        # analyse the element sequence (usage by seconds) in the profile
        for el in profl:

            usg = profl[el][0]
            cnt = profl[el][1]

            # check for avroomPC profile
            if pcProb==0: 
                if ( 8 < cnt < 22) and (18 < usg < 26): pcProb=40
                if ( 8 < cnt < 22) and (56 < usg < 60): pcProb=50
                if (18 < cnt < 22) and (18 < usg < 27): pcProb=50
                if (18 < cnt < 22) and (38 < usg < 40): pcProb=50
                if (18 < cnt < 22) and (75 < usg < 77): pcProb=50
                if (10 < cnt < 12) and (95 < usg < 97): pcProb=50
                if (16 < cnt < 18) and (104 < usg < 106): pcProb=50
                if (17 < cnt < 21) and (119 < usg < 122): pcProb=50
            elif pcProb<=50:
                if (17 < cnt < 22) and (113 < usg < 127): pcProb+=50
                if (11 < cnt < 40) and (109 < usg < 114): pcProb+=50
                if ( 7 < cnt < 14) and (138 < usg < 143): pcProb+=50
                if (30 < cnt < 32) and (135 < usg < 137): pcProb+=50
                if (     cnt > 23) and (106 < usg < 110): pcProb+=50
                if usg < 105 or usg > 141: pcProb = 0

            # check for fridge profile
            if frProb==0: 
                if (12 < cnt < 14) and (235 < usg < 237): frProb=50
                if (16 < cnt < 26) and (103 < usg < 180): frProb=50
                if (21 < cnt < 25) and ( 86 < usg < 100): frProb=50
                if (21 < cnt < 23) and ( 69 < usg <  71): frProb=50
            elif frProb==50: 
                if (cnt >  5) and (58 < usg < 80): frProb=100
                if (cnt >  0) and (58 < usg < 72): frProb= 90
                if (cnt > 20) and (60 < usg < 68): frProb=100

            # check for main lights profile
            if mlProb==0: 
                if ( 2 < cnt <  7) and (889 < usg < 899): mlProb=40
                if (12 < cnt < 14) and (840 < usg < 845): mlProb=50
            if mlProb==40:
                if (4 < cnt < 7) and (901 < usg < 916): mlProb=80
                if (4 < cnt < 7) and (850 < usg < 861): mlProb=80
            if mlProb==80:
                if (cnt > 4) and (910 < usg < 919): mlProb=100

        if frProb>=90: found="fridge"
        if mlProb>=40: found="mainLight"
        if pcProb>=40: found="AVRoomPC"
        
        probability = max(frProb,mlProb,pcProb)
        
        # save profile for further analysis
        with open( pwrProfileLog, "a") as f:
            f.write( getTmStmp()+" Cur.Pwr("+str(liste[-1])+") Suspect("+found+", "+str(probability)+'%) '+str(profl)+"\r\n" )
            f.close()
    
    return found, probability, profl
            
def analyzePowerData( list ):
    ''' 
    Analyze Power data - any hikes?
        ARGS:     list of recent power usage values (watt readings)
    '''
    
    # no data analysis when: 
    #   a) not enough data,
    #   b) event active or
    #   c) heating on
    if not watch['powerAlert'] and \
      ( len(list) < listSize \
        or watch['eventHasStarted'] \
        or watch['heatingActive']    ):
            return 
    
    # find and retain the lowest Watts value
    if min(list) > watch['lowestWatts']: watch['lowestWatts'] = min(list)
    if max(list) < watch['lowestWatts']: watch['lowestWatts'] = min(list)
    
    # no data analysis when: 
    #   d) all values are (nearly) identical!
    Logger.debug("Power min/max diff.: " + str(abs( max(list) - min(list) )))
    if abs( max(list) - min(list) ) < 5:
        watch['powerAlert'] = False
        watch['trustedApplianceRunning'] = False   
        watch['pwrAlertSuspicion'] = False   
        return
    
    # check for known power-usage pattern
    appliance, probability, powerProfile = getPowerProfile(list)

    currentUsage = list[-1]
    # recent change from profile:
    recentChg      = powerProfile[len(powerProfile)-1][0]
    changeDuration = powerProfile[len(powerProfile)-1][1]
    
    if watch['trustedApplianceRunning']:
        return
    
    if appliance=="fridge" or appliance=='AVRoomPC' and probability>90: 
        watch['pwrAlertSuspicion']  = False
        watch['trustedApplianceRunning'] = True
        text = appliance + " now using " + str(recentChg) + " Watts since " + str(changeDuration) + " secs. Total Usage: " + str(currentUsage) + " Watts."
        broadcast(text)
        Logger.debug(text)
        if currentUsage > 230:
            return
           
    # power is back to normal?
    if currentUsage < 231:
        if watch['powerAlert']: 
            Logger.debug( "==== stopped power alert =====")
        watch['powerAlert'] = False
        watch['trustedApplianceRunning'] = False   
        watch['pwrAlertSuspicion'] = False   
        return
       
    
    # We have a power usage increase
    if currentUsage - list[0] > 5:
        Logger.debug( "Power surge! Susp.appl.(" + appliance + ", probab. " + str(probability) + "%) PowerProfile: " + str(powerProfile) )
    
    if appliance=="fridge" or appliance=='AVRoomPC' and probability<=90:
        # we are not 100% sure yet that it's our watch['trustedApplianceRunning'] ...
        # Let's wait for another reading
        watch['pwrAlertSuspicion'] = True
        return

    # PowerAlert suspicion was NOT confirmed, so we must have another, unknown appliance running!
    if watch['pwrAlertSuspicion']:
        Logger.info( "PowerAlert suspicion was NOT confirmed, so we must have another, unknown appliance running! " + str(powerProfile) )
    
    # is average of last 50 readings 25% above previous avg?
    #recentHigh = getListAvg(list[-60:])
    
    Logger.debug("recent high: " + str(recentChg) + " - power alert? " + str(watch['powerAlert']) + " PowerProfile: " + str(powerProfile) )
    
    if not watch['powerAlert'] and not watch['trustedApplianceRunning']:
        if recentChg>5 and changeDuration>30:
            broadcast( "buildingControl.py power alert!\r\nUsage now at " + str(recentChg) + 
                       "\r\nsuspected appliance is " + appliance + "\r\nPowerProfile: " + str(powerProfile))
            #Logger.setLevel(logging.DEBUG) 
            watch['powerAlert'] = False
            return




''' Handling of MOTION in main room '''
def checkMotionActivity( tfLCD ):
    ''' MOTION control in MAIN room
    switch off the light if there was no motion in the last 5 mins (600 seconds) '''
    # read motion action file
    lastAction = getLastAction()
    # if last action wasn't switching on, 
    if ( lastAction[2].upper() != 'ON' ): return
    
    # convert first item in list to a floating number
    try:
        lastActionTime = float(lastAction[0])
    except:
        Logger.error("Failed to convert motionActionFile content to float: %s", lastAction[0])
        return                
        
    Logger.debug("Last motion-triggered activity was @ " +
                 str(datetime.datetime.fromtimestamp(lastActionTime)) + 
                 ", action: " + str(lastAction[1]) + " " + str(lastAction[2]) )
    # get last motion time
    now  = datetime.datetime.now()
    lastMotion = getLastMotion()
    Logger.info('Time since last motion: '+str( int(now.timestamp()-lastMotion) )+
              's, more than 300?'+str(now.timestamp()-lastMotion > 300)+' (Last action was:'+lastAction[2].upper() ) 
    # check if sufficient time has passed since last motion in the room
    #    and the last motion action was to switch on the lights
    #       if yes, switch off the light again
    if ( now.timestamp()-lastMotion > 600 ):
        # write current timestamp into the motions file (to avoid triggering another motion action)
        w = open(motionsFile, 'w')
        w.write( str(now.timestamp()) + ' ' + now.strftime("%Y-%m-%d %H:%M:%S") )
        w.close()
        # check if there was an event in room 1
        todaysEvent, watch['eventHasStarted'], toStart, room, sinceEnd, targetTemp, eventID, online_id = checkCurrentEvent( lclSQLcursor )
        if str(room).find('1')>=0:
            controlLights( lclSQLcursor, 'light,SpotPulpit,spot','off')
            time.sleep(1)   # repeat command to make it sure
            controlLights( lclSQLcursor, 'light,SpotPulpit,spot','off')
        else:
            controlLights( lclSQLcursor, 'light','off')        # execute switch off command
            time.sleep(1)   # repeat command to make it sure
            controlLights( lclSQLcursor, 'light','off')        # execute switch off command
        Logger.info( "switching light off after > 5 minutes of inactivity" )
        broadcast( "switching light off after > 5 minutes of inactivity" )
        Logger.info(str(now.timestamp()) + ', light, off, ' + now.strftime("%Y-%m-%d %H:%M:%S") )

        now  = datetime.datetime.now()
        aF = open( motionActionFile, 'w' )        # write this action to action file
        aF.write( str(now.timestamp()) + ', light, off, ' + now.strftime("%Y-%m-%d %H:%M:%S") )
        aF.close()
        
        tfLCD.backlight_off()

def getLastAction():
    ''' get last ACTION data '''
    try:
        file = open(motionActionFile)
    except:
        Logger.error("Error when opening motion action file in checkMotionActivity!")
        return 0,"Nothing","ON"    # we assume the worst and pretend the light was switched on ...       
    # read the file - format is: timestamp, what, onOrOff
    try:
        lastAction = file.read().split(', ')
    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ));
        Logger.info("Error when trying to read motion action file - Wrong format? - " + errmsg)
        file.close()
        return 0, 0, "ON"       # we assume the worst and pretend the light was switched on ...
    # it has to be 3 elements
    if len(lastAction) < 3:
        Logger.error("ERROR! Last motion action file, wrong content format: " + str(lastAction) )
        return 0, 0, "ON"       # we assume the worst and pretend the light was switched on ...
    #Logger.debug("Last motion action file content: " + str(lastAction) )
    return lastAction

def getLastMotion( update=False ):
    ''' 
    get last motion timestamp 
       or
    if the argument is True:
       => write new motion timestamp 
    '''
    # fictitious datetime for last motion
    lastMotion = 1388534400.0
    # this file contains the date of the last encountered motion
    if ( len (glob.glob(motionsFile) ) > 0 ):
        s = open(motionsFile).read().split()    # splite line by words (space limited strings)
        print('last motion file content:', s)
        try:
            lastMotion = float( s[0] )
        except:
            # ficitious start date
            lastMotion = 1388534400.0
            Logger.info('unable to properly convert motionfile timestamp value into float! '+str(s) )
    # if file does not exist yet
    else:
        Logger.info("no pre-existing motions found")
    # only update the motion file when requested!
    if not update: return lastMotion
    now  = datetime.datetime.now()
    # We have a new motion - write current timestamp into the motion file!
    w = open(motionsFile, 'w')
    w.write( str(now.timestamp()) + ' ' + now.strftime("%Y-%m-%d %H:%M:%S") )
    w.close()
    return lastMotion

def cb_motion_detected():
    ''' Callback function for detected motion '''
    Logger.debug("motion in main room detected!")
    # (for debugging onlY!) broadcast("Motion detected!")
    lastMotion = getLastMotion(True)    # write a new motion timestamp
    now  = datetime.datetime.now()
    diff = int( now.timestamp() - int(lastMotion) )
    lmt  = datetime.datetime.fromtimestamp(float(lastMotion)).strftime("%Y-%m-%d %H:%M:%S") 
    Logger.info("Motion Detected! Last motion was " + formatSeconds(diff) + " ago at " + lmt )
    lastAction = getLastAction()[2].upper()
    # DO NOTHING if last motion was more than 5 minutes (300 secs) ago and last action was "ON"
    if diff < 300 and lastAction == "ON": 
        Logger.info("Motion: No action needed, light was switched on less than 5 minutes ago")
        return
    Logger.info( "---- New motion detected, ACTION needed! ----")
    # get current event data (if any)
    todaysEvent, watch['eventHasStarted'], toStart, room, sinceEnd, targetTemp, eventID, online_id = checkCurrentEvent( lclSQLcursor )
    Logger.debug("todaysEvent, watch['eventHasStarted'], toStart, room, sinceEnd, targetTemp, eventID - " + \
                todaysEvent+', '+str(watch['eventHasStarted'])+', '+str(toStart)+', '+str(room)+', '+str(sinceEnd)+', '+str(targetTemp)+', '+str(eventID) )
    # DO NOTHING if light is already on and event is on in main room
    if lastAction == "ON" and watch['eventHasStarted'] and str(room).find('1')>=0:
        Logger.info("Motion: No action needed, EVENT is active and light should already be on...")
        return
        
    # wake up PC to enable camera recording  MKS 2015-02-10 disabled, not needed atm
    #wake_on_lan(PC_MAC_ADDR)
    
    # open file to write motionAction
    actionFile = open(motionActionFile, 'w')
    # for activity in main room, switch on all lights
    if ( watch['eventHasStarted'] 
         and str(room).find('1')>=0 
         and toStart < 1800 
         and toStart > 0 
        ):
        controlLights( lclSQLcursor, 'light,SpotPulpit,spot', 'on')
        action = str(now.timestamp()) + ', all, on' 
    # otherwise, just switch on the main light
    else:
        controlLights( lclSQLcursor, 'light', 'on')                 # use - controlLights() - asap!
        action = str(now.timestamp()) + ', light, on, ' + now.strftime("%Y-%m-%d %H:%M:%S")
    broadcast("Action after motion detected: " + action)
    sendEmail( ADMIN, 'buildingControl.py', "Lights were switched on after motion was detected: " + action )
    actionFile.write( action )
    # close all connections and files
    actionFile.close()

def cb_detection_cycle_ended():
    ''' Callback function for end of detection cycle '''
    Logger.debug("Motion Detection Cycle Ended (next detection possible in ~3 seconds)" )



''' Acquire recorded values from mySQL DB '''
def raspiTemp( cur ):
    ''' read latest temp value from Raspi '''
    timestampNow = round( datetime.datetime.timestamp( datetime.datetime.now() )) 
    # first, try to get data via logfile
    ts, temp = getLastTempHumid()
    age = timestampNow - ts
    
    # TODO! once babyTemp is back online ....
    return temp
    
    if age > 900:
        # try to get value from mySQL DB
        cur.execute("SELECT `ComputerTime`, `Temperature` FROM `TempHumid` ORDER BY `ComputerTime` DESC LIMIT 1" );
        r = cur.fetchone()
        age = timestampNow - r[0] 
        if age>900:
            Logger.info( "babyroom temp data is outdated! " + formatSeconds(age) + ' old: ' + \
                datetime.datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S") + ', ' + str(r[1]) )
        return r[1]
    return temp

def getLastTempValues( cur ):
    # read recent outdoor temp
    outdoor = getWeather()
    
    # read CURRENT temp sensor values
    sql = 'SELECT * FROM `sensors` ORDER BY computertime DESC LIMIT 1'
    result = cur.execute( sql )
    temps = (0,0,0,0)
    if result>0: temps = cur.fetchone()
    # return timestamp, heatwater, frontroom, mainroom, outdoor
    return temps[0], temps[1], temps[2], temps[3], outdoor

def getTFsensValues(lclSQLcursor):
    ''' Read the (TF) sensors and switches and write into local DB '''
    now = datetime.datetime.now()
    # get default values in case there's a problem
    timestamp, heatTemp, fronTemp, mainTemp, oldOutdoorTemp = getLastTempValues(lclSQLcursor)
    # check age of recent sensor readings
    dataAge = round( datetime.datetime.timestamp(now) - timestamp )
    if dataAge > 9000:
        exitCode = -1
        errmsg = "temp sensor values are "+str(dataAge)+" seconds old!! Check readTFsensors.py process!"
        notifyAll(errmsg)
    else: exitCode = 0
    babyTemp    = 10 #raspiTemp(lclSQLcursor)       # from temp sensor on Raspberry Pi ----CURRENTLY OOO----
    outdoorTemp = getWeather()
    if outdoorTemp == 99.5:       # function was unable to retrieve weather data
        outdoorTemp = oldOutdoorTemp # from weather service or alternatively, from last value
    # create SQL statement and write into DBs
    tempSQL = "INSERT INTO `building_templog` () VALUES ('" + now.strftime("%Y-%m-%d %H:%M:%S") + "', "
    tempSQL+= str(mainTemp) +", "+ str(heatTemp) +", "+ str(fronTemp) +", 0, 0, "+ str(outdoorTemp) +", "+ str(babyTemp) +");"
    executeSQL( lclSQLcursor, tempSQL, 'write TF sensor values into' )    # write into local DB on Raspi
    return tempSQL, outdoorTemp, mainTemp, fronTemp, heatTemp


''' currently unused ... '''
def checkForRecordingFile():
    ''' TODO !!
    Check if there is a file in the upload folder
    if yes, launch FTP upload in separate thread! 
    '''
    files = glob.glob("..\\" + editedRecFilePath + "\\*.mp3")
    if len(files)==0: return    # return if nothing was found
    if os.path.isfile("..\\" + editedRecFilePath + '\\' + ftpUploadIndicator):
        Logger.info( "Uploading still ongoing for file " + files[0] )
        return
    Logger.info( "Found file for ftp upload: " + str(files) )    
    # use process to allow running the upload in the background
    p = Process(target=uploadFTP, args=(files[0],))
    p.start()
    p.join()
    return

def writeToLCD( line, text, ):
    '''
    Write watts value to LCD and switch on LCD light if needed
    old layout:
        $LCDline0 = ("Heating: " + $heating + " @ " + $now.ToShortTimeString())
        $LCDline1 = ("Main:" + $MainRoomTemp + " Frt:" + $FrontRoomTemp)
        $LCDline2 = ("Pwr: " + $powerConsumption + " Watts  ")
        $LCDline3 = ( $curEvntTitle ).PadLeft(20)
    '''
    now=datetime.datetime.now()
    # failing to write to LCD is not fatal ...
    try:
        tfLCD.write_line(line,0,text)
        # always write the time ...
        tfLCD.write_line( 0, 15, now.strftime("%H:%M") )
        if watch['powerAlert'] or watts > 600:
            tfLCD.backlight_on()
        else:
            tfLCD.backlight_off()
    except:
        pass
    





#============================================================================
#
#                   MAIN program
#
#============================================================================


# set some initial values
watch = {}
watch['trustedApplianceRunning'] = False
watch['pwrAlertSuspicion']    = False
watch['eventHasStarted']   = False
watch['heatingActive']   = False
watch['lowestWatts']   = 0
watch['powerAlert']  = False


listSize  = 200  # for list of recent power readings




# Connect to the local mySQL DB
lclConn      = getMySQLconn()
lclSQLcursor = lclConn.cursor()



# get online configuration settings
settings = getSettings(lclSQLcursor)




# Connect to the TinkerForge modules
try:
    tfConn = getTFconn()        # Tinkerforge connection
except  Exception as e:
    errmsg = str(traceback.format_exception( *sys.exc_info() ))
    Logger.error("TinkerForge connection failed! Reason: " + errmsg )
tfLCD      = getTFLCD(tfConn)   # LCD bricklet object    
tfMD       = getMotion(tfConn)  # Motion bricklet object

# Register motion detection callback function
tfMD.register_callback(tfMD.CALLBACK_MOTION_DETECTED, cb_motion_detected)

# Register detection cycle ended callback 
tfMD.register_callback(tfMD.CALLBACK_DETECTION_CYCLE_ENDED, cb_detection_cycle_ended)  

# get variouse TF sensor objects
tfMainTemp = getTFsensors(tfConn,TF_MAINTEMP_UID)
tfFronTemp = getTFsensors(tfConn,TF_FRONTEMP_UID)
tfHeatTemp = getTFsensors(tfConn,TF_HEATTEMP_UID)



#--------------------------------------------------------
# start with the first reading of power usage
#--------------------------------------------------------

# open the HTTP connection
httpSession = requests.Session()                # create the httpSession object
watts       = getCurrentPower( httpSession )    # get the initial reading

# some global variables
count  = 0;  # counter for the loop    
recent = []; # collecting recent values to analyse aberrations

# start the list with the last 60 values ^= 1 minute of data
maxList(recent, watts, listSize);


# get current switches status
boiler_on, heating_on = checkHeatingStatus(tfConn)

# get initial values for comparison
mainTemp = fronTemp = 0


# write first reading into local DB
sql = "INSERT INTO `building_power` (`power`, `boiler_on`, `heating_on`) VALUES (" \
      + str(watts) +', '+ str(boiler_on) +', '+ str(heating_on) + ");"
executeSQL( lclSQLcursor, sql, "write first reading into" )


#------------------=========--------------------------------------
# initial recording of power data into remote DB via buildingAPI
#---------------------------=========-----------------------------
now = datetime.datetime.now()
writeApiPowerLog(watts, boiler_on, heating_on, now)







time.sleep(1)           # wait a moment ...

# start building a new SQL statement
sql = "INSERT INTO `building_power`(`datetime`,`power`,`boiler_on`,`heating_on`) VALUES "

# can change, will then trigger a reboot
exitCode = 0





#======================================================================#
#
#                              MAIN action
#
#======================================================================#
if __name__ == '__main__':

    oldWatts = watts    # keep track of previous value to react on changes


    while True:
        
        #---------------------------------------------------------------------------------------------------
        # read and evaluate  ==> POWER <==  usage
        #---------------------------------------------------------------------------------------------------
        # extract CURRENT watt value from online data
        watts = getCurrentPower( httpSession );
        # update the list of the last xxx values
        maxList(recent, watts, listSize);            
        # write current power data on LCD
        writeToLCD( 2, "Pwr: "+str(watts)+" Watts" )


        
        #---------------------------------------------------------------------------------------------------
        # add new values to SQL statement
        # when we have 10 values (= 10 seconds), write data into database
        #---------------------------------------------------------------------------------------------------
        now = datetime.datetime.now()        
        if now.second % 10 == 0:
        
            # get current switches status
            boiler_on, heating_on = checkHeatingStatus(tfConn)
            
            # check for trend changes in POWER usage etc
            if not watch['eventHasStarted'] and not watch['heatingActive']:
                analyzePowerData( recent );
            
            # build SQL statement
            sql += "('" + now.strftime("%Y-%m-%d %H:%M:%S") + "', "
            sql += str(watts) +', '+ str(boiler_on) +', '+ str(heating_on) + ");"
            executeSQL( lclSQLcursor, sql, 'record power data into' )
            # initialize SQL statment            
            sql = "INSERT INTO `building_power`(`datetime`,`power`,`boiler_on`,`heating_on`) VALUES "
        else:
            # otherwise, continue to build the SQL statement
            sql += "('" + now.strftime("%Y-%m-%d %H:%M:%S") + "', "
            sql += str(watts) +', '+ str(boiler_on)  +', '+ str(heating_on) +"), "


        #---------------------------------------------------------------------------------------------------
        # only write to REMOTE DB when value change is bigger than 5 Watt! 
        #---------------------------------------------------------------------------------------------------
        if abs(watts - oldWatts) > 5:  # tolerance changed to 5 Watt
            now     = datetime.datetime.now()
            prev    = now - datetime.timedelta(seconds=1)  # get timestamp from previous reading
            boiler_on, heating_on = checkHeatingStatus(tfConn)
            # write both, the old and new value into the DB using the buildingAPI method 
            #writeApiPowerLog( str(round(oldWatts,1)), boiler_on, heating_on, prev )
            writeApiPowerLog(                  watts, boiler_on, heating_on,  now )

            # retain the previous value
            oldWatts = watts

        
        #---------------------------------------------------------------------------------------------------
        # every 5 mins, read the (TF) sensors and switches and manage the EVENTs
        #---------------------------------------------------------------------------------------------------
        if (now.minute % 5 == 0 and now.second == 0)    or count == 0:

            # write status into static logfile
            boiler_on, heating_on = checkHeatingStatus(tfConn, writeLog=True)
        
            # get latest values and write them into remote DB
            oldMT, oldFT = mainTemp, fronTemp
            SQLcmd, outdoorTemp, mainTemp, fronTemp, heatTemp = getTFsensValues( lclSQLcursor )
            # only write into remote DB if there was a value change
            if not oldMT == mainTemp or not oldFT == fronTemp:
                writeApiTempLog(outdoorTemp, mainTemp, fronTemp, heatTemp, watts, heating_on)
            
            # write debug info into the logfile 
            Logger.info( 'Watts:' + str(watts) + ', recentAvg: ' + str(round( getListAvg(recent) )) +
                           "\r\nFridge on? "    + str(watch['trustedApplianceRunning'])     +
                           "\tHeating on? "     + str(watch['heatingActive'])    +
                           "\tPower Alert? "    + str(watch['powerAlert'])       +
                           "\tLowest value: "   + str(watch['lowestWatts'])       )
            
            #======================#
            #   EVENT MANAGEMENT   #
            #======================#---------------------------------------------------------------
            # Check for (valid) changes in the online event database 
            #--------------------------------------------------------------------------------------
            manageOnlineEvents( )
            
            #--------------------------------------------------------------------------------------
            # check if we have an event going on at the moment
            #--------------------------------------------------------------------------------------
            todaysEvent, watch['eventHasStarted'], toStart, room, sinceEnd, targetTemp, eventID, online_id = checkCurrentEvent( lclSQLcursor )
            #print( "todaysEvent, watch['eventHasStarted'], toStart, room, sinceEnd, targetTemp, eventID, online_id" )
            #print( todaysEvent, watch['eventHasStarted'], toStart, room, sinceEnd, targetTemp, eventID, online_id )
            # example data returned on the morning of an event:
            # ('Tuesday Night Service', False, 40061, '2', -46361)
            
            if todaysEvent!='' and settings['heating']!='OFF' :
                # find the current room temp of event room
                if str(room).find('1') < 0:
                    currentRoomTemp = fronTemp
                else:
                    currentRoomTemp = mainTemp
                #--------------------------------------------------------------------------------------
                #                   Calculate Switch-on Time
                #--------------------------------------------------------------------------------------
                # 1. get estimated amount by which the Temp increases per hour when heating is on,
                #       factoring in a slower increase for a colder outdoor temperature
                #       e.g., at 20ºC, the factor is 1.0 or 100%, at 0ºC, the factor is 0.8 or 80%
                #
                increasePerHour = round( (1.5 * (80 + float(outdoorTemp)) / 100), 2 )
                #
                # 2. estimated duration of pre-heating is (in hours)
                #       target temperature minus TARGET ROOM temp divided by increase/hour 
                #
                heatingDuration = round(  ( targetTemp - float(currentRoomTemp) ) / increasePerHour * 60 * 60  ) # to get seconds 
                #
                # 3. check if we are already in the heating phase
                #
                Logger.debug("Calculated values: (toStart - heatingDuration - currentRoomTemp) \n" + \
                                formatSeconds(toStart)+' - '+formatSeconds(heatingDuration)+' - '+str(currentRoomTemp) )

                # report estimated heating switch-on time to DB
                if toStart-heatingDuration>600 and sinceEnd < 0: 
                    reportEstimateOn( lclSQLcursor, toStart-heatingDuration, eventID, online_id )
                
                # if program was restarted, we do not know what the heating status is, so we have to check the TF switches!
                if boiler_on and heating_on: watch['heatingActive'] = True
                
                #-------------------------------------------------------------------------------------------------
                # if time to event start is shorter than pre-heating timespan , we need to switch heating on:
                #-------------------------------------------------------------------------------------------------
                if toStart < heatingDuration and sinceEnd < 0 and not boiler_on:
                    # we need to switch on heating !!
                    watch['heatingActive'] = True
                    notifyAll( 
                                "Trying to switch on heating for " + todaysEvent + \
                                ".\n (toStart, heatingDuration, sinceEnd) \n" + \
                                formatSeconds(toStart)+' - '+formatSeconds(heatingDuration)+' - '+formatSeconds(sinceEnd) + \
                                "\nCurrent room temp.: " + str(currentRoomTemp) + " Target room temp.: " + str(targetTemp)
                             )
                    switchHeating( lclSQLcursor, True, True, eventID, online_id )
                
                # if heating is already on but pre-heating timespan shorter than time until event starts, switch off heating...
                # (with a tolerance of 10 minutes!)
                if heating_on and toStart > (heatingDuration+1200) and sinceEnd < 0:
                    # we need to switch heating OFF !!
                    notifyAll( "Switch OFF heating as pre-heating timespan shorter than remaining time (toStart - heatingDuration - currentRoomTemp) "+\
                                formatSeconds(toStart)+' - '+formatSeconds(heatingDuration)+' - '+str(currentRoomTemp) )
                    if boiler_on:
                        if watch['eventHasStarted']:
                            # switch heating off, but leave boiler (hotwater) on, since event is already ongoing
                            switchHeating( lclSQLcursor, True, False, eventID, online_id )
                        else:
                            # switch everything off if event hasn't started yet
                            switchHeating( lclSQLcursor, False, False, eventID, online_id )
                    else:
                        switchHeating( lclSQLcursor, False, False, eventID, online_id )
                        watch['heatingActive'] = False
                
                # if event is ongoing and currentRoomTemp > targetTemp, switch off boiler!
                if watch['eventHasStarted'] and currentRoomTemp > targetTemp and heating_on:
                    notifyAll("Switching off boiler since event is ongoing and currentRoomTemp > targetTemp! " +
                                formatSeconds(toStart) + ' ' + str(currentRoomTemp) + ' ' + str(targetTemp) )
                    switchHeating( lclSQLcursor, True, False, eventID, online_id )
                
                # if event is ongoing and outdoorTemp > 17, switch off boiler!
                if watch['eventHasStarted'] and float(outdoorTemp) > 17 and heating_on:
                    notifyAll("Switching off boiler since outdoorTemp > 17! " +
                                formatSeconds(toStart) + ' ' + str(currentRoomTemp) + ' ' + str(outdoorTemp) )
                    switchHeating( lclSQLcursor, True, False, eventID, online_id )
                
                #--------------------------------------------------------------------------------------
                # switch boiler off 20 minutes after event ended
                #--------------------------------------------------------------------------------------
                if sinceEnd > 900 and boiler_on:
                    notifyAll(
                            "Trying to switch OFF heating for " + todaysEvent + \
                            "\n(sinceEnd, boiler on?" + formatSeconds(sinceEnd) + ' - ' + str(boiler_on) + \
                            ")\nCurrent room temp.: " + str(currentRoomTemp) + " Target room temp.: " + str(targetTemp)
                        )
                    switchHeating( lclSQLcursor, False, False, eventID, online_id)
                    watch['heatingActive'] = False
                    writeNextEventDate( lclSQLcursor, eventID, online_id )
                
            else:
                Logger.debug ("No event active now. (" + todaysEvent+' - '+str(watch['eventHasStarted'])+' - '+formatSeconds(toStart)+' - '+str(room)+' - '+formatSeconds(sinceEnd)+')')

            Logger.debug( "Event active? " + str(watch['eventHasStarted']) + ". In room: " + str(room) )
            Logger.debug(" ")
           

        #---------------------------------------------------------------------------------------------------
        # only every 60 seconds: check motion activity, check source code change or WOL request
        #---------------------------------------------------------------------------------------------------
        if count % 60 == 0:
                    
            # check if light was switched on triggered by the motion sensor
            # and if no event is active in room 1,
            # switch off the light if there was no motion in the last 5 mins
            if not watch['eventHasStarted'] or ( watch['eventHasStarted'] and str(room).find('1')<0 ):
                checkMotionActivity(tfLCD)
            
            # every minute check if we need to WOL AVROOM PC
            if onLinux and settings['source']=='remote' and settings['wol']: 
                print(settings)
                Logger.info("settings.xml contained instruction to WOL AVROOM")
                wake_on_lan( PC_MAC_ADDR )
                # reset wol field in DB to False
                #resetWOLinSettings( lclSQLcursor, remoteSQL )
                
            # check if debugging is requested
            if os.path.isfile('debug_off'):
                Logger.setLevel(logging.INFO) 
                
            # check if debugging is requested
            if os.path.isfile('debug_on'):
                Logger.setLevel(logging.DEBUG) 
                
            # check if the script source code has been changed meanwhile
            if ( scriptChangeDate != os.path.getmtime(__file__) ):
                    broadcast(__file__ + " Source code was changed - exiting script...")
                    exitCode=2
                    break
            if ( myFuncChangeDate != os.path.getmtime('libFunctions.py') ):
                    broadcast("libFunctions.py script was changed - exiting script...")
                    exitCode=2
                    break
       
        time.sleep(.95)             # wait 1 second
        count+=1                    # loop counter


    #---------------------------------------------------------------------------------------------------------
    # close all connections (HTTP, mySQL)
    #---------------------------------------------------------------------------------------------------------
    lclSQLcursor.close()
    #conn.close()
    tfConn.disconnect()
    httpSession.close()
    
    # END
    Logger.debug("Ending script gracefully ...")




Logger.info('Finished, exitCode is '+str(exitCode) )
# since program ends here, we can delete the PID file
os.remove( PIDfname )  
broadcast("Ending program with exit code " + str(exitCode) )
sys.exit(exitCode)
