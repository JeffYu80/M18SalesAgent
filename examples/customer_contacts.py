"""
Example: load customer contacts from M18.

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

    result = service.get_customer_contacts(
        customer_code="C001",
        be_id=1,
        email="alice@example.com",
    )

    print_section("Customer Contact Result")
    print_json(result)


if __name__ == "__main__":
    main()
