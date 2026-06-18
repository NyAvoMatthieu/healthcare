"""
DAG : ingestion_api_maladies
Extraction hebdomadaire des données épidémiologiques depuis l'API REST publique simulée.
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
    "retry_delay":       timedelta(minutes=10),
    "start_date":        datetime(2024, 1, 1),
}

dag = DAG(
    "ingestion_api_maladies",
    default_args=default_args,
    description="Ingestion hebdomadaire API santé publique → warehouse",
    schedule_interval="@weekly",
    catchup=False,
    tags=["api", "maladies", "epidemies", "ingestion"],
    doc_md="""
## ingestion_api_maladies

Interroge l'API REST de santé publique simulée pour récupérer :
- La liste des maladies référencées (avec codes CIM-10)
- Les alertes épidémiques en cours
- Les statistiques régionales de santé

Si l'API est inaccessible, le DAG se termine en SKIPPED sans erreur critique.
    """,
)


def _check_api(**ctx):
    from extract_api import check_api
    from db_utils import load_config
    cfg = load_config()
    ok  = check_api(cfg)
    ctx["ti"].xcom_push(key="api_ok", value=ok)
    if not ok:
        print("  API non disponible – démarrez api/mock_api.py")


def _extract_maladies(**ctx):
    if not ctx["ti"].xcom_pull(key="api_ok", task_ids="check_api_availability"):
        print("  API non disponible – ignoré"); return
    from extract_api import extract_maladies
    from db_utils import get_staging_engine, init_staging, load_config
    init_staging()
    n = extract_maladies(get_staging_engine(), load_config())
    ctx["ti"].xcom_push(key="n_maladies", value=n)
    print(f"  ✓ {n} maladies extraites")


def _extract_epidemies(**ctx):
    if not ctx["ti"].xcom_pull(key="api_ok", task_ids="check_api_availability"):
        print("  API non disponible – ignoré"); return
    from extract_api import extract_epidemies
    from db_utils import get_staging_engine, load_config
    n = extract_epidemies(get_staging_engine(), load_config())
    ctx["ti"].xcom_push(key="n_epidemies", value=n)
    print(f"  ✓ {n} épidémies extraites")


def _extract_regions(**ctx):
    if not ctx["ti"].xcom_pull(key="api_ok", task_ids="check_api_availability"):
        print("  API non disponible – ignoré"); return
    from extract_api import extract_regions
    from db_utils import get_staging_engine, load_config
    n = extract_regions(get_staging_engine(), load_config())
    ctx["ti"].xcom_push(key="n_regions", value=n)
    print(f"  ✓ {n} régions extraites")


def _validate_api_data(**ctx):
    import pandas as pd
    from db_utils import get_staging_engine
    engine = get_staging_engine()
    for table in ["stg_api_maladies", "stg_api_epidemies", "stg_api_regions"]:
        df = pd.read_sql(f"SELECT COUNT(*) AS n FROM {table}", engine)
        n  = df.iloc[0]["n"]
        print(f"  {table}: {n} lignes")
    print("  ✓ Validation API data OK")


def _transform_maladie(**ctx):
    if not ctx["ti"].xcom_pull(key="api_ok", task_ids="check_api_availability"):
        return
    from transform import transform_dim_maladie, transform_dim_region
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse
    init_warehouse()
    staging = get_staging_engine()
    wh      = get_warehouse_engine()
    n_mal = transform_dim_maladie(staging, wh)
    n_reg = transform_dim_region(staging, wh)
    print(f"  ✓ dim_maladie: {n_mal}, dim_region: {n_reg}")


def _compute_epidemio_kpis(**ctx):
    """Calcule les KPI épidémiologiques de base."""
    import pandas as pd
    from db_utils import get_warehouse_engine
    wh = get_warehouse_engine()
    try:
        df = pd.read_sql("""
            SELECT m.categorie, COUNT(*) AS nb_cas
            FROM fact_admissions fa
            JOIN dim_maladie m ON fa.maladie_id = m.maladie_id
            GROUP BY m.categorie ORDER BY nb_cas DESC
        """, wh)
        print("  Cas par catégorie de maladie :")
        for _, row in df.iterrows():
            print(f"    {row['categorie']}: {row['nb_cas']}")
    except Exception as e:
        print(f"  KPI non calculables (warehouse vide?): {e}")


def _update_etl_log(**ctx):
    from db_utils import get_staging_engine, log_etl
    engine  = get_staging_engine()
    api_ok  = ctx["ti"].xcom_pull(key="api_ok",      task_ids="check_api_availability")
    n_mal   = ctx["ti"].xcom_pull(key="n_maladies",   task_ids="extract_api_maladies")  or 0
    n_epi   = ctx["ti"].xcom_pull(key="n_epidemies",  task_ids="extract_api_epidemies") or 0
    n_reg   = ctx["ti"].xcom_pull(key="n_regions",    task_ids="extract_api_regions_stats") or 0
    status  = "SUCCESS" if api_ok else "SKIPPED"
    log_etl(engine, "ingestion_api_maladies", "pipeline_complete", status,
            n_mal + n_epi + n_reg)
    print(f"  ✓ ETL log: {status} – maladies={n_mal}, épidémies={n_epi}, régions={n_reg}")


t_check    = PythonOperator(task_id="check_api_availability",    python_callable=_check_api,          dag=dag)
t_maladies = PythonOperator(task_id="extract_api_maladies",      python_callable=_extract_maladies,   dag=dag)
t_epidemies= PythonOperator(task_id="extract_api_epidemies",     python_callable=_extract_epidemies,  dag=dag)
t_regions  = PythonOperator(task_id="extract_api_regions_stats", python_callable=_extract_regions,    dag=dag)
t_validate = PythonOperator(task_id="validate_api_data",         python_callable=_validate_api_data,  dag=dag)
t_transform= PythonOperator(task_id="transform_dim_maladie",     python_callable=_transform_maladie,  dag=dag)
t_kpis     = PythonOperator(task_id="compute_epidemio_kpis",     python_callable=_compute_epidemio_kpis, dag=dag)
t_log      = PythonOperator(task_id="update_etl_log",            python_callable=_update_etl_log,     dag=dag)

t_check >> [t_maladies, t_epidemies, t_regions] >> t_validate >> t_transform >> t_kpis >> t_log
