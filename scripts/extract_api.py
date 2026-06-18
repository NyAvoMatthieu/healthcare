"""
Extract data from the mock public health REST API into SQLite staging.
"""
import datetime
import time

import requests
from sqlalchemy import text

from db_utils import get_staging_engine, init_staging, log_etl, load_config

DAG_NAME = "ingestion_api_maladies"


def _api_get(endpoint: str, cfg: dict) -> list | dict | None:
    url     = cfg["api"]["base_url"].rstrip("/") + "/" + endpoint.lstrip("/")
    timeout = cfg["api"].get("timeout", 30)
    retries = cfg["api"].get("retry_attempts", 3)
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"API {url} inaccessible après {retries} tentatives: {e}")


def check_api(cfg: dict) -> bool:
    try:
        _api_get("/health", cfg)
        return True
    except Exception as e:
        print(f"  API non disponible: {e}")
        return False


def extract_maladies(engine, cfg: dict) -> int:
    data = _api_get("/maladies", cfg)
    rows = data if isinstance(data, list) else data.get("data", [])
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_api_maladies WHERE source_api='mock_api'"))
        for r in rows:
            conn.execute(text(
                """INSERT INTO stg_api_maladies
                   (maladie_id, nom_maladie, code_cim10, categorie, gravite,
                    taux_incidence, est_chronique, source_api, loaded_at)
                   VALUES (:id,:nom,:cim,:cat,:grav,:ti,:chron,'mock_api',:ts)"""
            ), {"id": r.get("maladie_id"), "nom": r.get("nom"),
                "cim": r.get("code_cim10"), "cat": r.get("categorie"),
                "grav": r.get("gravite"), "ti": r.get("taux_incidence"),
                "chron": r.get("est_chronique", 0),
                "ts": datetime.datetime.utcnow().isoformat()})
        conn.commit()
    return len(rows)


def extract_epidemies(engine, cfg: dict) -> int:
    data = _api_get("/epidemies", cfg)
    rows = data if isinstance(data, list) else data.get("data", [])
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_api_epidemies WHERE source_api='mock_api'"))
        for r in rows:
            conn.execute(text(
                """INSERT INTO stg_api_epidemies
                   (epidemie_id, maladie, region, nb_cas, date_debut,
                    date_fin, statut, source_api, loaded_at)
                   VALUES (:id,:mal,:reg,:cas,:dd,:df,:st,'mock_api',:ts)"""
            ), {"id": r.get("id"), "mal": r.get("maladie"),
                "reg": r.get("region"), "cas": r.get("nb_cas"),
                "dd": r.get("date_debut"), "df": r.get("date_fin"),
                "st": r.get("statut"),
                "ts": datetime.datetime.utcnow().isoformat()})
        conn.commit()
    return len(rows)


def extract_regions(engine, cfg: dict) -> int:
    data = _api_get("/regions", cfg)
    rows = data if isinstance(data, list) else data.get("data", [])
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_api_regions WHERE source_api='mock_api'"))
        for r in rows:
            conn.execute(text(
                """INSERT INTO stg_api_regions
                   (region_id, nom_region, population, nb_medecins,
                    nb_hopitaux, taux_mortalite, source_api, loaded_at)
                   VALUES (:id,:nom,:pop,:med,:hop,:tm,'mock_api',:ts)"""
            ), {"id": r.get("region_id"), "nom": r.get("nom_region"),
                "pop": r.get("population"), "med": r.get("nb_medecins"),
                "hop": r.get("nb_hopitaux"), "tm": r.get("taux_mortalite"),
                "ts": datetime.datetime.utcnow().isoformat()})
        conn.commit()
    return len(rows)


def run_all():
    init_staging()
    engine = get_staging_engine()
    cfg    = load_config()
    if not check_api(cfg):
        log_etl(engine, DAG_NAME, "check_api", "FAILED",
                error="API non disponible", source="mock_api")
        return 0
    total  = 0
    steps  = [
        ("maladies",  extract_maladies),
        ("epidemies", extract_epidemies),
        ("regions",   extract_regions),
    ]
    for name, fn in steps:
        try:
            n = fn(engine, cfg)
            log_etl(engine, DAG_NAME, f"extract_{name}", "SUCCESS", n, source="mock_api")
            print(f"  ✓ api.{name}: {n} lignes")
            total += n
        except Exception as e:
            log_etl(engine, DAG_NAME, f"extract_{name}", "FAILED",
                    error=str(e), source="mock_api")
            print(f"  ✗ api.{name}: {e}")
    return total


if __name__ == "__main__":
    print("Extraction API → Staging...")
    total = run_all()
    print(f"\n✓ Total: {total} lignes chargées depuis l'API")
