class MockSensor:
    connected = True
    is_running = True

    def __init__(self, name):
        self.name = name

class MockMotor:
    connected = True
    is_running = True

    def __init__(self, name):
        self.name = name

    def run_forever(self, speed_sp=0):
        print("Running at speed {} forever".format(speed_sp))

    def run_timed(self, speed_sp=0, time_sp=0):
        print("Running at speed {} for {}".format(speed_sp, time_sp))

    def stop(self, stop_action):
        print("Stopping with action {}".format(stop_action))

class LargeMotor(MockMotor):
    pass

class MediumMotor(MockMotor):
    pass

class UltrasonicSensor(MockSensor):
    pass
