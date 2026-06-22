"""Read-only binary/hex viewer."""

from __future__ import annotations

from pathlib import Path
import string

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class HexViewer(QWidget):
    kind = "binary"

    def __init__(self) -> None:
        super().__init__()
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.viewer.setMaximumBlockCount(20000)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.viewer)

    def load_bytes(self, data: bytes, max_bytes: int = 1024 * 1024) -> None:
        truncated = len(data) > max_bytes
        shown = data[:max_bytes]
        self.viewer.setPlainText(format_hex(shown, truncated, len(data)))

    def load_path(self, path: str | Path) -> None:
        self.load_bytes(Path(path).read_bytes())

    def serialize(self) -> str:
        raise RuntimeError("Hex viewer is read-only.")

    def validate(self) -> tuple[bool, str]:
        return False, "Binary editing is disabled by default."

    def is_modified(self) -> bool:
        return False

    def changed_summary(self, limit: int = 30) -> list[str]:
        return []

    def search(self, term: str) -> int:
        selections = []
        if term:
            document = self.viewer.document()
            cursor = QTextCursor(document)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#7a1e1e"))
            while True:
                cursor = document.find(term, cursor)
                if cursor.isNull():
                    break
                selection = QPlainTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = fmt
                selections.append(selection)
        self.viewer.setExtraSelections(selections)
        return len(selections)


def format_hex(data: bytes, truncated: bool = False, total_size: int | None = None) -> str:
    lines = []
    printable = set(bytes(string.printable, "ascii"))
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{byte:02X}" for byte in chunk)
        hex_part = hex_part.ljust(47)
        ascii_part = "".join(chr(byte) if byte in printable and byte not in b"\r\n\t\x0b\x0c" else "." for byte in chunk)
        lines.append(f"{offset:08X}  {hex_part}  {ascii_part}")
    if truncated:
        lines.append("")
        lines.append(f"[Hex preview truncated at {len(data):,} bytes of {total_size:,} total bytes.]")
    return "\n".join(lines)
