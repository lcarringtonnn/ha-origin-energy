"""Config flow for Origin Energy.

Asks for an imported browser session cookie rather than a password:
Origin's password endpoint is behind Kasada bot defence and cannot be
scripted. See docs/session-cookie.md.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    OriginEnergyApiClient,
    OriginEnergyApiError,
    pick_service,
    pick_time_unit,
)
from .auth import (
    OriginEnergyAuthError,
    OriginEnergyBlocked,
    async_login_with_cookie,
    current_session_cookie,
)
from .const import (
    CONF_AGREEMENT_ID,
    CONF_SESSION_COOKIE,
    CONF_TIME_UNIT,
    CONF_TIMEZONE,
    DEFAULT_TIMEZONE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_SESSION_COOKIE): str})


class OriginEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Origin Energy."""

    VERSION = 1

    def _configured_agreement_id(self) -> str | None:
        """Pin re-auth to the agreement this entry already tracks.

        Otherwise re-authenticating could silently move an entry onto a
        different meter, orphaning its statistics history.
        """
        if self.source != SOURCE_REAUTH:
            return None
        return self._get_reauth_entry().data.get(CONF_AGREEMENT_ID)

    async def _async_validate(
        self, cookie: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Exchange the cookie for tokens and read back the live service.

        Returns (entry_data, error_key) -- exactly one of which is set.
        """
        # A private session, because validating seeds a cookie into the jar
        # that must not leak into other integrations' requests.
        #
        # auto_cleanup=False + detach(): there is no config entry yet, so
        # automatic cleanup would only fire at Home Assistant shutdown and
        # the session would linger until then. Closing it instead is what
        # Home Assistant warns about -- detach() is the sanctioned way to
        # let go of one of its sessions.
        #
        # See coordinator.py: session default headers don't survive Home
        # Assistant, so the browser identity is applied per request.
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        try:
            tokens = await async_login_with_cookie(session, cookie)
            services = await OriginEnergyApiClient(
                session, tokens.access_token
            ).async_get_services("ELECTRICITY")

            # An account can list a closed agreement alongside the live one,
            # so services[0] is whichever the gateway happened to return
            # first rather than the one still supplying power.
            service = pick_service(services, self._configured_agreement_id())
            if service is None:
                return None, "no_services"
            timezone = (
                ((service.get("property") or {}).get("address") or {}).get(
                    "components", {}
                ).get("timezone")
                or DEFAULT_TIMEZONE
            )
            time_unit = pick_time_unit(service.get("availableUsageTimeUnits"))
            _LOGGER.debug("Origin Energy usage granularity: %s", time_unit)

            return {
                # Persist the cookie Auth0 handed back, not the one pasted in
                # -- it may already have been rolled forward.
                CONF_SESSION_COOKIE: current_session_cookie(session) or cookie,
                CONF_AGREEMENT_ID: service["agreementId"],
                CONF_TIMEZONE: timezone,
                CONF_TIME_UNIT: time_unit,
                "nmi": (service.get("meterPoint") or {}).get("identifier"),
            }, None
        except OriginEnergyBlocked:
            # The cookie may be perfectly good; telling the user to copy it
            # again would send them chasing the wrong thing.
            return None, "blocked"
        except OriginEnergyAuthError:
            return None, "invalid_auth"
        except OriginEnergyApiError:
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error setting up Origin Energy")
            return None, "unknown"
        finally:
            session.detach()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            data, error = await self._async_validate(
                user_input[CONF_SESSION_COOKIE].strip()
            )
            if error:
                errors["base"] = error
            else:
                assert data is not None
                await self.async_set_unique_id(data[CONF_AGREEMENT_ID])
                self._abort_if_unique_id_configured()
                nmi = data.pop("nmi", None)
                return self.async_create_entry(
                    title=f"Origin Energy ({nmi})" if nmi else "Origin Energy",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Triggered when the stored session cookie stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            data, error = await self._async_validate(
                user_input[CONF_SESSION_COOKIE].strip()
            )
            if error:
                errors["base"] = error
            else:
                assert data is not None
                data.pop("nmi", None)
                # Signing in as a different customer would otherwise rewrite
                # this entry's agreement id, silently pointing years of
                # statistics at someone else's meter.
                await self.async_set_unique_id(data[CONF_AGREEMENT_ID])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                # Keep the existing unique_id/entry so statistics history and
                # the Energy dashboard wiring survive the re-auth.
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=data
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
