#!/usr/bin/env python3

# Import modules
import argparse
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "brightness",
        help = 'set LED brightness',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "brightness",
        type = int,
        help = 'brightness (1 - 100)'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if params.brightness < 1 or params.brightness > 100:
        raise ValueError("The value must be between 1 and 100")

    # Make payload
    return [ common.make_payload(0x8004, bytes([ params.brightness ])) ]
