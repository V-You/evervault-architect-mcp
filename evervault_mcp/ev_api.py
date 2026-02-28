"""Evervault REST API client.

Wraps httpx for async HTTP calls to api.evervault.com.
Auth: HTTP Basic (app_id:api_key) per https://docs.evervault.com/api#authentication
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from evervault_mcp.errors import EvervaultAPIError

log = logging.getLogger("evervault_mcp.api")

BASE_URL = "https://api.evervault.com"
TIMEOUT = 5.0  # seconds -- demo reliability budget


class EvervaultClient:
    """Async client for the Evervault REST API."""

    def __init__(
        self,
        app_id: str | None = None,
        api_key: str | None = None,
    ):
        self.app_id = app_id or os.environ.get("EV_APP_ID", "")
        self.api_key = api_key or os.environ.get("EV_API_KEY", "")
        if not self.app_id or not self.api_key:
            log.warning(
                "EV_APP_ID or EV_API_KEY not set -- live API calls will fail"
            )
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                auth=(self.app_id, self.api_key),
                timeout=TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -- core endpoints -------------------------------------------------------

    async def encrypt(self, payload: Any) -> dict[str, Any]:
        """POST /encrypt -- encrypt any valid JSON value."""
        client = await self._get_client()
        log.info("encrypting payload (keys: %s)", _summarize_keys(payload))
        resp = await self._request(client, "POST", "/encrypt", json=payload)
        return resp

    async def inspect(self, token: str) -> dict[str, Any]:
        """POST /inspect -- inspect a single ev:... token."""
        client = await self._get_client()
        log.info("inspecting token")
        resp = await self._request(
            client, "POST", "/inspect", json={"token": token}
        )
        return resp

    async def inspect_many(self, tokens: list[str]) -> list[dict[str, Any]]:
        """Inspect multiple tokens by iterating the single-token API."""
        results = []
        for token in tokens:
            result = await self.inspect(token)
            results.append(result)
        return results

    # -- relay endpoints ------------------------------------------------------

    async def create_relay(
        self,
        destination_domain: str,
        routes: list[dict[str, Any]],
        encrypt_empty_strings: bool = False,
    ) -> dict[str, Any]:
        """POST /relays -- create a new Relay.

        Tool params use snake_case; this method maps to API camelCase.
        """
        client = await self._get_client()
        body = {
            "destinationDomain": destination_domain,
            "routes": routes,
            "encryptEmptyStrings": encrypt_empty_strings,
        }
        log.info("creating relay for %s (%d routes)", destination_domain, len(routes))
        return await self._request(client, "POST", "/relays", json=body)

    async def list_relays(self) -> list[dict[str, Any]]:
        """GET /relays -- list all relays for the current app.

        The API returns { "data": [...] }; we extract the array.
        """
        client = await self._get_client()
        log.info("listing relays")
        resp = await self._request(client, "GET", "/relays")
        # API wraps the list in a "data" key
        if isinstance(resp, dict) and "data" in resp:
            return resp["data"]
        return resp


    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Make an API request with standard error handling."""
        try:
            resp = await client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise EvervaultAPIError(
                code="timeout",
                message=f"API request timed out after {TIMEOUT}s",
                retriable=True,
                suggested_action="Check network connectivity and try again",
            ) from exc
        except httpx.HTTPError as exc:
            raise EvervaultAPIError(
                code="network_error",
                message=str(exc),
                retriable=True,
                suggested_action="Check network connectivity",
            ) from exc

        if resp.status_code == 401:
            raise EvervaultAPIError(
                code="ev_api_error",
                status=401,
                message="Authentication failed -- check EV_APP_ID and EV_API_KEY",
                retriable=False,
                suggested_action="Verify your API credentials in .env",
            )

        if resp.status_code >= 400:
            body = resp.text
            raise EvervaultAPIError(
                code="ev_api_error",
                status=resp.status_code,
                message=f"API returned {resp.status_code}: {body[:200]}",
                retriable=resp.status_code >= 500,
                suggested_action="Check the request payload and try again",
            )

        return resp.json()


def _summarize_keys(payload: Any) -> str:
    """Return a safe summary of payload keys for logging (no values)."""
    if isinstance(payload, dict):
        return ", ".join(payload.keys())
    return type(payload).__name__
