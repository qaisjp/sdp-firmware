from typing import List
from enum import Enum
from datetime import datetime, timedelta
from dateutil import rrule
from itertools import takewhile
import sched
import pickle
import warnings
import os.path
import asyncio

PICKLE_FILE = "rules.pickle.bin"
RELOAD_FREQUENCY = timedelta(seconds=10)


def datetime_sleep(dt: datetime):
    """Sleeps until dt"""
    delta = dt - datetime.now()
    yield from asyncio.sleep(delta.total_seconds())


class ActionName(Enum):
    PLANT_WATER = 0
    PLANT_CAPTURE_PHOTO = 1


class Action():
    name: ActionName
    plant_id: int
    data: map


class Event():
    event_id: int
    recurrences: List[str]
    actions: List[Action]

    test = 0

    def find_instances(self, before: datetime,
                       after: datetime = datetime.now()) -> List[datetime]:
        """Gets a list of trigger times before max_dt."""

        r = rrule.rrulestr(self.recurrences[0])

        return takewhile(lambda dt: dt < before,
                         filter(lambda dt: dt >= after, r))

    def trigger(self):
        self.test += 1
        print("Event was called ", self.test)


class Scheduler():
    _sched: sched.scheduler
    events: List[Event] = None

    def __init__(self):
        # Initialise backing sched
        self._sched = sched.scheduler(datetime.now, datetime_sleep)

        # Scheduler initiated, first read schedule from disk
        self.disk_load()

        # Download from network, if possible
        self.download()  # (todo: in a separate thread)

    def download(self):
        """Downloads events from the network.

        After download, the scheduler is automatically reloaded.

        The events are also automatically committed on disk.

        If the download fails, two things may happen:
        - If no events are currently loaded, an exception is thrown.
        - If events are downloaded, nothing happens (the old events apply)
        """

        success = False

        # If no events are downloaded, don't do anything
        if not success:
            return

        # Download events
        """DEMO EVENTS"""
        e = Event()
        e.recurrences = [str(rrule.rrule(freq=rrule.SECONDLY,
                             interval=2, dtstart=datetime.now()))]
        self.events = [e]

        # Save these events to disk
        self.disk_save()

        # Apply these new events
        self.reload()

    def disk_save(self):
        """Stores the rules currently in memory, to disk."""
        print("[Scheduler] Attempting to save to disk")

        # Exclaim a warning if rules do not exist
        if self.events is None:
            print("[Scheduler] Save to disk aborted (nothing to save)")
            return

        f = open(PICKLE_FILE, "wb")
        pickle.dump(self.events, f)
        f.flush()
        f.close()

    def disk_load(self):
        """Loads rules from disk to memory, and applies the events.

        If no rules are on disk, this will initialise events to an empty list.
        """

        if not os.path.isfile(PICKLE_FILE):
            warnings.warn("No events on disk, initialising empty events list.")
            self.events = []
            self.reload()
            return

        f = open(PICKLE_FILE, "rb")
        self.events = pickle.load(f)
        f.close()

        self.reload()

    def reload(self):
        """Deletes all events and reloads them.

        This only schedules events that occur in the next 24 hours.
        After 24 hours have passed, the events are reloaded from disk.

        This will allow all future events to be perpetually scheduled,
        but without murdering time.sleep.
        """
        print("[Scheduler] Reloading...")

        # Clear the backing sched
        list(map(self._sched.cancel, self._sched.queue))

        # Ensure the backing sched is empty
        assert self._sched.empty()

        # Schedule next set of events (up to next update time)
        min_dt: datetime = datetime.now()
        max_dt: datetime = min_dt + RELOAD_FREQUENCY
        for event in self.events:
            for t in event.find_instances(after=min_dt, before=max_dt):
                self._sched.enterabs(t, 0, event.trigger)

        # Schedule a self reload after all events have elapsed
        self._sched.enterabs(max_dt, 1, self.reload)


    async def run(self):
        print("[Scheduler] Running...")
        self._sched.run()
