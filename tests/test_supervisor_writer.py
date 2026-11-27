import sqlite3
import unittest

from acquisition.database.supervisor_schema import (
    ensure_supervisor_detail_columns,
)
from acquisition.database.supervisor_writer import (
    save_supervisor,
)


class TestSupervisorWriter(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")

        self.conn.execute("""
            CREATE TABLE supervisors (
                supervisor_id INTEGER PRIMARY KEY,
                court_id INTEGER NOT NULL,
                result_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                website TEXT NOT NULL DEFAULT '',
                raw_text TEXT NOT NULL DEFAULT '',
                UNIQUE(result_id, name)
            )
        """)

        ensure_supervisor_detail_columns(self.conn)

    def tearDown(self):
        self.conn.close()

    def save(self, name, result_id=12, **fields):
        return save_supervisor(
            self.conn,
            1,
            result_id,
            {"name": name, **fields},
        )

    def test_insert(self):
        supervisor_id = self.save(
            "Test Supervisor",
            zip_code="92653",
        )

        self.assertEqual(supervisor_id, 1)

    def test_update_preserves_id(self):
        first = self.save("Test Supervisor")
        second = self.save(
            "Test Supervisor",
            zip_code="92653",
        )

        self.assertEqual(first, second)

        row = self.conn.execute(
            "SELECT zip_code FROM supervisors"
        ).fetchone()

        self.assertEqual(row[0], "92653")

    def test_cleaned_name_preserves_id(self):
        original = "F.A.C.E.S. INC. Office: Laguna Hills"
        first = self.save(original)

        second = save_supervisor(
            self.conn,
            1,
            12,
            {
                "name": "F.A.C.E.S. INC.",
                "zip_code": "92653",
            },
            original_name=original,
        )

        self.assertEqual(first, second)

        rows = self.conn.execute(
            "SELECT name FROM supervisors"
        ).fetchall()

        self.assertEqual(rows, [("F.A.C.E.S. INC.",)])

    def test_separate_source_directories(self):
        first = self.save("Test Supervisor", result_id=12)
        second = self.save("Test Supervisor", result_id=27)

        self.assertNotEqual(first, second)

    def test_ambiguous_identity_rejected(self):
        self.save("Original Name")
        self.save("Cleaned Name")

        with self.assertRaises(ValueError):
            save_supervisor(
                self.conn,
                1,
                12,
                {"name": "Cleaned Name"},
                original_name="Original Name",
            )

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            self.save("")

    def test_all_detail_fields_persisted(self):
        details = {
            "zip_code": "92653",
            "service_area": "Laguna Hills",
            "service_counties": "Orange, Riverside",
            "languages": "English, Spanish",
            "additional_info": "Published rates: $100",
        }

        self.save("Test Supervisor", **details)

        row = self.conn.execute("""
            SELECT zip_code, service_area,
                   service_counties, languages,
                   additional_info
            FROM supervisors
        """).fetchone()

        self.assertEqual(row, tuple(details.values()))


if __name__ == "__main__":
    unittest.main()
