from RemoteMotorController import RemoteMotorController
from time import sleep
import asyncio
import threading

def do_loop(rm):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rm.connect()

def send_turn(rm):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rm.turn_left()

def main():
    rm = RemoteMotorController()
    ws_thread = threading.Thread(target=do_loop(rm), args=())
    ws_thread.daemon = True
    ws_thread.start()
    loop = asyncio.new_event_loop()
    task = loop.create_task(asyncio.sleep(5))
    loop.run_until_complete(task)

    turn_thread = threading.Thread(target=send_turn(rm), args=())
    turn_thread.daemon = True
    turn_thread.start()
    
    task2 = loop.create_task(asyncio.sleep(5))
    loop.run_until_complete(task2)
    # rm.send_message("Hi! Please work")

if __name__ == "__main__":
    main()