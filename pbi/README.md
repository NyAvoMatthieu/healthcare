# Power BI — Healthcare Analytics Platform

## Contenu du dossier pbi/

| Fichier | Description |
|---------|-------------|
| `export_for_powerbi.py` | Exporte le warehouse SQLite → Excel multi-onglets |
| `healthcare_powerbi.xlsx` | *(généré)* Fichier Excel source pour Power BI |
| `measures.dax` | Toutes les mesures DAX à copier-coller |
| `queries_powerquery.pq` | Scripts Power Query M pour chaque table |
| `report_plan.md` | Plan détaillé page par page (visuels + données) |
| `theme.json` | Thème couleur bleu médical pour Power BI |

---

## Étape 1 — Générer le fichier Excel

```bash
# Depuis la racine du projet
source /home/nyavo/airflow_project/airflow_env/bin/activate
python pbi/export_for_powerbi.py
```

→ Produit `pbi/healthcare_powerbi.xlsx` (~5 Mo, 14 onglets)

---

## Étape 2 — Importer dans Power BI Desktop

1. Ouvrir **Power BI Desktop**
2. **Accueil > Obtenir les données > Excel**
3. Sélectionner `pbi/healthcare_powerbi.xlsx`
4. Cocher **toutes les feuilles** sauf `_Metadonnees`
5. Cliquer **Charger**

---

## Étape 3 — Appliquer le thème

1. **Affichage > Thèmes > Parcourir les thèmes**
2. Sélectionner `pbi/theme.json`

---

## Étape 4 — Appliquer les transformations Power Query (optionnel)

Les transformations de `queries_powerquery.pq` ajoutent des colonnes calculées
utiles (Catégorie DMS, Niveau Occupation, Statut Résultat...).

Pour chaque bloc du fichier `.pq` :
1. **Transformer les données** (bouton Power Query)
2. Cliquer sur la requête correspondante (ex: `fact_admissions`)
3. **Affichage > Éditeur avancé**
4. Remplacer le contenu par le bloc du fichier `.pq`
5. **Fermer et appliquer**

> Mettez à jour `CheminExcel` avec votre chemin local.

---

## Étape 5 — Créer les mesures DAX

1. Dans le panneau **Données**, cliquer droit > **Nouvelle table**
   ```
   _Mesures = {""}
   ```
2. Sélectionner la table `_Mesures`
3. **Modélisation > Nouvelle mesure**
4. Copier-coller chaque bloc de `measures.dax`

> Commencer par les mesures simples (Total Admissions, DMS Moyen)
> avant les mesures avec DATEADD qui nécessitent une table de dates active.

---

## Étape 6 — Configurer les relations

Dans **Modélisation > Gérer les relations**, vérifier ou créer :

| Table source | Clé | Table cible | Clé | Cardinalité |
|---|---|---|---|---|
| `fact_admissions` | `patient_id` | `dim_patient` | `patient_id` | N:1 |
| `fact_admissions` | `hopital_id` | `dim_hopital` | `hopital_id` | N:1 |
| `fact_admissions` | `maladie_id` | `dim_maladie` | `maladie_id` | N:1 |
| `fact_admissions` | `temps_id` | `dim_temps` | `temps_id` | N:1 |
| `dim_hopital` | `region_id` | `dim_region` | `region_id` | N:1 |
| `fact_urgences` | `hopital_id` | `dim_hopital` | `hopital_id` | N:1 |
| `fact_laboratoires` | `patient_id` | `dim_patient` | `patient_id` | N:1 |
| `fact_occupation_lits` | `hopital_id` | `dim_hopital` | `hopital_id` | N:1 |

> Si `analytics_mart` est chargée, elle peut être utilisée seule (table dénormalisée)
> sans avoir besoin des relations ci-dessus.

---

## Étape 7 — Construire les pages

Suivre `report_plan.md` qui détaille les 7 pages :

| Page | Contenu principal |
|------|-------------------|
| 1 — Vue Générale | KPI cards + courbe mensuelle + carte régions |
| 2 — Patients | Démographie, tranches d'âge, villes |
| 3 — Hôpitaux | Comparaison, taux occupation, coûts |
| 4 — Régions | Carte France, admissions / 100k habitants |
| 5 — Épidémiologie | Top pathologies, chronique vs aiguë |
| 6 — Occupation Lits | Capteurs IoT, alertes, heatmap horaire |
| 7 — Pharmacie & Labos | Stock, anomalies, prescriptions |

---

## Rafraîchir les données

Quand les DAGs Airflow ont tourné et produit de nouvelles données :

```bash
python pbi/export_for_powerbi.py
```

Dans Power BI : **Accueil > Actualiser**

---

## Astuce — Mode analyse directe (sans export)

Si vous installez **SQLite ODBC Driver** (Windows) :
- Source : ODBC > DSN SQLite → `warehouse/warehouse.db`
- Aucun export Excel nécessaire, les données sont lues en direct
