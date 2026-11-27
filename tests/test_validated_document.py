"""Regression tests for validated PDF retention."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from acquisition.database.validated_document import (
    save_validated_document,
)


class TestValidatedDocument(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)

        patcher = patch(
            "acquisition.database.validated_document.ROOT",
            self.root,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_original_bytes(self):
        content = b"%PDF-1.7\nOriginal content"

        path = save_validated_document(1744, content)

        self.assertEqual(
            path,
            self.root / "documents/validated/1744.pdf",
        )
        self.assertEqual(path.read_bytes(), content)

    def test_reject_non_pdf(self):
        with self.assertRaises(ValueError):
            save_validated_document(1744, b"<html>Error</html>")

        self.assertFalse(
            (self.root / "documents/validated/1744.pdf").exists()
        )

    def test_replace_existing_document(self):
        save_validated_document(1744, b"%PDF-1.7\nOld")
        path = save_validated_document(1744, b"%PDF-1.7\nNew")

        self.assertEqual(
            path.read_bytes(),
            b"%PDF-1.7\nNew",
        )

    def test_no_temporary_file_remaining(self):
        path = save_validated_document(1744, b"%PDF-1.7\nContent")

        self.assertFalse(
            path.with_suffix(".pdf.tmp").exists()
        )

    def test_separate_documents(self):
        first = save_validated_document(1744, b"%PDF-1.7\nFirst")
        second = save_validated_document(1745, b"%PDF-1.7\nSecond")

        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), b"%PDF-1.7\nFirst")
        self.assertEqual(second.read_bytes(), b"%PDF-1.7\nSecond")


if __name__ == "__main__":
    unittest.main()
