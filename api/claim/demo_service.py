#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from api.claim.rules import ClaimRules
from api.db.db_models import DB, ClaimCase, ClaimMaterial, ClaimPolicy, ClaimReview, Tenant

logger = logging.getLogger(__name__)

DEMO_SOURCE_VERSION = "claim-demo-v1"
DEMO_CASE_COUNT = 20
EXTRA_MATERIALS = (
    "police_report",
    "identity_document",
    "bank_account",
    "repair_estimate",
)
MATERIAL_FILE_NAMES = {
    "accident_photos": "现场照片",
    "bank_account": "收款账户说明",
    "driving_license": "驾驶证",
    "identity_document": "身份证明",
    "liability_determination": "事故责任认定书",
    "police_report": "报警记录",
    "repair_estimate": "维修估损单",
    "repair_invoice": "维修发票",
    "vehicle_license": "行驶证",
}
VEHICLE_MODELS = (
    "虚构车型-甲",
    "虚构车型-乙",
    "虚构车型-丙",
    "虚构车型-丁",
)


@dataclass(frozen=True)
class DemoDataset:
    cases: tuple[dict[str, object], ...]
    policies: tuple[dict[str, object], ...]
    materials: tuple[dict[str, object], ...]


def demo_record_id(record_type: str, tenant_id: str, record_key: str) -> str:
    return uuid5(NAMESPACE_URL, f"ragflow-claim-demo/{tenant_id}/{record_type}/{record_key}").hex


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def build_demo_dataset(tenant_id: str, rules: ClaimRules) -> DemoDataset:
    tenant_id = _required_text(tenant_id, "tenant_id")
    accident_types = tuple(rules.accident_types.values())
    if not accident_types:
        raise ValueError("claim rules must define at least one accident type")

    cases: list[dict[str, object]] = []
    policies: list[dict[str, object]] = []
    materials: list[dict[str, object]] = []

    for index in range(1, DEMO_CASE_COUNT + 1):
        case_no = f"CASE2026{index:04d}"
        policy_no = f"POL2026{index:04d}"
        accident_rule = accident_types[(index - 1) % len(accident_types)]
        accident_time = datetime(
            2026,
            1 + ((index - 1) % 12),
            2 + ((index * 3) % 25),
            9 + (index % 8),
            (index * 7) % 60,
        )
        policy_start = accident_time - timedelta(days=90 + (index % 3) * 30)
        policy_end = policy_start + timedelta(days=365)
        policy_status = "effective"
        if index % 7 == 0:
            policy_end = accident_time - timedelta(days=2)
            policy_status = "expired"
        elif index % 11 == 0:
            policy_status = "cancelled"

        case_id = demo_record_id("case", tenant_id, case_no)
        cases.append(
            {
                "id": case_id,
                "tenant_id": tenant_id,
                "case_no": case_no,
                "policy_no": policy_no,
                "accident_type": accident_rule.code,
                "accident_time": accident_time,
                "accident_location": f"虚构演示地点-{index:02d}",
                "accident_description": f"虚构演示案件：{accident_rule.display_name}，无真实人员及车辆信息。",
                "estimated_loss": Decimal(3500 + index * 725),
                "case_status": ("new", "reviewing", "closed")[(index - 1) % 3],
                "source_version": DEMO_SOURCE_VERSION,
            }
        )
        policies.append(
            {
                "id": demo_record_id("policy", tenant_id, policy_no),
                "tenant_id": tenant_id,
                "policy_no": policy_no,
                "insured_name": f"虚构被保人{index:02d}",
                "vehicle_plate": f"DEMO-A{index:04d}",
                "vehicle_model": VEHICLE_MODELS[(index - 1) % len(VEHICLE_MODELS)],
                "coverage_amount": Decimal(150000 + index * 10000),
                "start_date": policy_start,
                "end_date": policy_end,
                "policy_status": policy_status,
            }
        )

        material_codes = list(accident_rule.required_materials)
        if index % 4 != 0 and len(material_codes) > 2:
            material_codes.pop()
        for material_code in EXTRA_MATERIALS[: index % 4]:
            if material_code not in material_codes:
                material_codes.append(material_code)

        for material_index, material_code in enumerate(material_codes):
            materials.append(
                {
                    "id": demo_record_id("material", tenant_id, f"{case_no}/{material_code}"),
                    "tenant_id": tenant_id,
                    "case_id": case_id,
                    "material_type": material_code,
                    "file_name": f"{MATERIAL_FILE_NAMES.get(material_code, material_code)}-{case_no}.pdf",
                    "object_location": None,
                    "verification_status": "verified" if material_index < 2 else "declared",
                }
            )

    return DemoDataset(cases=tuple(cases), policies=tuple(policies), materials=tuple(materials))


def _validate_demo_write(tenant_id: str, dataset: DemoDataset) -> None:
    records = (*dataset.cases, *dataset.policies, *dataset.materials)
    if any(record["tenant_id"] != tenant_id for record in records):
        logger.warning("Rejected claim demo write: dataset tenant does not match tenant_id=%s", tenant_id)
        raise ValueError("demo dataset tenant does not match target tenant")
    if Tenant.get_or_none(Tenant.id == tenant_id) is None:
        logger.warning("Rejected claim demo write: tenant_id=%s does not exist", tenant_id)
        raise ValueError(f"tenant {tenant_id} does not exist")

    for case in dataset.cases:
        existing = ClaimCase.get_or_none((ClaimCase.tenant_id == tenant_id) & (ClaimCase.case_no == case["case_no"]))
        if existing is not None and (existing.id != case["id"] or existing.source_version != DEMO_SOURCE_VERSION):
            logger.warning("Rejected claim demo write: non-demo case=%s tenant_id=%s", case["case_no"], tenant_id)
            raise ValueError(f"refusing to overwrite non-demo case {case['case_no']}")

    for policy in dataset.policies:
        existing = ClaimPolicy.get_or_none((ClaimPolicy.tenant_id == tenant_id) & (ClaimPolicy.policy_no == policy["policy_no"]))
        if existing is not None and existing.id != policy["id"]:
            logger.warning("Rejected claim demo write: non-demo policy=%s tenant_id=%s", policy["policy_no"], tenant_id)
            raise ValueError(f"refusing to overwrite non-demo policy {policy['policy_no']}")


def seed_demo_data(tenant_id: str, dataset: DemoDataset) -> dict[str, object]:
    tenant_id = _required_text(tenant_id, "tenant_id")
    _validate_demo_write(tenant_id, dataset)
    case_ids = [str(case["id"]) for case in dataset.cases]
    logger.info(
        "Seeding claim demo data tenant_id=%s source_version=%s cases=%d policies=%d materials=%d",
        tenant_id,
        DEMO_SOURCE_VERSION,
        len(dataset.cases),
        len(dataset.policies),
        len(dataset.materials),
    )

    with DB.atomic():
        for case in dataset.cases:
            existing = ClaimCase.get_or_none(ClaimCase.id == case["id"])
            if existing is None:
                ClaimCase.create(**case)
            else:
                ClaimCase.update(**{key: value for key, value in case.items() if key != "id"}).where(ClaimCase.id == case["id"]).execute()

        for policy in dataset.policies:
            existing = ClaimPolicy.get_or_none(ClaimPolicy.id == policy["id"])
            if existing is None:
                ClaimPolicy.create(**policy)
            else:
                ClaimPolicy.update(**{key: value for key, value in policy.items() if key != "id"}).where(ClaimPolicy.id == policy["id"]).execute()

        ClaimMaterial.delete().where((ClaimMaterial.tenant_id == tenant_id) & ClaimMaterial.case_id.in_(case_ids)).execute()
        if dataset.materials:
            ClaimMaterial.insert_many(dataset.materials).execute()

    logger.info(
        "Seeded claim demo data tenant_id=%s cases=%d policies=%d materials=%d",
        tenant_id,
        len(dataset.cases),
        len(dataset.policies),
        len(dataset.materials),
    )
    return {
        "tenant_id": tenant_id,
        "source_version": DEMO_SOURCE_VERSION,
        "case_count": len(dataset.cases),
        "policy_count": len(dataset.policies),
        "material_count": len(dataset.materials),
    }


def reset_demo_data(tenant_id: str) -> dict[str, int]:
    tenant_id = _required_text(tenant_id, "tenant_id")
    demo_cases = list(ClaimCase.select(ClaimCase.id, ClaimCase.policy_no).where((ClaimCase.tenant_id == tenant_id) & (ClaimCase.source_version == DEMO_SOURCE_VERSION)))
    logger.info(
        "Resetting claim demo data tenant_id=%s source_version=%s cases=%d",
        tenant_id,
        DEMO_SOURCE_VERSION,
        len(demo_cases),
    )
    case_ids = [case.id for case in demo_cases]
    policy_ids = [demo_record_id("policy", tenant_id, case.policy_no) for case in demo_cases]

    with DB.atomic():
        review_count = ClaimReview.delete().where((ClaimReview.tenant_id == tenant_id) & ClaimReview.case_id.in_(case_ids)).execute() if case_ids else 0
        material_count = ClaimMaterial.delete().where((ClaimMaterial.tenant_id == tenant_id) & ClaimMaterial.case_id.in_(case_ids)).execute() if case_ids else 0
        case_count = ClaimCase.delete().where((ClaimCase.tenant_id == tenant_id) & ClaimCase.id.in_(case_ids)).execute() if case_ids else 0
        policy_count = ClaimPolicy.delete().where((ClaimPolicy.tenant_id == tenant_id) & ClaimPolicy.id.in_(policy_ids)).execute() if policy_ids else 0

    logger.info(
        "Reset claim demo data tenant_id=%s cases=%d policies=%d materials=%d reviews=%d",
        tenant_id,
        case_count,
        policy_count,
        material_count,
        review_count,
    )
    return {
        "case_count": case_count,
        "policy_count": policy_count,
        "material_count": material_count,
        "review_count": review_count,
    }
