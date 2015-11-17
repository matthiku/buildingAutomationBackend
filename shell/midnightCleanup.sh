#!/bin/bash
#
# activities at midnight to clean up logfiles etc
#


# upload all logfiles to Dropbox
#/home/pi/Dropbox-Uploader/dropbox_uploader.sh upload /home/pi/Dropbox/BuildingControl/Logfiles /BuildingControl 

#
cd /home/pi/Dropbox/BuildingControl/Logfiles/


# now move all TXT files to temp folder as backup
#mv *.txt /tmp

# create a new subdir in Logfiles with the name of the Day of Year
#doy="$(date +%j)"
#mkdir /home/pi/Dropbox/BuildingControl/Logfiles/$doy
