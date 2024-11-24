#pyright: strict
#
# Copyright (c) 2023-2024 Johan Kanflo (github.com/kanflo)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
# A Python wrapper for reading a Home Assistant sensor
#

import datetime
from dateutil.parser import parse
import logging
from requests import get
import time
from typing import Any


class hass_sensor:
    """A class for modelling a HASS sensor"""
    def __init__(self, hass_host: str, token: str, sensor_name: str):
        """Object init

        Args:
            hass_host (str): HASS host name (from global mirror config)
            token (str): Your 'long lived' token (from global mirror config)
            sensor (str): Name of sensor
        """
        self._hass_host: str = hass_host
        self._token: str = token
        self._sensor_name: str = sensor_name
        self._last_check: int|None = None
        self._state: str|None = None
        self._attributes: str|None = None
        self._age: int = -1
        self._last_completed_check: int = -1

    def update(self) -> bool:
        """Update sensor

        Returns:
            bool: True if update went well
        """
        url = f"http://{self._hass_host}/api/states/{self._sensor_name}"
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }
        try:
            j: dict[str, str]|None = None
            response = get(url, headers = headers)
            j = response.json()
            if j is None:
                return False
            if "message" in j:
                logging.error(f"Fetch of {self._sensor_name} yielded message {j['message']}")
                return False
            if "last_changed" in j:
                dt = parse(j["last_changed"])
                now = datetime.datetime.utcnow()
                self._age = round((now.replace(tzinfo=datetime.timezone.utc) - dt).total_seconds())
            else:
                self._age = -1
            if "state" in j:
                self._state = j["state"]
            else:
                print(j)
                self._state = None
            if "attributes" in j:
                self._attributes = j["attributes"]
            else:
                self._attributes = None
            self._last_completed_check = round(time.time())
        except Exception:
            logging.error(f"Sensor fetch for {self._sensor_name} failed", exc_info=True)
            logging.error(j)
            return False
        return True

    def age(self) -> int:
        """Return age of current sensor state in seconds

        Returns:
            int: Ave of current state
        """
        return self._age

    def attributes(self) -> dict|None:
        """Return current attributes

        Returns:
            Any: Current attributes
        """
        return self._attributes

    def state(self) -> str|None:
        """Return current state

        Returns:
            Any: Current state
        """
        return self._state

    def name(self) -> str:
        """Return name of sensor

        Returns:
            str: Name of sensor
        """
        return self._sensor_name


if __name__ == "__main__":
    def main():
        """For testing"""
        host = "homeassistant.local:8123"
        token = "enter your token here"
        sensor1 = hass_sensor(host, token, "sensor.utomhus")
        sensor2 = hass_sensor(host, token, "sensor.p1s_nozzle_temperature")
        sensor3 = hass_sensor(host, token, "sensor.p1s_print_status")
        if sensor1.update():
            print(f"Sensor value: {sensor1.state()}   age:{sensor1.age()}")
        if sensor2.update():
            print(f"Sensor value: {sensor2.state()}   age:{sensor2.age()}")
        if sensor3.update():
            print(f"Sensor value: {sensor3.state()}   age:{sensor3.age()}")

    main()
