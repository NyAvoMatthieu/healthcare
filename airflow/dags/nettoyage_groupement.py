"""
DAG : nettoyage_groupement
Audit qualité, déduplication, normalisation et groupement des données staging.

Étapes :
  1. audit_qualite     – détecte nulls, outliers, doublons par table
  2. deduplication     – supprime les doublons (garde le plus récent)
  3. normalisation     – homogénéise formats dates, sexe, codes postaux
  4. groupement        – calcule tranches d'âge, catégories DMS, taux occupation
  5. validation_finale – score qualité global et rapport synthèse

Schedule : quotidien (@daily), après les DAGs d'ingestion
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
    "nettoyage_groupement",
    default_args=default_args,
    description="Audit qualité, déduplication, normalisation et groupement du staging",
    schedule="@daily",
    catchup=False,
    tags=["qualite", "nettoyage", "groupement", "deduplication"],
    doc_md="""
## nettoyage_groupement

Pipeline de qualité des données — s'exécute après les DAGs d'ingestion.

| Étape | Action |
|-------|--------|
| Audit qualité | Nulls, outliers, taux de complétude par table |
| Déduplication | Suppression doublons patients, admissions, médicaments |
| Normalisation | Dates ISO, sexe M/F, codes postaux 5 chiffres |
| Groupement | Tranches d'âge, catégories DMS, niveaux d'occupation |
| Validation | Score qualité global 0–100 |
    """,
)


# ── 1. AUDIT QUALITÉ ──────────────────────────────────────────────────────────

def _audit_qualite(**ctx):
    """Analyse la qualité des tables staging : nulls, doublons, outliers."""
    import pandas as pd
    from db_utils import get_staging_engine

    engine = get_staging_engine()
    rapport = {}

    # Patients
    try:
        df = pd.read_sql("SELECT * FROM stg_patients", engine)
        rapport["stg_patients"] = {
            "total":        len(df),
            "doublons":     df.duplicated(subset=["patient_id"]).sum(),
            "nulls_nom":    df["nom"].isna().sum(),
            "nulls_age":    df["age"].isna().sum(),
            "age_invalide": ((pd.to_numeric(df["age"], errors="coerce") < 0) |
                             (pd.to_numeric(df["age"], errors="coerce") > 120)).sum(),
            "sexe_invalide": (~df["sexe"].str.upper().isin(["M", "F"])).sum(),
        }
    except Exception as e:
        rapport["stg_patients"] = {"erreur": str(e)}

    # Admissions
    try:
        df = pd.read_sql("SELECT * FROM stg_admissions", engine)
        rapport["stg_admissions"] = {
            "total":       len(df),
            "doublons":    df.duplicated(subset=["admission_id"]).sum(),
            "nulls_pid":   df["patient_id"].isna().sum(),
            "nulls_date":  df["date_admission"].isna().sum(),
            "duree_neg":   (pd.to_numeric(df.get("duree_sejour", pd.Series([])),
                             errors="coerce") < 0).sum(),
        }
    except Exception as e:
        rapport["stg_admissions"] = {"erreur": str(e)}

    # Laboratoires
    try:
        df = pd.read_sql("SELECT * FROM stg_laboratoires", engine)
        rapport["stg_laboratoires"] = {
            "total":       len(df),
            "doublons":    df.duplicated(subset=["labo_id"]).sum(),
            "nulls_result": df["resultat"].isna().sum(),
        }
    except Exception as e:
        rapport["stg_laboratoires"] = {"erreur": str(e)}

    # Médicaments
    try:
        df = pd.read_sql("SELECT * FROM stg_medicaments", engine)
        rapport["stg_medicaments"] = {
            "total":       len(df),
            "doublons":    df.duplicated(subset=["prescription_id"]).sum(),
        }
    except Exception as e:
        rapport["stg_medicaments"] = {"erreur": str(e)}

    print("\n  === RAPPORT AUDIT QUALITÉ ===")
    for table, stats in rapport.items():
        print(f"\n  [{table}]")
        for k, v in stats.items():
            flag = " ⚠" if isinstance(v, int) and v > 0 and k != "total" else ""
            print(f"    {k:<20} {v}{flag}")

    ctx["ti"].xcom_push(key="audit_rapport", value=rapport)


# ── 2. DÉDUPLICATION ──────────────────────────────────────────────────────────

def _deduplication(**ctx):
    """Supprime les doublons dans les tables staging (garde le dernier en date)."""
    import pandas as pd
    from sqlalchemy import text
    from db_utils import get_staging_engine

    engine = get_staging_engine()
    stats  = {}

    dedup_config = [
        ("stg_patients",     "patient_id"),
        ("stg_admissions",   "admission_id"),
        ("stg_laboratoires", "labo_id"),
        ("stg_medicaments",  "prescription_id"),
        ("stg_hopitaux",     "hopital_id"),
    ]

    for table, pk in dedup_config:
        try:
            df     = pd.read_sql(f"SELECT * FROM {table}", engine)
            avant  = len(df)
            df     = df.drop_duplicates(subset=[pk], keep="last")
            apres  = len(df)
            retires = avant - apres
            if retires > 0:
                df.to_sql(table, engine, if_exists="replace", index=False)
                print(f"  ✓ {table}: {retires} doublon(s) supprimé(s) ({avant} → {apres})")
            else:
                print(f"  ✓ {table}: aucun doublon ({avant} lignes)")
            stats[table] = {"avant": avant, "apres": apres, "retires": retires}
        except Exception as e:
            print(f"  ⚠ {table}: {e}")
            stats[table] = {"erreur": str(e)}

    ctx["ti"].xcom_push(key="dedup_stats", value=stats)


# ── 3. NORMALISATION ──────────────────────────────────────────────────────────

def _normalisation(**ctx):
    """Homogénéise les formats : dates ISO, sexe M/F, codes postaux."""
    import pandas as pd
    from db_utils import get_staging_engine

    engine = get_staging_engine()

    # ── Patients : sexe et age ────────────────────────────────────────────────
    try:
        df = pd.read_sql("SELECT * FROM stg_patients", engine)
        avant = len(df)

        # Normaliser sexe → M / F majuscule
        df["sexe"] = df["sexe"].str.strip().str.upper()
        df.loc[df["sexe"].isin(["HOMME", "H", "MALE"]),   "sexe"] = "M"
        df.loc[df["sexe"].isin(["FEMME", "FEMALE", "FE"]), "sexe"] = "F"

        # Convertir age en entier, supprimer hors plage
        df["age"] = pd.to_numeric(df["age"], errors="coerce")
        invalides  = df[(df["age"] < 0) | (df["age"] > 120)].shape[0]
        df = df[(df["age"] >= 0) & (df["age"] <= 120) | df["age"].isna()]

        # Dates naissance ISO
        if "date_naissance" in df.columns:
            df["date_naissance"] = pd.to_datetime(
                df["date_naissance"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        df.to_sql("stg_patients", engine, if_exists="replace", index=False)
        print(f"  ✓ stg_patients normalisé: {invalides} âges hors plage supprimés")
    except Exception as e:
        print(f"  ⚠ Normalisation patients: {e}")

    # ── Admissions : dates ISO ────────────────────────────────────────────────
    try:
        df = pd.read_sql("SELECT * FROM stg_admissions", engine)
        for col in ["date_admission", "date_sortie"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
        df["duree_sejour"] = pd.to_numeric(df.get("duree_sejour"), errors="coerce").fillna(0).astype(int)
        df.to_sql("stg_admissions", engine, if_exists="replace", index=False)
        print("  ✓ stg_admissions: dates normalisées en ISO")
    except Exception as e:
        print(f"  ⚠ Normalisation admissions: {e}")

    # ── Hôpitaux : code postal 5 chiffres ────────────────────────────────────
    try:
        df = pd.read_sql("SELECT * FROM stg_hopitaux", engine)
        if "code_postal" in df.columns:
            df["code_postal"] = (
                df["code_postal"].astype(str).str.strip().str.zfill(5).str[:5]
            )
        df.to_sql("stg_hopitaux", engine, if_exists="replace", index=False)
        print("  ✓ stg_hopitaux: codes postaux normalisés")
    except Exception as e:
        print(f"  ⚠ Normalisation hôpitaux: {e}")

    print("  ✓ Normalisation terminée")


# ── 4. GROUPEMENT ─────────────────────────────────────────────────────────────

def _groupement(**ctx):
    """
    Calcule des colonnes de groupement sur le staging :
      - tranche_age (patients)
      - categorie_dms (admissions : courte / moyenne / longue)
      - niveau_occupation (capteurs : faible / normal / critique)
    """
    import pandas as pd
    from db_utils import get_staging_engine

    engine = get_staging_engine()

    # ── Patients → tranche_age ────────────────────────────────────────────────
    try:
        df = pd.read_sql("SELECT * FROM stg_patients", engine)
        age = pd.to_numeric(df["age"], errors="coerce")
        bins   = [0, 14, 29, 44, 59, 74, 89, 120]
        labels = ["0-14", "15-29", "30-44", "45-59", "60-74", "75-89", "90+"]
        df["tranche_age"] = pd.cut(age, bins=bins, labels=labels, right=True)
        df["tranche_age"] = df["tranche_age"].astype(str)
        df.to_sql("stg_patients", engine, if_exists="replace", index=False)
        dist = df["tranche_age"].value_counts().to_dict()
        print(f"  ✓ Tranches d'âge calculées : {dist}")
    except Exception as e:
        print(f"  ⚠ Groupement patients: {e}")

    # ── Admissions → categorie_dms ────────────────────────────────────────────
    try:
        df  = pd.read_sql("SELECT * FROM stg_admissions", engine)
        dms = pd.to_numeric(df.get("duree_sejour", pd.Series([])), errors="coerce")
        if not dms.empty:
            conditions = [dms <= 3, dms <= 7, dms > 7]
            choix      = ["Courte (<= 3j)", "Moyenne (4-7j)", "Longue (> 7j)"]
            import numpy as np
            df["categorie_dms"] = np.select(conditions, choix, default="Inconnue")
            df.to_sql("stg_admissions", engine, if_exists="replace", index=False)
            print(f"  ✓ Catégories DMS : {df['categorie_dms'].value_counts().to_dict()}")
    except Exception as e:
        print(f"  ⚠ Groupement admissions: {e}")

    # ── Capteurs → niveau_occupation ─────────────────────────────────────────
    try:
        df = pd.read_sql("SELECT * FROM stg_capteurs_lits", engine)
        taux = pd.to_numeric(df.get("taux_occupation", pd.Series([])), errors="coerce")
        if not taux.empty:
            import numpy as np
            df["niveau_occupation"] = np.select(
                [taux < 60, taux < 85, taux >= 85],
                ["Faible", "Normal", "Critique"],
                default="Inconnu"
            )
            df.to_sql("stg_capteurs_lits", engine, if_exists="replace", index=False)
            print(f"  ✓ Niveaux occupation: {df['niveau_occupation'].value_counts().to_dict()}")
    except Exception as e:
        print(f"  ⚠ Groupement capteurs: {e}")


# ── 5. VALIDATION FINALE ──────────────────────────────────────────────────────

def _validation_finale(**ctx):
    """Calcule un score qualité global 0–100 et affiche le rapport de synthèse."""
    import pandas as pd
    from db_utils import get_staging_engine, log_etl

    engine = get_staging_engine()
    audit  = ctx["ti"].xcom_pull(key="audit_rapport", task_ids="audit_qualite") or {}
    dedup  = ctx["ti"].xcom_pull(key="dedup_stats",   task_ids="deduplication")  or {}

    total_lignes    = 0
    total_doublons  = 0
    total_nulls     = 0
    tables_ok       = 0

    for table, stats in audit.items():
        if "erreur" not in stats:
            tables_ok      += 1
            total_lignes   += stats.get("total", 0)
            total_doublons += stats.get("doublons", 0)
            for k, v in stats.items():
                if k.startswith("nulls_") and isinstance(v, int):
                    total_nulls += v

    # Score = 100 - malus doublons - malus nulls
    score = 100
    if total_lignes > 0:
        score -= min(20, round(total_doublons / max(total_lignes, 1) * 100))
        score -= min(30, round(total_nulls    / max(total_lignes, 1) * 100))

    niveau = "EXCELLENT" if score >= 90 else "BON" if score >= 70 else "MOYEN" if score >= 50 else "FAIBLE"

    print("\n  ╔══════════════════════════════════════╗")
    print(f"  ║  SCORE QUALITÉ DONNÉES : {score:3d}/100     ║")
    print(f"  ║  Niveau : {niveau:<28}║")
    print("  ╠══════════════════════════════════════╣")
    print(f"  ║  Tables analysées   : {tables_ok:<15}║")
    print(f"  ║  Total lignes       : {total_lignes:<15,}║")
    print(f"  ║  Doublons supprimés : {total_doublons:<15}║")
    print(f"  ║  Valeurs nulles     : {total_nulls:<15}║")
    print("  ╚══════════════════════════════════════╝\n")

    log_etl(engine, "nettoyage_groupement", "validation_finale",
            "SUCCESS", total_lignes,
            source=f"score_qualite={score}")

    if score < 50:
        raise ValueError(f"Score qualité trop faible ({score}/100) — vérifiez les sources")


# ── Task wiring ───────────────────────────────────────────────────────────────

t_audit    = PythonOperator(task_id="audit_qualite",    python_callable=_audit_qualite,    dag=dag)
t_dedup    = PythonOperator(task_id="deduplication",    python_callable=_deduplication,    dag=dag)
t_norm     = PythonOperator(task_id="normalisation",    python_callable=_normalisation,    dag=dag)
t_group    = PythonOperator(task_id="groupement",       python_callable=_groupement,       dag=dag)
t_validate = PythonOperator(task_id="validation_finale",python_callable=_validation_finale,dag=dag)

t_audit >> t_dedup >> t_norm >> t_group >> t_validate
