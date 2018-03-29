"""
Support for the Nissan Leaf .

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nissanleaf/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, LENGTH_KILOMETERS, LENGTH_MILES)
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['leafpy==0.2.2']

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS = {
    'batteryCharging': ['Battery Charging'],
    'pluginState': ['Plugged In'],
}

SENSORS = {
    'batteryCapacity': ['Battery Capacity', None],
    'batteryRemaining': ['Remaining Battery', None],
    'batteryRemainingWH': ['Watt Hours Remaining', 'Wh'],
    'batteryRemainingPct': ['Battery Percent Remaining', '%'],
    'RangeWithAC_KM': ['Range With AC', LENGTH_KILOMETERS],
    'RangeWithoutAC_KM': ['Range Without AC', LENGTH_KILOMETERS],
    'RangeWithAC_MI': ['Range With AC', LENGTH_MILES],
    'RangeWithoutAC_MI': ['Range Without AC', LENGTH_MILES],
    'TimeToFull_110': ['Time to Battery Full', 'minutes'],
    'TimeToFull_220_3kw': ['Time to Battery Full (220v/3Kw Charge)', 'minutes'],
    'TimeToFull_220_6kw': ['Time to Battery Full (220v/6Kw Charge', 'minutes'],

}

DATA_LEAF = 'nissanleaf'
DOMAIN = 'nissanleaf'

FEATURE_NOT_AVAILABLE = "The feature %s is not available for your car %s"

NOTIFICATION_ID = 'nissanleaf_integration_notification'
NOTIFICATION_TITLE = 'Nissan Leaf integration setup'

SIGNAL_UPDATE_NISSANLEAF = "nissanleaf_update"


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=30):
            vol.All(cv.positive_int, vol.Clamp(min=5, max=120))
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Nissan Leaf System."""
    from leafpy import Leaf

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        leaf_api = Leaf(username, password)
        hass.data[DATA_LEAF] = leaf_api
    except Exception as ex:
        if ex.args[0].startswith('Cannot login.  Probably username & password are wrong.'):
            hass.components.persistent_notification.create(
                "Error:<br />Please check username and password."
                "You will need to restart Home Assistant after fixing.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
        else:
            hass.components.persistent_notification.create(
                "Error:<br />Can't communicate with Nissan Leaf API.<br />"
                "Error: {}"
                "You will need to restart Home Assistant after fixing."
                "".format(ex.args[0]),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)

        _LOGGER.error("Unable to communicate with Nissan Leaf API: %s",
                      ex.args)
        return False

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'device_tracker', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    def hub_refresh(event_time):
        """Call Nissan Leaf API to refresh information."""
        _LOGGER.info("Updating Nissan Leaf component.")
        hass.data[DATA_LEAF].
        dispatcher_send(hass, SIGNAL_UPDATE_NISSANLEAF)

    track_time_interval(
        hass,
        hub_refresh,
        timedelta(seconds=scan_interval))

    return True


class MercedesMeHub(object):
    """Representation of a base MercedesMe device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data


class MercedesMeEntity(Entity):
    """Entity class for MercedesMe devices."""

    def __init__(self, data, internal_name, sensor_name, vin, unit):
        """Initialize the MercedesMe entity."""
        self._car = None
        self._data = data
        self._state = False
        self._name = sensor_name
        self._internal_name = internal_name
        self._unit = unit
        self._vin = vin

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_NISSANLEAF, self._update_callback)

    def _update_callback(self):
        """Callback update method."""
        # If the method is made a callback this should be changed
        # to the async version. Check core.callback
        self.schedule_update_ha_state(True)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit
