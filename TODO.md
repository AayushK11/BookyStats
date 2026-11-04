# Delivery status

Reader-experience repairs, complementary metadata and learned ranking passed
the release gate and backed-up real-data validation. The owner reset removed
the earlier report 7. A fresh provider-enabled rebuild and repeat now published
`data\reports\report-2\library.pdf` (19 pages). Source import, analytics and delivery
passed; the overall run remains partial because enrichment is incomplete.
Implementation and acceptance evidence are tracked here; runtime data stays local.
See [PLAN.md](PLAN.md) for requirements and historical evidence.

## Owner-requested local reset — 2026-11-04

- [x] Remove repository databases, backups, reports, logs, model/vector runtime
  caches, `.venv`, build outputs and test/type/lint/Python caches.
  Removed 9,877 files and 267 pytest symlinks, about 1.09 GiB.
- [x] Preserve the three supplied CSVs, Google credentials, root configuration
  and every source/test change, including the 12 untracked implementation files.
  Verify all 191 retained files by SHA-256. Immediately after reset, `data`
  contained only `inputs` and `credentials`, without databases or reports.
- [x] Recreate the pinned CPU environment at the owner's request. Preserve only
  genuine provider cooldowns/counters from a verified validation copy; do not
  restore old catalog responses, library data, vectors or report caches.
- [x] Complete the requested fresh provider-enabled rebuild in 25m 11s and an
  unchanged provider-enabled repeat in 33.8s. Both correctly returned partial
  (exit 3), while all three imports, analytics and report delivery completed.
- [x] Verify 2,153 source records, all four stores comprehensively, immutable
  bundle hashes/shared manifest/as-of, original CSV/config bytes, Monte Cristo's
  1,276 pages and byte-preserving offline status. Render/inspect the 19-page PDF.
- [x] Measure first-run network requests: Open Library 1,420, Google 0 under its
  preserved quota gate, Wikidata 1 followed by maxlag deferral. Repeat: 0/0/1
  respectively; Wikidata's one request was a due retry, not zero-wire reuse.
  Taste/watchlist/recommendations reused with no encoder calls/runtime imports;
  source identities, previous report bytes and append-only log prefix survived.
- [ ] Complete remaining enrichment when providers permit it. The fresh cache
  currently has only 31 usable descriptions (22 rated Read, none watchlist).
  Learned ranking correctly stays inactive because per-fold description support
  is insufficient. Current coverage is 436 ranked/377 abstained, 10 shortlisted,
  not the earlier cache's 809 ranked. Open Library incomplete outcomes stay
  parked; Google cannot retry before 18:00:37 +05:30, which is not a promised
  quota reset. Wikidata maxlag remains external provider evidence.

## Complementary metadata and ranking integration — 2026-11-04

The semantic/learned recommendation upgrade was delivered on the actual local
data before reset. Optional GPU support is implemented and CPU-host tested;
real GPU execution and configured cross-platform CI are not yet verified.

- [x] Integrate pinned local CPU embeddings, verified atomic caches and explicit
  offline/setup failure behavior without loading a model in `status` or `fetch`.
- [x] Fit training-only cross-fitted hybrid weights, evaluate same-cohort ranking
  with connected coauthors held together, and apply predefined activation gates.
- [x] Add quality-bounded content/genre/author diversity with unchanged eligibility,
  possible-Read abstention and verified series ordering.
- [x] Preserve v1/v2 and early-v3 report bytes, run full CPU validation and actual
  model smoke, and publish backed-up real-data report/repeat acceptance.
  **1,425 Python tests** (one opt-in smoke skipped in the normal suite),
  51 JavaScript tests, Ruff lint/format, strict mypy and builds passed before the
  optional GPU extension. A clean noneditable Windows installation passed.
- [x] Rank **809/813** watchlist works (previously 539), with 10 shortlisted and
  four explicit abstentions. Same-cohort learned NDCG@10 **0.6242** beats mean
  **0.5262**, current/genre **0.5480** and simple length **0.5616**. Top-ten
  high-rating precision is **26.0%**, versus **14.3%** current and **16.3%**
  length. These retrospective results are not future recommendation accuracy.
- [x] Keep learned description/era weights at zero when unsupported; categorical
  and length evidence drive this fit. Retain descriptive public-blurb neighbors
  without claiming that semantic vectors improved rating prediction.
- [x] Reuse all 483 vectors on actual report 7 without encoder calls or model
  imports. Preserve all provider counters/gates and source/history bytes.
  Verify offline status is byte-preserving; render the 20-page PDF and inspect
  the shortlist/evidence pages.
- [x] Complete exclusive CPU/CUDA installations, lazy automatic device selection,
  explicit fallback/required-CUDA behavior and final clean-profile validation.
  Final gate: **1,444 Python tests** (two opt-in checks skipped in the normal
  suite), 51 JavaScript tests, Ruff lint/format, strict mypy and builds.
  Actual socket-blocked CPU inference, CUDA-profile CPU fallback, required-CUDA
  rejection and fresh-process no-runtime-import cache reuse passed on Windows.
  CPU fingerprint compatibility preserves all existing report-7 vectors.
- [ ] Exercise real compatible NVIDIA hardware; Windows CPU-host injected/provider
  fallback tests do not establish GPU performance, and Linux/macOS CI is pending.

- [x] Add an optional public Wikidata adapter with strict work/type identity,
  selected catalog-ID conflict vetoes, claim ranks/date precision, paired series
  membership/order and separately scoped original-work language.
- [x] Wire configuration, raw capture, durable cache/gates, queue versions,
  work-level analytics/quality and bounded request deferral. Reuse existing
  schema versions; do not rebuild stores or retry unchanged legacy attempts.
- [x] Add verified series context and earlier eligible installment ordering,
  equal-score shortlist variety and typed connected-coauthor-held-out
  baseline/current/shadow evaluation. Keep richer scoring inactive.
- [x] Preserve original v1 recommendation payloads/checksums/cache keys under
  strict version-specific decoding; test historical reads and corruption.
- [x] Complete the final gate: **1,361 Python tests, 51 JavaScript tests**,
  Ruff lint/format, strict mypy and sdist/wheel builds; packages exclude runtime
  data/configuration/credentials and include the provider/helper resources.
- [x] Run backed-up provider-enabled real-data E2E on copies and default stores;
  measure added coverage, settled-work zero-wire reuse, retained history,
  coherent report delivery and offline status.
- [x] Fix two live-discovered integration defects: persist HTTP-200 API pauses
  across clients and remove recognized numbered-series display suffixes from
  search queries without relaxing original-book identity checks.
- [x] Preserve all 2,153 source identities and original CSV/credential/history
  bytes. Keep schema versions unchanged; verify all four stores comprehensively.
  Actual default Wikidata results: four saved attempts, three selected works,
  one unresolved, 2,149 deferred. Read-series coverage **89 -> 90**; other headline
  coverage remains unchanged. Three settled-work lookups reused saved responses
  with zero new wire requests. Google/Open Library counters remain **998/1,421**.
- [x] Evaluate 572 rated works across 304 connected-author components. Same-cohort
  mean/current/shadow MAE: **0.2036 / 0.2272 / 0.2133 stars**. Shadow does not beat
  the mean and remains inactive; this is not recommendation accuracy.
- [x] Publish coherent report 5; verify all 20 pages' text frames and inspect the
  rendered reader experience. Offline status changes no database/sidecar bytes.
- [ ] Complete broader Wikidata acquisition when provider pauses permit it;
  Google remains under its existing quota gate and Open Library has parked
  incomplete outcomes. Successful report delivery is not full provider recovery.

## Reader-experience repair — 2026-11-04

- [x] Consume selected identity-valid saved Google descriptions/genres, retain
  work/edition boundaries, reject clipped previews as full descriptions, and
  preserve canonical Google book citations.
- [x] Recover grouped labeled page counts, including Monte Cristo's **1,276**
  pages, without changing source CSVs or book identity hashes.
- [x] Introduce bookish chapter styling, hide printed version bookkeeping,
  simplify new report paths, and retain immutable historical layouts.
- [x] Refine real-library pagination: intact charts and chapter-opening tile
  grids, with duplicate cover metrics removed only from the visible overview.
- [x] Explain progress, attempts/completions, partial metadata and report
  readiness; preserve append-only logs and complete grouped issue counts.
- [x] Final integrated gate: **1,264 Python tests, 51 JavaScript tests**, Ruff
  lint/format, strict mypy and package builds passed.
- [x] Final real-data refresh: 730 Read/813 watchlist works, 572 linked ratings,
  483 substantive descriptions and 1,033 genre-covered works. First-publication
  years cover 1,516 works; edition-publication dates cover 1,539. Clipped previews
  no longer count as full descriptions; coverage is not factual accuracy.
- [x] Recover strictly labeled publication dates and six exact genre aliases.
  Keep work/edition scope, precision and candidate provenance separate; report
  incompatible direct/row candidates without failing the collection.
- [x] Create verified backups of all four default stores, refresh offline, and
  repeat unchanged. All 2,153 records were unchanged on repeat; taste, watchlist
  and recommendation caches reused. Comprehensive verification passed for all
  four stores. CSV/config/credential bytes and historical reports were preserved.
- [x] Inspect the actual appended log and saved status; status changed no database
  bytes or sidecars. Report 3 matches all 20 visually accepted preview pages and
  passed text-frame and coherent-bundle hash/manifest checks.
- [x] Keep Google/Open Library wire counts at 998/1,421 and retry diagnostics
  unchanged. Both acceptance runs explicitly disabled online lookups; provider
  coverage remains partial and Google recovery was not tested.
- [x] Investigate Wikidata using seven public requests for five titles and
  offline refinement: three compatible work candidates, including explicit
  series order. No production integration; catalog disagreements remain vetoes,
  and this is not representative coverage or independently measured accuracy.

## Earlier integration — 2026-11-03

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
- The current saved inputs provide no trusted completion-date evidence;
  library-addition, publication and capture dates do not fill that missing
  personal reading history.
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

## Historical saved products — prior acceptance, not current output

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
