import csv
import shutil

import pytest

from hrgen.config import DEFAULT_SEED, SCALES
from hrgen.export import export_all
from hrgen.metrics import compute_metrics
from hrgen.pipeline import generate
from hrgen.validate import validate_dir, write_summary


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    scale = SCALES["starter"]
    tables, truth = generate(scale, DEFAULT_SEED)
    out = tmp_path_factory.mktemp("export")
    export_all(out, tables, truth, compute_metrics(tables, truth), scale.name, DEFAULT_SEED)
    checks, ok = validate_dir(out)
    return out, checks, ok


def test_validation_passes_on_clean_export(exported):
    _, checks, ok = exported
    failed = [f"{c['name']}: {c['detail']}" for c in checks if not c["ok"]]
    assert ok and not failed, failed
    assert len(checks) >= 25
    assert {c["kind"] for c in checks} == {"structural", "rule"}


def test_rule_checks_are_explained_by_ground_truth(exported):
    _, checks, _ = exported
    rules = {c["name"]: c for c in checks if c["kind"] == "rule"}
    labelled = [c for c in rules.values() if c["expected"]]
    assert len(labelled) == 4                              # one rule per injected issue type
    for c in labelled:
        assert c["found"] == c["expected"] and len(c["found"]) >= 3
    for c in rules.values():
        if not c["expected"]:
            assert c["found"] == []                        # no labelled anomaly -> no violations


def test_detects_a_broken_foreign_key(exported, tmp_path):
    out, _, _ = exported
    bad = tmp_path / "bad_fk"
    shutil.copytree(out, bad)
    path = bad / "assignment.csv"
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    rows[1][3] = "EMP-999999"                              # assignee_id that does not exist
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    checks, ok = validate_dir(bad)
    assert not ok
    assert any(c["name"].startswith("Foreign keys") and not c["ok"] for c in checks)


def test_detects_an_unlabelled_anomaly(exported, tmp_path):
    out, _, _ = exported
    bad = tmp_path / "bad_truth"
    shutil.copytree(out, bad)
    path = bad / "ground_truth" / "ground_truth.csv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    drop = next(i for i, line in enumerate(lines) if "OBSOLETE_CITATION" in line)
    path.write_text("".join(lines[:drop] + lines[drop + 1:]), encoding="utf-8", newline="")
    checks, ok = validate_dir(bad)
    assert not ok
    assert any(c["kind"] == "rule" and not c["ok"] for c in checks)


def test_summary_file_is_written(exported):
    out, checks, _ = exported
    text = write_summary(out, checks)
    assert (out / "validation_summary.md").exists()
    assert "Overall: **PASS**" in text and "Structural checks" in text and "Rule checks" in text