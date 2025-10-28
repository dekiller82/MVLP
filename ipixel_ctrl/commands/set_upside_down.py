#!/usr/bin/env python3

# Import modules
import argparse
from .. import arguments
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "upside-down",
        help = 'set upside-down visibility',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "upside_down",
        metavar="switch",
        type = arguments.helper_convert_bool,
        help = 'Choose on or off'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")

    # Make payload
    return [ common.make_payload(0x8006, bytes([ 0x01 if params.upside_down else 0x00 ])) ]
