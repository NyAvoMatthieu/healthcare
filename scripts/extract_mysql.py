"""
Incremental extraction from MySQL operational database into SQLite staging.
"""
import datetime
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_utils import get_staging_engine, get_mysql_engine, init_staging, log_etl, load_config

DAG_NAME = "ingestion_mysql"


def _last_load_date(staging_engine, table: str) -> str:
    """Return the most recent loaded_at date for a staging table."""
    cfg = load_config()
    lookback_h = cfg["etl"].get("incremental_lookback_hours", 24)
    with staging_engine.connect() as conn:
        row = conn.execute(text(f"SELECT MAX(loaded_at) FROM {table}")).fetchone()
    if row and row[0]:
        return row[0]
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=lookback_h)).isoformat()


def extract_mysql_patients(mysql_engine, staging_engine) -> int:
    last = _last_load_date(staging_engine, "stg_mysql_patients")
    df   = pd.read_sql(
        text("SELECT id, nom, prenom, date_naissance, sexe, region, updated_at FROM patients WHERE updated_at > :last"),
        mysql_engine, params={"last": last}
    )
    if df.empty:
        return 0
    df["source"]    = "mysql"
    df["loaded_at"] = datetime.datetime.utcnow().isoformat()
    df.to_sql("stg_mysql_patients", staging_engine, if_exists="append", index=False)
    return len(df)


def extract_mysql_admissions(mysql_engine, staging_engine) -> int:
    last = _last_load_date(staging_engine, "stg_mysql_admissions")
    df   = pd.read_sql(
        text("""SELECT id, patient_id, date_admission, date_sortie,
                       service, est_urgence, diagnostic, updated_at
                FROM admissions WHERE updated_at > :last"""),
        mysql_engine, params={"last": last}
    )
    if df.empty:
        return 0
    df["source"]    = "mysql"
    df["loaded_at"] = datetime.datetime.utcnow().isoformat()
    df.to_sql("stg_mysql_admissions", staging_engine, if_exists="append", index=False)
    return len(df)


def check_mysql_connection(mysql_engine) -> bool:
    try:
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"  MySQL non disponible: {e}")
        return False


def run_all():
    init_staging()
    staging_engine = get_staging_engine()
    try:
        mysql_engine = get_mysql_engine()
        if not check_mysql_connection(mysql_engine):
            log_etl(staging_engine, DAG_NAME, "check_mysql_connection", "FAILED",
                    error="Connexion MySQL impossible")
            return 0
    except Exception as e:
        print(f"  ✗ Configuration MySQL invalide: {e}")
        return 0

    total = 0
    steps = [
        ("patients",   extract_mysql_patients),
        ("admissions", extract_mysql_admissions),
    ]
    for name, fn in steps:
        try:
            n = fn(mysql_engine, staging_engine)
            log_etl(staging_engine, DAG_NAME, f"extract_{name}", "SUCCESS", n, source="mysql")
            print(f"  ✓ mysql.{name}: {n} nouvelles lignes")
            total += n
        except Exception as e:
            log_etl(staging_engine, DAG_NAME, f"extract_{name}", "FAILED",
                    error=str(e), source="mysql")
            print(f"  ✗ mysql.{name}: {e}")
    return total


if __name__ == "__main__":
    print("Extraction MySQL → Staging (incrémentale)...")
    total = run_all()
    print(f"\n✓ Total: {total} lignes chargées depuis MySQL")
