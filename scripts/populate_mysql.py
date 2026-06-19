"""
Peuple la base MySQL avec des données réalistes via Faker.
Permet de tester l'extraction incrémentale d'ingestion_mysql.py.

Run: python scripts/populate_mysql.py [--clear]
Options:
  --clear   Vide les tables avant insertion (défaut: append)
  --n N     Nombre de patients à insérer (défaut: 50)
"""
import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy import text

fake = Faker("fr_FR")
random.seed(None)  # Seed aléatoire pour données toujours nouvelles

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from db_utils import get_mysql_engine

SERVICES = [
    "Cardiologie","Neurologie","Urgences","Chirurgie générale",
    "Pédiatrie","Gynécologie","Orthopédie","Oncologie","Réanimation","Pneumologie",
]
DIAGNOSTICS = [
    "Infarctus du myocarde","AVC ischémique","Pneumonie","Diabète type 2",
    "Appendicite aiguë","Insuffisance cardiaque","BPCO","Sepsis",
    "Colique néphrétique","Lombalgie aiguë",
]
REGIONS = [
    "Île-de-France","Auvergne-Rhône-Alpes","Hauts-de-France",
    "Nouvelle-Aquitaine","Occitanie","Normandie","Bretagne",
    "Pays de la Loire","Grand Est","Provence-PACA",
]
SPECIALITES = [
    "Cardiologie","Neurologie","Chirurgie générale","Pédiatrie",
    "Urgentologie","Réanimation","Oncologie","Anesthésie",
]
MEDICAMENTS = [
    ("Paracétamol 1g","1g","3x/jour"),
    ("Amoxicilline 500mg","500mg","3x/jour"),
    ("Metformine 850mg","850mg","2x/jour"),
    ("Oméprazole 20mg","20mg","1x/jour"),
    ("Bisoprolol 5mg","5mg","1x/jour"),
    ("Furosémide 40mg","40mg","1x/jour"),
    ("Morphine 10mg","10mg","4x/jour"),
]
TESTS = [
    ("Glycémie",0.7,1.1,"g/L"),("NFS",4.0,10.0,"G/L"),
    ("CRP",0.0,5.0,"mg/L"),("Troponine",0.0,0.04,"µg/L"),
    ("Créatinine",60.0,110.0,"µmol/L"),
]


def insert_medecins(conn, n=10) -> list:
    ids = []
    for i in range(n):
        r = conn.execute(text("""
            INSERT INTO medecins (nom, prenom, specialite, service)
            VALUES (:nom, :prenom, :spe, :svc)
        """), {"nom": fake.last_name(), "prenom": fake.first_name(),
               "spe": random.choice(SPECIALITES), "svc": random.choice(SERVICES)})
        ids.append(r.lastrowid)
    print(f"  ✓ {n} médecins insérés")
    return ids


def insert_patients(conn, n=50) -> list:
    ids = []
    for _ in range(n):
        age = random.randint(1, 90)
        dob = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
        r = conn.execute(text("""
            INSERT INTO patients (nom, prenom, date_naissance, sexe, adresse, region)
            VALUES (:nom, :prenom, :dob, :sexe, :adr, :reg)
        """), {"nom": fake.last_name(), "prenom": fake.first_name(),
               "dob": dob.isoformat(), "sexe": random.choice(["M","F"]),
               "adr": fake.address().replace("\n"," "),
               "reg": random.choice(REGIONS)})
        ids.append(r.lastrowid)
    print(f"  ✓ {n} patients insérés")
    return ids


def insert_admissions(conn, patient_ids, medecin_ids, n_per_patient=2) -> list:
    adm_ids = []
    start   = datetime(2023, 6, 1)
    for pid in patient_ids:
        for _ in range(random.randint(1, n_per_patient)):
            d_adm  = start + timedelta(days=random.randint(0, 550))
            sejour = random.randint(1, 15)
            d_sort = d_adm + timedelta(days=sejour)
            urgence = random.choices([0, 1], weights=[65, 35])[0]
            r = conn.execute(text("""
                INSERT INTO admissions
                    (patient_id, date_admission, date_sortie, service,
                     est_urgence, diagnostic, medecin_id, statut)
                VALUES (:pid, :da, :ds, :svc, :urg, :diag, :mid, 'Sorti')
            """), {"pid": pid, "da": d_adm, "ds": d_sort,
                   "svc": random.choice(SERVICES),
                   "urg": urgence,
                   "diag": random.choice(DIAGNOSTICS),
                   "mid": random.choice(medecin_ids)})
            adm_ids.append((r.lastrowid, pid))
    print(f"  ✓ {len(adm_ids)} admissions insérées")
    return adm_ids


def insert_laboratoires(conn, patient_ids, adm_ids):
    count = 0
    for pid in patient_ids:
        for _ in range(random.randint(1, 5)):
            test = random.choice(TESTS)
            nom, vmin, vmax, unite = test
            if random.random() < 0.2:
                val     = round(random.uniform(vmin*0.3, vmin*0.9), 3) if random.random() < 0.5 \
                          else round(random.uniform(vmax*1.1, vmax*2.5), 3)
                anormal = 1
            else:
                val     = round(random.uniform(vmin, vmax), 3)
                anormal = 0
            d_test = datetime(2023, 6, 1) + timedelta(days=random.randint(0, 550))
            conn.execute(text("""
                INSERT INTO laboratoires
                    (patient_id, type_test, resultat, unite,
                     valeur_ref_min, valeur_ref_max, est_anormal, date_test)
                VALUES (:pid, :test, :val, :unite, :vmin, :vmax, :an, :dt)
            """), {"pid": pid, "test": nom, "val": val, "unite": unite,
                   "vmin": vmin, "vmax": vmax, "an": anormal, "dt": d_test})
            count += 1
    print(f"  ✓ {count} analyses de laboratoire insérées")


def insert_prescriptions(conn, patient_ids, adm_ids, medecin_ids):
    count = 0
    for pid in patient_ids:
        for _ in range(random.randint(1, 3)):
            med     = random.choice(MEDICAMENTS)
            d_presc = datetime(2023, 6, 1) + timedelta(days=random.randint(0, 550))
            conn.execute(text("""
                INSERT INTO prescriptions
                    (patient_id, medicament, dosage, frequence, duree_jours,
                     est_chronique, medecin_id, date_prescription)
                VALUES (:pid, :med, :dos, :freq, :dur, :chr, :mid, :dp)
            """), {"pid": pid, "med": med[0], "dos": med[1], "freq": med[2],
                   "dur": random.randint(3, 30),
                   "chr": random.choices([0,1], weights=[70,30])[0],
                   "mid": random.choice(medecin_ids), "dp": d_presc})
            count += 1
    print(f"  ✓ {count} prescriptions insérées")


def clear_tables(conn):
    for t in ["prescriptions","laboratoires","admissions","patients","medecins"]:
        conn.execute(text(f"DELETE FROM {t}"))
    print("  ✓ Tables vidées")


def main(n_patients=50, do_clear=False):
    print("\nConnexion MySQL...")
    try:
        engine = get_mysql_engine()
        with engine.connect() as conn:
            if do_clear:
                clear_tables(conn)
                conn.commit()

            med_ids = insert_medecins(conn, 10)
            conn.commit()
            pat_ids = insert_patients(conn, n_patients)
            conn.commit()
            adm_ids = insert_admissions(conn, pat_ids, med_ids)
            conn.commit()
            insert_laboratoires(conn, pat_ids, adm_ids)
            conn.commit()
            insert_prescriptions(conn, pat_ids, adm_ids, med_ids)
            conn.commit()

        print(f"\n✓ MySQL peuplé avec {n_patients} patients et leurs données associées")
        print("  Lancez maintenant: python scripts/extract_mysql.py")
    except Exception as e:
        print(f"\n✗ Erreur MySQL: {e}")
        print("  Vérifiez que MySQL est démarré et que config/config.yaml est correct.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Peupler la base MySQL Healthcare")
    parser.add_argument("--clear", action="store_true", help="Vider les tables avant insertion")
    parser.add_argument("--n",     type=int, default=50,  help="Nombre de patients (défaut: 50)")
    args = parser.parse_args()
    main(n_patients=args.n, do_clear=args.clear)
