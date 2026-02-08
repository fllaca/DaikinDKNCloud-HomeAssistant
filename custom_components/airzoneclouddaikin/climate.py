import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util import Throttle
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from .const import CONF_USERNAME, CONF_PASSWORD

# init logger
_LOGGER = logging.getLogger(__name__)

# default refresh interval
SCAN_INTERVAL = timedelta(seconds=10)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

AIRZONECLOUD_DEVICE_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the AirzonecloudDaikin platform"""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    if username is None or password is None:
        _LOGGER.error("missing username or password config")
        return

    from AirzoneCloudDaikin import AirzoneCloudDaikin

    api = None
    try:
        api = AirzoneCloudDaikin(username, password)
    except Exception as err:
        _LOGGER.error(err)
        hass.services.call(
            "persistent_notification",
            "create",
            {"title": "AirzonecloudDaikin error", "message": str(err)},
        )
        return

    entities = []
    for installation in api.installations:
        # create a shared throttled refresh function per installation
        # so multiple devices don't cause redundant API calls
        throttled_refresh = Throttle(MIN_TIME_BETWEEN_UPDATES)(installation.refresh_devices)
        for device in installation.devices:
            entities.append(AirzonecloudDaikinDevice(device, throttled_refresh))

    add_entities(entities)


class AirzonecloudDaikinDevice(ClimateEntity):
    """Representation of an Airzonecloud Daikin Device"""

    def __init__(self, azc_device, refresh_installation):
        """Initialize the device"""
        self._azc_device = azc_device
        self._refresh_installation = refresh_installation
        _LOGGER.info("init device {} ({})".format(self.name, self.unique_id))

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return "device_" + self._azc_device.id

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} - {}".format(self._azc_device.installation.name, self._azc_device.name)

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        mode = self._azc_device.mode

        if self._azc_device.is_on:
            if mode in ["cool", "cool-air"]:
                return HVACMode.COOL

            if mode in ["heat", "heat-air"]:
                return HVACMode.HEAT

            if mode == "ventilate":
                return HVACMode.FAN_ONLY

            if mode == "dehumidify":
                return HVACMode.DRY

        return HVACMode.OFF

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return AIRZONECLOUD_DEVICE_HVAC_MODES

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._azc_device.current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._azc_device.target_temperature

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return 1

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self._azc_device.set_temperature(round(float(temperature), 1))

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            if not self._azc_device.is_on:
                self.turn_on()

            # set hvac mode
            if hvac_mode == HVACMode.HEAT:
                self._azc_device.set_mode("heat")
            elif hvac_mode == HVACMode.COOL:
                self._azc_device.set_mode("cool")
            elif hvac_mode == HVACMode.DRY:
                self._azc_device.set_mode("dehumidify")
            elif hvac_mode == HVACMode.FAN_ONLY:
                self._azc_device.set_mode("ventilate")

    def turn_on(self):
        """Turn on."""
        self._azc_device.turn_on()

    def turn_off(self):
        """Turn off."""
        self._azc_device.turn_off()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        """return self._azc_device.min_temperature"""

        return TemperatureConverter.convert(
            self._azc_device.min_temperature, UnitOfTemperature.CELSIUS, self.temperature_unit
        )        
        """
        return convert_temperature(
            self._azc_device.min_temperature, TEMP_CELSIUS, self.temperature_unit
        )
        """

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        """return self._azc_device.max_temperature"""

        return TemperatureConverter.convert(
            self._azc_device.max_temperature, UnitOfTemperature.CELSIUS, self.temperature_unit
        )
        """
        return convert_temperature(
            self._azc_device.max_temperature, TEMP_CELSIUS, self.temperature_unit
        )
        """

    def update(self):
        """Refresh device data from the API."""
        self._refresh_installation()
