#!/bin/bash

tinkerforge call temperature-bricklet bTh get-temperature
if [ $? == 0 ]; then exit 0
fi

tinkerforge call temperature-bricklet bSC get-temperature
if [ $? == 0 ]; then exit 0
fi

tinkerforge call temperature-bricklet 6Jm get-temperature
if [ $? == 0 ]; then exit 0
fi

tinkerforge call dual-relay-bricklet 6D9 get-state
if [ $? == 0 ]; then exit 0
fi
