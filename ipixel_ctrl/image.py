#!/usr/bin/env python3

# Import modules
import io
from PIL import Image, ImageSequence

def resize_image(img: Image.Image, width: int, height: int) -> Image.Image:
    """
    Resizes an image to the specified width and height.

    :param img: The source PIL Image object.
    :param width: The target width.
    :param height: The target height.
    :return: The resized PIL Image object.
    """
    # If dimensions are invalid, return original image
    if width <= 0 or height <= 0:
        return img
    return img.resize((width, height), Image.Resampling.LANCZOS)

def clip_and_anchor_for_image(img: Image.Image, max_width: int, max_height: int, anchor: int) -> Image.Image:
    if anchor == 0x00:
        return img

    # Clipp
    clipped = img.crop((0, 0, min(img.size[0], max_width), min(img.size[1], max_height)))

    # Adjust Left-Right
    if anchor & 0x01 and not anchor & 0x02:
        offset_x = 0
    elif anchor & 0x02 and not anchor & 0x01:
        offset_x = max_width - clipped.width
    else:
        offset_x = max((max_width - clipped.width) // 2, 0)

    # Adjust Top-Bottom
    if anchor & 0x10 and not anchor & 0x20:
        offset_y = 0
    elif anchor & 0x02 and not anchor & 0x20:
        offset_y = max_height - clipped.height
    else:
        offset_y = max((max_height - clipped.height) // 2, 0)

    # Make result
    result = Image.new("RGBA", (max_width, max_height), (0, 0, 0, 0))
    result.paste(clipped.convert("RGBA"), (offset_x, offset_y))
    return result

def read_image_file_for_device(path: str, max_width: int, max_height: int, anchor: int, auto_resize: bool = False) -> bytes:
    r"""Load an image and prepare it for a device-specific PNG format.

    The image is clipped from the top-left if it exceeds the target size,
    and placed onto a transparent RGBA canvas of the specified dimensions.
    The content is aligned according to anchor flags, and exported as PNG
    byte data, suitable for transmission to a device that expects precise
    positioning and format.

    Anchor bits:
        - 0x01: align left
        - 0x02: align right
        - both unset or both set → horizontal center
        - 0x10: align top
        - 0x20: align bottom
        - both unset or both set → vertical center

    :param path: Path to the image file.
    :param max_width: Output image width for the device.
    :param max_height: Output image height for the device.
    :param anchor: Bitwise flags controlling image alignment.
    :param auto_resize: If True, resize the image to fit device dimensions.
    :return: PNG image data as bytes.
    """

    with Image.open(path) as img:
        processed_img = img.convert("RGBA")
        if auto_resize:
            processed_img = resize_image(processed_img, max_width, max_height)
        
        result = clip_and_anchor_for_image(processed_img, max_width, max_height, anchor)

        buf = io.BytesIO()
        result.save(buf, format = 'PNG', optimize = False, compress_level = 6, icc_profile = None)
        return buf.getvalue()

def read_animation_file_for_device(path: str, max_width: int, max_height: int, anchor: int, auto_resize: bool = False) -> bytes:
    frames = []
    with Image.open(path) as img:
        # Edit
        for frame in ImageSequence.Iterator(img):
            processed_frame = frame.convert("RGBA")
            if auto_resize:
                processed_frame = resize_image(processed_frame, max_width, max_height)
            frames.append(clip_and_anchor_for_image(processed_frame, max_width, max_height, anchor))
        if len(frames) < 1:
            raise ValueError("no frame GIF")
        # Save
        buf = io.BytesIO()
        frames[0].save(
            buf,
            format = "GIF",
            save_all = True,
            append_images = frames[1:],
            loop = img.info.get("loop", 0),
            duration = img.info.get("duration", 100),
            disposal = 2
        )
        return buf.getvalue()

def make_animation_from_image_file_for_device(paths: list[str], max_width: int, max_height: int, anchor: int, duration: int, auto_resize: bool = False) -> bytes:
    # Load PNG files
    png_files = []
    for path in paths:
        png_files.append(read_image_file_for_device(path, max_width, max_height, anchor, auto_resize))
    if len(png_files) < 1:
        raise ValueError("no PNG specified")

    # Make GIF file
    frames = [ Image.open(io.BytesIO(f)) for f in png_files]
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format = "GIF",
        save_all = True,
        append_images = frames[1:],
        loop = 0,
        duration = duration,
        disposal = 2
    )
    return buf.getvalue()

def make_joined_image_file_for_device(paths: list[str], max_width: int, max_height: int, anchor: int, auto_resize: bool = False) -> bytes:

    joined_width = 0
    joined_height = 0

    # Load PNG files
    png_files = []
    for path in paths:
        img = Image.open(path)
        joined_width += img.size[0]
        joined_height = max(joined_height, img.size[1])
        png_files.append(img)
    if len(png_files) < 1:
        raise ValueError("no PNG specified")

    # Join
    joined = Image.new("RGBA", (joined_width, joined_height), (0, 0, 0, 0))
    joined_x = 0
    for img in png_files:
        joined.paste(img, (joined_x, 0))
        joined_x += img.size[0]
    
    processed_img = joined
    if auto_resize:
        processed_img = resize_image(processed_img, max_width, max_height)

    result = clip_and_anchor_for_image(processed_img, max_width, max_height, anchor)
    buf = io.BytesIO()
    result.save(buf, format = 'PNG', optimize = False, compress_level = 6, icc_profile = None)
    return buf.getvalue()
