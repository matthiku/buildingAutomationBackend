#!/bin/bash
#
# Launch building monitoring and control program
#
# Normally, this script is called on reboot by a cron job
#

cd /home/pi/Dropbox/BuildingControl/

# get latest file versions
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/buildingControl.py
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/myFunctions.py

# if called manually with debug parameter
if [ "$1" == "debug" ]; then
	echo 'debug only'
	# kill all other python instances
	ps -A | grep 'python'
	pkill python3
	ps -A | grep 'python'
	# launch python prog
	/opt/python3.3.2/bin/python3.3 buildingControl.py "debug"
	ret=$?
	echo "Return code is $ret"
	exit $ret
fi


# endless loop until return code not 2
while true; do
    if [ -f "debug_on" ]; then
        debug="debug"
    fi
    echo "Is debug on? $debug"
    
    # launch python prog
    /opt/python3.3.2/bin/python3.3 buildingControl.py $debug
    ret=$?
    echo "Retcode $ret"
    if [ $ret -ne 2 ]; then
        break
    fi
    echo "buildingControl.py return code was: $ret - restarting in 5 secs!" | wall -n
    sleep 5
    # if return code was 2, the source code has changed and must be re-loaded 
    # MKS 2015-03-31 but not via Dropbox, as the code is already on the Raspi!
    #/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/buildingControl.py
    #/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/myFunctions.py
    # now python process will start again
done

echo 'buildingControl.py exit code is  ' $ret | wall -n

if [ $ret -eq 255 ]; then
	echo "buildingControl.sh: RC was 255, emailing alert and rebooting rPi" | wall
	/root/restart.sh
	#/etc/init.d/brickd restart
	/opt/python3.3.2/bin/python3.3 myFunctions.py 'matthiku@gmail.com' 'building control script stopped prematurely' 'TF sensors unreadable - rebooting Raspi'
fi

