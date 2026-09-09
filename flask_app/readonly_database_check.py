"""Contrôle non destructif de la base active avant publication.

Ce module n'importe pas l'application Flask et n'appelle ni create_all(), ni
 drop_all(), ni commit(). Il exécute uniquement SELECT 1, la lecture des noms
de tables et des COUNT(*) sur des tables connues.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, inspect, text


COUNT_TABLES = (
    "user",
    "student",
    "school_class",
    "subject",
    "course",
    "grade",
    "schedule_entry",
)


def _is_local_database(database_url: str) -> bool:
    return database_url.startswith("sqlite:///") and (
        "/tmp/" in database_url or ":memory:" in database_url
    )


def inspect_database(database_url: str | None = None) -> dict[str, Any]:
    """Retourne uniquement des métadonnées et compteurs, sans écrire en base."""
    url = database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL est requis pour un contrôle en lecture seule.")
    if not _is_local_database(url) and os.environ.get("LTT_READONLY_ACTIVE_DB") != "1":
        raise RuntimeError(
            "Le contrôle d’une base non locale exige LTT_READONLY_ACTIVE_DB=1 "
            "et reste strictement limité aux lectures."
        )

    connect_args: dict[str, Any] = {}
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    if url.startswith("mysql+pymysql://"):
        parsed = urlsplit(url)
        query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                 if key.lower() not in {"ssl", "sslmode"}]
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
        connect_args["ssl"] = {"ca": None}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            table_names = set(inspect(connection).get_table_names())
            counts: dict[str, int] = {}
            quote = "`" if connection.dialect.name in {"mysql", "mariadb"} else '"'
            for table in COUNT_TABLES:
                if table in table_names:
                    # Les noms proviennent exclusivement de COUNT_TABLES, jamais d'une entrée utilisateur.
                    counts[table] = int(connection.execute(text(f"SELECT COUNT(*) FROM {quote}{table}{quote}")).scalar_one())
            return {"read_only": True, "tables_seen": len(table_names), "counts": counts}
    finally:
        engine.dispose()


def main() -> None:
    result = inspect_database()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - sortie CLI concise
        print(f"READONLY_DATABASE_CHECK_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
