# Healthcare Analytics — Plan du Rapport Power BI

7 pages · Thème : bleu médical (#1565C0) + blanc

---

## Page 1 — Vue Générale (Dashboard KPI)

**Objectif :** Vue d'ensemble en un coup d'œil pour la direction.

### Visuels

| Visuel | Type | Données |
|--------|------|---------|
| Total Admissions | Carte | `[Total Admissions]` |
| Patients Distincts | Carte | `[Patients Distincts]` |
| DMS Moyen | Carte | `[DMS Moyen]` (format : 0.0 "j") |
| Coût Moyen Séjour | Carte | `[Coût Moyen Séjour]` (format : monétaire) |
| Taux Occupation | Carte + jauge | `[Taux Occupation Moyen]` |
| % Urgences | Carte | `[% Admissions Urgences]` |
| Admissions par mois | Graphique en courbes | Axe X : `dim_temps[nom_mois]`, Valeurs : `[Total Admissions]` |
| Répartition par hôpital | Graphique en barres | Axe : `dim_hopital[nom_hopital]`, Valeurs : `[Total Admissions]` |
| Carte des régions | Carte choroplèthe | Localisation : `dim_region[nom_region]`, Taille : `[Total Admissions]` |

### Filtres (Slicers)
- Année (`dim_temps[annee]`)
- Région (`dim_region[nom_region]`)
- Type hôpital (`dim_hopital[type_hopital]`)

---

## Page 2 — Analyse Patients

**Objectif :** Profil démographique et comportement des patients.

### Visuels

| Visuel | Type | Données |
|--------|------|---------|
| Répartition par sexe | Graphique en secteurs (donut) | Légende : `dim_patient[sexe]`, Valeurs : `[Total Admissions]` |
| Distribution par tranche d'âge | Histogramme | Axe : `dim_patient[tranche_age]`, Valeurs : `[Total Admissions]` |
| Âge moyen par sexe | Graphique en barres groupées | Axe : `dim_patient[sexe]`, Valeurs : `[Âge Moyen Patients]` |
| DMS par tranche d'âge | Graphique en barres | Axe : `dim_patient[tranche_age]`, Valeurs : `[DMS Moyen]` |
| Top 10 villes de provenance | Graphique en barres horizontales | Axe : `dim_patient[ville]`, Valeurs : `[Patients Distincts]` |
| Taux réadmission | Carte avec indicateur | `[Taux Réadmission]` |

### Filtres
- Tranche d'âge
- Sexe
- Année

---

## Page 3 — Performance Hôpitaux

**Objectif :** Comparer l'activité et l'efficacité des établissements.

### Visuels

| Visuel | Type | Données |
|--------|------|---------|
| Tableau comparatif hôpitaux | Tableau | Colonnes : Hôpital, Admissions, DMS moy, Coût moy, Taux occup |
| Admissions vs Capacité | Graphique combiné (barres + courbe) | Barres : `[Total Admissions]`, Courbe : `[Capacité Totale Lits]` |
| Taux d'occupation | Graphique en barres | Axe : `dim_hopital[nom_hopital]`, Valeurs : `[Taux Occupation Moyen]` |
| Alertes capacité | Carte + sparkline | `[Alertes Capacité]` |
| Coût moyen par hôpital | Heatmap / tableau coloré | Axe : hôpital, Intensité : `[Coût Moyen Séjour]` |
| Top hôpital | Carte avec titre dynamique | `TOPN(1, dim_hopital, [Total Admissions])` |

### Filtres
- Région
- Type d'hôpital
- Période

---

## Page 4 — Analyse par Région

**Objectif :** Disparités régionales d'accès et de soins.

### Visuels

| Visuel | Type | Données |
|--------|------|---------|
| Carte France | Carte ArcGIS ou Bing | Localisation : `dim_region[nom_region]`, Taille/Couleur : `[Total Admissions]` |
| Admissions pour 100k habitants | Mesure + barres | `DIVIDE([Total Admissions], SUM(dim_region[population]), 0) * 100000` |
| DMS par région | Barres horizontales triées | Axe : `dim_region[nom_region]`, Valeurs : `[DMS Moyen]` |
| Coût total par région | Treemap | Groupe : `dim_region[nom_region]`, Valeurs : `[Coût Total]` |
| Tableau de bord régional | Tableau | Région, Admissions, Patients, DMS, Coût moy |

### Filtres
- Région (slicer multi-sélection)
- Année

---

## Page 5 — Épidémiologie & Maladies

**Objectif :** Suivi des pathologies et tendances épidémiologiques.

### Visuels

| Visuel | Type | Données |
|--------|------|---------|
| Top 10 pathologies | Barres horizontales | Axe : `dim_maladie[nom_maladie]`, Valeurs : `[Total Admissions]` |
| Répartition par catégorie | Donut | Légende : `dim_maladie[categorie]`, Valeurs : `[Total Admissions]` |
| Chronique vs Aiguë | Barres empilées | Groupe : `dim_maladie[Chronique]`, Valeurs : `[Total Admissions]` |
| DMS Chroniques vs Aiguës | Cartes côte à côte | `[DMS Chroniques]` / `[DMS Aiguës]` |
| Évolution mensuelle par catégorie | Courbes multiples | Axe : mois, Séries : catégorie maladie |
| Matrice maladie × région | Heatmap | Lignes : maladie, Colonnes : région, Valeurs : admissions |

### Filtres
- Catégorie de maladie
- Chronique / Aiguë
- Période

---

## Page 6 — Occupation des Lits (IoT)

**Objectif :** Suivi temps réel simulé de l'occupation via les capteurs.

### Visuels

| Visuel | Type | Données |
|--------|------|---------|
| Taux moyen global | Jauge | `[Taux Occupation Moyen]`, Minimum : 0, Maximum : 100, Cible : 85 |
| Pic d'occupation | Carte | `[Pic Occupation]` |
| Alertes déclenchées | Carte (rouge si > 0) | `[Alertes Capacité]` |
| Évolution par heure de la journée | Courbe | Axe : `fact_occupation_lits[heure]`, Valeurs : `[Taux Occupation Moyen]` |
| Occupation par service | Barres | Axe : `fact_occupation_lits[service_id]`, Valeurs : taux moyen |
| Niveaux d'occupation | Donut | Légende : `[Niveau Occupation]`, Valeurs : Count |
| Tableau alertes par hôpital | Tableau conditionnel | Colonnes : Hôpital, Taux moy, Pic, Nb alertes |

### Formatage conditionnel
- Taux occupation : vert < 60%, orange 60–85%, rouge ≥ 85%

---

## Page 7 — Pharmacie & Laboratoires

**Objectif :** Suivi des analyses et de la chaîne médicament.

### Laboratoires

| Visuel | Type | Données |
|--------|------|---------|
| Total analyses | Carte | `[Total Analyses]` |
| Taux d'anomalies | Carte + jauge | `[Taux Anomalies]` |
| Répartition par type d'analyse | Donut | Légende : `fact_laboratoires[type_analyse]` |
| Anomalies par mois | Courbe | Axe : mois, Valeurs : count anomalies |

### Pharmacie

| Visuel | Type | Données |
|--------|------|---------|
| Valeur stock total | Carte | `[Valeur Stock Total]` |
| Médicaments en alerte | Carte (rouge) | `[Ruptures Stock]` |
| % en alerte | Jauge | `[% Alerte Stock]`, cible : < 5% |
| Top médicaments consommés | Barres | `fact_stock_pharmacie[nom_medicament]`, consommation |
| Évolution stock critique | Courbe | Date × `[Ruptures Stock]` |

---

## Modèle de données (Relations)

```
dim_temps      ──────┐
dim_patient    ───┐  │
dim_hopital    ─┐ │  │
dim_maladie    ┐│ │  │
dim_region ──→ dim_hopital
               │  │  │
               └──┼──┼──→ fact_admissions (table centrale)
                  │  │
                  │  └──→ fact_urgences
                  │  └──→ fact_laboratoires
                  │  └──→ fact_prescriptions
                  └──────→ fact_occupation_lits
```

**Cardinalités :**
- `dim_temps[temps_id]` → `fact_admissions[temps_id]` (1:N)
- `dim_patient[patient_id]` → `fact_admissions[patient_id]` (1:N)
- `dim_hopital[hopital_id]` → `fact_admissions[hopital_id]` (1:N)
- `dim_maladie[maladie_id]` → `fact_admissions[maladie_id]` (1:N)
- `dim_region[region_id]` → `dim_hopital[region_id]` (1:N)

---

## Thème visuel recommandé

```json
{
  "name": "Healthcare Analytics",
  "dataColors": [
    "#1565C0", "#0288D1", "#00897B",
    "#F57C00", "#C62828", "#558B2F",
    "#7B1FA2", "#37474F"
  ],
  "background": "#FFFFFF",
  "foreground": "#333333",
  "tableAccent": "#1565C0"
}
```

Chemin dans Power BI : **Affichage > Thèmes > Parcourir les thèmes** → sélectionner `pbi/theme.json`
