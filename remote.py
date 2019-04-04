from enum import Enum, unique
import websockets
import json
import asyncio
import logging as log
import threading


class UnhandledRPCTranslationException(Exception):
    pass


@unique
class RPCType(Enum):
    MOVE_IN_DIRECTION = "move"
    DEMO_START = "demo/start"
    SETTINGS_PATCH = "settings/patch"
    EVENTS = "events"
    SET_STANDBY = "standby"


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


@asyncio.coroutine
def ws_send(ws, i, data):
    print("start {}".format(i))
    yield from ws.send(json.dumps(data))
    print("end {}".format(i))


class Remote(object):
    def __init__(self, id, host="wss://api.growbot.tardis.ed.ac.uk"):
        log.info("[REMOTE] Init {}".format(id))
        self.id = id
        self.host = host
        self.callbacks = {}
        self.ws = None
        self.ws_i = 0
        self.__queue = []

    @asyncio.coroutine
    def connect(self):
        log.info("[REMOTE] Connect {}".format(self.id))
        self.ws = yield from websockets.connect(self.host+"/stream/"+self.id, write_limit=2**18)
        log.info("[REMOTE] Connection established on {}, {} queued messages".format(self.host+"/stream/"+self.id, len(self.__queue)))

        # Fire messages in the queue
        for data in self.__queue:
            log.info("[REMOTE] Firing queued message {}".format(data))
            self.__send(data)

        log.info("[REMOTE] Done queue stuff")

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

    def __send(self, data, friendly=True):
        # The we haven't connected yet, queue messages
        if self.ws is None:
            log.info("[REMOTE] Queueing message {}".format(data))
            self.__queue.append(data)
            return

        friendly_data = {"type": data["type"]}
        if friendly:
            friendly_data["data"] = data["data"]

        thname = threading.current_thread().name
        log.info("[REMOTE] [Thread:{}] Sending message {}".format(thname, friendly_data))
        asyncio.ensure_future(ws_send(self.ws, self.ws_i, data))
        self.ws_i += 1

    def plant_capture_photo(self, plant_id: int, image):
        body = {
            'type': "PLANT_CAPTURE_PHOTO",
            'data': {
                'plant_id': plant_id,
                'image': image,  # Must be base64 encoded
            }
        }

        log.info("[REMOTE] Sending an image of plant {}".format(str(plant_id)))
        self.__send(body, friendly=False)

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
        elif type == RPCType.SET_STANDBY:
            log.info("remote._translate_call('standby', {}, {}".format(data, fn))
            fn(data)
        else:
            raise UnhandledRPCTranslationException()
