"""
Example: inspect the raw customer payload and detect candidate contact tables.

Use this during UAT or production calibration to discover the actual customer
contact child table and field names in your M18 environment.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.customer_service import M18CustomerService
from examples._debug_utils import (
    find_candidate_contact_tables,
    print_candidate_rows,
    print_json,
    print_section,
    summarize_top_level_keys,
)


def main() -> None:
    service = M18CustomerService()

    customer_code = "C001"
    be_id = 1

    payload = service.get_customer_by_code(customer_code, be_id=be_id)

    print_section("Top-Level Keys")
    print_json(summarize_top_level_keys(payload))

    print_section("Candidate Contact Tables")
    candidates = find_candidate_contact_tables(payload)
    print_json(candidates)

    if candidates:
        table_name = candidates[0]["table"]
        if table_name.startswith("data."):
            rows = payload["data"][table_name.split(".", 1)[1]]["values"]
        else:
            rows = payload[table_name]["values"]
        print_section(f"Sample Rows From {table_name}")
        print_candidate_rows(rows)
    else:
        print_section("No Candidate Contact Tables Found")
        print("No obvious contact-like child table was detected in the payload.")


if __name__ == "__main__":
    main()
