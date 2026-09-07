"""
Cache key formatting utilities for versioned KV caching across circuits,
stints, telemetry embeddings, attributions, ledgers, and counterfactuals.
"""

DATA_VERSION = "2024-fastf1-v1"
LEDGER_VERSION = "v3_stage2"
MAP_VERSION = "v1_geo"
TELEMETRY_VERSION = "v1_seq"
FEATURE_SCHEMA_VERSION = "v1_behavioral_5feat"

class CacheKeys:
    """
    Structured, versioned cache key definitions.
    Prevents cache collisions and ensures clean invalidation across model/data versions.
    """
    
    @staticmethod
    def circuit_map(circuit_id: str, data_version: str = DATA_VERSION, map_version: str = MAP_VERSION) -> str:
        return f"circuit:{circuit_id}:map:{data_version}:{map_version}"

    @staticmethod
    def circuit_detail(circuit_id: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:detail:{data_version}"

    @staticmethod
    def circuit_sessions(circuit_id: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:sessions:{data_version}"

    @staticmethod
    def circuit_stints(circuit_id: str, driver_id: str | None = None, compound: str | None = None, data_version: str = DATA_VERSION) -> str:
        driver_tag = driver_id or "all"
        compound_tag = compound.upper() if compound else "all"
        return f"circuit:{circuit_id}:stints:{driver_tag}:{compound_tag}:{data_version}"

    @staticmethod
    def stint_ledger(stint_id: str, ledger_version: str = LEDGER_VERSION) -> str:
        return f"stint:{stint_id}:ledger:{ledger_version}"

    @staticmethod
    def stint_attribution(stint_id: str, model_version: str) -> str:
        return f"stint:{stint_id}:attribution:{model_version}"

    @staticmethod
    def stint_counterfactual(stint_id: str, model_version: str, feature: str, delta_pct: float) -> str:
        delta_str = f"{delta_pct:+.2f}"
        return f"stint:{stint_id}:counterfactual:{model_version}:{feature}:{delta_str}"

    @staticmethod
    def stint_signature(stint_id: str, model_version: str) -> str:
        return f"stint:{stint_id}:signature:{model_version}"

    @staticmethod
    def stint_signature_transfer(stint_id: str, model_version: str, target_driver: str) -> str:
        return f"stint:{stint_id}:signature_transfer:{model_version}:{target_driver}"

    @staticmethod
    def stints_compare(stint_a: str, stint_b: str, model_version: str) -> str:
        return f"stints:compare:{model_version}:{stint_a}:{stint_b}"

    @staticmethod
    def behavioral_embedding(model_version: str, stint_id: str, telemetry_version: str = TELEMETRY_VERSION) -> str:
        return f"embedding:{model_version}:{stint_id}:{telemetry_version}"

    @staticmethod
    def circuits_list(data_version: str = DATA_VERSION) -> str:
        return f"circuits:list:{data_version}"

    @staticmethod
    def races_list(data_version: str = DATA_VERSION) -> str:
        return f"races:list:{data_version}"

    @staticmethod
    def stints_list(race_id: str | None = None, data_version: str = DATA_VERSION) -> str:
        race_tag = race_id or "all"
        return f"stints:list:{race_tag}:{data_version}"

    @staticmethod
    def session_telemetry(circuit_id: str, session_id: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:telemetry:{data_version}"

    @staticmethod
    def session_drivers(circuit_id: str, session_id: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:drivers:{data_version}"

    @staticmethod
    def session_leaderboard(circuit_id: str, session_id: str, lap: int | str = "all", data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:leaderboard:{lap}:{data_version}"

    @staticmethod
    def signatures_list(model_version: str) -> str:
        return f"signatures:list:{model_version}"

    @staticmethod
    def session_drivers_analytics(circuit_id: str, session_id: str, model_version: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:drivers_analytics:{model_version}:{data_version}"

    @staticmethod
    def driver_analytics(circuit_id: str, session_id: str, driver_id: str, model_version: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:driver:{driver_id}:analytics:{model_version}:{data_version}"

    @staticmethod
    def driver_laps(circuit_id: str, session_id: str, driver_id: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:driver:{driver_id}:laps:{data_version}"

    @staticmethod
    def driver_stints(circuit_id: str, session_id: str, driver_id: str, data_version: str = DATA_VERSION) -> str:
        return f"circuit:{circuit_id}:session:{session_id}:driver:{driver_id}:stints:{data_version}"
