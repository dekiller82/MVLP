#!/usr/bin/env python3

# Import modules
import argparse
from .. import arguments
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "diy-mode",
        help = 'set DIY mode',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "diy_mode",
        metavar="switch",
        type = arguments.helper_convert_bool,
        help = 'Choose on or off'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")

    # Make payload
    payload  = bytes([ 0x01 if params.diy_mode else 0x00 ])
    return [ common.make_payload(0x0104, payload) ]
