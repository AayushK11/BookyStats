# Delivery status

The implementation lanes are integrated on the local `main` branch and the
code-level gate passes. The owner explicitly stopped the clean-slate E2E and
independent review, so this integration has no fresh real-data coverage,
accuracy or generated-report claims. Use `booky status` for actual saved state.
Databases and credentials remain local. See [PLAN.md](PLAN.md) for requirements
and dated historical evidence.

## Latest integration

- [x] Integrate conservative matching/enrichment, evidence-aware analytics,
  read-only storage inspection/verified backups, operational logging and a
  versioned reader-first report bundle.
- [x] Full code-level gate: **1,199 Python tests**, Ruff lint, Ruff format and
  strict mypy passed on 2026-11-03.
- [ ] Clean-slate E2E: stopped by owner; databases, credentials and saved
  bundles were not deleted or rebuilt.
- [ ] Independent implementation review: stopped by owner; not run.
- [ ] Fresh report: not generated because it requires running the data pipeline.
- [ ] Push: local commits are not yet pushed.

StoryGraph remains raw-only except explicit Read-row ratings and matching
identity. Goodreads is the only permitted reading-history authority. There is
no independently labeled matching or recommendation accuracy benchmark.

## Delivered foundation

- [x] Archive original CSV bytes and unknown fields before parsing.
- [x] Publish healthy source/shelf snapshots independently; retain last-good
  snapshots and analytics on failure.
- [x] Process exact configured paths without automatic source fetching, browser
  launch or archived fallback for missing paths.
- [x] Preserve full-snapshot semantics and fixed supplied CSVs: 2,597 archived
  rows, 2,153 active source records; StoryGraph processing uses Read rows only.
- [x] Separate Goodreads history/watchlist authority from StoryGraph personal
  ratings, provider metadata and community ratings.
- [x] Conservative work/edition matching, metadata caching and durable retry
  gates, including explicit Google daily-quota evidence handling.
- [x] Saved Read profile, enjoyment/content analysis and descriptive watchlist
  comparison, with capabilities, provenance and explicit missingness.
- [x] Separate taste/watchlist caches, immutable verified cache entries,
  historical reports and three-worker calculation for larger inputs.
- [x] Exactly three commands: `fetch`, `sync`, `status`; offline report access.
- [x] Version nonsecret configuration and original inputs; keep runtime data,
  backups, logs, credentials and generated exports local and ignored.

## Current production hardening

- [x] Veto and reverse automatic ISBN links contradicted by selected catalog
  identities; preserve human decisions and edition safeguards.
- [x] Open Library first, with Google only for declared remaining core gaps;
  investigate alternatives without unverified provider dependencies.
- [x] Reuse settled public evidence without age-only refetching; retain query
  identity, implementation compatibility, integrity and provenance checks.
- [x] Recover canonical work matches from a verified cross-query local catalog;
  preserve ambiguity, exact genre-family aliases and work/edition separation.
- [x] Bound new Open Library detail requests to 40 per provider instance while
  continuing cached recovery and retaining partial fields after deferral.
- [x] Keep weak unselected title-only catalog candidates out of conflict vetoes;
  retain corroborating ISBN ambiguity and selected catalog conflict safeguards.
- [x] Recover an automatically invalidated work link only for the same unchanged
  source pair under current reciprocal-uniqueness/conflict checks; never override
  human acceptance, rejection or undo.
- [x] Reduce Open Library search response size and checkpoint completed detail
  results before requesting the next record.
- [x] Evidence-backed reading-appetite enjoyment associations and rating
  representativeness, separate from explicit labels and official assessments.
- [x] Fix analytical Read-membership cache invalidation.
- [x] Keep StoryGraph dates and other personal fields raw-only; do not promote
  them into analytics.
- [x] Analyze Goodreads library-addition age separately from reading dates.
- [x] Make offline terminal status useful and simplify the root user guide.
- [x] Pass targeted tests, full Python/JavaScript tests, Ruff lint/format, strict
  mypy, package builds and isolated real-CSV acceptance/repeat checks.
- [x] Harden storage: read-only `upgrade_needed`-aware status without sidecar
  creation, verified SQLite backups before library v4/analytics v3/raw v3
  upgrades, metadata cache identity v1, bounded opens plus explicit
  `verify_store`, and four library indexes. Fixture/scratch-copy evidence only;
  no live data directory has been migrated.
- [ ] Storage follow-ups: migration ledger, owner-approved compaction/reset,
  stopping redundant historical writes, deep-verification cadence and
  checkpoint/maintenance policy. No table is dropped and no compression exists.

## Known limitations

- Metadata coverage remains partial. Provider quotas and unresolved identities
  cannot be removed by raising the local book budget or restarting a process.
- More linked ratings are not measured matching accuracy. Historical prediction
  checks did not establish gains over their same-cohort baselines.
- Supplemental completion dates cover a subset; library-addition, publication
  and capture dates do not fill missing personal reading history.
- Description rules are transparent text evidence, not validated whole-book
  labels, reader personality, official colors or recommendation accuracy.
- Manual capture helper tests do not establish current live-site compatibility,
  complete account collection or unattended access.

## Automatic product delivery

- [x] Generate separate explainable watchlist rankings, a varied shortlist,
  explicit exclusions and insufficient-evidence abstentions automatically.
- [x] Persist typed, hash-verified recommendation caches/history in the analytics
  database, with a strict verified v2-to-v3 migration.
- [x] Audit metadata coverage, identity anchors, provenance and cross-provider
  consistency without a human correction queue or unsupported accuracy score.
- [x] Generate the library PDF offline with charts, paginated tables, evidence,
  recommendations and licensed packaged Unicode fonts.
- [x] Publish coherent PDF/JSON bundles from one pinned manifest/as-of, verify
  hashes and update the latest pointer only after all outputs succeed.
- [x] Retain last-good products on failure and recover interrupted publication.
- [x] Append redacted incremental progress and complete grouped issue counts to
  one persistent log without deleting earlier sessions.
- [ ] Clean-slate runtime cleanup and fresh rebuild remain stopped; no user
  databases, logs, bundles, credentials or retry gates were deleted.

## Current saved products

- `data\reports\latest.json` identifies the latest complete bundle. The
  reader-first PDF is 15 pages, replacing the former 150-page presentation
  without deleting the historical bundle. It includes personal opening insights,
  ratings/favorites, separate Goodreads comparisons, returning authors, reading
  appetites with linked quotes, dated cohorts, watchlist composition and shortlist.
- Final bundle `data\reports\report-8` passed baseline and per-glyph body-frame
  bounds checks, including quote/source links; no body/footer overlap was found.
- The same bundle contains hash-verified analytics, metadata-quality and
  recommendation JSON with identical manifests/as-of timestamps.
- 730 Read works, 813 watchlist works, 574 linked unconflicted personal ratings
  and 232 findings. These differ from source-only inputs; coverage is not
  matching accuracy and no recommendation-quality gain is claimed.
- 359 ranked works, ten shortlisted and 454 insufficient-evidence abstentions.
  All ranked IDs passed current-watchlist, completed-work, possible-Read overlap
  and known-future-work checks. Both analytics caches and recommendations reused.
- The automatic quality audit reported no internal consistency diagnostics.
  That is not independent factual accuracy or complete metadata coverage.
- Recognized genres cover 329/730 Read works (45.1%) and 297/813 watchlist works
  (36.5%), up from 271 and 248. Descriptions cover 535/730 (73.3%) and 609/813
  (74.9%). Edition language remains unknown for every work; verified series
  coverage remains 70 Read/8 watchlist. **Enrichment is not solved.**
- All seven temporarily withdrawn rating links recovered automatically after
  the veto/recovery regression was fixed. No source ratings or original CSV
  bytes were edited, and no manual matching decisions were inserted.
- PDF fonts have explicit limits: complex-script shaping and RTL layout are
  not enabled; glyph availability alone does not establish correct rendering.

## Still to build

- [ ] Improve free/local metadata acquisition beyond incremental API recovery,
  benchmark selected identity-valid coverage, and address the low genre/series
  coverage without guessed labels, forced matches or repeated quota bypasses.
- [ ] Independently benchmark catalog/matching quality and recommendation
  usefulness; additional coverage and heuristic rankings do not establish accuracy.
- [ ] Validate an explicitly approved live acquisition route for both sources.
- [ ] Prove repeated complete same-account and unattended collection before any
  explicit scheduling approval; do not activate scheduling on this machine.
- [ ] Add durable orchestration/retry/resume if needed, without a resident
  pipeline service or broker.
- [ ] Define reviewed backup/restore and history-retention policies without
  automatic user-data or backup deletion.
- [ ] Frontend and personal/public annual reviews remain deferred.

## Earlier hardening acceptance

- Final gate: **815 Python tests, 51 JavaScript tests**, Ruff lint/format over
  92 Python files, strict mypy over 45 source files, sdist/wheel builds and diff
  checks passed. The pre-change Python baseline was 760 tests.
- Isolated real-CSV acceptance explicitly disabled both providers: 730 Read
  works, 813 watchlist works, 577 linked ratings, 278 usable public descriptions
  and 180 findings. These coverage counts did not improve merely because the
  analysis changed.
- Of 423 explicit StoryGraph completion dates, 406 were usable through confirmed
  Read-work links; 187 StoryGraph Read rows had no date. All 730 Read and 813
  watchlist library-addition dates were available separately. No Goodreads
  reading events were invented.
- The frozen-policy unchanged repeat reused both analytics caches with all
  2,153 source records unchanged. A missing configured Read path retained the
  730-record snapshot and last-good report; restored configuration recovered
  using both caches.
- A separate synthetic public-book fixture used actual Open Library search/detail
  responses. One selected lookup completed; adding a matching cross-source alias
  and repeating unchanged reused evidence with cumulative wire attempts staying
  **2 -> 2 -> 2**. The final fixture run and repeat completed with both analytics
  caches reused on repeat. This is not real-account collection or a full
  provider-enabled library rebuild; Google was disabled in this live smoke.
- All seven isolated real-CSV/live-smoke SQLite databases passed integrity and
  foreign-key checks. Original CSV SHA-256 hashes stayed unchanged.
- The previous source-only JSON export and isolated acceptance databases were
  removed in the subsequent approved cleanup; those counts are historical,
  not a claim that the files still exist. Default configuration, its
  10,000-book budget, credentials and scheduling remained unchanged.

Remaining provider work is a full coverage benchmark when operationally
available, plus an opt-in Hardcover pilot before deciding whether to integrate
another catalog. No complete-enrichment or improved-prediction claim is made.

Earlier provider-enabled rebuilds, one-off owner-approved resets and recovery
backups are historical records in PLAN.md, not an ongoing deletion policy or a
claim that those runtime artifacts exist in every checkout.
