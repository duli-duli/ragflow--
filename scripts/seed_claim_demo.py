#!/usr/bin/env python3
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

import argparse
import json
import logging
from collections.abc import Sequence

from api.claim.demo_service import build_demo_dataset, reset_demo_data, seed_demo_data
from api.claim.rules import load_claim_rules
from api.db.db_models import DB, init_database_tables

logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed or reset fictional car-insurance claim demo data for one tenant.")
    parser.add_argument("--tenant-id", required=True, help="Target RAGFlow tenant ID.")
    parser.add_argument("--reset-demo", action="store_true", help="Remove current demo version instead of seeding it.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = parse_args(argv)
    mode = "reset" if args.reset_demo else "seed"
    logger.info("Starting claim demo command mode=%s tenant_id=%s", mode, args.tenant_id)
    init_database_tables()

    if args.reset_demo:
        with DB.connection_context():
            summary = reset_demo_data(args.tenant_id)
    else:
        rules = load_claim_rules()
        dataset = build_demo_dataset(args.tenant_id, rules)
        with DB.connection_context():
            summary = seed_demo_data(args.tenant_id, dataset)
            summary["rule_version"] = rules.version

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    logger.info("Completed claim demo command mode=%s tenant_id=%s", mode, args.tenant_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
