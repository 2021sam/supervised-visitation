import argparse
import datetime as dt
import json
from pathlib import Path

import httpx
import yaml

from .core import extract_links, rank_links, save_json, fingerprint
from .crawler import crawl

ROOT = Path(__file__).resolve().parents[2]
OBJECTIVE = "Find professional supervised visitation providers"


def load_case(case_name=None):
    config = yaml.safe_load((ROOT / "tests/cases.yaml").read_text())
    case_name = case_name or config["default"]

    if case_name in config["cases"]:
        return case_name, config["cases"][case_name]

    registry_path = ROOT / "config/sources/california.yaml"

    if registry_path.exists():
        registry = yaml.safe_load(registry_path.read_text())

        for county in registry["counties"]:
            if county["id"] == case_name:
                return case_name, {
                    "homepage": county["court_url"],
                    "objective": OBJECTIVE,
                }

    raise ValueError(f"Unknown county or test case: {case_name}")


def run(case_name=None, phase="all", mode="live", run_root=None):
    case_name, case = load_case(case_name)

    base = Path(run_root) if run_root else ROOT / "runs"
    stamp = dt.datetime.now(dt.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    directory = base / case_name / stamp
    directory.mkdir(parents=True, exist_ok=False)

    try:
        if phase == "crawler":
            if mode != "live":
                raise ValueError(
                    "Crawler replay is not implemented yet; use --mode live"
                )

            result = crawl(
                case["homepage"],
                max_pages=35,
                max_depth=4,
            )

            save_json(
                directory / "crawler/input.json",
                {
                    "homepage": case["homepage"],
                    "objective": case["objective"],
                    "max_pages": 35,
                    "max_depth": 4,
                },
            )

            save_json(directory / "crawler/output.json", result)

            summary = {
                "status": "success",
                "case": case_name,
                "mode": mode,
                "phase": phase,
                "crawl_status": result["status"],
                "pages_attempted": result["pages_attempted"],
                "candidate_count": result["candidate_count"],
                "top_candidates": result["candidates"][:5],
                "run_directory": str(directory),
            }

        else:
            if mode == "live":
                with httpx.Client(
                    timeout=20,
                    follow_redirects=True,
                    headers={
                        "User-Agent":
                        "DiscoveryEngineLab/0.1 (testing; polite crawling)"
                    },
                ) as client:
                    response = client.get(case["homepage"])
                    response.raise_for_status()
                    html = response.text
                    effective_url = str(response.url)

                (directory / "homepage.html").write_text(html)

            else:
                prior = sorted(
                    (base / case_name).glob("*/homepage.html")
                )

                if not prior:
                    raise RuntimeError(
                        "No saved homepage. Run a live test first."
                    )

                html = prior[-1].read_text()
                effective_url = case["homepage"]

            links = extract_links(html, effective_url)
            ranked = rank_links(links)

            save_json(
                directory / "discovery/input.json",
                {
                    "homepage": case["homepage"],
                    "objective": case["objective"],
                    "html_sha256": fingerprint(html),
                },
            )

            save_json(
                directory / "discovery/output.json",
                {"links": links},
            )

            save_json(
                directory / "ranking/input.json",
                {"links": links},
            )

            save_json(
                directory / "ranking/output.json",
                {"ranked_links": ranked},
            )

            summary = {
                "status": "success",
                "case": case_name,
                "mode": mode,
                "phase": phase,
                "links_found": len(links),
                "top_links": ranked[:5],
                "run_directory": str(directory),
            }

        save_json(directory / "summary.json", summary)
        return summary

    except Exception as exc:
        summary = {
            "status": "failed",
            "case": case_name,
            "mode": mode,
            "phase": phase,
            "error": f"{type(exc).__name__}: {exc}",
            "run_directory": str(directory),
        }

        save_json(directory / "summary.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Repeatable website discovery lab"
    )

    parser.add_argument("case", nargs="?", default=None)

    parser.add_argument(
        "--phase",
        choices=["all", "discovery", "ranking", "crawler"],
        default="all",
    )

    parser.add_argument(
        "--mode",
        choices=["live", "replay"],
        default="live",
    )

    args = parser.parse_args()

    try:
        result = run(args.case, args.phase, args.mode)
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(result, indent=2))

    raise SystemExit(
        0 if result["status"] == "success" else 1
    )


if __name__ == "__main__":
    main()
