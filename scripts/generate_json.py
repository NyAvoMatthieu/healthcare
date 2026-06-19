"""
Génère data/capteurs_lits.json — flux IoT simulé des capteurs d'occupation
des lits hospitaliers (relevés toutes les 4h sur 90 jours).

Et data/stock_pharmacie.json — inventaire quotidien de la pharmacie centrale.
"""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

random.seed(42)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

HOPITAUX = [
    {"hopital_id": f"H{i:02d}", "capacite_lits": cap}
    for i, cap in enumerate(
        [800,350,750,420,680,310,600,280,700,500,
         450,380,420,550,480,720,320,280,350,180], 1
    )
]
SERVICES = [
    ("S01","Cardiologie",40),("S02","Neurologie",30),("S03","Urgences",80),
    ("S04","Chirurgie générale",50),("S05","Pédiatrie",35),
    ("S06","Gynécologie",25),("S07","Orthopédie",45),("S08","Oncologie",30),
    ("S09","Réanimation",20),("S10","Pneumologie",28),
]

MEDICAMENTS_STOCK = [
    {"code":"MED001","nom":"Paracétamol 1g","unite":"boîte","prix_unitaire":2.50,"stock_alerte":100},
    {"code":"MED002","nom":"Amoxicilline 500mg","unite":"boîte","prix_unitaire":5.80,"stock_alerte":50},
    {"code":"MED003","nom":"Morphine 10mg inj","unite":"ampoule","prix_unitaire":1.20,"stock_alerte":200},
    {"code":"MED004","nom":"Héparine 5000UI","unite":"flacon","prix_unitaire":3.40,"stock_alerte":150},
    {"code":"MED005","nom":"Insuline Glargine","unite":"stylo","prix_unitaire":18.50,"stock_alerte":80},
    {"code":"MED006","nom":"Furosémide 40mg","unite":"boîte","prix_unitaire":2.10,"stock_alerte":100},
    {"code":"MED007","nom":"Metformine 850mg","unite":"boîte","prix_unitaire":3.20,"stock_alerte":120},
    {"code":"MED008","nom":"Atorvastatine 20mg","unite":"boîte","prix_unitaire":7.40,"stock_alerte":90},
    {"code":"MED009","nom":"Oméprazole 20mg","unite":"boîte","prix_unitaire":4.10,"stock_alerte":110},
    {"code":"MED010","nom":"Salbutamol spray","unite":"flacon","prix_unitaire":6.80,"stock_alerte":60},
    {"code":"MED011","nom":"Prednisone 20mg","unite":"boîte","prix_unitaire":3.90,"stock_alerte":70},
    {"code":"MED012","nom":"Warfarine 5mg","unite":"boîte","prix_unitaire":4.50,"stock_alerte":80},
    {"code":"MED013","nom":"Bisoprolol 5mg","unite":"boîte","prix_unitaire":5.10,"stock_alerte":90},
    {"code":"MED014","nom":"Ramipril 5mg","unite":"boîte","prix_unitaire":4.20,"stock_alerte":100},
    {"code":"MED015","nom":"Doxycycline 100mg","unite":"boîte","prix_unitaire":5.60,"stock_alerte":50},
]


def gen_capteurs_lits():
    """Relevés IoT toutes les 4h pendant 90 jours pour les 10 premiers hôpitaux."""
    records = []
    start   = datetime(2024, 1, 1, 0, 0, 0)

    for hopital in HOPITAUX[:10]:
        hid = hopital["hopital_id"]
        for svc in random.sample(SERVICES, 5):
            sid, nom_svc, lits_total = svc
            # Tendance de base : semaine vs week-end, heure de pointe
            for j in range(90):
                d = start + timedelta(days=j)
                is_weekend = d.weekday() >= 5
                base_rate  = 0.65 if is_weekend else 0.82
                for h in [0, 4, 8, 12, 16, 20]:
                    ts = d.replace(hour=h)
                    # Pic en milieu de journée
                    hour_factor = 1.05 if 8 <= h <= 16 else 0.95
                    rate = min(1.0, base_rate * hour_factor + random.uniform(-0.08, 0.08))
                    lits_occ = round(lits_total * rate)
                    records.append({
                        "capteur_id":       f"CAP-{hid}-{sid}-{ts.strftime('%Y%m%d%H%M')}",
                        "hopital_id":       hid,
                        "service_id":       sid,
                        "nom_service":      nom_svc,
                        "timestamp":        ts.isoformat(),
                        "date":             d.date().isoformat(),
                        "heure":            h,
                        "lits_occupes":     lits_occ,
                        "lits_total":       lits_total,
                        "taux_occupation":  round(lits_occ / lits_total * 100, 1),
                        "alertes":          lits_occ >= lits_total,
                    })

    path = DATA_DIR / "capteurs_lits.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "iot_sensors", "nb_records": len(records), "data": records},
                  f, ensure_ascii=False, indent=2)
    print(f"  ✓ capteurs_lits.json — {len(records):,} relevés IoT")
    return path


def gen_stock_pharmacie():
    """Inventaire quotidien de la pharmacie sur 90 jours."""
    records = []
    start   = date(2024, 1, 1)

    for med in MEDICAMENTS_STOCK:
        stock = random.randint(med["stock_alerte"] * 3, med["stock_alerte"] * 8)
        for j in range(90):
            d = start + timedelta(days=j)
            # Consommation quotidienne aléatoire
            consommation = random.randint(5, 30)
            # Réapprovisionnement le lundi
            reappro = random.randint(50, 200) if d.weekday() == 0 and stock < med["stock_alerte"] * 2 else 0
            stock   = max(0, stock - consommation + reappro)
            records.append({
                "stock_id":         f"STK-{med['code']}-{d.isoformat()}",
                "date":             d.isoformat(),
                "code_medicament":  med["code"],
                "nom_medicament":   med["nom"],
                "unite":            med["unite"],
                "stock_disponible": stock,
                "consommation_j":   consommation,
                "reapprovisionnement": reappro,
                "prix_unitaire":    med["prix_unitaire"],
                "valeur_stock":     round(stock * med["prix_unitaire"], 2),
                "sous_seuil_alerte": stock < med["stock_alerte"],
            })

    path = DATA_DIR / "stock_pharmacie.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "pharmacie_centrale", "nb_records": len(records), "data": records},
                  f, ensure_ascii=False, indent=2)
    print(f"  ✓ stock_pharmacie.json — {len(records):,} entrées stock")
    return path


if __name__ == "__main__":
    print("Génération des fichiers JSON...")
    gen_capteurs_lits()
    gen_stock_pharmacie()
