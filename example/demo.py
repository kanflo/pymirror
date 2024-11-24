import logging
import pymirror
import pygame

"""A simple module that can have multiple instances.
"""

class demo:
    _mod_info: dict[str: str|int]
    _width: int
    _height: int
    _x_offset: int
    _y_offset: int
    def __init__(self, config):
        self._config = config


def init(mirror: pymirror.Mirror, config: dict[str: str]):
    logging.info('Hello world from the demo module with config %s' % config)
    return demo(config)


def draw(mirror: pymirror.Mirror, locals: any):
    del locals
    green: tuple[int, int, int] = (0, 255, 0)
    yellow: tuple[int, int, int] = (255, 255, 0)
    purple: tuple[int, int, int] = (255, 0, 255)
    mirror.draw_text("Left adjusted", 10, 30, green)
    mirror.draw_text("Center adjusted", mirror.width//2, 100, green, adjustment=pymirror.Adjustment.Center)
    mirror.draw_text("Right adjusted", mirror.width, 200, green, adjustment=pymirror.Adjustment.Right)

    mirror.draw_rect(100, 1000, 400, 400, yellow)
    mirror.draw_text("This text flows inside the bounding box", 100, 1000, green, width=400)

    mirror.draw_rect(0, 900, mirror.width-1, 20, yellow)

    mirror.fill_rect(0, 930, mirror.width-1, 20, purple)
