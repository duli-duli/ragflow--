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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

DEFAULT_CLAIM_RULES_PATH = Path(__file__).resolve().parents[2] / "conf" / "claim_rules.yaml"


@dataclass(frozen=True)
class AccidentRule:
    code: str
    display_name: str
    required_materials: tuple[str, ...]


@dataclass(frozen=True)
class ClaimRules:
    version: str
    accident_types: Mapping[str, AccidentRule]

    def get_rule(self, accident_type: str) -> AccidentRule | None:
        return self.accident_types.get(accident_type)

    def required_materials(self, accident_type: str) -> tuple[str, ...]:
        rule = self.get_rule(accident_type)
        return rule.required_materials if rule else ()


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def load_claim_rules(path: str | Path | None = None) -> ClaimRules:
    rules_path = Path(path) if path is not None else DEFAULT_CLAIM_RULES_PATH
    logger.debug("Loading claim rules from %s", rules_path)
    yaml = YAML(typ="safe", pure=True)
    try:
        with rules_path.open(encoding="utf-8") as rules_file:
            try:
                document = yaml.load(rules_file)
            except Exception as exc:
                logger.exception("Failed to parse claim rules from %s", rules_path)
                raise ValueError(f"unable to parse claim rules from {rules_path}") from exc
    except OSError as exc:
        logger.exception("Failed to read claim rules from %s", rules_path)
        raise ValueError(f"unable to load claim rules from {rules_path}") from exc

    if not isinstance(document, Mapping):
        raise ValueError("claim rules must be a mapping")

    version = _non_empty_string(document.get("version"), "version")
    raw_accident_types = document.get("accident_types")
    if not isinstance(raw_accident_types, Mapping) or not raw_accident_types:
        raise ValueError("accident_types must be a non-empty mapping")

    accident_types: dict[str, AccidentRule] = {}
    for raw_code, raw_rule in raw_accident_types.items():
        code = _non_empty_string(raw_code, "accident type code")
        if not isinstance(raw_rule, Mapping):
            raise ValueError(f"claim rule {code} must be a mapping")

        display_name = _non_empty_string(raw_rule.get("display_name"), f"claim rule {code}.display_name")
        raw_materials = raw_rule.get("required_materials")
        if not isinstance(raw_materials, list) or not raw_materials:
            raise ValueError(f"claim rule {code}.required_materials must be a non-empty list")
        required_materials = tuple(_non_empty_string(material, f"claim rule {code}.required_materials") for material in raw_materials)
        if len(set(required_materials)) != len(required_materials):
            raise ValueError(f"claim rule {code}.required_materials contains duplicates")

        accident_types[code] = AccidentRule(
            code=code,
            display_name=display_name,
            required_materials=required_materials,
        )

    logger.debug(
        "Loaded claim rules version=%s accident_types=%d path=%s",
        version,
        len(accident_types),
        rules_path,
    )
    return ClaimRules(version=version, accident_types=MappingProxyType(accident_types))
