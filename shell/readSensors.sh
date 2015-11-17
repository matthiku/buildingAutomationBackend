#!/bin/bash

#changelog
# 2015-01-07 - removed piping (is done in crontab now!)

cd /home/pi/Dropbox/BuildingControl/

# update the source code first
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/readTFsensors.py

# give mySQL db time to settle
sleep 30

# activate debugging either bei command line argument or if debug indicator file exists
if [ "$1" == "debug" ]; then
    debug="debug"
fi

# write the script's MD4 sum to the logfile
#md5=($(md5sum  readTFsensors.py))
#echo "MD5 hash value of readTFsensors.py: "$md5 >> "/home/pi/Dropbox/BuildingControl/Logfiles/errorlog_${doy}.txt"

while true; do
    if [ -f "debug_on" ]; then
        debug="debug"
    fi
    echo "Is debug on? $debug"
    
    # launch python prog
    /opt/python3.3.2/bin/python3.3 readTFsensors.py $debug
    ret=$?
    echo "Retcode $ret"
    # only continue if return code is either 60 or 9
    if [ $ret -ne 60 -a $ret -ne 9 ]; then
        break
    fi
    echo "readTFsensors return code was: $ret . Restarting now."  | wall -n
done

echo "readTFsensors return code was: $ret . Exiting ..."  | wall -n