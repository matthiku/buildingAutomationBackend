#!/usr/bin/env python3
# -*- coding: utf-8 -*-  

#===============================================================================+
#                           checkProc.py                                        |
#-------------------------------------------------------------------------------+
#                                                                               |
# PURPOSE:  heartbeat process to ensure smooth running of the scripts           |
#           buildingControl.py and readTFsensors.py                             |
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
# (1)   (modified on 08-JAN-2015, see changelog!)                               |
#       Before this python script is called, a shell script (cron job)          |
#       creates a short log file containing the currently running               |
#       PYTHON scripts as well as the last entries in the logbook that          |
#       shows when those scripts were started. (Location same as this script)   |
#       Currently, there should always 2 Python scripts be running:             |
#           1) buildingControl.py (power logging, motion control, event control)|
#           2) readTFsensors.py (temp sensor reading+logging to local SQL DB)   |
#       If one of the two is not running:                                       |
#           ==> REBOOT machine                                                  |
# (2)   readTFsensors.py creates small logfiles each time it receives a new     |
#       value from one of the sensors. Using the timestamp in those logfiles,   |
#       we determine the time that passed since the sensor was sending data.    |
#       If the average passed time of all sensors not sending data exceeds      |
#       a defined amount of seconds:                                            |
#           ==> REBOOT machine                                                  |
# (3)   Lastly, we check how long ago a successful read of the power usage was. |
#       Currently, there is NO ACTION on this.                                  |
#                                                                               |
# (4)   Midnight log-files clean-up (see change-log below)                      |
#                                                                               |
#===============================================================================+
# CHANGELOG                                                                     |
#                                                                               |
# 08-JAN-2015 Step 1 above has changed:                                         |
#             Now python handles all the data collection previsously done       |
#             in the shell script that called this python program:              |
#             # get list running python procs:  pgrep 'pyth' > checkProc.txt    |
#             # show last reported PIDs:                                        |
#             grep  'readTFsensors.py started'  $evalfile | tail -1 >>checkPr...|  
#             grep 'buildingControl.py started' $evalfile | tail -1 >>checkPr...|      
#                                                                               |
# 09-JAN-2015 Adding   MIDNIGHT CLEANUP   functionality: (new STEP 4)           |
#             ALL log FILES are sync'd to Dropbox                               |
#             BEFORE midnight, all 'txt' files are moved to the respective      |
#             day-of-the-year subfolder and yesterday's subfolder is deleted.   |
#             Also, throughout the program, error messages are                  |
#             broadcasted as well es printed                                    |
#                                                                               |
# 10-JAN-2015 Instead of a blunt restart of the Raspi, we now work with a       |
#             penalty points system - for each problem some points are awarded. |
#             Once a certain amount of points are reached, the reboot is due.   |
#             However, if all sensors are doing fine, the points go back to 0.  |
#                                                                               |
# 15-JAN-2015 Improved broadcast function (adding timestamp and file name)      |
#                                                                               |
# 16-JAN-2015 Checks own file date to discover source code changes (=> restart) |
#                                                                               |
# 17-JAN-2015 Before initiating the REBOOT, we try one last time to read the    |
#             sensors and if one of them responds, we reset the warning counter |
#                                                                               |
# 18-JAN-2015 Before initiating the REBOOT due to a missing Python program      |
#             (buildingControl.py and readTFsensors.py), we wait 30 secs and    |
#             check one more time - because the could just restart itself due   |
#             to a source code change                                           |
#                                                                               |
# 20-JAN-2015 Reading events table to see if an event is on today               |
#                                                                               |
# 25-FEB-2015 Reading last line of /var/www/th.log.txt containing temp/humid    |
#             sensor readings                                                   |
#                                                                               |
# 15-MAR-2015 Display more event details                                        |
#             display times in hh:mm:ss instead of just seconds                 |
#                                                                               |
# 30-MAR-2015 Streamlining output, removing excess lines                        |
#                                                                               |
# 01-APR-2015 outsourcing getLastTempHumid to libFunctions                       |
#             as it's also used by buildingControl.py                           |
#                                                                               |
# 14-APR-2015 a) improving TTY output with colours and better formatting        |
#             b) outsourcing getMySQLconn                                       |
#                                                                               |
# 27-APR-2015 add option to request current PIN (TAN) from events database      |
#                                                                               |
# 26-MAY-2015 getting power data directly from the web interface of the reader  |
#                                                                               |
# 28-MAY-2015 since values from sensors are only read when they change, we      |
#             need to make the verification more adaptive                       |
#                                                                               |
#===============================================================================+

#import pymysql
import requests
import datetime
import time
import sys
import os
import socket
import traceback
import subprocess
import shutil

from libFunctions import checkCurrentEvent
from libFunctions import getCurrentPower
from libFunctions import getMySQLconn
from libFunctions import getWeather
from libFunctions import formatSeconds
from libFunctions import hilite
from libFunctions import getLastTempHumid
from libFunctions import getCurrentTAN

# determine host os # ('win32' or 'linux2')
onWindows = False
onLinux   = False
if sys.platform == 'win32':
    onWindows = True
if sys.platform == 'linux2':
    onLinux   = True

LogFileDir = '/home/pi/Dropbox/BuildingControl/Logfiles/'
thisDir    = '/home/pi/Dropbox/BuildingControl/'
if onWindows:
    thisDir    = os.getcwd()
    LogFileDir = os.getcwd() + '\\Logfiles'
    

# maximun time in seconds the average delay/no response time of all sensors will be tolerated
maxDelay=1200
# maximum number of warning points before action is taken
# (warning points are collected when sensors keep sending the same value)
maxWarning=350


#------------------------------------------------------------------------
# get last modify date of this script
#------------------------------------------------------------------------
scriptChangeDate = os.path.getmtime(__file__)


oneoff = True

# Broadast messages to other terminals
def broadcast(text):
    now = datetime.datetime.now()
    text = now.strftime("%Y-%m-%d %H:%M:%S")+' - '+__file__+' - '+text
    print(text)
    if oneoff or onWindows: return   # no broadcast needed when this was run manually (ie in a terminal)
    subprocess.call('echo "'+str(text)+'"| wall -n', shell=True )

# returns a string with date, time and timestamp
def getTmStmp():
    now = datetime.datetime.now()
    tms = now.strftime("%Y-%m-%d %H:%M:%S")
    return str(tms) + " " + str(round( datetime.datetime.timestamp( now )) )

def checkSourceUpdate():
    # check if script source code has changed#
    os.chdir(thisDir)
    newScrChgDate = os.path.getmtime(__file__)
    os.chdir(LogFileDir)
    if ( scriptChangeDate != newScrChgDate ):
        broadcast( "Source code changed, (ending script). Old: "+str(scriptChangeDate) + ", New: " + str(newScrChgDate) )
        sys.exit(0)


#------------------------------------------------------------------------------------------------------
# check if an event is planned for today 
#------------------------------------------------------------------------------------------------------
def getTodaysEvent():
    # connect to the (local) mySQL DB on the Raspi
    print('-'*95)
    conn  = getMySQLconn()
    if conn==-1: 
        print("Unable to get mySQL connection!")
        return
    cur = conn.cursor()        
    # get power and switch status data
    eventName, evtActive, toStart, room, sinceEnd, targetTemp, eventID, online_id = checkCurrentEvent(cur)
    if not eventName=='':
        print( "        eventName         | evtActive |    toStart | room |   sinceEnd | targetTemp | eventID" )
        print( hilite( ( 
                         eventName.center(25)+' | '+str(evtActive).center(9)+' | '+formatSeconds( toStart ) + ' |  '+
                          str(room).center(3)+' | '+formatSeconds(sinceEnd) +' | '+str(targetTemp).center(10)+' | ' + str(eventID).center(7) 
                       ), 'green' ) )
    else:
        print("No scheduled event today.")
    
    print('-'*95)
    
    lclConn  = getMySQLconn()
    localSQL = lclConn.cursor()      
    if not localSQL==1:
        # get last event data
        localSQL.execute('SELECT * FROM `heating_logbook` ORDER BY timestamp DESC LIMIT 1')
        data = localSQL.fetchone() 
        try:
            text  = "Heating activity: " 
            if data[0].date() == datetime.date.today():
                text += hilite( 'today at '+data[0].strftime("%H:%M"), 'none', True ) 
            else:
                text += 'on ' + hilite( data[0].strftime("%A, %Y-%m-%d %H:%M"), 'none', True ) 
            if data[3].seconds > 0:
                text += hilite(" Estimate on: ",'none', True) + hilite( formatSeconds(data[3].seconds, False), 'green' )
            if data[4].seconds > 0:
                text += hilite(" Actual on: ",  'none', True) + hilite( formatSeconds(data[4].seconds, False), 'green' )
            if data[5].seconds > 0:
                text += hilite(" Actual off: ", 'none', True) + hilite( formatSeconds(data[5].seconds, False), 'green' )
            print(text)
        except:
            print(data)
    # close all open ends
    localSQL.close     # sql cursor
    lclConn.close      # sql connection     

    if oneoff: 
        print('-' * 75)
        print( "Current Event DB TAN is:", hilite( getCurrentTAN(localSQL), 'none', True ) )
    
    print('-'*75, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") )

#------------------------------------------------------------------------------------------------------
# get values and datetime of latest reading of power and dual relay switch 
#------------------------------------------------------------------------------------------------------
def printPwrAndSWdata():
    now = datetime.datetime.now()
    print( '-'*75,now.strftime("%Y-%m-%d %H:%M:%S") )
    
    # connect to the (local) mySQL DB on the Raspi
    #lclConn  = getMySQLconn()
    #localSQL = lclConn.cursor()        
    # get power and switch status data
    #localSQL.execute('SELECT * FROM `building_power` ORDER BY datetime DESC LIMIT 1')
    #data = localSQL.fetchone() 
    # close all open ends
    #localSQL.close     # sql cursor
    #lclConn.close      # sql connection        
    now = datetime.datetime.now()
    timestamp = round( datetime.datetime.timestamp( now )) 
    #print("DATA:", data)
    #lastReading = data[1].timestamp()
    httpSession = requests.Session()    # create the httpSession object
    data        = getCurrentPower( httpSession )     # get the initial reading    
    #print("timestamp, lastReading", timestamp, lastReading)
    #age = round(timestamp - lastReading) 
    age = 2 # since it's a live request
    color = 'green'
    if age > 150: color = 'yellow'
    if age > 450: color = 'red'
    agetext = ", last update " + hilite(formatSeconds( age ),color) + " ago"
    #power = round(data[2])
    power = data
    color = 'green'
    if power > 300: color = 'yellow'
    if power > 500: color = 'red'
    print( "    Power:", hilite(str(power).rjust(5),'none',True) + agetext ) 
    
    # now get DR status
    timestamp = round( datetime.datetime.timestamp( now )) 
    try: 
        line = open('DRstatus.log').read().split()
    except:
        broadcast("Unable to determine RD switches status - error when trying to open or read DRstatus.log!")
        broadcast(line)
        return 20, False
    if len(line)>0:
        age = timestamp - int(line[len(line)-1]) 
        color = 'green'
        if age > 150: color = 'yellow'
        if age > 450: color = 'red'
        agetext = hilite(formatSeconds( age ), color)
        color = 'green'
        if line[0]==1: 
            color = 'red'
            if line[1]==0: color = 'yellow'
        print( "DualRelay: ", hilite( (str(line[0])+' '+str(line[1])),color), ' last update', agetext, 'ago' )
    else:
        broadcast(" WARNING! Unable to determine RD switches status - DRstatus.log content is: "+str(line) )
        return 10, False
    return 0, line[0]

#------------------------------------------------------------------------------------------------------
# get values and datetime of latest reading of temperature sensors 
#------------------------------------------------------------------------------------------------------
def printSensorLogFiles():
    now = datetime.datetime.now()
    timestamp = round( datetime.datetime.timestamp( now )) 
    
    # read all logfiles (filenames must containt 'temp')
    files = os.listdir()
    ages,nr,oneGood = 0,0,False
    for fi in files:
        if fi[:4]=='temp':
            line = open(fi).read().split()
            if len(line)>5:     # we seem to have a valid content
                age = timestamp-int(line[5]) 
                color = 'green'
                if age < 599: oneGood=True       # if we have one good reading, TF is still working!
                else: color = 'yellow'
                ages+=age
                nr  +=1
                agetext = "last update " + hilite(formatSeconds(age),color) + " ago" 
                fname = fi.split('.')[0].rjust(9) + ":" 
                print( fname, hilite(line[0].rjust(6),'none',True), agetext )
            else:
                broadcast( 'Sensor Logfile was empty! ' + str(fi) + ', ' + str(line) )
    if onWindows: return 0
    
    # get babyroom temp
    #bts, babyTemp = getLastTempHumid()
    #age = timestamp-bts
    #color = 'green'
    #if age > 50: color = 'yellow'
    #if age > 150: color = 'red'
    #print( " Babyroom: ", (hilite(babyTemp,'none',True)+',').rjust(7), "last update", hilite(formatSeconds(age),color), "ago" )
    
    print( '-'*75 )

    # restart rPi if no new data since 'maxDelay' (on avg)
    if nr == 0: 
        broadcast(" No sensor logfiles found! REBOOT!")
        return 199    # ===> REBOOT!
    if not oneGood and ages/nr > maxDelay: 
        broadcast(" WARNING! Sensor logfiles found on average more than "+str(round(maxDelay/60))+" minutes old!")
        return 20
    if oneGood: return 0
    # return a "warning" if there was not one recent reading
    return 3



#------------------------------------------------------------------------------------------------------
# at midnight, all logfiles are synced to Dropbox and this program should end 
#------------------------------------------------------------------------------------------------------
def midnightCleanUp():
    now = datetime.datetime.now()
    # return if we are not shortly before midnight yet
    if now.hour < 23 or now.minute < 57: return
    
    doy = now.strftime("%j")     #day-of-year in 3-digits format (001-365)
    # no action if directory already exists!
    if os.path.isdir(doy): return
    
    broadcast("starting midnight cleanup .... " + doy)
    
    if onLinux:
        # ALL FILES are sync'd to Dropbox
        # /home/pi/Dropbox-Uploader/dropbox_uploader.sh upload /home/pi/Dropbox/BuildingControl/Logfiles /BuildingControl
        cmd = "/home/pi/Dropbox-Uploader/dropbox_uploader.sh upload " + LogFileDir + " /BuildingControl"
        subprocess.call(cmd, shell=True)
    
    # delete DOY subfolder of yesterday!
    yesterDOY=datetime.date.fromordinal(datetime.date.today().toordinal()-1).strftime("%j")
    if os.path.isdir(yesterDOY):
        shutil.move('./'+yesterDOY,'/tmp/' )     # we simply move the files to the tmp folder
    
    # All 'txt' files are moved to the current day-of-the-year subfolder.                                           
    filelist = os.listdir(".")
    os.mkdir(doy)
    for files in filelist:
        if files.endswith(".txt"):
            shutil.move(files,doy)
            
    broadcast("midnight cleanup finished ....")
    sys.exit(0) # now make a clean exit, shell script will restart me!

#------------------------------------------------------------------------------------------------------
# helper function to read log-files of each BM python program to get it's startup time and PID
#------------------------------------------------------------------------------------------------------
def getPyProgs():
    # read the content of all files named PID_<anything>.log
    #
    timestamp = round( datetime.datetime.timestamp( datetime.datetime.now() )) 
    pyProgs = {}        # create new dict
    files = os.listdir()        # get list of all files in Logfiles directory
    for fi in files:
        if fi[:4]=='PID_':      # only read "PID_*"-files
            line = open(fi).read().split()
            if len(line)>5:
                pid = line[1]
                age = timestamp-int(line[5]) 
                fname = fi.split('.')[0].split("_")[1]
                pyProgs[pid]=(fname,age)    # add to dict
            else:
                print("ERROR! - ",line)
    return pyProgs    

def getWinTasklist():
    tasks = subprocess.check_output("tasklist /NH", shell=True).decode("utf-8").splitlines()
    pids = []
    for task in tasks:
        if "python" in task: pids.append(task.split()[1])
    return pids

#------------------------------------------------------------------------------------------------------
# display PID and start time of each BM python program 
#------------------------------------------------------------------------------------------------------
def checkPythonProgs(retry=False):
    print('-'*95)
    # 1. get the PIDs of all Python processes
    if onLinux:
        pids = subprocess.check_output("pgrep pyth", shell=True).decode("utf-8").splitlines()
    else:
        pids = getWinTasklist()
    # 2. get the start time of Python processes from their log files
    pythonProgs = getPyProgs()
    okProgs=0
    for pid in pids: 
        if pid in pythonProgs and pid != myPID:
            print(pythonProgs[pid][0].rjust(16),'started',formatSeconds(pythonProgs[pid][1]).rjust(9)+' ago, PID is', pid)
            okProgs+=1
        if not pid in pythonProgs and pid != myPID:
            print( "running:", pids )
            print( "expected:", pythonProgs )
            print( "myPid:", myPID )
            print( "Failing to identify this python process! - ", pid )
            if onLinux:
                print( subprocess.check_output("ps axf | grep python", shell=True).decode("utf-8") )
    if oneoff: return           # stop here for one-off (manual) call 
    # Now test if exactly 2 other Python progs are running,
    # but give them another chance (e.g. while they are restarting itself due to source code change)
    if not okProgs==2:
        if not retry:
            print("first try pids:", pids)
            broadcast("Missing Python progs! Checking again in 60s.")
            time.sleep(60)
            checkPythonProgs(True)
            return
        print('-'*75, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") )
        print( pids )
        broadcast("Missing Python progs! Reboot required.")
        sys.exit(1)             # causes a REBOOT!

#------------------------------------------------------------------------------------------------------
# if one of the sensors is still replying, delay the reboot procedure
#------------------------------------------------------------------------------------------------------
def tempCheck():
    broadcast("making a direct temp check ....")
    try:
        answer = subprocess.check_output(['/root/getTemps.sh test'])
        broadcast("TempCheck proofed that all is good: " + answer)
        return True
    except:
        broadcast("TempCheck: no sensor replied !")
        return False






#===================================================================================================================
# Main progam (loop)
#===================================================================================================================
if __name__ == "__main__":

        
    if len(sys.argv)>1 and sys.argv[1] == 'loop':
        oneoff = False

    if len(sys.argv)>1 and sys.argv[1] == 'getTAN': 
        print( "Current TAN is:", getTAN() )
        sys.exit(0)

        
    myPID = str(os.getpid())
    # write PID to pid log file
    if not oneoff:
        PIDfname = os.path.join( LogFileDir, "PID_"+os.path.basename(__file__)+".log" )
        open( PIDfname, "w" ).write( "PID "+myPID+" started "+getTmStmp() )
        broadcast("- my PID is " + myPID)

    
    curPath=os.getcwd()     # save current path
    os.chdir(LogFileDir)    # go to logfiles dir
    # get current status of heating
    points, heating_on = printPwrAndSWdata()
    oldHeatingStatus = heating_on
    
    warning = 0     # counter for reading warnings

    
    while True:

        now = datetime.datetime.now()

        
        #---------------------------------------------
        # get the latest power and DR switch data
        #---------------------------------------------
        if not oneoff:
            points, heating_on = printPwrAndSWdata()
            
            # check if there was a change in the heating switch status
            if not oldHeatingStatus == heating_on:
                broadcast("Heating was now switched " + 'on' if heating_on else 'off' )
                oldHeatingStatus = heating_on


        #--------------------------------------------------------------------------------
        # read content to sensor log files (one line, containing the latest reading)
        #--------------------------------------------------------------------------------
        points += printSensorLogFiles()
        
        
        # we need to find a system were we can reset the warning counter
        # otherwise it would grow endlessly into negative value if everything is fine for a long time ....
        if points==0:       # all tests are good,
            warning=0       # warning counter goes back to 0
        else:                   # any problems and
            warning += points   # points are added to warning counter



        #---------------------------------------------
        # check the running Python processes
        #---------------------------------------------
        checkPythonProgs()



        #---------------------------------------------
        # is there an event today?
        #---------------------------------------------
        getTodaysEvent()



        #---------------------------------------------
        # that's it for manual running of this tool
        #---------------------------------------------
        if oneoff:      sys.exit(0)


        
        #---------------------------------------------
        # check warning counter
        #---------------------------------------------
        if warning>80:
            broadcast(" Current warning count is "+str(warning) )
        if warning > maxWarning: 
            if tempCheck():      # last chance, check the temp values directly
                warning = 0      # reset warning counter if at least one TF call was OK
            else:
                broadcast(" - reboot due to high warning count: " + str(warning) )
                sys.exit(1)



        # check if its source code was updated while the program is running
        checkSourceUpdate()


        #---------------------------------------------------------
        # at midnight, do some cleanup and roll-up of log files
        #---------------------------------------------------------
        midnightCleanUp()
        
        time.sleep(300)              # wait 5 minutes


        
    os.chdir(curPath)       # back to current directory
    print('-'*75)

# since program ends here, we can delete the PID file
os.remove( PIDfname )  
