"""
DAG : consolidation_donnees
Fusionne toutes les sources (CSV, Excel, XML, JSON, API, MySQL) en une vue
analytique unifiée dans le Data Warehouse.

Étapes :
  1. verif_sources      – vérifie que staging et warehouse sont peuplés
  2. consolider_dims    – recharge/met à jour toutes les dimensions
  3. consolider_facts   – recharge/met à jour toutes les tables de faits
  4. creer_mart         – crée la vue dénormalisée analytics_mart
  5. calculer_kpis      – matérialise les KPI dans kpi_cache
  6. export_csv         – exporte analytics_mart en CSV (reports/)
  7. validation_finale  – vérifie intégrité référentielle et compte lignes

Schedule : quotidien (@daily), après nettoyage_groupement
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
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
    "start_date":       datetime(2024, 1, 1),
}

dag = DAG(
    "consolidation_donnees",
    default_args=default_args,
    description="Consolidation toutes sources → analytics_mart + KPI cache",
    schedule="@daily",
    catchup=False,
    tags=["consolidation", "mart", "kpi", "export"],
    doc_md="""
## consolidation_donnees

Fusionne toutes les sources du Data Warehouse en une source unique analytique.

**Produit :**
- Table `analytics_mart` (dénormalisée, prête BI)
- Table `kpi_cache` (KPIs pré-calculés)
- Fichier `reports/analytics_mart_YYYY-MM-DD.csv`
    """,
)


# ── 1. VÉRIFICATION SOURCES ───────────────────────────────────────────────────

def _verif_sources(**ctx):
    import pandas as pd
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse

    init_warehouse()
    staging = get_staging_engine()
    wh      = get_warehouse_engine()

    staging_tables = [
        "stg_patients", "stg_admissions", "stg_laboratoires",
        "stg_medicaments", "stg_hopitaux",
    ]
    wh_tables = [
        "dim_patient", "dim_hopital", "dim_maladie", "dim_region",
        "fact_admissions",
    ]

    print("  Sources staging :")
    staging_ok = True
    for t in staging_tables:
        try:
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", staging).iloc[0]["n"]
            print(f"    {t:<30} {n:>8,} lignes")
            if n == 0:
                staging_ok = False
        except Exception:
            print(f"    {t:<30}   ⚠ absente")
            staging_ok = False

    print("  Warehouse :")
    for t in wh_tables:
        try:
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", wh).iloc[0]["n"]
            print(f"    {t:<30} {n:>8,} lignes")
        except Exception:
            print(f"    {t:<30}   (vide)")

    ctx["ti"].xcom_push(key="staging_ok", value=staging_ok)
    if not staging_ok:
        print("  ⚠ Certaines tables staging sont vides — résultats partiels attendus")


# ── 2. CONSOLIDER DIMENSIONS ─────────────────────────────────────────────────

def _consolider_dims(**ctx):
    from transform import (transform_dim_patient, transform_dim_hopital,
                           transform_dim_maladie, transform_dim_region,
                           transform_dim_temps)
    from db_utils import get_staging_engine, get_warehouse_engine, init_warehouse

    init_warehouse()
    staging = get_staging_engine()
    wh      = get_warehouse_engine()

    dims = {
        "dim_patient":  lambda: transform_dim_patient(staging, wh),
        "dim_hopital":  lambda: transform_dim_hopital(staging, wh),
        "dim_maladie":  lambda: transform_dim_maladie(staging, wh),
        "dim_region":   lambda: transform_dim_region(staging, wh),
        "dim_temps":    lambda: transform_dim_temps(staging, wh),
    }

    total = 0
    for name, fn in dims.items():
        try:
            n = fn()
            total += n or 0
            print(f"  ✓ {name}: {n} lignes")
        except Exception as e:
            print(f"  ⚠ {name}: {e}")

    ctx["ti"].xcom_push(key="n_dims", value=total)


# ── 3. CONSOLIDER FAITS ───────────────────────────────────────────────────────

def _consolider_facts(**ctx):
    from transform import (transform_fact_admissions, transform_fact_urgences,
                           transform_fact_laboratoires, transform_fact_prescriptions)
    from db_utils import get_staging_engine, get_warehouse_engine

    staging = get_staging_engine()
    wh      = get_warehouse_engine()

    facts = {
        "fact_admissions":    lambda: transform_fact_admissions(staging, wh),
        "fact_urgences":      lambda: transform_fact_urgences(staging, wh),
        "fact_laboratoires":  lambda: transform_fact_laboratoires(staging, wh),
        "fact_prescriptions": lambda: transform_fact_prescriptions(staging, wh),
    }

    total = 0
    for name, fn in facts.items():
        try:
            n = fn()
            total += n or 0
            print(f"  ✓ {name}: {n} lignes")
        except Exception as e:
            print(f"  ⚠ {name}: {e}")

    ctx["ti"].xcom_push(key="n_facts", value=total)


# ── 4. CRÉER ANALYTICS MART ───────────────────────────────────────────────────

def _creer_mart(**ctx):
    """
    Crée la table dénormalisée analytics_mart en joignant
    fact_admissions avec toutes les dimensions.
    """
    import pandas as pd
    from sqlalchemy import text
    from db_utils import get_warehouse_engine

    wh = get_warehouse_engine()

    sql = """
        SELECT
            fa.admission_id,
            fa.patient_id,
            p.nom,
            p.prenom,
            p.sexe,
            p.age,
            p.tranche_age,
            p.ville,
            fa.hopital_id,
            h.nom_hopital,
            h.type_hopital,
            h.capacite_lits,
            h.ville                AS ville_hopital,
            r.nom_region,
            r.population           AS pop_region,
            fa.maladie_id,
            m.nom_maladie,
            m.categorie            AS categorie_maladie,
            m.code_cim10,
            m.est_chronique,
            fa.temps_id,
            t.date,
            t.annee,
            t.trimestre,
            t.mois,
            t.nom_mois,
            t.semaine,
            t.est_weekend,
            fa.duree_sejour,
            fa.cout_hospitalisation,
            fa.mode_admission,
            fa.mode_sortie,
            fa.service
        FROM fact_admissions fa
        LEFT JOIN dim_patient p  ON fa.patient_id  = p.patient_id
        LEFT JOIN dim_hopital h  ON fa.hopital_id  = h.hopital_id
        LEFT JOIN dim_region  r  ON h.region_id    = r.region_id
        LEFT JOIN dim_maladie m  ON fa.maladie_id  = m.maladie_id
        LEFT JOIN dim_temps   t  ON fa.temps_id    = t.temps_id
    """

    try:
        df = pd.read_sql(sql, wh)
        df.to_sql("analytics_mart", wh, if_exists="replace", index=False)
        print(f"  ✓ analytics_mart créé : {len(df):,} lignes × {len(df.columns)} colonnes")
        ctx["ti"].xcom_push(key="n_mart", value=len(df))
    except Exception as e:
        print(f"  ⚠ Création analytics_mart: {e}")
        ctx["ti"].xcom_push(key="n_mart", value=0)


# ── 5. CALCULER KPIs ─────────────────────────────────────────────────────────

def _calculer_kpis(**ctx):
    """Pré-calcule les KPIs et les matérialise dans kpi_cache."""
    import pandas as pd
    from db_utils import get_warehouse_engine

    wh = get_warehouse_engine()

    kpis = []

    kpi_queries = {
        "taux_occupation_moyen": """
            SELECT ROUND(AVG(CAST(lits_occupes AS REAL) / NULLIF(lits_total,0) * 100), 1)
            FROM fact_occupation_lits
        """,
        "dms_moyen": """
            SELECT ROUND(AVG(duree_sejour), 1) FROM fact_admissions WHERE duree_sejour > 0
        """,
        "nb_admissions_total": """
            SELECT COUNT(*) FROM fact_admissions
        """,
        "nb_patients_distincts": """
            SELECT COUNT(DISTINCT patient_id) FROM fact_admissions
        """,
        "cout_moyen_sejour": """
            SELECT ROUND(AVG(cout_hospitalisation), 2) FROM fact_admissions
        """,
        "nb_maladies_distinctes": """
            SELECT COUNT(DISTINCT maladie_id) FROM fact_admissions
        """,
        "nb_hopitaux_actifs": """
            SELECT COUNT(DISTINCT hopital_id) FROM fact_admissions
        """,
        "pct_mode_urgence": """
            SELECT ROUND(100.0 * SUM(CASE WHEN mode_admission='Urgence' THEN 1 ELSE 0 END)
                         / NULLIF(COUNT(*),0), 1)
            FROM fact_admissions
        """,
    }

    for nom, sql in kpi_queries.items():
        try:
            val = pd.read_sql(sql.strip(), wh).iloc[0, 0]
            kpis.append({"kpi": nom, "valeur": str(val) if val is not None else "N/A",
                         "date_calcul": datetime.utcnow().isoformat()})
            print(f"  ✓ {nom}: {val}")
        except Exception as e:
            kpis.append({"kpi": nom, "valeur": "ERREUR", "date_calcul": datetime.utcnow().isoformat()})
            print(f"  ⚠ {nom}: {e}")

    # Top 5 maladies
    try:
        df = pd.read_sql("""
            SELECT m.nom_maladie, COUNT(*) AS nb
            FROM fact_admissions fa
            JOIN dim_maladie m ON fa.maladie_id = m.maladie_id
            GROUP BY m.nom_maladie ORDER BY nb DESC LIMIT 5
        """, wh)
        for i, row in df.iterrows():
            kpis.append({
                "kpi":         f"top_maladie_{i+1}",
                "valeur":      f"{row['nom_maladie']} ({row['nb']} cas)",
                "date_calcul": datetime.utcnow().isoformat(),
            })
            print(f"  ✓ top_maladie_{i+1}: {row['nom_maladie']} ({row['nb']} cas)")
    except Exception as e:
        print(f"  ⚠ Top maladies: {e}")

    # Sauvegarder dans kpi_cache
    try:
        df_kpi = pd.DataFrame(kpis)
        df_kpi.to_sql("kpi_cache", wh, if_exists="replace", index=False)
        print(f"\n  ✓ kpi_cache : {len(kpis)} indicateurs sauvegardés")
    except Exception as e:
        print(f"  ⚠ Sauvegarde kpi_cache: {e}")


# ── 6. EXPORT CSV ─────────────────────────────────────────────────────────────

def _export_csv(**ctx):
    """Exporte analytics_mart en CSV dans reports/."""
    import pandas as pd
    from db_utils import get_warehouse_engine, load_config

    wh  = get_warehouse_engine()
    cfg = load_config()

    reports_dir = Path(cfg["paths"]["base_dir"]) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    date_str  = datetime.utcnow().strftime("%Y-%m-%d")
    csv_path  = reports_dir / f"analytics_mart_{date_str}.csv"
    kpi_path  = reports_dir / f"kpi_cache_{date_str}.csv"

    try:
        df = pd.read_sql("SELECT * FROM analytics_mart", wh)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  ✓ analytics_mart exporté : {csv_path} ({len(df):,} lignes)")
    except Exception as e:
        print(f"  ⚠ Export analytics_mart: {e}")

    try:
        df_kpi = pd.read_sql("SELECT * FROM kpi_cache", wh)
        df_kpi.to_csv(kpi_path, index=False, encoding="utf-8-sig")
        print(f"  ✓ kpi_cache exporté : {kpi_path}")
    except Exception as e:
        print(f"  ⚠ Export kpi_cache: {e}")

    ctx["ti"].xcom_push(key="csv_path", value=str(csv_path))


# ── 7. VALIDATION FINALE ─────────────────────────────────────────────────────

def _validation_finale(**ctx):
    import pandas as pd
    from db_utils import get_warehouse_engine, get_staging_engine, log_etl

    wh      = get_warehouse_engine()
    staging = get_staging_engine()
    n_mart  = ctx["ti"].xcom_pull(key="n_mart",  task_ids="creer_analytics_mart") or 0
    n_dims  = ctx["ti"].xcom_pull(key="n_dims",  task_ids="consolider_dimensions") or 0
    n_facts = ctx["ti"].xcom_pull(key="n_facts", task_ids="consolider_faits")      or 0

    # Vérification intégrité : admissions sans patient connu
    try:
        df = pd.read_sql("""
            SELECT COUNT(*) AS n FROM fact_admissions fa
            LEFT JOIN dim_patient p ON fa.patient_id = p.patient_id
            WHERE p.patient_id IS NULL
        """, wh)
        orphelins = df.iloc[0]["n"]
        if orphelins > 0:
            print(f"  ⚠ {orphelins} admissions sans patient correspondant dans dim_patient")
        else:
            print("  ✓ Intégrité référentielle OK (0 orphelins)")
    except Exception as e:
        print(f"  ⚠ Vérif intégrité: {e}")

    print("\n  ╔══════════════════════════════════════╗")
    print("  ║     CONSOLIDATION TERMINÉE           ║")
    print("  ╠══════════════════════════════════════╣")
    print(f"  ║  Dimensions chargées : {n_dims:<13,}║")
    print(f"  ║  Faits chargés       : {n_facts:<13,}║")
    print(f"  ║  analytics_mart      : {n_mart:<13,}║")
    print("  ╚══════════════════════════════════════╝\n")

    log_etl(staging, "consolidation_donnees", "validation_finale",
            "SUCCESS", n_mart)


# ── Task wiring ───────────────────────────────────────────────────────────────

t_verif    = PythonOperator(task_id="verif_sources",         python_callable=_verif_sources,    dag=dag)
t_dims     = PythonOperator(task_id="consolider_dimensions", python_callable=_consolider_dims,  dag=dag)
t_facts    = PythonOperator(task_id="consolider_faits",      python_callable=_consolider_facts, dag=dag)
t_mart     = PythonOperator(task_id="creer_analytics_mart",  python_callable=_creer_mart,       dag=dag)
t_kpis     = PythonOperator(task_id="calculer_kpis",         python_callable=_calculer_kpis,    dag=dag)
t_export   = PythonOperator(task_id="export_csv",            python_callable=_export_csv,       dag=dag)
t_validate = PythonOperator(task_id="validation_finale",     python_callable=_validation_finale,dag=dag)

t_verif >> [t_dims, t_facts] >> t_mart >> t_kpis >> t_export >> t_validate
