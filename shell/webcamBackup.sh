#!/bin/bash

sleep 60

# activate debugging either bei command line argument or if debug indicator file exists
if [ "$1" == "debug" ]; then
    debug="debug"
fi

while true; do
    if [ -f "debug_on" ]; then
        debug="debug"
    fi
    echo "Is debug on? $debug"
    
    # launch python prog
    /usr/bin/python3.2 webcamBackup.py $debug
    ret=$?
    echo "Retcode $ret"
    
    # only continue if return code is either 60 or 9
    if [ $ret -ne 60 -a $ret -ne 9 ]; then
        break
    fi
done

echo "readTFsensors return code was: $ret . Exiting ..."  | wall -n