#!/usr/bin/env python3
"""Generate California county search status report and pie chart."""

import argparse
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE = PROJECT_ROOT / "registry.db"


def load_counties():
    """Read county flags and calculate SEARCHED from search history."""
    uri = f"{DATABASE.as_uri()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as db:
        return db.execute("""
            SELECT
                c.county,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM county_search_runs AS r
                    WHERE r.court_id = c.court_id
                ) THEN 1 ELSE 0 END AS SEARCHED,
                c.FOUND,
                c.MIA
            FROM courts AS c
            ORDER BY c.county COLLATE NOCASE
        """).fetchall()


def build_report(counties):
    """Build text report and exclusive pie-chart counts."""
    searched_count = sum(row[1] for row in counties)
    found_count = sum(row[2] for row in counties)
    mia_count = sum(row[3] for row in counties)

    chart_counts = Counter()

    for county, searched, found, mia in counties:
        if found:
            chart_counts["FOUND"] += 1
        elif mia:
            chart_counts["MIA"] += 1
        elif searched:
            chart_counts["SEARCHED ONLY"] += 1
        else:
            chart_counts["NOT YET SEARCHED"] += 1

    lines = [
        "CALIFORNIA SUPERVISED VISITATION PROVIDERS",
        "COUNTY DIRECTORY STATUS REPORT",
        "=" * 62,
        f"Total counties: {len(counties)}",
        "",
        "STATUS SUMMARY",
        "-" * 62,
        f"SEARCHED: {searched_count}",
        f"FOUND:    {found_count}",
        f"MIA:      {mia_count}",
        "",
        "COUNTY LIST",
        "-" * 62,
        f"{'COUNTY':<26} {'SEARCHED':>9} {'FOUND':>9} {'MIA':>7}",
        "-" * 62,
    ]

    for county, searched, found, mia in counties:
        lines.append(
            f"{county:<26} {searched:>9} {found:>9} {mia:>7}"
        )

    return "\n".join(lines) + "\n", chart_counts


def create_chart(counts, output):
    """Create pie chart without double-counting counties."""
    import matplotlib.pyplot as plt

    labels = [
        label for label in (
            "FOUND",
            "MIA",
            "SEARCHED ONLY",
            "NOT YET SEARCHED",
        )
        if counts[label] > 0
    ]

    values = [counts[label] for label in labels]
    total = sum(values)

    fig, ax = plt.subplots(figsize=(12, 8))

    wedges, _, _ = ax.pie(
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
        title="County Status",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=10,
    )

    ax.set_title(
        f"California Supervised Visitation Providers\n"
        f"County Directory Status — {total} Counties"
    )

    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Generate county search status report and pie chart."
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

    subprocess.run(["open", str(chart_path)], check=True)

    print(report)
    print(f"Text report: {text_path}")
    print(f"Pie chart:   {chart_path}")


if __name__ == "__main__":
    main()
