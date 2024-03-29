#! /usr/local/bin/python
# -*- coding: utf-8 -*-  

import sys, os, traceback, logging
import subprocess, re, psutil
import pymysql

import datetime, time, calendar
import json
import random

import requests         # handling http (for weather data)
import telnetlib        # (for dovado router/home automation)

from tinkerforge.ip_connection            import IPConnection
from tinkerforge.bricklet_lcd_20x4        import LCD20x4
from tinkerforge.bricklet_motion_detector import MotionDetector
from tinkerforge.bricklet_dual_relay      import DualRelay
from tinkerforge.bricklet_temperature     import Temperature
from tinkerforge.bricklet_ambient_light   import AmbientLight

# to enable multiprocessing
from multiprocessing import Process

# for WOL
import socket, struct



# get access to the logger
Logger = logging.getLogger("buildingControl") 

# determine host OS ('win32' or 'linux2')
onWindows = False
onLinux   = False
if sys.platform     == 'win32':
    onWindows        = True
if sys.platform[:5] == 'linux':
    onLinux          = True



# mySQL database access
lclSqlSrv = 'localhost'
lqlSqlUsr = 'monitoring'
lclSqlPwd = 'monitoring'
lclSqlDB  = 'monitoring'

getNextCSpotEventURL = 'https://plan.eec.ie/api/plans/next'


# need to have this now, so that we can read the local settings table
def getMySQLconn( ):
    ''' create mySQL database connection '''
    try:
        mySqlConn = pymysql.connect(host=lclSqlSrv, port=3306, user=lqlSqlUsr, passwd=lclSqlPwd, db=lclSqlDB)
    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.info( 'Local mySQL connection failed ... ' + errmsg )
        sendEmail(admin,'BuildingControl.py', 'local mySQL connection failed ... ' + errmsg + ' ' +  e )
        # raise
        return -1
    # return the mySQL connection object
    return mySqlConn
lclConn = getMySQLconn()
lclSQLcursor = lclConn.cursor()

def executeSQL(mySQLdbCursorObj, sqlCmd, taskDescription="access" ):
    ''' execute local SQL command '''
    Logger.debug("Trying to execute sql command: "+sqlCmd)
    result=0
    try:
        result = mySQLdbCursorObj.execute( sqlCmd )
        if sqlCmd.split()[0] != "SELECT":
            mySQLdbCursorObj.execute("COMMIT; ")
    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.error( sqlCmd + "Unable to " + taskDescription + " local DB!" + errmsg  + " RESULT was: " + str(result) + ' Error: ' + str(e) )


# define method to read settings from local DB
def getLclSettings(lclSQLcursor):
    executeSQL( lclSQLcursor, "SELECT `key`,`value` FROM `settings`;" )
    allSettings = lclSQLcursor.fetchall()
    settings = {}
    for item in allSettings:
        settings[item[0]] = item[1]
    settings['source'] = "local"
    return settings

# define minimal defaults so that we can run locally without any DB
# settings = {
#   'TFheatSwUID'   : '6D9',
# }

# now read the settings
settings = getLclSettings( lclSQLcursor )



admin  = settings['adminEmail']
backupAdmin  = settings['backupAdmin']

# URL for power usage reading on the youless monitor
youLessURL    = settings['youLessURL']


# Tinkerforge default values
TF_HOST       = 'localhost'
TF_PORT       =  4223
TF_LCD_UID    = settings['TFLCDUID']      # 'cYL'
TF_MOTION_UID = settings['TFmotionSwUID'] # 'iSC'
TF_HEATSW_UID = settings['TFheatSwUID']   # '6D9'

# dovado router API to control lighting
DOV_HOST = "192.168.0.1"
DOV_PORT =  6435




''' Building API ---------------------------------------------------------- START
'''
# define global API access data
apiItems = {
    # access to remote building database
    'url'          : settings['buildingAPIurl'],
    'headers'      : {'Accept' : 'application/json'},
    'expire'       : 0,
    'accToken'     : '',
    'tokenRequest' : {
                        'password' : settings['buildingAPIclient_secret'],
                        'email'    : settings['buildingAPIclient_email'],
                     }
} 


''' write HTML code returned from failed API call in to a file '''
def writeErrorHtml(html):
    try:
        fname = os.path.join( 'Logfiles', 'APIerror.html' )
        fhandle = open(fname, 'w')
        fhandle.write(html)
        fhandle.close()
    except: return


''' Handle unexpected data returned from API call '''
def handleAPIerrors(requestsResult, activity):
    if (requestsResult.text)[:15] == "<!DOCTYPE html>": # API call returned a HTML page!
        writeErrorHtml(requestsResult.text)
    else:
        if   requestsResult.status_code  < 500: Logger.info( requestsResult.json() )
        else:                      Logger.info( requestsResult.text )
    Logger.error("Error when trying to " + activity + \
        " remote DB via RESTful API! Status code: "+str(requestsResult.status_code))


''' request a new access token from remote REST API 
    return access_token and expiration time in seconds
'''
def getToken():
    r = requests.post(apiItems['url']+'login', data=apiItems['tokenRequest'], headers=apiItems['headers'])
    print('\ngetToken, response: ', r)
    if r.status_code == 200:
        apiItems['accToken'] = r.json()['access_token']
        apiItems['headers']['Authorization'] = 'Bearer ' + r.json()['access_token']
        return r.json()['expires_in']
    else:
        print('\ngetToken problem, result: ', r.text, '\nStatus code:', r.status_code, '\n\n')


''' access token handling '''
def checkToken():    
    now = datetime.datetime.now().timestamp()
    if apiItems['expire'] == 0 or apiItems['expire'] == "None":
        print(apiItems)
    # check if token has expired
    if apiItems['expire'] and apiItems['expire'] - now < 1:
        # get access token first
        expires_in = getToken()
        # set new expiration date
        apiItems['expire'] = expires_in
    else:
        print('*** checkToken failed! ***')
        print(apiItems)


def updateSettingsStatus():
    #/settings/status/OK
    checkToken()
    # payload = { 'access_token' : apiItems['accToken']  }
    r = requests.patch( apiItems['url']+'settings/status/OK', headers=apiItems['headers'] )
    if not r.status_code == 202: # 201=new record created
        handleAPIerrors(r, "update settings status on")
        return
    print( "\nSettings STATUS was updated to OK. API call Result: " + str(r.json()) )


''' get configuration settings '''
def getSettings( lclSQLcursor ):

    # first read the online settings table
    checkToken()
    r = requests.get( apiItems['url']+'settings', headers=apiItems['headers'] )
    # r = requests.get( apiItems['url']+'settings?access_token='+apiItems['accToken'] )
    # check the return code
    if not r.status_code == 200:
        handleAPIerrors(r, "read settings table from")
        # since online settngs are unavailable, fall back to local settings backup
        print("\nremote settings query failed!\n")
        return getLclSettings(lclSQLcursor)

    # returned data is in JSON format
    rmtSettings = r.json()['data']
    # create new dict object with all settings as key/value pair
    settings = {}
    for item in rmtSettings:
        settings[item['key']] = str(item['value'])

    # now check if the remote settings contain a valid PIN
    lclSettings = getLclSettings(lclSQLcursor)
    settingsTAN = str(lclSettings['seed'])

    # remote update requested with valid TAN?
    if settings['seed'] == settingsTAN and settings['status'] == 'UPDATE':
        # - set remote status back to OK
        updateSettingsStatus()
        # - update local settings
        updateLclSettings(lclSQLcursor, lclSettings, settings)
        settings['source'] = "remote"
        return settings
    
    if settings['status'] == 'UPDATE' and not settings['seed'] == settingsTAN:     # invalid remote TAN ...
        print("\nremote settings not accepted, wrong TAN:", settings['seed'] ,"Should be:", settingsTAN, '\n')

    return getLclSettings(lclSQLcursor)     # ignore remote settings


''' get online event table '''
def getApiEvents():
    r = requests.get(apiItems['url']+'events', headers=apiItems['headers'])
    if not r.status_code == 200:
        Logger.exception('Unable to read events table from remote DB via RESTful API!')
        return
    # returned data is in JSON format labelled 'data'
    return r.json()['data'] 


''' write PowerLog data into remote DB via buildingAPI '''
def writeApiPowerLog( watts, boiler_on, heating_on, tstamp ):
    # set token expiration time to now, so that 
    # we have to request a new token immediately for the buildingAPI
    checkToken()
    payload = { # create payload data as dict for buildingAPI
        'power'        : watts,
        'boiler_on'    : 1 if boiler_on  else 0,
        'heating_on'   : 1 if heating_on else 0,
        'updated_at'   : tstamp.strftime("%Y-%m-%d %H:%M:%S"),
        'access_token' : apiItems['accToken']  }
    r = requests.post(apiItems['url']+'powerlog', data=payload, headers=apiItems['headers'])
    if not r.status_code == 201: # (201=new record created)
        handleAPIerrors(r, "write power data to")

''' write TempLog data into remote DB via buildingAPI '''
def writeApiTempLog( outdoorTemp, mainTemp, fronTemp, heatTemp, watts, heating_on ):
    checkToken()
    payload = { # create payload data as dict for buildingAPI
        'mainroom'     : mainTemp,
        'auxtemp'      : heatTemp,
        'frontroom'    : fronTemp,
        'outdoor'      : outdoorTemp,
        'heating_on'   : '1' if heating_on else '0',
        'power'        : watts,
        'access_token' : apiItems['accToken']  }
    r = requests.post(apiItems['url']+'templog', data=payload, headers=apiItems['headers'])
    if not r.status_code == 201: # 201=new record created
        print('\noutdoorTemp, mainTemp, fronTemp, heatTemp, watts, heating_on', outdoorTemp, mainTemp, fronTemp, heatTemp, watts, heating_on)
        handleAPIerrors(r, "write tempLog data t")


''' write BuildingLog data into remote DB via buildingAPI '''
def writeApiBuildingLog( what, where, text ):
    checkToken()
    payload = { # create payload data as dict for buildingAPI
        'what'         : what,
        'where'        : where,
        'text'         : text,
        'access_token' : apiItems['accToken']  }
    r = requests.post(apiItems['url']+'buildinglog', data=payload, headers=apiItems['headers'])
    if not r.status_code == 201: # 201=new record created
        handleAPIerrors(r, "write buildingLog data to")


def writeApiEventLog( id, estOn='00:00', actOn='00:00', actOff='00:00' ):
    checkToken()
    Logger.info("Code writeApiEventLog, data received: " + \
                str(id) + " " + str(estOn) + " " + str(actOn) + " " + str(actOff))
    payload = { # create payload data as dict for buildingAPI
            'event_id'     : id,
            'estimateOn'   : estOn[:5],
            'actualOn'     : actOn[:5],
            'actualOff'    : actOff[:5],
            'access_token' : apiItems['accToken']
        }
    # send HTTP POST request to API
    r = requests.post(
            apiItems['url'] + 'eventlog',
            data=payload,
            headers=apiItems['headers']
        )
    if not r.status_code == 201: # 201=new record created
        handleAPIerrors(r, "write eventLog data to")


''' set nextdate of a certain event (once an event is over) '''
def writeApiEventNextdate( id, nextdate ):
    checkToken()
    print("# "*90)
    payload = { 'access_token' : apiItems['accToken']  }
    r = requests.patch( apiItems['url']+'events/'+str(id)+'/nextdate/'+nextdate, data=payload, headers=apiItems['headers'] )
    print('writeApiEventNextdate - result: ', r.text, '\n')
    if not r.status_code == 202: # 202= record updated
        handleAPIerrors(r, "write event nextdate via")


''' update status of a certain event (after changes were made) '''
def updateApiEventStatus( id, status ):
    checkToken()
    payload = { 'access_token' : apiItems['accToken']  }
    r = requests.patch( apiItems['url']+'events/'+str(id)+'/status/'+status, data=payload, headers=apiItems['headers'] )
    if not r.status_code == 202: # 201=new record created
        handleAPIerrors(r, "update event status via")
        return
    Logger.info( "Event with id " + str(id) + " was updated to status " + status + ". API call Result: " + str(r.json()) )

''' ------------------------------------------------------------------------------- End Building API
'''




''' -------------  generic helper functions  ----------------'''
def formatSeconds( secs, long=True ):
    ''' convert seconds (int or str) into NNhNNmNNs or NNmNNs or NNs (string) depending on amount of seconds '''
    try:
        secs = int(secs)
    except:
        return secs
    # handling negatives
    minus = ''
    if secs < 0: 
        minus = '-'
        secs = abs(secs)
    # formatting depends on amount of seconds
    if secs < 90:
        if long: return (minus + str(secs)+'s').rjust(10)
        return '00:01'
    if secs < 3600:
        if long: return (minus + str(secs//60)+'m'+('0'+str(secs%60))[-2:]+'s').rjust(10)
        return '00:'+str(secs//60)
    if long: return (minus + str(secs//3600)+'h'+('0'+str(secs%3600//60))[-2:]+'m'+('0'+str(secs%60))[-2:]+'s').rjust(10)
    return str(secs//3600)+':'+('0'+str(secs%3600//60))[-2:]


def hilite( string, color='none', bold=False ):
    ''' highlight text (but only if on a TTY device and not a file) '''
    if not sys.stdout.isatty() or sys.platform == 'win32': return str(string)
    attr = []
    if color == 'green' : attr.append('32')
    if color == 'yellow': attr.append('33')
    if color == 'red':    attr.append('31')
    if color == 'blue':   attr.append('34')
    if bold:              attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), str(string))
 

def cjust( string, length ):
    ''' return a centered string of the given length padded with spaces on both sides '''
    pass
   

def maxList( list, newElem, max ):
    list.append(newElem)
    if len(list) > max:
        list.reverse()
        list.pop()
        list.reverse()
    return list


def getListAvg( list ):
    return round( sum(list) / len(list) )


def rnd5( n ):
    return round(n*10/5)*5/10


def getTmStmp():
    ''' creates human-readable date (today) followed by the timestamp '''
    now = datetime.datetime.now()
    tms = now.strftime("%Y-%m-%d %H:%M:%S")
    return str(tms) + " " + str(round( datetime.datetime.timestamp( now )) )


def add_month(date):
    '''add one month to date, maybe falling to last day of month

    :param datetime.datetime date: the date

    ::
      >>> add_month(datetime(2014,1,31))
      datetime.datetime(2014, 2, 28, 0, 0)
      >>> add_month(datetime(2014,12,30))
      datetime.datetime(2015, 1, 30, 0, 0)
    '''
    # number of days this month
    month_days = calendar.monthrange(date.year, date.month)[1]
    candidate = date + datetime.timedelta(days=month_days)
    # but maybe we are a month too far
    if candidate.day != date.day:
        # go to last day of next month,
        # by getting one day before begin of candidate month
        return candidate.replace(day=1) - datetime.timedelta(days=1)
    else:
        return candidate




''' -------------  inner environment sensing  --------------------- '''
def computerOnline( name ):
    ''' Check if a computer is online (using ping) '''
    if sys.platform[:5] == 'linux':
        cmd = "ping "+name+" -c2"
    else:
        cmd = "ping "+name
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    # Interact with process: 
    #   Send data to stdin
    #   Read data from stdout and stderr, until end-of-file is reached
    #   Wait for process to terminate
    #   The optional input argument should be a string to be sent to the child process, or None, if no data should be sent to the child
    # Talk with date command i.e. read data from stdout and stderr. Store this info in tuple
    p.communicate()
    # Wait for date to terminate. Get return returncode
    p_status = p.wait()
    # check return code
    if p_status == 0: 
        return True
    return False
  

def wake_on_lan( macaddress ):
    """ Wake on LAN 
    Switches on remote computers using WOL. """
    # Check mac address format and try to compensate.
    if len(macaddress) == 12:
        pass
    elif len(macaddress) == 12 + 5:
        sep = macaddress[2]
        macaddress = macaddress.replace(sep, '')
    else:
        Logger.error('WOL: Incorrect MAC address format ' + macaddress)
 
   # Pad the synchronization stream.
    data = b'FFFFFFFFFFFF' + (macaddress * 20).encode()
    send_data = b'' 

    # Split up the hex values and pack.
    for i in range(0, len(data), 2):
        send_data += struct.pack( 'B', int(data[i: i + 2], 16) )

    # Broadcast it to the LAN.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    result = sock.sendto(send_data, ('<broadcast>', 7))    
    Logger.info('WOL - Result from trying to wake_on_Lan %s was %s.' %(macaddress, str(result),) )


def getPID( name ):
    #
    # returns an array of pids (or an empty array) 
    # of all tasks whose name matches name (case insensitive!)
    #
    tasklist = os.popen("tasklist").readlines()
    # a line in tasklist looks like:
    # chrome.exe                    8340 Console                    1     42,252 K
    name = name.lower()
    pids = []
    ok = False
    for task in tasklist:
        words = task.split()
        if (len(words) == 8 and words[0] == 'Image'):
            ok = True
            continue
        if not ok: continue
        procName = words[0].lower()
        if procName.find(name) >= 0:
            pids.append( words[1] )
    return pids


def schTaskIsRunning( name ):
    ''' Check if a certain scheduled task is running '''
    # only works on Windows
    if sys.platform != 'win32': return False
    
    cmd = "schtasks.exe /query /tn " + name
    try:
        result = (subprocess.check_output(cmd)).splitlines()
    except subprocess.CalledProcessError:
        return False

    for line in result:
        last =  line.decode('utf-8')
    #Logger.info(name + " is " + last.split()[-1])
    if last.split()[-1] == "Running":
        return True
    return False


def isRunning( procName ):
    ''' check if a certain program (process) is running
        input:  process name or parts thereof
        output: True or False
    '''
    # procList = [psutil.Process(i) for i in psutil.get_pid_list()]
    for proc in psutil.process_iter(attrs=['pid', 'name', 'username']):
        try:
            if procName in proc.info['name']: return True
        except psutil.AccessDenied: pass
    return False


def get_processes_running( processname ):
    ''' return the number of processes that are running with the given name '''
    processname = processname.upper()
    processList = subprocess.check_output(['tasklist']).splitlines()
    isRunning = 0
    for fields in processList:
        if len(fields) > 2:
            line = fields.decode(encoding='UTF-8', errors='ignore').split()
            if line[0].upper().find(processname) >= 0:
                print('\n', processname + " is running - " + " ".join(line) )
                isRunning += 1
    if isRunning > 0:
        print(str(isRunning) + " instance(s) of " + processname + " are running!\n" )
    else:
        print(processname + " is NOT running!\n" )
    return isRunning


def internet_on():
    import urllib
    url='http://google.com'
    request = urllib.request.Request(url)
    try:
        urllib.request.urlopen(request,timeout=1)    
        return True
    except: pass
    Logger.error("=== No connection to the Internet! ===")
    return False




''' ----------------  external notifications  ------------------ '''
def sendEmail( destination, subject, content ):

    # don't try this if we are offline
    if not internet_on(): return
    
    SMTPserver = 'smtp.gmail.com'
    sender =     'raspitf1@gmail.com'

    USERNAME = "raspitf1"
    PASSWORD = "Jesuslovesme!316"

    # typical values for text_subtype are plain, html, xml
    text_subtype = 'plain'

    from smtplib import SMTP_SSL as SMTP       # this invokes the secure SMTP protocol (port 465, uses SSL)
    # from smtplib import SMTP                  # use this for standard SMTP protocol   (port 25, no encryption)
    from email.mime.text import MIMEText

    try:
        msg = MIMEText(content, text_subtype)
        msg['Subject']= subject
        msg['From']   = sender # some SMTP servers will do this automatically, not all

        conn = SMTP(SMTPserver)
        conn.set_debuglevel(False)
        conn.login(USERNAME, PASSWORD)
        try:
            conn.sendmail(sender, destination, msg.as_string())
        finally:
            conn.close()

    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.info( "error when trying to send email: " + errmsg + ' Exception: ' + e )
        sys.exit( "mail failed; %s" + errmsg ) # give a error message


def broadcast( text ):
    ''' Broadast messages to other terminals '''
    now = datetime.datetime.now()
    lines = str(text).splitlines() 
    text = now.strftime("%Y-%m-%d %H:%M:%S") + ' - ' + __file__ + "\n" + lines[0]
    if onLinux: subprocess.call('echo "' + text + '"| wall -n', shell=True )
    # print('\nbroadcast - result', text, '\n')
    index = 1
    while index < len(lines):
        if onLinux: subprocess.call('echo "' + lines[index] + '"| wall -n', shell=True )
        print(lines[index])
        index += 1


def notifyAll( text, subject="Building Control Notification" ):
    ''' notify via logger, terminal and email '''
    Logger.info(text)
    broadcast(text)
    sendEmail([admin, backupAdmin], subject, text)





''' ----------------------  manage TINKERFORGE objects  ------------------------ '''
def getTFconn( HOST=TF_HOST, PORT=TF_PORT ):
    try:
        ipcon = IPConnection()
    except  Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.info( 'Tinkerforge IPConnection failed ... ' + errmsg )
        sendEmail(admin,'getPower.py', 'Tinkerforge IPConnection failed ... ' + errmsg + ' Exception: ' + e )
        sys.exit(-1) # should cause rPi to reboot
    try:
        ipcon.connect(HOST, PORT)
    except  Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.info( 'Tinkerforge unable to connect! ' + errmsg )
        sendEmail(admin,'getPower.py', 'Tinkerforge unable to connect! ' + errmsg + ' Exception: ' + e )
        sys.exit(-1) # should cause rPi to reboot
    return ipcon

def getTFLCD( ipcon, UID=TF_LCD_UID ):
    try:
        lcd = LCD20x4(UID, ipcon)
    except  Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.info( 'Tinkerforge LCD object creation failed ... ' + errmsg )
        sendEmail(admin,'getPower.py', 'Tinkerforge LCD object creation failed ... ' + errmsg + ' Exception: ' + e )
    return lcd

def getMotion( ipcon, UID=TF_MOTION_UID ):
    try:
        md = MotionDetector(UID, ipcon)
    except  Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.info( 'Tinkerforge MotionDetector object creation failed ... ' + errmsg )
        sendEmail(admin,'getPower.py', 'Tinkerforge MotionDetector object creation failed ... ' + errmsg + ' Exception: ' + e )
    return md

def getTFsensors( ipcon, UID,type='TEMP' ):
    result = ''
    try:
        if type == "TEMP":
            result = Temperature(UID, ipcon) # Create device object
            # use result.get_temperature()/100.0

        if type == "LUX":
            result = AmbientLight(UID, ipcon) # Create device object
            # use result.get_illuminance()/10.0
    except:
        Logger.exception( "Error! UID '" + UID + "' might be wrong! " + sys.exc_info()[0] ) 
    if result == '':
        Logger.Warning( "Error! Wrong TYPE parameter for getTFsensors function - " + type ) 
    return result




''' ---------------------- physical environment sensing ---------------- '''
def getLastTempHumid():
    ''' 
    read last line of /var/www/th.log.txt 
    containing the last reading of the temp/humid sensor that is connected to the RaspBerryPi 
    '''
    timestampNow = round( datetime.datetime.timestamp( datetime.datetime.now() ))
    try:
        thlog = open("/var/www/th.log.txt").read().splitlines()
    except:
        Logger.exception("getLastTempHumid: Unable to read /var/www/th.log.txt")
        return timestampNow, 9.9
        
    # read last line of logfile
    lineNo = -1
    try:
        words = thlog[lineNo].split()
    except:
        Logger.exception("getLastTempHumid: Failure when trying to read /var/www/th.log.txt")
        return timestampNow, 9.9
        
    # check if we have a complete line
    if len(words)<6:    # sometimes the line is not complete
        lineNo -= 1
        words = thlog[lineNo].split()
        
    # check if we have a valid reading
    # NORMAL: 2015-03-28 11:50:00  Temp:  14.7, RH:  63.0%
    # FAILED: 2015-03-28 11:38:00  Temp:  29.2, RH: 126.6%
    # loop max 9 times until we have a proper reading:
    humid = words[-1].split("%")
    while True:
        Logger.debug("getLastTempHumid: " + str(lineNo) + ' - ' + str(words))
        if abs(lineNo) >= len(thlog):    # we have run out of data in the file ...
            Logger.error("Unable to extract tempHumid data! Source: " + str(thlog) )
            return timestampNow, 9.9
        if len(humid) > 1 and ( lineNo < -9 or ( float(humid[0]) < 100 and humid[1] == "" ) ):
            break
        lineNo -= 1
        words = thlog[lineNo].split()
        humid = words[-1].split("%")
    
    try:
        readingTimestamp = datetime.datetime.strptime(words[-6]+'-'+words[-5],"%Y-%m-%d-%H:%M:%S").timestamp()
        return  readingTimestamp, words[-3].split(',')[0] # remove trailing comma!
    except:
        return timestampNow, 9.9


def getCurrentPower( httpSession ):
    ''' Get current POWER consumption
    read the WATT value from the YouLess device's webpage '''
    val=0
    try:
        response = httpSession.get( youLessURL, timeout=3 )
    except:
        return 0
    try:
        data = json.loads(response.text)
        val = data.get('pwr', -1)
    except:
        Logger.exception( "Cannot get or decode %s: %s" % (youLessURL) )
    return val


def checkHeatingStatus( ipcon, UID=TF_HEATSW_UID, writeLog=False ):
    ''' Check if heating has been switched on at the moment '''
    try:
        dr = DualRelay(UID, ipcon) # Create device object
        status = dr.get_state()
    except:
        Logger.exception("Failed to read switch status!")
        return (False,False)
    # return the current status (2 values!) as a list
    stat0,stat1='0','0'
    if status[0]: stat0='1' 
    if status[1]: stat1='1' 
    if writeLog:  open("./Logfiles/DRstatus.log","w").write( stat0+', '+stat1+" updated "+getTmStmp() )
    return ( status[0], status[1] )


def getWeather(getAll=False):
    ''' cget current outdoor temp '''
    try:
        r = requests.get('http://api.openweathermap.org/data/2.5/weather?q=Ennis,IE&APPID=639b476cc699eca2112cbccd5944f282', timeout=4)
        if not r.ok or len(r.content) < 400:
            return 99.5
    except:
        return 99.4
    try:
        temp = r.json()['main']['temp']-273.15 
    except:
        return 99.3
    # print only 2 decimal digits
    temp = "{0:.1f}".format(round(temp*10/5)*5/10) 
    if getAll:
        getAll = r.json()
        return temp, getAll['wind']['speed'], getAll['wind']['deg']
    return temp 





''' ------------------------------ AUTOMATION Actions ----------------------- '''
def switchHeating( mySQLdbCursorObj, sw1, sw2, eventID, online_id, UID=TF_HEATSW_UID, writeLog=True ):
    ''' Switch Heating on or Off and report via mySQL '''
    ipcon = getTFconn()
    try:
        dr = DualRelay(UID, ipcon) # Create device object
        isSw1, isSw2 = dr.get_state()
    except:
        Logger.exception("Unable to read switch status!")
        return
        
    now = datetime.datetime.now()
    if isSw1 == sw1 and isSw2 == sw2:
        Logger.debug("switchHeating: No change! " + str(sw1) +','+ str(sw2) )
        return
    try:
        dr.set_state(sw1, sw2)
        Logger.info( "Changed switch to " + str(sw1) + ", " + str(sw2) )
    except Exception as e:
        Logger.exception("Unable to CHANGE switch status! " + e)
        return
        
    # report into mySQL. Example:
    # INSERT INTO `heating_logbook` (`timestamp`, `eventID`, `eventStart`, `estimateOn`, `actualOn`, `actualOff`) VALUES (CURRENT_TIMESTAMP, '', '', '', '14:38:00', '');
    sqlCmd = "INSERT INTO heating_logbook (`eventID`, `actualOn`, `actualOff`)  VALUES ('" + str(eventID) + "', "
    actualOn = actualOff = '00:00'
    if sw1 == True:     actualOn = now.strftime( "%H:%M" )
    else:              actualOff = now.strftime( "%H:%M" )
    sqlCmd+= "'" + actualOn + "', '" + actualOff + "'); "

    # execute SQL remote and local
    executeSQL( mySQLdbCursorObj, sqlCmd, 'write heating switching time into' )  # local
    #if eventID==0: return   # heating control is on manual, so no event id involved
    # and remote
    writeApiEventLog( online_id, actOn=actualOn, actOff=actualOff )   


def controlLights( mySQLdbCursorObj, which, onOrOff ):
    ''' Control Lights via Dovado Router Web console '''
    user = b'admin'
    pwrd = b'jesusislord316'
    tnResult=''
    try:
        tn = telnetlib.Telnet(DOV_HOST,DOV_PORT)
        tn.read_until(b">> ")
        tn.write(b'user ' + user + b"\n")
        tn.read_until(b">> ")
        tn.write(b'pass ' + pwrd + b"\n")
        tn.read_until(b">> ")
        which = which.split(',')
        for w in which:
            tn.write(b"ts turn "+w.encode('utf-8')+b' '+onOrOff.encode('utf-8')+b"\n")
            tn.read_until(b">> ")
        tn.write(b"exit\n")
        tnResult = tn.read_all().decode("utf-8")
    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        print (e)
        Logger.error("Error when trying to telnet with Dovado Router for Light control! " + errmsg + ' Exception: ' + str(e) )
        return
    #if not 'bye' in tnResult:
    print('\nwhich, onOrOff, tnResult', which, onOrOff, tnResult)
    Logger.info("RESULT FROM controlLights "+str(which)+' '+onOrOff+": "+tnResult)
        
    #  log this into local DB building_logbook
    sql = "INSERT INTO `building_logbook` () VALUES ( NOW(), 'light', 'main', '"+onOrOff+"' )"
    executeSQL( mySQLdbCursorObj, sql, 'protocol light-switching into' )

    #  log data into remote DB via buildingAPI
    writeApiBuildingLog('light', 'main', onOrOff)




''' ========================== LOCAL DATABASE activity ========================= '''

def getCurrentTAN( mySQLdbCursorObj ):
    ''' extract current TAN (or seed code) from events DB '''
    try:
        result    = mySQLdbCursorObj.execute("SELECT `seed` FROM `building_events` ORDER BY `timestamp` DESC LIMIT 1; " )
        if result!=1: 
            Logger.error("getCurrentEvents - Unable to read local DB!" + str(result) )
            return
    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.error("getCurrentEvents - Unable to open/read local DB!" + errmsg + ' Exception: ' + e )
        return
    return mySQLdbCursorObj.fetchone()[0]


def checkCurrentEvent( mySQLdbCursorObj ):
    ''' 
    Check if an event is currently active 
        input:  mySql cursor object
        output: (tuple) eventName, isActive (bool), secondsToStart (can be negative if after the event), sinceEnd, targetTemp
    '''
    now = datetime.datetime.now()
    evtActive = False
    try:
        # execute SQL query using the current mySQL connection
        # we need to get earlier events on the same day first => ORDER BY start
        mySQLdbCursorObj.execute("SELECT * FROM `building_events` WHERE `status`='OK' ORDER BY `start` ; " )
        # should return:
        #   0   1          2          3       4     5        6      7    8      9        10        11     12   
        #   id	timestamp  online_id  status  seed  weekday  start  end  title  repeats  nextdate  rooms  targetTemp
    except:
        Logger.exception('Unable to read events table from DB!')
        return '', False, 0, 0, 0, 0
    # evaluate the returned data
    for r in mySQLdbCursorObj.fetchall():
        #print( r )
        # if this is a weekly event and today is this event's weekday
        # or this is a one-off event and today is the date
        #    then we have an event today!
        if  r[5]  == now.strftime("%A") and r[9] == 'weekly' \
        or  r[10] == datetime.date(now.year, now.month, now.day) :
                eventID    = r[0]
                online_id  = r[2]
                eventName  = r[8]
                eventStart = r[6]
                eventEnd   = r[7]
                room       = r[11]
                targetTemp = r[12]
                Logger.debug( "Today's event **"+ eventName + "** starts at "+ str(eventStart)+" and ends at " + str(eventEnd) )
                toStart = eventStart.seconds - (now.hour * 60 * 60 + now.minute * 60 + now.second)
                sinceEnd = (now.hour * 60 * 60 + now.minute * 60 + now.second) - eventEnd.seconds
                #if toStart  > 0:    print( "event starts in " + formatSeconds( toStart ) )
                # event is "active" from 30 mins before start until 30 mins after the end
                if toStart  < 1800: evtActive = True
                if sinceEnd > 1800: evtActive = False
                
                # return values only up to 30 mins after end of event
                if sinceEnd < 1800:
                    return eventName, evtActive, toStart, room, sinceEnd, targetTemp, eventID, online_id
    
    return '', False, 0, 0, 0, 0, 0, 0

def getNextCspotEvent():
    try:
        # get next event as data object via c-SPOT API
        r = requests.get(getNextCSpotEventURL, timeout=4)
        # problems with http request?
        if not r.ok or len(r.content) < 500: 
            return '', False, 0, 0, 0, 0, 0, 0
    except:
        return '', False, 0, 0, 0, 0, 0, 0

    now = datetime.datetime.now()
    event = r.json()
    eventID = event['id']
    online_id = int(event['id'])
    eventName = event['type']['name']
    # if it's a generic event type, the actual name is the subtitle
    if event['type']['generic'] == 1:
        eventName = event['subtitle']
    eventStart = datetime.datetime.fromisoformat(event['date'])
    evtActive = False
    # we only care about events in Main Room or Front Room!
    room = 0
    roomName = event['resources'][0]['name']
    if roomName == "Main Room":
        room = 1
    if roomName == "Front Room":
        room = 2

    if room != 0 and eventStart.date() == now.date():
        eventEnd = datetime.datetime.fromisoformat(event['date_end'])
        targetTemp = 21
        Logger.debug( "Today's event **"+ eventName + "** starts at "+ str(eventStart)+" and ends at " + str(eventEnd) )

        # how many seconds until start of event resp. end of event?
        toStart = ((eventStart.hour*60 + eventStart.minute) - (now.hour * 60 + now.minute)) * 60
        sinceEnd = ((now.hour * 60 + now.minute) - (eventEnd.hour * 60 + eventEnd.minute)) * 60
        
        # event is "active" from 30 mins before start until 30 mins after the end
        if toStart  < 1800: evtActive = True
        if sinceEnd > 1800: evtActive = False

        # return values only up to 30 mins after end of event
        if sinceEnd < 1800:
            return eventName, evtActive, toStart, room, sinceEnd, targetTemp, eventID, online_id

    return '', False, 0, 0, 0, 0, 0, 0

def writeNextEventDate( mySQLdbCursorObj, eventID, online_id ):
    '''once an event is over, this function writes the next event date into the local and remote DBs'''
    # get event details:
    #   select * from DB where event_id = eventID
    sqlCmd = "SELECT * FROM `building_events` WHERE `id`=" + str(eventID)
    try:
        result = mySQLdbCursorObj.execute( sqlCmd )
        if result!=1: 
            Logger.error("writeNextEventDate - Unable to read local DB!" + str(result) )
            return
    except Exception as e:
        errmsg = str(traceback.format_exception( *sys.exc_info() ))
        Logger.error("writeNextEventDate - Unable to open/read local DB!" + errmsg + ' Exception: ' + e )
        return
    evtData = mySQLdbCursorObj.fetchone()
    # calculate next event date according to repeat pattern
    #   if repeat = weekly:     nextEventDate = today +  7 days
    #   if repeat = biweekly:   nextEventDate = today + 14 days
    #   if repeat = monthly:    nextEventDate = today +  1 month (might have to be manually corrected ...)
    repeat = evtData[9]
    if repeat == 'once': return     # no need to calculate next date ...
    
    today = datetime.date.today()
    if repeat == 'weekly':   
        diff = datetime.timedelta( days = 7 )
        nextEventDate = (today + diff).strftime("%Y-%m-%d")
    if repeat == 'biweekly': 
        diff = datetime.timedelta( days =14 )
        nextEventDate = (today + diff).strftime("%Y-%m-%d")
    if repeat == 'monthly':  
        nextEventDate = add_month(today)
    
    # write next event date
    sqlCmd = "UPDATE `building_events` SET `nextdate`='"+str(nextEventDate)+"' WHERE `status`='OK' AND `id`=" + str(eventID)
    executeSQL( mySQLdbCursorObj, sqlCmd, "write next event date into" )
    # also write remotely via API
    #writeApiEventNextdate( online_id, str(nextEventDate) ) ## DISABLED as we use c-SPOT data now (2018-11-20)
    return


def resetWOLinSettings( mySQLdbCursorObj ):
    '''  after a forced WOL, reset wol field in settings table  '''
    try:
        mySQLdbCursorObj.execute( "UPDATE `settings` SET `wol`='0' WHERE `id`=0" )
    except:
        Logger.exception('Unable to reset WOL to 0 in settings table from DB!')
        return 1
    Logger.info("WOL setting was resetted.")


def insertNewEvent( mySQLdbCursorObj, ev, newTAN ):

    # for updates, change the status of the existing event to "OLD"
    if ev['status']  in  [ 'UPDATE', 'DELETE' ]:
        sqlCMD = "UPDATE `building_events` set `status`='OLD' where `online_id`='"+ev['id']+"';"
        executeSQL( mySQLdbCursorObj, sqlCMD )
 
    # insert the update as a new event
    sql = "INSERT INTO `building_events` ( "
    sql+= "`status`,`online_id`,`seed`,`weekday`,`start`,`end`,`title`,`repeats`,`nextdate`,`rooms`,`targetTemp`) VALUES ( 'OK', '"
    sql+= str(ev['id']) + "', '"
    sql+= str(ev['seed']) + "', '"
    sql+= ev['weekday'] + "', '"
    sql+= ev['start'] + "', '"
    sql+= ev['end'] + "', '"
    sql+= ev['title'] + "', '"
    sql+= ev['repeats'] + "', '"
    sql+= ev['nextdate'] + "', '"
    sql+= ev['rooms'] + "', '"
    sql+= str(ev['targetTemp']) + "' );"
    executeSQL( mySQLdbCursorObj, sql, "insert new/updated event into" )
    Logger.info("New event inserted locally: " + str(ev))

    # create a new TAN number (seed) and populate the local DB table with it
    sqlCMD = "UPDATE `building_events` SET `seed`=" + str(newTAN) + "; "
    executeSQL( mySQLdbCursorObj, sqlCMD, "write new TAN into" )


def reportEstimateOn( mySQLdbCursorObj, timeDiff, eventID, online_id ):
    ''' report estimated heating switch-on time to DB '''
    # first check if the new estimation is way different to the previous one
    mySQLdbCursorObj.execute('SELECT * FROM `heating_logbook` ORDER BY timestamp DESC LIMIT 1')
    oldData = mySQLdbCursorObj.fetchone() 

    # calculate estimated switch-on time and timediff from now
    try:
        now        = datetime.datetime.now()
        estimateOn = now + datetime.timedelta(seconds=timeDiff)
        estOn      = estimateOn.strftime("%H:%M")

        # do nothing if last recording was less than 10 minutes ago
        diff       = abs( estimateOn.second + estimateOn.minute*60 + estimateOn.hour * 60 * 60 - oldData[3].seconds )
        if str(oldData[1]) == str(eventID) and diff < 600: return    
    except:
        print("\nERROR when trying to calculate estimate on", timeDiff, oldData, estimateOn, estOn)

    # write it into local DB table
    sql = "INSERT INTO heating_logbook (`eventID`, `estimateOn`)  VALUES ('"+str(eventID) + "', '" + estOn + "');"
    print('\nreportEstimateOn = SQL code: \n', sql, '\n')
    executeSQL( mySQLdbCursorObj, sql, 'write estimated switch-on time into' )
    # write into remote DB table via API
    writeApiEventLog( online_id, estOn=estOn )


def updateLclSettings( lclSQLcursor, lclSettings, rmtSettings ):

    dirty = False

    for key in rmtSettings:
        if key in ('status', 'seed'): continue    # no need to copy these keys locally
        try: 
            # the following will throw a keyError if the key doesn't exist locally yet
            if not rmtSettings[key] == lclSettings[key]: 
                # remote value is different, so update this locally
                sql = "UPDATE `settings` SET `value`='" +str(rmtSettings[key])+ "' WHERE `key`='" +key+ "'; "
                executeSQL( lclSQLcursor, sql, "update local settings with online value for key: " + str(key) )
                print( "\nSuccessfully updated local settings with online value for key: " + str(key) )
                dirty = True

        except KeyError: 
            # key does not yet exist in the local DB, so we insert it:
            sql = "INSERT INTO `settings`( `value`, `key`) VALUES ( '" +str(rmtSettings[key])+ "', '" +key+ "' ); "
            executeSQL( lclSQLcursor, sql, "update local settings with NEW online value for key: "+str(key) )
            print( "\nSuccessfully updated local settings with NEW online value for key: "+str(key) )
            dirty = True

    if dirty:
        # - generate new random TAN number for local DB
        newSeed = str(random.randint(10000,99999))
        sql = "UPDATE `settings` SET `value`='" +newSeed+ "' WHERE `key`='seed'; "
        executeSQL( lclSQLcursor, sql, "update local settings with online value for key: " + str(key) )
        print("\nRemote settings accepted! New seed:", newSeed, '\n' )
        sendEmail(admin, 'Building Control Program Settings Updated', "new TAN is " + newSeed)
    else:
        print('\nRemote settings update requested, but no changes found!\n')



''' ----------------- when called from the command line ----------------- '''
if __name__ == "__main__":

    # send email when receiving 3 parameters
    # destination, subject, content
    if len(sys.argv) == 4:
        sendEmail(sys.argv[1], sys.argv[2], sys.argv[3])

    # with just 1 parameter, it should be a MAC address to send WOL packets to
    if len(sys.argv) == 2:
        print("\nTrying to wake-on-LAN for:", sys.argv[1], '\n')
        wake_on_lan(sys.argv[1])
