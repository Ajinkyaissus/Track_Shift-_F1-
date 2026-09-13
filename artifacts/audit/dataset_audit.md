# Dataset Forensic Audit Report

- **Source File**: `data/combined_2024_2025_laps.parquet`
- **SHA-256 Hash**: `46a41f7fa4e58c7a2cdb845685b2ee390c6fd1a8d1391b6a4ff8e2fcc4654b85`
- **Total Rows**: 44,738
- **True Data Grain**: `Event(Round) + Season + Driver + Stint + LapNumber`
- **Duplicate Grain Keys**: 2024 = 0, 2025 = 0

## 2024 vs 2025 Comparative Summary

| Metric | 2024 Training / Val | 2025 Held-Out Test |
| :--- | :--- | :--- |
| **Row Count** | 22,541 | 22,197 |
| **Events (Rounds)** | 23 | 24 |
| **Drivers** | 24 | 21 |
| **Stints** | 1087 | 1064 |
| **LapNumber Range** | 2.0 - 78.0 | 2.0 - 78.0 |
| **D Mean ± Std (s)** | 1.237 ± 1.822 | 1.132 ± 1.711 |
| **Delta_D Mean (s)** | 0.2081 | 0.1935 |
| **Delta2_D Mean (s)** | 0.1160 | 0.1139 |
| **TyreLife Mean (laps)** | 15.6 | 15.7 |
| **FuelProxy Mean (kg)** | 56.1 | 55.2 |

## Compound Distribution

### 2024
- **HARD**: 12,865 laps (57.1%)
- **MEDIUM**: 8,016 laps (35.6%)
- **SOFT**: 1,660 laps (7.4%)

### 2025
- **HARD**: 9,872 laps (44.5%)
- **MEDIUM**: 9,486 laps (42.7%)
- **SOFT**: 2,839 laps (12.8%)
