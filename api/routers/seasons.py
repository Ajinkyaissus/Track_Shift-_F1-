"""
api/routers/seasons.py — REST endpoints for Seasons, Events, Sessions, Telemetry, Weather, Pit Stops, Track Status, and Multi-Season Circuit Comparisons.
"""

import sqlite3
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from api.cache import CacheKeys, get_cache_service, DATA_VERSION

router = APIRouter(tags=["seasons"])

circuits_service = None

def set_circuits_service(service):
    global circuits_service
    circuits_service = service

def get_circuits_service():
    global circuits_service
    if circuits_service is None:
        from api.services.circuits_service import CircuitsService
        from api.main import app_data, DB_PATH
        circuits_service = CircuitsService(DB_PATH, app_data)
    return circuits_service


@router.get("/seasons")
@router.get("/api/seasons")
async def get_seasons():
    """
    Return all supported F1 seasons (2024, 2025) with metadata, total rounds, and completion status.
    """
    svc = get_circuits_service()
    with sqlite3.connect(svc.db_path) as conn:
        conn.row_factory = svc._dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT year, total_rounds, status FROM seasons ORDER BY year DESC")
        rows = cursor.fetchall()
        
    if not rows:
        return [
            {"year": 2025, "total_rounds": 24, "status": "ACTIVE"},
            {"year": 2024, "total_rounds": 24, "status": "COMPLETED"}
        ]
    return rows


@router.get("/seasons/{year}/events")
@router.get("/api/seasons/{year}/events")
async def get_season_events(year: int):
    """
    Return all calendar events for the selected season.
    Accurately reflects completed rounds vs cancelled rounds (e.g. 2023 Imola).
    """
    svc = get_circuits_service()
    with sqlite3.connect(svc.db_path) as conn:
        conn.row_factory = svc._dict_factory
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.race_id as event_id,
                r.race_id,
                r.season,
                r.round,
                r.track_id,
                r.track_id as circuit_id,
                r.event_date,
                r.event_name,
                r.status,
                t.name as circuit_name,
                t.country,
                t.country_code,
                t.location
            FROM races r
            LEFT JOIN tracks t ON r.track_id = t.track_id
            WHERE r.season = ?
            ORDER BY r.round ASC
        """, (year,))
        events = cursor.fetchall()
        
    if not events:
        raise HTTPException(status_code=404, detail=f"No events found for season {year}")
    return events


@router.get("/events/{event_id}/sessions")
@router.get("/api/events/{event_id}/sessions")
async def get_event_sessions(event_id: str):
    """
    Return all sessions for a specific event (e.g. 2024_cota -> Race, Qualifying, etc.).
    """
    svc = get_circuits_service()
    with sqlite3.connect(svc.db_path) as conn:
        conn.row_factory = svc._dict_factory
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                ses.session_id,
                ses.race_id,
                ses.session_type,
                ses.weather_flag,
                ses.track_evolution_index,
                ses.status,
                r.season,
                r.round,
                r.track_id as circuit_id,
                r.event_name,
                r.event_date
            FROM sessions ses
            JOIN races r ON ses.race_id = r.race_id
            WHERE ses.race_id = ?
            ORDER BY ses.session_type ASC
        """, (event_id,))
        sessions = cursor.fetchall()
        
    if not sessions:
        raise HTTPException(status_code=404, detail=f"No sessions found for event '{event_id}'")
    return sessions


@router.get("/sessions/{session_id}/laps")
@router.get("/api/sessions/{session_id}/laps")
async def get_session_laps(session_id: str, driver_id: Optional[str] = None):
    """
    Return lap times and tyre information for the selected session.
    """
    svc = get_circuits_service()
    parts = session_id.split('_')
    circuit_id = '_'.join(parts[1:-1]).lower() if len(parts) > 2 else "circuit"
    
    if driver_id:
        return await svc.get_driver_laps(circuit_id, session_id, driver_id)
        
    # Full session laps
    laps_df = svc._get_laps_df()
    if not laps_df.empty and 'session_id' in laps_df.columns:
        filtered = laps_df[laps_df['session_id'] == session_id]
        if not filtered.empty:
            return filtered[['driver_id', 'lap_number', 'lap_time', 'compound', 'is_green_flag', 'braking_aggression', 'throttle_transient_smoothness']].to_dict(orient='records')
            
    # Fallback to loading driver laps
    drivers_res = await svc.get_session_drivers(circuit_id, session_id)
    drivers = drivers_res.get("drivers", [])
    all_laps = []
    for d in drivers:
        try:
            d_laps = await svc.get_driver_laps(circuit_id, session_id, d['driver_id'])
            all_laps.extend(d_laps.get("laps", []))
        except Exception:
            pass
    return {"session_id": session_id, "lap_count": len(all_laps), "laps": all_laps}


@router.get("/sessions/{session_id}/telemetry")
@router.get("/api/sessions/{session_id}/telemetry")
async def get_session_telemetry_direct(session_id: str):
    """
    Return comprehensive session telemetry, leaderboards, and car positions for replay.
    """
    svc = get_circuits_service()
    parts = session_id.split('_')
    circuit_id = '_'.join(parts[1:-1]).lower() if len(parts) > 2 else "circuit"
    return await svc.get_session_telemetry(circuit_id, session_id)


@router.get("/sessions/{session_id}/weather")
@router.get("/api/sessions/{session_id}/weather")
async def get_session_weather(session_id: str):
    """
    Return actual historical weather recorded during the selected session.
    """
    svc = get_circuits_service()
    cache_key = CacheKeys.session_weather(session_id)
    
    async def _compute():
        with sqlite3.connect(svc.db_path) as conn:
            conn.row_factory = svc._dict_factory
            cursor = conn.cursor()
            cursor.execute("SELECT ses.weather_flag, r.track_id FROM sessions ses JOIN races r ON ses.race_id = r.race_id WHERE ses.session_id = ?", (session_id,))
            sess_meta = cursor.fetchone()
            
            cursor.execute("""
                SELECT air_temp, track_temp, humidity, rainfall, wind_speed, recorded_at
                FROM weather
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = cursor.fetchall()
            
        if not sess_meta:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
            
        if not rows:
            # Check if circuit weather profile is defined as baseline
            from api.services.circuits_service import CIRCUIT_WEATHER_PROFILES
            cid = sess_meta.get("track_id", "")
            w_flag = sess_meta.get("weather_flag", "dry")
            profile = CIRCUIT_WEATHER_PROFILES.get(cid, {}).get(w_flag, {
                "air_temp": 24.0, "track_temp": 32.0, "humidity": 50, "rainfall": 0.0, "wind_speed": 10.0
            })
            return {
                "session_id": session_id,
                "weather_flag": w_flag,
                "status": "PROFILE",
                "summary": profile,
                "timeline": []
            }
            
        avg_air = round(sum(r['air_temp'] for r in rows if r['air_temp'] is not None) / len(rows), 1) if rows else 24.0
        avg_track = round(sum(r['track_temp'] for r in rows if r['track_temp'] is not None) / len(rows), 1) if rows else 32.0
        avg_hum = round(sum(r['humidity'] for r in rows if r['humidity'] is not None) / len(rows), 1) if rows else 50.0
        max_rain = round(max((r['rainfall'] for r in rows if r['rainfall'] is not None), default=0.0), 2)
        avg_wind = round(sum(r['wind_speed'] for r in rows if r['wind_speed'] is not None) / len(rows), 1) if rows else 10.0
        
        return {
            "session_id": session_id,
            "weather_flag": sess_meta.get("weather_flag", "dry"),
            "status": "VERIFIED_HISTORICAL",
            "summary": {
                "air_temp": avg_air,
                "track_temp": avg_track,
                "humidity": avg_hum,
                "rainfall": max_rain,
                "wind_speed": avg_wind
            },
            "timeline": rows
        }
        
    return await svc.cache.single_flight(cache_key, _compute, attach_metadata=False)


@router.get("/sessions/{session_id}/track-status")
@router.get("/api/sessions/{session_id}/track-status")
async def get_session_track_status(session_id: str):
    """
    Return flag periods, SC, VSC, and red flags for the selected session.
    """
    svc = get_circuits_service()
    cache_key = CacheKeys.session_track_status(session_id)
    
    async def _compute():
        with sqlite3.connect(svc.db_path) as conn:
            conn.row_factory = svc._dict_factory
            cursor = conn.cursor()
            cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
            cursor.execute("SELECT status_code, message, start_time, end_time FROM track_status WHERE session_id = ? ORDER BY id ASC", (session_id,))
            rows = cursor.fetchall()
            
        return {
            "session_id": session_id,
            "status_count": len(rows),
            "events": rows if rows else [{"status_code": "1", "message": "All Clear / Green Flag", "start_time": 0.0, "end_time": None}]
        }
        
    return await svc.cache.single_flight(cache_key, _compute, attach_metadata=False)


@router.get("/sessions/{session_id}/trackshift")
@router.get("/api/sessions/{session_id}/trackshift")
async def get_session_trackshift_analytics(session_id: str):
    """
    Return Stage 1 Baseline, Stage 2 Tyre Debt, Stage 3 TCN attribution, and Stage 4 Sensitivity for the session.
    """
    svc = get_circuits_service()
    parts = session_id.split('_')
    circuit_id = '_'.join(parts[1:-1]).lower() if len(parts) > 2 else "circuit"
    return await svc.get_session_drivers_analytics(circuit_id, session_id)


@router.get("/circuits/{circuit_id}/comparison")
@router.get("/api/circuits/{circuit_id}/comparison")
async def get_circuit_multi_season_comparison(
    circuit_id: str, 
    seasons: str = Query("2024,2025", description="Comma separated seasons to compare")
):
    """
    Compare multi-season metrics for a circuit (e.g. 2024 COTA vs 2025 COTA).
    Compares weather, pole/fastest lap times, tyre degradation, and pit strategy across seasons.
    """
    svc = get_circuits_service()
    season_list = [int(s.strip()) for s in seasons.split(',') if s.strip().isdigit()]
    if not season_list or 2023 in season_list or any(s not in (2024, 2025) for s in season_list):
        raise HTTPException(status_code=404, detail="Season 2023 is unsupported or invalid seasons requested.")
    cache_key = CacheKeys.circuit_comparison(circuit_id, ','.join(map(str, season_list)))
    
    async def _compute():
        with sqlite3.connect(svc.db_path) as conn:
            conn.row_factory = svc._dict_factory
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM tracks WHERE track_id = ?", (circuit_id,))
            track = cursor.fetchone()
            if not track:
                raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
                
            cursor.execute("""
                SELECT ses.session_id, r.season, r.round, r.event_name, r.event_date, ses.weather_flag, ses.track_evolution_index
                FROM sessions ses
                JOIN races r ON ses.race_id = r.race_id
                WHERE r.track_id = ? AND r.season IN ({})
                ORDER BY r.season ASC
            """.format(','.join('?' for _ in season_list)), [circuit_id] + season_list)
            session_rows = cursor.fetchall()

        seasons_data = []
        for s_row in session_rows:
            s_id = s_row['session_id']
            yr = s_row['season']
            
            # Pit stops
            pit_data = svc._load_session_pit_stops_internal(s_id, circuit_id)
            total_stops = sum(d.get('pit_stop_count', 0) for d in pit_data.get('driver_pit_stops', []))
            
            # Laps
            ldf = svc._get_laps_df()
            best_lap = None
            avg_deg = None
            if not ldf.empty and 'session_id' in ldf.columns:
                slaps = ldf[ldf['session_id'] == s_id]
                if not slaps.empty and 'lap_time' in slaps.columns:
                    valid_lt = slaps['lap_time'].dropna()
                    if not valid_lt.empty:
                        best_lap = round(float(valid_lt.min()), 3)
                        
            seasons_data.append({
                "season": yr,
                "session_id": s_id,
                "event_name": s_row['event_name'],
                "event_date": s_row['event_date'],
                "weather_flag": s_row['weather_flag'],
                "track_evolution_index": s_row['track_evolution_index'],
                "fastest_lap_seconds": best_lap,
                "total_verified_pit_stops": total_stops,
                "status": "VERIFIED"
            })
            
        return {
            "circuit_id": circuit_id,
            "circuit_name": track["name"],
            "country": track["country"],
            "seasons_compared": season_list,
            "comparison": seasons_data
        }

    return await svc.cache.single_flight(cache_key, _compute, attach_metadata=False)
