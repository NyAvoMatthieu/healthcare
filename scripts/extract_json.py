"""
Extrait capteurs_lits.json et stock_pharmacie.json → staging SQLite.
"""
import datetime
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_utils import get_staging_engine, log_etl

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DAG_NAME = "ingestion_multi_format"


def extract_capteurs_lits(engine) -> int:
    path = DATA_DIR / "capteurs_lits.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable — lancez generate_json.py d'abord")

    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    df = pd.DataFrame(records)
    df["source_file"] = "capteurs_lits.json"
    df["loaded_at"]   = datetime.datetime.utcnow().isoformat()
    # Convertir booléen → int pour SQLite
    if "alertes" in df.columns:
        df["alertes"] = df["alertes"].astype(int)
    if "sous_seuil_alerte" in df.columns:
        df["sous_seuil_alerte"] = df["sous_seuil_alerte"].astype(int)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_capteurs_lits"))
        conn.commit()
    df.to_sql("stg_capteurs_lits", engine, if_exists="append", index=False,
              chunksize=1000)
    return len(df)


def extract_stock_pharmacie(engine) -> int:
    path = DATA_DIR / "stock_pharmacie.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable — lancez generate_json.py d'abord")

    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    df = pd.DataFrame(records)
    df["source_file"] = "stock_pharmacie.json"
    df["loaded_at"]   = datetime.datetime.utcnow().isoformat()
    if "sous_seuil_alerte" in df.columns:
        df["sous_seuil_alerte"] = df["sous_seuil_alerte"].astype(int)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_stock_pharmacie"))
        conn.commit()
    df.to_sql("stg_stock_pharmacie", engine, if_exists="append", index=False,
              chunksize=1000)
    return len(df)


def run_all(engine=None):
    engine = engine or get_staging_engine()
    total  = 0
    for name, fn in [("capteurs_lits",   extract_capteurs_lits),
                     ("stock_pharmacie", extract_stock_pharmacie)]:
        try:
            n = fn(engine)
            log_etl(engine, DAG_NAME, f"extract_json_{name}", "SUCCESS", n, source="json")
            print(f"  ✓ JSON.{name}: {n:,} lignes")
            total += n
        except Exception as e:
            log_etl(engine, DAG_NAME, f"extract_json_{name}", "FAILED", error=str(e))
            print(f"  ✗ JSON.{name}: {e}")
    return total


if __name__ == "__main__":
    print("Extraction JSON → Staging...")
    total = run_all()
    print(f"\n✓ Total: {total:,} lignes chargées depuis JSON")
