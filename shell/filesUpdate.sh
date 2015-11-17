#!/bin/bash

# updating main shell scripts and python modules

echo "$(date +%Y-%m-%d_%H:%M:%S) - downloading latest shell scripts ..." 
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/shell/checkProc.sh /root/checkProc.sh 
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/shell/readSensors.sh /root/readSensors.sh 
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/shell/buildingControl.sh /root/buildingControl.sh 

cd /home/pi/Dropbox/BuildingControl/

/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/myFunctions.py 
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/checkProc.py 
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/buildingControl.py 
/home/pi/Dropbox-Uploader/dropbox_uploader.sh download /BuildingControl/readTFSensors.py 

echo "$(date +%Y-%m-%d_%H:%M:%S) - download finished ..." 
