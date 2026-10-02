#!/usr/bin/env python3
"""
Builds catalog.json — the data bundle the fare-calc app downloads from this repo's
latest GitHub Release.

Keyless by design:
  * fares.json      — hand-maintained fare tables (copied from the app's verified seed)
  * station coords  — geocoded at build time from OpenStreetMap via Nominatim
                      (respecting their 1 request/second policy)
  * places          — curated common destinations, also Nominatim-geocoded

Stdlib only — no pip installs, runs in seconds on a free GitHub-hosted runner.
Output: catalog.json next to this script; the workflow attaches it to a Release.
Failures degrade gracefully: failed lookups are skipped and recorded in `warnings`.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Nominatim usage policy requires an identifying User-Agent that includes contact info.
# Edit the email below (it is just a politeness string — no signup anywhere).
USER_AGENT = "fare-calc-data-publisher/1.0 (https://github.com/maleks-py/fare-calc-data; contact: you@example.com)"
REQUEST_INTERVAL_SECONDS = 1.0  # Nominatim policy: max 1 req/s

# Geocode query templates per rail line (keys match fares.json's `line` values).
LINE_QUERY = {
    "MRT3": "{name} MRT-3 station, Metro Manila, Philippines",
    "LRT1": "{name} LRT-1 station, Metro Manila, Philippines",
    "LRT2": "{name} LRT-2 station, Metro Manila, Philippines",
}

# Curated everyday destinations offered as offline-friendly suggestions.
CURATED_PLACES = [
    "SM City North EDSA, Quezon City",
    "Trinoma, Quezon City",
    "UP Diliman, Quezon City",
    "Cubao, Quezon City",
    "Araneta City, Quezon City",
    "Katipunan, Quezon City",
    "Eastwood City, Quezon City",
    "Ortigas Center, Pasig",
    "SM Megamall, Mandaluyong",
    "Greenhills, San Juan",
    "Makati CBD, Makati",
    "Glorietta, Makati",
    "Ayala Center, Makati",
    "BGC Terminal, Taguig",
    "Bonifacio Global City, Taguig",
    "Market Market, Taguig",
    "SM Mall of Asia, Pasay",
    "NAIA Terminal 3, Pasay",
    "Manila City Hall, Manila",
    "Divisoria, Manila",
    "Quiapo Church, Manila",
    "University of Santo Tomas, Manila",
    "Intramuros, Manila",
    "SM Fairview, Quezon City",
    "Alabang Town Center, Muntinlupa",
]


def nominatim_search(query: str) -> dict | None:
    """First Nominatim hit for `query`, or None. Caller enforces the rate limit."""
    url = (
        "https://nominatim.openstreetmap.org/search?"
        + urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": 1})
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            results = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        print(f"  ! lookup failed ({query}): {exc}", file=sys.stderr)
        return None
    return results[0] if results else None


class RateLimiter:
    """Keeps requests at least REQUEST_INTERVAL_SECONDS apart."""

    def __init__(self) -> None:
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        self._last = time.monotonic()


def main() -> int:
    limiter = RateLimiter()
    warnings: list[str] = []

    fares = json.loads((REPO_ROOT / "fares.json").read_text(encoding="utf-8"))

    # --- Stations: geocode every station of every rail line ----------------------
    stations: list[dict] = []
    for station in fares.get("stations", []):
        template = LINE_QUERY.get(station["line"])
        if template is None:
            warnings.append(f"no geocode template for line {station['line']}")
            continue
        limiter.wait()
        hit = nominatim_search(template.format(name=station["name"]))
        if hit is None:
            warnings.append(f"geocode failed: {station['name']} ({station['line']})")
            continue
        stations.append(
            {
                # id + sequence come straight from fares.json: the app joins `id` with
                # its station-fare matrix to price rail legs, and orders by `sequence`
                # to draw each line on the map (Phase B/C).
                "id": station["id"],
                "name": station["name"],
                "line": station["line"],
                "sequence": station["sequence"],
                "lat": float(hit["lat"]),
                "lon": float(hit["lon"]),
                "source": "OpenStreetMap/Nominatim",
            }
        )
        print(f"  + {station['line']}: {station['name']} -> {hit['lat']:.5f},{hit['lon']:.5f}")

    # --- Places: curated destination suggestions ---------------------------------
    places: list[dict] = []
    for query in CURATED_PLACES:
        limiter.wait()
        hit = nominatim_search(query)
        if hit is None:
            warnings.append(f"geocode failed: {query}")
            continue
        places.append(
            {
                "name": query.split(",")[0],
                "lat": float(hit["lat"]),
                "lon": float(hit["lon"]),
                "kind": "destination",
            }
        )
        print(f"  + place: {query}")

    catalog = {
        "version": int(datetime.now(timezone.utc).strftime("%Y%m%d")),
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fares": fares,
        "stations": stations,
        "places": places,
        "warnings": warnings,
    }

    out_path = REPO_ROOT / "catalog.json"
    out_path.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"\ncatalog.json written: {len(stations)} stations, {len(places)} places, "
        f"{len(warnings)} warnings, fares v{fares.get('version')} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
