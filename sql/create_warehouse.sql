-- ============================================================
-- Healthcare Analytics Platform - Data Warehouse Schema
-- Star Schema - SQLite
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- DIMENSION TABLES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_region (
    region_id       INTEGER PRIMARY KEY,
    nom_region      TEXT NOT NULL,
    population      INTEGER,
    superficie      REAL,
    chef_lieu       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_hopital (
    hopital_id      INTEGER PRIMARY KEY,
    nom             TEXT NOT NULL,
    ville           TEXT,
    region_id       INTEGER,
    capacite_lits   INTEGER,
    type            TEXT CHECK(type IN ('CHU','CH','Clinique','EHPAD','SSR')),
    nb_medecins     INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
);

CREATE TABLE IF NOT EXISTS dim_service (
    service_id      INTEGER PRIMARY KEY,
    nom_service     TEXT NOT NULL,
    departement     TEXT,
    specialite      TEXT,
    nb_lits         INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_patient (
    patient_id      TEXT PRIMARY KEY,
    tranche_age     TEXT CHECK(tranche_age IN ('0-17','18-30','31-50','51-65','65+')),
    sexe            TEXT CHECK(sexe IN ('M','F')),
    region_id       INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
);

CREATE TABLE IF NOT EXISTS dim_temps (
    temps_id        INTEGER PRIMARY KEY,
    date            DATE NOT NULL UNIQUE,
    jour            INTEGER,
    mois            INTEGER,
    annee           INTEGER,
    trimestre       INTEGER,
    semaine         INTEGER,
    jour_semaine    TEXT,
    est_weekend     INTEGER DEFAULT 0,
    nom_mois        TEXT
);

CREATE TABLE IF NOT EXISTS dim_maladie (
    maladie_id      INTEGER PRIMARY KEY,
    nom_maladie     TEXT NOT NULL,
    code_cim10      TEXT,
    categorie       TEXT,
    gravite         INTEGER CHECK(gravite BETWEEN 1 AND 5),
    est_chronique   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- FACT TABLES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fact_admissions (
    admission_id        TEXT PRIMARY KEY,
    patient_id          TEXT,
    temps_id            INTEGER,
    hopital_id          INTEGER,
    service_id          INTEGER,
    maladie_id          INTEGER,
    duree_sejour        INTEGER,
    est_urgence         INTEGER DEFAULT 0,
    nb_lits_utilises    INTEGER DEFAULT 1,
    cout_sejour         REAL,
    est_readmission     INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES dim_patient(patient_id),
    FOREIGN KEY (temps_id)    REFERENCES dim_temps(temps_id),
    FOREIGN KEY (hopital_id)  REFERENCES dim_hopital(hopital_id),
    FOREIGN KEY (service_id)  REFERENCES dim_service(service_id),
    FOREIGN KEY (maladie_id)  REFERENCES dim_maladie(maladie_id)
);

CREATE TABLE IF NOT EXISTS fact_urgences (
    urgence_id              TEXT PRIMARY KEY,
    patient_id              TEXT,
    temps_id                INTEGER,
    hopital_id              INTEGER,
    temps_attente_minutes   INTEGER,
    niveau_urgence          INTEGER CHECK(niveau_urgence BETWEEN 1 AND 5),
    disposition             TEXT CHECK(disposition IN ('Hospitalisé','Renvoyé','Transféré','DAMA')),
    est_hospitalise         INTEGER DEFAULT 0,
    duree_prise_en_charge   INTEGER,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES dim_patient(patient_id),
    FOREIGN KEY (temps_id)    REFERENCES dim_temps(temps_id),
    FOREIGN KEY (hopital_id)  REFERENCES dim_hopital(hopital_id)
);

CREATE TABLE IF NOT EXISTS fact_laboratoires (
    labo_id             TEXT PRIMARY KEY,
    patient_id          TEXT,
    temps_id            INTEGER,
    hopital_id          INTEGER,
    type_test           TEXT NOT NULL,
    resultat_numerique  REAL,
    unite               TEXT,
    est_anormal         INTEGER DEFAULT 0,
    valeur_ref_min      REAL,
    valeur_ref_max      REAL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES dim_patient(patient_id),
    FOREIGN KEY (temps_id)    REFERENCES dim_temps(temps_id),
    FOREIGN KEY (hopital_id)  REFERENCES dim_hopital(hopital_id)
);

CREATE TABLE IF NOT EXISTS fact_prescriptions (
    prescription_id TEXT PRIMARY KEY,
    patient_id      TEXT,
    temps_id        INTEGER,
    hopital_id      INTEGER,
    service_id      INTEGER,
    medicament      TEXT NOT NULL,
    dosage          TEXT,
    duree_jours     INTEGER,
    est_chronique   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES dim_patient(patient_id),
    FOREIGN KEY (temps_id)    REFERENCES dim_temps(temps_id),
    FOREIGN KEY (hopital_id)  REFERENCES dim_hopital(hopital_id),
    FOREIGN KEY (service_id)  REFERENCES dim_service(service_id)
);

-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_fact_admissions_patient  ON fact_admissions(patient_id);
CREATE INDEX IF NOT EXISTS idx_fact_admissions_temps    ON fact_admissions(temps_id);
CREATE INDEX IF NOT EXISTS idx_fact_admissions_hopital  ON fact_admissions(hopital_id);
CREATE INDEX IF NOT EXISTS idx_fact_admissions_maladie  ON fact_admissions(maladie_id);
CREATE INDEX IF NOT EXISTS idx_fact_urgences_patient    ON fact_urgences(patient_id);
CREATE INDEX IF NOT EXISTS idx_fact_urgences_temps      ON fact_urgences(temps_id);
CREATE INDEX IF NOT EXISTS idx_fact_labo_patient        ON fact_laboratoires(patient_id);
CREATE INDEX IF NOT EXISTS idx_fact_labo_temps          ON fact_laboratoires(temps_id);
CREATE INDEX IF NOT EXISTS idx_fact_presc_patient       ON fact_prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_dim_temps_date           ON dim_temps(date);
CREATE INDEX IF NOT EXISTS idx_dim_temps_annee_mois     ON dim_temps(annee, mois);
