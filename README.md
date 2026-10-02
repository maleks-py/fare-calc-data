# fare-calc-data — the public data repo

This folder is a **starter kit for a separate, public GitHub repository** that the
CommuteFare PH app downloads its data from. Nothing in here runs inside the app repo —
the app repo deliberately has no workflows (owner's ground rule: $0, no CI).

What this repo does once it exists:

```
daily cron (GitHub Actions, free on public repos)
   └─ scripts/build_catalog.py
        ├─ fares.json        (fare tables, hand-maintained here)
        ├─ Nominatim/OSM     (station + destination coordinates, keyless)
        └─ catalog.json      (the bundle)
   └─ attached to a GitHub Release tagged catalog-YYYYMMDD
        └─ app downloads: releases/latest/download/catalog.json  (CDN, no API, no key)
```

The app **never triggers a run** — it only fetches the static file, at most once a day.

## One-time setup (≈2 minutes)

1. Create the public repo (any name; `fare-calc-data` is the default the app expects):

   ```bash
   gh repo create fare-calc-data --public
   ```

2. Push the contents of **this folder** (`data-repo/`) to its root — the files should
   end up as `README.md`, `fares.json`, `scripts/build_catalog.py`,
   `.github/workflows/publish-catalog.yml`:

   ```bash
   cd /tmp && git clone git@github.com:<you>/fare-calc-data.git && cd fare-calc-data
   cp -r /path/to/fare-calc/data-repo/. .
   git add -A && git commit -m "Catalog publisher v1" && git push
   ```

3. Set your contact email in `scripts/build_catalog.py` (`USER_AGENT` constant).
   Nominatim's usage policy asks for an identifiable contact — it's a politeness
   string only, no signup anywhere.

4. Fire the first run manually (the daily 03:17 PHT cron takes over after that):

   ```bash
   gh workflow run publish-catalog.yml --repo <you>/fare-calc-data
   ```

5. Check the result: the Actions tab should go green and
   `https://github.com/<you>/fare-calc-data/releases/latest/download/catalog.json`
   should download the JSON.

If you named the repo something else, update `OWNER`/`REPO` in the app's
`data/catalog/CatalogRepository.kt`.

## What's in catalog.json

```jsonc
{
  "version": 20261002,               // build date (YYYYMMDD) — app compares to detect updates
  "generatedAt": "2026-10-02T…",     // ISO timestamp of the build
  "fares": { /* fares.json verbatim: rules, discounts, stations, stationFares */ },
  "stations": [                      // rail stations with coordinates (Phase B/C's key data)
    { "id": 1, "name": "North Avenue", "line": "MRT3", "sequence": 1,
      "lat": 14.6507, "lon": 121.0327, "source": "OpenStreetMap/Nominatim" }
  ],
  "places": [                        // curated destinations for instant search suggestions
    { "name": "SM Mall of Asia", "lat": 14.5352, "lon": 120.9801, "kind": "destination" }
  ],
  "warnings": [ "geocode failed: …" ] // anything that failed, so nothing silently vanishes
}
```

`stations[].id` and `sequence` mirror `fares.json` exactly — the app joins `id` against
its station-fare matrix (912 fares) to price rail legs, and orders by `sequence` to draw
each rail line on the map. That's why the script copies them instead of re-deriving.

## What each app phase uses this repo for

| App phase | Uses | Why it matters there |
|---|---|---|
| A — Plan Trip (shipped) | `places` | merged into destination search; `fares` reserved |
| B — data activation | `fares` + `stations` | fare updates without shipping an APK; station coordinates unlock **rail legs** (walk → ride → walk, priced via the station matrix) |
| C — map view | `stations` + `places` | station/destination markers and ordered rail lines on the map. **Map tiles themselves come from OpenFreeMap directly in the app** — not from this repo |

Nothing else. The app never triggers runs, never calls the GitHub API, and needs no
token: it just fetches `releases/latest/download/catalog.json` from the CDN.

## Updating fares

Edit `fares.json` here (same schema as the app's seed — copy the app's
`app/src/main/assets/fare_rules.json` after editing it there), bump its `version`,
commit, then `gh workflow run publish-catalog.yml`. The app picks the new bundle up
on its next daily sync. Until the app ships catalog-driven fare updates (Phase B),
this file is the forward-looking source of truth; the bundled seed keeps the app
working offline regardless.

## Why a Release asset and not `raw.githubusercontent.com`?

Release assets are served from GitHub's CDN with no rate limits and no API tokens,
so the app can poll daily forever for free. Raw file URLs are rate-limited and
discouraged for app traffic.

## Notes

- `fares.json` here is a copy of the app's verified seed v2 (LTFRB matrices effective
  2026-09-28; sources documented in the app repo's `docs/SOURCES.md`).
- Geocode failures degrade gracefully: missing stations land in `warnings[]` and the
  app simply falls back to its online geocoder for those.
- Public repo → Actions minutes are free; the job is a few minutes of 1 req/s
  Nominatim lookups.
