#-------------------------------------------------
#
# - check for sundayservice recording 
# - make soundrecorder process have high prio in Windows
# - rename sound recording file and copy it into DropBox
# 
#-------------------------------------------------
#
# (c) 2015 M.KUHS
#
#-------------------------------------------------

#-------------------------------------------------
# (requires Python 3.x)
#-------------------------------------------------
#
# imports -
#
#
#-------------------------------------------------
import time
import signal
import sys
import glob
import psutil
import shutil
import os
import datetime


#------------------------------------------------------------------------
#                                   Logging 
#------------------------------------------------------------------------
import logging
#import logging.config
#logging.config.fileConfig('logging.conf')
global Logger
Logger = logging.getLogger("getPower.py")    # create logger obj with a name of this module
Logger.setLevel(logging.DEBUG) 

now = datetime.datetime.now()           # determine log file name
logDir = ".\Logfiles";
logName = "getPowerLog_"+str(now.timetuple().tm_yday)+'.txt';
if sys.platform == 'linux2':
    logDir = "./Logfiles";

file_log_handler = logging.FileHandler( (os.path.join(logDir, logName)) ) 
Logger.addHandler(file_log_handler)

stderr_log_handler = logging.StreamHandler()    # log to the console as well
Logger.addHandler(stderr_log_handler)

formatter = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s: %(message)s')
file_log_handler.setFormatter(formatter)
stderr_log_handler.setFormatter(formatter)

print('Started')



# my own functions
from libFunctions import *

    

#------------------------------------------------------------------------------------------------------
#                                       Constants
#------------------------------------------------------------------------------------------------------

ADMIN  = 'church.ennis@gmail.com'   # recipient of warning/error emails


# determine host os # ('win32' or 'linux2')
onWindows = False
onLinux   = False
if sys.platform == 'win32':
    onWindows = True
if sys.platform == 'linux2':
    onLinux   = True


# file that indicates that we're currently uploading a file via FTP
ftpUploadIndicator = "currentlyUploading.txt"
    
# Path containing the edited Sunday service recording file for upload via FTP
editedRecFilePath  = "Exchange\\Stuff for Uploading"

# sound recording file handling
soundRecordingRenamed        = False
soundRecordingFileUploadPath = '..\\Exchange\\Audio\\'
soundRecordingFile           = "C:\\DATA\\sunday.wma"

#------------------------------------------------------------------------
# get last modify date of this script
#------------------------------------------------------------------------
scriptChangeDate = os.path.getmtime(__file__)
myFuncChangeDate = os.path.getmtime('libFunctions.py')


#------------------------------------------------------------------------
# check if an argument was given (anything goes)
#   for a one-off run to return current power immediately
#------------------------------------------------------------------------
oneOff = False
if len(sys.argv) > 1:
    oneOff = True;


    
                        #===========================#
                        #    F U N C T I O N S      #
                        #===========================#

#-----------------------------------------------------------------------------------
# handle keyboard interrupts
#-----------------------------------------------------------------------------------
def signal_handler(signal, frame):
    print('You pressed Ctrl+C! Program gracefully ended.')
    sys.exit(0)
    
# configure the above function as the signal handler
signal.signal(signal.SIGINT, signal_handler)



#------------------------------------------------------------------------------------------------------
# Check if the SoundRecording process (on a Sunday) is running
#------------------------------------------------------------------------------------------------------
def checkSoundRecordingPrio():
    if not onWindows: return      # only on Windows!
    if not schTaskIsRunning("SundayServiceRec"):
        notifyAll("SoundRecorder was not running!" )
        cmd = "schtasks.exe /run /tn SundayServiceRec" 
        result = (subprocess.check_output(cmd)).decode('utf-8').splitlines()
        Logger.debug( str(result) )
    else:
        Logger.debug( "Soundrecorder was running..." )
        
    # set process priority to high
    for pid in getPID('soundrecorder'):
        p = psutil.Process( int( pid ) )
        if p.nice() < 128:
            p.nice( psutil.HIGH_PRIORITY_CLASS )


#------------------------------------------------------------------------------------------------------
# If the SoundRecording process has finished, rename the file and copy to DropBox
#------------------------------------------------------------------------------------------------------
def checkSoundRecordingFile():
    if not onWindows: return      # only on Windows!
    
    Logger.debug("Searching for " + soundRecordingFile)
    print("Searching for " + soundRecordingFile)
    
    if os.path.isfile( soundRecordingFile ):
        Logger.debug( soundRecordingFile + " found!" )
        newName = 'sunday_'+str(now.year)+'-'+str(now.month).rjust(2,'0')+'-'+str(now.day).rjust(2,'0')+'.wma'
        os.rename( soundRecordingFile, newName )
        soundRecordingRenamed = True
        # try copying file to Dropbox area
        Logger.info("Trying to copy " + newName + " to " + soundRecordingFileUploadPath)
        try:
            shutil.copy2(newName, soundRecordingFileUploadPath)
        except:
            Logger.exception("copy of "+ newName + ' to ' + soundRecordingFileUploadPath + 'failed!')
            notifyAll("copy of "+ newName + 'failed!')
    else: 
        Logger.debug('File not found: '+soundRecordingFile)
        return    # return if nothing was found
    


#------------------------------------------------------------------------------------------------------
# upload file via ftp
#------------------------------------------------------------------------------------------------------
def uploadFTP( file ):

    # check if file exists
    if ( not os.path.isfile(file) ):
        Logger.error("uloadFTP: file not found: " + file)
        return
    print("Beginning FTP upload background job with", file)
    
    curpath = os.getcwd()               # store current path
    fpath, fname = os.path.split(file)  # get path and name separated
    os.chdir(fpath)                     # change working dir to fpath
    tt = open(ftpUploadIndicator,'w')
    tt.write('currently uploading: '+fname)
    tt.close()
    
    # build ftp command set
    ftp = ftplib.FTP("ftp1.reg365.net")
    ftp.login("ennisevangelicalchurch.org", "Tha!land:01")
    ftp.cwd("web/jdownloads/")
    
    # work out host path according to file type and day of week
    filename, file_extension = os.path.splitext( file )
    if file_extension.lower() == '.mp3':
        ftp.cwd('Sermon Recordings')
        # presume type of file depending on day of week!
        now = datetime.datetime.now()
        if ( now.weekday() > 1 and now.weekday() < 6 ):
            if (filename.find("Judges")>0):
                hostPath = 'bible study teaching/Judges Series'
            else:
                hostPath = 'bible study teaching'
        else:   
            hostPath = 'sunday service teaching'
            if (filename.find("Ephesians")>0):
                hostPath = 'sunday service teaching/Ephesians Series'
            if (filename.find("Genesis")>0):
                hostPath = 'sunday service teaching/Genesis Series'
                
        ftp.cwd(hostPath)
        
    # Path for Newsletters
    if file_extension.lower() == '.pdf':
        ftp.cwd('Documents and Newsletters')
        ftp.cwd('Newsletter')
        hostPath = 'Newsletter'
        
    # rename local file to remove special characters
    os.rename(fname, fname.replace("'", " ") )
    fname = fname.replace("'", " ")
        
    print("About to send FTP upload command to ", hostPath)
    ftp.storbinary("STOR " + fname, open(fname, "rb"), 1024)
    ftpRC = ftp.lastresp    
    # to avoid continuous processing, if upload fails, rename the file in ANY case!
    os.rename(fname, fname+".uploaded" )
    # evaluate return code from upload
    if int(ftpRC) == 226: 
        print('File uploaded to FTP server: ' + file + ". RC:" + ftpRC)
        sendEmail([admin,'phil.pain@yahoo.co.uk'],'File uploaded to FTP server: ', file + "\nwas uploaded to " + hostPath + "\n RC:" + ftpRC)
    else:
        print('File upload to FTP server failed! File name: ' + file + ". Error code:" + ftpRC)
        sendEmail(admin,'File uploaded to FTP server failed!', file + '\nError: ' + ftpRC )
    ftp.quit()
    os.remove(ftpUploadIndicator)       # remove the temporary indicator file again
    os.chdir(curpath)           # go back to current working directory
    return        

    
#------------------------------------------------------------------------------------------------------
# Check if there is a file in the upload folder
# if yes, launch FTP upload in separate thread!
#------------------------------------------------------------------------------------------------------
def checkForRecordingFile():
    Logger.debug("Searching for mp3 files in", "..\\" + editedRecFilePath)
    print("Searching for mp3 files in", "..\\" + editedRecFilePath)
    files = glob.glob("..\\" + editedRecFilePath + "\\*.mp3")
    Logger.debug("Found: " + str(files))
    if len(files)==0: 
        Logger.debug('no mp3 files found in '+editedRecFilePath)
        return    # return if nothing was found
    if os.path.isfile("..\\" + editedRecFilePath + '\\' + ftpUploadIndicator):
        print( "Uploading still ongoing for file " + files[0] )
        return
    Logger.debug( "Found file for ftp upload: " + str(files) )    
    sendEmail( [admin,'phil.pain@yahoo.co.uk'], 'Beginning to upload to FTP server: ', str(files) )
    # use process to allow running the upload in the background
    p = Process(target=uploadFTP, args=(files[0],))
    p.start()
    p.join()
    return

    
        
#------------------------------------------------------------------------------------------------------
# Check if there is a PDF file in the upload folder
# if yes, launch FTP upload in separate thread!
#------------------------------------------------------------------------------------------------------
def checkForNewsletterFile():

    Logger.debug("Searching for pdf files in ..\\" + editedRecFilePath)
    print("Searching for pdf files in ..\\" + editedRecFilePath)
    files = glob.glob("..\\" + editedRecFilePath + "\\*.pdf")
    Logger.debug("Found " + str(files))
    
    if len(files)==0: 
        Logger.debug('no PDF files found in '+editedRecFilePath)
        return    # return if nothing was found
    if os.path.isfile("..\\" + editedRecFilePath + '\\' + ftpUploadIndicator):
        print( "Uploading still ongoing for file " + files[0] )
        return
    Logger.debug( "Found file for ftp upload: " + str(files) )    
    
    sendEmail( [admin,'phil.pain@yahoo.co.uk'], 'Beginning to upload to FTP server: ', str(files) )
    
    # use process to allow running the upload in the background
    p = Process(target=uploadFTP, args=(files[0],))
    p.start()
    p.join()
    return


#======================================================
#
#                   MAIN program
#
#======================================================



# some global variables
count  = 0;  # counter for the loop    


#----------------------------------
# endless loop
#----------------------------------
if __name__ == '__main__':

    while True:

        now = datetime.datetime.now()
        print('waiting... ' +  str(count))
        
        # this script should run only on a Sunday ...
        #if now.isoweekday() < 7: print("This script should only run on a Sunday..."); break
        
        # --------------------------------------------
        # do some maintenance "stuff" every 5 mins
        # --------------------------------------------
        #
        if (now.minute % 5 == 0 and now.second < 10)    or count == 0:
            print('checking files.... '+ str(now.hour) + ' ' + str(soundRecordingRenamed) )
            
            # on a Sunday morning, check if SoundRecorder is running
            if ( now.isoweekday() == 7 and now.hour > 10 and now.hour < 13 ): 
                print('checkSoundRecordingPrio}')
                checkSoundRecordingPrio()
            
            # on a Sunday morning, check if SoundRecorder is finished and rename file
            #if ( now.isoweekday() == 7 and now.hour > 12 and not soundRecordingRenamed): 
            if ( now.hour > 12 and not soundRecordingRenamed): 
                checkSoundRecordingFile()
                print('checkSoundRecordingFile')
                    
            
            # check for edited sound recording file for ftp upload
            if onWindows: 
                checkForRecordingFile()
                checkForNewsletterFile()
            
            Logger.debug("="*55)
            

        #---------------------------------------------------------------------------------------------------
        # only every 60 seconds, 
        # check if the script source code has been changed meanwhile
        if count % 60 == 0:
            print('checking for changed script' + str(scriptChangeDate))
            if ( scriptChangeDate != os.path.getmtime(__file__) ):
                    print("Source code was changed - exiting script...")
                    break
            if ( myFuncChangeDate != os.path.getmtime('libFunctions.py') ):
                    print("libFunctions.py script was changed - exiting script...")
                    break

        
        # wait 1 minute
        time.sleep(60)
        count+=1

    
    # END
    Logger.debug("Ending script gracefully ...")

print('Finished')
