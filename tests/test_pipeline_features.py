import pandas as pd
import numpy as np
from pipeline.features import (
    compute_braking_aggression,
    compute_throttle_transient_smoothness,
    compute_lateral_dynamics_proxy,
    compute_kerb_usage,
    compute_lockup_flag_rate,
    estimate_fuel_load
)

def test_feature_computations_valid():
    n_points = 500
    time_series = np.linspace(0, 90, n_points)
    speed_series = 200 + 50 * np.sin(np.linspace(0, 4 * np.pi, n_points))
    throttle_series = np.clip(80 + 20 * np.sin(np.linspace(0, 4 * np.pi, n_points)), 0, 100)
    brake_series = (np.sin(np.linspace(0, 4 * np.pi, n_points)) < -0.2)
    x_series = 500 * np.cos(np.linspace(0, 2 * np.pi, n_points))
    y_series = 500 * np.sin(np.linspace(0, 2 * np.pi, n_points))
    rpm_series = 8000 + 2000 * np.sin(np.linspace(0, 4 * np.pi, n_points))
    
    tel = pd.DataFrame({
        'Time': pd.to_timedelta(time_series, unit='s'),
        'Speed': speed_series,
        'Throttle': throttle_series,
        'Brake': brake_series,
        'X': x_series,
        'Y': y_series,
        'RPM': rpm_series,
        'Distance': np.linspace(0, 5000, n_points)
    })
    
    braking = compute_braking_aggression(tel)
    assert isinstance(braking, float)
    assert not np.isnan(braking)
    
    throttle = compute_throttle_transient_smoothness(tel)
    assert isinstance(throttle, float)
    assert not np.isnan(throttle)
    
    lat = compute_lateral_dynamics_proxy(tel)
    assert isinstance(lat, float)
    assert not np.isnan(lat)
    
    kerb = compute_kerb_usage(tel)
    assert isinstance(kerb, float)
    assert not np.isnan(kerb)
    
    lockup = compute_lockup_flag_rate(tel)
    assert isinstance(lockup, float)
    assert not np.isnan(lockup)

def test_features_missing_channels_resilience():
    n_points = 100
    tel = pd.DataFrame({
        'Time': pd.to_timedelta(np.linspace(0, 90, n_points), unit='s'),
        'Speed': np.full(n_points, 200.0),
        'Throttle': np.full(n_points, 100.0)
    })
    
    assert compute_braking_aggression(tel) == 0.0 or np.isnan(compute_braking_aggression(tel))
    assert compute_lateral_dynamics_proxy(tel) == 0.0 or np.isnan(compute_lateral_dynamics_proxy(tel))
    assert compute_kerb_usage(tel) == 0.0
    assert compute_lockup_flag_rate(tel) == 0.0

def test_estimate_fuel_load():
    fuel_l1 = estimate_fuel_load(lap_number=1, start_lap=1, session_type='R')
    fuel_l20 = estimate_fuel_load(lap_number=20, start_lap=1, session_type='R')
    assert fuel_l1 > fuel_l20
    assert fuel_l1 == 108.5
    assert fuel_l20 == 80.0
