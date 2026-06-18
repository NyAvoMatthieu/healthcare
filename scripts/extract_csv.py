"""
Extract CSV source files and load into SQLite staging database.
"""
import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_utils import get_staging_engine, init_staging, log_etl, load_config

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DAG_NAME = "ingestion_csv"


def _load_table(df: pd.DataFrame, table: str, engine, source_file: str) -> int:
    df = df.copy()
    df["source_file"] = source_file
    df["loaded_at"]   = datetime.datetime.utcnow().isoformat()
    df.to_sql(table, engine, if_exists="append", index=False)
    return len(df)


def extract_patients(engine=None) -> int:
    engine = engine or get_staging_engine()
    csv    = DATA_DIR / "patients.csv"
    df     = pd.read_csv(csv, dtype=str)
    # Basic cleanup
    df.columns = [c.strip().lower() for c in df.columns]
    df.dropna(subset=["patient_id"], inplace=True)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_patients WHERE source_file='patients.csv'"))
        conn.commit()
    return _load_table(df, "stg_patients", engine, "patients.csv")


def extract_admissions(engine=None) -> int:
    engine = engine or get_staging_engine()
    csv    = DATA_DIR / "admissions.csv"
    df     = pd.read_csv(csv, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df.dropna(subset=["admission_id", "patient_id"], inplace=True)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_admissions WHERE source_file='admissions.csv'"))
        conn.commit()
    return _load_table(df, "stg_admissions", engine, "admissions.csv")


def extract_sorties(engine=None) -> int:
    engine = engine or get_staging_engine()
    csv    = DATA_DIR / "sorties.csv"
    df     = pd.read_csv(csv, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df.dropna(subset=["sortie_id", "admission_id"], inplace=True)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_sorties WHERE source_file='sorties.csv'"))
        conn.commit()
    return _load_table(df, "stg_sorties", engine, "sorties.csv")


def extract_laboratoires(engine=None) -> int:
    engine = engine or get_staging_engine()
    csv    = DATA_DIR / "laboratoires.csv"
    df     = pd.read_csv(csv, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df.dropna(subset=["labo_id", "patient_id"], inplace=True)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_laboratoires WHERE source_file='laboratoires.csv'"))
        conn.commit()
    return _load_table(df, "stg_laboratoires", engine, "laboratoires.csv")


def extract_medicaments(engine=None) -> int:
    engine = engine or get_staging_engine()
    csv    = DATA_DIR / "medicaments.csv"
    df     = pd.read_csv(csv, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df.dropna(subset=["prescription_id", "patient_id"], inplace=True)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_medicaments WHERE source_file='medicaments.csv'"))
        conn.commit()
    return _load_table(df, "stg_medicaments", engine, "medicaments.csv")


def extract_hopitaux(engine=None) -> int:
    engine = engine or get_staging_engine()
    csv    = DATA_DIR / "hopitaux.csv"
    df     = pd.read_csv(csv, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_hopitaux WHERE source_file='hopitaux.csv'"))
        conn.commit()
    return _load_table(df, "stg_hopitaux", engine, "hopitaux.csv")


def run_all():
    init_staging()
    engine = get_staging_engine()
    total  = 0
    steps  = [
        ("patients",      extract_patients),
        ("admissions",    extract_admissions),
        ("sorties",       extract_sorties),
        ("laboratoires",  extract_laboratoires),
        ("medicaments",   extract_medicaments),
        ("hopitaux",      extract_hopitaux),
    ]
    for name, fn in steps:
        try:
            n = fn(engine)
            log_etl(engine, DAG_NAME, f"extract_{name}", "SUCCESS", n, source=name)
            print(f"  ✓ {name}: {n} lignes chargées")
            total += n
        except Exception as e:
            log_etl(engine, DAG_NAME, f"extract_{name}", "FAILED", error=str(e), source=name)
            print(f"  ✗ {name}: {e}")
    return total


if __name__ == "__main__":
    print("Extraction CSV → Staging...")
    total = run_all()
    print(f"\n✓ Total: {total} lignes chargées dans le staging")
