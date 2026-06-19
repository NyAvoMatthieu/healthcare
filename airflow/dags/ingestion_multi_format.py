"""
DAG : ingestion_multi_format
Ingestion des sources Excel, XML et JSON vers le staging SQLite.

Sources traitées :
  - Excel : personnel_medical.xlsx (médecins, infirmiers, plannings)
  - XML   : comptes_rendus.xml (HL7-like discharge summaries)
  - JSON  : capteurs_lits.json (IoT capteurs d'occupation)
            stock_pharmacie.json (inventaire pharmacie)

Schedule : quotidien (@daily)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

default_args = {
    "owner":            "healthcare_etl",
    "depends_on_past":  False,
    "email_on_failure": False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "start_date":       datetime(2024, 1, 1),
}

dag = DAG(
    "ingestion_multi_format",
    default_args=default_args,
    description="Ingestion Excel + XML + JSON → staging SQLite",
    schedule="@daily",
    catchup=False,
    tags=["excel", "xml", "json", "multi-format", "ingestion"],
    doc_md="""
## ingestion_multi_format

Pipeline d'ingestion des sources de données multi-formats :

| Source | Fichier | Contenu |
|--------|---------|---------|
| Excel  | `personnel_medical.xlsx` | Médecins, Infirmiers, Plannings |
| XML    | `comptes_rendus.xml` | Comptes-rendus HL7-like |
| JSON   | `capteurs_lits.json` | Capteurs IoT occupation lits |
| JSON   | `stock_pharmacie.json` | Inventaire pharmacie |

Chaque groupe s'exécute en parallèle. Seule la validation est commune.
    """,
)

# ── Checks ────────────────────────────────────────────────────────────────────

def _check_files(**ctx):
    from pathlib import Path
    data_dir = Path(SCRIPTS_DIR).parent / "data"
    files    = {
        "Excel":  data_dir / "personnel_medical.xlsx",
        "XML":    data_dir / "comptes_rendus.xml",
        "JSON-1": data_dir / "capteurs_lits.json",
        "JSON-2": data_dir / "stock_pharmacie.json",
    }
    missing = {k: str(v) for k, v in files.items() if not v.exists()}
    present = {k for k in files if k not in missing}
    ctx["ti"].xcom_push(key="present_sources", value=list(present))
    if missing:
        print(f"  ⚠ Fichiers manquants (ignorés) : {list(missing.keys())}")
        print(f"    → Lancez les générateurs dans scripts/generate_*.py")
    print(f"  ✓ Sources disponibles : {list(present)}")


# ── Excel tasks ───────────────────────────────────────────────────────────────

def _extract_excel(**ctx):
    from extract_excel import run_all
    from db_utils import get_staging_engine, init_staging
    init_staging()
    n = run_all(get_staging_engine())
    ctx["ti"].xcom_push(key="n_excel", value=n)
    print(f"  ✓ Excel total: {n} lignes")


# ── XML tasks ─────────────────────────────────────────────────────────────────

def _extract_xml(**ctx):
    from extract_xml import run_all
    from db_utils import get_staging_engine, init_staging
    init_staging()
    n = run_all(get_staging_engine())
    ctx["ti"].xcom_push(key="n_xml", value=n)
    print(f"  ✓ XML total: {n} documents")


# ── JSON tasks ────────────────────────────────────────────────────────────────

def _extract_json(**ctx):
    from extract_json import run_all
    from db_utils import get_staging_engine, init_staging
    init_staging()
    n = run_all(get_staging_engine())
    ctx["ti"].xcom_push(key="n_json", value=n)
    print(f"  ✓ JSON total: {n:,} lignes")


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_all(**ctx):
    import pandas as pd
    from db_utils import get_staging_engine
    engine = get_staging_engine()
    tables = [
        "stg_personnel", "stg_plannings",
        "stg_comptes_rendus", "stg_actes_medicaux",
        "stg_capteurs_lits", "stg_stock_pharmacie",
    ]
    print("  Contenu staging (nouvelles sources) :")
    for t in tables:
        try:
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", engine).iloc[0]["n"]
            print(f"    {t:<30} {n:>8,} lignes")
        except Exception:
            print(f"    {t:<30}   (table absente)")

    # Validation métier : taux occupation capteurs
    try:
        df = pd.read_sql("""
            SELECT hopital_id,
                   ROUND(AVG(taux_occupation),1) AS taux_moy,
                   MAX(taux_occupation) AS taux_max
            FROM stg_capteurs_lits
            GROUP BY hopital_id
            ORDER BY taux_moy DESC LIMIT 5
        """, engine)
        print("\n  Top 5 hôpitaux par taux d'occupation moyen (capteurs) :")
        for _, row in df.iterrows():
            print(f"    {row['hopital_id']}: {row['taux_moy']}% (max {row['taux_max']}%)")
    except Exception as e:
        print(f"  ⚠ Validation capteurs: {e}")


# ── Transform new dimensions/facts ────────────────────────────────────────────

def _transform_new_facts(**ctx):
    """
    Charge les nouvelles tables de faits dans le warehouse :
    - fact_occupation_lits  (depuis stg_capteurs_lits)
    - fact_stock_pharmacie  (depuis stg_stock_pharmacie)

    La jointure avec dim_temps se fait en pandas (pas en SQL) car staging et
    warehouse sont deux bases SQLite distinctes — SQLite ne supporte pas les
    JOIN cross-database.
    """
    import pandas as pd
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse
    init_warehouse()
    staging = get_staging_engine()
    wh      = get_warehouse_engine()

    # Charger dim_temps depuis le warehouse pour la jointure pandas
    try:
        df_temps = pd.read_sql("SELECT temps_id, date FROM dim_temps", wh)
    except Exception:
        df_temps = pd.DataFrame(columns=["temps_id", "date"])
        print("  ⚠ dim_temps absente — temps_id sera NULL")

    # fact_occupation_lits
    try:
        df_cap = pd.read_sql("""
            SELECT capteur_id, hopital_id, service_id, date,
                   heure, lits_occupes, lits_total, taux_occupation, alertes
            FROM stg_capteurs_lits
        """, staging)
        if not df_cap.empty:
            df_cap = df_cap.merge(df_temps, on="date", how="left")
            df_cap.to_sql("fact_occupation_lits", wh, if_exists="replace", index=False)
            print(f"  ✓ fact_occupation_lits: {len(df_cap):,} lignes")
    except Exception as e:
        print(f"  ⚠ fact_occupation_lits: {e}")

    # fact_stock_pharmacie
    try:
        df_stk = pd.read_sql("""
            SELECT stock_id, date, code_medicament, nom_medicament,
                   stock_disponible, consommation_j, reapprovisionnement,
                   valeur_stock, sous_seuil_alerte
            FROM stg_stock_pharmacie
        """, staging)
        if not df_stk.empty:
            df_stk = df_stk.merge(df_temps, on="date", how="left")
            df_stk.to_sql("fact_stock_pharmacie", wh, if_exists="replace", index=False)
            print(f"  ✓ fact_stock_pharmacie: {len(df_stk):,} lignes")
    except Exception as e:
        print(f"  ⚠ fact_stock_pharmacie: {e}")


def _update_etl_log(**ctx):
    from db_utils import get_staging_engine, log_etl
    engine = get_staging_engine()
    n_excel = ctx["ti"].xcom_pull(key="n_excel", task_ids="extract_excel") or 0
    n_xml   = ctx["ti"].xcom_pull(key="n_xml",   task_ids="extract_xml")   or 0
    n_json  = ctx["ti"].xcom_pull(key="n_json",  task_ids="extract_json")  or 0
    log_etl(engine, "ingestion_multi_format", "pipeline_complete",
            "SUCCESS", n_excel + n_xml + n_json)
    print(f"  ✓ ETL log: excel={n_excel}, xml={n_xml}, json={n_json:,}")


# ── Task wiring ───────────────────────────────────────────────────────────────

t_check     = PythonOperator(task_id="check_source_files",  python_callable=_check_files,        dag=dag)
t_excel     = PythonOperator(task_id="extract_excel",       python_callable=_extract_excel,      dag=dag)
t_xml       = PythonOperator(task_id="extract_xml",         python_callable=_extract_xml,        dag=dag)
t_json      = PythonOperator(task_id="extract_json",        python_callable=_extract_json,       dag=dag)
t_validate  = PythonOperator(task_id="validate_all",        python_callable=_validate_all,       dag=dag)
t_transform = PythonOperator(task_id="transform_new_facts", python_callable=_transform_new_facts, dag=dag)
t_log       = PythonOperator(task_id="update_etl_log",      python_callable=_update_etl_log,     dag=dag)

# Les 3 extractions tournent en parallèle après le check
t_check >> [t_excel, t_xml, t_json] >> t_validate >> t_transform >> t_log
