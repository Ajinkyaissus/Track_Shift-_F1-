/*
 * TrackShift ESP32 Physical Telemetry Firmware Sample
 * 
 * Hardware:
 *   - ESP32 Development Board (e.g. NodeMCU ESP-32S)
 *   - MLX90614 Contactless Infrared Temperature Sensor (I2C) for Tyre Surface
 *   - Analog 0-5V / 0-3.3V Tyre Pressure Transducer
 *   - DHT22 / BME280 for Ambient Temperature
 * 
 * Communication:
 *   - Wi-Fi Station Mode
 *   - HTTP POST to http://<TRACKSHIFT_SERVER_IP>:8000/api/physical-telemetry/ingest
 *   - Packet Rate: 10 Hz
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>

// Wi-Fi Credentials
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// TrackShift API Ingestion Port
const char* INGEST_URL = "http://192.168.1.100:8000/api/physical-telemetry/ingest";
const char* DEVICE_ID = "TRACKSHIFT-ESP32-01";
const char* DEVICE_KEY = "trackshift_dev_key_2025";

// Hardware Sensor Pins
const int PRESSURE_PIN_FL = 34; // Analog ADC input
const int MLX90614_I2C_ADDR = 0x5A; // I2C address for MLX90614

unsigned long lastTransmitTime = 0;
const unsigned long TRANSMIT_INTERVAL_MS = 100; // 10 Hz (100ms)
unsigned long sequence = 1;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[TrackShift] Initializing Physical Telemetry Gateway...");

  Wire.begin(21, 22); // SDA = 21, SCL = 22 on ESP32
  pinMode(PRESSURE_PIN_FL, INPUT);

  // Connect to Wi-Fi
  Serial.print("[TrackShift] Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n[TrackShift] Wi-Fi Connected!");
  Serial.print("[TrackShift] IP Address: ");
  Serial.println(WiFi.localIP());
}

float readInfraredTyreTemp() {
  // Read MLX90614 Object Temperature over I2C
  Wire.beginTransmission(MLX90614_I2C_ADDR);
  Wire.write(0x07); // RAM Access Command for TOBJ1 (Object Temperature)
  if (Wire.endTransmission(false) != 0) {
    return -999.0; // Sensor offline or disconnected
  }

  Wire.requestFrom(MLX90614_I2C_ADDR, 3);
  if (Wire.available() >= 2) {
    uint16_t raw = Wire.read() | (Wire.read() << 8);
    Wire.read(); // Read PEC (checksum)
    float tempC = (raw * 0.02) - 273.15;
    return tempC;
  }
  return -999.0;
}

float readTyrePressurePsi() {
  // Read analog transducer (0-3.3V maps to 0-50 PSI)
  int adcVal = analogRead(PRESSURE_PIN_FL);
  float voltage = (adcVal / 4095.0) * 3.3;
  // Calibration: 0.5V = 0 psi, 4.5V scaled to 3.3V divisor
  float psi = (voltage - 0.33) * 15.0;
  if (psi < 0.0) psi = 0.0;
  return psi;
}

void loop() {
  unsigned long now = millis();

  if (now - lastTransmitTime >= TRANSMIT_INTERVAL_MS) {
    lastTransmitTime = now;

    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[TrackShift] Wi-Fi disconnected. Reconnecting...");
      WiFi.reconnect();
      return;
    }

    float tyreTempFL = readInfraredTyreTemp();
    float tyrePressureFL = readTyrePressurePsi();

    // Create JSON document
    StaticJsonDocument<512> doc;
    doc["device_id"] = DEVICE_ID;
    doc["timestamp"] = now / 1000.0;
    doc["sequence"] = sequence++;
    doc["transport"] = "HTTP_WIFI";

    JsonObject sensors = doc.createNestedObject("sensors");

    // Only include sensors that are physically connected and responding
    if (tyreTempFL > -40.0 && tyreTempFL < 200.0) {
      JsonObject temps = sensors.createNestedObject("tyre_temperature");
      temps["FL"] = tyreTempFL;
      // If equipped with multiple sensors, add FR, RL, RR here
    }

    if (tyrePressureFL >= 0.0 && tyrePressureFL <= 70.0) {
      JsonObject pressures = sensors.createNestedObject("tyre_pressure");
      pressures["FL"] = tyrePressureFL;
      sensors["tyre_pressure_unit"] = "psi";
    }

    sensors["ambient_temperature"] = 23.5;

    // Serialize JSON
    String requestBody;
    serializeJson(doc, requestBody);

    // Send HTTP POST
    HTTPClient http;
    http.begin(INGEST_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Key", DEVICE_KEY);

    int httpResponseCode = http.POST(requestBody);

    if (httpResponseCode == 200) {
      Serial.printf("[TrackShift] Ingested packet #%lu (HTTP 200)\n", sequence - 1);
    } else {
      Serial.printf("[TrackShift] Ingest failed: HTTP %d\n", httpResponseCode);
    }

    http.end();
  }
}
