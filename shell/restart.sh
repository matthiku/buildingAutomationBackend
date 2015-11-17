# controlled restarting of machine

date >>"/home/pi/Dropbox/BuildingControl/Logfiles/rebootlog.txt"
echo "rebooting machine ...">>"/home/pi/Dropbox/BuildingControl/Logfiles/rebootlog.txt"

echo waiting 30 seconds
echo "Rebooting in 30 seconds!" | wall
sleep 30
sudo reboot

date >>"/home/pi/Dropbox/BuildingControl/Logfiles/rebootlog.txt"

