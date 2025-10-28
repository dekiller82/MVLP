#!/usr/bin/env python3

# Import modules
import argparse
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "screen",
        help = 'set visible screen.',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "screen",
        type = int,
        help = 'screen (1 - 9)'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if params.screen < 1 or params.screen > 9:
        raise ValueError("The value must be between 1 and 9")

    # Make payload
    return [ common.make_payload(0x8007, bytes([ params.screen ])) ]
