'''
Will make sure that me buddy program will be restarted once it fails or has ended.
'''

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time
from datetime import datetime

# in order to later check if my source file has been changed (so that I can gracefully stop!)
thisDir = os.getenv("HOMEPATH") + '\\DropBox\\BuildingControl\\'
thisDir = os.getcwd()
# Get the modification time of the file in seconds since epoch
# my_source_last_modification_time = os.path.getmtime(file_path)
now = datetime.now()


# ------------------------------------------------------------------------
# get last modify date of this script
# ------------------------------------------------------------------------
scriptChangeDate = os.path.getmtime(__file__)



# ------------------------------------------------------------------------------------------------------
# check if my own source has been changed!
# ------------------------------------------------------------------------------------------------------
def checkSourceUpdate(oldDate):
    '''check if script source code has changed'''
    os.chdir(thisDir)
    newScrChgDate = os.path.getmtime(__file__)
    # os.chdir(LogFileDir)
    if scriptChangeDate != newScrChgDate:
        print("Source code changed, (ending script). Old: " +
                  str(scriptChangeDate) + ", New: " + str(newScrChgDate))
        sys.exit(0)

def checkIsMyBuddyStillRunning():
    '''
        checks if my buddy called 'nextEvent' is still there
    '''
    print(now.strftime("%H:%M:%S"))


def getWinTasklist():
    tasks = subprocess.check_output(
        "tasklist /NH", shell=True).decode("utf-8").splitlines()
    pids = []
    for task in tasks:
        if "python" in task:
            pids.append(task.split()[1])
    return pids

if __name__ == "__main__":

    now = datetime.now()

    while True:

        checkIsMyBuddyStillRunning()
        
        time.sleep(10)

        checkSourceUpdate(scriptChangeDate)

        now = datetime.now()
