"""
TrackShift Physical Telemetry Hardware Adapters.

Defines hardware-agnostic transport abstractions for real physical sensors
communicating via HTTP POST, USB Serial / COM ports, or gateways.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import logging

logger = logging.getLogger("trackshift.hardware")


class PhysicalSensorAdapter(ABC):
    """Abstract base adapter for normalizing sensor streams from various physical transports."""

    @abstractmethod
    def parse_packet(self, raw_data: Any) -> Dict[str, Any]:
        """Parses and normalizes raw hardware payload into TrackShift canonical schema."""
        pass


class ESP32HTTPAdapter(PhysicalSensorAdapter):
    """Adapter for ESP32 / Arduino / Raspberry Pi sending JSON payloads over Wi-Fi HTTP POST."""

    def parse_packet(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw_data, dict):
            raise ValueError("Expected dictionary JSON payload from HTTP transport")
        
        # Ensure canonical transport metadata
        normalized = dict(raw_data)
        normalized["transport"] = "HTTP_WIFI"
        normalized["received_at"] = time.time()
        return normalized


class SerialGatewayAdapter(PhysicalSensorAdapter):
    """
    Adapter for microcontrollers streaming JSON/CSV lines over USB Serial
    (e.g., COM3, COM4 on Windows, /dev/ttyUSB0 on Linux).
    """

    def __init__(self, device_id: str = "TRACKSHIFT-SERIAL-01", baud_rate: int = 115200):
        self.device_id = device_id
        self.baud_rate = baud_rate

    def parse_packet(self, raw_data: Any) -> Dict[str, Any]:
        if isinstance(raw_data, str):
            import json
            raw_data = json.loads(raw_data.strip())
        
        if not isinstance(raw_data, dict):
            raise ValueError("Serial payload must parse to a JSON object")

        normalized = dict(raw_data)
        if "device_id" not in normalized:
            normalized["device_id"] = self.device_id
        normalized["transport"] = "USB_SERIAL"
        normalized["received_at"] = time.time()
        return normalized
