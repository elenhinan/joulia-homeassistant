# Joulia / Aneo Mobility Cloud API Documentation

This documentation provides the reverse-engineered API specification for **Joulia EV Charging** (formerly Aneo Mobility / Elaway), analyzed from the Android application package `com.aneo.mobility.ladeapp` (v1.37.2).

---

## 1. Architecture & Environments

The application is built on **React Native / Expo** compiled with Meta's **Hermes JavaScript Engine** (`index.android.bundle`). The backend infrastructure integrates with **UtilityCloud**, **AMPECO**, and hardware protocols via an OpenAPI/Orval-based service architecture with Microsoft **SignalR** for real-time WebSocket events.

### Base URLs

| Environment | Base URL | Usage |
| :--- | :--- | :--- |
| **Production API** | `https://api.aneomobility.com` | Primary API for customer apps and portals |
| **Test / Staging API** | `https://api-test.aneomobility.com` | Internal testing / staging backend |
| **SignalR Realtime Hub** | `https://api.aneomobility.com/hubs/chargers` | WebSocket streaming for live charger state and meter updates |
| **Customer Portal** | `https://portal.aneomobility.com` / `https://my.joulia.io` | Web dashboard |
| **Criipto BankID Auth** | `https://aneomobility.criipto.id` | Nordic electronic identity verification (BankID) |

---

## 2. Authentication & Session Persistence

### Authentication Flow

Authentication uses standard **JSON Web Tokens (JWT)** with long-lived **Refresh Tokens**:

1. **Initial Authentication (`POST /api/account/authenticate`)**
   - **Payload**:
     ```json
     {
       "username": "user@example.com",
       "password": "your_password"
     }
     ```
   - **Response (`TokenInfoSchema`)**:
     ```json
     {
       "id": "<user_uuid>",
       "userName": "user@example.com",
       "accessToken": "<access_token_jwt>",
       "refreshToken": "<long_lived_refresh_token_string>",
       "refreshTokenExpiresAt": "2027-01-01T00:00:00.000Z"
     }
     ```

2. **Token Refresh (`POST /api/account/token/refresh`)**
   - The refresh token has a **90-day validity window**.
   - **Payload**:
     ```json
     {
       "userId": "<user_uuid>",
       "refreshToken": "<long_lived_refresh_token_string>"
     }
     ```
   - **Response**:
     ```json
     {
       "accessToken": "<new_access_token_jwt>",
       "refreshToken": "<new_rolling_refresh_token_string>",
       "expiresAt": "2027-04-01T00:00:00.000Z"
     }
     ```

3. **Required HTTP Headers**
   All subsequent API requests require standard Authorization headers:
   - `Authorization: Bearer <accessToken>`
   - `Content-Type: application/json`
   - `Accept: application/json`
   - `User-Agent: Joulia-Charge/1.37.2 (Android; HA-Integration)`

---

## 3. Core API Endpoints

### 3.1 Subscriptions & Facilities

#### List Account Subscriptions
* **Method**: `GET`
* **Route**: `/api/subscription/v3/subscriptions`
* **Description**: Returns all housing facilities, parking lots, and assigned chargers connected to the authenticated user account.
* **Response Sample (`List[SubscriptionDtov3]`)**:
```json
[
  {
    "id": "<subscription_uuid>",
    "crmId": "<crm_subscription_id>",
    "status": "Active",
    "chargingFacilityId": "<facility_id>",
    "chargingFacilityName": "Housing Community (Assigned Spots)",
    "housingCompanyName": "Housing Community Name",
    "countryCode": "NO",
    "charger": {
      "chargerId": "<CHARGER_SERIAL_ID>",
      "chargerOwnership": "Aneo Norway",
      "supplier": "Easee"
    },
    "parkingLot": {
      "id": "<parking_lot_id>",
      "name": "12",
      "chargingBoxSupplier": "Easee"
    },
    "fixedParking": true,
    "canOverrideChargerAccessControl": true,
    "hasChargerAccessControlOverrideEnabled": false,
    "chargerInstallationStatus": "Installed"
  }
]
```

---

### 3.2 Charger Details & Live Status

#### Get Charger by ID (v2)
* **Method**: `GET`
* **Route**: `/api/chargingpoint/v2/{chargerId}`
* **Parameters**: `chargerId` (e.g. `<CHARGER_SERIAL_ID>`)
* **Description**: Returns hardware model, online status, socket states, permanently locked cable state, capabilities, and firmware configurations.
* **Response Sample (`ChargerDtov2`)**:
```json
{
  "id": 100001,
  "chargerId": "<CHARGER_SERIAL_ID>",
  "manufacturer": "Easee",
  "chargerModel": "Easee Charge",
  "chargerStatus": "Available",
  "lastSeen": "2026-10-26T18:00:00.000Z",
  "sockets": [
    {
      "id": 1,
      "status": "Charging",
      "isCableLockedPermanently": false,
      "isInFreeChargingMode": true,
      "freeChargingRfidTag": "<rfid_tag>",
      "isOwned": true,
      "lastUpdated": "2026-10-26T18:00:00.000Z"
    }
  ],
  "capabilities": {
    "lockCable": { "capable": true, "reason": null },
    "accessControl": { "capable": true, "reason": null },
    "reboot": { "capable": true, "reason": null },
    "remoteStart": { "capable": true, "reason": null },
    "remoteStop": { "capable": true, "reason": null },
    "scheduling": { "capable": false, "reason": "NotSupported" }
  }
}
```

---

### 3.3 Active Charging Session

#### Get Socket Active Session
* **Method**: `GET`
* **Route**: `/api/chargingpoint/{chargerId}/{socketId}/session`
* **Parameters**:
  - `chargerId`: string (e.g. `<CHARGER_SERIAL_ID>`)
  - `socketId`: integer (typically `1`)
* **Response Sample (`OngoingSessionDto`)**:
```json
{
  "startTime": "2026-10-26T16:00:00.000Z",
  "totalKwh": 14.52,
  "currentKw": null
}
```

---

### 3.4 Charger Controls

#### 1. Set Cable Lock (Lock/Unlock Cable)
* **Method**: `POST`
* **Route**: `/api/chargingpoint/v3/set-cable-lock`
* **Request Body**:
```json
{
  "chargerId": "<CHARGER_SERIAL_ID>",
  "socketId": 1,
  "isCableLockedPermanently": true
}
```
* **Response**: `200 OK` (`{}`)

#### 2. Start Charging (Remote Start Transaction)
* **Method**: `POST`
* **Route**: `/api/chargingpoint/v3/transaction/start`
* **Request Body**:
```json
{
  "chargerId": "<CHARGER_SERIAL_ID>",
  "socketId": 1,
  "subscriptionId": "<subscription_uuid>"
}
```
* **Response**: `200 OK` / `CommandResult`

#### 3. Stop Charging (Remote Stop Transaction)
* **Method**: `POST`
* **Route**: `/api/chargingpoint/v3/transaction/stop`
* **Request Body**:
```json
{
  "chargerId": "<CHARGER_SERIAL_ID>",
  "socketId": 1,
  "subscriptionId": "<subscription_uuid>"
}
```
* **Response**:
```json
{
  "response": "STOP_TX_CMD_SUCCESS",
  "cpmsResponse": "",
  "charger": { "id": 100001, "status": "Available" }
}
```

#### 4. Reboot Charger
* **Method**: `POST`
* **Route**: `/api/chargingpoint/shared/charger/reboot`
* **Request Body**:
```json
{
  "chargerId": "<CHARGER_SERIAL_ID>"
}
```

---

### 3.5 Energy Consumption & Spot Prices

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/utilitycloudconsumption/subscription/{subscriptionId}/consumption-daily` | `GET` | Historical daily power consumption (kWh) |
| `/api/utilitycloudconsumption/subscription/{subscriptionId}/consumption-monthly` | `GET` | Monthly aggregated energy totals & costs |
| `/api/utilitycloudconsumption/subscription/{subscriptionId}/hour-prices` | `GET` | Dynamic spot prices per hour for smart charging |
| `/api/powerconsumption/subscription/{subscriptionId}/transactions` | `GET` | Completed charging transactions history |
| `/api/rfid` | `GET` | Registered RFID charging tags/chips |
