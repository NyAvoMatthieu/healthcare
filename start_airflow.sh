#!/usr/bin/env bash
# Démarre l'environnement complet Healthcare Analytics Platform
# Usage : bash start_airflow.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "======================================================"
echo "  Healthcare Analytics Platform — Démarrage Airflow"
echo "======================================================"

# 1. Activer le virtualenv — priorité au venv existant avec Airflow
EXISTING_AIRFLOW_ENV="/home/nyavo/airflow_project/airflow_env"

if [ -f "$EXISTING_AIRFLOW_ENV/bin/airflow" ]; then
  source "$EXISTING_AIRFLOW_ENV/bin/activate"
  echo "  ✓ Virtualenv existant activé : $EXISTING_AIRFLOW_ENV"
elif [ -d "$PROJECT_DIR/venv" ]; then
  source "$PROJECT_DIR/venv/bin/activate"
  echo "  ✓ Virtualenv projet activé"
else
  echo "  Création d'un nouveau virtualenv..."
  python3 -m venv "$PROJECT_DIR/venv"
  source "$PROJECT_DIR/venv/bin/activate"
fi

# 2. Configurer AIRFLOW_HOME
export AIRFLOW_HOME="$PROJECT_DIR/airflow"
echo "  ✓ AIRFLOW_HOME = $AIRFLOW_HOME"

# 3. Vérifier qu'Airflow est installé
if ! python -m airflow version &>/dev/null; then
  echo ""
  echo "  Airflow non trouvé. Installation..."
  pip install -r "$PROJECT_DIR/requirements.txt" -q
  pip install "apache-airflow==3.2.2" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-3.13.txt" \
    -q
  echo "  ✓ Airflow installé"
fi

AIRFLOW_VERSION=$(python -m airflow version 2>/dev/null)
echo "  ✓ Airflow $AIRFLOW_VERSION"

# 4. Initialiser la DB si nécessaire
if [ ! -f "$AIRFLOW_HOME/airflow.db" ]; then
  echo "  Initialisation de la base Airflow..."
  airflow db migrate
  airflow users create \
    --username admin --password admin \
    --firstname Admin --lastname User \
    --role Admin --email admin@localhost.com 2>/dev/null || true
  echo "  ✓ Base Airflow initialisée (admin/admin)"
fi

# 5. Mettre à jour dags_folder dans airflow.cfg
if [ -f "$AIRFLOW_HOME/airflow.cfg" ]; then
  sed -i "s|^dags_folder = .*|dags_folder = $PROJECT_DIR/airflow/dags|" \
    "$AIRFLOW_HOME/airflow.cfg"
  echo "  ✓ dags_folder configuré → $PROJECT_DIR/airflow/dags"
fi

# 6. Démarrer l'API mock en arrière-plan (optionnel)
if ! curl -s http://localhost:5000/health &>/dev/null; then
  echo "  Démarrage de l'API mock..."
  nohup python "$PROJECT_DIR/api/mock_api.py" \
    > "$PROJECT_DIR/logs/mock_api.log" 2>&1 &
  echo "  ✓ API mock démarrée (http://localhost:5000)"
fi

echo ""
echo "======================================================"
echo "  Lancement d'Airflow standalone..."
echo "  UI disponible sur : http://localhost:8080"
echo "  Login : admin / admin"
echo "  Arrêt : Ctrl+C"
echo "======================================================"
echo ""

airflow standalone
