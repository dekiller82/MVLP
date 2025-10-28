#!/usr/bin/env python3

# Import modules
import argparse

def args(subparser):
    arg = subparser.add_parser(
        "expert",
        help = 'send data manually',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "expert_data",
        help = 'payload (AABBCC or AA BB CC)'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if params.expert_data is None or len(params.expert_data) < 1:
        raise ValueError("At least one byte must be specified. None was given")

    # Make payload
    return [bytes.fromhex(params.expert_data)]
