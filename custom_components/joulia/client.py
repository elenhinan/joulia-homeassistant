"""Client library for Joulia (Aneo Mobility) Cloud API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

DEFAULT_BASE_URL = "https://api.aneomobility.com"


@dataclass
class AuthTokens:
    user_id: str
    username: str
    access_token: str
    refresh_token: str
    refresh_token_expires_at: Optional[datetime] = None


@dataclass
class SocketInfo:
    id: int
    status: str
    is_cable_locked_permanently: bool
    is_in_free_charging_mode: bool
    free_charging_rfid_tag: Optional[str]
    is_owned: bool
    last_updated: Optional[str] = None


@dataclass
class ChargerCapabilities:
    lock_cable: bool
    access_control: bool
    reboot: bool
    remote_start: bool
    remote_stop: bool
    scheduling: bool


@dataclass
class ChargerDetails:
    id: int
    charger_id: str
    manufacturer: str
    charger_model: str
    charger_status: str
    last_seen: Optional[str]
    sockets: List[SocketInfo]
    capabilities: ChargerCapabilities
    cell_rssi: Optional[int] = None
    wifi_rssi: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActiveSession:
    start_time: Optional[str]
    total_kwh: float
    current_kw: Optional[float]


@dataclass
class Subscription:
    id: str
    crm_id: str
    status: str
    charging_facility_id: str
    charging_facility_name: str
    housing_company_name: str
    country_code: str
    charger_id: str
    supplier: str
    parking_lot_name: str


class JouliaApiError(Exception):
    """Base exception for Joulia API errors."""
    pass


class JouliaAuthError(JouliaApiError):
    """Authentication or token error."""
    pass


class JouliaClient:
    """Async HTTP client for Joulia (Aneo Mobility) EV Charger Cloud API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
        tokens: Optional[AuthTokens] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.tokens: Optional[AuthTokens] = tokens
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> JouliaClient:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "Joulia-Charge/1.37.2 (HomeAssistant-Integration)",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Joulia-Charge/1.37.2 (HomeAssistant-Integration)",
                },
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def authenticate(self, username: str, password: str) -> AuthTokens:
        """Authenticate with username (email) and password."""
        client = self._ensure_client()
        url = "/api/account/authenticate"
        payload = {"username": username, "password": password}

        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise JouliaAuthError(f"Authentication failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        expires_at = None
        if "refreshTokenExpiresAt" in data and data["refreshTokenExpiresAt"]:
            try:
                expires_at = datetime.fromisoformat(data["refreshTokenExpiresAt"].replace("Z", "+00:00"))
            except ValueError:
                pass

        self.tokens = AuthTokens(
            user_id=data["id"],
            username=data["userName"],
            access_token=data["accessToken"],
            refresh_token=data["refreshToken"],
            refresh_token_expires_at=expires_at,
        )
        return self.tokens

    async def refresh_token(self) -> AuthTokens:
        """Refresh access token using the persistent refresh token."""
        if not self.tokens or not self.tokens.refresh_token:
            raise JouliaAuthError("No refresh token available.")

        client = self._ensure_client()
        url = "/api/account/token/refresh"
        payload = {
            "userId": self.tokens.user_id,
            "refreshToken": self.tokens.refresh_token,
        }

        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise JouliaAuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        self.tokens.access_token = data["accessToken"]
        self.tokens.refresh_token = data.get("refreshToken", self.tokens.refresh_token)
        if "expiresAt" in data and data["expiresAt"]:
            try:
                self.tokens.refresh_token_expires_at = datetime.fromisoformat(
                    data["expiresAt"].replace("Z", "+00:00")
                )
            except ValueError:
                pass

        return self.tokens

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """Perform an authenticated request with automatic token refresh."""
        client = self._ensure_client()
        headers = {}
        if self.tokens and self.tokens.access_token:
            headers["Authorization"] = f"Bearer {self.tokens.access_token}"

        resp = await client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code == 401 and retry_on_401 and self.tokens and self.tokens.refresh_token:
            await self.refresh_token()
            headers["Authorization"] = f"Bearer {self.tokens.access_token}"
            resp = await client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code >= 400:
            raise JouliaApiError(f"Request {method} {path} failed ({resp.status_code}): {resp.text}")

        return resp

    async def get_subscriptions(self) -> List[Subscription]:
        """List all subscriptions and assigned chargers for the account."""
        resp = await self._request("GET", "/api/subscription/v3/subscriptions")
        data = resp.json()
        results: List[Subscription] = []
        for item in data:
            charger_info = item.get("charger") or {}
            parking_info = item.get("parkingLot") or {}
            results.append(
                Subscription(
                    id=item.get("id", ""),
                    crm_id=item.get("crmId", ""),
                    status=item.get("status", ""),
                    charging_facility_id=item.get("chargingFacilityId", ""),
                    charging_facility_name=item.get("chargingFacilityName", ""),
                    housing_company_name=item.get("housingCompanyName", ""),
                    country_code=item.get("countryCode", "NO"),
                    charger_id=charger_info.get("chargerId", ""),
                    supplier=charger_info.get("supplier", ""),
                    parking_lot_name=parking_info.get("name", ""),
                )
            )
        return results

    async def get_charger_details(self, charger_id: str) -> ChargerDetails:
        """Get live charger information, sockets, and capabilities by charger ID."""
        resp = await self._request("GET", f"/api/chargingpoint/v2/{charger_id}")
        data = resp.json()

        sockets = []
        for s in data.get("sockets", []):
            sockets.append(
                SocketInfo(
                    id=s.get("id", 1),
                    status=s.get("status", "Unknown"),
                    is_cable_locked_permanently=s.get("isCableLockedPermanently", False),
                    is_in_free_charging_mode=s.get("isInFreeChargingMode", False),
                    free_charging_rfid_tag=s.get("freeChargingRfidTag"),
                    is_owned=s.get("isOwned", False),
                    last_updated=s.get("lastUpdated"),
                )
            )

        caps_raw = data.get("capabilities", {})
        capabilities = ChargerCapabilities(
            lock_cable=caps_raw.get("lockCable", {}).get("capable", False),
            access_control=caps_raw.get("accessControl", {}).get("capable", False),
            reboot=caps_raw.get("reboot", {}).get("capable", False),
            remote_start=caps_raw.get("remoteStart", {}).get("capable", False),
            remote_stop=caps_raw.get("remoteStop", {}).get("capable", False),
            scheduling=caps_raw.get("scheduling", {}).get("capable", False),
        )

        cell_rssi = None
        wifi_rssi = None
        for cfg in data.get("chargerConfigurations", []):
            if cfg.get("configName") == "CellRSSI":
                try:
                    cell_rssi = int(cfg.get("configValue", ""))
                except (ValueError, TypeError):
                    pass
            elif cfg.get("configName") == "WiFiRSSI":
                try:
                    wifi_rssi = int(cfg.get("configValue", ""))
                except (ValueError, TypeError):
                    pass

        return ChargerDetails(
            id=data.get("id", 0),
            charger_id=data.get("chargerId", charger_id),
            manufacturer=data.get("manufacturer", ""),
            charger_model=data.get("chargerModel", ""),
            charger_status=data.get("chargerStatus", "Unknown"),
            last_seen=data.get("lastSeen"),
            sockets=sockets,
            capabilities=capabilities,
            cell_rssi=cell_rssi,
            wifi_rssi=wifi_rssi,
            raw=data,
        )

    async def get_session(self, charger_id: str, socket_id: int = 1) -> ActiveSession:
        """Get the current charging session stats (kWh delivered, power in kW, start time)."""
        resp = await self._request("GET", f"/api/chargingpoint/{charger_id}/{socket_id}/session")
        data = resp.json()
        return ActiveSession(
            start_time=data.get("startTime"),
            total_kwh=data.get("totalKwh", 0.0),
            current_kw=data.get("currentKw"),
        )

    async def set_cable_lock(self, charger_id: str, socket_id: int, locked: bool) -> bool:
        """Lock or unlock the charging cable permanently."""
        payload = {
            "chargerId": charger_id,
            "socketId": socket_id,
            "isCableLockedPermanently": locked,
        }
        resp = await self._request("POST", "/api/chargingpoint/v3/set-cable-lock", json=payload)
        return resp.status_code == 200

    async def start_transaction(
        self, charger_id: str, socket_id: int, subscription_id: str
    ) -> Dict[str, Any]:
        """Send remote start transaction command to the charger."""
        payload = {
            "chargerId": charger_id,
            "socketId": socket_id,
            "subscriptionId": subscription_id,
        }
        resp = await self._request("POST", "/api/chargingpoint/v3/transaction/start", json=payload)
        return resp.json()

    async def stop_transaction(
        self, charger_id: str, socket_id: int, subscription_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send remote stop transaction command to the charger."""
        payload = {
            "chargerId": charger_id,
            "socketId": socket_id,
        }
        if subscription_id:
            payload["subscriptionId"] = subscription_id

        resp = await self._request("POST", "/api/chargingpoint/v3/transaction/stop", json=payload)
        return resp.json()

    async def reboot_charger(self, charger_id: str) -> bool:
        """Reboot the charger hardware."""
        payload = {"chargerId": charger_id}
        resp = await self._request("POST", "/api/chargingpoint/shared/charger/reboot", json=payload)
        return resp.status_code == 200

