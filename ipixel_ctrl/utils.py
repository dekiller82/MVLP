#!/usr/bin/env python3

# Import modules
from itertools import chain
import zlib

def dump_data(data: bytes) -> None:
    r"""Print binary data in a human-readable hex + offset format.

    This function outputs the input byte data in a hexdump-like table,
    showing 16 bytes per line with their offset. If the input is None
    or empty, it displays a placeholder line of '**'.

    :param data: The binary data to display as a hex dump.
    :return: None
    """

    # Header
    print("| Offset   | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 0A | 0B | 0C | 0D | 0E | 0F |")
    print("|----------+----+----+----+----+----+----+----+----+----+----+----+----+----+----+----+----+")
    # Body
    if data is None or len(data) == 0:
        print("| 00000000 |" + " ** |" * 16)
        return
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_bytes = ' | '.join(chain((f"{b:02X}" for b in chunk), ('**' for _ in range(16 - len(chunk)))))
        print(f"| {i:08X} | {hex_bytes} |")
    print('')

def crc32(data: bytes) -> int:
    r"""Compute CRC-32 checksum of the given binary data.

    This function returns a 32-bit unsigned CRC checksum for the input bytes,
    compatible with the standard CRC-32 algorithm used in formats like PNG.

    :param data: The binary data to compute the CRC-32 checksum for.
    :return: Unsigned 32-bit CRC value as an integer.
    """

    return zlib.crc32(data) & 0xFFFFFFFF

def read_binary_from_file(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()
