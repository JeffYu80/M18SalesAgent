"""
Example: save a sales order using standard save with code-to-ID resolution.

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

    result = service.save_sales_order(
        be_id=7,
        header={
            "cusCode": "320",
            "curId": 3,
            "flowTypeId": 5,
            "staffCode": "000001",
            "tDate": "2026-05-08",
        },
        lines=[
            {
                "proCode": "PGD798MB",
                "unitCode": "PCS",
                "qty": 1,
                "up": 130,
            }
        ],
    )

    print_section("Sales Order Save Result")
    print_json(result)


if __name__ == "__main__":
    main()
