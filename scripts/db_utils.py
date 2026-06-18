"""Shared database utilities — path resolution and connection helpers."""
import os
import sqlite3
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text


def load_config() -> dict:
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_db_path(relative: str) -> Path:
    base = Path(__file__).resolve().parent.parent
    return base / relative


def get_staging_engine():
    cfg  = load_config()
    path = resolve_db_path(cfg["paths"]["staging_db"])
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def get_warehouse_engine():
    cfg  = load_config()
    path = resolve_db_path(cfg["paths"]["warehouse_db"])
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def get_mysql_engine():
    cfg = load_config()["mysql"]
    url = (
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        f"?charset={cfg['charset']}"
    )
    return create_engine(url, echo=False)


def init_staging():
    """Create staging schema if not already present."""
    engine   = get_staging_engine()
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_staging.sql"
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        for stmt in sql_path.read_text(encoding="utf-8").split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
        conn.commit()


def init_warehouse():
    """Create warehouse schema if not already present."""
    engine   = get_warehouse_engine()
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_warehouse.sql"
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("PRAGMA journal_mode=WAL"))
        for stmt in sql_path.read_text(encoding="utf-8").split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
        conn.commit()


def log_etl(engine, dag_name: str, task_name: str, status: str,
            records: int = 0, error: str = None, source: str = None, run_id: int = None):
    """Insert or update an etl_log row."""
    import datetime
    with engine.connect() as conn:
        if run_id is None:
            conn.execute(text(
                """INSERT INTO etl_log
                   (dag_name, task_name, start_time, status, records_processed, error_message, source)
                   VALUES (:dag, :task, :ts, :status, :rec, :err, :src)"""
            ), {"dag": dag_name, "task": task_name, "ts": datetime.datetime.utcnow().isoformat(),
                "status": status, "rec": records, "err": error, "src": source})
        else:
            conn.execute(text(
                """UPDATE etl_log
                   SET end_time=:ts, status=:status, records_processed=:rec, error_message=:err
                   WHERE run_id=:rid"""
            ), {"ts": datetime.datetime.utcnow().isoformat(), "status": status,
                "rec": records, "err": error, "rid": run_id})
        conn.commit()
