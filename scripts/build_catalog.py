#!/usr/bin/env python3
"""
Builds catalog.json — the data bundle the fare-calc app downloads from this repo's
latest GitHub Release.

Design (v2, static):
  * fares.json     — fare tables, hand-maintained (copy from the app repo's seed)
  * stations.json  — rail station coordinates (static; verified against Wikidata)
  * places.json    — curated common destinations (static)

v1 geocoded stations/places from Nominatim on each run. That turned out to be
unreliable: Nominatim blocks/throttles requests from GitHub-hosted runner IPs
(shared cloud addresses), so a "green" run could still publish an empty catalog.
Coordinates barely change, so they live in this repo now — the build is fully
deterministic, needs no network, and finishes in milliseconds.

The only network call is optional: fetching the previously published catalog to
decide whether anything changed. The version number only increases when the
content actually changes, so the app (which re-applies fare data only when the
catalog version grows) never re-seeds needlessly.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The app downloads from the Release asset URL; the build compares against it too.
OWNER, REPO = "maleks-py", "fare-calc-data"
PREVIOUS_URL = f"https://github.com/{OWNER}/{REPO}/releases/latest/download/catalog.json"


def load(name: str) -> dict | list:
    return json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))


def fetch_previous() -> dict | None:
    """Previously published catalog, or None (first run / offline / not yet published)."""
    try:
        with urllib.request.urlopen(PREVIOUS_URL, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def main() -> int:
    fares = load("fares.json")
    stations = load("stations.json")
    places = load("places.json")

    previous = fetch_previous()
    unchanged = (
        previous is not None
        and previous.get("fares") == fares
        and previous.get("stations") == stations
        and previous.get("places") == places
    )

    today = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
    if unchanged:
        # Content identical: keep the old version so apps don't re-seed for nothing.
        version = int(previous["version"])
        note = "no content changes — version kept"
    else:
        version = max((previous or {}).get("version", 0) + 1, today)
        note = "content changed (or first run)"

    catalog = {
        "version": version,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fares": fares,
        "stations": stations,
        "places": places,
        "warnings": [],
    }

    out_path = REPO_ROOT / "catalog.json"
    out_path.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"catalog.json v{version} ({note}): {len(stations)} stations, {len(places)} places, "
        f"fares v{fares.get('version')} -> {out_path}"
    )
    if unchanged:
        print("(Workflow still publishes a fresh asset; the app skips re-seeding.)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — surface everything to the run log
        print(f"fatal: {exc}", file=sys.stderr)
        raise
