import asyncio
from scheduler import Scheduler, Event, Action, ActionName
from dateutil.rrule import rrule, SECONDLY
from datetime import datetime, timedelta
import logging as log
import sys


def check_24_hours():
    s = Scheduler(reload_freq=timedelta(seconds=12))
    asyncio.ensure_future(s.run())

    # EXAMPLE DOWNLOAD START
    rule1 = rrule(freq=SECONDLY, interval=5, dtstart=datetime.now(), count=60)
    rule2 = rrule(freq=SECONDLY, interval=9, dtstart=datetime.now(), count=60)

    a1 = Action(ActionName.PLANT_CAPTURE_PHOTO, 5)
    a2 = Action(ActionName.PLANT_WATER, 9)

    e1 = Event()
    e1.recurrences = [str(rule1)]
    e1.actions = [a1]

    e2 = Event()
    e2.recurrences = [str(rule2)]
    e2.actions = [a2]
    # EXAMPLE DOWNLOAD END

    s.push_events([e1, e2])


def run():
    check_24_hours()

    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks()
    loop.run_until_complete(asyncio.gather(*pending))


if __name__ == "__main__":
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s",
                    level=log.INFO, stream=sys.stdout)
    run()
    print("Completed!")
