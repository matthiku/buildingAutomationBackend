
#!/bin/bash

# show 'tail' of recent BM log files

echo "=============================================================================================================================="
tail -n 15 /home/pi/Dropbox/BuildingControl/Logfiles/*.txt
echo "=============================================================================================================================="
tail -n 15 /home/pi/Dropbox/BuildingControl/*.txt
echo ""
echo "=============================================================================================================================="

# run checkProc now
/root/checkProc.sh
