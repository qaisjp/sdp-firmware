# sdp-firmware
Firmware for GrowBot.

## Protocol Buffers

**When you update protos/control.proto you need to update the corresponding Python files.**

To do this, just run this command: `python -m grpc_tools.protoc -Iprotos --python_out=. --grpc_python_out=. protos/control.proto`

This requires the `grpcio-tools` package to be installed.
