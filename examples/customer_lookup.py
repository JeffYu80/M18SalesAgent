"""
Example: search customers in M18.

Run after your M18 credentials are configured for `M18Client`.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.customer_service import M18CustomerService
from examples._debug_utils import print_json, print_section


def main() -> None:
    service = M18CustomerService()

    result = service.search_customers(
        be_id=1,
        quick_search="C001",
        start_row=0,
        end_row=10,
    )

    print_section("Customer Search Result")
    print_json(result)

    summaries = result.get("summaries", [])
    if summaries:
        print_section("Customer Summaries")
        print_json(summaries)


if __name__ == "__main__":
    main()
