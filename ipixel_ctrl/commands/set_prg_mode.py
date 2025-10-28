#!/usr/bin/env python3

# Import modules
import argparse
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "prg-mode",
        help = 'set program mode',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "buffer",
        type = lambda x: int(x, 0),
        nargs = "+",
        help = 'buffer number (0x01 - 0xFF)'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if params.buffer is None or len(params.buffer) < 1:
        raise ValueError("At least one buffer number must be specified. None was given")

    # Make payload
    payload  = len(params.buffer).to_bytes(2, 'little')
    payload += bytes(params.buffer)
    return [ common.make_payload(0x8008, payload) ]
