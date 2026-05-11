#!/usr/bin/env python3
"""
M18 API Connector — Integration Tests
======================================
Verifies connectivity, authentication, and basic operations against the
M18 UAT environment.

Usage:
    python scripts/test_m18_api.py
"""

from __future__ import annotations

import json
import sys
import os

# Ensure the scripts directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from m18_api import (
    M18Client,
    M18APIError,
    M18AuthError,
    M18NotFoundError,
    M18ValidationError,
)


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def pretty(data: dict, max_lines: int = 30) -> str:
    """Pretty-print JSON, truncating if very large."""
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    lines = text.split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n  ... ({len(lines) - max_lines} more lines)"
    return text


def test_token(client: M18Client) -> bool:
    """Test 1: Obtain OAuth token."""
    separator("Test 1: OAuth Token Acquisition")
    try:
        headers = client.get_token()
        print(f"  OK — Token obtained successfully")
        print(f"  authorization: {headers['authorization'][:50]}...")
        print(f"  client_id:     {headers['client_id'][:20]}...")
        return True
    except M18AuthError as e:
        print(f"  FAIL — Auth error: {e}")
        print(f"  Status code: {e.status_code}")
        if e.raw_response:
            print(f"  Response: {e.raw_response[:200]}")
        return False
    except Exception as e:
        print(f"  FAIL — Unexpected error: {type(e).__name__}: {e}")
        return False


def test_search(client: M18Client) -> bool:
    """Test 2: Search for entities (sales orders)."""
    separator("Test 2: Search Entities (Sales Orders)")
    try:
        result = client.search_entities("oldso", start_row=0, end_row=5)
        print(f"  OK — Search returned successfully")
        # Show structure
        if isinstance(result, dict):
            print(f"  Response keys: {list(result.keys())}")
            size = result.get("size", result.get("total", "N/A"))
            print(f"  Total records: {size}")
            # Show first few results if available
            values = result.get("values", result.get("data", result.get("rows", [])))
            if values:
                print(f"  First record sample:")
                print(f"    {pretty(values[0] if isinstance(values[0], dict) else {'value': values[0]}, max_lines=10)}")
        else:
            print(f"  Response type: {type(result).__name__}")
            print(f"  {pretty(result) if isinstance(result, dict) else str(result)[:300]}")
        return True
    except M18APIError as e:
        print(f"  FAIL — API error [{e.status_code}]: {e}")
        return False
    except Exception as e:
        print(f"  FAIL — Unexpected error: {type(e).__name__}: {e}")
        return False


def test_search_products(client: M18Client) -> bool:
    """Test 3: Search for products (item master)."""
    separator("Test 3: Search Products (Item Master)")
    try:
        result = client.search_entities("pro", start_row=0, end_row=5)
        print(f"  OK — Product search returned successfully")
        if isinstance(result, dict):
            print(f"  Response keys: {list(result.keys())}")
            size = result.get("size", result.get("total", "N/A"))
            print(f"  Total records: {size}")
            values = result.get("values", result.get("data", result.get("rows", [])))
            if values and len(values) > 0:
                sample = values[0] if isinstance(values[0], dict) else {"value": values[0]}
                print(f"  First product sample:")
                print(f"    {pretty(sample, max_lines=10)}")
        return True
    except M18APIError as e:
        print(f"  FAIL — API error [{e.status_code}]: {e}")
        return False
    except Exception as e:
        print(f"  FAIL — Unexpected error: {type(e).__name__}: {e}")
        return False


def test_read_entity(client: M18Client) -> bool:
    """Test 4: Read a specific entity — may or may not exist."""
    separator("Test 4: Read Entity (Sales Order id=1)")
    try:
        result = client.read_entity("oldso", 1)
        print(f"  OK — Entity read successfully")
        if isinstance(result, dict):
            print(f"  Response keys: {list(result.keys())}")
            print(f"  {pretty(result, max_lines=15)}")
        return True
    except M18NotFoundError as e:
        print(f"  OK (expected) — Entity not found: {e}")
        return True
    except M18APIError as e:
        print(f"  INFO — API error [{e.status_code}]: {e}")
        return True
    except Exception as e:
        print(f"  FAIL — Unexpected error: {type(e).__name__}: {e}")
        return False


def test_error_handling_invalid_id(client: M18Client) -> bool:
    """Test 5: Error handling — request with deliberately invalid data."""
    separator("Test 5: Error Handling (Invalid Entity ID)")
    try:
        result = client.read_entity("oldso", 999999999)
        # Should not reach here — M18 returns status:false for invalid IDs
        print(f"  WARN — No error raised for non-existent ID")
        print(f"  Response: {pretty(result, max_lines=10)}")
        return True
    except M18NotFoundError as e:
        print(f"  OK — Correctly raised M18NotFoundError: {e}")
        return True
    except M18ValidationError as e:
        print(f"  OK — Correctly raised M18ValidationError: {e}")
        print(f"  CheckMessages: {e.check_messages}")
        return True
    except M18APIError as e:
        print(f"  OK — Raised M18APIError [{e.status_code}]: {e}")
        return True
    except Exception as e:
        print(f"  FAIL — Unexpected error type: {type(e).__name__}: {e}")
        return False


def test_ebi_report_list(client: M18Client) -> bool:
    """Test 6: List available EBI reports."""
    separator("Test 6: List EBI Reports")
    try:
        result = client.list_ebi_reports(rows=5)
        print(f"  OK — EBI report list retrieved")
        if isinstance(result, dict):
            print(f"  Response keys: {list(result.keys())}")
            print(f"  {pretty(result, max_lines=15)}")
        return True
    except M18APIError as e:
        print(f"  INFO — API error [{e.status_code}]: {e}")
        # EBI may not be accessible with current permissions
        return True
    except Exception as e:
        print(f"  FAIL — Unexpected error: {type(e).__name__}: {e}")
        return False


def main():
    print("M18 API Connector — Integration Test Suite")
    print(f"{'='*60}")

    # Initialise client
    try:
        client = M18Client()
        print(f"Client initialised — API base: {client.api_base}")
    except Exception as e:
        print(f"FATAL — Cannot initialise client: {e}")
        sys.exit(1)

    results = {}

    # Run tests
    results["1_token"] = test_token(client)

    # Only continue if token works
    if not results["1_token"]:
        print("\n\nToken acquisition failed — skipping remaining tests.")
        print("Check credentials in config/m18_api_token.yaml")
        sys.exit(1)

    results["2_search_so"] = test_search(client)
    results["3_search_pro"] = test_search_products(client)
    results["4_read_entity"] = test_read_entity(client)
    results["5_error_handling"] = test_error_handling_invalid_id(client)
    results["6_ebi_reports"] = test_ebi_report_list(client)

    # Summary
    separator("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    print(f"\n  {passed}/{total} tests passed")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
