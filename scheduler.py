from enum import Enum
from datetime import datetime, timedelta, timezone
from dateutil import rrule
from itertools import takewhile
import logging as log
import sched
import pickle
import warnings
import os.path
import asyncio


def datetime_sleep(dt: datetime):
    """Sleeps until dt"""
    delta = dt - datetime.now(timezone.utc)
    yield from asyncio.sleep(delta.total_seconds())


class ActionName(Enum):
    PLANT_WATER = 0
    PLANT_CAPTURE_PHOTO = 1
    ROBOT_RANDOM_MOVEMENT = 2


class Event():
    event_id = None
    recurrences = []
    actions = []
    ephemeral = False

    test = 0

    def find_instances(self, before, after=datetime.now(timezone.utc)):
        """Gets a list of trigger times before max_dt."""

        r = rrule.rrulestr(self.recurrences[0])
        before = before.replace(tzinfo=None)
        after = after.replace(tzinfo=None)

        return takewhile(lambda dt: dt.replace(tzinfo=None) < before,
                         filter(lambda dt: dt.replace(tzinfo=None) >= after, r))

    @staticmethod
    def from_dict(dict):
        e = Event()
        e.event_id = dict['id']
        e.recurrences = dict['recurrences']
        e.actions = dict['actions']
        e.ephemeral = dict.get('ephemeral', False)
        return e

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
    # _sched: sched.scheduler
    __events = None

    # filename: str
    # reload_freq: timedelta

    def __init__(self, filename="rules.pickle.bin",
                 reload_freq=timedelta(hours=24)):

        # Store settings
        self.filename = filename
        self.reload_freq = reload_freq

        # Initialise backing sched
        self._sched = sched.scheduler(datetime.now, datetime_sleep)

        self.run_event_cb = lambda e: print("Run event cb", e)

        # Scheduler initiated, first read schedule from disk
        self.disk_load()

    def push_events(self, events):
        """Updates the event list, saves to disk, and reloads the scheduler"""

        for event in events:
            log.info("[SCHED] Pushing " + str(event))

        self.__events = events

        # Save these events to disk
        self.disk_save()

        # Apply these new events
        self.reload()

    def disk_save(self):
        """Stores the rules currently in memory, to disk."""
        log.info("[SCHED] Attempting to save to disk")

        # Exclaim a warning if rules do not exist
        if self.__events is None:
            log.warn("[SCHED] Save to disk aborted (nothing to save)")
            return

        f = open(self.filename, "wb")
        pickle.dump(self.__events, f)
        f.flush()
        f.close()

    def disk_load(self):
        """Loads rules from disk to memory, and applies the events.

        If no rules are on disk, this will initialise events to an empty list.
        """

        if not os.path.isfile(self.filename):
            warnings.warn("No events on disk, initialising empty events list.")
            self.__events = []
            self.disk_save()
            self.reload()
            return

        f = open(self.filename, "rb")
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
        log.info("[SCHED] Reloading...")

        # Clear the backing sched
        list(map(self._sched.cancel, self._sched.queue))

        # Ensure the backing sched is empty
        assert self._sched.empty()

        # Schedule next set of events (up to next update time)
        min_dt = datetime.now(timezone.utc)
        max_dt = min_dt + self.reload_freq
        for event in self.__events:
            for t in event.find_instances(after=min_dt, before=max_dt):
                self._sched.enterabs(t.replace(tzinfo=None), 0, lambda: self.run_event_cb(event))

        # Schedule a self reload after all events have elapsed
        self._sched.enterabs(max_dt, 1, self.reload)

    async def run(self):
        log.info("[SCHED] Running...")
        self._sched.run()
