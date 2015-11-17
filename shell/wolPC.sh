#!/bin/bash
echo "------------------------------------------------------------ "

#ping -c 2 192.168.0.140

cd /home/pi/Dropbox/BuildingControl/


ping 192.168.0.209 -c 2

# AVROOM pc
/opt/python3.3.2/bin/python3.3 myFunctions.py '00-19-B9-10-C5-98'

ping 192.168.0.209 -c 2


#leorobbie-tec 
#/opt/python3.3.2/bin/python3.3 myFunctions.py 'F4-6D-04-92-B5-5F'

#sleep 60

#ping -c 5 192.168.0.140
