"""Conservative save-file detection for NOXLAB SEWIZARD."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import base64
import configparser
import gzip
import json
import math
from pathlib import Path
import sqlite3
import string
import xml.etree.ElementTree as ET
import zlib

try:
    from .profiles.rpg_maker import detect_rpg_maker_payload
except ImportError:
    from profiles.rpg_maker import detect_rpg_maker_payload


ENGINE_PROFILES = [
    "Unity",
    "Unreal Engine",
    "Godot",
    "RPG Maker MV/MZ",
    "RPG Maker VX Ace",
    "Ren'Py",
    "GameMaker",
    "Construct",
    "Source Engine",
    "Bethesda Creation Engine",
    "Minecraft / NBT-style data",
    "Generic JSON save",
    "Generic XML save",
    "Generic INI/CFG save",
    "Generic text save",
    "Generic binary save / hex view",
    "Unknown / manual mode",
]

FILE_EXTENSIONS = [
    ".sav",
    ".save",
    ".dat",
    ".bin",
    ".json",
    ".xml",
    ".ini",
    ".cfg",
    ".txt",
    ".slot",
    ".profile",
    ".player",
    ".rpgsave",
    ".rvdata",
    ".rvdata2",
    ".rxdata",
    ".sol",
    ".plist",
    ".pak",
    ".db",
    ".sqlite",
    ".bytes",
    ".data",
    ".backup",
    ".bak",
]

COMMON_SEARCH_TERMS = [
    "money",
    "gold",
    "coin",
    "level",
    "xp",
    "health",
    "inventory",
    "item",
    "skill",
    "quest",
]

TEXT_EXTENSIONS = {".txt", ".log", ".save", ".profile", ".player", ".cfg"}
INI_EXTENSIONS = {".ini", ".cfg"}
JSON_EXTENSIONS = {".json"}
XML_EXTENSIONS = {".xml", ".plist"}
SQLITE_EXTENSIONS = {".db", ".sqlite"}
LIKELY_COMPRESSED_EXTENSIONS = {".zip", ".gz", ".pak"}
STRUCTURED_EDITABLE = {"json", "xml", "ini", "text"}


@dataclass
class DetectionResult:
    path: str
    filename: str
    extension: str
    size: int
    modified_at: str
    detected_type: str
    profile_hint: str
    is_text: bool
    is_binary: bool
    is_compressed: bool
    is_encrypted_like: bool
    can_edit: bool
    read_only: bool
    text_encoding: str | None = None
    warning: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def human_size(self) -> str:
        return format_size(self.size)


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def detect_save(path: str | Path, max_parse_bytes: int = 16 * 1024 * 1024) -> DetectionResult:
    save_path = Path(path)
    stat = save_path.stat()
    extension = save_path.suffix.lower()
    modified_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    raw = save_path.read_bytes()

    base = {
        "path": str(save_path),
        "filename": save_path.name,
        "extension": extension or "(none)",
        "size": stat.st_size,
        "modified_at": modified_at,
    }

    metadata: dict[str, str] = {
        "File name": save_path.name,
        "Path": str(save_path),
        "Size": format_size(stat.st_size),
        "Modified": modified_at,
        "Extension": extension or "(none)",
    }

    if not raw:
        return DetectionResult(
            **base,
            detected_type="text",
            profile_hint="Generic text save",
            is_text=True,
            is_binary=False,
            is_compressed=False,
            is_encrypted_like=False,
            can_edit=True,
            read_only=False,
            text_encoding="utf-8",
            metadata=metadata | {"Notes": "Empty file"},
        )

    if raw.startswith(b"SQLite format 3\x00"):
        return DetectionResult(
            **base,
            detected_type="sqlite",
            profile_hint="SQLite database",
            is_text=False,
            is_binary=True,
            is_compressed=False,
            is_encrypted_like=False,
            can_edit=False,
            read_only=True,
            warning="SQLite files are detected read-only in this MVP. Editing will be added with a dedicated viewer.",
            metadata=metadata | _sqlite_metadata(save_path),
        )

    compression = detect_compression(raw, extension)
    if compression:
        return DetectionResult(
            **base,
            detected_type=compression,
            profile_hint="Compressed or packed save",
            is_text=False,
            is_binary=True,
            is_compressed=True,
            is_encrypted_like=False,
            can_edit=False,
            read_only=True,
            warning="This save appears compressed or packed. It is opened read-only until this format has safe profile support.",
            metadata=metadata | {"Container": compression},
        )

    if stat.st_size > max_parse_bytes:
        entropy = shannon_entropy(raw[: max_parse_bytes])
        return DetectionResult(
            **base,
            detected_type="binary",
            profile_hint="Generic binary save / hex view",
            is_text=False,
            is_binary=True,
            is_compressed=False,
            is_encrypted_like=entropy > 7.4,
            can_edit=False,
            read_only=True,
            warning="Large saves are opened read-only in this MVP unless a known safe profile is detected.",
            metadata=metadata | {"Entropy sample": f"{entropy:.2f}"},
        )

    if looks_like_raw_binary(raw):
        entropy = shannon_entropy(raw)
        encrypted_like = entropy > 7.4
        warning = "This save format is not safely editable yet."
        if encrypted_like:
            warning = "This save looks encrypted or packed and is not safely editable yet."
        return DetectionResult(
            **base,
            detected_type="binary",
            profile_hint="Generic binary save / hex view",
            is_text=False,
            is_binary=True,
            is_compressed=False,
            is_encrypted_like=encrypted_like,
            can_edit=False,
            read_only=True,
            warning=warning,
            metadata=metadata | {"Entropy": f"{entropy:.2f}", "Mode": "Read-only hex view"},
        )

    text_info = decode_text(raw)
    if text_info is not None:
        text, encoding = text_info
        stripped = text.lstrip("\ufeff\r\n\t ")
        metadata["Encoding"] = encoding

        if extension == ".rpgsave":
            rpg_result = detect_rpg_maker_payload(text)
            if rpg_result.kind == "json":
                metadata.update(rpg_result.metadata)
                return _result(
                    base,
                    metadata,
                    "json",
                    "RPG Maker MV/MZ",
                    True,
                    False,
                    False,
                    False,
                    True,
                    False,
                    encoding,
                    rpg_result.warning,
                )
            if rpg_result.kind != "unknown":
                metadata.update(rpg_result.metadata)
                return _result(
                    base,
                    metadata,
                    "rpg_maker_unsupported",
                    "RPG Maker MV/MZ",
                    True,
                    False,
                    False,
                    False,
                    False,
                    True,
                    encoding,
                    rpg_result.warning,
                )

        if extension in INI_EXTENSIONS and looks_like_ini(text, extension):
            parser = configparser.ConfigParser()
            try:
                parser.read_string(text)
            except configparser.Error as exc:
                return _result(
                    base,
                    metadata | {"INI error": str(exc)},
                    "text",
                    "Generic text save",
                    True,
                    False,
                    False,
                    False,
                    True,
                    False,
                    encoding,
                    "File looks INI-like but did not parse as INI. It is opened as text.",
                )
            return _result(
                base,
                metadata,
                "ini",
                "Generic INI/CFG save",
                True,
                False,
                False,
                False,
                True,
                False,
                encoding,
            )

        if looks_like_json(stripped, extension):
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                return _result(
                    base,
                    metadata | {"JSON error": str(exc)},
                    "text",
                    "Generic text save",
                    True,
                    False,
                    False,
                    False,
                    True,
                    False,
                    encoding,
                    "File looks JSON-like but did not parse as JSON. It is opened as text.",
                )
            return _result(
                base,
                metadata,
                "json",
                "Generic JSON save",
                True,
                False,
                False,
                False,
                True,
                False,
                encoding,
            )

        if looks_like_xml(stripped, extension):
            try:
                ET.fromstring(text)
            except ET.ParseError as exc:
                return _result(
                    base,
                    metadata | {"XML error": str(exc)},
                    "text",
                    "Generic text save",
                    True,
                    False,
                    False,
                    False,
                    True,
                    False,
                    encoding,
                    "File looks XML-like but did not parse as XML. It is opened as text.",
                )
            return _result(
                base,
                metadata,
                "xml",
                "Generic XML save",
                True,
                False,
                False,
                False,
                True,
                False,
                encoding,
            )

        if looks_like_ini(text, extension):
            parser = configparser.ConfigParser()
            try:
                parser.read_string(text)
            except configparser.Error as exc:
                return _result(
                    base,
                    metadata | {"INI error": str(exc)},
                    "text",
                    "Generic text save",
                    True,
                    False,
                    False,
                    False,
                    True,
                    False,
                    encoding,
                    "File looks INI-like but did not parse as INI. It is opened as text.",
                )
            return _result(
                base,
                metadata,
                "ini",
                "Generic INI/CFG save",
                True,
                False,
                False,
                False,
                True,
                False,
                encoding,
            )

        if is_mostly_printable(text):
            warning = ""
            profile = "Generic text save"
            if extension in {".sav", ".dat", ".bin", ".bytes", ".data"}:
                warning = "This text-like save has a generic extension. It may use a checksum; keep a backup before editing."
            return _result(
                base,
                metadata,
                "text",
                profile,
                True,
                False,
                False,
                False,
                True,
                False,
                encoding,
                warning,
            )

    entropy = shannon_entropy(raw)
    encrypted_like = entropy > 7.4
    warning = "This save format is not safely editable yet."
    if encrypted_like:
        warning = "This save looks encrypted or packed and is not safely editable yet."

    return DetectionResult(
        **base,
        detected_type="binary",
        profile_hint="Generic binary save / hex view",
        is_text=False,
        is_binary=True,
        is_compressed=False,
        is_encrypted_like=encrypted_like,
        can_edit=False,
        read_only=True,
        warning=warning,
        metadata=metadata | {"Entropy": f"{entropy:.2f}", "Mode": "Read-only hex view"},
    )


def _result(
    base: dict[str, str | int],
    metadata: dict[str, str],
    detected_type: str,
    profile_hint: str,
    is_text: bool,
    is_binary: bool,
    is_compressed: bool,
    is_encrypted_like: bool,
    can_edit: bool,
    read_only: bool,
    text_encoding: str | None,
    warning: str = "",
) -> DetectionResult:
    return DetectionResult(
        **base,
        detected_type=detected_type,
        profile_hint=profile_hint,
        is_text=is_text,
        is_binary=is_binary,
        is_compressed=is_compressed,
        is_encrypted_like=is_encrypted_like,
        can_edit=can_edit,
        read_only=read_only,
        text_encoding=text_encoding,
        warning=warning,
        metadata=metadata
        | {
            "Detected type": detected_type,
            "Profile hint": profile_hint,
            "Mode": "Editable" if can_edit and not read_only else "Read-only",
        },
    )


def detect_compression(raw: bytes, extension: str) -> str | None:
    if raw.startswith(b"\x1f\x8b"):
        try:
            gzip.decompress(raw)
            return "gzip"
        except OSError:
            return "gzip-like"
    if raw.startswith(b"PK\x03\x04"):
        return "zip-like"
    if extension in LIKELY_COMPRESSED_EXTENSIONS:
        return "packed-extension"
    try:
        zlib.decompress(raw)
        return "zlib"
    except zlib.error:
        return None


def decode_text(raw: bytes) -> tuple[str, str] | None:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" in text and encoding.startswith("utf-8"):
            continue
        if is_probable_text(text):
            return text, encoding
    return None


def is_probable_text(text: str) -> bool:
    if not text:
        return True
    control = 0
    checked = text[:8192]
    for char in checked:
        if char in "\r\n\t":
            continue
        if ord(char) < 32:
            control += 1
    return control / max(1, len(checked)) < 0.03


def is_mostly_printable(text: str) -> bool:
    printable = set(string.printable)
    checked = text[:8192]
    if not checked:
        return True
    good = sum(1 for char in checked if char in printable or ord(char) > 127)
    return good / len(checked) > 0.92


def looks_like_json(text: str, extension: str) -> bool:
    if extension in JSON_EXTENSIONS or text.startswith("{"):
        return True
    if text.startswith("["):
        stripped = text[1:].lstrip()
        return not stripped or stripped[0] in '{["-0123456789tfn'
    return False


def looks_like_xml(text: str, extension: str) -> bool:
    return extension in XML_EXTENSIONS or text.startswith("<?xml") or text.startswith("<")


def looks_like_ini(text: str, extension: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith(("#", ";"))]
    has_section = any(line.startswith("[") and line.endswith("]") for line in lines)
    has_key_value = any(("=" in line or ":" in line) and not line.startswith("[") for line in lines)
    return has_section and has_key_value and (extension in INI_EXTENSIONS or has_section)


def shannon_entropy(raw: bytes) -> float:
    if not raw:
        return 0.0
    counts = [0] * 256
    for byte in raw:
        counts[byte] += 1
    entropy = 0.0
    length = len(raw)
    for count in counts:
        if count:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


def looks_like_raw_binary(raw: bytes) -> bool:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf")):
        return False
    sample = raw[:8192]
    if not sample:
        return False
    null_ratio = sample.count(0) / len(sample)
    if null_ratio > 0.05:
        return True
    control_bytes = 0
    for byte in sample:
        if byte in (9, 10, 13):
            continue
        if byte < 32:
            control_bytes += 1
    return control_bytes / len(sample) > 0.12


def _sqlite_metadata(path: Path) -> dict[str, str]:
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return {"SQLite": "Header detected; table listing failed"}
    table_names = ", ".join(row[0] for row in rows) if rows else "(no tables)"
    return {"SQLite tables": table_names}


def is_base64_like(text: str) -> bool:
    compact = "".join(text.split())
    if len(compact) < 24:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    if any(char not in allowed for char in compact):
        return False
    try:
        base64.b64decode(compact, validate=False)
    except Exception:
        return False
    return True
