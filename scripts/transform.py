"""
Transform staging data into Data Warehouse star schema dimensions and facts.
"""
import datetime
import random
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_utils import (get_staging_engine, get_warehouse_engine,
                      init_warehouse, log_etl)

random.seed(42)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DAG_NAME = "transform"


# ── Dimension transformations ─────────────────────────────────────────────────

def transform_dim_region(staging, wh):
    # Priority: API data, fallback CSV
    df = pd.read_sql("SELECT * FROM stg_api_regions", staging)
    if df.empty:
        csv = DATA_DIR / "regions.csv"
        if csv.exists():
            df = pd.read_csv(csv, dtype=str)
    if df.empty:
        return 0

    df = df.rename(columns={
        "region_id": "region_id", "nom_region": "nom_region",
        "population": "population", "superficie": "superficie",
        "chef_lieu": "chef_lieu",
    })
    for col in ["population", "superficie"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "chef_lieu" not in df.columns:
        df["chef_lieu"] = None

    out = df[["region_id", "nom_region", "population", "superficie", "chef_lieu"]].drop_duplicates("region_id")
    out.to_sql("dim_region", wh, if_exists="replace", index=False)
    return len(out)


def transform_dim_hopital(staging, wh):
    df = pd.read_sql("SELECT * FROM stg_hopitaux", staging)
    if df.empty:
        csv = DATA_DIR / "hopitaux.csv"
        if csv.exists():
            df = pd.read_csv(csv, dtype=str)
    if df.empty:
        return 0

    df["capacite_lits"] = pd.to_numeric(df.get("capacite_lits", 0), errors="coerce").fillna(200)
    df["nb_medecins"]   = pd.to_numeric(df.get("nb_medecins", 0),   errors="coerce").fillna(50)
    out = df[["hopital_id","nom","ville","region_id","capacite_lits","type","nb_medecins"]].drop_duplicates("hopital_id")
    out.to_sql("dim_hopital", wh, if_exists="replace", index=False)
    return len(out)


def transform_dim_service(staging, wh):
    csv = DATA_DIR / "services.csv"
    if not csv.exists():
        return 0
    df  = pd.read_csv(csv, dtype=str)
    df["nb_lits"] = pd.to_numeric(df.get("nb_lits", 20), errors="coerce").fillna(20)
    out = df[["service_id","nom_service","departement","specialite","nb_lits"]].drop_duplicates("service_id")
    out.to_sql("dim_service", wh, if_exists="replace", index=False)
    return len(out)


def transform_dim_maladie(staging, wh):
    df = pd.read_sql("SELECT * FROM stg_api_maladies", staging)
    if df.empty:
        csv = DATA_DIR / "maladies.csv"
        if csv.exists():
            df = pd.read_csv(csv, dtype=str)
    if df.empty:
        return 0

    df = df.rename(columns={"nom": "nom_maladie"}) if "nom" in df.columns else df
    df["gravite"]     = pd.to_numeric(df.get("gravite",     3), errors="coerce").fillna(3)
    df["est_chronique"] = pd.to_numeric(df.get("est_chronique", 0), errors="coerce").fillna(0)
    cols = ["maladie_id","nom_maladie","code_cim10","categorie","gravite","est_chronique"]
    out  = df[[c for c in cols if c in df.columns]].drop_duplicates("maladie_id")
    out.to_sql("dim_maladie", wh, if_exists="replace", index=False)
    return len(out)


def transform_dim_patient(staging, wh):
    df = pd.read_sql("SELECT * FROM stg_patients", staging)
    if df.empty:
        return 0

    def age_grp(age):
        try:
            a = int(age)
            if a < 18:  return "0-17"
            if a < 31:  return "18-30"
            if a < 51:  return "31-50"
            if a < 66:  return "51-65"
            return "65+"
        except Exception:
            return "31-50"

    # Map region name → region_id
    regions_csv = DATA_DIR / "regions.csv"
    region_map  = {}
    if regions_csv.exists():
        r_df = pd.read_csv(regions_csv, dtype=str)
        region_map = dict(zip(r_df["nom_region"], r_df["region_id"]))

    df["tranche_age"] = df["age"].apply(age_grp)
    df["region_id"]   = df["region"].map(region_map).fillna("R01")
    df["age"]         = pd.to_numeric(df["age"], errors="coerce")

    # Garder toutes les colonnes utiles pour l'analyse
    keep = ["patient_id", "nom", "prenom", "date_naissance", "age",
            "sexe", "tranche_age", "region_id"]
    keep = [c for c in keep if c in df.columns]
    out = df[keep].drop_duplicates("patient_id")
    out.to_sql("dim_patient", wh, if_exists="replace", index=False)
    return len(out)


def transform_dim_temps(wh, start_year=2022, end_year=2026):
    import calendar
    MOIS_FR = ["Janvier","Février","Mars","Avril","Mai","Juin",
               "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

    rows, tid = [], 1
    d = datetime.date(start_year, 1, 1)
    end = datetime.date(end_year, 12, 31)
    while d <= end:
        rows.append({
            "temps_id":     tid,
            "date":         d.isoformat(),
            "jour":         d.day,
            "mois":         d.month,
            "annee":        d.year,
            "trimestre":    (d.month - 1) // 3 + 1,
            "semaine":      d.isocalendar()[1],
            "jour_semaine": JOURS_FR[d.weekday()],
            "est_weekend":  1 if d.weekday() >= 5 else 0,
            "nom_mois":     MOIS_FR[d.month - 1],
        })
        d  += datetime.timedelta(days=1)
        tid += 1
    df = pd.DataFrame(rows)
    df.to_sql("dim_temps", wh, if_exists="replace", index=False)
    return len(df)


# ── Fact transformations ──────────────────────────────────────────────────────

def transform_fact_admissions(staging, wh):
    adm = pd.read_sql("SELECT * FROM stg_admissions", staging)
    sor = pd.read_sql("SELECT * FROM stg_sorties",    staging)
    if adm.empty:
        return 0

    # Merge with sorties to compute duree_sejour
    merged = adm.merge(sor[["admission_id","date_sortie"]], on="admission_id", how="left")

    def sejour_days(row):
        try:
            d1 = datetime.date.fromisoformat(str(row["date_admission"])[:10])
            d2 = datetime.date.fromisoformat(str(row["date_sortie"])[:10])
            return max(1, (d2 - d1).days)
        except Exception:
            return random.randint(1, 10)

    merged["duree_sejour"] = merged.apply(sejour_days, axis=1)

    # Join with dim_temps to get temps_id
    temps = pd.read_sql("SELECT temps_id, date FROM dim_temps", wh)
    temps["date"] = pd.to_datetime(temps["date"]).dt.date.astype(str)
    merged["date_key"] = merged["date_admission"].astype(str).str[:10]
    merged = merged.merge(temps.rename(columns={"date":"date_key"}), on="date_key", how="left")

    # Coerce hopital / service / maladie ids
    for col in ["hopital_id","service_id","maladie_id"]:
        if col not in merged.columns:
            merged[col] = None

    merged["est_urgence"]        = pd.to_numeric(merged.get("urgence", 0), errors="coerce").fillna(0).astype(int)
    merged["mode_admission"]     = merged["est_urgence"].map({1: "Urgence", 0: "Programmée"})
    merged["est_readmission"]    = 0
    merged["nb_lits_utilises"]   = 1
    merged["cout_hospitalisation"] = merged["duree_sejour"] * random.randint(200, 800)
    merged["cout_sejour"]        = merged["cout_hospitalisation"]
    merged["mode_sortie"]        = "Domicile"
    merged["service"]            = merged.get("service", pd.Series(["Médecine générale"] * len(merged)))

    out = merged[[
        "admission_id","patient_id","temps_id","hopital_id",
        "service_id","maladie_id","duree_sejour","est_urgence",
        "mode_admission","mode_sortie","service",
        "nb_lits_utilises","cout_hospitalisation","cout_sejour","est_readmission"
    ]].drop_duplicates("admission_id").dropna(subset=["temps_id"])
    out["temps_id"] = out["temps_id"].astype(int)
    out.to_sql("fact_admissions", wh, if_exists="replace", index=False)
    return len(out)


def transform_fact_urgences(staging, wh):
    adm = pd.read_sql("SELECT * FROM stg_admissions WHERE urgence='1' OR urgence=1", staging)
    if adm.empty:
        return 0

    temps = pd.read_sql("SELECT temps_id, date FROM dim_temps", wh)
    temps["date"] = pd.to_datetime(temps["date"]).dt.date.astype(str)
    adm["date_key"] = adm["date_admission"].astype(str).str[:10]
    adm = adm.merge(temps.rename(columns={"date":"date_key"}), on="date_key", how="left")

    adm["urgence_id"]            = adm["admission_id"].apply(lambda x: f"URG-{x}")
    adm["temps_attente_minutes"] = [random.randint(15, 240) for _ in range(len(adm))]
    adm["niveau_urgence"]        = [random.randint(1, 5)    for _ in range(len(adm))]
    adm["disposition"]           = random.choices(
        ["Hospitalisé","Renvoyé","Transféré","DAMA"], weights=[60,30,7,3], k=len(adm))
    adm["est_hospitalise"]       = (adm["disposition"] == "Hospitalisé").astype(int)
    adm["duree_prise_en_charge"] = adm["temps_attente_minutes"] + random.randint(30, 120)

    out = adm[[
        "urgence_id","patient_id","temps_id","hopital_id",
        "temps_attente_minutes","niveau_urgence","disposition",
        "est_hospitalise","duree_prise_en_charge"
    ]].dropna(subset=["temps_id"])
    out["temps_id"] = out["temps_id"].astype(int)
    out.to_sql("fact_urgences", wh, if_exists="replace", index=False)
    return len(out)


def transform_fact_laboratoires(staging, wh):
    df = pd.read_sql("SELECT * FROM stg_laboratoires", staging)
    if df.empty:
        return 0

    temps = pd.read_sql("SELECT temps_id, date FROM dim_temps", wh)
    temps["date"] = pd.to_datetime(temps["date"]).dt.date.astype(str)
    df["date_key"] = df["date_test"].astype(str).str[:10]
    df = df.merge(temps.rename(columns={"date":"date_key"}), on="date_key", how="left")

    df["hopital_id"]        = [f"H{random.randint(1,20):02d}" for _ in range(len(df))]
    df["resultat_numerique"] = pd.to_numeric(df.get("resultat",0), errors="coerce")
    df["est_anormal"]        = pd.to_numeric(df.get("est_anormal",0), errors="coerce").fillna(0).astype(int)
    df["valeur_ref_min"]     = pd.to_numeric(df.get("valeur_ref_min"), errors="coerce")
    df["valeur_ref_max"]     = pd.to_numeric(df.get("valeur_ref_max"), errors="coerce")

    out = df[[
        "labo_id","patient_id","temps_id","hopital_id",
        "type_test","resultat_numerique","unite","est_anormal",
        "valeur_ref_min","valeur_ref_max"
    ]].dropna(subset=["temps_id"])
    out["temps_id"] = out["temps_id"].astype(int)
    out.to_sql("fact_laboratoires", wh, if_exists="replace", index=False)
    return len(out)


def transform_fact_prescriptions(staging, wh):
    df = pd.read_sql("SELECT * FROM stg_medicaments", staging)
    if df.empty:
        return 0

    temps = pd.read_sql("SELECT temps_id, date FROM dim_temps", wh)
    temps["date"] = pd.to_datetime(temps["date"]).dt.date.astype(str)
    df["date_key"] = df["date_prescription"].astype(str).str[:10]
    df = df.merge(temps.rename(columns={"date":"date_key"}), on="date_key", how="left")

    df["hopital_id"]  = [f"H{random.randint(1,20):02d}" for _ in range(len(df))]
    df["service_id"]  = [f"S{random.randint(1,15):02d}" for _ in range(len(df))]
    df["duree_jours"] = pd.to_numeric(df.get("duree_jours",7), errors="coerce").fillna(7).astype(int)
    df["est_chronique"] = pd.to_numeric(df.get("est_chronique",0), errors="coerce").fillna(0).astype(int)

    out = df[[
        "prescription_id","patient_id","temps_id","hopital_id",
        "service_id","medicament","dosage","duree_jours","est_chronique"
    ]].dropna(subset=["temps_id"])
    out["temps_id"] = out["temps_id"].astype(int)
    out.to_sql("fact_prescriptions", wh, if_exists="replace", index=False)
    return len(out)


# ── Entry point ───────────────────────────────────────────────────────────────

def run_all():
    init_warehouse()
    staging = get_staging_engine()
    wh      = get_warehouse_engine()

    steps = [
        ("dim_region",            lambda: transform_dim_region(staging, wh)),
        ("dim_hopital",           lambda: transform_dim_hopital(staging, wh)),
        ("dim_service",           lambda: transform_dim_service(staging, wh)),
        ("dim_maladie",           lambda: transform_dim_maladie(staging, wh)),
        ("dim_patient",           lambda: transform_dim_patient(staging, wh)),
        ("dim_temps",             lambda: transform_dim_temps(wh)),
        ("fact_admissions",       lambda: transform_fact_admissions(staging, wh)),
        ("fact_urgences",         lambda: transform_fact_urgences(staging, wh)),
        ("fact_laboratoires",     lambda: transform_fact_laboratoires(staging, wh)),
        ("fact_prescriptions",    lambda: transform_fact_prescriptions(staging, wh)),
    ]
    total = 0
    for name, fn in steps:
        try:
            n = fn()
            log_etl(staging, DAG_NAME, name, "SUCCESS", n)
            print(f"  ✓ {name}: {n} lignes")
            total += n
        except Exception as e:
            log_etl(staging, DAG_NAME, name, "FAILED", error=str(e))
            print(f"  ✗ {name}: {e}")
    return total


if __name__ == "__main__":
    print("Transformation Staging → Data Warehouse...")
    total = run_all()
    print(f"\n✓ Total: {total} lignes chargées dans le warehouse")
