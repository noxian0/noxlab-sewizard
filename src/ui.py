"""PySide6 UI for NOXLAB SEWIZARD."""

from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from .backup import BackupEntry, BackupManager
    from .detector import COMMON_SEARCH_TERMS, ENGINE_PROFILES, FILE_EXTENSIONS, DetectionResult, detect_save
    from .editors.hex_viewer import HexViewer
    from .editors.ini_editor import IniEditor
    from .editors.json_editor import JsonEditor
    from .editors.text_editor import TextEditor
    from .editors.xml_editor import XmlEditor
    from .safe_save import SafeSaveError, safe_write_text
    from .settings import AppSettings, RecentStore, SettingsStore
    from .paths import asset_path
except ImportError:
    from backup import BackupEntry, BackupManager
    from detector import COMMON_SEARCH_TERMS, ENGINE_PROFILES, FILE_EXTENSIONS, DetectionResult, detect_save
    from editors.hex_viewer import HexViewer
    from editors.ini_editor import IniEditor
    from editors.json_editor import JsonEditor
    from editors.text_editor import TextEditor
    from editors.xml_editor import XmlEditor
    from safe_save import SafeSaveError, safe_write_text
    from settings import AppSettings, RecentStore, SettingsStore
    from paths import asset_path


ASCII_TITLE = r"""
 _   _  _____  ___        _    ____    ____  _______        _____ _____   _    ____  ____
| \ | |/ _ \ \/ / |      / \  | __ )  / ___|| ____\ \      / /_ _|__  /  / \  |  _ \|  _ \
|  \| | | | \  /| |     / _ \ |  _ \  \___ \|  _|  \ \ /\ / / | |  / /  / _ \ | |_) | | | |
| |\  | |_| /  \| |___ / ___ \| |_) |  ___) | |___  \ V  V /  | | / /_ / ___ \|  _ <| |_| |
|_| \_|\___/_/\_\_____/_/   \_\____/  |____/|_____|  \_/\_/  |___/____/_/   \_\_| \_\____/
""".strip("\n")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NOXLAB SEWIZARD")
        icon_file = asset_path("noxlab_sewizard_wand.ico")
        if not icon_file.exists():
            icon_file = asset_path("noxlab_sewizard.ico")
        if icon_file.exists():
            self.setWindowIcon(QIcon(str(icon_file)))
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.recent_store = RecentStore(max_items=self.settings.max_recent)
        self.backups = BackupManager(self.settings.backup_folder)
        self.current_file: Path | None = None
        self.current_detection: DetectionResult | None = None
        self.current_backup: Path | None = None
        self.current_kind = "text"

        self._build_ui()
        self._apply_theme()
        self._set_empty_state()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(10)

        root.addLayout(self._header())

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(210)
        for label in [
            "Open Save File",
            "Recent Saves",
            "Engine / Format Profiles",
            "Backup Manager",
            "Tools",
            "Settings",
            "About",
        ]:
            self.sidebar.addItem(QListWidgetItem(label))
        self.sidebar.itemClicked.connect(self._sidebar_action)
        body.addWidget(self.sidebar)

        main = QWidget()
        body.addWidget(main, 1)
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        main_layout.addWidget(self._file_panel())
        main_layout.addWidget(self._editor_panel(), 1)
        main_layout.addLayout(self._action_bar())

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(92)
        root.addWidget(self.log)

    def _header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(ASCII_TITLE)
        title.setObjectName("AsciiTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(False)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title.setContentsMargins(0, 8, 0, 8)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        contact = QLabel("Discord: noxian_ | GitHub: noxian0")
        contact.setObjectName("ContactLine")
        contact.setTextFormat(Qt.TextFormat.PlainText)
        contact.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_box.addWidget(title)
        title_box.addWidget(contact)

        info = QVBoxLayout()
        subtitle = QLabel("Local Game Save Editor")
        subtitle.setObjectName("Subtitle")
        warning = QLabel("Offline / single-player saves only.")
        warning.setObjectName("Warning")
        disclaimer = QLabel("Edit only saves for games you own. Backups are strongly recommended.")
        disclaimer.setObjectName("SmallText")
        info.addStretch(1)
        info.addWidget(subtitle)
        info.addWidget(warning)
        info.addWidget(disclaimer)
        info.addStretch(1)

        layout.addLayout(title_box, 1)
        layout.addLayout(info)
        return layout

    def _file_panel(self) -> QWidget:
        group = QGroupBox("Save File")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        self.path_label = QLabel("")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detected_label = QLabel("")
        self.backup_label = QLabel("")
        self.mode_label = QLabel("")

        self.selection_mode = QComboBox()
        self.selection_mode.addItems(["Auto-detect", "Game engine/profile", "File extension"])
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(ENGINE_PROFILES)
        self.extension_combo = QComboBox()
        self.extension_combo.addItems(FILE_EXTENSIONS)

        self.metadata = QTableWidget(0, 2)
        self.metadata.setHorizontalHeaderLabels(["Field", "Value"])
        self.metadata.horizontalHeader().setStretchLastSection(True)
        self.metadata.verticalHeader().setVisible(False)
        self.metadata.setMaximumHeight(132)

        self.backup_combo = QComboBox()
        self.restore_button = QPushButton("Restore Backup")
        self.restore_button.clicked.connect(self.restore_selected_backup)

        layout.addWidget(QLabel("Selected file path"), 0, 0)
        layout.addWidget(self.path_label, 0, 1, 1, 3)
        layout.addWidget(QLabel("Detected format"), 1, 0)
        layout.addWidget(self.detected_label, 1, 1)
        layout.addWidget(QLabel("Mode"), 1, 2)
        layout.addWidget(self.mode_label, 1, 3)
        layout.addWidget(QLabel("Selection mode"), 2, 0)
        layout.addWidget(self.selection_mode, 2, 1)
        layout.addWidget(QLabel("Engine/profile"), 2, 2)
        layout.addWidget(self.profile_combo, 2, 3)
        layout.addWidget(QLabel("Extension"), 3, 0)
        layout.addWidget(self.extension_combo, 3, 1)
        layout.addWidget(QLabel("Backup status"), 3, 2)
        layout.addWidget(self.backup_label, 3, 3)
        layout.addWidget(self.metadata, 4, 0, 1, 4)
        layout.addWidget(self.backup_combo, 5, 0, 1, 3)
        layout.addWidget(self.restore_button, 5, 3)
        return group

    def _editor_panel(self) -> QWidget:
        group = QGroupBox("Editor")
        layout = QVBoxLayout(group)

        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search keys, values, text, or hex")
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_current_editor)
        self.common_terms = QComboBox()
        self.common_terms.addItem("Common terms")
        self.common_terms.addItems(COMMON_SEARCH_TERMS)
        self.common_terms.currentTextChanged.connect(self._common_term_selected)
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(self.search_button)
        search_row.addWidget(self.common_terms)
        layout.addLayout(search_row)

        self.editor_stack = QStackedWidget()
        self.json_editor = JsonEditor()
        self.xml_editor = XmlEditor()
        self.ini_editor = IniEditor()
        self.text_editor = TextEditor()
        self.hex_viewer = HexViewer()
        self.editor_stack.addWidget(self.json_editor)
        self.editor_stack.addWidget(self.xml_editor)
        self.editor_stack.addWidget(self.ini_editor)
        self.editor_stack.addWidget(self.text_editor)
        self.editor_stack.addWidget(self.hex_viewer)
        layout.addWidget(self.editor_stack, 1)
        return group

    def _action_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.open_button = QPushButton("Open Save File")
        self.save_button = QPushButton("Save Changes")
        self.export_button = QPushButton("Export Copy")
        self.open_button.clicked.connect(self.open_file_dialog)
        self.save_button.clicked.connect(self.save_changes)
        self.export_button.clicked.connect(self.export_copy)
        layout.addStretch(1)
        layout.addWidget(self.open_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.export_button)
        return layout

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #08090b;
                color: #ece8e8;
                font-family: Segoe UI, Arial;
                font-size: 10pt;
            }
            #AsciiTitle {
                color: #ff2020;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 9pt;
                font-weight: 700;
            }
            #ContactLine {
                color: #ff4a4a;
                font-family: Segoe UI, Arial;
                font-size: 11pt;
                font-weight: 700;
            }
            #Subtitle {
                color: #ffffff;
                font-size: 20pt;
                font-weight: 700;
            }
            #Warning {
                color: #ff3b3b;
                font-size: 11pt;
                font-weight: 700;
            }
            #SmallText {
                color: #b7aaaa;
            }
            QGroupBox {
                border: 1px solid #3a1114;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                background: #111215;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #ff4040;
            }
            QListWidget, QTextEdit, QPlainTextEdit, QTreeWidget, QTableWidget, QComboBox, QLineEdit {
                background: #0d0f12;
                border: 1px solid #2b2f36;
                border-radius: 4px;
                color: #f3eeee;
                selection-background-color: #8c1f24;
            }
            QListWidget::item {
                padding: 9px;
            }
            QListWidget::item:selected {
                background: #8c1f24;
            }
            QPushButton {
                background: #8f151d;
                border: 1px solid #c92832;
                border-radius: 4px;
                color: white;
                padding: 7px 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #b71f2a;
            }
            QPushButton:disabled {
                background: #34373c;
                border-color: #474b52;
                color: #8c8c8c;
            }
            QHeaderView::section {
                background: #171a1f;
                color: #ff5a5a;
                border: 1px solid #30343b;
                padding: 4px;
            }
            """
        )

    def _set_empty_state(self) -> None:
        self.path_label.setText("No save file selected.")
        self.detected_label.setText("-")
        self.backup_label.setText("-")
        self.mode_label.setText("-")
        self.save_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.log_action("Ready. Open an offline or single-player save file to begin.")

    def _sidebar_action(self, item: QListWidgetItem) -> None:
        text = item.text()
        if text == "Open Save File":
            self.open_file_dialog()
        elif text == "Recent Saves":
            self.show_recent_dialog()
        elif text == "Engine / Format Profiles":
            self.show_profiles_dialog()
        elif text == "Backup Manager":
            self.show_backup_manager()
        elif text == "Tools":
            self.show_tools_dialog()
        elif text == "Settings":
            self.show_settings_dialog()
        elif text == "About":
            self.show_about_dialog()

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Save File", str(Path.home()), "All files (*.*)")
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path) -> None:
        try:
            detection = detect_save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Open Save File", str(exc))
            return

        self.current_file = path
        self.current_detection = detection
        self.current_kind = detection.detected_type if detection.detected_type in {"json", "xml", "ini", "text"} else "binary"
        self.current_backup = None
        self.recent_store.add(path)
        self._show_detection(detection)
        self._load_editor(path, detection)
        self._refresh_backups()

        if detection.warning:
            self.log_action(detection.warning)
        self.log_action(f"Save loaded: {path.name}")
        self.log_action(f"Format detected: {detection.detected_type}")

    def _show_detection(self, detection: DetectionResult) -> None:
        self.path_label.setText(detection.path)
        self.detected_label.setText(detection.detected_type)
        mode = "Read-only" if detection.read_only else "Editable"
        self.mode_label.setText(mode)
        self.backup_label.setText("Pending" if detection.can_edit else "Available for manual backup/export")
        self.profile_combo.setCurrentText(detection.profile_hint if detection.profile_hint in ENGINE_PROFILES else "Unknown / manual mode")
        if detection.extension in FILE_EXTENSIONS:
            self.extension_combo.setCurrentText(detection.extension)
        self.metadata.setRowCount(0)
        for key, value in detection.metadata.items():
            row = self.metadata.rowCount()
            self.metadata.insertRow(row)
            self.metadata.setItem(row, 0, QTableWidgetItem(str(key)))
            self.metadata.setItem(row, 1, QTableWidgetItem(str(value)))
        self.metadata.resizeColumnsToContents()

    def _load_editor(self, path: Path, detection: DetectionResult) -> None:
        self.save_button.setEnabled(False)
        self.export_button.setEnabled(True)
        encoding = detection.text_encoding or "utf-8"

        if detection.can_edit and not detection.read_only:
            if self.settings.always_backup:
                try:
                    self.current_backup = self.backups.create_backup(path)
                except OSError as exc:
                    QMessageBox.critical(self, "Backup Failed", f"Editing is disabled because backup failed:\n{exc}")
                    self._load_hex(path)
                    return
                self.backup_label.setText(f"Created: {self.current_backup.name}")
                self.log_action(f"Backup created: {self.current_backup.name}")
            try:
                text = path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                text = path.read_text(encoding=encoding, errors="replace")

            try:
                if detection.detected_type == "json":
                    self.json_editor.load_text(text)
                    self.editor_stack.setCurrentWidget(self.json_editor)
                elif detection.detected_type == "xml":
                    self.xml_editor.load_text(text)
                    self.editor_stack.setCurrentWidget(self.xml_editor)
                elif detection.detected_type == "ini":
                    self.ini_editor.load_text(text)
                    self.editor_stack.setCurrentWidget(self.ini_editor)
                else:
                    self.text_editor.load_text(text, "text")
                    self.editor_stack.setCurrentWidget(self.text_editor)
            except Exception as exc:
                self.log_action(f"Editor load failed, switching to read-only hex view: {exc}")
                self._load_hex(path)
                return
            self.save_button.setEnabled(True)
            return

        self._load_hex(path)

    def _load_hex(self, path: Path) -> None:
        self.hex_viewer.load_path(path)
        self.editor_stack.setCurrentWidget(self.hex_viewer)
        self.save_button.setEnabled(False)
        self.mode_label.setText("Read-only")
        if self.current_detection and self.current_detection.warning:
            self.backup_label.setText("Read-only; export/backup available")

    def _refresh_backups(self) -> None:
        self.backup_combo.clear()
        if not self.current_file:
            self.restore_button.setEnabled(False)
            return
        entries = self.backups.list_backups(self.current_file)
        for entry in entries:
            self.backup_combo.addItem(f"{entry.path.name}  ({entry.created_at})", str(entry.path))
        self.restore_button.setEnabled(bool(entries))

    def _current_editor(self):
        return self.editor_stack.currentWidget()

    def save_changes(self) -> None:
        if not self.current_file or not self.current_detection:
            return
        if self.current_detection.read_only or not self.current_detection.can_edit:
            QMessageBox.information(self, "Save Disabled", "This save format is not safely editable yet.")
            return
        editor = self._current_editor()
        valid, error = editor.validate()
        if not valid:
            QMessageBox.warning(self, "Validation Failed", error)
            self.log_action(f"Validation failed: {error}")
            return
        if not editor.is_modified():
            self.log_action("No changes to save.")
            return

        changes = editor.changed_summary()
        if changes:
            preview = "\n".join(changes[:40])
        else:
            preview = "Changes detected."
        answer = QMessageBox.question(
            self,
            "Save Changes",
            f"Review changes before saving:\n\n{preview}\n\nWrite changes to the selected save?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.log_action("Save cancelled.")
            return

        if self.settings.always_backup:
            try:
                self.current_backup = self.backups.create_backup(self.current_file)
                self.log_action(f"Backup created: {self.current_backup.name}")
            except OSError as exc:
                QMessageBox.critical(self, "Backup Failed", f"Save cancelled because backup failed:\n{exc}")
                return

        encoding = self.current_detection.text_encoding or "utf-8"
        try:
            safe_write_text(self.current_file, editor.serialize(), self.current_kind, encoding)
        except SafeSaveError as exc:
            QMessageBox.critical(self, "Safe Save Failed", str(exc))
            self.log_action(f"Safe save failed: {exc}")
            return

        self.log_action("Changes saved.")
        self.open_file(self.current_file)

    def export_copy(self) -> None:
        if not self.current_file:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Export Copy", str(self.current_file.with_suffix(self.current_file.suffix + ".copy")))
        if not target:
            return
        target_path = Path(target)
        editor = self._current_editor()
        if self.current_detection and self.current_detection.can_edit and not self.current_detection.read_only and editor.is_modified():
            valid, error = editor.validate()
            if not valid:
                QMessageBox.warning(self, "Export Failed", error)
                return
            target_path.write_text(editor.serialize(), encoding=self.current_detection.text_encoding or "utf-8")
        else:
            shutil.copy2(self.current_file, target_path)
        self.log_action(f"Exported copy: {target_path}")

    def restore_selected_backup(self) -> None:
        if not self.current_file:
            return
        backup_path = self.backup_combo.currentData()
        if not backup_path:
            return
        answer = QMessageBox.question(
            self,
            "Restore Backup",
            "Restore the selected backup over the current save? A backup of the current file will be created first.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            current_backup = self.backups.restore_backup(backup_path, self.current_file, backup_current=True)
        except OSError as exc:
            QMessageBox.critical(self, "Restore Failed", str(exc))
            return
        if current_backup:
            self.log_action(f"Backup created before restore: {current_backup.name}")
        self.log_action("Backup restored.")
        self.open_file(self.current_file)

    def search_current_editor(self) -> None:
        term = self.search_box.text()
        editor = self._current_editor()
        count = editor.search(term) if hasattr(editor, "search") else 0
        self.log_action(f"Search results for '{term}': {count}")

    def _common_term_selected(self, text: str) -> None:
        if text and text != "Common terms":
            self.search_box.setText(text)
            self.search_current_editor()

    def show_recent_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Recent Saves")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for item in self.recent_store.load():
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        buttons = QHBoxLayout()
        open_button = QPushButton("Open")
        clear_button = QPushButton("Clear")
        close_button = QPushButton("Close")
        buttons.addWidget(open_button)
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        def open_selected() -> None:
            item = list_widget.currentItem()
            if item:
                dialog.accept()
                self.open_file(Path(item.text()))

        def clear_recent() -> None:
            self.recent_store.clear()
            list_widget.clear()
            self.log_action("Recent saves cleared.")

        open_button.clicked.connect(open_selected)
        clear_button.clicked.connect(clear_recent)
        close_button.clicked.connect(dialog.reject)
        dialog.resize(720, 360)
        dialog.exec()

    def show_profiles_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Engine / Format Profiles",
            "Profiles are selectors for detection hints in the MVP. Unknown formats remain read-only unless a safe editor is available.",
        )

    def show_tools_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Tools",
            "Available now: metadata view, safe backup, restore, export copy, text search, JSON search, INI search, XML search, and read-only hex view.",
        )

    def show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "About NOXLAB SEWIZARD",
            "NOXLAB SEWIZARD\n\nLocal Game Save Editor\n\nOffline / single-player saves only. No cloud, no account, no live process editing.",
        )

    def show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings
            self.settings_store.save(self.settings)
            self.backups.set_folder(self.settings.backup_folder)
            self.recent_store.max_items = self.settings.max_recent
            self._refresh_backups()
            self.log_action("Settings saved.")

    def show_backup_manager(self) -> None:
        dialog = BackupManagerDialog(self.backups, self.current_file, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_backups()

    def log_action(self, message: str) -> None:
        self.log.append(message)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = AppSettings(**settings.__dict__)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.backup_folder = QLineEdit(self.settings.backup_folder)
        browse = QPushButton("Browse")
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.backup_folder, 1)
        folder_row.addWidget(browse)
        self.always_backup = QCheckBox()
        self.always_backup.setChecked(self.settings.always_backup)
        self.unknown_read_only = QCheckBox()
        self.unknown_read_only.setChecked(self.settings.unknown_read_only)
        self.hex_editing = QCheckBox()
        self.hex_editing.setChecked(self.settings.advanced_hex_editing)
        form.addRow("Backup folder location", folder_row)
        form.addRow("Always create backup", self.always_backup)
        form.addRow("Open unknown files as read-only", self.unknown_read_only)
        form.addRow("Enable advanced hex editing", self.hex_editing)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        def browse_folder() -> None:
            folder = QFileDialog.getExistingDirectory(self, "Backup Folder", self.backup_folder.text())
            if folder:
                self.backup_folder.setText(folder)

        def save_settings() -> None:
            self.settings.backup_folder = self.backup_folder.text()
            self.settings.always_backup = self.always_backup.isChecked()
            self.settings.unknown_read_only = self.unknown_read_only.isChecked()
            self.settings.advanced_hex_editing = self.hex_editing.isChecked()
            self.accept()

        browse.clicked.connect(browse_folder)
        save.clicked.connect(save_settings)
        cancel.clicked.connect(self.reject)


class BackupManagerDialog(QDialog):
    def __init__(self, manager: BackupManager, current_file: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.current_file = current_file
        self.setWindowTitle("Backup Manager")
        self.resize(760, 420)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        self.restore = QPushButton("Restore")
        self.delete = QPushButton("Delete")
        self.open_folder = QPushButton("Open Folder")
        self.close = QPushButton("Close")
        buttons.addWidget(self.restore)
        buttons.addWidget(self.delete)
        buttons.addWidget(self.open_folder)
        buttons.addStretch(1)
        buttons.addWidget(self.close)
        layout.addLayout(buttons)

        self.restore.clicked.connect(self.restore_selected)
        self.delete.clicked.connect(self.delete_selected)
        self.open_folder.clicked.connect(self.open_backup_folder)
        self.close.clicked.connect(self.accept)
        self.reload()

    def reload(self) -> None:
        self.list_widget.clear()
        for entry in self.manager.list_backups(self.current_file):
            item = QListWidgetItem(f"{entry.path.name} | {entry.created_at} | {entry.size} bytes")
            item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
            self.list_widget.addItem(item)
        self.restore.setEnabled(self.current_file is not None and self.list_widget.count() > 0)
        self.delete.setEnabled(self.list_widget.count() > 0)

    def selected_path(self) -> Path | None:
        item = self.list_widget.currentItem()
        if not item:
            return None
        return Path(item.data(Qt.ItemDataRole.UserRole))

    def restore_selected(self) -> None:
        path = self.selected_path()
        if not path or not self.current_file:
            return
        answer = QMessageBox.question(self, "Restore Backup", "Restore selected backup over the current save?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.restore_backup(path, self.current_file, backup_current=True)
        self.accept()

    def delete_selected(self) -> None:
        path = self.selected_path()
        if not path:
            return
        answer = QMessageBox.question(self, "Delete Backup", "Delete selected backup?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.delete_backup(path)
        self.reload()

    def open_backup_folder(self) -> None:
        try:
            self.manager.open_folder()
        except RuntimeError as exc:
            QMessageBox.information(self, "Backup Folder", str(exc))
