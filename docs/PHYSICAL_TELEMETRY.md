# TrackShift — Real Physical Sensor Telemetry Architecture & Ingestion Guide

TrackShift incorporates an authoritative, hardware-agnostic physical telemetry ingestion layer that bridges real microcontrollers, sensors, and hardware gateways directly to the TrackShift analytics engine and frontend dashboard in real time.

---

## 1. Architectural Overview

```
                      PHYSICAL ENVIRONMENT
                (Tyres, Brake Rotors, Ambient Track)
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       MLX90614 / Thermistors        Analog Pressure Sensors
      (Infrared Tyre Temp °C)         (0-5V / 0-3.3V Transducers)
               │                               │
               └───────────────┬───────────────┘
                               ▼
                MICROCONTROLLER / GATEWAY LAYER
               (ESP32 / Arduino / Raspberry Pi)
                               │
               ┌───────────────┴───────────────┐
        Wi-Fi HTTP POST                   USB Serial
    /api/physical-telemetry/ingest      COM3 / /dev/ttyUSB0
               │                               │
               │                    serial_gateway.py
               │                               │
               └───────────────┬───────────────┘
                               ▼
                     FASTAPI INGESTION PORT
                     (Port 8000 / Auth & Rate Limit)
                               │
                               ▼
                     TELEMETRY VALIDATION
              (Physical Ranges, Sequence, Schema)
                               │
                               ▼
                     NORMALIZED TELEMETRY
              (Canonical Units: °C, bar, psi, km/h)
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
      TDSM Boundary Partition           WebSocket Fan-Out
     (Model Architecture Frozen)      /ws/physical-telemetry
                                               │
                                               ▼
                                      TRACKSHIFT FRONTEND
                                   (Physical Telemetry Tab)
```

---

## 2. Ingestion API Specification

### Endpoint: `POST /api/physical-telemetry/ingest`
- **Port**: `8000`
- **Content-Type**: `application/json`
- **Header**: `X-Device-Key` (Configurable via `PHYSICAL_DEVICE_KEY` environment variable; default: `trackshift_dev_key_2025`)

### Ingestion Packet Schema (JSON)
```json
{
  "device_id": "TRACKSHIFT-ESP32-01",
  "timestamp": 1726200000.125,
  "sequence": 1042,
  "transport": "HTTP_WIFI",
  "sensors": {
    "tyre_temperature": {
      "FL": 82.4,
      "FR": 84.1,
      "RL": 79.8,
      "RR": 81.2
    },
    "tyre_pressure": {
      "FL": 21.3,
      "FR": 21.5,
      "RL": 20.9,
      "RR": 21.1
    },
    "tyre_pressure_unit": "psi",
    "ambient_temperature": 24.5,
    "track_temperature": 34.8,
    "wheel_speed": 215.4
  }
}
```

> [!IMPORTANT]
> **Strict Physical Truth Rule**:
> Only include sensors that physically exist and are functioning on the connected device. If your physical microcontroller only has an infrared sensor for the Front-Left tyre, **do not include dummy or zero values for the other corners**. The backend will accurately register the Front-Left corner and mark unequipped sensors as offline.

---

## 3. Physical Validation and Range Bounds

Every packet is verified against physical limits. Impossible values are rejected with **HTTP 422**:

| Sensor | Canonical Unit | Valid Physical Range | Rejection Example |
|---|---|---|---|
| **Tyre Temperature** | $^\circ\text{C}$ | $-40.0^\circ\text{C}$ to $+200.0^\circ\text{C}$ | $999999.0^\circ\text{C}$ $\rightarrow$ HTTP 422 |
| **Tyre Pressure** | $\text{bar}$ (or $\text{psi}$) | $0.0$ to $5.0\text{ bar}$ ($0$ to $72.5\text{ psi}$) | $-5.0\text{ bar}$ $\rightarrow$ HTTP 422 |
| **Ambient Temperature** | $^\circ\text{C}$ | $-30.0^\circ\text{C}$ to $+70.0^\circ\text{C}$ | $150.0^\circ\text{C}$ $\rightarrow$ HTTP 422 |
| **Track Temperature** | $^\circ\text{C}$ | $-20.0^\circ\text{C}$ to $+95.0^\circ\text{C}$ | $-80.0^\circ\text{C}$ $\rightarrow$ HTTP 422 |
| **Wheel Speed** | $\text{km/h}$ | $0.0$ to $450.0\text{ km/h}$ | $1200.0\text{ km/h}$ $\rightarrow$ HTTP 422 |

---

## 4. Heartbeat & Connection State Machine

The backend dynamically tracks packet freshness for every registered device:

- **`ONLINE`** (Emerald): A valid packet has been ingested within **$2.5\text{ seconds}$**.
- **`STALE`** (Amber): No packet received within **$2.5\text{s} - 5.0\text{s}$**.
- **`OFFLINE`** (Crimson): No packet received for **$> 5.0\text{ seconds}$** or device unequipped.

When offline, the frontend immediately displays **`PHYSICAL SENSOR OFFLINE`**. Under no circumstances will synthetic, random, or estimated values be generated.

---

## 5. Dedicated Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/physical-telemetry/ingest` | Authoritative packet ingestion from microcontrollers. |
| `GET` | `/api/physical-telemetry/status` | Heartbeat summary (online devices, packet count, timeouts). |
| `GET` | `/api/physical-telemetry/devices` | Detailed list of registered devices and per-sensor health. |
| `GET` | `/api/physical-telemetry/latest/{device_id}` | Latest normalized readings with unit conversions. |
| `GET` | `/api/physical-telemetry/history/{device_id}` | Time-series history for gap-accurate charting. |
| `WS` | `/ws/physical-telemetry` | Real-time WebSocket event fan-out to connected clients. |

---

## 6. Microcontroller Setup

### A. Wi-Fi Microcontroller (ESP32)
1. Open [`scripts/hardware/esp32_firmware_sample.ino`](file:///c:/Users/harsh/Downloads/TrackShift-main/scripts/hardware/esp32_firmware_sample.ino) in the Arduino IDE.
2. Install libraries: `ArduinoJson` (v6+) and `Adafruit_MLX90614`.
3. Set your Wi-Fi credentials (`WIFI_SSID`, `WIFI_PASSWORD`).
4. Set `INGEST_URL` to your TrackShift server address (e.g. `http://192.168.1.100:8000/api/physical-telemetry/ingest`).
5. Flash to the ESP32. As soon as packets arrive, the dashboard turns `ONLINE`.

### B. USB Serial Gateway (Windows COM3/COM4 or Linux /dev/ttyUSB0)
Connect any serial device outputting JSON lines and run the serial gateway:
```powershell
python scripts/hardware/serial_gateway.py --port COM3 --baud 115200 --device-id TRACKSHIFT-SERIAL-01
```

### C. Live Test Harness
To verify the end-to-end pipeline without physical hardware:
```powershell
# Send 20 verified packets at 2 Hz
python scripts/hardware/test_physical_sender.py --count 20 --hz 2.0

# Verify 422 rejection of impossible values
python scripts/hardware/test_physical_sender.py --impossible-val
```

---

## 7. Provenance and Scientific Separation

TrackShift strictly separates data sources:
* **`REAL PHYSICAL SENSOR TELEMETRY`**: Measured from microcontrollers/gateways.
* **`REAL HISTORICAL F1 TELEMETRY`**: Canonical session laps from FastF1.
* **`ACTUAL TDSM MODEL OUTPUT`**: Scientific multi-horizon degradation predictions ($S_t = [D_t, \Delta D_t, \Delta^2 D_t]$).

Physical telemetry is displayed alongside TDSM in the dedicated **`PHYSICAL SENSORS`** tab and is never secretly injected into frozen model features.
