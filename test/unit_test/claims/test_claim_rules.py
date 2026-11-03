from io import StringIO
from pathlib import Path

import pytest

import api.claim.rules as claim_rules
from api.claim.rules import load_claim_rules


def test_load_claim_rules_from_repository_config():
    rules = load_claim_rules()

    assert rules.version == "claim-rules-v1"
    assert set(rules.accident_types) == {
        "single_vehicle_collision",
        "two_vehicle_collision",
        "vehicle_repair",
    }
    assert rules.required_materials("two_vehicle_collision") == (
        "driving_license",
        "vehicle_license",
        "accident_photos",
        "liability_determination",
    )


def test_unknown_accident_type_has_explicit_empty_requirements():
    rules = load_claim_rules()

    assert rules.get_rule("unknown") is None
    assert rules.required_materials("unknown") == ()


def test_duplicate_required_material_is_rejected(monkeypatch):
    invalid_rules = {
        "version": "invalid-v1",
        "accident_types": {
            "invalid": {
                "display_name": "无效规则",
                "required_materials": ["driving_license", "driving_license"],
            }
        },
    }
    monkeypatch.setattr(Path, "open", lambda self, *args, **kwargs: StringIO(""))
    monkeypatch.setattr(claim_rules.YAML, "load", lambda self, stream: invalid_rules)

    with pytest.raises(ValueError, match="contains duplicates"):
        load_claim_rules("invalid.yaml")
