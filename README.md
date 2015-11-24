# buildingAutomationBackend

####Using Tinkerforge modules and a Raspberry Pi or Windows PC to control heating, lighting and access monitoring

This module reads/manipulates the various sensors and actors and monitors the events database which in turn determine the heating and lighting control.

Using -
* [Tinkerforge](http://www.tinkerforge.com/en) modules
* Raspberry Pi with RaspBian or Windows PC
* Python 3.x scripts
 
See [this diagram](https://github.com/matthiku/buildingAutomationBackend/blob/master/Hardware%20Layout.png) for an overview of the modules used

It's the back-end part of a 3-tiered project called "Building Automation, Control and Monitoring":
>[buildingAutomationBackend](https://github.com/matthiku/buildingAutomationBackend)  < - > [buildingAPI](https://github.com/matthiku/buildingAPI)  < - > [buildingAutomationFrontend](https://github.com/matthiku/buildingAutomationFrontend)
