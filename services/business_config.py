"""
Business configuration loader for M18 services.

Loads from config/m18.{env}.yaml where env defaults to "uat".
Set M18_ENV env var to switch environments (e.g. M18_ENV=prod).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent


def load_business_config() -> Dict[str, Any]:
    """Load business config from the merged environment config file."""
    env = os.environ.get("M18_ENV", "uat")
    path = ROOT_DIR / "config" / f"m18.{env}.yaml"
    if not path.exists():
        path = ROOT_DIR / "config" / "m18.uat.yaml"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            return data
    return {}
