"""
Example: search products in M18.
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

    result = service.search_products(
        be_id=7,
        quick_search="PGD798MB",
        start_row=0,
        end_row=10,
    )

    print_section("Product Search Result")
    print_json(result)


if __name__ == "__main__":
    main()
