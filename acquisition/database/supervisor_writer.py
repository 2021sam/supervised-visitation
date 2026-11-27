"""Persist supervisor records while preserving existing IDs."""

from acquisition.database.supervisor_schema import (
    SUPERVISOR_DETAIL_COLUMNS,
)


def save_supervisor(
    connection,
    court_id,
    result_id,
    record,
    *,
    original_name=None,
):
    """Insert or update a supervisor within its source directory."""

    name = record["name"].strip()
    original_name = (original_name or name).strip()

    if not name:
        raise ValueError("Supervisor name is required")

    fields = (
        "name",
        "phone",
        "email",
        "website",
        "raw_text",
        *SUPERVISOR_DETAIL_COLUMNS,
    )

    values = tuple(record.get(field) or "" for field in fields)

    matches = connection.execute("""
        SELECT supervisor_id
        FROM supervisors
        WHERE result_id = ?
          AND name IN (?, ?)
    """, (result_id, original_name, name)).fetchall()

    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous supervisor identity: {name}"
        )

    if matches:
        supervisor_id = matches[0][0]

        assignments = ", ".join(
            f"{field} = ?" for field in fields
        )

        connection.execute(
            f"UPDATE supervisors SET court_id = ?, "
            f"{assignments} WHERE supervisor_id = ?",
            (court_id, *values, supervisor_id),
        )

        return supervisor_id

    columns = ", ".join(("court_id", "result_id", *fields))
    placeholders = ", ".join("?" for _ in range(len(fields) + 2))

    cursor = connection.execute(
        f"INSERT INTO supervisors ({columns}) "
        f"VALUES ({placeholders})",
        (court_id, result_id, *values),
    )

    return cursor.lastrowid
