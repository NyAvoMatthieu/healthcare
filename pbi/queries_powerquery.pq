// ============================================================================
// queries_powerquery.pq — Scripts Power Query M pour Healthcare Analytics
//
// Instructions :
//   1. Power BI Desktop > Transformer les données (Power Query)
//   2. Pour chaque requête ci-dessous :
//      Accueil > Nouvelle source > Requête vide
//      Affichage > Éditeur avancé > Coller le bloc correspondant
//
// IMPORTANT : Remplacez le chemin dans Source_Excel par le vôtre
//   Exemple Windows : C:\Users\VotreNom\Documents\S6\Datawarehouse\
//                     healthcare-analytics\pbi\healthcare_powerbi.xlsx
// ============================================================================


// ============================================================================
// REQUÊTE PARTAGÉE — Chemin vers le fichier Excel
// (Créer cette requête en premier, les autres y font référence)
// ============================================================================

// Nom de la requête : CheminExcel
let
    Chemin = "C:\Chemin\Vers\healthcare-analytics\pbi\healthcare_powerbi.xlsx"
in
    Chemin


// ============================================================================
// dim_patient
// ============================================================================
let
    Source       = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille      = Source{[Item="dim_patient",Kind="Sheet"]}[Data],
    EnTetes      = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols    = Table.TransformColumnTypes(EnTetes, {
                       {"patient_id",  type text},
                       {"nom",         type text},
                       {"prenom",      type text},
                       {"sexe",        type text},
                       {"age",         Int64.Type},
                       {"tranche_age", type text},
                       {"ville",       type text},
                       {"code_postal", type text},
                       {"date_naissance", type date}
                   }),
    Nettoyage    = Table.SelectRows(TypesCols,
                       each [patient_id] <> null and [patient_id] <> "")
in
    Nettoyage


// ============================================================================
// dim_hopital
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="dim_hopital",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"hopital_id",    type text},
                    {"nom_hopital",   type text},
                    {"type_hopital",  type text},
                    {"capacite_lits", Int64.Type},
                    {"ville",         type text},
                    {"region_id",     type text}
                })
in
    TypesCols


// ============================================================================
// dim_maladie
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="dim_maladie",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"maladie_id",   type text},
                    {"nom_maladie",  type text},
                    {"categorie",    type text},
                    {"code_cim10",   type text},
                    {"est_chronique",Int64.Type}
                }),
    // Colonne booléenne lisible
    AjoutLabel= Table.AddColumn(TypesCols, "Chronique",
                    each if [est_chronique] = 1 then "Oui" else "Non",
                    type text)
in
    AjoutLabel


// ============================================================================
// dim_region
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="dim_region",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"region_id",  type text},
                    {"nom_region", type text},
                    {"population", Int64.Type}
                })
in
    TypesCols


// ============================================================================
// dim_temps
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="dim_temps",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"temps_id",   Int64.Type},
                    {"date",       type date},
                    {"annee",      Int64.Type},
                    {"trimestre",  Int64.Type},
                    {"mois",       Int64.Type},
                    {"nom_mois",   type text},
                    {"semaine",    Int64.Type},
                    {"jour",       Int64.Type},
                    {"nom_jour",   type text},
                    {"est_weekend",Int64.Type}
                }),
    AjoutWeekend = Table.AddColumn(TypesCols, "Weekend",
                       each if [est_weekend] = 1 then "Weekend" else "Semaine",
                       type text)
in
    AjoutWeekend


// ============================================================================
// fact_admissions
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="fact_admissions",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"admission_id",        type text},
                    {"patient_id",          type text},
                    {"hopital_id",          type text},
                    {"maladie_id",          type text},
                    {"temps_id",            Int64.Type},
                    {"duree_sejour",        Int64.Type},
                    {"cout_hospitalisation",type number},
                    {"mode_admission",      type text},
                    {"mode_sortie",         type text},
                    {"service",             type text}
                }),
    // Catégorie DMS calculée côté Power Query aussi
    AjoutDMSCat = Table.AddColumn(TypesCols, "Catégorie DMS",
                      each if [duree_sejour] <= 3 then "Courte (≤ 3j)"
                           else if [duree_sejour] <= 7 then "Moyenne (4-7j)"
                           else "Longue (> 7j)",
                      type text)
in
    AjoutDMSCat


// ============================================================================
// fact_urgences
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="fact_urgences",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"urgence_id",         type text},
                    {"patient_id",         type text},
                    {"hopital_id",         type text},
                    {"temps_id",           Int64.Type},
                    {"motif",              type text},
                    {"gravite",            type text},
                    {"temps_attente_min",  Int64.Type},
                    {"temps_pec_min",      Int64.Type},
                    {"orientation",        type text}
                })
in
    TypesCols


// ============================================================================
// fact_laboratoires
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="fact_laboratoires",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"labo_id",      type text},
                    {"admission_id", type text},
                    {"patient_id",   type text},
                    {"temps_id",     Int64.Type},
                    {"type_analyse", type text},
                    {"resultat",     type number},
                    {"unite",        type text},
                    {"est_anormal",  Int64.Type}
                }),
    AjoutStatut = Table.AddColumn(TypesCols, "Statut Résultat",
                      each if [est_anormal] = 1 then "⚠ Anormal" else "✓ Normal",
                      type text)
in
    AjoutStatut


// ============================================================================
// fact_prescriptions
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="fact_prescriptions",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"prescription_id",  type text},
                    {"admission_id",     type text},
                    {"patient_id",       type text},
                    {"temps_id",         Int64.Type},
                    {"nom_medicament",   type text},
                    {"dosage",           type text},
                    {"quantite",         Int64.Type},
                    {"prix_unitaire",    type number},
                    {"duree_traitement", Int64.Type}
                }),
    AjoutCoutTotal = Table.AddColumn(TypesCols, "Coût Total Prescription",
                         each [quantite] * [prix_unitaire],
                         type number)
in
    AjoutCoutTotal


// ============================================================================
// fact_occupation_lits
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="fact_occupation_lits",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"capteur_id",      type text},
                    {"hopital_id",      type text},
                    {"service_id",      type text},
                    {"date",            type date},
                    {"heure",           Int64.Type},
                    {"lits_occupes",    Int64.Type},
                    {"lits_total",      Int64.Type},
                    {"taux_occupation", type number},
                    {"alertes",         Int64.Type}
                }),
    AjoutNiveau = Table.AddColumn(TypesCols, "Niveau Occupation",
                      each if [taux_occupation] >= 85 then "Critique (≥85%)"
                           else if [taux_occupation] >= 60 then "Normal (60-84%)"
                           else "Faible (<60%)",
                      type text)
in
    AjoutNiveau


// ============================================================================
// analytics_mart (table dénormalisée — vue principale)
// ============================================================================
let
    Source    = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille   = Source{[Item="analytics_mart",Kind="Sheet"]}[Data],
    EnTetes   = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true]),
    TypesCols = Table.TransformColumnTypes(EnTetes, {
                    {"admission_id",         type text},
                    {"patient_id",           type text},
                    {"nom",                  type text},
                    {"prenom",               type text},
                    {"sexe",                 type text},
                    {"age",                  Int64.Type},
                    {"tranche_age",          type text},
                    {"hopital_id",           type text},
                    {"nom_hopital",          type text},
                    {"type_hopital",         type text},
                    {"nom_region",           type text},
                    {"nom_maladie",          type text},
                    {"categorie_maladie",    type text},
                    {"date",                 type date},
                    {"annee",                Int64.Type},
                    {"mois",                 Int64.Type},
                    {"nom_mois",             type text},
                    {"est_weekend",          Int64.Type},
                    {"duree_sejour",         Int64.Type},
                    {"cout_hospitalisation", type number},
                    {"mode_admission",       type text},
                    {"mode_sortie",          type text},
                    {"service",              type text}
                })
in
    TypesCols


// ============================================================================
// kpi_cache (table des indicateurs pré-calculés)
// ============================================================================
let
    Source  = Excel.Workbook(File.Contents(CheminExcel), null, true),
    Feuille = Source{[Item="kpi_cache",Kind="Sheet"]}[Data],
    EnTetes = Table.PromoteHeaders(Feuille, [PromoteAllScalars=true])
in
    EnTetes
