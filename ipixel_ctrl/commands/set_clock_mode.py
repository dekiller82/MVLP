#!/usr/bin/env python3

# Import modules
import argparse
from datetime import datetime
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "clock-mode",
        help = 'set clock mode',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "--style",
        dest = 'clock_mode_style',
        type = int,
        default = 1,
        help = 'clock style (1 - 8)'
    )
    arg.add_argument(
        "--show-date",
        dest = 'clock_mode_show_date',
        default = False,
        action = "store_true",
        help = 'show date'
    )
    arg.add_argument(
        "--show-24h",
        dest = 'clock_mode_show_24h',
        default = False,
        action = "store_true",
        help = 'show 24-hour clock'
    )
    arg.add_argument(
        "--date",
        metavar = "YYYY-mm-dd",
        dest = 'clock_mode_date',
        default = '2000-01-01',
        help = 'clock date'
    )
    arg.add_argument(
        "--time",
        metavar = "HH:MM:SS",
        dest = 'clock_mode_time',
        default = '00:00:00',
        help = 'clock time'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if params.clock_mode_style < 1 or params.clock_mode_style > 8:
        raise ValueError("The style must be between 1 and 8")

    # Set Data
    date = datetime.strptime(params.clock_mode_date, "%Y-%m-%d").date()
    time = datetime.strptime(params.clock_mode_time, "%H:%M:%S").time()

    # Make payload
    result = []
    payload  = bytes([ time.hour ])
    payload += bytes([ time.minute ])
    payload += bytes([ time.second ])
    payload += bytes([ 0x00 ])
    result.append(common.make_payload(0x8001, payload))
    payload  = bytes([ params.clock_mode_style ])
    payload += bytes([ 0x01 if params.clock_mode_show_24h else 0x00 ])
    payload += bytes([ 0x01 if params.clock_mode_show_date else 0x00 ])
    payload += bytes([ date.year % 100 ])
    payload += bytes([ date.month ])
    payload += bytes([ date.day ])
    payload += bytes([ date.isoweekday() ])
    result.append(common.make_payload(0x0106, payload))
    return result
