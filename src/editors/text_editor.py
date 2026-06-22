"""Plain text editor widget."""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class TextEditor(QWidget):
    kind = "text"

    def __init__(self) -> None:
        super().__init__()
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.original_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

    def load_text(self, text: str, kind: str = "text") -> None:
        self.kind = kind
        self.original_text = text
        self.editor.setPlainText(text)

    def serialize(self) -> str:
        return self.editor.toPlainText()

    def validate(self) -> tuple[bool, str]:
        return True, ""

    def is_modified(self) -> bool:
        return self.serialize() != self.original_text

    def changed_summary(self, limit: int = 30) -> list[str]:
        old_lines = self.original_text.splitlines()
        new_lines = self.serialize().splitlines()
        changes: list[str] = []
        max_len = max(len(old_lines), len(new_lines))
        for index in range(max_len):
            old = old_lines[index] if index < len(old_lines) else ""
            new = new_lines[index] if index < len(new_lines) else ""
            if old != new:
                changes.append(f"line {index + 1}: {old!r} -> {new!r}")
            if len(changes) >= limit:
                changes.append("...")
                break
        return changes

    def search(self, term: str) -> int:
        selections = []
        if term:
            document = self.editor.document()
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
        self.editor.setExtraSelections(selections)
        return len(selections)
