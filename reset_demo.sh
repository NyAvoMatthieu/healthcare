#!/usr/bin/env bash
# =============================================================================
# reset_demo.sh — Réinitialisation complète pour démonstration
#
# Usage :
#   ./reset_demo.sh          # reset complet (données + DBs + rapports)
#   ./reset_demo.sh --soft   # reset DBs uniquement (garde les fichiers data/)
#   ./reset_demo.sh --help
# =============================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
AIRFLOW_VENV="/home/nyavo/airflow_project/airflow_env"
AIRFLOW_HOME="$BASE_DIR/airflow"
SCRIPTS_DIR="$BASE_DIR/scripts"
PYTHON="$AIRFLOW_VENV/bin/python"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

MODE="full"
[[ "${1:-}" == "--soft" ]] && MODE="soft"
[[ "${1:-}" == "--help" ]] && {
    echo "Usage: ./reset_demo.sh [--soft]"
    echo "  (aucun argument) : reset complet — supprime données, DBs, rapports, logs Airflow"
    echo "  --soft           : reset léger  — supprime DBs et rapports seulement"
    exit 0
}

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Healthcare Analytics Platform — Reset Démonstration    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Mode : ${YELLOW}$MODE${NC}"
echo ""

# ── Confirmation ──────────────────────────────────────────────────────────────
read -rp "  Confirmer le reset ? [o/N] " CONFIRM
[[ "$CONFIRM" =~ ^[oOyY]$ ]] || { echo "  Annulé."; exit 0; }
echo ""

# ── 1. Arrêter les processus en cours ────────────────────────────────────────
echo -e "${YELLOW}[1/5] Arrêt des processus en cours...${NC}"

pkill -f "airflow" 2>/dev/null && echo "  ✓ Airflow arrêté" || echo "  ℹ Airflow non actif"
pkill -f "mock_api.py" 2>/dev/null && echo "  ✓ API arrêtée" || echo "  ℹ API non active"
sleep 1

# ── 2. Suppression des bases de données ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/5] Suppression des bases de données...${NC}"

for f in "$BASE_DIR/staging/staging.db" \
          "$BASE_DIR/staging/staging.db-shm" \
          "$BASE_DIR/staging/staging.db-wal" \
          "$BASE_DIR/warehouse/warehouse.db" \
          "$BASE_DIR/warehouse/warehouse.db-shm" \
          "$BASE_DIR/warehouse/warehouse.db-wal"; do
    [[ -f "$f" ]] && rm -f "$f" && echo "  ✓ Supprimé : $(basename $f)"
done

# ── 3. Suppression des rapports ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/5] Suppression des rapports...${NC}"
rm -f "$BASE_DIR/reports/"*.html "$BASE_DIR/reports/"*.csv 2>/dev/null \
    && echo "  ✓ Rapports supprimés" || echo "  ℹ Aucun rapport à supprimer"

# ── 4. Reset complet : données + logs Airflow ─────────────────────────────────
if [[ "$MODE" == "full" ]]; then
    echo ""
    echo -e "${YELLOW}[4/5] Suppression des fichiers de données et logs Airflow...${NC}"

    # Données générées
    for f in "$BASE_DIR/data/"*.csv \
              "$BASE_DIR/data/"*.xlsx \
              "$BASE_DIR/data/"*.xml \
              "$BASE_DIR/data/"*.json; do
        [[ -f "$f" ]] && rm -f "$f" && echo "  ✓ Supprimé : data/$(basename $f)"
    done

    # Logs Airflow (runs history)
    if [[ -d "$AIRFLOW_HOME/logs" ]]; then
        find "$AIRFLOW_HOME/logs" -name "*.log" -delete 2>/dev/null
        echo "  ✓ Logs Airflow supprimés"
    fi

    # Cache Python
    find "$SCRIPTS_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    echo "  ✓ Cache Python supprimé"
else
    echo ""
    echo -e "${YELLOW}[4/5] Mode soft — fichiers data/ conservés${NC}"
fi

# ── 5. Régénération complète ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/5] Régénération des données...${NC}"
echo ""

source "$AIRFLOW_VENV/bin/activate"
export AIRFLOW_HOME="$AIRFLOW_HOME"

cd "$BASE_DIR"

if [[ "$MODE" == "full" ]]; then
    echo "  → Génération CSV..."
    $PYTHON "$SCRIPTS_DIR/generate_data.py" && echo "  ✓ CSV générés"

    echo "  → Génération Excel..."
    $PYTHON "$SCRIPTS_DIR/generate_excel.py" && echo "  ✓ Excel généré"

    echo "  → Génération XML..."
    $PYTHON "$SCRIPTS_DIR/generate_xml.py" && echo "  ✓ XML généré"

    echo "  → Génération JSON..."
    $PYTHON "$SCRIPTS_DIR/generate_json.py" && echo "  ✓ JSON générés"
fi

echo ""
echo "  → Initialisation staging + warehouse + transformations..."
$PYTHON "$SCRIPTS_DIR/init_project.py"

# ── Réinitialiser les runs Airflow (optionnel) ────────────────────────────────
echo ""
echo "  → Remise à zéro des runs Airflow..."
for dag in ingestion_csv_patients ingestion_csv_admissions \
           ingestion_api_maladies ingestion_multi_format \
           ingestion_mysql nettoyage_groupement \
           consolidation_donnees rapport_email; do
    airflow dags unpause "$dag" 2>/dev/null || true
done
echo "  ✓ Tous les DAGs actifs"

# ── Résumé final ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Reset terminé avec succès !                 ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  Prochaines étapes :                                     ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  1. Démarrer l'API (terminal 1) :                        ║${NC}"
echo -e "${GREEN}║     python api/mock_api.py                               ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  2. Démarrer Airflow (terminal 2) :                      ║${NC}"
echo -e "${GREEN}║     ./start_airflow.sh                                   ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  3. Ouvrir l'UI : http://localhost:8080                  ║${NC}"
echo -e "${GREEN}║     Login : admin / BVxruwEMkCt3mRQA                    ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  4. Déclencher les DAGs dans l'ordre :                   ║${NC}"
echo -e "${GREEN}║     ingestion_* → nettoyage → consolidation → rapport    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
