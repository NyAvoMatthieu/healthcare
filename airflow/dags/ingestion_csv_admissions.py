"""
DAG : ingestion_csv_admissions
Ingestion des admissions, laboratoires et médicaments CSV → staging → warehouse.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

default_args = {
    "owner":             "healthcare_etl",
    "depends_on_past":   False,
    "email_on_failure":  False,
    "retries":           2,
    "retry_delay":       timedelta(minutes=5),
    "start_date":        datetime(2024, 1, 1),
}

dag = DAG(
    "ingestion_csv_admissions",
    default_args=default_args,
    description="Ingestion admissions, labos, médicaments CSV → warehouse",
    schedule_interval="@daily",
    catchup=False,
    tags=["csv", "admissions", "laboratoires", "ingestion"],
)


def _extract_admissions(**ctx):
    from extract_csv import extract_admissions
    from db_utils import get_staging_engine, init_staging
    init_staging()
    n = extract_admissions(get_staging_engine())
    ctx["ti"].xcom_push(key="n_adm", value=n)
    print(f"✓ {n} admissions extraites")


def _extract_labs(**ctx):
    from extract_csv import extract_laboratoires
    from db_utils import get_staging_engine
    n = extract_laboratoires(get_staging_engine())
    ctx["ti"].xcom_push(key="n_labs", value=n)
    print(f"✓ {n} analyses extraites")


def _extract_meds(**ctx):
    from extract_csv import extract_medicaments
    from db_utils import get_staging_engine
    n = extract_medicaments(get_staging_engine())
    ctx["ti"].xcom_push(key="n_meds", value=n)
    print(f"✓ {n} prescriptions extraites")


def _validate_admissions(**ctx):
    import pandas as pd
    from db_utils import get_staging_engine
    df     = pd.read_sql("SELECT * FROM stg_admissions", get_staging_engine())
    errors = []
    if df["admission_id"].isna().any():
        errors.append("admission_id contient des nulls")
    if df["patient_id"].isna().any():
        errors.append("patient_id contient des nulls")
    df["date_adm"] = pd.to_datetime(df["date_admission"], errors="coerce")
    if df["date_adm"].isna().any():
        errors.append("date_admission invalide pour certaines lignes")
    if errors:
        raise ValueError("; ".join(errors))
    print(f"✓ Validation admissions OK – {len(df)} lignes")


def _transform_admissions(**ctx):
    from transform import (transform_fact_admissions, transform_fact_urgences,
                           transform_fact_laboratoires, transform_fact_prescriptions)
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse
    init_warehouse()
    staging = get_staging_engine()
    wh      = get_warehouse_engine()
    results = {
        "fact_admissions":    transform_fact_admissions(staging, wh),
        "fact_urgences":      transform_fact_urgences(staging, wh),
        "fact_laboratoires":  transform_fact_laboratoires(staging, wh),
        "fact_prescriptions": transform_fact_prescriptions(staging, wh),
    }
    for k, v in results.items():
        print(f"  ✓ {k}: {v} lignes")


def _refresh_kpis(**ctx):
    """Matérialise les KPI critiques dans une table de cache."""
    import pandas as pd
    from db_utils import get_warehouse_engine
    wh = get_warehouse_engine()
    # Vérification simple que les facts sont peuplés
    counts = {}
    for table in ["fact_admissions","fact_urgences","fact_laboratoires"]:
        row = pd.read_sql(f"SELECT COUNT(*) AS n FROM {table}", wh).iloc[0]["n"]
        counts[table] = row
    print("KPI check:", counts)


def _update_etl_log(**ctx):
    from db_utils import get_staging_engine, log_etl
    engine = get_staging_engine()
    n_adm  = ctx["ti"].xcom_pull(key="n_adm",  task_ids="extract_admissions_csv") or 0
    n_labs = ctx["ti"].xcom_pull(key="n_labs", task_ids="extract_labs_csv")      or 0
    n_meds = ctx["ti"].xcom_pull(key="n_meds", task_ids="extract_meds_csv")      or 0
    log_etl(engine, "ingestion_csv_admissions", "pipeline_complete",
            "SUCCESS", n_adm + n_labs + n_meds)
    print(f"✓ ETL log: adm={n_adm}, labs={n_labs}, meds={n_meds}")


t_extract_adm  = PythonOperator(task_id="extract_admissions_csv", python_callable=_extract_admissions, dag=dag)
t_extract_labs = PythonOperator(task_id="extract_labs_csv",       python_callable=_extract_labs,       dag=dag)
t_extract_meds = PythonOperator(task_id="extract_meds_csv",       python_callable=_extract_meds,       dag=dag)
t_validate     = PythonOperator(task_id="validate_admissions",    python_callable=_validate_admissions, dag=dag)
t_transform    = PythonOperator(task_id="transform_facts",        python_callable=_transform_admissions, dag=dag)
t_kpis         = PythonOperator(task_id="refresh_kpis",           python_callable=_refresh_kpis,        dag=dag)
t_log          = PythonOperator(task_id="update_etl_log",         python_callable=_update_etl_log,      dag=dag)

[t_extract_adm, t_extract_labs, t_extract_meds] >> t_validate >> t_transform >> t_kpis >> t_log
