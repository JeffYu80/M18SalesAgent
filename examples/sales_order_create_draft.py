"""
Example: create a sales order draft by business codes.

Run after your M18 credentials are configured for `M18Client`.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples._debug_utils import print_json, print_section
from services.sales_order_service import M18SalesOrderService


def main() -> None:
    service = M18SalesOrderService()

    result = service.create_draft_from_codes(
        be_code="PUS",
        be_id=7,
        cus_code="320",
        lines=[
            {
                "proCode": "PGD798MB",
                "unitCode": "PCS",
                "qty": 1,
                "up": 130,
                "disc": 0,
            }
        ],
        extra_fields={"staffCode": "000001"},
    )

    print_section("Sales Order Draft Result")
    print_json(result)


if __name__ == "__main__":
    main()
