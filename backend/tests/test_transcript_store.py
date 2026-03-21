import os
import tempfile
import unittest
from pathlib import Path

from voz_a_texto.desktop.transcript_store import TranscriptStore


class TestTranscriptStoreEmpty(unittest.TestCase):
    def test_empty_store_has_no_entries(self):
        store = TranscriptStore()
        self.assertEqual(store.count, 0)
        self.assertEqual(store.entries, [])

    def test_empty_store_full_text_is_empty(self):
        store = TranscriptStore()
        self.assertEqual(store.full_text, "")

    def test_empty_store_cannot_export(self):
        store = TranscriptStore()
        self.assertFalse(store.can_export)

    def test_empty_store_last_text_is_empty(self):
        store = TranscriptStore()
        self.assertEqual(store.last_text, "")


class TestTranscriptStoreAppend(unittest.TestCase):
    def test_append_single_entry(self):
        store = TranscriptStore()
        store.append("Hola mundo")
        self.assertEqual(store.count, 1)
        self.assertEqual(store.full_text, "Hola mundo")
        self.assertTrue(store.can_export)

    def test_append_multiple_entries(self):
        store = TranscriptStore()
        store.append("Primera linea")
        store.append("Segunda linea")
        self.assertEqual(store.count, 2)
        self.assertEqual(store.full_text, "Primera linea\nSegunda linea")

    def test_append_strips_whitespace(self):
        store = TranscriptStore()
        store.append("  texto con espacios  ")
        self.assertEqual(store.entries[0].text, "texto con espacios")

    def test_append_ignores_empty_text(self):
        store = TranscriptStore()
        store.append("")
        store.append("   ")
        store.append(None)
        self.assertEqual(store.count, 0)

    def test_append_with_timestamp(self):
        store = TranscriptStore()
        store.append("transcripcion", timestamp="2026-03-20T16:00:00")
        self.assertEqual(store.entries[0].timestamp, "2026-03-20T16:00:00")

    def test_last_text_returns_most_recent(self):
        store = TranscriptStore()
        store.append("primera")
        store.append("segunda")
        store.append("tercera")
        self.assertEqual(store.last_text, "tercera")

    def test_entries_returns_copy(self):
        store = TranscriptStore()
        store.append("a")
        entries = store.entries
        entries.clear()
        self.assertEqual(store.count, 1, "Modificar la lista devuelta no debe afectar el store")


class TestTranscriptStoreClear(unittest.TestCase):
    def test_clear_removes_all_entries(self):
        store = TranscriptStore()
        store.append("uno")
        store.append("dos")
        store.clear()
        self.assertEqual(store.count, 0)
        self.assertEqual(store.full_text, "")
        self.assertFalse(store.can_export)

    def test_append_after_clear(self):
        store = TranscriptStore()
        store.append("antes")
        store.clear()
        store.append("despues")
        self.assertEqual(store.count, 1)
        self.assertEqual(store.full_text, "despues")


class TestTranscriptStoreExport(unittest.TestCase):
    def test_export_writes_file(self):
        store = TranscriptStore()
        store.append("Linea uno")
        store.append("Linea dos")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = store.export_to_file(tmp_path)
            self.assertEqual(result, Path(tmp_path))
            content = Path(tmp_path).read_text(encoding="utf-8")
            self.assertEqual(content, "Linea uno\nLinea dos")
        finally:
            os.unlink(tmp_path)

    def test_export_raises_on_empty_store(self):
        store = TranscriptStore()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with self.assertRaises(ValueError):
                store.export_to_file(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_export_raises_on_invalid_path(self):
        store = TranscriptStore()
        store.append("contenido")
        with self.assertRaises(OSError):
            store.export_to_file("/ruta/inexistente/archivo.txt")


if __name__ == "__main__":
    unittest.main()
