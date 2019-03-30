from enum import Enum, unique
import websockets
import json
import asyncio
import logging as log


class UnhandledRPCTranslationException(Exception):
    pass


@unique
class RPCType(Enum):
    MOVE_IN_DIRECTION = "move"
    DEMO_START = "demo/start"
    SETTINGS_PATCH = "settings/patch"
    EVENTS = "events"


@unique
class LogType(Enum):
    UNKNOWN = 0
    PLANT_WATERED = 1


@unique
class LogSeverity(Enum):
    INFO = 0
    SUCCESS = 1
    WARNING = 2
    DANGER = 3


class Remote(object):
    def __init__(self, id, host="ws://api.growbot.tardis.ed.ac.uk"):
        log.info("[REMOTE] Init {}".format(id))
        self.id = id
        self.host = host
        self.callbacks = {}
        self.ws = None
        self.__queue = []

    @asyncio.coroutine
    def connect(self):
        log.info("[REMOTE] Connect {}".format(self.id))
        self.ws = yield from websockets.connect(self.host+"/stream/"+self.id)
        log.info("WebSockets connection established on {}, {} queued messages".format(self.host+"/stream/"+self.id, len(self.__queue)))

        # Fire messages in the queue
        for data in self.__queue:
            self.ws.send(data)

        # Delete the queue
        self.__queue = None

        while True:
            message = yield from self.ws.recv()
            result = json.loads(message)

            type = RPCType(result['type'])
            data = result['data']
            if type in self.callbacks:
                self._translate_call(type, data, self.callbacks[type])
            else:
                log.error("[REMOTE] Uncaught message for type {} with data {}".format(type, data))

    def __send(self, data):
        # The we haven't connected yet, queue messages
        if self.ws is None:
            self.__queue.append(data)
            return

        self.ws.send(data)

    def plant_capture_photo(self, plant_id: int, image):
        body = {
            'type': "PLANT_CAPTURE_PHOTO",
            'data': {
                plant_id: plant_id,
                image: image,  # Must be base64 encoded
            }
        }

        self.__send(body)

    def create_log_entry(self, type, message, severity=LogSeverity.INFO,
                         plant_id=None):

        assert isinstance(type, LogType)
        assert isinstance(severity, LogSeverity)

        body = {
            'type': "CREATE_LOG_ENTRY",
            'data': {
                'type': type.name,
                'message': message,
                'severity': severity.value,
                'plant_id': plant_id,
            }
        }

        self.__send(body)

    def update_soil_moisture(self, plant, moisture):
        body = {
            'type': 'UPDATE_SOIL_MOISTURE',
            'data': {
                'plant': plant,
                'moisture': moisture
            }
        }

        self.__send(body)

    def close(self):
        if hasattr(self, "ws"):
            self.ws.close()

    def add_callback(self, type, fn):
        self.callbacks[type] = fn

    def _translate_call(self, type, data, fn):
        """
        Internal only
        """
        if type == RPCType.MOVE_IN_DIRECTION:
            fn(data)
        elif type == RPCType.DEMO_START:
            fn(data)
        elif type == RPCType.SETTINGS_PATCH:
            fn(data["Key"], data["Value"])
        elif type == RPCType.EVENTS:
            fn(data)
        else:
            raise UnhandledRPCTranslationException()
