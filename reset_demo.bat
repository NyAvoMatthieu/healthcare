@echo off
REM =============================================================================
REM reset_demo.bat — Réinitialisation complète pour démonstration (Windows)
REM
REM Usage :
REM   reset_demo.bat          reset complet (données + DBs + rapports)
REM   reset_demo.bat soft     reset léger (DBs uniquement)
REM =============================================================================
setlocal EnableDelayedExpansion

set BASE_DIR=%~dp0
set BASE_DIR=%BASE_DIR:~0,-1%
set SCRIPTS_DIR=%BASE_DIR%\scripts
set AIRFLOW_VENV=C:\airflow_project\airflow_env
set AIRFLOW_HOME=%BASE_DIR%\airflow

set MODE=full
if /I "%1"=="soft" set MODE=soft
if /I "%1"=="--soft" set MODE=soft
if /I "%1"=="--help" goto :help
goto :main

:help
echo Usage: reset_demo.bat [soft]
echo   (aucun argument) : reset complet — supprime données, DBs, rapports
echo   soft             : reset leger  — supprime DBs et rapports seulement
exit /b 0

:main
echo.
echo ============================================================
echo    Healthcare Analytics Platform - Reset Demonstration
echo ============================================================
echo.
echo  Mode : %MODE%
echo.
set /p CONFIRM=" Confirmer le reset ? [o/N] : "
if /I not "%CONFIRM%"=="o" if /I not "%CONFIRM%"=="y" (
    echo  Annule.
    exit /b 0
)
echo.

REM ── 1. Arrêt processus ────────────────────────────────────────────────────
echo [1/5] Arret des processus en cours...
taskkill /F /IM python.exe /T 2>nul && echo   OK  Python arrete || echo   i  Aucun processus Python
echo.

REM ── 2. Suppression bases de données ──────────────────────────────────────
echo [2/5] Suppression des bases de donnees...
for %%f in (
    "%BASE_DIR%\staging\staging.db"
    "%BASE_DIR%\staging\staging.db-shm"
    "%BASE_DIR%\staging\staging.db-wal"
    "%BASE_DIR%\warehouse\warehouse.db"
    "%BASE_DIR%\warehouse\warehouse.db-shm"
    "%BASE_DIR%\warehouse\warehouse.db-wal"
) do (
    if exist %%f (
        del /F /Q %%f
        echo   OK  Supprime : %%~nxf
    )
)
echo.

REM ── 3. Suppression rapports ───────────────────────────────────────────────
echo [3/5] Suppression des rapports...
if exist "%BASE_DIR%\reports\*.html" del /F /Q "%BASE_DIR%\reports\*.html"
if exist "%BASE_DIR%\reports\*.csv"  del /F /Q "%BASE_DIR%\reports\*.csv"
echo   OK  Rapports supprimes
echo.

REM ── 4. Reset complet : données ────────────────────────────────────────────
if "%MODE%"=="full" (
    echo [4/5] Suppression des fichiers de donnees...
    for %%e in (csv xlsx xml json) do (
        if exist "%BASE_DIR%\data\*.%%e" (
            del /F /Q "%BASE_DIR%\data\*.%%e"
            echo   OK  Supprime : data\*.%%e
        )
    )
    REM Logs Airflow
    if exist "%AIRFLOW_HOME%\logs" (
        for /R "%AIRFLOW_HOME%\logs" %%f in (*.log) do del /F /Q "%%f" 2>nul
        echo   OK  Logs Airflow supprimes
    )
) else (
    echo [4/5] Mode soft - fichiers data\ conserves
)
echo.

REM ── 5. Régénération ───────────────────────────────────────────────────────
echo [5/5] Regeneration des donnees...
echo.

REM Trouver Python (venv ou système)
if exist "%AIRFLOW_VENV%\Scripts\python.exe" (
    set PYTHON=%AIRFLOW_VENV%\Scripts\python.exe
) else if exist "%BASE_DIR%\venv\Scripts\python.exe" (
    set PYTHON=%BASE_DIR%\venv\Scripts\python.exe
) else (
    set PYTHON=python
)

cd /d "%BASE_DIR%"

if "%MODE%"=="full" (
    echo   Generating CSV...
    "%PYTHON%" "%SCRIPTS_DIR%\generate_data.py"
    if !errorlevel! neq 0 goto :error

    echo   Generating Excel...
    "%PYTHON%" "%SCRIPTS_DIR%\generate_excel.py"
    if !errorlevel! neq 0 goto :error

    echo   Generating XML...
    "%PYTHON%" "%SCRIPTS_DIR%\generate_xml.py"
    if !errorlevel! neq 0 goto :error

    echo   Generating JSON...
    "%PYTHON%" "%SCRIPTS_DIR%\generate_json.py"
    if !errorlevel! neq 0 goto :error
)

echo   Initialisation staging + warehouse...
"%PYTHON%" "%SCRIPTS_DIR%\init_project.py"
if %errorlevel% neq 0 goto :error

REM ── Résumé ────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo    Reset termine avec succes !
echo ============================================================
echo.
echo  Prochaines etapes :
echo.
echo  1. Demarrer l'API (terminal 1) :
echo     python api\mock_api.py
echo.
echo  2. Demarrer Airflow (terminal 2) :
echo     start_airflow.bat
echo.
echo  3. Ouvrir l'UI : http://localhost:8080
echo     Login : admin / BVxruwEMkCt3mRQA
echo.
echo  4. Declencher les DAGs dans l'ordre :
echo     ingestion_* -> nettoyage -> consolidation -> rapport
echo.
goto :end

:error
echo.
echo  ERREUR lors de la regeneration — verifiez les messages ci-dessus.
exit /b 1

:end
endlocal
