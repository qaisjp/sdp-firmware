from typing import List
from enum import Enum
from datetime import datetime
import time
import sched
import pickle
import warnings
import os.path

PICKLE_FILE = "rules.pickle.bin"


def datetime_sleep(dt: datetime):
    """Sleeps until dt"""
    delta = dt - datetime.now()
    time.sleep(delta.total_seconds())


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


class Scheduler():
    _sched: sched.scheduler
    events: List[Event] = None

    def __init__(self):
        # Initialise backing sched
        self._sched = sched.scheduler(datetime, datetime_sleep)

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

        # Download events
        pass  # todo

        self.disk_save()

    def disk_save(self):
        """Stores the rules currently in memory, to disk."""
        print("disk_save() called")

        # Exclaim a warning if rules do not exist
        if self.events is None:
            warnings.warn("Cannot save None events to disk")
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

        # Clear the backing sched
        list(map(self._sched.cancel, self._sched.queue))

        # Ensure the backing sched is empty
        assert self._sched.empty()

        # Loop through self.events and schedule events for next 24 hours
        pass  # todo

        # Schedule a self reload after 24 hours.
        # Be careful about race conditions?
        pass  # todo
