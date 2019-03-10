from concurrent import futures

import logging
import grpc
import firmware
import time
import google.protobuf

import control_pb2
import control_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class EV3Servicer(control_pb2_grpc.EV3Servicer):
    """Provides methods that implement functionality of EV3 server."""

    def __init__(self):
        self.gb = firmware.GrowBot(-1, -1)

    def Move(self, request, context):
        direction = request.direction
        if direction == control_pb2.MoveRequest.FORWARD:
            self.gb.drive_forward()
        elif direction == control_pb2.MoveRequest.BACKWARD:
            self.gb.drive_backward()
        elif direction == control_pb2.MoveRequest.LEFT:
            self.gb.left_side_turn()
        elif direction == control_pb2.MoveArmRequest.RIGHT:
            self.gb.right_side_turn()

        return google.protobuf.empty_pb2.Empty()

    def MoveArm(self, request, context):
        direction = request.direction

        if direction == control_pb2.MoveArmRequest.UP:
            self.gb.raise_arm()
        elif direction == control_pb2.MoveArmRequest.DOWN:
            self.gb.lower_arm()
        elif direction == control_pb2.MoveArmRequest.STOP:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            context.set_details('Method not implemented!')
            raise NotImplementedError('Method not implemented!')

        return google.protobuf.empty_pb2.Empty()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    control_pb2_grpc.add_EV3Servicer_to_server(
        EV3Servicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()

    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    logging.basicConfig()
    serve()
