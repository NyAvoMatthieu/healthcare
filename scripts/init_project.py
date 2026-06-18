"""
Script d'initialisation complet du projet Healthcare Analytics Platform.
Lance dans l'ordre : génération données → staging → warehouse → vérification.

Run: python scripts/init_project.py
"""
import sys
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def step(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print("\n  Healthcare Analytics Platform — Initialisation\n")

    # 1. Génération des données CSV
    step("1/4  Génération des données CSV")
    import generate_data
    generate_data.gen_regions()
    generate_data.gen_hopitaux()
    generate_data.gen_services()
    generate_data.gen_maladies()
    pids = generate_data.gen_patients(100)
    adms = generate_data.gen_admissions(pids, 500)
    generate_data.gen_sorties(adms)
    generate_data.gen_laboratoires(pids, 1000)
    generate_data.gen_medicaments(pids, 500)

    # 2. Initialisation du staging
    step("2/4  Initialisation + Chargement Staging")
    from db_utils import init_staging
    init_staging()
    import extract_csv
    total_staging = extract_csv.run_all()
    print(f"\n  → {total_staging} lignes dans le staging")

    # 3. Initialisation du warehouse
    step("3/4  Transformation → Data Warehouse")
    import transform
    total_wh = transform.run_all()
    print(f"\n  → {total_wh} lignes dans le warehouse")

    # 4. Vérification
    step("4/4  Vérification du Data Warehouse")
    import pandas as pd
    from db_utils import get_warehouse_engine
    wh = get_warehouse_engine()
    tables = [
        "dim_patient", "dim_temps", "dim_hopital", "dim_service",
        "dim_region",  "dim_maladie",
        "fact_admissions", "fact_urgences", "fact_laboratoires", "fact_prescriptions",
    ]
    print(f"\n  {'Table':<28} {'Lignes':>8}")
    print(f"  {'-'*38}")
    for t in tables:
        try:
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", wh).iloc[0]["n"]
            print(f"  {t:<28} {n:>8,}")
        except Exception as e:
            print(f"  {t:<28}    ERREUR: {e}")

    print("\n  ✓ Projet initialisé avec succès!")
    print(f"\n  Staging  : {BASE_DIR / 'staging/staging.db'}")
    print(f"  Warehouse: {BASE_DIR / 'warehouse/warehouse.db'}")
    print(f"\n  Prochaine étape :")
    print(f"    python api/mock_api.py       # Démarrer l'API (optionnel)")
    print(f"    airflow standalone           # Démarrer Airflow")


if __name__ == "__main__":
    main()
