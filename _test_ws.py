from RemoteMotorController import RemoteMotorController
import asyncio
import threading
from RobotController import RobotController
from Navigator import Navigator


def sender_action(rm, loop):
    asyncio.set_event_loop(loop)
    rm.connect()
    loop.run_forever()


def receiver_action(rm, loop):
    asyncio.set_event_loop(loop)
    rm.connect(sender=False, port_nr=19221)
    loop.run_forever()


def main():
    rc = RobotController()
    nv = Navigator(rc)
    rm = RemoteMotorController(nv)

    ws_sender_loop = asyncio.new_event_loop()
    ws_sender_thread = threading.Thread(target=sender_action,
                                        args=(rm, ws_sender_loop,))
    ws_sender_thread.setDaemon(True)
    ws_sender_thread.start()

    ws_receiver_loop = asyncio.new_event_loop()
    ws_receiver_thread = threading.Thread(target=receiver_action,
                                          args=(rm, ws_receiver_loop,))
    ws_receiver_thread.setDaemon(True)
    ws_receiver_thread.start()

    wait_loop = asyncio.new_event_loop()
    task = wait_loop.create_task(asyncio.sleep(5))
    wait_loop.run_until_complete(task)

    while True:
        rm.turn_left(-1)

    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
