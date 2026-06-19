"""
Génère data/comptes_rendus.xml — comptes-rendus d'hospitalisation au format
inspiré HL7 CDA (Clinical Document Architecture), source typique des SIH.

Chaque <compte_rendu> correspond à une admission avec :
  - diagnostic principal (code CIM-10)
  - actes médicaux réalisés
  - informations de sortie
"""
import random
from datetime import date, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

from faker import Faker

fake = Faker("fr_FR")
random.seed(42)
Faker.seed(42)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DIAGNOSTICS = [
    ("I21","Infarctus du myocarde"),("I63","AVC ischémique"),
    ("J18","Pneumonie bactérienne"),("E11","Diabète type 2"),
    ("K35","Appendicite aiguë"),("I50","Insuffisance cardiaque"),
    ("J44","BPCO exacerbée"),("A41","Sepsis"),("N23","Colique néphrétique"),
    ("M54","Lombalgie aiguë"),("F32","Épisode dépressif majeur"),
    ("C34","Cancer bronchique"),("I10","HTA maligne"),("U07","COVID-19"),
    ("S72","Fracture col fémur"),
]
ACTES = [
    ("YYYY001","Coronarographie"),("YYYY002","Appendicectomie"),
    ("YYYY003","IRM cérébrale"),("YYYY004","Scanner thoracique"),
    ("YYYY005","Endoscopie digestive"),("YYYY006","Échographie cardiaque"),
    ("YYYY007","Biopsie pulmonaire"),("YYYY008","Pose de pace-maker"),
    ("YYYY009","Dialyse"),("YYYY010","Transfusion sanguine"),
    ("YYYY011","Ponction lombaire"),("YYYY012","Arthroscopie genou"),
]
MODES_ENTREE  = ["Urgences","Consultation","Transfert","Programmé"]
MODES_SORTIE  = ["Domicile","EHPAD","Transfert","Décès","HAD"]
MEDECINS = [f"MED{i:03d}" for i in range(1, 61)]


def _admission_ids():
    """Charge les admission_id du CSV si disponible, sinon génère."""
    csv = DATA_DIR / "admissions.csv"
    if csv.exists():
        import csv as csvlib
        with open(csv, encoding="utf-8") as f:
            reader = csvlib.DictReader(f)
            return [row["admission_id"] for row in reader]
    return [f"A{i:05d}" for i in range(1, 301)]


def gen_xml():
    admission_ids = _admission_ids()
    sample = random.sample(admission_ids, min(300, len(admission_ids)))

    root = Element("comptes_rendus_hospitalisation")
    root.set("version", "1.0")
    root.set("xmlns", "urn:healthcare-analytics:cda")
    root.set("date_export", date.today().isoformat())

    start = date(2023, 1, 1)

    for i, aid in enumerate(sample, 1):
        cr = SubElement(root, "compte_rendu")
        cr.set("id", f"CR{i:04d}")

        SubElement(cr, "admission_id").text   = aid
        SubElement(cr, "patient_id").text     = f"P{random.randint(1,100):04d}"

        d_adm  = start + timedelta(days=random.randint(0, 700))
        sejour = random.randint(1, 21)
        d_sort = d_adm + timedelta(days=sejour)

        SubElement(cr, "date_admission").text = d_adm.isoformat()
        SubElement(cr, "date_sortie").text    = d_sort.isoformat()
        SubElement(cr, "duree_sejour").text   = str(sejour)

        diag = random.choice(DIAGNOSTICS)
        diag_el = SubElement(cr, "diagnostic_principal")
        diag_el.set("code_cim10", diag[0])
        diag_el.text = diag[1]

        # Diagnostics secondaires (0 à 2)
        diags_sec = SubElement(cr, "diagnostics_secondaires")
        for d2 in random.sample(DIAGNOSTICS, random.randint(0, 2)):
            if d2[0] != diag[0]:
                ds = SubElement(diags_sec, "diagnostic")
                ds.set("code_cim10", d2[0])
                ds.text = d2[1]

        # Actes médicaux (1 à 3)
        actes_el = SubElement(cr, "actes_medicaux")
        for acte in random.sample(ACTES, random.randint(1, 3)):
            a = SubElement(actes_el, "acte")
            a.set("code", acte[0])
            a.text = acte[1]

        SubElement(cr, "medecin_responsable").text = random.choice(MEDECINS)
        SubElement(cr, "mode_entree").text         = random.choice(MODES_ENTREE)
        SubElement(cr, "mode_sortie").text         = random.choice(MODES_SORTIE)
        SubElement(cr, "hopital_id").text          = f"H{random.randint(1,20):02d}"

        observations = SubElement(cr, "observations")
        SubElement(observations, "texte").text = fake.sentence(nb_words=15)

    tree = ElementTree(root)
    indent(tree, space="  ")
    path = DATA_DIR / "comptes_rendus.xml"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print(f"  ✓ comptes_rendus.xml — {len(sample)} comptes-rendus")
    return path


if __name__ == "__main__":
    gen_xml()
