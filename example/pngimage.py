import logging
import pymirror
import pygame

#
# A module for displaying a PNG image
#
# YAML configuration
#  top: int - Y coordinate
#  left: int - X coordinate
#  width: int - Width of image
#  height: int - Height of image
#  image_name: str - Name of image relative to you module directory
#
# Optional YAML configuration
#  x_offset: int - X offset of image, for fine adjustments
#  y_offset: int - Y offset of image, for fine adjustments
#  invert: bool - Invert pixels of image
#

# Encapsulating the module data in an object allows for us to have more than one
# image on screen.
class png_image:
    _mod_info: dict[str: str|int]
    _image: pygame.Surface
    _width: int
    _height: int
    _x_offset: int
    _y_offset: int
    def __init__(self, config: dict, image: pygame.Surface, width: int, height: int, x_offset: int, y_offset: int):
        self._config = config
        self._image = image
        self._width = width
        self._height = height
        self._x_offset = x_offset
        self._y_offset = y_offset


def init(mirror: pymirror.Mirror, config: dict[str: str]):
    logging.info(f"Hello world from the pngimage module with config {config}")
    invert = False
    x_offset = 0
    y_offset = 0
    if "x_offset" in config:
        x_offset = config["x_offset"]
    if "y_offset" in config:
        y_offset = config["y_offset"]
    if "invert" in config:
        invert = config["invert"]
    (image, width, height) = mirror.load_image(config["image_name"], invert = invert, width = config["width"])
    return png_image(config, image, width, height, x_offset, y_offset)


def draw(mirror: pymirror.Mirror, image: png_image):
    mirror.blit_image(image._image, image._x_offset, image._y_offset)
