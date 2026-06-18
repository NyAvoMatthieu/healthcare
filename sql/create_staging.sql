-- ============================================================
-- Healthcare Analytics Platform - Staging Zone Schema
-- SQLite - Receives raw data before transformation
-- ============================================================

-- ------------------------------------------------------------
-- ETL LOGGING
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS etl_log (
    run_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dag_name            TEXT NOT NULL,
    task_name           TEXT,
    start_time          TIMESTAMP,
    end_time            TIMESTAMP,
    status              TEXT CHECK(status IN ('RUNNING','SUCCESS','FAILED','SKIPPED')),
    records_processed   INTEGER DEFAULT 0,
    error_message       TEXT,
    source              TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- STAGING TABLES - CSV SOURCES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stg_patients (
    patient_id      TEXT,
    nom             TEXT,
    prenom          TEXT,
    date_naissance  TEXT,
    age             INTEGER,
    sexe            TEXT,
    region          TEXT,
    tranche_age     TEXT,
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_admissions (
    admission_id    TEXT,
    patient_id      TEXT,
    date_admission  TEXT,
    service         TEXT,
    urgence         INTEGER,
    diagnostic      TEXT,
    hopital_id      TEXT,
    service_id      TEXT,
    maladie_id      TEXT,
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_sorties (
    sortie_id       TEXT,
    admission_id    TEXT,
    date_sortie     TEXT,
    motif_sortie    TEXT,
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_laboratoires (
    labo_id             TEXT,
    patient_id          TEXT,
    type_test           TEXT,
    resultat            REAL,
    unite               TEXT,
    valeur_ref_min      REAL,
    valeur_ref_max      REAL,
    est_anormal         INTEGER,
    date_test           TEXT,
    source_file         TEXT,
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_medicaments (
    prescription_id TEXT,
    patient_id      TEXT,
    medicament      TEXT,
    dosage          TEXT,
    frequence       TEXT,
    duree_jours     INTEGER,
    est_chronique   INTEGER DEFAULT 0,
    date_prescription TEXT,
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_hopitaux (
    hopital_id      TEXT,
    nom             TEXT,
    ville           TEXT,
    region          TEXT,
    region_id       TEXT,
    capacite_lits   INTEGER,
    type            TEXT,
    nb_medecins     INTEGER,
    source_file     TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- STAGING TABLES - API SOURCES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stg_api_maladies (
    maladie_id      TEXT,
    nom_maladie     TEXT,
    code_cim10      TEXT,
    categorie       TEXT,
    gravite         INTEGER,
    taux_incidence  REAL,
    est_chronique   INTEGER,
    source_api      TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_api_epidemies (
    epidemie_id     TEXT,
    maladie         TEXT,
    region          TEXT,
    nb_cas          INTEGER,
    date_debut      TEXT,
    date_fin        TEXT,
    statut          TEXT,
    source_api      TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_api_regions (
    region_id       TEXT,
    nom_region      TEXT,
    population      INTEGER,
    nb_medecins     INTEGER,
    nb_hopitaux     INTEGER,
    taux_mortalite  REAL,
    source_api      TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- STAGING TABLES - MYSQL SOURCE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stg_mysql_patients (
    id              INTEGER,
    nom             TEXT,
    prenom          TEXT,
    date_naissance  TEXT,
    sexe            TEXT,
    region          TEXT,
    updated_at      TEXT,
    source          TEXT DEFAULT 'mysql',
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_mysql_admissions (
    id              INTEGER,
    patient_id      INTEGER,
    date_admission  TEXT,
    date_sortie     TEXT,
    service         TEXT,
    est_urgence     INTEGER,
    diagnostic      TEXT,
    updated_at      TEXT,
    source          TEXT DEFAULT 'mysql',
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
