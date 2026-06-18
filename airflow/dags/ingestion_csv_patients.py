"""
DAG : ingestion_csv_patients
Extrait les fichiers CSV patients / sorties et alimente le Data Warehouse.
"""
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Ajouter scripts/ au path pour les imports locaux
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

default_args = {
    "owner":             "healthcare_etl",
    "depends_on_past":   False,
    "email_on_failure":  False,
    "email_on_retry":    False,
    "retries":           2,
    "retry_delay":       timedelta(minutes=5),
    "start_date":        datetime(2024, 1, 1),
}

dag = DAG(
    "ingestion_csv_patients",
    default_args=default_args,
    description="Ingestion quotidienne des fichiers CSV patients → staging → warehouse",
    schedule_interval="@daily",
    catchup=False,
    tags=["csv", "patients", "ingestion"],
    doc_md="""
## ingestion_csv_patients

Ce DAG lit les fichiers CSV **patients.csv** et **sorties.csv**, valide
les données, charge le staging SQLite, puis transforme vers le Data Warehouse.

**Sources :** `data/patients.csv`, `data/sorties.csv`
**Cible :**   `staging/staging.db` → `warehouse/warehouse.db`
    """,
)


def _check_csv_files(**ctx):
    from pathlib import Path
    base = Path(SCRIPTS_DIR).parent
    required = ["patients.csv", "sorties.csv"]
    missing  = [f for f in required if not (base / "data" / f).exists()]
    if missing:
        raise FileNotFoundError(f"Fichiers CSV manquants : {missing}")
    print(f"✓ Fichiers CSV présents : {required}")


def _extract_patients(**ctx):
    from extract_csv import extract_patients
    from db_utils import get_staging_engine, init_staging
    init_staging()
    n = extract_patients(get_staging_engine())
    print(f"✓ {n} patients extraits")
    ctx["ti"].xcom_push(key="n_patients", value=n)


def _extract_sorties(**ctx):
    from extract_csv import extract_sorties
    from db_utils import get_staging_engine
    n = extract_sorties(get_staging_engine())
    print(f"✓ {n} sorties extraites")


def _validate_patients(**ctx):
    import pandas as pd
    from db_utils import get_staging_engine
    engine = get_staging_engine()
    df = pd.read_sql("SELECT * FROM stg_patients", engine)
    errors = []
    if df["patient_id"].isna().any():
        errors.append("patient_id contient des valeurs nulles")
    invalid_sexe = df[~df["sexe"].isin(["M","F","m","f"])]["sexe"].unique()
    if len(invalid_sexe) > 0:
        errors.append(f"Valeurs sexe invalides : {invalid_sexe}")
    df["age_num"] = pd.to_numeric(df["age"], errors="coerce")
    if (df["age_num"] < 0).any() or (df["age_num"] > 120).any():
        errors.append("Âges hors plage [0, 120]")
    if errors:
        raise ValueError("Validation échouée : " + "; ".join(errors))
    print(f"✓ Validation OK – {len(df)} patients valides")


def _transform_patients(**ctx):
    from transform import transform_dim_patient
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse
    init_warehouse()
    n = transform_dim_patient(get_staging_engine(), get_warehouse_engine())
    print(f"✓ dim_patient: {n} lignes chargées")


def _update_etl_log(**ctx):
    from db_utils import get_staging_engine, log_etl
    engine = get_staging_engine()
    n = ctx["ti"].xcom_pull(key="n_patients", task_ids="extract_patients_csv") or 0
    log_etl(engine, "ingestion_csv_patients", "pipeline_complete", "SUCCESS", n)
    print(f"✓ ETL log mis à jour ({n} enregistrements)")


check_files     = PythonOperator(task_id="check_csv_files",     python_callable=_check_csv_files,  dag=dag)
extract_patients = PythonOperator(task_id="extract_patients_csv", python_callable=_extract_patients, dag=dag)
extract_sorties  = PythonOperator(task_id="extract_sorties_csv",  python_callable=_extract_sorties,  dag=dag)
validate         = PythonOperator(task_id="validate_patients",    python_callable=_validate_patients, dag=dag)
transform        = PythonOperator(task_id="transform_patients",   python_callable=_transform_patients, dag=dag)
update_log       = PythonOperator(task_id="update_etl_log",       python_callable=_update_etl_log,   dag=dag)

check_files >> [extract_patients, extract_sorties] >> validate >> transform >> update_log
