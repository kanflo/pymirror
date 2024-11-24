"""
The MIT License (MIT)

Copyright (c) 2019-2024 Johan Kanflo (github.com/kanflo)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from typing import *
from enum import Enum
import sys
import json
import logging
import datetime
import time
import configparser
import traceback as tb
import os
import pathlib
import pymirror.sunrise as sunrise
try:
    import pygame
    import pygame.display
except ImportError:
    print("PyGame missing, see docs/readme.rst")
    sys.exit(1)
try:
    from mqttwrapper import run_script
except ImportError:
    print("Missing mqttwrapper:\npython -m pip install -r requirements.txt")
    sys.exit(1)

__all__ = ["run", "Mirror"]

config: dict[str: str] = None

class Adjustment(Enum):
    Left = 1
    Center = 2
    Right = 3

class Module():
    """A class that describes a module"""
    def __init__(self, mirror: "Mirror", name: str, source: str, config: dict[str: str], top: int, left: int, width: int, height: int):
        """Initialize this module

        Args:
            mirror (Mirror): The mirror we're showing this module on
            name (str): Name of module
            source (str): Path to module, relative your config file
            config (dict): Loaded config
            top (int): Top position
            left (int): Left position
            width (int): Width of module
            height (int): Height of module
        """
        logging.debug(f"Init module {name}")
        self.mirror = mirror
        self.name: str = name
        self.source: str = source
        self.config: dict[str, str] = config
        self.top: int = top
        self.left: int = left
        self.width: int = width
        self.height: int = height
        self.search_paths: list[str] = mirror.search_paths
        self.active: bool = True
        self.crashed_at: datetime.datetime = None
        self.exception: Exception|None = None
        self.locals: dict[str: str|int] = {}

    def load(self):
        """Load module"""
        module_name: str = str(self.source).replace(".py", "").replace("/", ".")
        logging.info(f"Loading module {self.name} from {self.source}")
        here: str = os.getcwd()

        for path in list(self.search_paths):
            try:
                sys.path.append(str(path))
                os.chdir(str(path))
                self._module = __import__(module_name, fromlist=[""])
                break
            except ModuleNotFoundError as e:
                logging.error(f"Module {module_name} not found", exc_info=e)
                self._module = None
            except FileNotFoundError as e:
                logging.error(f"File {module_name} not found", exc_info=e)
                pass
            finally:
                sys.path.remove(str(path))
        new_path: pathlib.path = path / self.source
        if not new_path.is_dir():
            new_path = new_path.parent
        if self._module and new_path not in self.search_paths:
            # Location of module is a search path allowing a module to load images
            # from it's own directory.
            self.search_paths.append(new_path)
        os.chdir(here)
        if self._module is None:
            logging.error(f"Failed to load module {module_name}")
            sys.exit(1)


    def draw(self):
        """Virtual methd"""
        pass

class Mirror():
    """ A class that describes a mirror. The Mirror object is passed to every module
    and is used for drawing.
    """
    fonts = {}
    def __init__(self, config_file: str, fps: int|None = None, fullscreen: bool|None = None, scale: float|None = None, module_filter: str = None, x_pos: int|None = None, y_pos: int|None = None, frame_debug: bool = False):
        """Initialize mirror

        Args:
            config_file (str): Path and name of config file
            fps (int | None, optional): FPS to run module at. Defaults to None.
            fullscreen (bool | None, optional): True to run in fullscreen mode, False to run in windowed mode. Defaults to None.
            scale (float | None, optional): Scale, a float > 0 and <= 1.0. Useful for developing on smaller displays. Defaults to None.
            module_filter (str, optional): Name of single module that will be loaded, others will not. Defaults to None.
            x_pos (int | None, optional): X position of window, if running in windowed mode. Defaults to None.
            y_pos (int | None, optional): Y position of window, if running in windowed mode. Defaults to None.
            frame_debug (bool, optional): If True, draw a bounding box for all modules. Defaults to False.
        """
        self.fps: float = fps
        self.fullscreen: bool = fullscreen
        self.scale: float = scale
        self.x_pos: int = x_pos
        self.y_pos: int = y_pos
        self.frame_debug: bool = frame_debug
        self.module_filter: str = module_filter

        self.latitude: str|None = None
        self.longitude: str|None = None
        self.font_name: str|None = None
        self.font_size: int|None = None

        self.modules: list[Module] = []
        self.current_module: Module|None = None
        self.cache_dir: pathlib.Path|None = None
        # Used by the splash screen
        self.splashing: bool = True
        self.splashing_past_module_init: bool = False
        self.python_icon: pygame.Surface = None
        self.icon_width: int|None = None
        self.debug_mqtt_broker : str|None = None
        # Search paths when loading modules, fonts, graphics and so on
        config_file: pathlib.Path = pathlib.Path(config_file).absolute()
        self.search_paths: list[str] = [config_file.parent, pathlib.Path(__file__).parent.absolute()]
        logging.debug(f"Loading config from {config_file}")

        self._load_config(config_file)

        if self.x_pos is not None and self.y_pos is not None:
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{self.x_pos},{self.y_pos}"

        pygame.init()
        info = pygame.display.Info()
        if not self.width:
            self.width = info.current_w
        if not self.height:
            self.height = info.current_h

        if fullscreen:
            self.screen = pygame.display.set_mode((int(self.scale * self.width), int(self.scale * self.height)), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
            #pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
        else:
            self.screen = pygame.display.set_mode((int(self.scale * self.width), int(self.scale * self.height)))

        if "arm" in os.uname().machine:
            # Always hide the cursor on Pis
            pygame.mouse.set_visible(False)


    def _load_config(self, config_name: pathlib.Path) -> bool:
        """Load pymirror config

        Returns:
            Dict consisting of the following keys frin the module config section
                name: str         name of module
                source: str       source file for module
                top: int          top location of module
                left: int         left location of module
                width: int        width of module
                height: int       height of module
                conf: Dict        All other fields from the module configuration section

            The following fields are inherited from the app config, if set in app config
                latitude: float   Latitude of mirror
                longitude: float  Longitude of mirror

            The following fields will be copied from the app config unless already set by the module config
                font_size: int    Font size
                font_name: str    Font file name
        """
        logging.debug("Loading config")
        app_conf = {"modules" : []}
        self.config = {}
        config = configparser.ConfigParser()
        try:
            with open(config_name) as f:
                # Weeell, config.read(...) does not complain if the config file is missing...
                pass
            config.read(config_name, encoding="utf-8")
        except Exception as error:
            print(f"Failed to read config file {error}")
            sys.exit(1)

        for s in config:
            if s == "mirrorconfig":
                try:
                    for c in config.items(s):
                        app_conf[c[0]] = string2whatever(c[1])
                        if c[0] == "scale" and self.scale is None:
                            self.scale = string2whatever(c[1])
                        elif c[0] == "fullscreen" and self.fullscreen is None:
                            self.fullscreen = string2whatever(c[1])
                        elif c[0] == "screen_width":
                            self.width = string2whatever(c[1])
                        elif c[0] == "screen_height":
                            self.height = string2whatever(c[1])
                        elif c[0] == "longitude":
                            self.longitude = string2whatever(c[1])
                        elif c[0] == "latitude":
                            self.latitude = string2whatever(c[1])
                        elif c[0] == "timezone":
                            self.timezone = string2whatever(c[1])
                        elif c[0] == "font_name":
                            self.font_name = string2whatever(c[1])
                        elif c[0] == "font_size":
                            self.font_size = string2whatever(c[1])
                        elif c[0] == "cache_dir":
                            self.cache_dir = config_name.parent / pathlib.Path(string2whatever(c[1]))
                        elif c[0] == "debug_mqtt_broker":
                            self.debug_mqtt_broker = string2whatever(c[1])
                        elif c[0] == "fps":
                            self.fps = string2whatever(c[1])
                        else:
                            self.config[c[0]] = c[1]

                except Exception as e:
                    logging.error("Exception occurred when reading mirror config", exc_info=e)
            elif s == "DEFAULT":
                pass
            else:  # Loading modules
                module_name = s
                if self.module_filter is not None and self.module_filter != module_name:
                    logging.info(f"Skipping module {module_name}")
                    continue
                try:
                    module = {"name" : s}
                    c = config.items(s)
                    module_conf = {}
                    module_source = config.get(s, "source")
                    top = int(config.get(s, "top"))
                    left = int(config.get(s, "left"))
                    width = int(config.get(s, "width"))
                    height = int(config.get(s, "height"))
                    logging.debug(f"Module bounds: {top},{left}, {width},{height}")

                    if top < 0:
                        top = self.height + top
                    if height < 0:
                        height = self.height + height
                    if left < 0:
                        left = self.width + left
                    if width < 0:
                        width = self.width + width

                    # todo: inherit app settings
                    for a in c:
                        module_conf[a[0]] = string2whatever(a[1])
                    module_conf["font_name"] = self.font_name
                    module_conf["font_size"] = self.font_size

                except Exception as error:
                    logging.error(f"Exception occurred when reading {s} config", exc_info=error)
                logging.debug(f"Creating module {module_name} from {module_source}")
                module = Module(self, module_name, module_source, module_conf, top, left, width, height)
                self.modules.append(module)
                self.config = app_conf
        return True


    def run(self):
        """Run the mirror, never returns"""
        try:
            if self.latitude and self.longitude and self.timezone:
                sunrise.init(self.latitude, self.longitude, self.timezone)
            clock = pygame.time.Clock()

            white: tuple[int, int, int] = (255, 255, 255)

            cwd: str = os.getcwd()
            # Make sure we're in the pymirror directory
            os.chdir(pathlib.Path(__file__).parent.absolute())
            font = pygame.font.Font(self.font_name, self.font_size)
            os.chdir(cwd)
            font_height = font.render("dg", True, white).get_height()

            (python_icon, python_width, python_height) = self.load_image("python.png", invert=True, width=256)

            now = datetime.datetime.now()
            splash_end = now + datetime.timedelta(seconds = 4)

            logging.debug(f"Mirror WxH: {self.width}x{self.height}")
            # Show splash screen while loading modules
            self.fill_rect(0, 0, self.width, self.height)
            self._draw_splash("Loading Modules")
            pygame.display.flip()

            for module in self.modules:
                module.load()
                self.current_module = module
                module.locals = module._module.init(self, module.config)
                self.current_module = None

            if self.debug_mqtt_broker:
                self.init_mqtt_debug()

            self.splashing_past_module_init = True
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        logging.info("Exiting")
                        return

                self.fill_rect(0, 0, self.width, self.height)
                self._draw_modules()
                debug_info = self.get_debug_info()  # TODO: Create a mechanism for extracting debug info runtime
                if splash_end > datetime.datetime.now():
                    self._draw_splash()
                else:
                    self.splashing = False
                pygame.display.flip()
                clock.tick(self.fps) # Argument really is fps ;)

        except Exception as error:
            die("Caught exception", error)

    def get_current_module(self) -> Module:
        return self.current_module

    def get_config(self, key: str) -> str:
        """Return entry from the YAML [mirrorconfig] section

        Args:
            key (str): Config key from the mirrorconfig section

        Raises:
            Exception: If the key us not found, an exception is thrown

        Returns:
            str: Config value
        """
        if self.config is not None and key in self.config:
            return self.config[key]
        else:
            raise Exception(f"Key {key} not found in 'mirrorconfig' section.")


    def get_debug_info(self) -> dict:
        """Return debug information about the mirror

        Returns:
            dict: debug info
        """
        modules = {}
        for m in self.modules:
            info = {}
            if hasattr(m._module, "get_debug_info"):
                info["debug"] = m._module.get_debug_info(m.locals)
            info["active"] = m.active
            info["crashed_at"] = m.crashed_at
            info["exception"] = m.exception
            modules[m.name] = info
        return {"modules" : modules}  # TODO: Add more mirror info


    def _draw_modules(self):
        """Draw modules. Internal function called from run()
        """
        for m in self.modules:
            if not m.active:
                continue
            if self.frame_debug:
                # Debugging, fill each module background with blue
                self.current_module = None
                if m.width+1 != self.width or m.height+1 != self.height:
                    # Don't fill full screen modules with blue
                    self.draw_rect(m.left, m.top, m.width, m.height, color = (0, 255, 0))
            self.current_module = m

            try:
                m._module.draw(self, m.locals)
            except Exception as error:
                logging.error(f"Caught exception when drawing {m.source}, disabling module")
                logging.exception(error)
                m.active = False
                m.crashed_at = time.time()
                m.exception = "".join(tb.format_exception(None, error, error.__traceback__))

        self.current_module = None


    def draw_text(self, string: str, x: int, y: int, color: tuple = None, font_file: str = None, size: int = None, adjustment: Adjustment = Adjustment.Left, draw_shadow: bool = False, width: int|None = None) -> int:
        """Draw text on mirror

        Arguments:
            string {str} -- String to draw
            x {int} -- Left positiom
            y {int} -- Top positiom

        Keyword Arguments:
            color {tuple} -- Color tuple (tr, g, b) (default: {None})
            font_file {str} -- File name of fong (default: {None})
            size {int} -- Font size (default: {None})
            adjustment {Adjustment} -- Adjustment (default: {"left"})

        Returns:
            int: Width of blitted text (unscaled value)
        """
        center_x: bool = x == -1
        center_y: bool = y == -1
        if self.current_module:
            if width is not None:
                view_width = width
            else:
                view_width = self.current_module.width
        else:
            if width is not None:
                view_width = width
            else:
                view_width = self.width

        line_spacing = int(self.scale * 10) # TODO: add as parameter

        if not size:
            size = self.font_size
        if not color:
            try:
                r = int(self.font_color[0:2], 16)
                g = int(self.font_color[2:4], 16)
                b = int(self.font_color[4:6], 16)
            except:
                r = g = b = 255
            color = (r, g, b)

        if self.current_module:
            x += self.current_module.left
            y += self.current_module.top
        if center_x:
            x += view_width // 2
        if center_y:
            y += view_width // 2  # TODO: This must be incorrect
        x = int(self.scale * x)
        y = int(self.scale * y)
        size = int(self.scale * size)

        if font_file:
            # Assuming it is a module provided font find, cd to the module directory
            module_path = str(pathlib.Path(__file__).parent.parent.absolute())
            module_path += "/" + os.path.dirname(self.current_module["source"])
            logging.info(f"Font {module_path}")
            os.chdir(module_path)
        else:
            # Assuming it is the default pymirror font
            font_file = "ubuntu-font-family-0.83/Ubuntu-C.ttf"
            os.chdir(pathlib.Path(__file__).parent.absolute())

        font_key = f"{font_file}-{size}"
        if not font_key in self.fonts:
            font = pygame.font.Font(font_file, size)
            self.fonts[font_key] = font
#            font_height = font.render("dg", True, white).get_height()

        text = self.fonts[font_key].render(string, True, color)
        if draw_shadow:
            shadow_text = self.fonts[font_key].render(string, True, (0,0,0))
        if text.get_width() > view_width * self.scale:
            # Feeble attempt at flowing text
            temp: str = ""
            parts: list[str] = string.split(" ")
            while len(parts) > 0:
                next_part = parts.pop(0)
                text = self.fonts[font_key].render(temp + " " + next_part, True, color)
                if draw_shadow:
                    shadow_text = self.fonts[font_key].render(temp + " " + next_part, True, (0,0,0))
                if text.get_width() > view_width * self.scale:
                    text = self.fonts[font_key].render(temp, True, color)
                    if draw_shadow:
                        shadow_text = self.fonts[font_key].render(temp, True, (0,0,0))
                    temp_x = x
                    if adjustment == Adjustment.Center:
                        temp_x = x - text.get_width() // 2
                    elif adjustment == Adjustment.Right:
                        temp_x = x - text.get_width()
                    if draw_shadow:
                        self.screen.blit(shadow_text, (temp_x+1, y+1))
                    self.screen.blit(text, (temp_x, y))
                    y += size + line_spacing
                    temp = next_part
                else:
                    temp += " " + next_part
            if len(temp) > 0:
                text = self.fonts[font_key].render(temp, True, color)
                if draw_shadow:
                    text = self.fonts[font_key].render(temp, True, (0,0,0))
            else:
                text = None
        if text:
            if adjustment == Adjustment.Center:
                x -= text.get_width() // 2
            elif adjustment == Adjustment.Right:
                x -= text.get_width()
            if draw_shadow:
                self.screen.blit(shadow_text, (x+1, y+1))
            self.screen.blit(text, (x, y))
        return int(text.get_width() / self.scale)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: tuple = None):
        """Fill rectangle

        Arguments:
            x {int} -- left corner, relative the current module
            y {int} -- top corner, relative the current module
            width {int} -- width of rectangle
            height {int} -- height of rectangle

        Keyword Arguments:
            color {tuple} -- Color (r, g, b) (default: {None})

        Todo:
            Handle clipping of current module
        """
        if self.current_module:
            x += self.current_module.left
            y += self.current_module.top
        if not color:
            color = (0, 0, 0)
        s = self.screen
        x = int(self.scale * x)
        y = int(self.scale * y)
        width = int(self.scale * width)
        height = int(self.scale * height)
        rect = pygame.Rect(x, y, width, height)
        s.fill(color, rect)


    def draw_rect(self, x: int, y: int, width: int, height: int, color: tuple = None):
        """Draw rectangle

        Arguments:
            x {int} -- left corner, relative the current module
            y {int} -- top corner, relative the current module
            width {int} -- width of rectangle
            height {int} -- height of rectangle

        Keyword Arguments:
            color {tuple} -- Color (r, g, b) (default: {None})

        Todo:
            Handle clipping of current module
        """
        if self.current_module:
            x += self.current_module.left
            y += self.current_module.top
        if not color:
            color = (0, 0, 0)
        s = self.screen
        x = int(self.scale * x)
        y = int(self.scale * y)
        width = int(self.scale * width)
        height = int(self.scale * height)
        pygame.draw.line(s, color, (x, y), (x+width, y))
        pygame.draw.line(s, color, (x+width, y), (x+width, y+height))
        pygame.draw.line(s, color, (x, y+height), (x+width, y+height))
        pygame.draw.line(s, color, (x, y), (x, y+height))


    def load_image(self, image_name: str, width: int, invert: bool = False) -> Tuple[pygame.Surface, int, int]:
        """Load image and return triplet of image data, width & height. Image
        will be scaled proportinally and according to the global scale settings.
        Images are cached when scaled as this operation takes a considerable
        amount of time on a slow Raspberry Pi.

        Arguments:
            image_name {str} -- Image name (png)
            width {int} -- Image width in pixels

        Keyword Arguments:
            invert {bool} -- True if image is to be inverted (default: False)

        Returns:
            Tuple (imgage data, image width, image height). Please note that the image dimensions
            are the real image dimensions and not the scaled values.
        """
        image: pygame.Surface|None = None
        search_paths: list[pathlib.Path] = []
        if self.current_module is not None:
            logging.debug(f"Module {self.current_module.name} loading image {image_name}")
            search_paths = self.current_module.search_paths
        else:
            logging.debug(f"PyMirror loading image {image_name}")
            search_paths = self.search_paths

        if self.splashing:
            self._draw_splash(f"Loading {image_name}")

        if self.cache_dir:
            if not os.path.isdir(self.cache_dir):
                logging.info(f"Creating cache dir at {self.cache_dir}")
                os.makedirs(self.cache_dir)

            cached_name: pathlib.Path = self.cache_dir / f"{image_name.replace('/', '_')}-{int(invert)}-{width}-{int(100*self.scale)}"
            if os.path.isfile(cached_name):
                logging.debug(f"Found {cached_name} in cache")
                height = os.path.getsize(cached_name) // int(self.scale*width) // 4 # RGBA
                scaled_width = int(self.scale*width)
                scaled_height = os.path.getsize(cached_name) // scaled_width // 4 # RGBA
                try:
                    with open(cached_name, "rb") as file:
                        image = pygame.image.fromstring(file.read(), (scaled_width, scaled_height), "RGBA")
                except Exception:
                    logging.debug(f"Loading {cached_name} from cache failed", exc_info=True)

        # Not cached or cache loading failed
        if image is None:
            candidate_path: pathlib.Path|None = None
            logging.debug(f"Loading {image_name}")
            for path in search_paths:
                candidate_path = path / image_name
                logging.info(f"Checking {candidate_path}")
                if candidate_path.is_file():
                    logging.info(f"Found {candidate_path}")
                    break
                else:
                    candidate_path = None

            if candidate_path is None:
                logging.error(f"Image {image_name} not found")
                return (None, None, None)

            logging.info(f"Loading image {candidate_path}")
            image = pygame.image.load(candidate_path)
            if image is None:
                logging.error(f"Image {image_name} failed to load")
                return (None, None, None)
            if invert:
                image.lock()
                for x in range(image.get_width()):
                    for y in range(image.get_height()):
                        RGBA = image.get_at((x, y))
                        for i in range(3):
                            # Invert RGB, but not Alpha
                            RGBA[i] = 255 - RGBA[i]
                        image.set_at((x, y), RGBA)
                image.unlock()
            if width:
                (image_width, image_height) = image.get_size()
                ratio = image_width / image_height
                height = int(width / ratio)
                scaled_width = int(self.scale * width)
                scaled_height = int(self.scale * height)
                image = pygame.transform.smoothscale(image, (scaled_width, scaled_height))

            if self.cache_dir:
                with open(cached_name, "wb") as file:
                    file.write(pygame.image.tostring(image, "RGBA"))
        return (image, width, height)


    def blit_image(self, image: pygame.Surface, x: int, y: int, width: int = None, height: int = None):
        """Blit a PyGame image (surface) onto the mirror

        Args:
            image (pygame.Surface): Image loaded using PyGame
            x (int): X position
            y (int): Y position
            width (int, optional): Width of image (currently not used). Defaults to None.
            height (int, optional): Height of image (currently not used). Defaults to None.
        """
        if self.current_module:
            x += self.current_module.left
            y += self.current_module.top
        x = int(self.scale * x)
        y = int(self.scale * y)
        self.screen.blit(image, (x, y))


    def _draw_splash(self, message: str = None):
        """Internal function. Draw PyMirror splash screen

        Args:
            mirror (Mirror): PyMirror object
            message (str): Message to display
        """
        if not self.splashing:
            return

        # As we are might be calling this function withing the context of a module,
        # make sure we do not offset drawing to the module's frame.
        temp = self.current_module
        self.current_module = None

        if self.python_icon is None:
            self.splashing = False  # Lest we will recurse here ;)
            (self.python_icon, self.python_width, self.python_height) = self.load_image("python.png", invert=True, width=256)
            self.splashing = True

        if not self.splashing_past_module_init:
            self.fill_rect(0, 0, self.width, self.height)
        self.fill_rect(self.width//2-200-2, self.height//3-2, 406, 404, color = (155, 155, 155))
        self.fill_rect(self.width//2-200, self.height//3, 400, 400, color = (0, 0, 0))
        self.draw_text("PyMirror", self.width//2, self.height//3, adjustment=Adjustment.Center, size=100)
        self.blit_image(self.python_icon, self.width//2 - self.python_width//2, self.height//3 + 120)
        if message and not self.splashing_past_module_init:
            self.draw_text(message, self.width//2, self.height//3 + 410, adjustment=Adjustment.Center, size=50)
        # Restore current_module
        self.current_module = temp
        pygame.display.flip()


    def init_mqtt_debug(self):
        def mqtt_callback(topic: str, payload: str):
            logging.debug(f"Got {topic, payload} : {payload}")
            if topic == "pymirror/ping":
                return [(f"pymirror/{self.name.lower()}", "pong")]
            elif topic == "pymirror/debug":
                return [(f"pymirror/{self.name.lower()}", json.dumps(debug_info))]
        try:
            run_script(mqtt_callback, broker=f"mqtt://{self.debug_mqtt_broker}", topics=["pymirror/#"], blocking=False)
        except Exception as e:
            logging.error(f"Failed to connect to MQTT broker {self.debug_mqtt_broker}", exc_info=e)

def die(err_str: str, exception: Exception):
    """Die with error message

    Arguments:
        err_str {str} -- Error message
        exception {Exception} -- Exception that caused us to cease operations
    """
    logging.error(err_str, exc_info=exception)
    sys.exit(1)


def string2whatever(str: str):
    """Return a Python variable representation of 'str'
       Return boolean True for "true" or "yes"
       Return float 1.3 for "1.3"
       Return int 1 for "1"
       Or just return "foo32" if neither an int, float or bool

    Args:
        str ([type]): [description]

    Returns:
        [type]: [description]
    """
    str = str.lstrip().rstrip()

    if str.isdigit():
        return int(str)
    elif str.lower() in ["true", "yes"]:
        return True
    elif str.lower() in ["false", "no"]:
        return False
    else:
        try:
            return float(str)
        except ValueError:
            return str


def main():
    import coloredlogs
    import logging
    import argparse
    import sys

    parser = argparse.ArgumentParser(description = "One more magic mirror, this time in Python")
    parser.add_argument("-v", "--verbose", help = "Increase output verbosity", action = "store_true")
    parser.add_argument("-c", "--config", action = "store", help = "Configuration file", required=True)
    parser.add_argument("-m", "--module", action = "store", help = "Only load modules matching MODULE", default = None)
    parser.add_argument("-d", "--debug", action = "store_true", help = "Run in debug mode, halting on module exceptions", default = None)
    parser.add_argument("-g", "--frame-debug", action = "store_true", help = "Frame debugging (fill module background with blue)", default = False)
    parser.add_argument("-f", "--fps", action = "store", help = "Override fps option in config file", default = None)
    parser.add_argument("-x", "--x", action = "store", help = "Set window x position", default = None)
    parser.add_argument("-y", "--y", action = "store", help = "Set window y position", default = None)
    parser.add_argument("-F", "--fullscreen", action = "store_true", help = "Override fullscreen option in config file", default = None)
    parser.add_argument("-s", "--scale", action = "store", help = "Override scale option in config file", default = None)
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    styles = {"critical": {"bold": True, "color": "red"}, "debug": {"color": "green"}, "error": {"color": "red"}, "info": {"color": "white"}, "notice": {"color": "magenta"}, "spam": {"color": "green", "faint": True}, "success": {"bold": True, "color": "green"}, "verbose": {"color": "blue"}, "warning": {"color": "yellow"}}
    level = logging.DEBUG if "-v" in sys.argv or "--verbose" in sys.argv else logging.INFO
    coloredlogs.install(level=level, fmt="%(asctime)s.%(msecs)03d \033[0;90m%(levelname)-8s "
                        ""
                        "\033[0;36m%(filename)-18s%(lineno)3d\033[00m "
                        "%(message)s",
                        level_styles = styles)

    logging.info(f"---[ Starting {sys.argv[0]} ]---------------------------------------------")

    fps = None
    scale = None
    fullscreen = None
    if args.fps is not None:
        fps = int(args.fps)
    if args.scale is not None:
        scale = float(args.scale)
    if args.fullscreen is not None:
        fullscreen = bool(args.fullscreen)
    mirror = Mirror(args.config, fps = fps, scale = scale, fullscreen = fullscreen, module_filter = args.module, x_pos = args.x, y_pos = args.y, frame_debug = args.frame_debug)
    mirror.run()
