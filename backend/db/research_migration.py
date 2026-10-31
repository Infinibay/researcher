"""Atomic additive research migration, using one packaged SQL resource."""

import sqlite3
from pathlib import Path


def apply_research_schema(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
    statement = ""
    for line in (
        Path(__file__)
        .with_name("research_schema.sql")
        .read_text()
        .splitlines(keepends=True)
    ):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise sqlite3.OperationalError("Incomplete research migration SQL")
    conn.commit()
