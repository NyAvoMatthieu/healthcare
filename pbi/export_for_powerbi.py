"""
export_for_powerbi.py
Exporte toutes les tables du Data Warehouse en un fichier Excel multi-onglets
optimisé pour Power BI Desktop.

Usage :
    python pbi/export_for_powerbi.py
    python pbi/export_for_powerbi.py --out pbi/healthcare_powerbi.xlsx

Produit : pbi/healthcare_powerbi.xlsx  (< 10 Mo en général)
"""
import sys
import types
import argparse
from pathlib import Path
from datetime import datetime

# Stub lxml — incompatible avec Python 3.13 (SystemError UnicodeDecodeError)
# openpyxl tente de l'importer ; on injecte un module factice pour l'éviter.
if "lxml.etree" not in sys.modules:
    _lxml = types.ModuleType("lxml")
    _lxml_etree = types.ModuleType("lxml.etree")
    _lxml_etree.LXML_VERSION = (0, 0, 0, 0)
    sys.modules.setdefault("lxml", _lxml)
    sys.modules["lxml.etree"] = _lxml_etree

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

import pandas as pd
from db_utils import get_warehouse_engine, get_staging_engine


# Tables à exporter et leur source
WAREHOUSE_TABLES = [
    # Dimensions
    "dim_patient",
    "dim_hopital",
    "dim_maladie",
    "dim_region",
    "dim_temps",
    "dim_service",
    # Faits
    "fact_admissions",
    "fact_urgences",
    "fact_laboratoires",
    "fact_prescriptions",
    "fact_occupation_lits",
    "fact_stock_pharmacie",
    # Mart consolidé
    "analytics_mart",
    "kpi_cache",
]

# Colonnes à exclure de l'export (trop techniques pour PBI)
EXCLUDE_COLS = {"__pycache__"}


def load_table(engine, table: str) -> pd.DataFrame | None:
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
        return df
    except Exception as e:
        print(f"  ⚠ {table}: {e}")
        return None


def clean_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit les colonnes booléennes et nettoie les types pour Excel."""
    for col in df.columns:
        if df[col].dtype == object:
            # Tronquer les textes très longs
            df[col] = df[col].astype(str).str[:32767]
        elif str(df[col].dtype) == "bool":
            df[col] = df[col].astype(int)
    return df


def export(out_path: Path):
    wh      = get_warehouse_engine()
    staging = get_staging_engine()

    print(f"\n  Healthcare Analytics — Export Power BI")
    print(f"  Destination : {out_path}\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    exported = {}
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:

        for table in WAREHOUSE_TABLES:
            df = load_table(wh, table)
            if df is None or df.empty:
                print(f"  ○ {table:<30} (vide ou absente)")
                continue

            df = clean_for_excel(df)
            # Nom d'onglet max 31 caractères (limite Excel)
            sheet_name = table[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            exported[table] = len(df)
            print(f"  ✓ {table:<30} {len(df):>8,} lignes")

        # Feuille de métadonnées
        meta = pd.DataFrame([
            {"info": "Projet",      "valeur": "Healthcare Analytics Platform"},
            {"info": "Export",      "valeur": datetime.now().strftime("%Y-%m-%d %H:%M")},
            {"info": "Source",      "valeur": str(BASE_DIR / "warehouse" / "warehouse.db")},
            {"info": "Tables",      "valeur": str(len(exported))},
            {"info": "Total lignes","valeur": str(sum(exported.values()))},
        ])
        meta.to_excel(writer, sheet_name="_Metadonnees", index=False)

    size_kb = out_path.stat().st_size // 1024
    print(f"\n  ✓ Export terminé : {out_path.name}  ({size_kb} Ko)")
    print(f"  ✓ {len(exported)} tables exportées — {sum(exported.values()):,} lignes total")
    print(f"\n  → Ouvrez Power BI Desktop")
    print(f"  → Accueil > Obtenir les données > Excel")
    print(f"  → Sélectionnez : {out_path}")
    print(f"  → Cochez toutes les feuilles et cliquez Charger\n")

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", default=str(BASE_DIR / "pbi" / "healthcare_powerbi.xlsx"),
        help="Chemin du fichier Excel de sortie"
    )
    args = parser.parse_args()
    export(Path(args.out))
