#!/usr/bin/env python3

PAYLOAD_LEN_SIZE = 0x02
PAYLOAD_CMD_SIZE = 0x02

def make_payload(command: int, data:bytes) -> bytes:
    length = PAYLOAD_LEN_SIZE + PAYLOAD_CMD_SIZE + len(data)
    return length.to_bytes(PAYLOAD_LEN_SIZE, 'little') + command.to_bytes(PAYLOAD_CMD_SIZE, 'little') + data
