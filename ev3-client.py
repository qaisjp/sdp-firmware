import websockets
import asyncio

class EV3_Client:
    def __init__(self, host="10.42.0.1"):
        self.host = host
        asyncio.get_event_loop().run_until_complete(self.connect())

    @asyncio.coroutine
    def connect(self):
        websocket_pi = yield from websockets.connect("ws://{}:{}/".format(self.host, 8866))

        try:
            yield from websocket_pi.send("conn-est")
        finally:
            yield from websocket_pi.close()


def main():
    ev3 = EV3_Client(host="localhost")

if __name__ == "__main__":
    main()