"""
Extrait comptes_rendus.xml (format HL7-like) → staging SQLite.
Utilise lxml pour le parsing XPath.
"""
import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from sqlalchemy import text

from db_utils import get_staging_engine, log_etl

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DAG_NAME = "ingestion_multi_format"
FILE     = DATA_DIR / "comptes_rendus.xml"
NS_URI   = "urn:healthcare-analytics:cda"
NS       = {"ns": NS_URI}


def _tag(name: str) -> str:
    return f"{{{NS_URI}}}{name}"


def _text(el, tag) -> str | None:
    node = el.find(_tag(tag))
    return node.text.strip() if node is not None and node.text else None


def extract_comptes_rendus(engine) -> int:
    if not FILE.exists():
        raise FileNotFoundError(f"{FILE} introuvable — lancez generate_xml.py d'abord")

    tree = ET.parse(str(FILE))
    root = tree.getroot()

    rows       = []
    rows_actes = []

    for cr in root.findall(_tag("compte_rendu")):
        cr_id      = cr.get("id")
        diag_el    = cr.find(_tag("diagnostic_principal"))
        code_cim10 = diag_el.get("code_cim10") if diag_el is not None else None
        diag_txt   = diag_el.text if diag_el is not None else None

        # Actes médicaux → table séparée
        actes_container = cr.find(_tag("actes_medicaux"))
        if actes_container is not None:
            for acte in actes_container.findall(_tag("acte")):
                rows_actes.append({
                    "cr_id":       cr_id,
                    "code_acte":   acte.get("code"),
                    "libelle_acte": acte.text,
                    "loaded_at":   datetime.datetime.utcnow().isoformat(),
                })

        # Diagnostics secondaires concaténés
        sec_container = cr.find(_tag("diagnostics_secondaires"))
        sec = []
        if sec_container is not None:
            sec = [f"{d.get('code_cim10')}:{d.text}"
                   for d in sec_container.findall(_tag("diagnostic"))]

        rows.append({
            "cr_id":               cr_id,
            "admission_id":        _text(cr, "admission_id"),
            "patient_id":          _text(cr, "patient_id"),
            "hopital_id":          _text(cr, "hopital_id"),
            "medecin_responsable": _text(cr, "medecin_responsable"),
            "date_admission":      _text(cr, "date_admission"),
            "date_sortie":         _text(cr, "date_sortie"),
            "duree_sejour":        _text(cr, "duree_sejour"),
            "code_cim10":          code_cim10,
            "diagnostic_principal": diag_txt,
            "diagnostics_secondaires": "|".join(sec),
            "mode_entree":         _text(cr, "mode_entree"),
            "mode_sortie":         _text(cr, "mode_sortie"),
            "observations":        _text(cr.find(_tag("observations")) or cr, "texte"),
            "nb_actes":            len(rows_actes),
            "source_file":         "comptes_rendus.xml",
            "loaded_at":           datetime.datetime.utcnow().isoformat(),
        })

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stg_comptes_rendus"))
        conn.execute(text("DELETE FROM stg_actes_medicaux"))
        conn.commit()

    import pandas as pd
    pd.DataFrame(rows).to_sql("stg_comptes_rendus", engine, if_exists="append", index=False)
    pd.DataFrame(rows_actes).to_sql("stg_actes_medicaux", engine, if_exists="append", index=False)
    return len(rows)


def run_all(engine=None):
    engine = engine or get_staging_engine()
    try:
        n = extract_comptes_rendus(engine)
        log_etl(engine, DAG_NAME, "extract_xml_comptes_rendus", "SUCCESS", n, source="xml")
        print(f"  ✓ XML comptes_rendus: {n} documents")
        return n
    except Exception as e:
        log_etl(engine, DAG_NAME, "extract_xml_comptes_rendus", "FAILED", error=str(e))
        print(f"  ✗ XML: {e}")
        return 0


if __name__ == "__main__":
    print("Extraction XML → Staging...")
    n = run_all()
    print(f"\n✓ {n} comptes-rendus XML chargés dans le staging")
