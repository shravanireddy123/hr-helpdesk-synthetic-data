import csv
import json
import sqlite3
from collections import Counter

import pytest

from hrgen.config import DEFAULT_SEED, SCALES
from hrgen.export import (COLUMNS, GROUND_TRUTH_TABLES, PK, TABLE_ORDER, cell,
                          export_all, sorted_rows)
from hrgen.metrics import compute_metrics
from hrgen.pipeline import generate

SCALE = SCALES["starter"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tables, truth = generate(SCALE, DEFAULT_SEED)
    metrics = compute_metrics(tables, truth)
    out = tmp_path_factory.mktemp("run1")
    manifest = export_all(out, tables, truth, metrics, SCALE.name, DEFAULT_SEED)
    return tables, truth, metrics, out, manifest


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def all_tables(tables, truth):
    """(relative path prefix, table name, rows) for data tables and ground-truth tables."""
    for name in TABLE_ORDER:
        yield "", name, tables[name]
    for name in GROUND_TRUTH_TABLES:
        yield "ground_truth/", name, truth[name]


def test_row_counts_in_csv_and_json(built):
    tables, truth, _, out, _ = built
    for prefix, name, rows in all_tables(tables, truth):
        csv_rows = read_csv(out / f"{prefix}{name}.csv")
        assert csv_rows[0] == COLUMNS[name]
        assert len(csv_rows) - 1 == len(rows)
        data = json.loads((out / f"{prefix}{name}.json").read_text(encoding="utf-8"))
        assert len(data) == len(rows)


def test_csv_content_round_trips(built):
    tables, truth, _, out, _ = built
    for prefix, name, rows in all_tables(tables, truth):
        expected = [[str(cell(r[c])) for c in COLUMNS[name]] for r in sorted_rows(name, rows)]
        assert read_csv(out / f"{prefix}{name}.csv")[1:] == expected, name


def test_files_sorted_by_primary_key(built):
    tables, truth, _, out, _ = built
    for prefix, name, _ in all_tables(tables, truth):
        rows = read_csv(out / f"{prefix}{name}.csv")
        idx = [COLUMNS[name].index(c) for c in PK[name]]
        keys = [tuple(r[i] for i in idx) for r in rows[1:]]
        assert keys == sorted(keys), name


def test_sql_seed_loads_and_keys_hold(built):
    tables, _, _, out, _ = built
    text = (out / "seed.sql").read_text(encoding="utf-8")
    assert "issue_type" not in text                       # ground truth is not in the SQL seed
    conn = sqlite3.connect(":memory:")
    conn.executescript(text)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert names == set(TABLE_ORDER)
    for name in TABLE_ORDER:
        count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        assert count == len(tables[name]), name
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_manifest_is_complete_and_correct(built):
    import hashlib
    tables, truth, _, out, manifest = built
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == manifest
    expected_files = {"seed.sql", "metrics.json"}
    for prefix, name, _ in all_tables(tables, truth):
        expected_files |= {f"{prefix}{name}.csv", f"{prefix}{name}.json"}
    assert set(manifest["files"]) == expected_files        # manifest.json does not list itself
    for rel, info in manifest["files"].items():
        data = (out / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == info["sha256"], rel
        assert info["bytes"] == len(data)
    assert manifest["row_counts"] == {n: len(tables[n]) for n in TABLE_ORDER}
    assert manifest["seed"] == DEFAULT_SEED and manifest["scale"] == "starter"
    assert manifest["generator_command"] == "python -m hrgen --scale starter --seed 20261022"


def test_ground_truth_is_kept_separate(built):
    _, _, _, out, _ = built
    for name in TABLE_ORDER:
        header = read_csv(out / f"{name}.csv")[0]
        assert not ({"issue_type", "issue_id"} & set(header)), name
    for name in GROUND_TRUTH_TABLES:
        assert (out / "ground_truth" / f"{name}.csv").exists()
        assert not (out / f"{name}.csv").exists()


def test_two_runs_give_identical_files(built, tmp_path):
    _, _, _, out1, manifest1 = built
    tables, truth = generate(SCALE, DEFAULT_SEED)          # a completely fresh run
    metrics = compute_metrics(tables, truth)
    manifest2 = export_all(tmp_path, tables, truth, metrics, SCALE.name, DEFAULT_SEED)
    assert manifest1 == manifest2
    for rel in list(manifest1["files"]) + ["manifest.json"]:
        assert (out1 / rel).read_bytes() == (tmp_path / rel).read_bytes(), rel


def test_metrics_shape_and_ranges(built):
    _, _, m, _, _ = built
    for p in ("P1", "P2", "P3"):
        assert 0 <= m["first_response_sla_attainment_pct"][p] <= 100
        assert 0 <= m["resolution_sla_attainment_pct"][p] <= 100
    for key in ("clarification_rate_pct", "clarification_reply_rate_pct", "escalation_rate_pct",
                "citation_accuracy_pct", "sensitive_routing_accuracy_pct"):
        assert 0 < m[key] <= 100, key
    bh = m["business_hours_to_resolve"]
    assert 0 < bh["median"] <= bh["p90"]
    assert m["tickets_total"] == SCALE.tickets and m["messages_total"] == SCALE.messages


def test_metrics_agree_with_ground_truth(built):
    tables, truth, m, _, _ = built
    counts = Counter(g["issue_type"] for g in truth["ground_truth"])
    assert m["anomaly_counts"] == dict(sorted(counts.items()))
    n_cites = len(tables["message_citation"])
    assert m["citation_accuracy_pct"] == round(100 * (n_cites - counts["OBSOLETE_CITATION"]) / n_cites, 2)
    sensitive = sum(1 for t in tables["ticket"] if t["is_sensitive"])
    assert m["sensitive_routing_accuracy_pct"] == round(
        100 * (sensitive - counts["SENSITIVE_MISROUTED"]) / sensitive, 2)
    assert sum(m["tickets_per_category"].values()) == len(tables["ticket"])
    assert sum(m["messages_per_category"].values()) == len(tables["message"])


def test_metrics_file_matches_computed_metrics(built):
    _, _, m, out, _ = built
    assert json.loads((out / "metrics.json").read_text(encoding="utf-8")) == m