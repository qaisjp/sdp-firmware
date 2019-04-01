import websockets
import asyncio
import sys
import logging as log
import firmware
import threading
import random
import time
import json
import SigFinish

class EV3_Client:
    def __init__(self, host="10.42.0.1"):
        self.host = host
        self.est = False
        self.ws_receiver = None
        self.ws_sender = None
        self.stop_now = False
        self.distress_called = None
        self.last_distress_sent = time.time()
        self.firmware = firmware.GrowBot(-1,-1) # Battery/water levels to be implemented
        self.turn_issued = False
        self.random_issued = False
        self.approach_complete = False
        self.retry_complete = False
        self.approach_escape_complete = False
        self.approach_problem = False

    def connect(self, sender=False):
        try:
            try:
                if not sender:
                    log.info("Connecting receiver to Pi receiver...")
                    asyncio.get_event_loop().run_until_complete(self.setup_receiver())
                else:
                    log.info("Connecting sender to Pi sender...")
                    asyncio.get_event_loop().run_until_complete(self.setup_sender())
            except KeyboardInterrupt:
                self.firmware.stop()
        except websockets.exceptions.ConnectionClosed:
            self.firmware.stop()
            self.connect(sender)

    @asyncio.coroutine
    def setup_receiver(self, port_nr=8866):
        while True:
            try:
                self.ws_receiver = yield from websockets.connect("ws://{}:{}/".format(self.host, port_nr), ping_interval=None)
                break
            except ConnectionRefusedError:
                # Connection refused, repeat trying in a few seconds
                log.warn("Connection to port {} refused, trying again in 5 seconds.".format(port_nr))
                yield from asyncio.sleep(5)
                continue

        log.info("Web socket connection established on {}:{}".format(self.ws_receiver.host, self.ws_receiver.port))
        try:
            while True:
                msg = yield from self.ws_receiver.recv()
                process_thread = threading.Thread(target=self.message_process, args=(msg,))
                process_thread.start()
        finally:
            self.firmware.stop()
            self.ws_receiver.close()

    @asyncio.coroutine
    def setup_sender(self, port_nr=19221):
        while True:
            try:
                self.ws_sender = yield from websockets.connect("ws://{}:{}/".format(self.host, port_nr), ping_interval=None)
                break
            except ConnectionRefusedError:
                # Connection refused, repeat trying in a few seconds
                log.warn("Connection to port {} refused, trying again in 5 seconds.".format(port_nr))
                yield from asyncio.sleep(5)
                continue

        log.info("Web socket connection established on {}:{}".format(self.ws_sender.host, self.ws_sender.port))
        try:
            init_package = {
                "type": "init",
                "turning_constant": str(self.firmware.turning_constant),
                "severity": 0
            }
            log.info("[EV3 > Pi] Sending init info: {}".format(json.dumps(init_package)))
            # yield from self.ws_sender.send(json.dumps(init_package))

            while True:
                try:
                    package = {
                        "type": "sensor",
                        "front_sensor": str(self.firmware.front_sensor.value()),
                        "back_sensor": str(self.firmware.back_sensor.value()),
                        "severity": 0
                    }
                    log.info("[EV3 > Pi] Sending sensor data (\"front_sensor\": {}, \"back_sensor\": {})"
                        .format(package["front_sensor"], package["back_sensor"]))
                    yield from self.ws_sender.send(json.dumps(package))
                except ValueError as e:
                    log.error("[EV3] Value error: {}".format(e))
                if self.distress_called is not None:
                    if self.distress_called - self.last_distress_sent > 5:
                        distress_package = {
                            "type": "distress",
                            "message": "sensor_stuck",
                            "severity": 3
                        }
                        log.info("[EV3 > Pi] Sending distress signal, reason: {}".format(distress_package["message"]))
                        yield from self.ws_sender.send(json.dumps(distress_package))
                        self.last_distress_sent = time.time()
                        self.distress_called = None
                time.sleep(1)
                if self.approach_complete:
                    package = {
                            "type": "approach_complete",
                            "severity": 1
                    }
                    if self.approach_problem:
                        package["approach_problem"] = True
                    else:
                        package["approach_problem"] = False
                    log.info("[EV3 > Pi] Sending approach complete message, approach_problem={}.".format(str(self.approach_problem)))
                    yield from self.ws_sender.send(json.dumps(package))
                    self.approach_complete = False
                    self.approach_problem = False
                if self.retry_complete:
                    package = {
                            "type": "retry_complete",
                            "severity": 1
                    }
                    log.info("[EV3 > Pi] Sending retry complete message.")
                    yield from self.ws_sender.send(json.dumps(package))
                    self.retry_complete = False
                if self.approach_escape_complete:
                    package = {
                            "type": "approach_escape_complete",
                            "severity": 1
                    }
                    log.info("[EV3 > Pi] Sending approach escape complete message.")
                    yield from self.ws_sender.send(json.dumps(package))
                    self.approach_escape_complete = False
        finally:
            self.firmware.stop()
            self.ws_sender.close()

    def message_process(self, msg):
        package = json.loads(msg)
        action = package["action"]
        log.info("[EV3 < Pi] Received action \"{}\"".format(action))

        if action == "stop":
            log.info("Stopping.")
            self.stop_now = True
            self.firmware.stop()
            self.turn_issued = False
            self.random_issued = False

        elif action == "approached":
            log.info("Plant approached, starting procedures.")
            self.stop_now = True
            self.firmware.stop()
            self.turn_issued = True # Set this flag to true to ignore most messages
            self.approached_routine() # Do approach routines
            self.turn_issued = False

        elif action == "retry_approach":
            log.info("Retrying approaching due to plant not centred.")
            self.stop_now = True
            self.firmware.stop()
            self.turn_issued = True # Set this flag to true to ignore most messages
            self.retry_approach_routine() # Do retry
            self.turn_issued = False

        elif action == "approach_escape":
            log.info("Turning around in spot to leave the current plant.")
            self.stop_now = True
            self.firmware.stop()
            self.turn_issued = True # Set this flag to true to ignore most messages
            turn_start = time.time()
            if random.random() <= 0.5:
                self.firmware.left_side_turn(twin_turn=True, running_speed=75)
            else:
                self.firmware.right_side_turn(twin_turn=True, running_speed=75)
            while time.time() - turn_start < 7:
                pass
            self.turn_issued = False
            self.approach_escape_complete = True

        elif self.turn_issued:
            # If a turn is currently in progress, skip the message
            log.info("Message ignored due to self.turn_issued is True")
            log.info("Message content: {}".format(str(package)))
            return

        elif action == "left":
            if package["turn_timed"]:
                turn_time = int(package["turn_turnTime"])
                self.turn_issued = True
                self.firmware.left_side_turn(run_forever=True, running_speed=75) # Turn forever
                self.timed_turn(turn_time)
                self.turn_issued = False
            else:
                angle = int(package["angle"])
                log.info("Turning left by {}.".format(angle))
                if angle < 0:
                    self.firmware.left_side_turn(running_speed=75, twin_turn=True)
                elif angle == 0:
                    pass
                else:
                    self.turn_issued = True
                    self.firmware.left_side_turn(running_speed=75, run_forever=False, run_by_deg=True, twin_turn=True, turn_degree=angle)
                    self.turn_issued = False
            self.random_issued = False
            self.stop_now = False
        elif action == "right":
            if package["turn_timed"]:
                turn_time = int(package["turn_turnTime"])
                self.turn_issued = True
                self.firmware.right_side_turn(run_forever=True, running_speed=75) # Turn forever
                self.timed_turn(time)
                self.turn_issued = False
            else:
                angle = int(package["angle"])
                log.info("Turning right by {}.".format(angle))
                if angle < 0:
                    self.firmware.right_side_turn(running_speed=75, twin_turn=True)
                elif angle == 0:
                    pass
                else:
                    self.turn_issued = True
                    self.firmware.right_side_turn(running_speed=75, run_forever=False, run_by_deg=True, twin_turn=True, turn_degree=angle)
                    self.turn_issued = False
            self.random_issued = False
            self.stop_now = False
        elif action == "forward":
            log.info("Going forward.")
            self.firmware.drive_forward(running_speed=100)
            self.random_issued = False
            self.stop_now = False
            # TODO: sensors
        elif action == "backward":
            log.info("Going backward.")
            self.firmware.drive_backward(running_speed=100)
            self.random_issued = False
            self.stop_now = False
            # TODO: sensors
        elif action == "random":
            if self.random_issued:
                log.info("Message ignored due to self.random_issued is True")
                log.info("Message content: {}".format(str(package)))
            else:
                self.stop_now = False
                self.random_issued = True
                log.info("Performing random movements.")
                self.random_movement()
                self.random_issued = False
            self.stop_now = False
        else:
            log.info("Invalid command.")
            self.firmware.stop()

    def random_movement(self):
        currently_turning = True
        while True:
            if currently_turning:
                # Turning mode
                turn_left = random.random() # Decide a direction to turn
                # Let wheels run forever
                if turn_left < 0.5:
                    self.firmware.right_side_turn(run_forever=True, running_speed=75)
                else:
                    self.firmware.left_side_turn(run_forever=True, running_speed=75)

                # Start a "timer" to listen for stop signal and measure time elapsed for the loop
                loop_start_time = time.time()
                turn_time = random.randint(1, 10) # Length of turn, in seconds
                log.info("Random turn, time={}".format(turn_time))

                stop_called = False
                # Loop here, until either stop_now is triggered or requested time has elapsed
                while time.time() - loop_start_time < turn_time:
                    front_sensor_read = 10000
                    try:
                        front_sensor_read = self.firmware.front_sensor.value()
                    except ValueError:
                        pass
                    if front_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                        # If sensor value is too low, back up, then leave this loop
                        self.firmware.drive_backward(running_speed=75)
                        backup_start = time.time()
                        backup_time = 5 # Total time to back up if obstacle encountered, in seconds
                        while time.time() - backup_start < backup_time:
                            # If obstacle encountered at the back, stop now and continue to go forward
                            back_sensor_read = 10000
                            try:
                                back_sensor_read = self.firmware.back_sensor.value()
                            except ValueError:
                                pass
                            if self.stop_now:
                                # Also listen for stop_now flag
                                self.firmware.stop()
                                self.stop_now = False
                                stop_called = True
                            if back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                                self.firmware.stop()
                                break

                        break
                    if self.stop_now:
                        print("Triggered stop_now, stopping random turning...")
                        self.firmware.stop() # Stop all motors
                        self.stop_now = False
                        stop_called = True

                if not stop_called:
                    log.info("Switching to random forward driving.")
                    while True:
                        try:
                            front_sensor_read = self.firmware.front_sensor.value()
                            back_sensor_read = self.firmware.back_sensor.value()
                        except ValueError:
                            pass
                        if front_sensor_read < self.firmware.sensor_obstacle_threshold * 10 and back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                            # Robot stuck, stop and send distress signal
                            self.firmware.stop()
                            self.distress_called = time.time()
                        else:
                            break
                    currently_turning = False
                else:
                    break
            else:
                # Driving forward forever
                self.firmware.drive_forward(run_forever=True, running_speed=100)

                loop_start_time = time.time()
                move_time = random.randint(1, 20) # Length of forward drive, in seconds
                log.info("Random forward drive, time={}".format(move_time))

                stop_called = False

                # Loop here, until either stop_now is triggered, sensor value is below threshold or requested time has elapsed
                while time.time() - loop_start_time < move_time:
                    front_sensor_read = 10000
                    try:
                        front_sensor_read = self.firmware.front_sensor.value()
                    except ValueError:
                        pass
                    if front_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                        # If sensor value is too low, back up, then leave this loop
                        self.firmware.drive_backward(running_speed=75)
                        backup_start = time.time()
                        backup_time = 5 # Total time to back up if obstacle encountered, in seconds
                        while time.time() - backup_start < backup_time:
                            # If obstacle encountered at the back, stop now and continue to turn
                            back_sensor_read = 10000
                            try:
                                back_sensor_read = self.firmware.back_sensor.value()
                            except ValueError:
                                pass
                            if self.stop_now:
                                # Also listen for stop_now flag
                                self.firmware.stop()
                                self.stop_now = False
                                stop_called = True
                            if back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                                self.firmware.stop()
                                break

                        break
                    if self.stop_now:
                        # Stop the random walk now
                        print("Triggered stop_now, stopping random turning...")
                        self.firmware.stop() # Stop all motors
                        # TODO: what happens next?
                        self.stop_now = False
                        stop_called = True

                if not stop_called:
                    log.info("Switching to random turning.")
                    while True:
                        try:
                            front_sensor_read = self.firmware.front_sensor.value()
                            back_sensor_read = self.firmware.back_sensor.value()
                        except ValueError:
                            pass
                        if front_sensor_read < self.firmware.sensor_obstacle_threshold * 10 and back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                            # Robot stuck, stop and send distress signal
                            self.firmware.stop()
                            self.distress_called = time.time()
                        else:
                            break
                    currently_turning = True
                else:
                    break

    # Invoked when the plant is reached - turn, extend arms, etc.
    def approached_routine(self):
        self.firmware.raise_arm()
        approach_start = time.time()
        while time.time() - approach_start < 10:
            try:
                front_sensor_read = self.firmware.front_sensor.value()
                if front_sensor_read < 75 and front_sensor_read > 50:
                    self.firmware.stop()
                    break
                elif front_sensor_read < 50:
                    self.firmware.drive_backward(running_speed=75)
                else:
                    self.firmware.drive_forward(running_speed=75)
            except ValueError:
                continue

        if time.time() - approach_start > 10:
            log.info("Approach timeout, retreat.")
            self.firmware.lower_arm()
            self.retry_approach_routine()
            self.approach_complete = True
            self.approach_problem = True
            return

        self.firmware.right_side_turn(run_by_deg=True, turn_degree=15, run_forever=False, running_speed=75)
        time.sleep(5)

        self.firmware.drive_backward(run_forever=False, running_speed=75, running_time=10)

        self.firmware.lower_arm()
        self.approach_complete = True

    def retry_approach_routine(self):
        self.firmware.drive_backward(running_speed=100)
        backup_start = time.time()
        backup_time = 10
        while time.time() - backup_start < backup_time:
            try:
                back_sensor_read = self.firmware.back_sensor.value()
                if back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                    break
            except ValueError:
                continue

        self.firmware.stop()
        self.retry_complete = True

    def timed_turn(self, turn_time):
        turn_start_time = time.time()
        log.info("Timed turn, time={}".format(turn_time))

        stop_called = False
        # Loop here, until either stop_now is triggered or requested time has elapsed
        while time.time() - turn_start_time < turn_time:
            front_sensor_read = 10000
            try:
                front_sensor_read = self.firmware.front_sensor.value()
            except ValueError:
                pass
            if front_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                # If sensor value is too low, back up, then leave this loop
                self.firmware.drive_backward(running_speed=75)
                backup_start = time.time()
                backup_time = 5 # Total time to back up if obstacle encountered, in seconds
                while time.time() - backup_start < backup_time:
                    # If obstacle encountered at the back, stop now and continue to go forward
                    back_sensor_read = 10000
                    try:
                        back_sensor_read = self.firmware.back_sensor.value()
                    except ValueError:
                        pass
                    if self.stop_now:
                        # Also listen for stop_now flag
                        self.firmware.stop()
                        self.stop_now = False
                        stop_called = True
                    if back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                        self.firmware.stop()
                        break

                break
            if self.stop_now:
                print("Triggered stop_now, stopping timed turning...")
                self.firmware.stop() # Stop all motors
                self.stop_now = False
                stop_called = True

        if not stop_called:
            # Check whether the robot is stuck - send a message if stuck until resolved, else continue
            while True:
                try:
                    front_sensor_read = self.firmware.front_sensor.value()
                    back_sensor_read = self.firmware.back_sensor.value()
                except ValueError:
                    pass
                if front_sensor_read < self.firmware.sensor_obstacle_threshold * 10 and back_sensor_read < self.firmware.sensor_obstacle_threshold * 10:
                    # Robot stuck, stop and send distress signal
                    self.firmware.stop()
                    self.distress_called = time.time()
                else:
                    break
        else:
            pass

        # Timer expired, stop the robot
        log.info("Finished turning, stopping.")
        self.firmware.stop()

def socket_sender_establish_loop(client, loop):
    asyncio.set_event_loop(loop)
    client.connect(sender=True)

def socket_receiver_establish_loop(client, loop):
    asyncio.set_event_loop(loop)
    client.connect(sender=False)

@asyncio.coroutine
def socket_error_message_loop(msg):

    while True:
        try:
            ws = yield from websockets.connect("ws://10.42.0.1:19221", ping_interval=None)
            break
        except ConnectionRefusedError:
            # Connection refused, repeat trying in a few seconds
            log.warn("Connection to port {} refused, trying again in 5 seconds.".format(19221))
            yield from asyncio.sleep(5)
            continue

    try:
        error_package = {
                            "type": "error",
                            "message": msg,
                            "severity": 3
                        }
        yield from ws.send(json.dumps(error_package))
    finally:
        yield from ws.close()
        sys.exit(1)


def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    try:
        ev3 = EV3_Client()

        try:
            ws_receiver = asyncio.new_event_loop()
            ws_receiver_thread = threading.Thread(
                name="ws_receiver_thread",
                target=socket_receiver_establish_loop,
                args=(ev3, ws_receiver,),
                daemon=True,
            )
            ws_receiver_thread.start()

            ws_sender = asyncio.new_event_loop()
            ws_sender_thread = threading.Thread(
                name="ws_sender_thread",
                target=socket_sender_establish_loop,
                args=(ev3, ws_sender,),
                daemon=True,
            )
            ws_sender_thread.start()

            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            ev3.firmware.stop()
    except IOError as e:
        log.error("\033[1;37;41m[EV3] Error encountered, attempting to send message to Pi...\033[0m")
        log.info("[EV3] Error details: {}".format(str(e)))
        asyncio.get_event_loop().run_until_complete(socket_error_message_loop(str(e)))


if __name__ == "__main__":
    main()