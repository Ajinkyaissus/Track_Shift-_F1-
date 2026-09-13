"""
TrackShift Physical Telemetry Service.

Authoritative ingestion, validation, unit normalization, rate limiting,
heartbeat tracking, and WebSocket fan-out for real physical sensors.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, Set
from collections import deque
from fastapi import WebSocket
import logging

logger = logging.getLogger("trackshift.physical_telemetry")

# Physical sensor validation limits (strict canonical ranges)
VALID_RANGES = {
    "tyre_temperature": (-40.0, 200.0),   # °C
    "tyre_pressure_bar": (0.0, 5.0),      # bar (0 to ~72.5 psi)
    "ambient_temperature": (-30.0, 70.0), # °C
    "track_temperature": (-20.0, 95.0),   # °C
    "wheel_speed": (0.0, 450.0),          # km/h
}

MAX_SENSOR_RATE_HZ = 50.0
ONLINE_TIMEOUT_SECONDS = 5.0
STALE_TIMEOUT_SECONDS = 2.5
MAX_HISTORY_PER_DEVICE = 1000


class PhysicalTelemetryValidationException(ValueError):
    """Raised when an incoming physical packet violates physical laws or schema requirements."""
    pass


class PhysicalTelemetryRateLimitException(Exception):
    """Raised when incoming packet frequency exceeds MAX_SENSOR_RATE_HZ."""
    pass


class PhysicalTelemetryService:
    """Authoritative singleton managing physical sensor telemetry ingestion and broadcasting."""

    def __init__(self):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, deque] = {}
        self._rate_timestamps: Dict[str, deque] = {}
        self._active_websockets: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._total_ingested = 0

    async def register_websocket(self, websocket: WebSocket):
        """Registers a frontend client for real-time sensor updates."""
        await websocket.accept()
        self._active_websockets.add(websocket)
        logger.info(f"[PhysicalTelemetry] WebSocket client connected. Active: {len(self._active_websockets)}")
        
        # Immediately send current state snapshot
        status_payload = self.get_global_status()
        try:
            await websocket.send_json({
                "type": "SNAPSHOT",
                "timestamp": time.time(),
                "status": status_payload,
                "devices": self.get_devices()
            })
        except Exception as e:
            logger.warning(f"[PhysicalTelemetry] Failed to send initial snapshot: {e}")

    def unregister_websocket(self, websocket: WebSocket):
        """Removes a disconnected frontend WebSocket client."""
        self._active_websockets.discard(websocket)
        logger.info(f"[PhysicalTelemetry] WebSocket client disconnected. Active: {len(self._active_websockets)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Fans out normalized packet or event to all active WebSocket listeners."""
        if not self._active_websockets:
            return
        
        disconnected = set()
        for ws in self._active_websockets:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)
        
        for ws in disconnected:
            self._active_websockets.discard(ws)

    def validate_and_normalize(self, raw_packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates schema, physical ranges, units, and sequence numbers.
        Normalizes to canonical units (°C, bar, psi, km/h).
        Rejects impossible or corrupt data.
        """
        if not isinstance(raw_packet, dict):
            raise PhysicalTelemetryValidationException("Packet must be a valid JSON object")

        device_id = raw_packet.get("device_id")
        if not device_id or not isinstance(device_id, str) or len(device_id.strip()) == 0:
            raise PhysicalTelemetryValidationException("Missing or invalid 'device_id'")
        device_id = device_id.strip()

        sequence = raw_packet.get("sequence")
        if sequence is None or not isinstance(sequence, int) or sequence < 0:
            raise PhysicalTelemetryValidationException("Missing or invalid non-negative 'sequence' integer")

        sensors = raw_packet.get("sensors")
        if not isinstance(sensors, dict) or len(sensors) == 0:
            raise PhysicalTelemetryValidationException("Packet must contain a non-empty 'sensors' mapping")

        # Ingestion timestamp
        now = time.time()
        packet_time = raw_packet.get("timestamp")
        if packet_time is None:
            normalized_time = now
        elif isinstance(packet_time, (int, float)):
            normalized_time = float(packet_time)
        elif isinstance(packet_time, str):
            try:
                import datetime
                dt = datetime.datetime.fromisoformat(packet_time.replace("Z", "+00:00"))
                normalized_time = dt.timestamp()
            except Exception:
                normalized_time = now
        else:
            normalized_time = now

        # Reject packets with absurd timestamps (> 1 day old or > 60s in future)
        if abs(now - normalized_time) > 86400:
            normalized_time = now

        # Rate limiting check (sliding 1-second window)
        if device_id not in self._rate_timestamps:
            self._rate_timestamps[device_id] = deque(maxlen=int(MAX_SENSOR_RATE_HZ * 2))
        
        rate_window = self._rate_timestamps[device_id]
        rate_window.append(now)
        # Purge entries older than 1 second
        while rate_window and now - rate_window[0] > 1.0:
            rate_window.popleft()
        
        current_hz = len(rate_window)
        if current_hz > MAX_SENSOR_RATE_HZ:
            raise PhysicalTelemetryRateLimitException(
                f"Device '{device_id}' exceeded MAX_SENSOR_RATE_HZ ({current_hz} Hz > {MAX_SENSOR_RATE_HZ} Hz)"
            )

        # Sequence check
        prev_dev = self._devices.get(device_id)
        is_duplicate = False
        is_out_of_order = False
        if prev_dev:
            last_seq = prev_dev.get("last_sequence", -1)
            if sequence == last_seq:
                is_duplicate = True
            elif sequence < last_seq:
                is_out_of_order = True

        normalized_sensors: Dict[str, Any] = {}
        sensor_status: Dict[str, str] = {}

        # 1. Tyre Temperatures (FL, FR, RL, RR in °C)
        if "tyre_temperature" in sensors:
            raw_temp = sensors["tyre_temperature"]
            if isinstance(raw_temp, dict):
                norm_temps = {}
                min_t, max_t = VALID_RANGES["tyre_temperature"]
                for corner in ["FL", "FR", "RL", "RR"]:
                    if corner in raw_temp and raw_temp[corner] is not None:
                        val = float(raw_temp[corner])
                        if not (min_t <= val <= max_t):
                            raise PhysicalTelemetryValidationException(
                                f"Tyre temperature {corner} impossible: {val}°C (must be {min_t} to {max_t}°C)"
                            )
                        norm_temps[corner] = round(val, 2)
                if norm_temps:
                    normalized_sensors["tyre_temperature"] = {
                        "unit": "°C",
                        "values": norm_temps
                    }
                    sensor_status["tyre_temperature"] = "online"

        # 2. Tyre Pressures (FL, FR, RL, RR in bar and psi)
        if "tyre_pressure" in sensors:
            raw_press = sensors["tyre_pressure"]
            if isinstance(raw_press, dict):
                norm_press_bar = {}
                norm_press_psi = {}
                min_b, max_b = VALID_RANGES["tyre_pressure_bar"]
                unit_hint = str(sensors.get("tyre_pressure_unit", "bar")).lower()

                for corner in ["FL", "FR", "RL", "RR"]:
                    if corner in raw_press and raw_press[corner] is not None:
                        val = float(raw_press[corner])
                        # Handle psi input conversion if explicitly marked
                        if unit_hint == "psi":
                            val_bar = val / 14.5038
                            val_psi = val
                        else:
                            val_bar = val
                            val_psi = val * 14.5038

                        if not (min_b <= val_bar <= max_b):
                            raise PhysicalTelemetryValidationException(
                                f"Tyre pressure {corner} impossible: {val_bar:.2f} bar (must be {min_b} to {max_b} bar)"
                            )
                        norm_press_bar[corner] = round(val_bar, 3)
                        norm_press_psi[corner] = round(val_psi, 1)

                if norm_press_bar:
                    normalized_sensors["tyre_pressure"] = {
                        "unit_canonical": "bar",
                        "values_bar": norm_press_bar,
                        "values_psi": norm_press_psi
                    }
                    sensor_status["tyre_pressure"] = "online"

        # 3. Ambient & Track Temperatures
        if "ambient_temperature" in sensors and sensors["ambient_temperature"] is not None:
            amb = float(sensors["ambient_temperature"])
            min_a, max_a = VALID_RANGES["ambient_temperature"]
            if not (min_a <= amb <= max_a):
                raise PhysicalTelemetryValidationException(
                    f"Ambient temperature impossible: {amb}°C (must be {min_a} to {max_a}°C)"
                )
            normalized_sensors["ambient_temperature"] = {"unit": "°C", "value": round(amb, 1)}
            sensor_status["ambient_temperature"] = "online"

        if "track_temperature" in sensors and sensors["track_temperature"] is not None:
            trk = float(sensors["track_temperature"])
            min_trk, max_trk = VALID_RANGES["track_temperature"]
            if not (min_trk <= trk <= max_trk):
                raise PhysicalTelemetryValidationException(
                    f"Track temperature impossible: {trk}°C (must be {min_trk} to {max_trk}°C)"
                )
            normalized_sensors["track_temperature"] = {"unit": "°C", "value": round(trk, 1)}
            sensor_status["track_temperature"] = "online"

        # 4. Wheel Speed / IMU if present
        if "wheel_speed" in sensors and sensors["wheel_speed"] is not None:
            spd = float(sensors["wheel_speed"])
            min_s, max_s = VALID_RANGES["wheel_speed"]
            if not (min_s <= spd <= max_s):
                raise PhysicalTelemetryValidationException(
                    f"Wheel speed impossible: {spd} km/h (must be {min_s} to {max_s} km/h)"
                )
            normalized_sensors["wheel_speed"] = {"unit": "km/h", "value": round(spd, 1)}
            sensor_status["wheel_speed"] = "online"

        if not normalized_sensors:
            raise PhysicalTelemetryValidationException(
                "No valid physical sensors recognized or measured in payload"
            )

        normalized_packet = {
            "device_id": device_id,
            "timestamp": normalized_time,
            "ingested_at": now,
            "sequence": sequence,
            "is_duplicate": is_duplicate,
            "is_out_of_order": is_out_of_order,
            "packet_rate_hz": round(float(current_hz), 1),
            "transport": raw_packet.get("transport", "HTTP_WIFI"),
            "sensors": normalized_sensors,
            "sensor_status": sensor_status,
            "provenance": {
                "source": "REAL PHYSICAL SENSOR TELEMETRY",
                "device_id": device_id,
                "authoritative_layer": "FastAPI Physical Ingestion Layer"
            }
        }

        return normalized_packet

    async def ingest_packet(self, raw_packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authoritative entry point for physical sensor packets.
        Validates, records state, updates history, and broadcasts via WebSocket.
        """
        normalized = self.validate_and_normalize(raw_packet)
        device_id = normalized["device_id"]
        now = time.time()

        async with self._lock:
            self._total_ingested += 1
            prev = self._devices.get(device_id, {})
            packet_count = prev.get("packet_count", 0) + 1

            self._devices[device_id] = {
                "device_id": device_id,
                "status": "online",
                "last_seen": now,
                "packet_count": packet_count,
                "last_sequence": normalized["sequence"],
                "packet_rate_hz": normalized["packet_rate_hz"],
                "transport": normalized["transport"],
                "latest_telemetry": normalized,
                "sensor_status": normalized["sensor_status"]
            }

            if device_id not in self._history:
                self._history[device_id] = deque(maxlen=MAX_HISTORY_PER_DEVICE)
            self._history[device_id].append(normalized)

        # Fan-out to connected frontends
        await self.broadcast({
            "type": "PHYSICAL_TELEMETRY_PACKET",
            "device_id": device_id,
            "packet": normalized
        })

        return {
            "status": "success",
            "device_id": device_id,
            "sequence": normalized["sequence"],
            "ingested_at": normalized["ingested_at"],
            "packet_rate_hz": normalized["packet_rate_hz"],
            "sensors_processed": list(normalized["sensors"].keys())
        }

    def evaluate_device_health(self, device_id: str) -> str:
        """Determines if a device is online, stale, or offline based on timeouts."""
        device = self._devices.get(device_id)
        if not device:
            return "offline"
        
        elapsed = time.time() - device["last_seen"]
        if elapsed <= STALE_TIMEOUT_SECONDS:
            return "online"
        elif elapsed <= ONLINE_TIMEOUT_SECONDS:
            return "stale"
        else:
            return "offline"

    def get_global_status(self) -> Dict[str, Any]:
        """Returns overall ingestion status and summary of connected devices."""
        now = time.time()
        online_count = 0
        stale_count = 0
        offline_count = 0

        for dev_id, dev in self._devices.items():
            status = self.evaluate_device_health(dev_id)
            if status == "online":
                online_count += 1
            elif status == "stale":
                stale_count += 1
            else:
                offline_count += 1

        overall_status = "online" if online_count > 0 else ("stale" if stale_count > 0 else "offline")

        return {
            "system_status": overall_status,
            "active_devices_online": online_count,
            "active_devices_stale": stale_count,
            "devices_offline": offline_count,
            "total_registered_devices": len(self._devices),
            "total_packets_ingested": self._total_ingested,
            "server_time": now,
            "max_sensor_rate_hz": MAX_SENSOR_RATE_HZ,
            "timeouts": {
                "stale_seconds": STALE_TIMEOUT_SECONDS,
                "offline_seconds": ONLINE_TIMEOUT_SECONDS
            }
        }

    def get_devices(self) -> List[Dict[str, Any]]:
        """Returns all registered physical devices with real-time health and sensor lists."""
        now = time.time()
        result = []
        for dev_id, dev in self._devices.items():
            health = self.evaluate_device_health(dev_id)
            elapsed = round(now - dev["last_seen"], 2)
            
            # Update individual sensor status if device is offline or stale
            sensors_health = {}
            for s_name, s_state in dev.get("sensor_status", {}).items():
                if health == "offline":
                    sensors_health[s_name] = "offline"
                elif health == "stale":
                    sensors_health[s_name] = "stale"
                else:
                    sensors_health[s_name] = s_state

            result.append({
                "device_id": dev_id,
                "status": health,
                "last_seen": dev["last_seen"],
                "seconds_since_last_packet": elapsed,
                "packet_count": dev["packet_count"],
                "last_sequence": dev["last_sequence"],
                "packet_rate_hz": dev["packet_rate_hz"] if health == "online" else 0.0,
                "transport": dev["transport"],
                "sensors": sensors_health
            })
        return result

    def get_latest(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Returns latest normalized telemetry for a specific physical device."""
        device = self._devices.get(device_id)
        if not device:
            return None
        
        health = self.evaluate_device_health(device_id)
        latest = dict(device["latest_telemetry"])
        latest["current_device_status"] = health
        latest["seconds_since_last_packet"] = round(time.time() - device["last_seen"], 2)
        return latest

    def get_history(self, device_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Returns recent packet history for a device (for timeline plotting)."""
        history = self._history.get(device_id)
        if not history:
            return []
        limit = min(limit, MAX_HISTORY_PER_DEVICE)
        return list(history)[-limit:]


# Global singleton instance
_physical_telemetry_service: Optional[PhysicalTelemetryService] = None


def get_physical_telemetry_service() -> PhysicalTelemetryService:
    global _physical_telemetry_service
    if _physical_telemetry_service is None:
        _physical_telemetry_service = PhysicalTelemetryService()
    return _physical_telemetry_service
