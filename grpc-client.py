from __future__ import print_function

import logging
import time
import os

import grpc

import control_pb2
import control_pb2_grpc


def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    host = os.getenv("HOST", "robot:50051") # HOST=localhost:50051 when you want to test
    with grpc.insecure_channel(host) as channel:
        stub = control_pb2_grpc.EV3Stub(channel)
        
        while True:
            print("Waiting 1s")
            time.sleep(1)
            print("Sending move")
            move = control_pb2.MoveRequest(
                direction=control_pb2.MoveRequest.FORWARD
            )

            stub.Move(move)


if __name__ == '__main__':
    logging.basicConfig()
    run()
