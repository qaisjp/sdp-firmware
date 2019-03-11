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

    def __init__(self, name: ActionName, plant_id: int, data: map = {}):
        self.name = name
        self.plant_id = plant_id
        self.data = data

    def perform(self):
        if self.name == ActionName.PLANT_WATER:
            print("Supposed to water plant_id {} and data {}".format(
                self.plant_id, self.data))
        elif self.name == ActionName.PLANT_CAPTURE_PHOTO:
            print("Supposed to take picture of plant_id {} and data {}".format(
                self.plant_id, self.data))
        else:
            print("Unknown action: name: {}, plant_id: {}, data: {}".format(
                self.name, self.plant_id, self.data))

    def __str__(self):
        return "Action(name={}, plant_id={}, data={})".format(
            self.name.name, self.plant_id, self.data)


class Event():
    event_id: int = None
    recurrences: List[str] = []
    actions: List[Action] = []

    test = 0

    def find_instances(self, before: datetime,
                       after: datetime = datetime.now()) -> List[datetime]:
        """Gets a list of trigger times before max_dt."""

        r = rrule.rrulestr(self.recurrences[0])

        return takewhile(lambda dt: dt < before,
                         filter(lambda dt: dt >= after, r))

    def trigger(self):
        if len(self.actions) == 0:
            print("Event triggered:", self)
            return

        for action in self.actions:
            action.perform()

    def __str__(self):
        recurrences = "\n        "
        if len(self.recurrences) > 0:
            recurrences += ",\n        ".join(self.recurrences) + "\n    "
        else:
            recurrences = ""

        actions = "\n        "
        if len(self.actions) > 0:
            actions += ",\n        ".join(map(str, self.actions)) + "\n    "
        else:
            actions = ""

        return """Event(
    event_id={},
    recurrences=[{}],
    actions=[{}]
)""".format(self.event_id, recurrences, actions)


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

        for event in events:
            print("[Scheduler] Pushing " + str(event))

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
            self.disk_save()
            self.reload()
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
