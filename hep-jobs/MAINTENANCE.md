# Weekly maintenance of the HEP faculty map

Maintain only `hep-jobs/` in `DavidCyncynates/DavidCyncynates.github.io`. The map covers the **2026–2027 application cycle**. This document is the durable instruction for the weekly agent in the existing chat; it does not create a schedule itself. Do not modify the personal daily job-search task, the LZ paper map, or other website sections.

## Evidence and scope

- Include faculty vacancies in high-energy theory and experiment, astroparticle physics, cosmology, and explicitly marked adjacent or broad-physics opportunities. Keep formal vacancies, expressions of interest, and fellowship-hosting routes distinct. An EOI is not a guaranteed faculty position. Ordinary postdocs and student jobs are outside the catalog.
- Use employer advertisements, university recruitment/department/group pages, and employer-authored Academic Jobs Online, Interfolio, AAS, INSPIRE, or equivalent advertisements. General boards and search results discover leads; verify the actual advertisement before promoting a new job to `verified`.
- Require explicit cycle evidence. A 2027 appointment date alone does not establish the 2026–27 application cycle. Keep ambiguous new leads as `needs-review`, outside the default map. Do not silently roll the database into the next cycle.
- Record the advertisement's deadline meaning, date, time, and IANA timezone when given. Never invent an exact time or timezone. Priority and review-start dates do not establish closure. Preserve superseded deadlines with `active:false` and a note linking the extension evidence.
- For two-stage routes, record host EOI and national application deadlines separately. A later national deadline cannot reopen an expired hard host EOI; the final national deadline closes the route even when the host date is only a priority date. Preserve stage and closure flags.
- Do not infer closure from a timeout, blocked request, missing page, empty search, HTTP 404, or an advertisement disappearing from a list. An explicit closure requires a freshly read closure source. Existing facts and verification survive access failures. Conflicting new evidence can justify review, with both sources retained.
- Preserve expired, closed, and uncertain records. The interface evaluates dates at viewing time and hides passed hard deadlines by default. Never delete a record merely because it is no longer open. A duplicate discovered later should be retained with a documented resolution until a deliberate schema migration is reviewed.
- Do not import private application rankings, fit assessments, correspondence, referee information, documents, or chat transcripts. Store only public factual evidence and short summaries. Keep third-party licensing and attribution intact.
- Use official Carnegie designations only where applicable. International research profiles are descriptive categories, not invented R1/R2 equivalences. Verify the relevant campus; do not conflate institutions, consortia, or similarly named locations.

## Persistent state and freshness

`data/maintenance-ledger.json` is the durable ledger, committed with the catalog. Its initial job versions preserve the seed's existing evidence dates; its source `lastFullScanAt` and `lastSuccessfulCheckAt` start empty. A verified listing is not evidence of an exhaustive board scan. `seedReportedFullScan` is a retained source claim, not a promoted scan frontier.

Every attempt has a timestamp and outcome: `complete`, `partial`, `failed`, or `skipped`. Only a complete scan advances `lastFullScanAt`. Complete means the stated search scope and all relevant pagination were checked; it requires `coverage` and `paginationComplete:true`. Reading one advertisement is normally a partial check of a recruitment directory. A failure changes the failure history, never prior successful timestamps or job facts. Skipping does not advance the rotation clock.

The initial expansion run in `data/maintenance-runs/` transparently records final evidence-assessment times: its pages were read successfully earlier in the same session, and exact fetch times were not recorded. Each entry marks `timestampBasis`, `sourceReadDate`, and `sourceReadAt:null`; its successful timestamp is an assessment time, not a claim of a new HTTP request. All twelve checks are partial. For subsequent weekly runs, record actual read/check times as they happen; retain this explicit distinction if reassessing earlier evidence.

Keep historical attempts, prior factual versions, run records, and synchronization history. Never reinitialize an existing ledger. Do not set `checkedOn`, successful timestamps, or coverage dates to today's date merely because a build or automation ran. `generatedAt` is the build time, not the last successful vacancy survey. Public freshness labels must use actual successful evidence, and distinguish partial coverage from a completed scan.

The ledger tool is offline: it fetches nothing, modifies no catalog records, and publishes nothing. It uses atomic writes, rejects dropped jobs, and requires recorded successful source evidence for revisions to established jobs or promotion of new verified jobs. It cannot establish that the evidence itself is true; the agent must read and assess it.

## Weekly procedure

1. Read this document and the ledger from the latest `main`. Use a clean branch named `codex/hep-jobs-…`. Respect concurrent edits; do not overwrite another run or reset the user's working files. If another refresh is active, avoid a duplicate refresh. Compare the ledger on main again before publication.
2. Run the offline checks and request the source plan from the `hep-jobs` directory:

   ```sh
   python3 scripts/validate_catalog.py
   python3 scripts/refresh_ledger.py plan --rotation-limit 24
   ```

3. Check **all `weeklyRequired` sources**: central discipline/national boards and sources for jobs whose hard deadlines have not passed, including unresolved leads. Process the rotating institution/department/group/recruitment queue. Its order interleaves countries and prioritizes sources least recently attempted, so one broken source cannot prevent other institutions being checked. Check `retry` failures, but do not let retries consume the whole rotation budget. Retired source entries remain in history.
4. Aim to cover every directory within four weekly runs. Increase the rotation budget when the directory grows, and inspect `sourcesWithoutFullScanIn28Days` and `remainingRotationSources`. These are backlog disclosures, not proof of a completed global survey. For classification-only sources, check official classification releases rather than vacancies. If a large board cannot be fully paginated, save the actual bounded coverage as `partial` and a continuation in its coverage note; do not mark it complete. Carry that continuation into the next run. Failed checks must be retried or reported as continuing gaps.
5. Expand beyond the seed's North American/theory bias every week: include experimental HEP, at least one undercovered country/region, local-language recruitment terms, and department/group pages that may not cross-post to major boards. Add actual discovered public sources with stable IDs, country/institution links, and honest discovery status. New sources do not require a prior frontier. To register sources before checking them, add them to the research registry, rebuild, and run `python3 scripts/refresh_ledger.py sync --sources-only`. This registers source discovery without importing any proposed job changes. Do not claim exhaustive coverage merely because all current registered sources were checked.
6. Save a run report containing only public evidence. Record every attempted source, including failures; use a unique run ID and actual timezone-aware timestamps. Then append it:

   ```sh
   python3 scripts/refresh_ledger.py record --report /path/to/run-report.json
   ```

   A report has this shape (example values are illustrative, not evidence):

   ```json
   {
     "runId": "hep-jobs-2026-11-04T110000Z",
     "startedAt": "2026-11-04T11:00:00+00:00",
     "finishedAt": "2026-11-04T11:20:00+00:00",
     "checks": [
       {
         "sourceId": "existing-source-id",
         "checkedAt": "2026-11-04T11:10:00+00:00",
         "outcome": "partial",
         "evidenceUrls": ["https://university.example/jobs/advertisement"],
         "summary": "Read the current advertisement; its deadline is unchanged.",
         "coverage": "One advertisement; department directory not scanned."
       }
     ]
   }
   ```

   For `complete`, include truthful coverage notes and `paginationComplete:true`. For `failed`, describe the observed failure and avoid vacancy conclusions. Do not fabricate successful reads for sources that were only discovered or indexed.
7. Edit the canonical `data/research/*-jobs.json` records and supporting source/classification/location registries, then run `python3 scripts/build_catalog.py`. If `data/research/review-resolutions.json` exists, inspect it: the builder applies its per-job fields after base records, so stale overrides can silently undo edits. Prefer merging resolved fields into their canonical job records and clearing the corresponding overrides, checking that the built facts are unchanged. Preserve job and source IDs; normalize institutional aliases. Update `checkedOn` only for jobs actually reassessed. A new unresolved lead may be retained without promotion. Verify campus coordinates from a public source and use `location.verification:"verified"` before plotting; do not put a plausible guessed point on the map.
8. For factual revisions or newly verified jobs, save an evidence array with `jobId`, `checkedOn`, `sourceIds`, and a factual `summary`. Its source IDs must belong to the job and have successful checks recorded on that UTC date, after the previous factual version. Revisions cannot use stale success followed by a newer failure. Explicit closure evidence must include the closure-source ID. Append the new versions:

   ```sh
   python3 scripts/refresh_ledger.py sync --report /path/to/job-evidence.json
   ```

   A no-change run can use `sync` without `--report`; failures still remain in the ledger. If a guard rejects a change, preserve the failure/attempt history and fix or withdraw the unsupported catalog edit. Never weaken the guard to force a publication. Do not advance evidence dates as a workaround.
9. Before publication, run:

   ```sh
   python3 scripts/validate_catalog.py --require-map-ready
   python3 -m unittest discover -s scripts -p 'test_*.py'
   ```

   Inspect map filters, deadline coloring, close-location clustering, expired-job behavior, keyboard access, and a mobile viewport when relevant changes are made. Check new markers and linked advertisements. No empty or unverified coordinates may be plotted. Review the diff for private information, unrelated website edits, source-ID churn, removed historical jobs, and unjustified mass changes.
10. Commit only `hep-jobs/`, including the updated ledger. Open a pull request against `main`, summarize factual additions/changes and actual coverage gaps, and attach the PR to the chat. Use the authorized PR/merge workflow; publish only after checks pass. Confirm the deployed JSON and page reflect the merged commit. A ledger-only update is useful when no vacancies changed. If validation or deployment fails, report the specific failure and retain the last working public map. Do not report a failed run as a successful refresh.

The weekly heartbeat should stay quiet when nothing meaningful changed. Notify the user about new or materially changed opportunities, completed publication, persistent coverage failures, or a required decision. Do not send applications, emails, or other messages to institutions.

## Seed and recovery commands

The initial ledger is already seeded; this command is for a genuinely new catalog only:

```sh
python3 scripts/refresh_ledger.py init
```

`init` refuses to overwrite existing history. If a run is interrupted, retry an identical `record` report with the same run ID: it is idempotent. A different report cannot overwrite that run ID. Save the follow-up with a new ID. If main changed during the run, rebase carefully and merge the append-only evidence histories; never replace another run's ledger with an older copy. The catalog and ledger remain standard JSON, with prior job versions recoverable from the ledger and Git history.
