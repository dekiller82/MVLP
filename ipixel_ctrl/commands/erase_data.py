#!/usr/bin/env python3

# Import modules
import argparse
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "erase-data",
        help = 'erase buffer data',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "--all",
        dest = 'erase_all',
        default = False,
        action="store_true",
        help = 'erase all buffer'
    )
    arg.add_argument(
        "buffer",
        type = lambda x: int(x, 0),
        nargs = "*",
        help = 'buffer number (0x01 - 0xFF)'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if not params.erase_all and ( params.buffer is None or len(params.buffer) < 1):
        raise ValueError("At least one buffer number must be specified. None was given")

    # Make payload
    if params.erase_all:
        payload  = 0x00FF.to_bytes(2, 'little')
        payload += bytes(range(0x01, 0xFF))
    else:
        payload  = len(params.buffer).to_bytes(2, 'little')
        payload += bytes(params.buffer)

    return [ common.make_payload(0x0102, payload) ]
