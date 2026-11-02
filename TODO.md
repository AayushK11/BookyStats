# Next steps

**CSV sync and backend analytics are implemented and acceptance checks passed.**
Full provider enrichment remains incomplete because Google reports a daily quota
limit; the guarded Open Library follow-up is complete.
Watchlist ranking, automated source collection and scheduling remain future work.
The requested `fetch` command generates the explicit Goodreads browser-console helper.
Detailed requirements and historical evidence stay in [PLAN.md](PLAN.md).

## Working foundation

- [x] Archive original bytes before parsing; preserve unknown fields.
- [x] Import the supplied 1,054 StoryGraph, 813 watchlist and 730 Read records.
- [x] Keep Goodreads history/watchlist separate from StoryGraph personal ratings.
- [x] Publish healthy scopes independently; retain last complete results on failure.
- [x] Process exact configured CSV paths without source browsers or archived fallback.
- [x] Restore the three timestamped inputs byte-for-byte from the raw archive.
  Their stamps are archive capture times, not proven export-generation times.
- [x] Provide nonsecret root config; allow local overrides and isolate other data directories.
- [x] Show config path and CSV ready/missing state in local status.
- [x] Support optional Google Books/Open Library lookups and local Google authorization.
- [x] Verify configured-file E2E: all 2,597 rows and hashes, unchanged repeat,
  independent failure retention; actual local run 10 passed.
- [x] Remove unused browser/source code, dependencies, fixtures and shared declarations.
- [x] Integrate analytics after metadata with offline status and a saved full JSON report.
- [x] Save hash-checked analytics caches and historical reports in ignored
  `data\analytics.sqlite3`; cache taste and watchlist separately.
- [x] Pass the latest integrated gate: 695 Python and 51 JavaScript tests,
  Ruff lint/format over 87 files, strict mypy over 43 files, sdist/wheel
  builds and diff checks.

## Clean reset and actual-data acceptance

- [x] Delete old databases and ignored runtime/temporary files, including the
  old virtual environment, profiles, backups and logs, as explicitly requested.
- [x] Preserve saved Google authorization and exact hashes of the three CSVs/root
  config. Rebuild the environment; retain new useful E2E databases afterward.
- [x] Recreate the virtual environment, restore dependencies and pass the full gate.
- [x] Gate unverified browser CSV genre/series labels while preserving raw values
  and empty/unsupported states; 97 CSV/literal-policy tests passed.
- [x] Finish actual fresh run 1: all 2,597 rows complete; parallel analytics
  produced 400 findings and 314 rated Read works. Finding counts are not fixed targets.
- [x] Final installed-CLI run 8 recalculated 400 findings in parallel for
  314/730 rated Read works; run 9 retained all 2,597 unchanged and reused both caches.
- [x] Run 10 failed only the configured missing Read path while StoryGraph/watchlist
  completed; report 8 stayed last-good. Run 11 recovered, reused both caches and
  left all 2,597 unchanged, with final report 9.
  Inputs were never renamed/changed; only a temporary config path changed.
- [x] Test failed-worker last-report retention and serial/parallel parity.
- [x] Remove the temporary metadata-disabled override and restore root defaults:
  both providers enabled, weekly disabled.
- [x] Confirm all three CSV/root-config hashes and latest raw source bytes are
  unchanged. New useful E2E databases remain retained.
- [ ] Finish full provider enrichment when authorized and operationally available.
  Google returned HTTP 429 with an explicit daily quota limit; reset time unknown.
  Open Library has no deferred targets; validation issues remain explicit.
- [x] Persist safe HTTP status, Retry-After/deadline, wire counts and provider/host
  retry state across restarts. Preserve original bytes through raw schema v3
  migration; retain unknown legacy diagnostics without inventing headers.
- [x] Refine incomplete/contaminated batches without relaxing identity selection,
  preserve successful prefixes on deferral, and prioritize Read within budgets.
- [x] Audit 1,024 matching pairs, including 609 confirmed ISBN links and 415
  unresolved pairs; review a deterministic sample of 77. This measures evidence
  consistency, not independent matching precision. No safe recall relaxation
  was justified. Fix edition-observation identity freshness.
- [x] Add author-component-blocked holdout and deterministic component-resampling
  stability evidence. The fixed baseline shows no convincing predictive edge.
- [x] Finish the normal guarded provider pass, compare the saved fixed cohort
  and trusted field coverage, then verify cache reuse and recovery.
- [x] Correct matched-edition language versus work translation availability;
  validate the saved baseline and final input under the same corrected policy.
- [x] Implement exactly `fetch`, `sync` and `status`, package the console helper,
  and pass 51 fixture-based JavaScript tests. Live browser behavior is unverified.
- [x] Verify CSV-only reconstruction with real storage/provider adapters/analytics
  and fixture HTTP in two independent empty directories, followed by cached repeats.
- [x] Preserve generated databases locally and ignore them for the final commit:
  the library exceeds GitHub's regular-file size limit. Keep original CSVs/root
  config versioned; logs/cache/profiles/backups/credentials remain ignored.
- [x] Format and pass final installed-CLI E2E runs 13–16: parallel v5 calculation,
  cached repeat, independent missing-Read failure retaining report 12, and recovery
  with both caches reused. Final report 13 has 2,151 findings for 338/730 rated Read.
- [x] Verify all 2,597 rows unchanged, original CSV/root-config hashes, latest raw
  source bytes, saved authorization and removal of the temporary config override.

Latest guarded provider results: Google deferred 2,596 after its first daily-quota
rejection. Open Library reported 2,333 completed outcomes across 2,561 targets,
2,250 candidates and zero deferred targets. Selected input references increased
19 to 1,228; Read coverage is 338 ratings, 461 descriptions, 291 genre/subject-known
and 477 work-publication years. The fixed-cohort prediction MAEs worsened;
coverage gains must not be presented as accuracy gains.

## Backend analytics

- [x] Start with the capability inventory in PLAN.md §§19–23: supported,
  subset-only, needs enrichment/observations, or unsupported.
- [x] Save the exact compatible source/metadata inputs and their versions,
  accounts, dates, coverage and raw references before calculating.
- [x] Build supported statistics and preference weights with clear populations,
  sample sizes, missingness, uncertainty and supporting books.
- [x] Reuse saved results when relevant data/code/config is unchanged.
  Watchlist-only changes must not recompute taste analysis.
- [x] Keep this backend-only: no frontend, images or annual reviews; public commands
  are exactly `fetch`, `sync` and `status`.
- [x] Implement known-feature-only comparisons, shrunk effects/rating lifts and
  author fragility, with leakage-safe leave-one-work-out prediction checks.
- [x] Implement equal-volume yearly genre breadth and shared-stratum comparisons
  of current ratings grouped by actual reading year; group en/eng while retaining
  original language provenance. Include the full as-of date/year in cache keys.
- [x] Keep dated/review analyses gated on the actual data: there are no reading dates.
- [x] Add rating-independent all-Read profiles, page quartiles, distinct-work
  first-publication versus edition years, known-feature combinations, metadata
  quality, rating-availability bias checks and fractional Read/watchlist comparison.
- [x] Add versioned description themes/six-hunger content mentions with evidence
  quotes, independent of ratings and without genre proxies or personality scores.
- [x] Run profile/enjoyment/content with three worker processes for larger inputs;
  keep main-process SQLite writes, serial small inputs and no pool on cache hits.
  Parallel/serial parity and failed-worker retention are tested.
- [x] Pass the earlier 54 targeted checks, followed by the final integrated gate above.
- [x] Implement narrower optional-field recovery, refreshed metadata schema/version
  and confirmed-work details; the CLI enables work details.
- [x] Reconcile confirmed provider-work IDs/alternate editions and expose selected
  public work metadata across confirmed catalog links without copying reader or
  other-record edition facts. Use calculator `analytics-v5-scoped-language-validation`.
- [x] Verify current Read input: 730 works, 338 rating-linked (46.3%),
  461 descriptions, 291 trusted genre/subject-known and 477 work-publication years.
- [x] Separate public book references from immutable CSV observation lineage;
  include description provenance in semantic cache keys. Description evidence is
  available for 461 works; 269 lack it. Counts describe word-rule mentions, not
  whole-book labels, personality or an official color assessment.
- [x] Compare held-out errors against the same 314-work training-mean baseline.
  Do not label increased coverage as matching or recommendation accuracy.

The current Read CSV has no usable dated events or personal reviews. Confirmed
rating links increased from 314 to 338 (+24 this pass); that is coverage, not accuracy.
Improve matching/metadata conservatively rather than guessing missing facts.

## Later

- [ ] Rank the current Goodreads watchlist with clear eligibility, reasons,
  confidence and exact input references.
- [ ] Keep personal/public annual reviews deferred until the core pipelines work.

## Deferred

- [ ] Implement and validate an approved live acquisition route for both sources.
  Preserve the official-export/RSS/browser research in PLAN.md.
- [ ] Prove repeated complete same-account collection and unattended operation
  before any explicit scheduling approval. Files/replay do not qualify.
- [ ] Add reliable retry/resume orchestration if needed; no resident service or broker.
- [ ] Define backup/restore and history-retention policies without automatic data deletion.
- [ ] Do not activate Windows scheduling on this machine.
