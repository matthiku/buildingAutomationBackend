# buildingAutomationBackend

####Using Tinkerforge modules and a Raspberry Pi or Windows PC to control heating, lighting and access monitoring

This module reads/manipulates the various sensors and actors and monitors the events database which in turn determine the heating and lighting control.

**Using -**
* [Tinkerforge](http://www.tinkerforge.com/en) modules
* Raspberry Pi with [RaspBian](http://raspbian.org/) or Windows PC
* Python 3.x scripts
* Shell scripts for Linux

**Required Python packages**
* requests
* pymysql
* tinkerforge
* psutil

Also utilizes the DropboxUploader tool, see https://www.raspberrypi.org/magpi/dropbox-raspberry-pi/

**An overview of the modules used**
![this diagram](https://github.com/matthiku/buildingAutomationBackend/blob/master/Hardware%20Layout.png)


## Background
This module is the back-end part of a 3-tiered project called "Building Automation, Control and Monitoring":

>[buildingAutomationBackend](https://github.com/matthiku/buildingAutomationBackend)  < - > [buildingAPI](https://github.com/matthiku/buildingAPI)  < - > [buildingAutomationFrontend](https://github.com/matthiku/buildingAutomationFrontend)

![flowdiagram](https://github.com/matthiku/buildingAutomationBackend/blob/master/Building%20Management%20Overview%20Small.png)
[Full Size](https://github.com/matthiku/buildingAutomationBackend/blob/master/Building%20Management%20Overview.png)

(C) Matthias Kuhs, Ireland, 2015
