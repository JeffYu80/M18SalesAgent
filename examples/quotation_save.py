"""
Example: save a sales quotation using standard save with code-to-ID resolution.

Run after your M18 credentials are configured for `M18Client`.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.quotation_service import M18QuotationService
from examples._debug_utils import print_json, print_section


def main() -> None:
    service = M18QuotationService()

    result = service.save_quotation(
        be_id=7,
        header={
            "cusCode": "320",
            "currency": "USD",  # Omit to use the customer master currency.
            "flowTypeId": 5,
            "staffCode": "000001",
            "tDate": "2026-05-07",
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

    print_section("Quotation Save Result")
    print_json(result)


if __name__ == "__main__":
    main()
