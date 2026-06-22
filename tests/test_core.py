from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from src.backup import BackupManager
from src.detector import detect_save
from src.safe_save import SafeSaveError, safe_write_text


class CoreWorkflowTests(unittest.TestCase):
    def test_detect_json_xml_ini_text_and_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_file = root / "save.json"
            xml_file = root / "save.xml"
            ini_file = root / "config.ini"
            text_file = root / "notes.save"
            binary_file = root / "slot.sav"
            json_file.write_text('{"gold": 10, "level": 2}', encoding="utf-8")
            xml_file.write_text("<save><gold>10</gold></save>", encoding="utf-8")
            ini_file.write_text("[player]\ngold=10\nlevel=2\n", encoding="utf-8")
            text_file.write_text("gold=10\nlevel=2\n", encoding="utf-8")
            binary_file.write_bytes(bytes(range(256)))

            self.assertEqual(detect_save(json_file).detected_type, "json")
            self.assertEqual(detect_save(xml_file).detected_type, "xml")
            self.assertEqual(detect_save(ini_file).detected_type, "ini")
            self.assertEqual(detect_save(text_file).detected_type, "text")
            binary = detect_save(binary_file)
            self.assertEqual(binary.detected_type, "binary")
            self.assertTrue(binary.read_only)

    def test_backup_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save = root / "save.json"
            save.write_text('{"gold": 10}', encoding="utf-8")
            manager = BackupManager(root / "backups")
            backup = manager.create_backup(save)

            save.write_text('{"gold": 99}', encoding="utf-8")
            manager.restore_backup(backup, save, backup_current=True)

            self.assertEqual(json.loads(save.read_text(encoding="utf-8"))["gold"], 10)
            self.assertGreaterEqual(len(manager.list_backups(save)), 2)

    def test_safe_json_save_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "save.json"
            save.write_text('{"gold": 10}', encoding="utf-8")

            safe_write_text(save, '{"gold": 25}', "json", "utf-8")
            self.assertEqual(json.loads(save.read_text(encoding="utf-8"))["gold"], 25)

            with self.assertRaises((SafeSaveError, json.JSONDecodeError)):
                safe_write_text(save, '{"gold": ', "json", "utf-8")

            self.assertEqual(json.loads(save.read_text(encoding="utf-8"))["gold"], 25)

    def test_compressed_or_unsupported_opens_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsupported = root / "unknown.dat"
            unsupported.write_bytes(b"\x00\xff\x10\x80" * 128)

            result = detect_save(unsupported)

            self.assertTrue(result.read_only)
            self.assertFalse(result.can_edit)


if __name__ == "__main__":
    unittest.main()
