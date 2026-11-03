from datetime import datetime
from decimal import Decimal

import pytest
from peewee import DecimalField, IntegrityError, SqliteDatabase

from api.db.db_models import ClaimCase, ClaimMaterial, ClaimPolicy, ClaimReview, ClaimSetting

CLAIM_MODELS = (ClaimCase, ClaimPolicy, ClaimMaterial, ClaimReview, ClaimSetting)


def test_claim_tables_are_autodiscoverable_data_models():
    assert [model._meta.table_name for model in CLAIM_MODELS] == [
        "claim_case",
        "claim_policy",
        "claim_material",
        "claim_review",
        "claim_setting",
    ]
    assert isinstance(ClaimCase.estimated_loss, DecimalField)
    assert ClaimCase._meta.indexes == [(("tenant_id", "case_no"), True)]
    assert ClaimPolicy._meta.indexes == [(("tenant_id", "policy_no"), True)]


def test_claim_models_store_decimal_json_and_tenant_unique_key():
    database = SqliteDatabase(":memory:")
    with database.bind_ctx(CLAIM_MODELS):
        database.create_tables(CLAIM_MODELS)
        ClaimCase.create(
            id="case-1",
            tenant_id="tenant-a",
            case_no="CASE20260001",
            policy_no="POL20260001",
            accident_type="two_vehicle_collision",
            accident_time=datetime(2026, 3, 1, 10, 0),
            accident_location="虚构地点",
            accident_description="虚构演示案件",
            estimated_loss=Decimal("1234.56"),
            case_status="new",
            source_version="claim-demo-v1",
        )
        ClaimReview.create(
            id="review-1",
            tenant_id="tenant-a",
            user_id="user-1",
            case_id="case-1",
            request_id="request-1",
            status="queued",
            rule_version="claim-rules-v1",
        )

        case = ClaimCase.get_by_id("case-1")
        review = ClaimReview.get_by_id("review-1")
        assert case.estimated_loss == Decimal("1234.56")
        assert review.policy_check == {}
        assert review.citations == []

        with pytest.raises(IntegrityError):
            ClaimCase.create(
                id="case-2",
                tenant_id="tenant-a",
                case_no="CASE20260001",
                policy_no="POL20260002",
                accident_type="single_vehicle_collision",
                accident_time=datetime(2026, 3, 2, 10, 0),
                accident_location="虚构地点",
                accident_description="重复案件编号",
                estimated_loss=Decimal("100.00"),
                case_status="new",
                source_version="claim-demo-v1",
            )
    database.close()
