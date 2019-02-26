from enum import Enum, unique
import websockets
import json
import asyncio

class UnhandledRPCTranslationException(Exception):
    pass

@unique
class RPCType(Enum):
    MOVE_IN_DIRECTION = "move"
    DEMO_START = "demo/start"
    SETTINGS_PATCH = "settings/patch"

class Remote(object):
    def __init__(self, id, host="ws://api.growbot.tardis.ed.ac.uk"):
        self.id = id
        self.host = host
        self.callbacks = {}

    @asyncio.coroutine
    def connect(self):
        self.ws = yield from websockets.connect(self.host+"/stream/"+self.id)
        while True:
            message = yield from self.ws.recv()
            result = json.loads(message)

            type = RPCType(result['type'])
            data = result['data']
            if type in self.callbacks:
                self._translate_call(type, data, self.callbacks[type])
            else:
                print("Uncaught message for type", type, "with data", data)

    def close(self):
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
        else:
            raise UnhandledRPCTranslationException()
