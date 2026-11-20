#!/usr/bin/env python3

import sqlite3
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://courts.ca.gov/find-your-court"
DB_PATH = "registry.db"

COUNTIES = {
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras",
    "Colusa", "Contra Costa", "Del Norte", "El Dorado",
    "Fresno", "Glenn", "Humboldt", "Imperial", "Inyo",
    "Kern", "Kings", "Lake", "Lassen", "Los Angeles",
    "Madera", "Marin", "Mariposa", "Mendocino", "Merced",
    "Modoc", "Mono", "Monterey", "Napa", "Nevada",
    "Orange", "Placer", "Plumas", "Riverside",
    "Sacramento", "San Benito", "San Bernardino",
    "San Diego", "San Francisco", "San Joaquin",
    "San Luis Obispo", "San Mateo", "Santa Barbara",
    "Santa Clara", "Santa Cruz", "Shasta", "Sierra",
    "Siskiyou", "Solano", "Sonoma", "Stanislaus",
    "Sutter", "Tehama", "Trinity", "Tulare",
    "Tuolumne", "Ventura", "Yolo", "Yuba",
}


def fetch_courts():
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    courts = {}

    # Each county appears in the official directory table.
    # The county-name link leads to its Superior Court website.
    for row in soup.select("tr"):
        for link in row.select("a[href]"):
            county = link.get_text(" ", strip=True)
            county = " ".join(county.split())

            if county not in COUNTIES:
                continue

            url = urljoin(SOURCE_URL, link["href"])

            if county in courts and courts[county] != url:
                raise ValueError(
                    f"Conflicting links for {county}"
                )

            courts[county] = url
            break

    missing = COUNTIES - courts.keys()

    if missing:
        raise RuntimeError(
            f"Found {len(courts)}/58 courts. "
            f"Missing: {', '.join(sorted(missing))}. "
            "Database was not modified."
        )

    return courts


def save_courts(courts):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS courts (
                court_id INTEGER PRIMARY KEY,
                county TEXT NOT NULL UNIQUE,
                court_url TEXT NOT NULL,
                source_url TEXT NOT NULL
            )
        """)

        conn.executemany("""
            INSERT INTO courts (
                county, court_url, source_url
            )
            VALUES (?, ?, ?)
            ON CONFLICT(county) DO UPDATE SET
                court_url = excluded.court_url,
                source_url = excluded.source_url
        """, [
            (county, url, SOURCE_URL)
            for county, url in sorted(courts.items())
        ])

        conn.commit()


def main():
    courts = fetch_courts()
    save_courts(courts)

    print(f"Saved {len(courts)} California courts")
    print(f"Database: {DB_PATH}")

    for county, url in sorted(courts.items()):
        print(f"{county}: {url}")


if __name__ == "__main__":
    main()
