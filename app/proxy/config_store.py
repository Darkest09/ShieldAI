"""JSON-backed runtime toggles for recognizers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "shadow_mode": False,
    "credit_card_scanning": True,
    "email_scanning": True,
    # Minimum confidence a detection needs to count (raises precision).
    "score_threshold": 0.5,
    # Built-in Presidio entities irrelevant to a Nepali banking context — dropped
    # to cut false positives (US/UK-specific identifiers).
    "disabled_builtin_entities": [
        "US_SSN", "US_ITIN", "US_PASSPORT", "US_DRIVER_LICENSE", "US_BANK_NUMBER",
        "UK_NHS", "UK_NINO", "AU_ABN", "AU_ACN", "AU_TFN", "AU_MEDICARE",
        "IN_PAN", "IN_AADHAAR", "IN_VEHICLE_REGISTRATION", "SG_NRIC_FIN",
    ],
    "custom_recognizers": {
        "NP_CITIZENSHIP_NUMBER": True,
        "NP_MOBILE_NUMBER": True,
        "AWS_ACCESS_KEY_ID": True,
        "AWS_SECRET_ACCESS_KEY": True,
        "STRIPE_API_KEY": True,
        "BANK_ACCOUNT_NUMBER": True,
        "SWIFT_BIC_CODE": True,
    },
}


def config_path_resolve(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def load_config(path_str: str) -> dict[str, Any]:
    p = config_path_resolve(path_str)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        save_config(path_str, DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    merged = dict(DEFAULT_CONFIG)
    merged.update(json.loads(p.read_text(encoding="utf-8")))
    if "custom_recognizers" in merged and isinstance(
        merged["custom_recognizers"], dict
    ):
        base = dict(DEFAULT_CONFIG["custom_recognizers"])
        base.update(merged["custom_recognizers"])
        merged["custom_recognizers"] = base
    return merged


def save_config(path_str: str, cfg: dict[str, Any]) -> None:
    p = config_path_resolve(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")


def merge_patch(path_str: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = load_config(path_str)
    for k, v in patch.items():
        if (
            k == "custom_recognizers"
            and isinstance(v, dict)
            and isinstance(current.get("custom_recognizers"), dict)
        ):
            current["custom_recognizers"].update(v)
        else:
            current[k] = v
    save_config(path_str, current)
    return current
