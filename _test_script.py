from RemoteMotorController import RemoteMotorController
from time import sleep
import asyncio
import threading

def do_loop(rm, loop):
    asyncio.set_event_loop(loop)
    rm.connect()
    loop.run_forever()

def main():
    rm = RemoteMotorController()
    ws_loop = asyncio.new_event_loop()
    ws_thread = threading.Thread(target=do_loop, args=(rm, ws_loop,))
    ws_thread.setDaemon(True)
    ws_thread.start()


    wait_loop = asyncio.new_event_loop()
    task = wait_loop.create_task(asyncio.sleep(5))
    wait_loop.run_until_complete(task)
    while True:
        rm.turn_left()

    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()