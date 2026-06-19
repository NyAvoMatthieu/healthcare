@echo off
:: ======================================================
:: Healthcare Analytics Platform — Démarrage Airflow
:: Usage : double-clic ou start_airflow.bat
:: Testé sur Windows 10/11 avec Python 3.10+
:: ======================================================

setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
:: Supprimer le backslash final
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo.
echo ======================================================
echo   Healthcare Analytics Platform -- Demarrage Airflow
echo ======================================================
echo   Repertoire : %PROJECT_DIR%
echo.

:: ----------------------------------------------------------
:: 1. Créer/activer le virtualenv
:: ----------------------------------------------------------
:: Priorité au virtualenv existant contenant déjà Airflow
set "EXISTING_ENV=C:\Users\%USERNAME%\airflow_project\airflow_env"

if exist "%EXISTING_ENV%\Scripts\airflow.exe" (
    call "%EXISTING_ENV%\Scripts\activate.bat"
    echo   OK Virtualenv existant active : %EXISTING_ENV%
) else if exist "%PROJECT_DIR%\venv\Scripts\activate.bat" (
    call "%PROJECT_DIR%\venv\Scripts\activate.bat"
    echo   OK Virtualenv projet active
) else (
    echo   Creation du virtualenv...
    python -m venv "%PROJECT_DIR%\venv"
    if errorlevel 1 (
        echo   ERREUR : Python introuvable. Verifiez que Python est dans le PATH.
        pause & exit /b 1
    )
    call "%PROJECT_DIR%\venv\Scripts\activate.bat"
    echo   OK Virtualenv cree et active
)

:: ----------------------------------------------------------
:: 2. Configurer AIRFLOW_HOME (obligatoire sur Windows)
:: ----------------------------------------------------------
set "AIRFLOW_HOME=%PROJECT_DIR%\airflow"
echo   OK AIRFLOW_HOME = %AIRFLOW_HOME%

:: Airflow requiert ces variables sur Windows
set "AIRFLOW__CORE__DAGS_FOLDER=%PROJECT_DIR%\airflow\dags"
set "AIRFLOW__CORE__LOAD_EXAMPLES=False"

:: ----------------------------------------------------------
:: 3. Installer les dépendances si nécessaire
:: ----------------------------------------------------------
python -m airflow version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Airflow non trouve. Installation en cours (5-10 min)...
    pip install -r "%PROJECT_DIR%\requirements.txt" -q
    if errorlevel 1 (
        echo   ERREUR lors de l'installation de requirements.txt
        pause & exit /b 1
    )

    :: Détecter la version Python pour les contraintes
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do set PYMAJ=%%a& set PYMIN=%%b
    set "CONSTRAINT_URL=https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-!PYMAJ!.!PYMIN!.txt"

    echo   Contraintes : !CONSTRAINT_URL!
    pip install "apache-airflow==3.2.2" --constraint "!CONSTRAINT_URL!" -q
    if errorlevel 1 (
        echo   ERREUR lors de l'installation d'Airflow.
        echo   Essayez manuellement :
        echo     pip install apache-airflow==3.2.2 --constraint %CONSTRAINT_URL%
        pause & exit /b 1
    )
    echo   OK Airflow installe
)

for /f "delims=" %%v in ('python -m airflow version 2^>nul') do set AV=%%v
echo   OK Airflow %AV%

:: ----------------------------------------------------------
:: 4. Initialiser la base de données Airflow
:: ----------------------------------------------------------
if not exist "%AIRFLOW_HOME%\airflow.db" (
    echo.
    echo   Initialisation de la base Airflow...
    airflow db migrate
    if errorlevel 1 (
        echo   ERREUR : airflow db migrate a echoue.
        pause & exit /b 1
    )
    airflow users create ^
        --username admin ^
        --password admin ^
        --firstname Admin ^
        --lastname User ^
        --role Admin ^
        --email admin@localhost.com >nul 2>&1
    echo   OK Base Airflow initialisee  (login : admin / admin)
)

:: ----------------------------------------------------------
:: 5. Forcer le dossier des DAGs via variable d'environnement
::    (plus fiable que de modifier airflow.cfg sur Windows)
:: ----------------------------------------------------------
set "AIRFLOW__CORE__DAGS_FOLDER=%PROJECT_DIR%\airflow\dags"
echo   OK DAGs folder = %AIRFLOW__CORE__DAGS_FOLDER%

:: ----------------------------------------------------------
:: 6. Démarrer l'API mock en arrière-plan (optionnel)
:: ----------------------------------------------------------
curl -s http://localhost:5000/health >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Demarrage de l'API mock en arriere-plan...
    if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"
    start /B python "%PROJECT_DIR%\api\mock_api.py" ^
        > "%PROJECT_DIR%\logs\mock_api.log" 2>&1
    echo   OK API mock sur http://localhost:5000
)

:: ----------------------------------------------------------
:: 7. Lancer Airflow standalone
:: ----------------------------------------------------------
echo.
echo ======================================================
echo   Lancement d'Airflow standalone...
echo   UI disponible sur : http://localhost:8080
echo   Login : admin / admin
echo   Arret : Ctrl+C dans cette fenetre
echo ======================================================
echo.

airflow standalone

echo.
echo   Airflow arrete.
pause
