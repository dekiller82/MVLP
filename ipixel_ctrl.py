#!/usr/bin/env python3

# Import modules
import argparse
import asyncio
import sys
import ipixel_ctrl

# Module information
__title__        = "ipxel_ctrl"
__description__  = "Control iPixel LED without vendor app."
__url__          = 'https://www.sdolphin.jp'
__version__      = '1.0.0'
__build__        = 0x010000
__author__       = 'sdolphin'
__author_email__ = 'sdolphin@sdolphin.jp'
__license__      = "MIT"
__copyright__    = 'Copyright (C) 2025 sdolphin.jp'

# Send command
async def send_command(params: argparse.Namespace) -> int:
    # Scan devices
    if params.command =='scan':
        await ipixel_ctrl.bluetooth.scan()
        return 0

    # Check arguments
    if params.target is None or params.command is None:
        raise ValueError("No target or command are specified")
    if not params.command in ipixel_ctrl.arguments.COMMANDS.keys():
        raise ValueError("Unknown command specified")

    # Make payload
    payloads = ipixel_ctrl.arguments.COMMANDS[params.command](params)
    for payload in payloads:
        if params.verbose:
            print("Payload:")
            ipixel_ctrl.utils.dump_data(payload)

    # Send payload
    await ipixel_ctrl.bluetooth.send(params.target, payloads)

    return 0

# Entrypoint
def main() -> int:
    try:
        # Parse arguments
        args = ipixel_ctrl.arguments.parse(sys.argv[1:])
        # Send command
        asyncio.run(send_command(args))
    except (argparse.ArgumentError, argparse.ArgumentTypeError, ValueError) as e:
        print(f"{e}")
        return 1
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return 1

    return 0

# Run main() if run as script
if __name__ == '__main__':
    sys.exit(main())
