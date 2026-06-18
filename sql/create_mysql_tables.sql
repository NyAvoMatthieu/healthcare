-- ============================================================
-- Healthcare Analytics Platform - MySQL Source Tables
-- Simulates an operational hospital information system
-- ============================================================

CREATE DATABASE IF NOT EXISTS healthcare_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE healthcare_db;

CREATE TABLE IF NOT EXISTS medecins (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nom         VARCHAR(100) NOT NULL,
    prenom      VARCHAR(100) NOT NULL,
    specialite  VARCHAR(100),
    service     VARCHAR(100),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_specialite (specialite)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS patients (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,
    prenom          VARCHAR(100) NOT NULL,
    date_naissance  DATE NOT NULL,
    sexe            CHAR(1) CHECK(sexe IN ('M','F')),
    adresse         TEXT,
    region          VARCHAR(100),
    numero_secu     VARCHAR(20) UNIQUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS admissions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    date_admission  DATETIME NOT NULL,
    date_sortie     DATETIME,
    service         VARCHAR(100) NOT NULL,
    est_urgence     TINYINT(1) DEFAULT 0,
    diagnostic      VARCHAR(255),
    medecin_id      INT,
    statut          ENUM('En cours','Sorti','Transféré') DEFAULT 'En cours',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (medecin_id)  REFERENCES medecins(id) ON DELETE SET NULL,
    INDEX idx_patient_id   (patient_id),
    INDEX idx_date_admission (date_admission),
    INDEX idx_updated_at   (updated_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS laboratoires (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    admission_id    INT,
    type_test       VARCHAR(100) NOT NULL,
    resultat        DECIMAL(10,3),
    unite           VARCHAR(50),
    valeur_ref_min  DECIMAL(10,3),
    valeur_ref_max  DECIMAL(10,3),
    est_anormal     TINYINT(1) DEFAULT 0,
    date_test       DATETIME NOT NULL,
    technicien_id   INT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)   REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE SET NULL,
    INDEX idx_patient_id (patient_id),
    INDEX idx_date_test  (date_test),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS prescriptions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    admission_id    INT,
    medicament      VARCHAR(200) NOT NULL,
    dosage          VARCHAR(100),
    frequence       VARCHAR(100),
    duree_jours     INT,
    est_chronique   TINYINT(1) DEFAULT 0,
    medecin_id      INT,
    date_prescription DATETIME NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)   REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE SET NULL,
    FOREIGN KEY (medecin_id)   REFERENCES medecins(id)  ON DELETE SET NULL,
    INDEX idx_patient_id (patient_id),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- User with limited privileges for ETL extraction
-- ------------------------------------------------------------
-- Run as MySQL root:
-- CREATE USER 'healthcare_user'@'localhost' IDENTIFIED BY 'healthcare_pass';
-- GRANT SELECT ON healthcare_db.* TO 'healthcare_user'@'localhost';
-- FLUSH PRIVILEGES;
