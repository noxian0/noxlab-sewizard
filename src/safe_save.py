"""Validation-first save writing."""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET


class SafeSaveError(RuntimeError):
    """Raised when a save cannot be safely validated or written."""


def validate_text_for_kind(kind: str, text: str) -> None:
    try:
        if kind == "json":
            json.loads(text)
        elif kind == "xml":
            ET.fromstring(text)
        elif kind == "ini":
            parser = configparser.ConfigParser()
            parser.read_string(text)
            if not parser.sections():
                raise SafeSaveError("INI validation failed: no sections found.")
        elif kind == "text":
            return
        else:
            raise SafeSaveError(f"Saving is disabled for unsupported type: {kind}")
    except (json.JSONDecodeError, ET.ParseError, configparser.Error) as exc:
        raise SafeSaveError(str(exc)) from exc


def safe_write_text(target_file: str | Path, text: str, kind: str, encoding: str = "utf-8") -> None:
    target = Path(target_file)
    validate_text_for_kind(kind, text)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".sewizard.tmp", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)

        reopened = tmp_path.read_text(encoding=encoding)
        validate_text_for_kind(kind, reopened)
        os.replace(tmp_path, target)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            if isinstance(exc, SafeSaveError):
                raise
            raise SafeSaveError(str(exc)) from exc
