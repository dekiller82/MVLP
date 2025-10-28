#!/usr/bin/env python3

# Import modules
import argparse
from . import common

def args(subparser):
    subparser.add_parser(
        "default-mode",
        help = 'set default mode',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")

    # Make payload
    return [ common.make_payload(0x8003, bytes([])) ]
