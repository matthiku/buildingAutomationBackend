#!/bin/bash

# checkProc is the heartbeat of the buildingControl system
# it launches checkProc.py which monitors the running processes
#
# changelog
#
# 2015-01-07 - all output used to go to a logfile,
# but we'll try to use the piping in crontab instead


# last boot time
#echo "$(date +%Y-%m-%d_%H:%M:%S) - launching shell script ...."
#echo "--------------------------------------------------------------------------------"
#echo "Last$(who -b)"

if [ "$1" != "" ]; then
    echo "$(date +%Y-%m-%d_%H:%M:%S) - downloading latest shell scripts ..." 
	/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/shell/checkProc.sh /root/checkProc.sh 
	/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/shell/readSensors.sh /root/readSensors.sh 
	/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/shell/buildingControl.sh /root/buildingControl.sh 
    if [ "$1" == "updSh" ]; then exit
    fi
fi

if [ "$1" == "loop" ]; then
    # TODO: avoid endless reboot-loops
    echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - wait 600 secs to allow machine to settle ..."
    sleep 600
fi

cd /home/pi/Dropbox/BuildingControl/

if [ "$1" != "" ]; then
    echo "$(date +%Y-%m-%d_%H:%M:%S) - downloading latest version of checkProc.py ..." 
	/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/checkProc.py 
fi

while true; do
    # run python evaluation prog 
    #echo "$(date +%Y-%m-%d_%H:%M:%S) - launching Python"
    /opt/python3.3.2/bin/python3.3 checkProc.py $1 
    ret=$?
    #echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - RetCode from Python was: $ret"
    if [ $ret -ne 0 ]; then
        echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.py returned error, ending loop...." | wall -n
        # send email alert
        /opt/python3.3.2/bin/python3.3 myFunctions.py "church.ennis@gmail.com" "EEC RaspiTF1 is restarting" "checkProc.py has returned an error and the Linux machine will restart now. Check logfiles on Dropbox!"
        break
    fi
    if [ "$1" != "loop" ]; then
        # reboot required by python script
        break
    fi
    # upload logfiles to Dropbox
    echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - Uploading log files ...."
    /home/pi/Dropbox-Uploader/dropbox_uploader.sh upload /home/pi/Dropbox/BuildingControl/Logfiles /BuildingControl
    echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - waiting 2 minutes...."
    sleep 120
done

if [ "$1" == "test" ]; then 
    echo "test only"
    sleep 20
    exit
fi

# do this only for one-off calls to this script
# currently not needed ....
if [ "$1" == "" ]; then 
    exit $ret
    echo "=============================================================================================================================="
    echo -n "btH (main room) "
    tinkerforge call temperature-bricklet bTh get-temperature
    ret=$?
    if [ $ret -ne 0 ]; then echo "RC: $ret"
    fi
    echo -n "bSC (heat water) "
    tinkerforge call temperature-bricklet bSC get-temperature
    ret=$?
    if [ $ret -ne 0 ]; then echo "RC: $ret"
    fi
    echo -n "6Jm (front room) "
    tinkerforge call temperature-bricklet 6Jm get-temperature
    ret=$?
    if [ $ret -ne 0 ]; then echo "RC: $ret"
    fi
    echo "Dual Relay status:"
    tinkerforge call dual-relay-bricklet 6D9 get-state
    ret=$?
    if [ $ret -ne 0 ]; then echo "RC: $ret"
    fi
    echo "=============================================================================================================================="
    exit $ret
fi


# upload logfiles to Dropbox
echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - Uploading log files ...."
/home/pi/Dropbox-Uploader/dropbox_uploader.sh upload /home/pi/Dropbox/BuildingControl/Logfiles /BuildingControl > /dev/nul
#rm /home/pi/Dropbox/BuildingControl/Logfiles/*.txt  <- must have been done by python prog already!

# upload shell scripts to Dropbox
#echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - Uploading shell scripts ...."
#/home/pi/Dropbox-Uploader/dropbox_uploader.sh upload /root/*.sh /BuildingControl/shell



if [ "$ret" -ne 0 ] && [ "$1" == "loop" ]; then
    echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - RetCode $ret, rebooting machine ...."
    echo "$(date +%Y-%m-%d_%H:%M:%S) - checkProc.sh - RetCode $ret, rebooting machine ...." | wall -n
    /root/restart.sh
fi
