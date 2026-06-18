"""
Mock Public Health REST API — simulates a regional health statistics service.
Run: python api/mock_api.py
Port: 5000
"""
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ── Static reference data ─────────────────────────────────────────────────────

MALADIES = [
    {"maladie_id": "M01", "nom": "Infarctus du myocarde",        "code_cim10": "I21", "categorie": "Cardiovasculaire", "gravite": 5, "taux_incidence": 185.4, "est_chronique": 0},
    {"maladie_id": "M02", "nom": "Accident vasculaire cérébral", "code_cim10": "I63", "categorie": "Neurologique",     "gravite": 5, "taux_incidence": 143.2, "est_chronique": 0},
    {"maladie_id": "M03", "nom": "Pneumonie",                    "code_cim10": "J18", "categorie": "Respiratoire",     "gravite": 3, "taux_incidence": 320.0, "est_chronique": 0},
    {"maladie_id": "M04", "nom": "Diabète de type 2",            "code_cim10": "E11", "categorie": "Endocrinien",      "gravite": 2, "taux_incidence": 510.0, "est_chronique": 1},
    {"maladie_id": "M05", "nom": "Hypertension artérielle",      "code_cim10": "I10", "categorie": "Cardiovasculaire", "gravite": 2, "taux_incidence": 1200.0,"est_chronique": 1},
    {"maladie_id": "M06", "nom": "Fracture du col du fémur",     "code_cim10": "S72", "categorie": "Traumatologie",    "gravite": 3, "taux_incidence": 95.0,  "est_chronique": 0},
    {"maladie_id": "M07", "nom": "Cancer du poumon",             "code_cim10": "C34", "categorie": "Oncologie",        "gravite": 5, "taux_incidence": 48.3,  "est_chronique": 1},
    {"maladie_id": "M08", "nom": "Insuffisance cardiaque",       "code_cim10": "I50", "categorie": "Cardiovasculaire", "gravite": 4, "taux_incidence": 220.0, "est_chronique": 1},
    {"maladie_id": "M09", "nom": "Appendicite aiguë",            "code_cim10": "K35", "categorie": "Chirurgie",        "gravite": 3, "taux_incidence": 105.0, "est_chronique": 0},
    {"maladie_id": "M10", "nom": "Dépression sévère",            "code_cim10": "F32", "categorie": "Psychiatrique",    "gravite": 2, "taux_incidence": 390.0, "est_chronique": 1},
    {"maladie_id": "M11", "nom": "BPCO",                         "code_cim10": "J44", "categorie": "Respiratoire",     "gravite": 3, "taux_incidence": 280.0, "est_chronique": 1},
    {"maladie_id": "M12", "nom": "Sepsis",                       "code_cim10": "A41", "categorie": "Infectieux",       "gravite": 5, "taux_incidence": 72.0,  "est_chronique": 0},
    {"maladie_id": "M13", "nom": "Colique néphrétique",          "code_cim10": "N23", "categorie": "Urologie",         "gravite": 2, "taux_incidence": 380.0, "est_chronique": 0},
    {"maladie_id": "M14", "nom": "Gastro-entérite aiguë",        "code_cim10": "A09", "categorie": "Digestif",         "gravite": 1, "taux_incidence": 850.0, "est_chronique": 0},
    {"maladie_id": "M15", "nom": "COVID-19",                     "code_cim10": "U07", "categorie": "Infectieux",       "gravite": 4, "taux_incidence": 620.0, "est_chronique": 0},
    {"maladie_id": "M16", "nom": "Asthme aigu grave",            "code_cim10": "J45", "categorie": "Respiratoire",     "gravite": 3, "taux_incidence": 170.0, "est_chronique": 1},
    {"maladie_id": "M17", "nom": "Thrombose veineuse profonde",  "code_cim10": "I80", "categorie": "Cardiovasculaire", "gravite": 3, "taux_incidence": 120.0, "est_chronique": 0},
    {"maladie_id": "M18", "nom": "Insuffisance rénale chronique","code_cim10": "N18", "categorie": "Nephrologie",      "gravite": 3, "taux_incidence": 290.0, "est_chronique": 1},
    {"maladie_id": "M19", "nom": "Lombalgie aiguë",              "code_cim10": "M54", "categorie": "Rhumatologie",     "gravite": 1, "taux_incidence": 1800.0,"est_chronique": 0},
    {"maladie_id": "M20", "nom": "Cholécystite aiguë",           "code_cim10": "K81", "categorie": "Chirurgie",        "gravite": 3, "taux_incidence": 88.0,  "est_chronique": 0},
]

EPIDEMIES = [
    {"id": "E001", "maladie": "Grippe saisonnière",  "region": "Île-de-France",        "nb_cas": 1542, "date_debut": "2024-11-01", "date_fin": None,         "statut": "Active"},
    {"id": "E002", "maladie": "Gastro-entérite",     "region": "Auvergne-Rhône-Alpes", "nb_cas": 876,  "date_debut": "2024-10-15", "date_fin": None,         "statut": "Active"},
    {"id": "E003", "maladie": "COVID-19",             "region": "Hauts-de-France",      "nb_cas": 423,  "date_debut": "2024-09-01", "date_fin": "2024-11-30", "statut": "Terminée"},
    {"id": "E004", "maladie": "Coqueluche",           "region": "Bretagne",             "nb_cas": 215,  "date_debut": "2024-08-01", "date_fin": None,         "statut": "Active"},
    {"id": "E005", "maladie": "Méningite à méningocoque","region": "Occitanie",         "nb_cas": 12,   "date_debut": "2024-11-10", "date_fin": None,         "statut": "Alerte"},
    {"id": "E006", "maladie": "Grippe saisonnière",  "region": "Normandie",            "nb_cas": 387,  "date_debut": "2024-11-05", "date_fin": None,         "statut": "Active"},
    {"id": "E007", "maladie": "Légionellose",         "region": "Provence-PACA",        "nb_cas": 28,   "date_debut": "2024-07-20", "date_fin": "2024-09-15", "statut": "Terminée"},
]

REGIONS = [
    {"region_id": "R01", "nom_region": "Île-de-France",            "population": 12174880, "nb_medecins": 38420, "nb_hopitaux": 52, "taux_mortalite": 8.2},
    {"region_id": "R02", "nom_region": "Auvergne-Rhône-Alpes",    "population": 8092048,  "nb_medecins": 24100, "nb_hopitaux": 38, "taux_mortalite": 8.9},
    {"region_id": "R03", "nom_region": "Hauts-de-France",          "population": 5973626,  "nb_medecins": 16200, "nb_hopitaux": 29, "taux_mortalite": 10.1},
    {"region_id": "R04", "nom_region": "Nouvelle-Aquitaine",       "population": 6063495,  "nb_medecins": 18700, "nb_hopitaux": 31, "taux_mortalite": 9.3},
    {"region_id": "R05", "nom_region": "Occitanie",                "population": 5985751,  "nb_medecins": 19800, "nb_hopitaux": 28, "taux_mortalite": 8.7},
    {"region_id": "R06", "nom_region": "Normandie",                "population": 3372000,  "nb_medecins": 9400,  "nb_hopitaux": 18, "taux_mortalite": 9.8},
    {"region_id": "R07", "nom_region": "Bretagne",                 "population": 3380000,  "nb_medecins": 9800,  "nb_hopitaux": 17, "taux_mortalite": 9.0},
    {"region_id": "R08", "nom_region": "Pays de la Loire",         "population": 3840000,  "nb_medecins": 11200, "nb_hopitaux": 19, "taux_mortalite": 8.5},
    {"region_id": "R09", "nom_region": "Grand Est",                "population": 5577000,  "nb_medecins": 14900, "nb_hopitaux": 27, "taux_mortalite": 9.6},
    {"region_id": "R10", "nom_region": "Provence-PACA",            "population": 5101000,  "nb_medecins": 17600, "nb_hopitaux": 24, "taux_mortalite": 9.1},
    {"region_id": "R11", "nom_region": "Centre-Val de Loire",      "population": 2577000,  "nb_medecins": 7100,  "nb_hopitaux": 15, "taux_mortalite": 9.9},
    {"region_id": "R12", "nom_region": "Bourgogne-Franche-Comté",  "population": 2820000,  "nb_medecins": 7800,  "nb_hopitaux": 16, "taux_mortalite": 10.2},
    {"region_id": "R13", "nom_region": "Corse",                    "population": 345000,   "nb_medecins": 1100,  "nb_hopitaux": 4,  "taux_mortalite": 10.5},
]

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Healthcare Mock API", "version": "1.0.0"})


@app.route("/api/maladies")
def get_maladies():
    return jsonify({"count": len(MALADIES), "data": MALADIES})


@app.route("/api/maladies/<maladie_id>")
def get_maladie(maladie_id):
    for m in MALADIES:
        if m["maladie_id"] == maladie_id:
            return jsonify(m)
    return jsonify({"error": "Maladie non trouvée"}), 404


@app.route("/api/epidemies")
def get_epidemies():
    return jsonify({"count": len(EPIDEMIES), "data": EPIDEMIES})


@app.route("/api/regions")
def get_regions():
    return jsonify({"count": len(REGIONS), "data": REGIONS})


@app.route("/api/regions/<region_id>/maladies")
def get_region_maladies(region_id):
    region = next((r for r in REGIONS if r["region_id"] == region_id), None)
    if not region:
        return jsonify({"error": "Région non trouvée"}), 404
    import random
    random.seed(hash(region_id))
    stats = [
        {"maladie": m["nom"], "nb_cas": random.randint(10, 500),
         "taux_incidence": round(m["taux_incidence"] * random.uniform(0.7, 1.3), 1)}
        for m in MALADIES[:10]
    ]
    return jsonify({"region": region["nom_region"], "maladies": stats})


@app.route("/api/stats/national")
def get_national_stats():
    total_pop  = sum(r["population"]  for r in REGIONS)
    total_hop  = sum(r["nb_hopitaux"] for r in REGIONS)
    total_med  = sum(r["nb_medecins"] for r in REGIONS)
    taux_moy   = sum(r["taux_mortalite"] for r in REGIONS) / len(REGIONS)
    return jsonify({
        "population_totale":    total_pop,
        "nb_hopitaux":          total_hop,
        "nb_medecins":          total_med,
        "taux_mortalite_moyen": round(taux_moy, 2),
        "nb_regions":           len(REGIONS),
        "epidemies_actives":    sum(1 for e in EPIDEMIES if e["statut"] in ("Active","Alerte")),
    })


if __name__ == "__main__":
    print("Healthcare Mock API démarrée sur http://localhost:5000")
    print("Endpoints : /health, /api/maladies, /api/epidemies, /api/regions, /api/stats/national")
    app.run(host="0.0.0.0", port=5000, debug=False)
