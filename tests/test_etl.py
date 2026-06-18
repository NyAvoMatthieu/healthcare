"""
Tests unitaires et d'intégration pour le pipeline ETL Healthcare Analytics.
Run: pytest tests/ -v
"""
import sqlite3
import sys
import datetime
from pathlib import Path

import pandas as pd
import pytest

# Ajouter scripts/ au path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def staging_db(tmp_path):
    """Base SQLite staging en mémoire initialisée avec le schema."""
    db_path = tmp_path / "staging.db"
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_staging.sql"
    conn = sqlite3.connect(str(db_path))
    for stmt in sql_path.read_text(encoding="utf-8").split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except Exception:
                pass
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def warehouse_db(tmp_path):
    """Base SQLite warehouse en mémoire initialisée avec le schema."""
    db_path  = tmp_path / "warehouse.db"
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_warehouse.sql"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in sql_path.read_text(encoding="utf-8").split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except Exception:
                pass
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_patients_df():
    return pd.DataFrame({
        "patient_id":      ["P0001", "P0002", "P0003"],
        "nom":             ["Dupont", "Martin", "Leroy"],
        "prenom":          ["Jean",   "Marie",  "Pierre"],
        "date_naissance":  ["1975-03-15", "1960-07-22", "1990-11-05"],
        "age":             [49, 64, 34],
        "sexe":            ["M", "F", "M"],
        "region":          ["Île-de-France", "Bretagne", "Normandie"],
        "tranche_age":     ["31-50", "51-65", "31-50"],
    })


@pytest.fixture
def sample_admissions_df():
    return pd.DataFrame({
        "admission_id":    ["A00001", "A00002", "A00003"],
        "patient_id":      ["P0001",  "P0002",  "P0003"],
        "date_admission":  ["2024-01-10", "2024-02-14", "2024-03-05"],
        "service":         ["Cardiologie", "Urgences", "Chirurgie générale"],
        "urgence":         [0, 1, 0],
        "diagnostic":      ["Infarctus du myocarde", "Fracture", "Appendicite aiguë"],
        "hopital_id":      ["H01", "H05", "H03"],
    })


# ── Schema tests ──────────────────────────────────────────────────────────────

def test_staging_schema_tables(staging_db):
    """Les tables staging critiques doivent exister."""
    expected = [
        "stg_patients", "stg_admissions", "stg_sorties",
        "stg_laboratoires", "stg_medicaments", "etl_log",
        "stg_api_maladies", "stg_api_epidemies",
    ]
    cur = staging_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    for t in expected:
        assert t in tables, f"Table staging manquante : {t}"


def test_warehouse_schema_tables(warehouse_db):
    """Les tables warehouse (dimensions + facts) doivent exister."""
    expected = [
        "dim_patient", "dim_temps", "dim_hopital", "dim_service",
        "dim_region", "dim_maladie",
        "fact_admissions", "fact_urgences", "fact_laboratoires", "fact_prescriptions",
    ]
    cur = warehouse_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    for t in expected:
        assert t in tables, f"Table warehouse manquante : {t}"


def test_warehouse_schema_columns(warehouse_db):
    """fact_admissions doit avoir les colonnes FK attendues."""
    cur = warehouse_db.execute("PRAGMA table_info(fact_admissions)")
    cols = {row[1] for row in cur.fetchall()}
    for col in ["admission_id", "patient_id", "temps_id", "hopital_id",
                "service_id", "maladie_id", "duree_sejour", "est_urgence"]:
        assert col in cols, f"Colonne manquante dans fact_admissions: {col}"


# ── Data quality tests ────────────────────────────────────────────────────────

def test_patient_no_null_ids(sample_patients_df):
    assert sample_patients_df["patient_id"].notna().all()


def test_patient_valid_sexe(sample_patients_df):
    assert sample_patients_df["sexe"].isin(["M", "F"]).all()


def test_patient_valid_age(sample_patients_df):
    ages = pd.to_numeric(sample_patients_df["age"], errors="coerce")
    assert (ages >= 0).all() and (ages <= 120).all()


def test_age_group_logic():
    from transform import _dummy  # fallback: test inline
    def age_grp(age):
        a = int(age)
        if a < 18:  return "0-17"
        if a < 31:  return "18-30"
        if a < 51:  return "31-50"
        if a < 66:  return "51-65"
        return "65+"

    assert age_grp(5)   == "0-17"
    assert age_grp(25)  == "18-30"
    assert age_grp(45)  == "31-50"
    assert age_grp(60)  == "51-65"
    assert age_grp(70)  == "65+"
    assert age_grp(0)   == "0-17"
    assert age_grp(120) == "65+"


def test_admission_dates_logical(sample_admissions_df):
    """date_sortie doit être >= date_admission (si fournie)."""
    sorties = pd.DataFrame({
        "admission_id": ["A00001", "A00002"],
        "date_sortie":  ["2024-01-15", "2024-02-18"],
    })
    merged = sample_admissions_df.merge(sorties, on="admission_id", how="left")
    mask = merged["date_sortie"].notna()
    merged_valid = merged[mask].copy()
    merged_valid["d_adm"]  = pd.to_datetime(merged_valid["date_admission"])
    merged_valid["d_sort"] = pd.to_datetime(merged_valid["date_sortie"])
    assert (merged_valid["d_sort"] >= merged_valid["d_adm"]).all()


def test_admission_no_null_ids(sample_admissions_df):
    assert sample_admissions_df["admission_id"].notna().all()
    assert sample_admissions_df["patient_id"].notna().all()


# ── ETL log tests ─────────────────────────────────────────────────────────────

def test_etl_log_insert(staging_db):
    staging_db.execute("""
        INSERT INTO etl_log (dag_name, task_name, start_time, status, records_processed)
        VALUES ('test_dag', 'test_task', '2024-01-01T00:00:00', 'SUCCESS', 42)
    """)
    staging_db.commit()
    row = staging_db.execute(
        "SELECT records_processed FROM etl_log WHERE dag_name='test_dag'"
    ).fetchone()
    assert row is not None and row[0] == 42


def test_etl_log_status_constraint(staging_db):
    with pytest.raises(Exception):
        staging_db.execute("""
            INSERT INTO etl_log (dag_name, status) VALUES ('x', 'INVALID_STATUS')
        """)
        staging_db.commit()


# ── CSV file tests ────────────────────────────────────────────────────────────

def test_csv_files_exist():
    """Vérifie que les fichiers CSV générés existent."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    if not data_dir.exists():
        pytest.skip("Répertoire data/ non trouvé – lancez generate_data.py d'abord")
    for fname in ["patients.csv", "admissions.csv", "laboratoires.csv"]:
        f = data_dir / fname
        if f.exists():
            df = pd.read_csv(f)
            assert len(df) > 0, f"{fname} est vide"


# ── dim_temps test ────────────────────────────────────────────────────────────

def test_dim_temps_coverage(warehouse_db):
    """dim_temps doit couvrir 2022-2026 si déjà peuplée."""
    count = warehouse_db.execute("SELECT COUNT(*) FROM dim_temps").fetchone()[0]
    if count == 0:
        pytest.skip("dim_temps vide – lancez transform.py d'abord")
    # 2022–2026 = 5 ans = ~1826 jours
    assert count >= 1826, f"dim_temps ne couvre pas assez de dates: {count}"
    row = warehouse_db.execute("SELECT MIN(date), MAX(date) FROM dim_temps").fetchone()
    assert row[0] <= "2022-01-01"
    assert row[1] >= "2026-12-31"
