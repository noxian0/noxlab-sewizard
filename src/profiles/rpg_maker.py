"""RPG Maker profile detection stubs.

RPG Maker MV/MZ commonly stores save payloads as LZ-string compressed Base64.
The MVP intentionally does not guess-write those files until a proper decoder and
encoder are integrated and tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
import json


@dataclass
class RpgMakerDetection:
    kind: str
    warning: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def detect_rpg_maker_payload(text: str) -> RpgMakerDetection:
    stripped = text.strip()
    try:
        json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        return RpgMakerDetection(
            kind="json",
            warning="RPG Maker JSON-like save detected. Backup required before editing.",
            metadata={"RPG Maker": "JSON-like payload"},
        )

    compact = "".join(stripped.split())
    if _is_base64(compact):
        return RpgMakerDetection(
            kind="compressed_base64",
            warning="RPG Maker MV/MZ compressed Base64 saves need LZ-string support and are opened read-only in this MVP.",
            metadata={"RPG Maker": "Compressed/Base64-like payload"},
        )

    return RpgMakerDetection(kind="unknown")


def _is_base64(value: str) -> bool:
    if len(value) < 24:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    if any(char not in allowed for char in value):
        return False
    try:
        base64.b64decode(value, validate=False)
    except Exception:
        return False
    return True
