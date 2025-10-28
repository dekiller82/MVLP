#!/usr/bin/env python3

# Import modules
import argparse
from .. import arguments
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "set-pixel",
        help = 'set pixel',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "--pos",
        dest = 'pixel_pos',
        metavar="x,y",
        type = arguments.helper_conver_pair,
        required = True,
        help = 'pixel position'
    )
    arg.add_argument(
        "--color",
        dest = 'pixel_color',
        metavar="0xRRGGBB",
        type = lambda x: int(x, 0),
        default = 0xFFFFFF,
        help = 'pixel color'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")

    # Make payload
    payload  = params.pixel_color.to_bytes(4, 'big')
    payload += bytes([ params.pixel_pos[0] ])
    payload += bytes([ params.pixel_pos[1] ])
    return [ common.make_payload(0x0105, payload) ]
