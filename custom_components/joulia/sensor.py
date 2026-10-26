"""Sensors for Joulia EV Charging."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JouliaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joulia sensors based on a config entry."""
    coordinator: JouliaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    for charger_id in coordinator.data:
        entities.extend(
            [
                JouliaStatusSensor(coordinator, charger_id),
                JouliaSessionEnergySensor(coordinator, charger_id),
                JouliaChargingPowerSensor(coordinator, charger_id),
                JouliaCellSignalSensor(coordinator, charger_id),
            ]
        )

    async_add_entities(entities)


class JouliaBaseEntity(CoordinatorEntity[JouliaDataUpdateCoordinator]):
    """Base class for Joulia entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.charger_id = charger_id

    @property
    def charger_data(self) -> Dict[str, Any]:
        """Return the data dict for this charger."""
        return self.coordinator.data.get(self.charger_id, {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this charger."""
        charger = self.charger_data.get("charger")
        sub = self.charger_data.get("subscription")

        manufacturer = charger.manufacturer if charger else "Joulia"
        model = charger.charger_model if charger else "EV Charger"
        location = f"{sub.housing_company_name} - Spot {sub.parking_lot_name}" if sub else None

        return DeviceInfo(
            identifiers={(DOMAIN, self.charger_id)},
            name=f"Joulia {self.charger_id}",
            manufacturer=manufacturer,
            model=model,
            suggested_area=location,
        )


class JouliaStatusSensor(JouliaBaseEntity, SensorEntity):
    """Sensor reporting the charger socket status."""

    _attr_translation_key = "charger_status"
    _attr_icon = "mdi:ev-station"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize status sensor."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_status"
        self._attr_name = "Status"

    @property
    def native_value(self) -> Optional[str]:
        """Return the current charger or socket status."""
        charger = self.charger_data.get("charger")
        if not charger:
            return None
        if charger.sockets:
            return charger.sockets[0].status
        return charger.charger_status

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra attributes."""
        sub = self.charger_data.get("subscription")
        charger = self.charger_data.get("charger")
        attrs: Dict[str, Any] = {}
        if sub:
            attrs["facility"] = sub.charging_facility_name
            attrs["housing_company"] = sub.housing_company_name
            attrs["parking_lot"] = sub.parking_lot_name
            attrs["supplier"] = sub.supplier
        if charger:
            attrs["hardware_status"] = charger.charger_status
            attrs["last_seen"] = charger.last_seen
        return attrs


class JouliaSessionEnergySensor(JouliaBaseEntity, SensorEntity):
    """Sensor tracking energy delivered during the active or most recent session."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize energy sensor."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_session_energy"
        self._attr_name = "Session Energy"

    @property
    def native_value(self) -> Optional[float]:
        """Return the kWh delivered in the active charging session."""
        session = self.charger_data.get("session")
        if session:
            return session.total_kwh
        return 0.0

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return session start time."""
        session = self.charger_data.get("session")
        if session and session.start_time:
            return {"session_start_time": session.start_time}
        return {}


class JouliaChargingPowerSensor(JouliaBaseEntity, SensorEntity):
    """Sensor reporting real-time charging power in kW."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:flash"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize power sensor."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_charging_power"
        self._attr_name = "Charging Power"
        self._last_kwh: Optional[float] = None
        self._last_time: Optional[datetime] = None
        self._calculated_power: float = 0.0

    @property
    def native_value(self) -> Optional[float]:
        """Return the live charging power in kW."""
        session = self.charger_data.get("session")
        charger = self.charger_data.get("charger")

        # 1. If API provides currentKw directly, use it
        if session and session.current_kw is not None:
            return round(session.current_kw, 2)

        # 2. Check if charger is actively charging
        is_charging = False
        if charger and charger.sockets:
            is_charging = charger.sockets[0].status.lower() in ["charging"]

        if not is_charging:
            self._last_kwh = None
            self._last_time = None
            self._calculated_power = 0.0
            return 0.0

        # 3. Calculate instantaneous power from rate of totalKwh change
        current_kwh = session.total_kwh if session else None
        now = datetime.now(timezone.utc)

        if current_kwh is not None:
            if self._last_kwh is not None and self._last_time is not None:
                delta_kwh = current_kwh - self._last_kwh
                delta_hours = (now - self._last_time).total_seconds() / 3600.0

                # If energy increased over an interval > 5 seconds
                if delta_hours > (5.0 / 3600.0) and delta_kwh > 0.0:
                    power = delta_kwh / delta_hours
                    # Sanity check: cap to realistic 22 kW AC max
                    if 0.1 <= power <= 25.0:
                        self._calculated_power = round(power, 2)
                        self._last_kwh = current_kwh
                        self._last_time = now
                elif delta_hours > (180.0 / 3600.0) and delta_kwh == 0.0:
                    # No energy delivered for > 3 minutes while charging (battery full / balancing)
                    self._calculated_power = 0.0

            else:
                self._last_kwh = current_kwh
                self._last_time = now

        return self._calculated_power


class JouliaCellSignalSensor(JouliaBaseEntity, SensorEntity):
    """Sensor reporting cellular signal strength (RSSI)."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:signal-cellular-3"

    def __init__(
        self,
        coordinator: JouliaDataUpdateCoordinator,
        charger_id: str,
    ) -> None:
        """Initialize signal sensor."""
        super().__init__(coordinator, charger_id)
        self._attr_unique_id = f"{charger_id}_cell_rssi"
        self._attr_name = "Cellular Signal"

    @property
    def native_value(self) -> Optional[int]:
        """Return cellular signal in dBm."""
        charger = self.charger_data.get("charger")
        if charger and charger.cell_rssi is not None:
            return charger.cell_rssi
        return None
