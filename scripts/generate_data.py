"""
Generate realistic French healthcare sample data using Faker.
Run: python scripts/generate_data.py
"""
import os
import random
import csv
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

fake = Faker("fr_FR")
random.seed(42)
Faker.seed(42)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Reference data ────────────────────────────────────────────────────────────

REGIONS = [
    ("R01", "Île-de-France",        12174880, 12012),
    ("R02", "Auvergne-Rhône-Alpes", 8092048,  69711),
    ("R03", "Hauts-de-France",      5973626,  31813),
    ("R04", "Nouvelle-Aquitaine",   6063495,  84061),
    ("R05", "Occitanie",            5985751,  72724),
    ("R06", "Normandie",            3372000,  29906),
    ("R07", "Bretagne",             3380000,  27208),
    ("R08", "Pays de la Loire",     3840000,  32082),
    ("R09", "Grand Est",            5577000,  57441),
    ("R10", "Provence-PACA",        5101000,  31400),
    ("R11", "Centre-Val de Loire",  2577000,  32247),
    ("R12", "Bourgogne-Franche-Comté", 2820000, 47784),
    ("R13", "Corse",                345000,   8680),
]

SERVICES = [
    ("S01", "Cardiologie",         "Médecine",    "Cardiologie",       40),
    ("S02", "Neurologie",          "Médecine",    "Neurologie",        30),
    ("S03", "Urgences",            "Urgences",    "Médecine d'urgence",80),
    ("S04", "Chirurgie générale",  "Chirurgie",   "Chirurgie générale",50),
    ("S05", "Pédiatrie",           "Médecine",    "Pédiatrie",         35),
    ("S06", "Gynécologie",         "Médecine",    "Gynécologie",       25),
    ("S07", "Orthopédie",          "Chirurgie",   "Orthopédie",        45),
    ("S08", "Oncologie",           "Médecine",    "Oncologie",         30),
    ("S09", "Réanimation",         "Réanimation", "Réanimation",       20),
    ("S10", "Pneumologie",         "Médecine",    "Pneumologie",       28),
    ("S11", "Gastro-entérologie",  "Médecine",    "Gastroentérologie", 32),
    ("S12", "Rhumatologie",        "Médecine",    "Rhumatologie",      22),
    ("S13", "Psychiatrie",         "Psychiatrie", "Psychiatrie",       40),
    ("S14", "Dermatologie",        "Médecine",    "Dermatologie",      18),
    ("S15", "Endocrinologie",      "Médecine",    "Endocrinologie",    20),
]

MALADIES = [
    ("M01", "Infarctus du myocarde",        "I21", "Cardiovasculaire", 5, 0),
    ("M02", "Accident vasculaire cérébral", "I63", "Neurologique",     5, 0),
    ("M03", "Pneumonie",                    "J18", "Respiratoire",     3, 0),
    ("M04", "Diabète de type 2",            "E11", "Endocrinien",      2, 1),
    ("M05", "Hypertension artérielle",      "I10", "Cardiovasculaire", 2, 1),
    ("M06", "Fracture du col du fémur",     "S72", "Traumatologie",    3, 0),
    ("M07", "Cancer du poumon",             "C34", "Oncologie",        5, 1),
    ("M08", "Insuffisance cardiaque",       "I50", "Cardiovasculaire", 4, 1),
    ("M09", "Appendicite aiguë",            "K35", "Chirurgie",        3, 0),
    ("M10", "Dépression sévère",            "F32", "Psychiatrique",    2, 1),
    ("M11", "BPCO",                         "J44", "Respiratoire",     3, 1),
    ("M12", "Sepsis",                       "A41", "Infectieux",       5, 0),
    ("M13", "Colique néphrétique",          "N23", "Urologie",         2, 0),
    ("M14", "Gastro-entérite aiguë",        "A09", "Digestif",         1, 0),
    ("M15", "Asthme aigu grave",            "J45", "Respiratoire",     3, 1),
    ("M16", "Thrombose veineuse profonde",  "I80", "Cardiovasculaire", 3, 0),
    ("M17", "Cholécystite aiguë",           "K81", "Chirurgie",        3, 0),
    ("M18", "Insuffisance rénale chronique","N18", "Nephrologie",      3, 1),
    ("M19", "Lombalgie aiguë",              "M54", "Rhumatologie",     1, 0),
    ("M20", "COVID-19",                     "U07", "Infectieux",       4, 0),
]

HOPITAUX = [
    ("H01", "CHU Paris-Centre",       "Paris",         "R01", 800, "CHU", 450),
    ("H02", "CH Versailles",          "Versailles",    "R01", 350, "CH",  180),
    ("H03", "CHU Lyon-Sud",           "Lyon",          "R02", 750, "CHU", 400),
    ("H04", "CH Grenoble",            "Grenoble",      "R02", 420, "CH",  200),
    ("H05", "CHU Lille",              "Lille",         "R03", 680, "CHU", 380),
    ("H06", "CH Amiens",              "Amiens",        "R03", 310, "CH",  160),
    ("H07", "CHU Bordeaux",           "Bordeaux",      "R04", 600, "CHU", 350),
    ("H08", "CH Pau",                 "Pau",           "R04", 280, "CH",  140),
    ("H09", "CHU Toulouse",           "Toulouse",      "R05", 700, "CHU", 390),
    ("H10", "CH Montpellier",         "Montpellier",   "R05", 500, "CH",  250),
    ("H11", "CH Rouen",               "Rouen",         "R06", 450, "CH",  220),
    ("H12", "CH Caen",                "Caen",          "R06", 380, "CH",  190),
    ("H13", "CH Rennes",              "Rennes",        "R07", 420, "CH",  210),
    ("H14", "CH Nantes",              "Nantes",        "R08", 550, "CHU", 300),
    ("H15", "CH Strasbourg",          "Strasbourg",    "R09", 480, "CH",  240),
    ("H16", "CHU Marseille",          "Marseille",     "R10", 720, "CHU", 400),
    ("H17", "CH Toulon",              "Toulon",        "R10", 320, "CH",  160),
    ("H18", "CH Orléans",             "Orléans",       "R11", 280, "CH",  140),
    ("H19", "CH Dijon",               "Dijon",         "R12", 350, "CH",  175),
    ("H20", "CH Ajaccio",             "Ajaccio",       "R13", 180, "CH",   90),
]

MEDICAMENTS = [
    ("Paracétamol 1g",   "1g",      "3x/jour",  5,  False),
    ("Amoxicilline 500", "500mg",   "3x/jour",  7,  False),
    ("Metformine 850",   "850mg",   "2x/jour",  30, True),
    ("Amlodipine 5",     "5mg",     "1x/jour",  30, True),
    ("Oméprazole 20",    "20mg",    "1x/jour",  14, False),
    ("Ibuprofène 400",   "400mg",   "3x/jour",  5,  False),
    ("Atorvastatine 20", "20mg",    "1x/jour",  30, True),
    ("Bisoprolol 5",     "5mg",     "1x/jour",  30, True),
    ("Ramipril 5",       "5mg",     "1x/jour",  30, True),
    ("Furosémide 40",    "40mg",    "1x/jour",  14, True),
    ("Morphine 10",      "10mg",    "4x/jour",  3,  False),
    ("Héparine 5000",    "5000 UI", "2x/jour",  7,  False),
    ("Prednisone 20",    "20mg",    "1x/jour",  10, False),
    ("Salbutamol spray", "200µg",   "au besoin",30, True),
    ("Warfarine 5",      "5mg",     "1x/jour",  90, True),
    ("Levothyroxine 50", "50µg",    "1x/jour",  30, True),
    ("Sertraline 50",    "50mg",    "1x/jour",  30, True),
    ("Alprazolam 0.25",  "0.25mg",  "2x/jour",  14, False),
    ("Insuline Glargine","10 UI",   "1x/jour",  30, True),
    ("Doxycycline 100",  "100mg",   "2x/jour",  10, False),
]

TESTS_LABO = [
    ("Glycémie",    0.7,  1.1,  "g/L"),
    ("NFS",         4.0,  10.0, "G/L"),
    ("CRP",         0.0,  5.0,  "mg/L"),
    ("Troponine",   0.0,  0.04, "µg/L"),
    ("Créatinine",  60.0, 110.0,"µmol/L"),
    ("Urée",        2.5,  8.0,  "mmol/L"),
    ("ALAT",        7.0,  56.0, "UI/L"),
    ("ASAT",        10.0, 40.0, "UI/L"),
    ("TSH",         0.4,  4.0,  "mUI/L"),
    ("D-Dimères",   0.0,  500.0,"µg/L"),
    ("Hémoglobine", 12.0, 17.5, "g/dL"),
    ("Plaquettes",  150.0,400.0,"G/L"),
    ("Potassium",   3.5,  5.0,  "mmol/L"),
    ("Sodium",      135.0,145.0,"mmol/L"),
    ("Bilirubine",  0.0,  12.0, "µmol/L"),
]

MOTIFS_SORTIE = [
    "Guérison",
    "Amélioration",
    "Transfert vers autre établissement",
    "Sortie contre avis médical",
    "Décès",
    "Retour à domicile avec soins",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def rand_date(start_year=2023, end_date=None):
    start = date(start_year, 1, 1)
    end   = end_date or date.today()
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def age_group(age):
    if age < 18:  return "0-17"
    if age < 31:  return "18-30"
    if age < 51:  return "31-50"
    if age < 66:  return "51-65"
    return "65+"


def write_csv(filename, rows, header):
    path = DATA_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  ✓ {filename} ({len(rows)} lignes)")

# ── Generators ────────────────────────────────────────────────────────────────

def gen_regions():
    rows = [(r[0], r[1], r[2], r[3], fake.city()) for r in REGIONS]
    write_csv("regions.csv", rows,
              ["region_id","nom_region","population","superficie","chef_lieu"])

def gen_hopitaux():
    rows = [(h[0],h[1],h[2],h[3],h[4],h[5],h[6]) for h in HOPITAUX]
    write_csv("hopitaux.csv", rows,
              ["hopital_id","nom","ville","region_id","capacite_lits","type","nb_medecins"])

def gen_services():
    rows = [(s[0],s[1],s[2],s[3],s[4]) for s in SERVICES]
    write_csv("services.csv", rows,
              ["service_id","nom_service","departement","specialite","nb_lits"])

def gen_maladies():
    rows = [(m[0],m[1],m[2],m[3],m[4],m[5]) for m in MALADIES]
    write_csv("maladies.csv", rows,
              ["maladie_id","nom_maladie","code_cim10","categorie","gravite","est_chronique"])

def gen_patients(n=100):
    rows = []
    for i in range(1, n+1):
        pid = f"P{i:04d}"
        age = random.randint(1, 95)
        dob = date.today() - timedelta(days=age*365 + random.randint(0,364))
        reg = random.choice(REGIONS)
        rows.append((pid, fake.last_name(), fake.first_name(), dob.isoformat(),
                     age, random.choice(["M","F"]), reg[1], age_group(age)))
    write_csv("patients.csv", rows,
              ["patient_id","nom","prenom","date_naissance","age","sexe","region","tranche_age"])
    return [r[0] for r in rows]

def gen_admissions(patient_ids, n=500):
    rows  = []
    used  = set()
    for i in range(1, n+1):
        aid     = f"A{i:05d}"
        pid     = random.choice(patient_ids)
        hopital = random.choice(HOPITAUX)
        service = random.choice(SERVICES)
        maladie = random.choice(MALADIES)
        date_adm = rand_date(2023)
        urgence  = random.choices([0, 1], weights=[65, 35])[0]
        rows.append((aid, pid, date_adm.isoformat(),
                     service[1], urgence, maladie[1],
                     hopital[0], service[0], maladie[0]))
        used.add((aid, date_adm))
    write_csv("admissions.csv", rows,
              ["admission_id","patient_id","date_admission","service",
               "urgence","diagnostic","hopital_id","service_id","maladie_id"])
    return [(r[0], r[2]) for r in rows]

def gen_sorties(admissions):
    rows = []
    for i, (aid, date_adm) in enumerate(admissions, 1):
        if random.random() < 0.90:
            d_adm  = date.fromisoformat(date_adm)
            sejour = random.randint(1, 30)
            d_sort = d_adm + timedelta(days=sejour)
            if d_sort > date.today():
                d_sort = date.today()
            rows.append((f"SO{i:05d}", aid, d_sort.isoformat(),
                         random.choice(MOTIFS_SORTIE)))
    write_csv("sorties.csv", rows,
              ["sortie_id","admission_id","date_sortie","motif_sortie"])

def gen_laboratoires(patient_ids, n=1000):
    rows = []
    for i in range(1, n+1):
        pid   = random.choice(patient_ids)
        test  = random.choice(TESTS_LABO)
        nom, vmin, vmax, unite = test
        spread   = (vmax - vmin)
        # 20% chance of abnormal result
        if random.random() < 0.20:
            if random.random() < 0.5:
                val = round(random.uniform(vmin * 0.3, vmin * 0.95), 3)
            else:
                val = round(random.uniform(vmax * 1.05, vmax * 2.5), 3)
            anormal = 1
        else:
            val = round(random.uniform(vmin, vmax), 3)
            anormal = 0
        d = rand_date(2023)
        rows.append((f"L{i:06d}", pid, nom, val, unite, vmin, vmax, anormal, d.isoformat()))
    write_csv("laboratoires.csv", rows,
              ["labo_id","patient_id","type_test","resultat","unite",
               "valeur_ref_min","valeur_ref_max","est_anormal","date_test"])

def gen_medicaments(patient_ids, n=500):
    rows = []
    for i in range(1, n+1):
        pid  = random.choice(patient_ids)
        med  = random.choice(MEDICAMENTS)
        nom, dosage, freq, duree, chronique = med
        d = rand_date(2023)
        rows.append((f"RX{i:05d}", pid, nom, dosage, freq, duree, int(chronique), d.isoformat()))
    write_csv("medicaments.csv", rows,
              ["prescription_id","patient_id","medicament","dosage",
               "frequence","duree_jours","est_chronique","date_prescription"])


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Génération des données de référence...")
    gen_regions()
    gen_hopitaux()
    gen_services()
    gen_maladies()

    print("\nGénération des données patients...")
    patient_ids = gen_patients(100)

    print("\nGénération des données hospitalières...")
    admissions = gen_admissions(patient_ids, 500)
    gen_sorties(admissions)

    print("\nGénération des données cliniques...")
    gen_laboratoires(patient_ids, 1000)
    gen_medicaments(patient_ids, 500)

    print(f"\n✓ Tous les fichiers CSV générés dans : {DATA_DIR}")
