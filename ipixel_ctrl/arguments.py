#!/usr/bin/env python3

# Import modules
import argparse
from .commands import *

COMMANDS = {
    "expert": expert.make,
    "write-png": write_data_png.make,
    "write-gif": write_data_gif.make,
    "erase-data": erase_data.make,
    "diy-mode": set_diy_mode.make,
    "set-pixel": set_pixel.make,
    "clock-mode": set_clock_mode.make,
    "power": set_power.make,
    "default-mode": set_default_mode.make,
    "brightness": set_brightness.make,
    "upside-down": set_upside_down.make,
    "screen": set_screen.make,
    "prg-mode": set_prg_mode.make,
}

def helper_convert_bool(value: str) -> bool:
    if value.lower() == "on":
        return True
    elif value.lower() == "off":
        return False
    else:
        raise argparse.ArgumentTypeError("The value must be either 'on' or 'off'")

def helper_conver_pair(value: str) -> tuple[int, int]:
    try:
        x_str, y_str = value.split(",")
        return int(x_str), int(y_str)
    except ValueError:
        raise argparse.ArgumentTypeError("The value must be in the format: number,number")

def parse(argv: list[str]):
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )

    ## Global option
    parser.add_argument(
        "--verbose",
        default = False,
        action="store_true",
    )
    parser.add_argument(
        "--target",
        help = 'Devices\'s MAC address or UUID'
    )

    # Sub commands
    subcmd = parser.add_subparsers(
        dest = "command",
        metavar="command",
        required = True
    )
    subcmd.add_parser(
        "scan",
        help = 'scan ipixel color devices'
    )
    set_power.args(subcmd)
    set_brightness.args(subcmd)
    set_upside_down.args(subcmd)
    set_default_mode.args(subcmd)
    set_clock_mode.args(subcmd)
    set_diy_mode.args(subcmd)
    set_pixel.args(subcmd)
    set_prg_mode.args(subcmd)
    set_screen.args(subcmd)
    erase_data.args(subcmd)
    write_data_gif.args(subcmd)
    write_data_png.args(subcmd)
    expert.args(subcmd)

    ## Do parse
    return parser.parse_args(argv)
