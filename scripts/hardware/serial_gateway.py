"""
TrackShift USB Serial Physical Telemetry Gateway.

Bridges microcontrollers (ESP32, Arduino, Raspberry Pi Pico) connected via USB Serial
(e.g., COM3, COM4 on Windows, /dev/ttyUSB0 on Linux) to the TrackShift FastAPI Ingestion Port.

Usage:
    python scripts/hardware/serial_gateway.py --port COM3 --baud 115200 --device-id TRACKSHIFT-SERIAL-01
"""

import os
import sys
import time
import json
import argparse
import requests

try:
    import serial
except ImportError:
    serial = None

DEFAULT_INGEST_URL = os.environ.get("TRACKSHIFT_INGEST_URL", "http://localhost:8000/api/physical-telemetry/ingest")
DEFAULT_DEVICE_KEY = os.environ.get("PHYSICAL_DEVICE_KEY", "trackshift_dev_key_2025")


def parse_args():
    parser = argparse.ArgumentParser(description="TrackShift USB Serial Gateway")
    parser.add_argument("--port", "-p", default=os.environ.get("DEVICE_PORT", "COM3"),
                        help="Serial/COM port (e.g. COM3, COM4, /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=int(os.environ.get("BAUD_RATE", 115200)),
                        help="Baud rate (default: 115200)")
    parser.add_argument("--device-id", "-d", default=os.environ.get("DEVICE_ID", "TRACKSHIFT-SERIAL-01"),
                        help="Device identifier")
    parser.add_argument("--url", "-u", default=DEFAULT_INGEST_URL,
                        help="FastAPI ingestion endpoint URL")
    parser.add_argument("--key", "-k", default=DEFAULT_DEVICE_KEY,
                        help="X-Device-Key authentication header")
    return parser.parse_args()


def run_gateway():
    args = parse_args()
    
    if serial is None:
        print("[ERROR] pyserial is not installed. Install with: pip install pyserial")
        sys.exit(1)

    print("==================================================")
    print(" TRACKSHIFT USB SERIAL TELEMETRY GATEWAY")
    print(f" Port:        {args.port}")
    print(f" Baud Rate:   {args.baud}")
    print(f" Device ID:   {args.device_id}")
    print(f" Ingest URL:  {args.url}")
    print("==================================================")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1.0)
        print(f"[ONLINE] Opened serial port {args.port} successfully.")
    except Exception as e:
        print(f"[OFFLINE] Failed to open serial port {args.port}: {e}")
        print("Ensure the microcontroller is plugged in and the correct COM port is specified.")
        sys.exit(1)

    seq = 1
    session = requests.Session()
    headers = {
        "Content-Type": "application/json",
        "X-Device-Key": args.key
    }

    try:
        while True:
            line = ser.readline().decode('utf-8', errors='replace').strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print(f"[WARN] Non-JSON serial line received: {line}")
                continue

            # Ensure packet envelope
            packet = {
                "device_id": data.get("device_id", args.device_id),
                "timestamp": data.get("timestamp", time.time()),
                "sequence": data.get("sequence", seq),
                "transport": "USB_SERIAL",
                "sensors": data.get("sensors", data)
            }
            seq += 1

            try:
                resp = session.post(args.url, json=packet, headers=headers, timeout=1.0)
                if resp.status_code == 200:
                    res_json = resp.json()
                    print(f"[INGESTED] Seq #{packet['sequence']} | Device: {packet['device_id']} | Sensors: {res_json.get('sensors_processed')}")
                else:
                    print(f"[REJECTED] HTTP {resp.status_code}: {resp.text}")
            except requests.RequestException as re:
                print(f"[ERROR] Ingestion endpoint unreachable: {re}")
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[STOPPED] Serial gateway stopped by user.")
    finally:
        ser.close()


if __name__ == "__main__":
    run_gateway()
