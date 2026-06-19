"""
Extrait personnel_medical.xlsx (3 feuilles) → staging SQLite.
"""
import sys, types, datetime
from pathlib import Path

if "lxml.etree" not in sys.modules:
    _m = types.ModuleType("lxml.etree")
    _m.LXML_VERSION = (0, 0, 0, 0)
    sys.modules.setdefault("lxml", types.ModuleType("lxml"))
    sys.modules["lxml.etree"] = _m

import pandas as pd
from sqlalchemy import text

from db_utils import get_staging_engine, log_etl

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DAG_NAME = "ingestion_multi_format"
FILE     = DATA_DIR / "personnel_medical.xlsx"


def extract_medecins(engine) -> int:
    df = pd.read_excel(FILE, sheet_name="Medecins", dtype=str)
    df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
    df["source_file"] = "personnel_medical.xlsx|Medecins"
    df["loaded_at"]   = datetime.datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_personnel WHERE type_personnel='Médecin'"))
        conn.commit()
    df["type_personnel"] = "Médecin"
    df.to_sql("stg_personnel", engine, if_exists="append", index=False)
    return len(df)


def extract_infirmiers(engine) -> int:
    df = pd.read_excel(FILE, sheet_name="Infirmiers", dtype=str)
    df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
    df["source_file"] = "personnel_medical.xlsx|Infirmiers"
    df["loaded_at"]   = datetime.datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_personnel WHERE type_personnel='Infirmier'"))
        conn.commit()
    df["type_personnel"] = "Infirmier"
    df.to_sql("stg_personnel", engine, if_exists="append", index=False)
    return len(df)


def extract_plannings(engine) -> int:
    df = pd.read_excel(FILE, sheet_name="Plannings", dtype=str)
    df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
    df["source_file"] = "personnel_medical.xlsx|Plannings"
    df["loaded_at"]   = datetime.datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_plannings"))
        conn.commit()
    df.to_sql("stg_plannings", engine, if_exists="append", index=False)
    return len(df)


def run_all(engine=None):
    engine = engine or get_staging_engine()
    if not FILE.exists():
        raise FileNotFoundError(f"{FILE} introuvable — lancez generate_excel.py d'abord")
    total = 0
    for name, fn in [("médecins", extract_medecins),
                     ("infirmiers", extract_infirmiers),
                     ("plannings", extract_plannings)]:
        try:
            n = fn(engine)
            log_etl(engine, DAG_NAME, f"extract_excel_{name}", "SUCCESS", n, source="excel")
            print(f"  ✓ Excel.{name}: {n} lignes")
            total += n
        except Exception as e:
            log_etl(engine, DAG_NAME, f"extract_excel_{name}", "FAILED", error=str(e))
            print(f"  ✗ Excel.{name}: {e}")
    return total


if __name__ == "__main__":
    print("Extraction Excel → Staging...")
    total = run_all()
    print(f"\n✓ Total: {total} lignes chargées depuis Excel")
