import json
import random
from datetime import date

import pytest
from faker import Faker

from hrgen.config import REFERENCE_DATE, SCALES
from hrgen.master_data import build_master_data


def build(scale_name="starter", seed=20261022):
    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    return build_master_data(rng, fake, SCALES[scale_name])


@pytest.fixture(scope="module", params=["starter", "full"])
def tables(request):
    return request.param, build(request.param)


def test_row_counts_match_scale(tables):
    name, t = tables
    s = SCALES[name]
    assert len(t["department"]) == s.departments
    assert len(t["employee"]) == s.employees
    assert len(t["policy_document"]) == s.policy_documents
    assert len(t["knowledge_article"]) == s.knowledge_articles
    assert len(t["category"]) == 6


def test_primary_keys_and_emails_unique(tables):
    _, t = tables
    keys = {"department": "department_id", "employee": "employee_id", "category": "category_id",
            "policy_document": "policy_id", "policy_version": "version_id",
            "knowledge_article": "kb_id"}
    for table, pk in keys.items():
        values = [r[pk] for r in t[table]]
        assert len(values) == len(set(values)), table
    emails = [r["email"] for r in t["employee"]]
    assert len(emails) == len(set(emails))


def test_foreign_keys_exist(tables):
    _, t = tables
    dept = {r["department_id"] for r in t["department"]}
    emp = {r["employee_id"] for r in t["employee"]}
    cat = {r["category_id"] for r in t["category"]}
    pol = {r["policy_id"] for r in t["policy_document"]}
    ver = {r["version_id"] for r in t["policy_version"]}
    kb = {r["kb_id"] for r in t["knowledge_article"]}
    assert all(r["department_id"] in dept for r in t["employee"])
    assert all(r["manager_id"] in emp for r in t["employee"] if r["manager_id"])
    assert all(r["manager_id"] != r["employee_id"] for r in t["employee"])
    assert all(r["category_id"] in cat and r["owner_department_id"] in dept for r in t["policy_document"])
    assert all(r["policy_id"] in pol for r in t["policy_version"])
    assert all(r["category_id"] in cat for r in t["knowledge_article"])
    assert all(r["kb_id"] in kb and r["version_id"] in ver for r in t["kb_policy_version"])


def test_every_staff_role_exists(tables):
    _, t = tables
    roles = {r["role"] for r in t["employee"]}
    assert {"employee", "candidate", "manager", "hr_partner",
            "hr_er_specialist", "it_ops_partner", "admin"} <= roles


def test_policy_version_periods(tables):
    _, t = tables
    by_policy = {}
    for v in t["policy_version"]:
        by_policy.setdefault(v["policy_id"], []).append(v)
    for versions in by_policy.values():
        versions.sort(key=lambda v: v["version_no"])
        assert [v["version_no"] for v in versions] == list(range(1, len(versions) + 1))
        for i, v in enumerate(versions):
            if i == len(versions) - 1:
                assert v["effective_to"] is None          # only the latest is open-ended
            else:
                assert date.fromisoformat(v["effective_from"]) < date.fromisoformat(v["effective_to"])
                # next version starts the day after this one ends -> no overlap, no gap
                assert (date.fromisoformat(versions[i + 1]["effective_from"])
                        - date.fromisoformat(v["effective_to"])).days == 1
                assert json.loads(v["key_rules"]) != json.loads(versions[i + 1]["key_rules"])


def test_policies_cover_every_category(tables):
    _, t = tables
    assert {p["category_id"] for p in t["policy_document"]} == {c["category_id"] for c in t["category"]}


def test_articles_have_links_and_valid_dates(tables):
    _, t = tables
    linked = {b["kb_id"] for b in t["kb_policy_version"]}
    assert linked == {a["kb_id"] for a in t["knowledge_article"]}
    assert all(a["published_at"][:10] <= REFERENCE_DATE for a in t["knowledge_article"])
    pairs = [(b["kb_id"], b["version_id"]) for b in t["kb_policy_version"]]
    assert len(pairs) == len(set(pairs))


def test_same_seed_gives_identical_data():
    assert build("starter") == build("starter")