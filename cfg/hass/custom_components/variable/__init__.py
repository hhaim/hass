"""variable implementation for Homme Assistant."""
import asyncio
import logging
import json
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.const import CONF_NAME, ATTR_ICON
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

DOMAIN = "variable"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_ATTRIBUTES = "attributes"
CONF_VALUE = "value"
CONF_RESTORE = "restore"

ATTR_VARIABLE = "variable"
ATTR_VALUE = "value"
ATTR_VALUE_TEMPLATE = "value_template"
ATTR_ATTRIBUTES = "attributes"
ATTR_ATTRIBUTES_TEMPLATE = "attributes_template"
ATTR_REPLACE_ATTRIBUTES = "replace_attributes"

SERVICE_SET_VARIABLE = "set_variable"
SERVICE_SET_VARIABLE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VARIABLE): cv.string,
        vol.Optional(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_VALUE_TEMPLATE): cv.template,
        vol.Optional(ATTR_ATTRIBUTES): dict,
        vol.Optional(ATTR_ATTRIBUTES_TEMPLATE): cv.template,
        vol.Optional(ATTR_REPLACE_ATTRIBUTES): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.slug: vol.Any(
                    {
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(CONF_VALUE): cv.match_all,
                        vol.Optional(CONF_ATTRIBUTES): dict,
                        vol.Optional(CONF_RESTORE): cv.boolean,
                    },
                    None,
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_set_variable(
    hass: HomeAssistant,
    variable: str,
    value: Any = None,
    value_template: Any = None,
    attributes: Optional[Dict[str, Any]] = None,
    attributes_template: Any = None,
    replace_attributes: bool = False,
) -> None:
    """Set variable via service call."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VARIABLE,
        {
            ATTR_VARIABLE: variable,
            ATTR_VALUE: value,
            ATTR_VALUE_TEMPLATE: value_template,
            ATTR_ATTRIBUTES: attributes,
            ATTR_ATTRIBUTES_TEMPLATE: attributes_template,
            ATTR_REPLACE_ATTRIBUTES: replace_attributes,
        },
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up variables."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for variable_id, variable_config in config[DOMAIN].items():
        if not variable_config:
            variable_config = {}

        name = variable_config.get(CONF_NAME)
        value = variable_config.get(CONF_VALUE)
        attributes = variable_config.get(CONF_ATTRIBUTES)
        restore = variable_config.get(CONF_RESTORE, False)

        entities.append(
            Variable(variable_id, name, value, attributes, restore)
        )

    @callback
    async def async_set_variable_service(call: ServiceCall) -> None:
        """Handle calls to the set_variable service."""
        entity_id = ENTITY_ID_FORMAT.format(call.data.get(ATTR_VARIABLE))
        entity = component.get_entity(entity_id)

        if entity:
            await entity.async_set_variable(
                call.data.get(ATTR_VALUE),
                call.data.get(ATTR_VALUE_TEMPLATE),
                call.data.get(ATTR_ATTRIBUTES),
                call.data.get(ATTR_ATTRIBUTES_TEMPLATE),
                call.data.get(ATTR_REPLACE_ATTRIBUTES, False),
            )
        else:
            _LOGGER.warning("Failed to set unknown variable: %s", entity_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VARIABLE,
        async_set_variable_service,
        schema=SERVICE_SET_VARIABLE_SCHEMA,
    )

    await component.async_add_entities(entities)
    return True


class Variable(RestoreEntity):
    """Representation of a variable."""

    def __init__(
        self,
        variable_id: str,
        name: Optional[str],
        value: Any,
        attributes: Optional[Dict[str, Any]],
        restore: bool,
    ) -> None:
        """Initialize a variable."""
        self.entity_id = ENTITY_ID_FORMAT.format(variable_id)
        self._attr_name = name
        self._value = value
        self._attributes = attributes or {}
        self._restore = restore
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        
        if self._restore:
            # If variable state has been saved, restore it
            if (last_state := await self.async_get_last_state()) is not None:
                self._value = last_state.state
                # Optionally restore attributes (commented out in original)
                if last_state.attributes:
                     self._attributes.update(last_state.attributes)


    @property
    def name(self) -> Optional[str]:
        """Return the name of the variable."""
        return self._attr_name

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to be used for this entity."""
        if self._attributes:
            return self._attributes.get(ATTR_ICON)
        return None

    @property
    def state(self) -> Any:
        """Return the state of the component."""
        return self._value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return self._attributes

    async def async_set_variable(
        self,
        value: Any = None,
        value_template: Any = None,
        attributes: Optional[Dict[str, Any]] = None,
        attributes_template: Any = None,
        replace_attributes: bool = False,
    ) -> None:
        """Update variable."""
        current_state = self.hass.states.get(self.entity_id)
        updated_attributes = None
        updated_value = None

        # Handle attributes update
        if not replace_attributes and self._attributes:
            updated_attributes = dict(self._attributes)

        if attributes is not None:
            if updated_attributes is not None:
                updated_attributes.update(attributes)
            else:
                updated_attributes = attributes

        elif attributes_template is not None:
            attributes_template.hass = self.hass

            try:
                rendered_attributes = await attributes_template.async_render(
                    {"variable": current_state}, parse_result=False
                )
                
                attributes_data = json.loads(rendered_attributes)

                if isinstance(attributes_data, dict):
                    if updated_attributes is not None:
                        updated_attributes.update(attributes_data)
                    else:
                        updated_attributes = attributes_data

            except (TemplateError, json.JSONDecodeError, ValueError) as ex:
                _LOGGER.error(
                    "Could not render attributes_template for %s: %s",
                    self.entity_id,
                    ex,
                )

        # Handle value update
        if value is not None:
            updated_value = value

        elif value_template is not None:
            try:
                value_template.hass = self.hass
                updated_value = await value_template.async_render(
                    {"variable": current_state}, parse_result=False
                )
            except TemplateError as ex:
                _LOGGER.error(
                    "Could not render value_template for %s: %s",
                    self.entity_id,
                    ex,
                )

        # Apply updates
        if updated_attributes is not None:
            self._attributes = updated_attributes

        if updated_value is not None:
            self._value = updated_value

        # NEW: Use async_write_ha_state() instead of async_schedule_update_ha_state()
        self.async_write_ha_state()
