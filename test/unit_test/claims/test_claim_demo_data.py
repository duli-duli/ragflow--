from collections import defaultdict

import pytest
from peewee import SqliteDatabase

import api.claim.demo_service as demo_service
from api.claim.demo_service import DEMO_SOURCE_VERSION, build_demo_dataset
from api.claim.rules import load_claim_rules
from api.db.db_models import ClaimCase, ClaimMaterial, ClaimPolicy, ClaimReview, ClaimSetting

CLAIM_MODELS = (ClaimCase, ClaimPolicy, ClaimMaterial, ClaimReview, ClaimSetting)

def test_demo_dataset_has_required_size_and_fictional_labels():
    dataset = build_demo_dataset("tenant-a", load_claim_rules())

    assert len(dataset.cases) == 20
    assert len(dataset.policies) == 20
    assert all(2 <= count <= 8 for count in _material_counts(dataset).values())
    assert all(case["source_version"] == DEMO_SOURCE_VERSION for case in dataset.cases)
    assert all(str(case["case_no"]).startswith("CASE2026") for case in dataset.cases)
    assert all(str(policy["insured_name"]).startswith("虚构被保人") for policy in dataset.policies)
    assert all(str(policy["vehicle_plate"]).startswith("DEMO-A") for policy in dataset.policies)


def test_demo_dataset_is_deterministic_per_tenant():
    rules = load_claim_rules()

    first = build_demo_dataset("tenant-a", rules)
    second = build_demo_dataset("tenant-a", rules)
    other_tenant = build_demo_dataset("tenant-b", rules)

    assert first == second
    assert first.cases[0]["id"] != other_tenant.cases[0]["id"]


def test_demo_materials_cover_complete_and_missing_rule_scenarios():
    rules = load_claim_rules()
    dataset = build_demo_dataset("tenant-a", rules)
    submitted_by_case = defaultdict(set)
    for material in dataset.materials:
        submitted_by_case[material["case_id"]].add(material["material_type"])

    missing_counts = []
    for case in dataset.cases:
        required = set(rules.required_materials(case["accident_type"]))
        missing_counts.append(len(required - submitted_by_case[case["id"]]))

    assert any(count == 0 for count in missing_counts)
    assert any(count > 0 for count in missing_counts)


def test_demo_dataset_ids_are_unique():
    dataset = build_demo_dataset("tenant-a", load_claim_rules())
    record_ids = [record["id"] for group in (dataset.cases, dataset.policies, dataset.materials) for record in group]

    assert len(record_ids) == len(set(record_ids))


def test_demo_dataset_from_another_tenant_is_rejected_before_write():
    dataset = build_demo_dataset("tenant-b", load_claim_rules())

    with pytest.raises(ValueError, match="does not match target tenant"):
        demo_service._validate_demo_write("tenant-a", dataset)


def test_seed_is_idempotent_and_reset_removes_demo_records(monkeypatch):
    rules = load_claim_rules()
    dataset = build_demo_dataset("tenant-a", rules)
    database = SqliteDatabase(":memory:")
    with database.bind_ctx(CLAIM_MODELS):
        database.create_tables(CLAIM_MODELS)
        monkeypatch.setattr(demo_service.DB, "atomic", database.atomic)
        monkeypatch.setattr(demo_service, "_validate_demo_write", lambda tenant_id, demo_dataset: None)

        first_summary = demo_service.seed_demo_data("tenant-a", dataset)
        second_summary = demo_service.seed_demo_data("tenant-a", dataset)

        assert first_summary == second_summary
        assert ClaimCase.select().count() == 20
        assert ClaimPolicy.select().count() == 20
        assert ClaimMaterial.select().count() == len(dataset.materials)

        reset_summary = demo_service.reset_demo_data("tenant-a")
        assert reset_summary["case_count"] == 20
        assert reset_summary["policy_count"] == 20
        assert reset_summary["material_count"] == len(dataset.materials)
        assert ClaimCase.select().count() == 0
        assert ClaimPolicy.select().count() == 0
        assert ClaimMaterial.select().count() == 0
    database.close()


def _material_counts(dataset):
    counts = defaultdict(int)
    for material in dataset.materials:
        counts[material["case_id"]] += 1
    return counts
