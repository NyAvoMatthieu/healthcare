"""
DAG : ingestion_mysql
Extraction incrémentale depuis MySQL (système hospitalier opérationnel) → staging.
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
    "retries":           3,
    "retry_delay":       timedelta(minutes=2),
    "start_date":        datetime(2024, 1, 1),
}

dag = DAG(
    "ingestion_mysql",
    default_args=default_args,
    description="Extraction incrémentale MySQL → staging SQLite (toutes les heures)",
    schedule_interval="@hourly",
    catchup=False,
    tags=["mysql", "incremental", "ingestion"],
    doc_md="""
## ingestion_mysql

Extraction incrémentale de la base MySQL opérationnelle.
Utilise `updated_at > dernière_extraction` pour ne charger que les nouvelles lignes.

**Fréquence :** toutes les heures
**Condition :** si MySQL non disponible → DAG marqué SKIPPED (pas d'échec)
    """,
)


def _check_mysql(**ctx):
    from extract_mysql import check_mysql_connection
    from db_utils import get_mysql_engine
    try:
        engine = get_mysql_engine()
        ok = check_mysql_connection(engine)
    except Exception as e:
        ok = False
        print(f"  Erreur config MySQL: {e}")
    ctx["ti"].xcom_push(key="mysql_ok", value=ok)
    if not ok:
        print("  MySQL non disponible – DAG passera en mode dégradé")


def _extract_patients(**ctx):
    mysql_ok = ctx["ti"].xcom_pull(key="mysql_ok", task_ids="check_mysql_connection")
    if not mysql_ok:
        print("  MySQL non disponible – tâche ignorée"); return
    from extract_mysql import extract_mysql_patients
    from db_utils import get_mysql_engine, get_staging_engine, init_staging
    init_staging()
    n = extract_mysql_patients(get_mysql_engine(), get_staging_engine())
    ctx["ti"].xcom_push(key="n_patients", value=n)
    print(f"  ✓ {n} patients extraits depuis MySQL")


def _extract_admissions(**ctx):
    mysql_ok = ctx["ti"].xcom_pull(key="mysql_ok", task_ids="check_mysql_connection")
    if not mysql_ok:
        print("  MySQL non disponible – tâche ignorée"); return
    from extract_mysql import extract_mysql_admissions
    from db_utils import get_mysql_engine, get_staging_engine
    n = extract_mysql_admissions(get_mysql_engine(), get_staging_engine())
    ctx["ti"].xcom_push(key="n_admissions", value=n)
    print(f"  ✓ {n} admissions extraites depuis MySQL")


def _merge_staging(**ctx):
    """Déduplique les enregistrements MySQL vs CSV dans le staging."""
    import pandas as pd
    from db_utils import get_staging_engine
    engine = get_staging_engine()
    # Exemple : supprimer les doublons patients (même patient_id)
    df = pd.read_sql("SELECT * FROM stg_patients", engine)
    before = len(df)
    df = df.drop_duplicates(subset=["patient_id"], keep="last")
    after = len(df)
    if before != after:
        df.to_sql("stg_patients", engine, if_exists="replace", index=False)
        print(f"  ✓ Déduplication: {before} → {after} patients")
    else:
        print(f"  ✓ Pas de doublons détectés ({before} patients)")


def _update_dimensions(**ctx):
    mysql_ok = ctx["ti"].xcom_pull(key="mysql_ok", task_ids="check_mysql_connection")
    if not mysql_ok:
        return
    from transform import transform_dim_patient
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse
    init_warehouse()
    n = transform_dim_patient(get_staging_engine(), get_warehouse_engine())
    print(f"  ✓ dim_patient mise à jour: {n} lignes")


def _update_facts(**ctx):
    mysql_ok = ctx["ti"].xcom_pull(key="mysql_ok", task_ids="check_mysql_connection")
    if not mysql_ok:
        return
    from transform import transform_fact_admissions, transform_fact_urgences
    from db_utils import get_staging_engine, get_warehouse_engine
    staging = get_staging_engine()
    wh      = get_warehouse_engine()
    n_adm  = transform_fact_admissions(staging, wh)
    n_urg  = transform_fact_urgences(staging, wh)
    print(f"  ✓ fact_admissions: {n_adm}, fact_urgences: {n_urg}")


def _update_etl_log(**ctx):
    from db_utils import get_staging_engine, log_etl
    engine     = get_staging_engine()
    mysql_ok   = ctx["ti"].xcom_pull(key="mysql_ok", task_ids="check_mysql_connection")
    n_patients = ctx["ti"].xcom_pull(key="n_patients",  task_ids="extract_mysql_patients") or 0
    n_adm      = ctx["ti"].xcom_pull(key="n_admissions", task_ids="extract_mysql_admissions") or 0
    status     = "SUCCESS" if mysql_ok else "SKIPPED"
    log_etl(engine, "ingestion_mysql", "pipeline_complete", status,
            (n_patients or 0) + (n_adm or 0))
    print(f"  ✓ ETL log: status={status}, patients={n_patients}, admissions={n_adm}")


t_check   = PythonOperator(task_id="check_mysql_connection",    python_callable=_check_mysql,        dag=dag)
t_pat     = PythonOperator(task_id="extract_mysql_patients",    python_callable=_extract_patients,   dag=dag)
t_adm     = PythonOperator(task_id="extract_mysql_admissions",  python_callable=_extract_admissions, dag=dag)
t_merge   = PythonOperator(task_id="merge_staging",             python_callable=_merge_staging,      dag=dag)
t_dims    = PythonOperator(task_id="update_dimensions",         python_callable=_update_dimensions,  dag=dag)
t_facts   = PythonOperator(task_id="update_facts",              python_callable=_update_facts,       dag=dag)
t_log     = PythonOperator(task_id="update_etl_log",            python_callable=_update_etl_log,     dag=dag)

t_check >> [t_pat, t_adm] >> t_merge >> t_dims >> t_facts >> t_log
