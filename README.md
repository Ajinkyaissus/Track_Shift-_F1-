# TrackShift — Formula 1 Real-Time Telemetry, TDSM Forecasting & Strategy Decision-Support System

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C.svg?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5.0+-646CFF.svg?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![FastF1](https://img.shields.io/badge/FastF1-3.4+-FF1801.svg?style=for-the-badge&logo=formula1&logoColor=white)](https://github.com/theOehrly/Fast-F1)
[![Hardware IoT](https://img.shields.io/badge/IoT-ESP32%20%7C%20Arduino%20%7C%20UDP-00599C.svg?style=for-the-badge&logo=arduino&logoColor=white)](#-physical-telemetry--hardware-integration)
[![Tests](https://img.shields.io/badge/Tests-217%20Passing%20(100%25)-brightgreen.svg?style=for-the-badge)](#-verification--tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

**A scientifically disciplined, causal race-performance forecasting, physical telemetry ingestion, and deterministic pit-strategy engine for modern Formula 1.**

<p align="center">
  <strong>Built by Harshit Ranbhare &bull; Ajinkya Supate &bull; Harshal Upadhye</strong>
</p>

[System Architecture](#-system-architecture) •
[Core Capabilities](#-core-capabilities) •
[Scientific Benchmarks](#-audited-scientific-metrics-2025-held-out-season) •
[Hardware Integration](#-physical-telemetry--hardware-integration) •
[Quickstart](#-quickstart-guide) •
[API Reference](#-api-endpoints-reference)

</div>

---

## 🏎️ Overview

> ⚡ **Original & In-House Architecture (OG)**: TrackShift is an original, ground-up engineering initiative. The **Tyre Degradation State Model (TDSM)** is our own custom model architecture—designed, mathematically formulated, trained from raw telemetry, and rigorously tested in-house across 22,197 laps. No off-the-shelf pre-trained models or generic third-party wrappers were used.

**TrackShift** is a state-of-the-art Formula 1 engineering platform designed to bridge the gap between high-frequency physics telemetry, machine-learned tyre degradation dynamics, and mission-critical pit wall strategy decisions.

Built on the **Tyre Degradation State Model (TDSM)**, the system models continuous tyre wear transitions across multi-lap horizons ($+1, +3, +5, +10$ laps) using causal temporal formulations trained strictly on chronological 2024 race telemetry, fully validated on 22,197 laps across the unseen 2025 season.

In addition to timing loop intelligence, TrackShift incorporates a **Physical Telemetry Ingestion Engine** capable of interfacing with direct CAN/Serial sensor feeds, ESP32/Arduino microcontroller rigs, and F1 23/24 UDP simulator telemetry to monitor tyre temperatures, pressures, and wheel slip in real time.

---

## 🏗️ System Architecture

```
                                  ┌─────────────────────────────────────────────────────────┐
                                  │                TELEMETRY INGESTION SOURCES               │
                                  ├────────────────────────────┬────────────────────────────┤
                                  │  FastF1 Live Timing Feed   │  Hardware / Sim Telemetry  │
                                  │  (Historical + Real-Time)  │  (ESP32, UDP 20777, BLE)   │
                                  └─────────────┬──────────────┴─────────────┬──────────────┘
                                                │                            │
                                                ▼                            ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           TRACKSHIFT CORE BACKEND (FASTAPI)                                       │
│                                                                                                                   │
│   ┌────────────────────────────────┐    ┌───────────────────────────────────┐    ┌────────────────────────────┐   │
│   │     PHYSICAL SENSOR ENGINE     │    │        TDSM FORECAST ENGINE       │    │     DETERMINISTIC STRATEGY │   │
│   │ • 50 Hz Hardware Ingestion     │    │ • State: S_t = (D, ΔD, Δ²D)       │    │ • Pit Window Optimization  │   │
│   │ • Tyre Thermal/Pressure Bands  │───>│ • Multi-Horizon (+1,+3,+5,+10 L)  │───>│ • Undercut Threat Scoring  │   │
│   │ • Lockup & Glaze Safety Alerts │    │ • Causal Feature Scaler (Frozen)  │    │ • Tyre Debt Liquidation    │   │
│   │ • Fail-Safe Watchdog           │    │ • High-Availability Fallback Mode │    │ • Tactical Driver Advisory │   │
│   └────────────────────────────────┘    └───────────────────────────────────┘    └────────────────────────────┘   │
└───────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                                            │ REST APIs + WebSockets
                                                            ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       TRACKSHIFT INTERACTIVE REACT 18 DASHBOARD                                   │
│                                                                                                                   │
│   ┌──────────────────────────────┐  ┌───────────────────────────────────┐  ┌──────────────────────────────────┐   │
│   │     24-CIRCUIT GPS MAPS      │  │        TDSM FORECAST PANEL        │  │     PHYSICAL TELEMETRY PANEL     │   │
│   │ Real GPS geometry, turns,    │  │ Multi-horizon trajectories, error │  │ Live tyre thermal matrix,        │   │
│   │ sectors & speed heatmaps     │  │ drift badges & confidence bands   │  │ PSI bars, wheel speeds & alarms  │   │
│   └──────────────────────────────┘  └───────────────────────────────────┘  └──────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Core Capabilities

### 1. Tyre Degradation State Model (TDSM)
- **Causal State Transitions**: Models tyre condition as a dynamic kinematic state $S_t = (D_t, \Delta D_t, \Delta^2 D_t)$ alongside environmental and stint context (Tyre Life, Fuel Proxy, Compound One-Hot).
- **Multi-Horizon Delta Forecasting**: Predicts forward degradation deltas $\Delta \hat{D}_{t+h}$ for $+1, +3, +5,$ and $+10$ laps into the future.
- **Fail-Safe Fallback**: Includes `FallbackTDSM`, ensuring zero silent downtime during live race operations while explicitly marking fallback provenance.

### 2. Deterministic Pit Wall Strategy Decision Engine
- **Tyre Cliff Avoidance**: Flags compounding degradation before the exponential thermal/mechanical cliff strikes ($D_t > 2.40\text{s}$, $\Delta^2 D_t > 0.25\text{s/lap}^2$).
- **Undercut Vulnerability Index**: Computes rival threat percentages ($0–100\%$) based on delta gap, pit delta ($26.0\text{s}$ nominal), and outlap gain.
- **Actionable Driver Advisory**: Emits deterministic instructions: `STAY OUT`, `PIT NOW`, `PUSH`, `MANAGE`, `ATTACK`, `DEFEND`, or `MONITOR`.

### 3. Physical Telemetry & Simulator Integration
- **Multi-Source Ingestion**: Native adapters for **F1 23 / F1 24 Game UDP** packets (Port 20777), **Arduino / ESP32** serial/Bluetooth microcontrollers, and mock test replay streams.
- **Critical Safety Alarms**: Detects tyre blistering ($>115^\circ\text{C}$), surface glazing ($<80^\circ\text{C}$), puncture pressure collapse ($<1.30\text{ bar}$), and sudden wheel lockups ($>4.5\text{G}$ deceleration).

### 4. 24-Circuit GPS Intelligence
- Complete vector GPS track geometry for all 24 Formula 1 calendar circuits.
- Turn numbering, DRS detection zones, speed traps, sector delta visual overlays, and multi-season driver stint comparisons.

---

## 📊 Audited Scientific Metrics (2025 Held-Out Season)

TDSM was trained exclusively on 2024 race telemetry (Rounds 1–18 train, Rounds 19–24 validation). It was evaluated across **22,197 laps over all 24 rounds of the unseen 2025 season** via strict causal walk-forward replay. No 2025 data was leaked into scaler parameters or model weights. Stint boundary horizons ($t + h \ge \text{stint length}$) are strictly masked (`mask = 0.0`) without synthetic data synthesis.

### Baseline Comparison

| Horizon | Metric | TDSM (Primary) | Persistence ($\hat{D} = D_t$) | Trend ($\hat{D} = D_t + h \Delta D$) | Scientific Significance |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **+1 Lap** | **MAE**<br>**RMSE**<br>**Bias** | **0.4720 s**<br>**1.2574 s**<br>**-0.0000 s** | 0.4239 s<br>1.3070 s<br>-0.2002 s | 0.5961 s<br>1.5307 s<br>-0.1328 s | **3.8% lower RMSE** than Persistence; perfectly zero mean bias. |
| **+3 Laps** | **MAE**<br>**RMSE**<br>**Bias** | **0.6274 s**<br>**1.3092 s**<br>**+0.1119 s** | 0.5630 s<br>1.3813 s<br>-0.3389 s | 1.1420 s<br>2.3035 s<br>-0.1459 s | **5.2% lower RMSE**. Trend model baseline error diverges past 1.14s. |
| **+5 Laps** | **MAE**<br>**RMSE**<br>**Bias** | **0.6628 s**<br>**1.3659 s**<br>**+0.0370 s** | 0.6598 s<br>1.4698 s<br>-0.4579 s | 1.6470 s<br>3.1886 s<br>-0.1571 s | **7.1% lower RMSE**. Persistence underestimates thermal degradation by -0.46s. |
| **+10 Laps** | **MAE**<br>**RMSE**<br>**Bias** | **0.8657 s**<br>**1.5277 s**<br>**+0.2131 s** | 0.8825 s<br>1.6906 s<br>-0.7186 s | 2.8750 s<br>5.2299 s<br>-0.1469 s | **9.6% lower RMSE** and superior MAE. Persistence misses over 0.71s of wear. |

### 95% Bootstrap Confidence Intervals (1,000 Resamples)
- **+1 Horizon**: MAE = **0.4720 s** — 95% CI: `[0.4559 s, 0.4875 s]` ($N = 21,133$)
- **+3 Horizon**: MAE = **0.6274 s** — 95% CI: `[0.6083 s, 0.6470 s]` ($N = 19,046$)
- **+5 Horizon**: MAE = **0.6628 s** — 95% CI: `[0.6405 s, 0.6853 s]` ($N = 17,016$)
- **+10 Horizon**: MAE = **0.8657 s** — 95% CI: `[0.8351 s, 0.8970 s]` ($N = 12,367$)

---

## 📡 Physical Telemetry & Hardware Integration

TrackShift connects directly to hardware data streams for real-time race diagnostics:

### 1. Supported Adapters
- **`f1_sim_udp`**: Ingests direct UDP telemetry broadcast packets from EA Sports F1 23/F1 24 on port `20777`.
- **`serial`**: Reads ASCII/JSON or binary telemetry strings from Arduino or ESP32 dev boards (e.g. `/dev/ttyUSB0` or `COM3`).
- **`ble`**: Bluetooth Low Energy peripheral adapter for wireless telemetry sensors.
- **`mock`**: Deterministic synthetic replay stream for testing and CI/CD pipelines.

### 2. Physical Sensor Thresholds

| Sensor Metric | Nominal Racing Range | Alert Trigger | Actionable Threat |
| :--- | :---: | :---: | :--- |
| **Tyre Temp (FL/FR/RL/RR)** | $85^\circ\text{C} - 105^\circ\text{C}$ | $< 80^\circ\text{C}$ / $> 115^\circ\text{C}$ | Surface Glaze (Loss of Grip) / Blistering & Delamination |
| **Tyre Pressure** | $1.40 - 2.05\text{ bar}$ (~20–30 psi) | $< 1.30\text{ bar}$ / $> 2.30\text{ bar}$ | Slow Puncture / Overpressure Structural Stress |
| **Wheel Deceleration** | $< 3.5\text{ G}$ | $> 4.5\text{ G}$ | Wheel Lockup / Flat-Spotting Detected |
| **Ingestion Watchdog** | $10 - 20\text{ Hz}$ | Stale $> 2.5\text{s}$ / Offline $> 5.0\text{s}$ | Sensor Drop-off / Device Unserviceable |

---

## 📂 Repository Structure

```text
TrackShift-main/
├── api/                             # FastAPI Serving Architecture
│   ├── main.py                      # Application Entry Point & Unified Routing
│   ├── routers/                     # Endpoint Modules
│   │   ├── tdsm.py                  # TDSM Prediction & Health Endpoints
│   │   ├── physical_telemetry.py    # Hardware Telemetry & Sensor State
│   │   ├── circuits.py              # 24 FIA Track Coordinates & Turn Metadata
│   │   ├── stints.py                # Stint Analysis & Tyre Life
│   │   └── seasons.py               # 2024 & 2025 Calendar Sessions
│   └── services/                    # Business & Analytics Logic
│       ├── physical_telemetry_service.py # Telemetry Streaming & Safety Watchdog
│       ├── hardware_adapters.py     # UDP, Serial, BLE & Mock Hardware Drivers
│       └── driver_advisory_service.py # Deterministic Strategy Recommendations
├── artifacts/                       # Trained Weights, Audit Records & Metrics
│   ├── audit/                       # Cryptographic Integrity Logs & Coverage Reports
│   ├── tdsm/                        # Frozen Production Model Weights & Scaler
│   └── validation_2025/             # 2025 Held-Out Verification Plots & Metrics
├── configs/                         # Central Feature Configurations
├── frontend/                        # Interactive React 18 + Vite User Interface
│   ├── src/
│   │   ├── components/              # Circuit Map, TDSM Forecast, Hardware Panel, etc.
│   │   ├── context/                 # Telemetry & UI State Management
│   │   └── App.jsx                  # Main Dashboard Layout
│   └── package.json                 # Frontend Dependencies & Scripts
├── scripts/                         # Operational & Maintenance Tools
│   ├── run_api.py                   # Zero-Conflict FastAPI Launcher (Auto Port Release)
│   ├── train.py                     # Canonical TDSM 2024 Model Trainer
│   ├── validate_2025.py             # Causal 2025 Walk-Forward Replay
│   ├── audit.py                     # Cryptographic & Chronological Leakage Audit
│   ├── benchmark.py                 # Latency & Throughput Verification
│   └── create_zip_archive.py        # Clean Distribution Packaging Utility
├── tests/                           # 217 Automated Tests (100% Pass Rate)
├── trackshift/                      # Canonical Core Library
│   ├── domain_constants.py          # Universal Physical & Strategy Constants
│   ├── tdsm/                        # TDSM Model Architecture, Dataset & Inference
│   └── strategy/                    # Decision Engine, Stint Simulator & Config
├── pytest.ini                       # Test Suite Configuration
├── requirements.txt                 # Backend Python Dependencies
└── package.json                     # Root Project Workspace Scripts
```

---

## ⚡ Quickstart Guide

### Prerequisites
- **Python 3.10+** (Tested on Python 3.12)
- **Node.js 18+** & **npm**
- Modern Web Browser (Chrome, Firefox, Edge)

### 1. Clone & Set Up Backend

```bash
# Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Launching TrackShift

TrackShift includes dedicated zero-conflict launchers:

#### Start Backend API (FastAPI on Port 8000)
```bash
npm run api
# Or directly:
python scripts/run_api.py --reload
```
*Note: The launcher automatically frees port 8000 if an orphaned process is holding it, preventing `WinError 10013` conflicts.*

#### Start Frontend Dashboard (Vite on Port 5173)
In a second terminal:
```bash
npm run dev
```

Open **`http://localhost:5173`** in your browser to view the live dashboard!

---

## 🧪 Verification & Tests

TrackShift enforces strict automated regression and scientific integrity verification across all subsystems:

```bash
# Run the complete test suite
pytest tests/
```

### Coverage Highlights (217 Tests Passing):
- **All 24 Circuits**: Verified coordinate continuity, closed loops, turn metadata, and bounding boxes.
- **TDSM Forecast**: Verified input tensor scaling, multi-horizon shapes, temporal masks, and zero future leakage.
- **Physical Telemetry**: Sensor parsing, rate limiting ($50\text{ Hz}$), lockup triggers, and safety warning logic.
- **Clean Architecture**: Single-source-of-truth constants verification and strict domain boundary checks.

---

## 🔌 API Endpoints Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/tdsm/health` | `GET` | TDSM operational status, loaded weights, scaler state & active mode |
| `/api/tdsm/predict` | `POST` | Multi-horizon tyre degradation forecast for given stint state |
| `/api/telemetry/physical/state` | `GET` | Current hardware sensor readings (temperatures, pressures, alarms) |
| `/api/telemetry/physical/configure` | `POST` | Switch hardware source (`f1_sim_udp`, `serial`, `ble`, `mock`) |
| `/api/circuits` | `GET` | Comprehensive catalogue of all 24 Formula 1 circuits |
| `/api/circuits/{id}/map` | `GET` | High-fidelity GPS track vectors, corner metrics, and DRS zones |
| `/api/stints/{year}/{round}` | `GET` | Full tyre stint history and compound sequence for session |
| `/api/strategy/advisory` | `POST` | Deterministic pit window & pace guidance recommendation |

---

## 🛡️ Scientific Integrity & Constraints

1. **Strict Temporal Isolation**: Scalers, feature encoders, and weights are fitted solely on 2024 race telemetry. 2025 data serves exclusively as unseen, out-of-distribution evaluation data.
2. **Zero Synthetic Imputation**: Stint termination horizons ($t + h \ge \text{stint length}$) are strictly marked with `mask = 0.0` and excluded from loss and metric computation.
3. **Deterministic Governance**: All tactical strategy recommendations follow deterministic, physical rules with explicit threshold bounds—preventing dangerous black-box hallucinations on the pit wall.

---

## 👥 Authors & Core Contributors

**TrackShift** is an **original ("OG") project**. The entire platform, hardware telemetry ingestion engine, and proprietary **TDSM neural forecasting architecture** were conceived, mathematically formulated, trained, and empirically tested in-house by:
- **Harshit Ranbhare**
- **Ajinkya Supate**
- **Harshal Upadhye**

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
