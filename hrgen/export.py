"""Exports: CSV + JSON per table, seed.sql, metrics.json and manifest.json (with SHA-256).

Everything is sorted by primary key and written as UTF-8 with '\\n' line endings, so two
runs with the same seed give byte-identical files. The manifest never contains the output
path, so it is identical across runs too.
"""
import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path

from .config import REFERENCE_DATE

TABLE_ORDER = [                     # parents before children
    "department", "employee", "category", "policy_document", "policy_version",
    "knowledge_article", "kb_policy_version", "ticket", "assignment",
    "ticket_status_event", "message", "message_citation", "sla", "resolution",
]
GROUND_TRUTH_TABLES = ["ground_truth", "expected_decisions"]

COLUMNS = {
    "department": ["department_id", "name", "location"],
    "employee": ["employee_id", "full_name", "email", "department_id", "manager_id", "role",
                 "employment_type", "location", "hire_date", "status"],
    "category": ["category_id", "name", "default_queue", "is_sensitive", "default_priority"],
    "policy_document": ["policy_id", "title", "category_id", "audience", "owner_department_id"],
    "policy_version": ["version_id", "policy_id", "version_no", "effective_from", "effective_to",
                       "key_rules", "summary"],
    "knowledge_article": ["kb_id", "title", "category_id", "body", "status", "published_at"],
    "kb_policy_version": ["kb_id", "version_id"],
    "ticket": ["ticket_id", "employee_id", "category_id", "subject", "created_at", "priority",
               "is_sensitive", "is_ambiguous", "missing_context"],
    "assignment": ["assignment_id", "ticket_id", "queue", "assignee_id", "assigned_at", "reason"],
    "ticket_status_event": ["event_id", "ticket_id", "from_status", "to_status", "event_at", "actor_id"],
    "message": ["message_id", "ticket_id", "sender_id", "sender_role", "message_type", "sent_at", "body"],
    "message_citation": ["message_id", "version_id", "kb_id", "snippet"],
    "sla": ["sla_id", "ticket_id", "priority", "first_response_due", "resolution_due",
            "paused_minutes", "first_responded_at", "business_minutes_to_first_response",
            "first_response_met", "resolution_met"],
    "resolution": ["resolution_id", "ticket_id", "resolved_at", "resolution_code",
                   "cited_version_id", "business_minutes_to_resolve"],
    "ground_truth": ["issue_id", "issue_type", "entity", "record_id", "ticket_id",
                     "expected_value", "observed_value", "rule_reference"],
    "expected_decisions": ["ticket_id", "expected_queue", "expected_version_id", "needs_clarification"],
}

PK = {
    "department": ["department_id"], "employee": ["employee_id"], "category": ["category_id"],
    "policy_document": ["policy_id"], "policy_version": ["version_id"],
    "knowledge_article": ["kb_id"], "kb_policy_version": ["kb_id", "version_id"],
    "ticket": ["ticket_id"], "assignment": ["assignment_id"], "ticket_status_event": ["event_id"],
    "message": ["message_id"], "message_citation": ["message_id", "version_id"],
    "sla": ["sla_id"], "resolution": ["resolution_id"],
    "ground_truth": ["issue_id"], "expected_decisions": ["ticket_id"],
}

FKS = {  # column, parent table, parent column
    "employee": [("department_id", "department", "department_id"),
                 ("manager_id", "employee", "employee_id")],
    "policy_document": [("category_id", "category", "category_id"),
                        ("owner_department_id", "department", "department_id")],
    "policy_version": [("policy_id", "policy_document", "policy_id")],
    "knowledge_article": [("category_id", "category", "category_id")],
    "kb_policy_version": [("kb_id", "knowledge_article", "kb_id"),
                          ("version_id", "policy_version", "version_id")],
    "ticket": [("employee_id", "employee", "employee_id"), ("category_id", "category", "category_id")],
    "assignment": [("ticket_id", "ticket", "ticket_id"), ("assignee_id", "employee", "employee_id")],
    "ticket_status_event": [("ticket_id", "ticket", "ticket_id"), ("actor_id", "employee", "employee_id")],
    "message": [("ticket_id", "ticket", "ticket_id"), ("sender_id", "employee", "employee_id")],
    "message_citation": [("message_id", "message", "message_id"),
                         ("version_id", "policy_version", "version_id"),
                         ("kb_id", "knowledge_article", "kb_id")],
    "sla": [("ticket_id", "ticket", "ticket_id")],
    "resolution": [("ticket_id", "ticket", "ticket_id"),
                   ("cited_version_id", "policy_version", "version_id")],
}
UNIQUE = {"employee": ["email"], "sla": ["ticket_id"], "resolution": ["ticket_id"]}
INTEGER_COLS = {"version_no", "paused_minutes", "business_minutes_to_first_response",
                "business_minutes_to_resolve", "is_sensitive", "is_ambiguous", "missing_context",
                "first_response_met", "resolution_met"}


def cell(value):
    """CSV representation: empty for NULL, true/false for booleans."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def sorted_rows(name: str, rows: list[dict]) -> list[dict]:
    """Rows sorted by primary key; also checks the columns match the schema exactly."""
    cols = COLUMNS[name]
    for r in rows:
        assert set(r) == set(cols), f"{name}: unexpected columns {sorted(set(r) ^ set(cols))}"
    return sorted(rows, key=lambda r: tuple(r[c] for c in PK[name]))


def _to_csv(name: str, rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS[name])
    for r in rows:
        writer.writerow([cell(r[c]) for c in COLUMNS[name]])
    return buf.getvalue()


def _to_json(name: str, rows: list[dict]) -> str:
    data = [{c: r[c] for c in COLUMNS[name]} for r in rows]
    return json.dumps(data, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def _create_sql(name: str) -> str:
    parts = [f"{c} {'INTEGER' if c in INTEGER_COLS else 'TEXT'}" for c in COLUMNS[name]]
    parts.append(f"PRIMARY KEY ({', '.join(PK[name])})")
    parts += [f"UNIQUE ({c})" for c in UNIQUE.get(name, [])]
    parts += [f"FOREIGN KEY ({c}) REFERENCES {t} ({rc})" for c, t, rc in FKS.get(name, [])]
    return f"CREATE TABLE {name} ({', '.join(parts)})"


def _to_sql(tables: dict[str, list[dict]]) -> str:
    """CREATE TABLE + INSERT statements via an in-memory SQLite database and iterdump."""
    conn = sqlite3.connect(":memory:")
    for name in TABLE_ORDER:
        conn.execute(_create_sql(name))
        cols = COLUMNS[name]
        marks = ", ".join(["?"] * len(cols))
        conn.executemany(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({marks})",
                         [tuple(r[c] for c in cols) for r in tables[name]])
    conn.commit()
    text = "PRAGMA foreign_keys=OFF;\n" + "\n".join(conn.iterdump()) + "\n"
    conn.close()
    return text


def _write(out: Path, rel: str, text: str, files: dict, rows=None) -> None:
    data = text.encode("utf-8")
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    files[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "rows": rows}


def export_all(out: Path, tables: dict, truth: dict, metrics: dict,
               scale_name: str, seed: int) -> dict:
    """Write every output file and return the manifest (also saved as manifest.json)."""
    out = Path(out)
    files: dict[str, dict] = {}
    ordered = {name: sorted_rows(name, tables[name]) for name in TABLE_ORDER}
    for name, rows in ordered.items():
        _write(out, f"{name}.csv", _to_csv(name, rows), files, len(rows))
        _write(out, f"{name}.json", _to_json(name, rows), files, len(rows))
    _write(out, "seed.sql", _to_sql(ordered), files)
    _write(out, "metrics.json", json.dumps(metrics, sort_keys=True, indent=2) + "\n", files)
    for name in GROUND_TRUTH_TABLES:          # separate folder, never referenced by data tables
        rows = sorted_rows(name, truth[name])
        _write(out, f"ground_truth/{name}.csv", _to_csv(name, rows), files, len(rows))
        _write(out, f"ground_truth/{name}.json", _to_json(name, rows), files, len(rows))

    manifest = {
        "generator_command": f"python -m hrgen --scale {scale_name} --seed {seed}",
        "scale": scale_name,
        "seed": seed,
        "reference_date": REFERENCE_DATE,
        "row_counts": {name: len(ordered[name]) for name in TABLE_ORDER},
        "ground_truth_row_counts": {name: len(truth[name]) for name in GROUND_TRUTH_TABLES},
        "files": dict(sorted(files.items())),
    }
    (out / "manifest.json").write_bytes(
        (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    return manifest