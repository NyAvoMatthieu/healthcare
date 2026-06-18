-- ============================================================
-- Healthcare Analytics Platform - KPI Queries
-- All queries target warehouse.db (SQLite star schema)
-- ============================================================

-- ------------------------------------------------------------
-- KPI 1 : Taux d'occupation des lits
-- Lits occupés / Capacité totale * 100
-- ------------------------------------------------------------
-- KPI: taux_occupation_lits
SELECT
    h.nom                                           AS hopital,
    h.capacite_lits,
    COUNT(fa.admission_id)                          AS admissions_actives,
    ROUND(COUNT(fa.admission_id) * 100.0 / h.capacite_lits, 2) AS taux_occupation_pct
FROM fact_admissions fa
JOIN dim_hopital h ON fa.hopital_id = h.hopital_id
JOIN dim_temps t   ON fa.temps_id   = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
  AND t.mois  = CAST(strftime('%m', 'now') AS INTEGER)
GROUP BY h.hopital_id, h.nom, h.capacite_lits
ORDER BY taux_occupation_pct DESC;

-- ------------------------------------------------------------
-- KPI 2 : Durée moyenne de séjour (DMS)
-- ------------------------------------------------------------
-- KPI: duree_moyenne_sejour
SELECT
    s.nom_service,
    ROUND(AVG(fa.duree_sejour), 1)  AS dms_jours,
    MIN(fa.duree_sejour)            AS min_jours,
    MAX(fa.duree_sejour)            AS max_jours,
    COUNT(*)                        AS nb_sejours
FROM fact_admissions fa
JOIN dim_service s ON fa.service_id = s.service_id
JOIN dim_temps  t  ON fa.temps_id   = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
GROUP BY s.service_id, s.nom_service
ORDER BY dms_jours DESC;

-- ------------------------------------------------------------
-- KPI 3 : Admissions par jour (30 derniers jours)
-- ------------------------------------------------------------
-- KPI: admissions_par_jour
SELECT
    t.date,
    t.jour_semaine,
    COUNT(fa.admission_id)                          AS nb_admissions,
    SUM(fa.est_urgence)                             AS nb_urgences,
    COUNT(fa.admission_id) - SUM(fa.est_urgence)    AS nb_programmees
FROM fact_admissions fa
JOIN dim_temps t ON fa.temps_id = t.temps_id
WHERE t.date >= date('now', '-30 days')
GROUP BY t.date, t.jour_semaine
ORDER BY t.date DESC;

-- ------------------------------------------------------------
-- KPI 4 : Top 10 maladies les plus fréquentes
-- ------------------------------------------------------------
-- KPI: top_maladies
SELECT
    m.nom_maladie,
    m.categorie,
    m.code_cim10,
    m.gravite,
    COUNT(fa.admission_id)  AS nb_cas,
    ROUND(COUNT(fa.admission_id) * 100.0 / SUM(COUNT(fa.admission_id)) OVER(), 2) AS pct_total
FROM fact_admissions fa
JOIN dim_maladie m ON fa.maladie_id = m.maladie_id
JOIN dim_temps   t ON fa.temps_id   = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
GROUP BY m.maladie_id, m.nom_maladie, m.categorie, m.code_cim10, m.gravite
ORDER BY nb_cas DESC
LIMIT 10;

-- ------------------------------------------------------------
-- KPI 5 : Cas par région
-- ------------------------------------------------------------
-- KPI: cas_par_region
SELECT
    r.nom_region,
    r.population,
    COUNT(fa.admission_id)                                              AS nb_admissions,
    ROUND(COUNT(fa.admission_id) * 100000.0 / r.population, 1)         AS taux_pour_100k,
    ROUND(AVG(fa.duree_sejour), 1)                                      AS dms_moy
FROM fact_admissions fa
JOIN dim_patient p  ON fa.patient_id  = p.patient_id
JOIN dim_region  r  ON p.region_id    = r.region_id
JOIN dim_temps   t  ON fa.temps_id    = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
GROUP BY r.region_id, r.nom_region, r.population
ORDER BY nb_admissions DESC;

-- ------------------------------------------------------------
-- KPI 6 : Répartition par tranche d'âge
-- ------------------------------------------------------------
-- KPI: repartition_age
SELECT
    p.tranche_age,
    COUNT(fa.admission_id)  AS nb_admissions,
    SUM(fa.est_urgence)     AS nb_urgences,
    ROUND(AVG(fa.duree_sejour), 1) AS dms_moy,
    ROUND(COUNT(fa.admission_id) * 100.0 / SUM(COUNT(fa.admission_id)) OVER(), 2) AS pct_total
FROM fact_admissions fa
JOIN dim_patient p ON fa.patient_id = p.patient_id
GROUP BY p.tranche_age
ORDER BY p.tranche_age;

-- ------------------------------------------------------------
-- KPI 7 : Taux de réadmission (30 jours)
-- ------------------------------------------------------------
-- KPI: taux_readmission
SELECT
    s.nom_service,
    COUNT(fa.admission_id)                              AS total_admissions,
    SUM(fa.est_readmission)                             AS nb_readmissions,
    ROUND(SUM(fa.est_readmission) * 100.0 / COUNT(fa.admission_id), 2) AS taux_readmission_pct
FROM fact_admissions fa
JOIN dim_service s ON fa.service_id = s.service_id
GROUP BY s.service_id, s.nom_service
ORDER BY taux_readmission_pct DESC;

-- ------------------------------------------------------------
-- KPI 8 : Temps moyen d'attente aux urgences
-- ------------------------------------------------------------
-- KPI: temps_attente_urgences
SELECT
    t.nom_mois                                      AS mois,
    t.annee,
    h.nom                                           AS hopital,
    ROUND(AVG(fu.temps_attente_minutes), 0)         AS attente_moy_min,
    MIN(fu.temps_attente_minutes)                   AS attente_min,
    MAX(fu.temps_attente_minutes)                   AS attente_max,
    COUNT(fu.urgence_id)                            AS nb_passages,
    SUM(fu.est_hospitalise)                         AS nb_hospitalises
FROM fact_urgences fu
JOIN dim_temps   t ON fu.temps_id   = t.temps_id
JOIN dim_hopital h ON fu.hopital_id = h.hopital_id
GROUP BY t.annee, t.mois, t.nom_mois, h.hopital_id, h.nom
ORDER BY t.annee DESC, t.mois DESC;

-- ------------------------------------------------------------
-- KPI 9 : Résultats de laboratoire anormaux
-- ------------------------------------------------------------
-- KPI: labo_anormaux
SELECT
    fl.type_test,
    COUNT(*)                                AS total_tests,
    SUM(fl.est_anormal)                     AS nb_anormaux,
    ROUND(SUM(fl.est_anormal) * 100.0 / COUNT(*), 2) AS taux_anomalie_pct
FROM fact_laboratoires fl
JOIN dim_temps t ON fl.temps_id = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
GROUP BY fl.type_test
ORDER BY taux_anomalie_pct DESC;

-- ------------------------------------------------------------
-- KPI 10 : Admissions urgentes vs programmées
-- ------------------------------------------------------------
-- KPI: urgences_vs_programmees
SELECT
    t.annee,
    t.mois,
    t.nom_mois,
    SUM(fa.est_urgence)                         AS nb_urgences,
    COUNT(fa.admission_id) - SUM(fa.est_urgence) AS nb_programmees,
    COUNT(fa.admission_id)                       AS total,
    ROUND(SUM(fa.est_urgence) * 100.0 / COUNT(fa.admission_id), 2) AS pct_urgences
FROM fact_admissions fa
JOIN dim_temps t ON fa.temps_id = t.temps_id
GROUP BY t.annee, t.mois, t.nom_mois
ORDER BY t.annee DESC, t.mois DESC;

-- ------------------------------------------------------------
-- KPI 11 : Admissions par service
-- ------------------------------------------------------------
-- KPI: admissions_par_service
SELECT
    s.nom_service,
    s.specialite,
    s.nb_lits,
    COUNT(fa.admission_id)  AS nb_admissions,
    ROUND(AVG(fa.duree_sejour), 1)  AS dms,
    SUM(fa.est_urgence)     AS nb_urgences
FROM fact_admissions fa
JOIN dim_service s ON fa.service_id = s.service_id
JOIN dim_temps   t ON fa.temps_id   = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
GROUP BY s.service_id, s.nom_service, s.specialite, s.nb_lits
ORDER BY nb_admissions DESC;

-- ------------------------------------------------------------
-- KPI 12 : Évolution mensuelle des admissions
-- ------------------------------------------------------------
-- KPI: evolution_mensuelle
SELECT
    t.annee,
    t.mois,
    t.nom_mois,
    COUNT(fa.admission_id)  AS nb_admissions,
    SUM(fa.est_urgence)     AS nb_urgences,
    ROUND(AVG(fa.duree_sejour), 1) AS dms_moy
FROM fact_admissions fa
JOIN dim_temps t ON fa.temps_id = t.temps_id
GROUP BY t.annee, t.mois, t.nom_mois
ORDER BY t.annee, t.mois;

-- ------------------------------------------------------------
-- KPI 13 : Répartition hommes / femmes
-- ------------------------------------------------------------
-- KPI: repartition_sexe
SELECT
    p.sexe,
    COUNT(fa.admission_id)  AS nb_admissions,
    ROUND(AVG(fa.duree_sejour), 1)  AS dms_moy,
    SUM(fa.est_urgence)     AS nb_urgences,
    ROUND(COUNT(fa.admission_id) * 100.0 / SUM(COUNT(fa.admission_id)) OVER(), 2) AS pct
FROM fact_admissions fa
JOIN dim_patient p ON fa.patient_id = p.patient_id
GROUP BY p.sexe;

-- ------------------------------------------------------------
-- KPI 14 : Prescriptions par médicament (Top 15)
-- ------------------------------------------------------------
-- KPI: top_medicaments
SELECT
    fp.medicament,
    COUNT(*)            AS nb_prescriptions,
    ROUND(AVG(fp.duree_jours), 1) AS duree_moy_jours,
    SUM(fp.est_chronique) AS nb_chroniques
FROM fact_prescriptions fp
GROUP BY fp.medicament
ORDER BY nb_prescriptions DESC
LIMIT 15;

-- ------------------------------------------------------------
-- KPI 15 : Taux d'incidence par région (pour 100 000 habitants)
-- ------------------------------------------------------------
-- KPI: taux_incidence_region
SELECT
    r.nom_region,
    m.nom_maladie,
    m.categorie,
    COUNT(fa.admission_id)                                  AS nb_cas,
    r.population,
    ROUND(COUNT(fa.admission_id) * 100000.0 / r.population, 2) AS taux_incidence_100k
FROM fact_admissions fa
JOIN dim_patient  p ON fa.patient_id  = p.patient_id
JOIN dim_region   r ON p.region_id    = r.region_id
JOIN dim_maladie  m ON fa.maladie_id  = m.maladie_id
JOIN dim_temps    t ON fa.temps_id    = t.temps_id
WHERE t.annee = strftime('%Y', 'now')
GROUP BY r.region_id, r.nom_region, m.maladie_id, m.nom_maladie, m.categorie, r.population
ORDER BY taux_incidence_100k DESC;
