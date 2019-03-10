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
    __events: List[Event] = None

    def __init__(self):
        # Initialise backing sched
        self._sched = sched.scheduler(datetime.now, datetime_sleep)

        # Scheduler initiated, first read schedule from disk
        self.disk_load()

    def push_events(self, events: List[Event]):
        """Updates the event list, saves to disk, and reloads the scheduler"""

        self.__events = events

        # Save these events to disk
        self.disk_save()

        # Apply these new events
        self.reload()

    def disk_save(self):
        """Stores the rules currently in memory, to disk."""
        print("[Scheduler] Attempting to save to disk")

        # Exclaim a warning if rules do not exist
        if self.__events is None:
            print("[Scheduler] Save to disk aborted (nothing to save)")
            return

        f = open(PICKLE_FILE, "wb")
        pickle.dump(self.__events, f)
        f.flush()
        f.close()

    def disk_load(self):
        """Loads rules from disk to memory, and applies the events.

        If no rules are on disk, this will initialise events to an empty list.
        """

        if not os.path.isfile(PICKLE_FILE):
            warnings.warn("No events on disk, initialising empty events list.")
            self.__events = []
            return

        f = open(PICKLE_FILE, "rb")
        self.__events = pickle.load(f)
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
        for event in self.__events:
            for t in event.find_instances(after=min_dt, before=max_dt):
                self._sched.enterabs(t, 0, event.trigger)

        # Schedule a self reload after all events have elapsed
        self._sched.enterabs(max_dt, 1, self.reload)

    async def run(self):
        print("[Scheduler] Running...")
        self._sched.run()
