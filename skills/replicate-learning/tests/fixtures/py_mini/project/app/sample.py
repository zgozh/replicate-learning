# -*- coding: utf-8 -*-
"""Mini host-project module used by the replicate-learning regression fixtures.

It exists to pin four injection/preflight behaviours that only show up on Python:
  * a module docstring and a multi-line SQL string (lines inside a string literal must never
    be given an inline teaching annotation — the annotation would change the program);
  * a backslash line continuation (appending anything to that line breaks the statement);
  * ordinary key lines that *should* carry teaching notes;
  * a unit-test-shaped function so the fixture can also exercise the verification phase.
"""
import sqlite3

FETCH_ACCOUNT_SQL = """select id,
       name
from account
where id = ?"""


def fetch_account(conn, account_id):
    cur = conn.cursor()
    cur.execute(FETCH_ACCOUNT_SQL, (account_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return {"id": row[0], "name": row[1]}


def account_label(conn, account_id, fallback="unknown"):
    record = fetch_account(conn, account_id)
    label = record["name"] if record else \
        fallback
    return label.strip()


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
