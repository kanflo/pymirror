__version__ = '2.1'
__all__ = ['Mirror', 'is_day', 'is_night', 'sun_lookup']
__author__ = 'Johan Kanflo <github.com/kanflo>'

from .pymirror import Mirror, Module, Adjustment
from .sunrise import init, is_day, is_night, sun_lookup
