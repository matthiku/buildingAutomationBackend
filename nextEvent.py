'''
Controls the heating at EEC
'''

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import sys
import os
from   datetime import datetime, timedelta
import requests

# import tinkerforge modules
from tinkerforge.bricklet_temperature import BrickletTemperature
from tinkerforge.bricklet_dual_relay import BrickletDualRelay
from tinkerforge.ip_connection import IPConnection


HOST   = "localhost"
PORT   = 4223
DR_UID = "6D9"  # UID of Dual Relay Bricklet
MR_UID = "bTh"  # main room temp
FR_UID = "6Jm"  # downstairs temp
HW_UID = "bSC"  # heating water


# To calculate the required pre-heating duration and switch-on time
TARGET_TEMPERATURE = 20.00              # for now we use a generic target temperature
HEATING_RATE       = 1.01               # time (in hours) it takes to increase the
                                        #           room temperature by 1 degree Celsius


# Draw solid boxes around text
DRAW_TOP_LEFT     = "┌" # (U+250C) for the top left corner
DRAW_BOTTOM_RIGHT = "┘"  # (U+2518) for the bottom right corner
DRAW_HORIZONTAL   = "─" # (U+2500) for the horizontal lines
DRAW_TOP_RIGHT    = "┐" # (U+2510) for the top right corner
DRAW_VERTICAL     = "│"  # (U+2502) for the vertical lines
DRAW_BOTTOM_LEFT  = "└" # (U+2514) for the bottom left corner


# Global variables
hoursNeeded    = 0
secondsNeeded  = 0

frontRoomTemp    = 0
mainRoomTemp     = 0
heatingWaterTemp = 0


'''

    M O D U L E S

'''

'''
    ---------------------------------------------------------------------------------------------
    MODULE: heating_time()
    
      This module calculates the time required to heat a room from its current temperature
         to a target temperature at a specified heating rate.
    
     Args:
         current_temp(float): The current temperature of the room in degrees Celsius.
          target_temp(float): The target temperature to be reached in degrees Celsius.
         heating_rate(float): The rate at which the room is heated, in degrees Celsius per hour.
    
     Returns:
         float: The time required to heat the room to the target temperature, in hours.
    
     Example:
         >> > heating_time(20, 100, 10)
         8.0
    
     Note:
         The function assumes that the heating rate is constant
         and that it does not vary with temperature.
     ---------------------------------------------------------------------------------------------'''
def heating_time(current_temp, target_temp, heating_rate):
    ''' 
        calculates the time required to heat a room from its current temperature 
            to a target temperature at a specified heating rate 
        '''
    temp_difference = target_temp - current_temp
    return temp_difference * heating_rate


def get_temp_sensor_values():
    ''' Check and show the current room temperatures and heating water temp '''

    # just to be on the save side
    try:
        print("trying to disconnect - ", end="")
        ipcon.disconnect()
        print("success!")
    except:
        print("wasn't connected!")

    # get and show Main Room Temp ------------------------------------------------------------
    t1 = BrickletTemperature(MR_UID, ipcon)  # Create device object
    ipcon.connect(HOST, PORT)  # Connect to brickd
    # Don't use device before ipcon is connected!
    temperature = t1.get_temperature()
    print("┌──────────────────────────────────────────┐")
    print("│       Main Room Temperature: " + (str(temperature/100.0) + " °C").ljust(12)[:12] + "│")
    mainRoomTemp = temperature/100

    # Get  Front  Room  temperature ---------------------------------------------
    t1 = BrickletTemperature(FR_UID, ipcon)  # Create device object
    temperature = t1.get_temperature()
    print("│      Front Room Temperature: " + (str(temperature/100.0) + " °C").ljust(12)[:12] + "│")
    frontRoomTemp = temperature/100

    # Get  Heating  Water  temperature ------------------------------------------
    t1 = BrickletTemperature(HW_UID, ipcon)  # Create device object
    temperature = t1.get_temperature()
    print("│   Heating Water Temperature: " + (str(temperature/100.0) + " °C").ljust(12)[:12] + "│")
    print("└──────────────────────────────────────────┘\n")
    heatingWaterTemp = temperature/100

    # just to be on the save side
    try:
        print("trying to disconnect - ", end="")
        ipcon.disconnect()
        print("success!")
    except:
        print("wasn't connected!")

    return mainRoomTemp, frontRoomTemp, heatingWaterTemp



if __name__ == "__main__":


    # first, connect to my Tinkerforge bricklets
    ipcon = IPConnection()  # Create IP connection

    #===========================================================================+
    #  Check the current room temperatures and get a handle on the Dual Relay!  !
    #===========================================================================+
    mainRoomTemp, frontRoomTemp, heatingWaterTemp = get_temp_sensor_values()

    # Get Dual  Relay  Status ---------------------------------------------------
    ipcon.connect(HOST, PORT)  # Connect to brickd
    dr = BrickletDualRelay(DR_UID, ipcon)   # create the device object
    dr_status = dr.get_state()
    dr_status_SW0 = dr_status[0]
    dr_status_SW1 = dr_status[1]
    print("                    +--> Switch 1: ", dr_status_SW0)
    print("Dual Relay Status --+")
    print("                    +--> Switch 2: ", dr_status_SW1)

    ipcon.disconnect()



    #=================================================================
    # get next event data
    #=================================================================
    URL = "https://plan.eec.ie/api/plans/next"
    payload = {
        "key": "value"
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.get(URL, data=json.dumps(payload), headers=headers, timeout=5)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # print("Request successful!")
        # Get the content of the response
        data = response.json()
        # print(data)
    else:
        print(f"Request failed with status code {response.status_code}")
        sys.exit()

    # These are just time value strings without a date, eg. "12:00:00"
    startOfEvent = data['date']
    endOfEvent   = startOfEvent[:10] + " " + data['type']['end']
    nameOfEvent  = data['type']['name']

    print("startOfEvent", startOfEvent)

    print("\nWe have an upcoming event: " + nameOfEvent +
        ", on " + data['date'] + ", ending at " + endOfEvent + ".")

    #===============================================================================
    # calculate the required lead-in time to get the desired room temperature
    #===============================================================================

    # create datetime objects for the two dates
    date1 = datetime.now()
    date2 = datetime.strptime(data['date'], "%Y-%m-%d %H:%M:%S")

    # calculate the time difference
    time_diff = date2 - date1

    # print the time difference in seconds
    secondsUntilEvent = round(time_diff.total_seconds(), 0)
    print('\nTime until event starts: ' +
          str( round(time_diff.total_seconds() / 3600, 2) ) + ' hours' +
          " or ", secondsUntilEvent, " seconds.")


    currentRoomTemp = mainRoomTemp          # for now we only use the Main Room temperature

    print("Current Room Temp. is ", str(currentRoomTemp), "°C",
          "\n Target Room Temp. is ", TARGET_TEMPERATURE, "°C",
            "\n      Heating Rate is ", HEATING_RATE, "°C per hour.")

    # check if we actually still have to heat the room
    if currentRoomTemp < TARGET_TEMPERATURE:
        hoursNeeded = heating_time(
            currentRoomTemp, TARGET_TEMPERATURE, HEATING_RATE)
        secondsNeeded = round(hoursNeeded * 3600, 0)
        print("\nTo achieve the target room temperature, we need to switch on the heating for",
              round(hoursNeeded, 2), "hours beforehand or ", secondsNeeded, " seconds.")

    else:
        print("====> Room already has or exceeds the desired temperature! <====")

        # that means we should turn off the heating (switch 2) but 
        # leave the warm water active (switch 1) as long as the event has not ended yet.
        
        # :::: TODO ::::



    # ============================================================================================
    # Calculate the exact date and time on which the heating should be switched on
    # ============================================================================================

    # create datetime objects for the the current time and the switch-on time
    now = datetime.now()
    # add number of seconds to now and subtract the amount of time needed to heat up the room 
    #                                                       to get the actual switch-on time!
    switchOnTime = now + timedelta(seconds=secondsUntilEvent - secondsNeeded)

    print("Seconds until event starts: ", secondsUntilEvent)
    print("         End of event is at ", endOfEvent)

    print("\nTo be exact, it should be activated on or after ", switchOnTime, "\n")


    # in order to later check if my source file has been changed (so that I can gracefully stop!)
    file_path = os.getenv("HOMEPATH") + r'\DropBox\BuildingControl\nextEvent.py'
    # Get the modification time of the file in seconds since epoch
    my_source_last_modification_time = os.path.getmtime(file_path)


    while True:

        # re-calculate the switch-on time
        now = datetime.now()
        switchOnTime = now + timedelta(seconds=secondsUntilEvent - secondsNeeded)


        # ============================================================================================
        # Are we already within the heating phase?
        # ============================================================================================

        # first, we need to convert the "End of Event" entity into a dateTime object 
        # in order to be able to programmatically handle it.
        endOfEventDateObj = datetime.strptime( endOfEvent, "%Y-%m-%d %H:%M:%S" )
        print("\nEnd of today's Event:", endOfEventDateObj)
        
        # Check if event is already over!
        if secondsUntilEvent < 0 and now > endOfEventDateObj:
            print("\nEvent has already finished. Need to make sure that heating is off!")
            print("\nHeating phase has ended, making sure both relays are off:")
            ipcon.connect(HOST, PORT)                   # Connect to brickd
            dr = BrickletDualRelay(DR_UID, ipcon)       # create the device object
            dr.set_state(False, False)

            # show current Dual Relay switches status
            dr_status = dr.get_state()
            dr_status_SW0 = dr_status[0]
            dr_status_SW1 = dr_status[1]
            print("                    +--> Switch 1: ", dr_status_SW0)
            print("Dual Relay Status --+")
            print("                    +--> Switch 2: ", dr_status_SW1)

            ipcon.disconnect()

        else:
            if secondsUntilEvent < secondsNeeded:
                # Heating phase has or will begin!

                # connect to the Dual Relay bricklet
                ipcon.connect(HOST, PORT)  # Connect to brickd
                dr = BrickletDualRelay(DR_UID, ipcon)   # create the device object

                # show current Relay status
                dr_status = dr.get_state()
                dr_status_SW0 = dr_status[0]
                dr_status_SW1 = dr_status[1]
                print("                    +--> Switch 1: ", dr_status_SW0)
                print("Dual Relay Status --+")
                print("                    +--> Switch 2: ", dr_status_SW1)

                # switch in both relays if still off
                if dr_status_SW0 is False:
                    if dr_status_SW0 is False:
                        print("\nHeating phase has started, switching on both relays ...")
                        dr.set_state(True, True)
                else:
                    get_temp_sensor_values()  # get and show current temp values
                    print(now, "\n === Heating is already on! === ")

                # just to be on the save side  - replace:  >> ipcon.disconnect() <<
                try:
                    print("trying to disconnect - ", end="")
                    ipcon.disconnect()
                    print("success!")
                except:
                    print("wasn't connected!")



            else:
                print("Still waiting for Heating Phase to begin:  ", now)


        # now to check if my source file has been changed (so that I can gracefully stop!)
        if my_source_last_modification_time != os.path.getmtime(file_path):
            print("\nGracefully stopping myself since my sourcecode has been changed while I was sleeping!")
            sys.exit()


        # =============================== wait a minute! ==================================
        time.sleep(60)

        get_temp_sensor_values()
