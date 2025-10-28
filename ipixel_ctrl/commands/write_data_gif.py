#!/usr/bin/env python3

# Import modules
import argparse
from .. import image
from .. import utils
from . import common

def args(subparser):
    arg = subparser.add_parser(
        "write-gif",
        help = 'write gif data',
        description = '',
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 120)
    )
    arg.add_argument(
        "--buffer",
        dest = 'start_buffer',
        metavar="no.",
        type = lambda x: int(x, 0),
        required = True,
        help = 'write start buffer number (0x01 - 0xFF)'
    )
    arg.add_argument(
        "--make-from-image",
        dest = 'make_from_image',
        type = int,
        default = 0,
        help = 'make animation from image files, specify duration (msec), enable on > 0'
    )
    arg.add_argument(
        "--auto-resize",
        dest = 'auto_resize',
        default = False,
        action = "store_true",
        help = 'resize image to device width/height'
    )
    arg.add_argument(
        "--device-width",
        dest = 'device_width',
        type = int,
        default = 96,
        help = 'T.B.D.'
    )
    arg.add_argument(
        "--device-height",
        dest = 'device_height',
        type = int,
        default = 32,
        help = 'T.B.D.'
    )
    arg.add_argument(
        "--anchor",
        type = lambda x: int(x, 0),
        default = 0x33,
        help = 'T.B.D.'
    )
    arg.add_argument(
        "image_file",
        nargs = "+",
        help = 'image file (gif)'
    )

def make(params: argparse.Namespace) -> list[bytes]:
    # Check arguments
    if params is None:
        raise ValueError("Invalid arguments")
    if params.image_file is None or len(params.image_file) < 1:
        raise ValueError("At least one image file must be specified. None was given")
    if params.start_buffer < 1 or params.start_buffer > 255:
        raise ValueError("The buffer must be between 1 and 255")

    if params.make_from_image > 0:
        # Set data
        data_gif  = image.make_animation_from_image_file_for_device(params.image_file, params.device_width, params.device_height, params.anchor, params.make_from_image, getattr(params, 'auto_resize', False))
        data_size = len(data_gif)
        data_csum = utils.crc32(data_gif)

        # Make payload
        payload  = bytes([0x00])
        payload += data_size.to_bytes(4, 'little')
        payload += data_csum.to_bytes(4, 'little')
        payload += bytes([0x00])
        payload += bytes([ params.start_buffer ])
        payload += data_gif
        return [ common.make_payload(0x0003, payload) ]

    result = []
    for i in range(len(params.image_file)):
        if (params.start_buffer + i) > 0xFF:
            break

        # Set data
        data_gif  = image.read_animation_file_for_device(params.image_file[i], params.device_width, params.device_height, params.anchor, getattr(params, 'auto_resize', False))
        data_size = len(data_gif)
        data_csum = utils.crc32(data_gif)

        # Make payload
        payload  = bytes([0x00])
        payload += data_size.to_bytes(4, 'little')
        payload += data_csum.to_bytes(4, 'little')
        payload += bytes([0x00])
        payload += bytes([ params.start_buffer + i ])
        payload += data_gif
        result.append(common.make_payload(0x0003, payload))

    return result
