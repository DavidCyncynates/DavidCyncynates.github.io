# HEP faculty jobs · 2026–2027

A static geographical job map for `https://davidcyncynates.github.io/hep-jobs/`.

The browser uses bundled Leaflet and Natural Earth boundaries; no map API key,
paid model API, tile service, account, or backend is required. All map assets
are served with the site. Job details link directly to source advertisements.

## Local preview

From this directory, run `python3 -m http.server 4190 --bind 127.0.0.1`, then open
`http://127.0.0.1:4190/`. The page supports desktop and mobile layouts.

## Data and checks

Canonical inputs live under `data/research/`. `*-jobs.json` hold job records;
`locations.json` holds sourced campus/city coordinates. The source registries
and Carnegie metadata retain their provenance and licences. Do not modify only
the generated exports: the next build will replace them.

```sh
python3 scripts/build_catalog.py
python3 scripts/validate_catalog.py --require-map-ready
python3 -m unittest discover -s scripts -p 'test_*.py'
node --test scripts/test_*.mjs
```

The build creates `data/catalog.json`, individual exports, SQLite, and the
readable `catalog.html`. Institution scan labels are derived from the recorded source attempts and dated `data/research/institution-scans.json` reviews. Each completed scan retains its bounded search scope; partial and blocked scans retain their gaps. It emits exact UTC cutoffs for browser evaluation from
advertised timezone/date semantics. Viewing-time status does not mutate records.

`core.mjs` contains date/filter/clustering rules. Clusters use projected screen
pixels and are recomputed with zoom and filters. Distinct searches at one
location remain separate records and expand into a keyboard-accessible list.

`smooth-zoom.mjs` uses the bundled Leaflet 1.9.4 native pinch movement hooks for
cursor-anchored continuous wheel zoom; recheck the adapter before upgrading
Leaflet. Geometry and clusters update once after a gesture, and unchanged
cluster markers are reused. `cluster-updates.mjs` preserves a pressed marker
until its click finishes, so regrouping cannot swallow an interaction.

## Weekly maintenance

Read `MAINTENANCE.md`. `data/maintenance-ledger.json` preserves evidence versions,
source attempts, and incomplete coverage. Failed reads never delete jobs or
advance successful coverage. Weekly maintenance runs through the Codex desktop
schedule, not GitHub Actions; Actions validates changes before publication.
The weekly schedule is active for Mondays at 11:00 Europe/Rome (Codex automation `refresh-hep-faculty-job-map`). The Mac must be awake and Codex running for this local schedule. The existing personal daily-search task is separate.

## Global source expansion

The 28 October 2026 pass added 43 verified listings and retained 20 further
leads for review (16 catalog records and four research follow-ups). Expired
listings remain archived. The coverage report and evidence audit in
`data/maintenance-runs/global-survey-20261028-*.json` describe 151 recorded
checks across 123 source URLs, including failures and retries. No board scan
was marked complete in that initial discovery pass.

The subsequent institution-directory scan reviewed all 84 listed institutions
and added 15 verified searches, including two expired calls retained in the
archive. It completed the stated vacancy-list scopes for 69 institutions;
14 retain specific coverage gaps and one remains blocked. The directory shows
dated results and expandable scope notes instead of a blanket pending label.
The append-only source attempts and institution reviews retain failures,
pagination limits and the evidence behind each result. Completed scans cover
the stated sources and filters, not an assertion that no other vacancy exists.
Weekly maintenance carries the unresolved gaps forward and marks completed
checks stale after 28 days.

## Attribution

- Leaflet 1.9.4: BSD-2-Clause, licence in `vendor/leaflet/LICENSE`.
- World boundaries: Natural Earth, public domain.
- US campus coordinates: US Department of Education, NCES/IPEDS HD2024.
- City coordinates: GeoNames, CC BY 4.0; references retained per location.
- US research classifications: ACE and Carnegie Foundation, Carnegie 2025,
  CC BY-NC-SA 4.0. International profiles are descriptive, not equivalents.
- Advertisements retain their original rights; this catalog contains short
  factual summaries and source links. No blanket code licence is applied to
  third-party data.
