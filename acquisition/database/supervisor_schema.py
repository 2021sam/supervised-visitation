"""Manage additional supervisor database fields."""

SUPERVISOR_DETAIL_COLUMNS = (
    "zip_code",
    "service_area",
    "service_counties",
    "languages",
    "additional_info",
)


def ensure_supervisor_detail_columns(connection):
    """Add missing supervisor detail columns."""

    existing = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(supervisors)"
        )
    }

    if not existing:
        raise ValueError("Supervisors table does not exist")

    added = []

    for column in SUPERVISOR_DETAIL_COLUMNS:
        if column not in existing:
            connection.execute(
                f"ALTER TABLE supervisors "
                f"ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
            )
            added.append(column)

    return added
