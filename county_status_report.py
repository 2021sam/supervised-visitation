#!/usr/bin/env python3
"""Generate a county classification list and pie chart from registry.db."""

import argparse
import sqlite3
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE = PROJECT_ROOT / "registry.db"


def load_counties():
    """Read county classifications without modifying the database."""
    uri = f"{DATABASE.as_uri()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as db:
        return db.execute(
            """
            SELECT county, classification
            FROM courts
            ORDER BY county COLLATE NOCASE
            """
        ).fetchall()


def build_report(counties):
    """Create a copyable text report."""
    counts = Counter(
        classification or "UNCLASSIFIED"
        for _, classification in counties
    )

    lines = [
        "CALIFORNIA SUPERVISED VISITATION",
        "COUNTY DIRECTORY STATUS REPORT",
        "=" * 45,
        f"Total counties: {len(counties)}",
        "",
        "CLASSIFICATION SUMMARY",
        "-" * 45,
    ]

    for status, count in sorted(counts.items()):
        lines.append(f"{status}: {count}")

    lines.extend([
        "",
        "COUNTY LIST",
        "-" * 45,
    ])

    for index, (county, classification) in enumerate(counties, 1):
        status = classification or "UNCLASSIFIED"
        lines.append(f"{index:02d}. {county:<22} {status}")

    return "\n".join(lines) + "\n", counts


def create_chart(counts, output):
    """Save a pie chart with county counts and a detailed legend."""
    import matplotlib.pyplot as plt

    labels = sorted(counts)
    values = [counts[label] for label in labels]
    total = sum(values)

    fig, ax = plt.subplots(figsize=(12, 8))

    wedges, _, autotexts = ax.pie(
        values,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 3 else "",
        startangle=90,
        pctdistance=0.75,
        wedgeprops={"edgecolor": "white"},
    )

    legend_labels = [
        f"{label}: {counts[label]} counties "
        f"({counts[label] / total:.1%})"
        for label in labels
    ]

    ax.legend(
        wedges,
        legend_labels,
        title="County Classification",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=10,
    )

    ax.set_title(
        f"California Supervised Visitation\\n"
        f"County Directory Status — {total} Counties"
    )

    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)



def main():
    parser = argparse.ArgumentParser(
        description="Generate a county list and classification pie chart."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports",
    )
    args = parser.parse_args()

    counties = load_counties()

    if len(counties) != 58:
        raise RuntimeError(
            f"Expected 58 California counties, found {len(counties)}"
        )

    report, counts = build_report(counties)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    text_path = args.output_dir / "county_status.txt"
    chart_path = args.output_dir / "county_status_pie.png"

    text_path.write_text(report, encoding="utf-8")
    create_chart(counts, chart_path)
    import subprocess
    subprocess.run(["open", str(chart_path)], check=True)

    print(report)
    print(f"Text report: {text_path}")
    print(f"Pie chart:   {chart_path}")


if __name__ == "__main__":
    main()
