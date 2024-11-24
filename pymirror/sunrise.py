"""
This module calculates sunrise and sunset given the user's location on Earth
by calling sunrise-sunset.org. Results are not cached, be kind to the API.

See https://sunrise-sunset.org/api
"""

from typing import *
import sys
import requests
import json
import logging
import datetime
try:
    from dateutil.parser import parse
except ImportError:
    print("Missing dateutil:\npython -m pip install -r requirements.txt")
    sys.exit(1)
try:
    import pytz
except ModuleNotFoundError:
    print("Missing pytz:\npython -m pip install -r requirements.txt")
    sys.exit(1)

g_lat: Union[float, None] = None
g_lon: Union[float, None]  = None
g_tz: Union[str, None]  = None


def init(lat: float, lon: float, timezone: str = "Europe/Copenhagen"):
    """Initialize the module given the user's location on Earth

    Arguments:
        lat {float} -- Latitude
        lon {float} -- Longitude

    Keyword Arguments:
        timezone {str} -- Name of time zone (default: {"Europe/Copenhagen"})
    """
    global g_lat
    global g_lon
    global g_tz
    g_lat = lat
    g_lon = lon
    try:
        g_tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        logging.error("Unknown TZ name, see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")


def is_day() -> bool:
    """Return wether if is day nor not

    Returns:
        bool -- True if it is currently daytime, False is not or unknown
    """
    sun = sun_lookup()
    if sun is None:
        return False
    sunrise = sun["sunrise"]
    sunset = sun["sunset"]
    now = datetime.datetime.now(g_tz)
    return now >= sunrise and now < sunset


def is_night() -> bool:
    """Return wether if is night nor not

    Returns:
        bool -- True if it is currently nighttime, False is not or unknown
    """
    sun = sun_lookup()
    if sun is None:
        return False
    sunrise = sun["sunrise"]
    sunset = sun["sunset"]
    now = datetime.datetime.now(g_tz)
    return now < sunrise or now >= sunset


def sun_lookup(tomorrow: bool = False) -> Dict[str, datetime.datetime]:
    """Lookup the rising and setting of the sun today

    Keyword Arguments:
        tomorrow {bool} -- Check tomorrow instead of today (default: {False})

    Returns:
        Dict[str, datetime.datetime] -- Dict with the rise and setting time of the sun
                                        keyed on "sunrise" and "sunset"
    """
    assert (g_lat != None), "Did you forget to call sunrise.init(lat, lon)?"
    assert (g_lon != None), "Did you forget to call sunrise.init(lat, lon)?"
    url =  "https://api.sunrise-sunset.org/json?lng=%f&lat=%f&formatted=0" % (g_lon, g_lat)
    if tomorrow:
        url += "&date=tomorrow"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A"
    }
    try:
        r = requests.get(url, headers = headers)
        if r.status_code != 200:
            logging.error("Sunrise failed with %d for %s" % (r.status_code, url))
            return None
        if not r.text:
            logging.error("Sunrise returned no data")
            return None
    except Exception as e:
        logging.error("Sunrise fetch caused exception", exc_info=True)
        return None
    else:
        try:
            data = json.loads(r.text)
            sunrise = parse(data["results"]["sunrise"]).astimezone(g_tz)
            sunset = parse(data["results"]["sunset"]).astimezone(g_tz)
            return {"sunrise" : sunrise, "sunset" : sunset}
        except Exception as e:
            logging.error("Sunrise parsing caused exception", exc_info=True)
            return None
