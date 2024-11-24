import logging
import datetime
import pymirror

_config: dict[str: str|int]

"""A simple module that only can have one single instance but serves as an example of how very little
code you need to write in order to display something onscreen.
"""

def init(mirror: pymirror.Mirror, config: dict[str: str]):
    del mirror
    global _config
    _config = config
    logging.info(f"Hello world from the time module with config {config}")
    return None


def draw(mirror: pymirror.Mirror, locals: any):
    del locals
    global _config
    now = datetime.datetime.now()
    str = f"{now.hour:02d}:{now.minute:02d}"
    mirror.draw_text(str, _config["width"], 0, adjustment = pymirror.Adjustment.Center, size = _config["font_size"])
