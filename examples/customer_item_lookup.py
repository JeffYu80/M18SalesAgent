"""
Example: query customer item codes through EBI report 102.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples._debug_utils import print_json, print_section
from services.product_service import M18ProductService


def main() -> None:
    service = M18ProductService()

    result = service.query_customer_item_codes(
        customer_code="320",
        product_code="PGD798MB",
        be_id=7,
    )

    print_section("Customer Item Lookup Result")
    print_json(
        {
            "report": result.get("report"),
            "customer": result.get("customer"),
            "product": result.get("product"),
            "customerPartMatches": result.get("customerPartMatches", []),
            "externalCodes": result.get("externalCodes", []),
        }
    )


if __name__ == "__main__":
    main()
