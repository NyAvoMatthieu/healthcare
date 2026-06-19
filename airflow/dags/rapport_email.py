"""
DAG : rapport_email
Génère un rapport HTML hebdomadaire des KPIs Healthcare et l'envoie par email.

Si l'envoi SMTP est désactivé (email.enabled=false dans config.yaml),
le rapport est uniquement sauvegardé dans reports/ sans erreur.

Étapes :
  1. generer_rapport_html  – construit le rapport HTML avec KPIs + tableaux
  2. sauvegarder_rapport   – écrit le fichier dans reports/
  3. envoyer_email         – envoie via SMTP (ou log si désactivé)

Schedule : hebdomadaire (@weekly)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

default_args = {
    "owner":            "healthcare_etl",
    "depends_on_past":  False,
    "email_on_failure": False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=10),
    "start_date":       datetime(2024, 1, 1),
}

dag = DAG(
    "rapport_email",
    default_args=default_args,
    description="Rapport hebdomadaire KPI Healthcare → HTML + email optionnel",
    schedule="@weekly",
    catchup=False,
    tags=["rapport", "email", "kpi", "hebdomadaire"],
    doc_md="""
## rapport_email

Génère et envoie le rapport hebdomadaire des KPIs.

**Configuration email** : `config/config.yaml` → section `email`
- `enabled: false` → rapport sauvegardé uniquement dans `reports/`
- `enabled: true`  → rapport envoyé par SMTP + sauvegardé

**Destinataires par défaut** : définis dans `email.to_addrs`
    """,
)


# ── Helpers HTML ──────────────────────────────────────────────────────────────

def _html_kpi_card(titre: str, valeur: str, unite: str = "", couleur: str = "#2196F3") -> str:
    return f"""
    <div style="display:inline-block;margin:10px;padding:20px 30px;
                background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.12);
                border-left:5px solid {couleur};min-width:180px;vertical-align:top">
      <div style="font-size:13px;color:#777;text-transform:uppercase;letter-spacing:1px">{titre}</div>
      <div style="font-size:32px;font-weight:700;color:#222;margin:8px 0">{valeur}</div>
      <div style="font-size:13px;color:#999">{unite}</div>
    </div>"""


def _html_table(df, max_rows: int = 15) -> str:
    import pandas as pd
    if df is None or df.empty:
        return "<p style='color:#999;font-style:italic'>Aucune donnée disponible.</p>"
    df = df.head(max_rows)
    header = "".join(
        f"<th style='background:#37474f;color:#fff;padding:8px 12px;text-align:left'>{c}</th>"
        for c in df.columns
    )
    rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        bg = "#f5f5f5" if i % 2 == 0 else "#fff"
        cells = "".join(
            f"<td style='padding:7px 12px;border-bottom:1px solid #eee'>{v}</td>"
            for v in row
        )
        rows += f"<tr style='background:{bg}'>{cells}</tr>"
    return f"""
    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <thead><tr>{header}</tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


# ── 1. GÉNÉRER RAPPORT HTML ───────────────────────────────────────────────────

def _generer_rapport(**ctx):
    import pandas as pd
    from db_utils import get_warehouse_engine, load_config

    wh      = get_warehouse_engine()
    cfg     = load_config()
    date_fr = datetime.utcnow().strftime("%d/%m/%Y")
    semaine = datetime.utcnow().strftime("Semaine %W – %Y")

    # ── Lecture KPI cache ─────────────────────────────────────────────────────
    kpis = {}
    try:
        df_kpi = pd.read_sql("SELECT kpi, valeur FROM kpi_cache", wh)
        kpis   = dict(zip(df_kpi["kpi"], df_kpi["valeur"]))
    except Exception:
        pass

    def kv(key, defaut="N/A"):
        return kpis.get(key, defaut)

    # ── Tableaux analytiques ──────────────────────────────────────────────────
    def safe_sql(sql, label):
        try:
            return pd.read_sql(sql, wh)
        except Exception as e:
            print(f"  ⚠ {label}: {e}")
            return pd.DataFrame()

    df_maladies = safe_sql("""
        SELECT m.nom_maladie AS Maladie, m.categorie AS Catégorie,
               COUNT(*) AS Admissions,
               ROUND(AVG(fa.duree_sejour),1) AS "DMS moy."
        FROM fact_admissions fa
        JOIN dim_maladie m ON fa.maladie_id = m.maladie_id
        GROUP BY m.nom_maladie, m.categorie
        ORDER BY Admissions DESC LIMIT 10
    """, "top maladies")

    df_hopitaux = safe_sql("""
        SELECT h.nom_hopital AS Hôpital, r.nom_region AS Région,
               COUNT(*) AS Admissions,
               ROUND(AVG(fa.duree_sejour),1) AS "DMS moy.",
               ROUND(AVG(fa.cout_hospitalisation),0) AS "Coût moy. (€)"
        FROM fact_admissions fa
        JOIN dim_hopital h ON fa.hopital_id = h.hopital_id
        LEFT JOIN dim_region r ON h.region_id = r.region_id
        GROUP BY h.nom_hopital, r.nom_region
        ORDER BY Admissions DESC LIMIT 8
    """, "top hôpitaux")

    df_regions = safe_sql("""
        SELECT r.nom_region AS Région,
               COUNT(*) AS Admissions,
               COUNT(DISTINCT fa.patient_id) AS "Patients uniques",
               ROUND(AVG(fa.cout_hospitalisation),0) AS "Coût moy. (€)"
        FROM fact_admissions fa
        JOIN dim_hopital h ON fa.hopital_id = h.hopital_id
        JOIN dim_region r ON h.region_id = r.region_id
        GROUP BY r.nom_region ORDER BY Admissions DESC
    """, "régions")

    df_mensuel = safe_sql("""
        SELECT t.annee AS Année, t.nom_mois AS Mois,
               COUNT(*) AS Admissions,
               ROUND(AVG(fa.duree_sejour),1) AS "DMS moy.",
               ROUND(SUM(fa.cout_hospitalisation),0) AS "CA total (€)"
        FROM fact_admissions fa
        JOIN dim_temps t ON fa.temps_id = t.temps_id
        GROUP BY t.annee, t.mois, t.nom_mois
        ORDER BY t.annee DESC, t.mois DESC LIMIT 12
    """, "tendance mensuelle")

    df_sexe = safe_sql("""
        SELECT p.sexe AS Sexe,
               COUNT(*) AS Admissions,
               ROUND(AVG(p.age),1) AS "Âge moyen",
               ROUND(AVG(fa.duree_sejour),1) AS "DMS moy."
        FROM fact_admissions fa
        JOIN dim_patient p ON fa.patient_id = p.patient_id
        GROUP BY p.sexe
    """, "répartition sexe")

    df_occupation = safe_sql("""
        SELECT h.nom_hopital AS Hôpital,
               ROUND(AVG(fo.taux_occupation),1) AS "Taux occup. moy (%)",
               MAX(fo.taux_occupation) AS "Pic max (%)",
               SUM(fo.alertes) AS "Nb alertes"
        FROM fact_occupation_lits fo
        JOIN dim_hopital h ON fo.hopital_id = h.hopital_id
        GROUP BY h.nom_hopital
        ORDER BY "Taux occup. moy (%)" DESC LIMIT 8
    """, "occupation lits")

    # ── Construction HTML ─────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Rapport Healthcare Analytics – {date_fr}</title>
  <style>
    * {{ box-sizing:border-box; margin:0; padding:0 }}
    body {{ font-family:'Segoe UI',Arial,sans-serif; background:#f0f2f5; color:#333 }}
    .header {{ background:linear-gradient(135deg,#1565c0,#0288d1);
               color:#fff; padding:40px 50px }}
    .header h1 {{ font-size:28px; font-weight:300; letter-spacing:1px }}
    .header .sub {{ font-size:14px; opacity:.8; margin-top:6px }}
    .section {{ background:#fff; margin:20px 40px; border-radius:10px;
                padding:30px; box-shadow:0 2px 8px rgba(0,0,0,.08) }}
    .section h2 {{ font-size:18px; color:#1565c0; border-bottom:2px solid #e3f2fd;
                   padding-bottom:10px; margin-bottom:20px }}
    .kpis {{ padding:20px 40px; background:#e8eaf6 }}
    .footer {{ text-align:center; padding:30px; color:#999; font-size:12px }}
    .badge {{ display:inline-block; padding:3px 10px; border-radius:12px;
              font-size:12px; font-weight:600 }}
    .badge-ok {{ background:#e8f5e9; color:#388e3c }}
    .badge-warn {{ background:#fff3e0; color:#f57c00 }}
  </style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <h1>Healthcare Analytics Platform</h1>
  <div class="sub">Rapport hebdomadaire automatisé &nbsp;·&nbsp; {semaine} &nbsp;·&nbsp; Généré le {date_fr}</div>
</div>

<!-- KPI CARDS -->
<div class="kpis">
  <h2 style="font-size:15px;color:#3f51b5;margin-bottom:15px">Indicateurs Clés de Performance</h2>
  {_html_kpi_card("Admissions totales",   kv("nb_admissions_total"),     "admissions",    "#1565c0")}
  {_html_kpi_card("Patients distincts",   kv("nb_patients_distincts"),   "patients",      "#0288d1")}
  {_html_kpi_card("DMS moyen",            kv("dms_moyen"),               "jours",         "#00897b")}
  {_html_kpi_card("Taux occupation",      kv("taux_occupation_moyen"),   "%",             "#f57c00")}
  {_html_kpi_card("Coût moyen / séjour",  kv("cout_moyen_sejour"),       "€",             "#7b1fa2")}
  {_html_kpi_card("Admissions urgences",  kv("pct_mode_urgence"),        "% via urgences","#c62828")}
  {_html_kpi_card("Maladies référencées", kv("nb_maladies_distinctes"),  "pathologies",   "#558b2f")}
  {_html_kpi_card("Hôpitaux actifs",      kv("nb_hopitaux_actifs"),      "établissements","#37474f")}
</div>

<!-- TOP MALADIES -->
<div class="section">
  <h2>Top 10 Pathologies – Admissions & Durée de Séjour</h2>
  {_html_table(df_maladies)}
</div>

<!-- TOP HÔPITAUX -->
<div class="section">
  <h2>Performance par Hôpital</h2>
  {_html_table(df_hopitaux)}
</div>

<!-- RÉGIONS -->
<div class="section">
  <h2>Activité par Région</h2>
  {_html_table(df_regions)}
</div>

<!-- RÉPARTITION PAR SEXE -->
<div class="section">
  <h2>Répartition par Genre</h2>
  {_html_table(df_sexe)}
</div>

<!-- OCCUPATION LITS -->
<div class="section">
  <h2>Occupation des Lits (Capteurs IoT)</h2>
  {_html_table(df_occupation)}
</div>

<!-- TENDANCE MENSUELLE -->
<div class="section">
  <h2>Tendance Mensuelle (12 derniers mois)</h2>
  {_html_table(df_mensuel)}
</div>

<!-- FOOTER -->
<div class="footer">
  Généré automatiquement par <strong>Healthcare Analytics Platform</strong>
  via Apache Airflow &nbsp;·&nbsp; DAG <code>rapport_email</code>
  &nbsp;·&nbsp; {date_fr}
</div>

</body>
</html>"""

    ctx["ti"].xcom_push(key="html_content", value=html)
    print(f"  ✓ Rapport HTML généré ({len(html):,} caractères)")


# ── 2. SAUVEGARDER RAPPORT ────────────────────────────────────────────────────

def _sauvegarder_rapport(**ctx):
    from db_utils import load_config

    html      = ctx["ti"].xcom_pull(key="html_content", task_ids="generer_rapport_html")
    cfg       = load_config()
    date_str  = datetime.utcnow().strftime("%Y-%m-%d")

    reports_dir = Path(cfg["paths"]["base_dir"]) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    html_path = reports_dir / f"rapport_hebdo_{date_str}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  ✓ Rapport sauvegardé : {html_path}")

    # Garder seulement les 10 derniers rapports
    rapports = sorted(reports_dir.glob("rapport_hebdo_*.html"))
    for ancien in rapports[:-10]:
        ancien.unlink()
        print(f"  ✗ Ancien rapport supprimé : {ancien.name}")

    ctx["ti"].xcom_push(key="html_path", value=str(html_path))


# ── 3. ENVOYER EMAIL ──────────────────────────────────────────────────────────

def _envoyer_email(**ctx):
    """
    Envoie le rapport par email si email.enabled=true dans config.yaml.
    Sinon, affiche un résumé sans erreur.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    from email.mime.base      import MIMEBase
    from email                import encoders
    from db_utils import load_config, get_staging_engine, log_etl

    cfg       = load_config()
    email_cfg = cfg.get("email", {})
    html      = ctx["ti"].xcom_pull(key="html_content", task_ids="generer_rapport_html")
    html_path = ctx["ti"].xcom_pull(key="html_path",    task_ids="sauvegarder_rapport")
    date_fr   = datetime.utcnow().strftime("%d/%m/%Y")

    if not email_cfg.get("enabled", False):
        print("  ℹ Email désactivé (email.enabled=false dans config.yaml)")
        print(f"  → Rapport disponible ici : {html_path}")
        print("  → Pour activer l'envoi, éditez config/config.yaml :")
        print("       email:")
        print("         enabled: true")
        print("         smtp_user: votre@gmail.com")
        print("         smtp_password: mot_de_passe_application")
        log_etl(get_staging_engine(), "rapport_email", "envoyer_email",
                "SKIPPED", 0, source="email_disabled")
        return

    # Construction du message
    subject = (f"{email_cfg.get('subject_prefix','[Healthcare]')} "
               f"Rapport hebdomadaire – {date_fr}")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = email_cfg["from_addr"]
    msg["To"]      = ", ".join(email_cfg["to_addrs"])

    # Corps HTML
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Pièce jointe HTML
    try:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(Path(html_path).read_bytes())
        encoders.encode_base64(part)
        filename = Path(html_path).name
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)
    except Exception as e:
        print(f"  ⚠ Impossible d'attacher le fichier: {e}")

    # Envoi SMTP
    try:
        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(email_cfg["smtp_user"], email_cfg["smtp_password"])
            server.sendmail(
                email_cfg["from_addr"],
                email_cfg["to_addrs"],
                msg.as_string()
            )
        destinataires = ", ".join(email_cfg["to_addrs"])
        print(f"  ✓ Email envoyé à : {destinataires}")
        log_etl(get_staging_engine(), "rapport_email", "envoyer_email",
                "SUCCESS", 1, source=destinataires)
    except Exception as e:
        print(f"  ✗ Échec envoi email : {e}")
        log_etl(get_staging_engine(), "rapport_email", "envoyer_email",
                "ERROR", 0, error=str(e))
        raise


# ── Task wiring ───────────────────────────────────────────────────────────────

t_generer    = PythonOperator(task_id="generer_rapport_html", python_callable=_generer_rapport,    dag=dag)
t_sauvegarder= PythonOperator(task_id="sauvegarder_rapport",  python_callable=_sauvegarder_rapport,dag=dag)
t_email      = PythonOperator(task_id="envoyer_email",        python_callable=_envoyer_email,      dag=dag)

t_generer >> t_sauvegarder >> t_email
