import requests
import datetime, time, calendar

def getNextCspotEvent():
    try:
        r = requests.get('https://plan.eec.ie/api/plans/next', timeout=4)
        if not r.ok or len(r.content) < 200:
            return '', False, 0, 0, 0, 0, 0, 0
    except:
        print("failed")
        return '', False, 0, 0, 0, 0, 0, 0

    now = datetime.datetime.now()
    event = r.json()
    eventID = int(event['id'])
    online_id = event['id']
    eventName = event['type']['name']
    eventStart = datetime.datetime.fromisoformat(event['date'])
    evtActive = False
    # we only care about events in Main Room or Front Room!
    room = 0
    roomName = event['resources'][0]['name']
    if roomName == "Main Room":
        room = 1
    if roomName == "Front Room":
        room = 2

    if room != 0 and eventStart.date() == now.date():
        eventEnd = datetime.datetime.fromisoformat(event['date_end'])
        targetTemp = 21
        print( "Today's event **"+ eventName + "** starts at "+ str(eventStart)+" and ends at " + str(eventEnd) )

        # how many seconds until start of event resp. end of event?
        toStart = ((eventStart.hour*60 + eventStart.minute) - (now.hour * 60 + now.minute)) * 60
        sinceEnd = ((now.hour * 60 + now.minute) - (eventEnd.hour * 60 + eventEnd.minute)) * 60
        
        # event is "active" from 30 mins before start until 30 mins after the end
        if toStart  < 1800: evtActive = True
        if sinceEnd > 1800: evtActive = False

        # return values only up to 30 mins after end of event
        if sinceEnd < 1800:
            print( eventName, evtActive, toStart, room, sinceEnd, targetTemp, eventID, online_id)

    return '', False, 0, 0, 0, 0, 0, 0

getNextCspotEvent()
