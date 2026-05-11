"""
Helpers for readable M18 integration debugging output.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


def print_section(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"{'=' * 80}")


def print_json(data: Any, max_lines: int = 120) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    lines = text.splitlines()
    if len(lines) > max_lines:
        text = "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
    print(text)


def summarize_top_level_keys(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for key, value in payload.items():
        entry: Dict[str, Any] = {"key": key, "type": type(value).__name__}
        if isinstance(value, dict):
            entry["nested_keys"] = list(value.keys())[:20]
            values = value.get("values")
            if isinstance(values, list):
                entry["values_count"] = len(values)
                if values and isinstance(values[0], dict):
                    entry["sample_fields"] = list(values[0].keys())[:20]
        elif isinstance(value, list):
            entry["values_count"] = len(value)
            if value and isinstance(value[0], dict):
                entry["sample_fields"] = list(value[0].keys())[:20]
        summary.append(entry)
    return summary


def _candidate_tables_from_container(container: Dict[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    contact_markers = (
        "contact",
        "email",
        "phone",
        "mobile",
        "dept",
        "position",
        "fax",
        "tel",
        "man",
        "whatsapp",
    )

    for key, value in container.items():
        if isinstance(value, list):
            rows = value
        elif isinstance(value, dict):
            rows = value.get("values")
        else:
            continue

        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            continue

        sample_fields = [str(field).lower() for field in rows[0].keys()]
        score = sum(1 for marker in contact_markers if any(marker in field for field in sample_fields))
        key_lower = key.lower()
        if key_lower in {"cust", "cuscontact", "contact", "contactt"} or "contact" in key_lower or score >= 2:
            candidates.append(
                {
                    "table": f"{prefix}{key}",
                    "rows": len(rows),
                    "sample_fields": list(rows[0].keys())[:20],
                    "match_score": score,
                }
            )

    return candidates


def find_candidate_contact_tables(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    candidates.extend(_candidate_tables_from_container(payload))

    data_container = payload.get("data")
    if isinstance(data_container, dict):
        candidates.extend(_candidate_tables_from_container(data_container, prefix="data."))

    return sorted(candidates, key=lambda item: item["match_score"], reverse=True)


def print_candidate_rows(rows: Iterable[Dict[str, Any]], max_rows: int = 3) -> None:
    sample = list(rows)[:max_rows]
    print_json(sample, max_lines=80)
