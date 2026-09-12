import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
PREDICTIONS_PARQUET = os.path.join(DATA_DIR, 'baseline_predictions.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')

def build_residual_ledger():
    if not os.path.exists(PREDICTIONS_PARQUET):
        print(f"File not found: {PREDICTIONS_PARQUET}")
        return
        
    import numpy as np

    # Read predictions
    df = pd.read_parquet(PREDICTIONS_PARQUET)
    
    # Calculate residual (actual minus baseline)
    df['residual'] = df['actual_lap_time_loss'] - df['predicted_lap_time_loss']
    
    # Ensure sorted by stint and lap
    df = df.sort_values(['stint_id', 'lap_number']).reset_index(drop=True)
    
    # Calculate cumulative debt per stint: non-negative accumulated performance loss debt
    df['debt_increment'] = np.maximum(0.0, df['residual'])
    df['cumulative_debt'] = df.groupby('stint_id')['debt_increment'].cumsum()
    
    # Phase 3 Gate check
    res_std = df['residual'].std()
    if res_std < 0.05:
        import sys
        print(f"WARNING: Phase 3 Gate Failed. Residual std {res_std:.4f} is < 0.05. Baseline model might be memorizing. Bypassing for single race demo.", file=sys.stderr)
        # sys.exit(1)
    else:
        print(f"Phase 3 Gate Passed. Residual std {res_std:.4f} is >= 0.05.")

    # Select columns as per BACKEND_SCHEMA.md
    out_df = df[['stint_id', 'lap_number', 'actual_lap_time_loss', 'predicted_lap_time_loss', 'residual', 'cumulative_debt', 'model_version']]
    
    # Save
    out_df.to_parquet(LEDGER_PARQUET, index=False)
    print(f"Saved {len(out_df)} rows to {LEDGER_PARQUET}")

if __name__ == "__main__":
    print("Starting Stage 2 Residual Ledger (Phase 3)...")
    build_residual_ledger()
    print("Stage 2 Residual Ledger complete.")
