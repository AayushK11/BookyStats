# Next steps

**Configured CSV sync and backend analytics are implemented.** Final queue/matching
fixes passed the frozen-source gate and the approved clean rebuild/repeat passed
source and analytics acceptance. Both runs honestly remain partial because full
provider enrichment is incomplete; saved Google evidence identifies a daily project
quota limit, not a known reset time. Ranking, automatic source collection and
scheduling remain future work. Detailed requirements and historical evidence
stay in [PLAN.md](PLAN.md).

## Working foundation

- [x] Archive original bytes/unknown fields before parsing; publish healthy scopes
  independently and retain last complete snapshots on failure.
- [x] Read exact configured CSV paths without source browsers or archived fallback.
  Keep advanced explicit-file replay separate.
- [x] Document full collection snapshots rather than delta-only patches;
  same-reader new exports replace their scope. Reuse unchanged metadata identities;
  rating/status-only changes affect analytics without provider invalidation.
  Never-attempted records and due transient retries may still queue.
- [x] Preserve the fixed original CSVs: 1,054 StoryGraph rows, 813 Goodreads
  watchlist rows and 730 Goodreads Read rows; filename stamps are archive times.
- [x] Process only 610 explicit StoryGraph Read rows, including all 603 personal
  ratings. Archive the other 444 rows without matching/enriching them. Missing,
  empty or unknown Read Status fails that source scope. Goodreads owns history.
- [x] Report 2,597 raw rows separately from 2,153 active processed source records.
- [x] Keep profiles/settings in nonsecret root config, with local override and
  isolation for other data directories. Show config/CSV readiness in status.
- [x] Keep exactly `fetch`, `sync` and `status` public. `fetch` only generates the
  explicit manual Goodreads console helper; live browser behavior is unverified.
- [x] Support optional Google Books/Open Library and local Google authorization;
  never prompt in headless mode or fetch from status.
- [x] Keep inputs/root config versioned and all runtime databases, logs, backups,
  profiles, credentials and generated report exports local/ignored.

## Queue and matching repair acceptance

- [x] Remove age-driven metadata refresh. Load legacy `metadata.max_age_days`
  compatibly but ignore it and omit it when saving; remove it from root config.
- [x] Park unchanged deterministic partial/ambiguous/invalid attempts rather than
  re-requesting them each sync. Keep their coverage outcomes visible. New records,
  identity changes or provider-implementation changes can become eligible.
- [x] Apply a six-hour record floor to transient retries; persist host/provider
  gates, safe HTTP diagnostics and wire counts across processes.
- [x] Keep conservative, reversible work-only reciprocal unique full-title/
  full-author links, with active-scope, series/volume/omnibus and selected-catalog
  conflict guards. Keep editions separate without shared validated ISBN evidence;
  never use synthetic record IDs as bibliographic identifiers.
- [x] Normalize genres through 77 exact aliases across 25 versioned families;
  retain original provider subjects and unmapped unknowns rather than promoting
  marketing/classification or unverified browser labels.
- [x] Pass isolated real-CSV source-only acceptance with providers disabled:
  repeat/cache reuse, missing configured Read-path partial failure retaining the
  last-good report, then restored-config recovery.
- [x] Finish narrow shared-ISBN/subset-author/title repairs and explicit structured
  Google daily-quota cooldown validation. A confirmed daily quota needs a durable
  six-hour floor, respecting longer Retry-After; generic quota errors stay unknown.
- [x] Pass the frozen-source final gate after those fixes: 760 Python and 51
  JavaScript tests, Ruff lint/format over 90 Python files, strict mypy over 44
  source files, sdist/wheel builds and diff checks.

Final rebuilt coverage is 576/730 rating-linked Read works (78.9%), compared with
338 (46.3%) before these repairs: +238 links, not a matching-accuracy score.
All 603 StoryGraph Read ratings remain preserved; 27 remain unlinked under
catalog/subtitle/coauthor/ambiguity safeguards. Trusted Read metadata covers
529 descriptions, 552 original-work years, 271 normalized-genre-known works,
70 series-known works, 722 page counts and 729 formats. The former 291 broad-
subject-known count is not comparable with normalized genre coverage.
Matched-edition language remains unknown for all Read works.

## Approved final clean rebuild

This is the owner's explicit one-off operation, not normal sync or a retention
policy. Earlier broad resets are historical evidence in PLAN.md.

- [x] Retain recovery backup `data\backups\repair-20261102T181021Z`, containing all
  four databases and an input-hash manifest. Preserve original CSV hashes.
- [x] Back up all four databases at
  `data\backups\before-clean-rebuild-20261102T183257Z`; remove only
  `raw.sqlite3`, `library.sqlite3` and `analytics.sqlite3`.
- [x] Retain `metadata.sqlite3`, its provider cache and retry gates, saved
  credentials, all original CSVs and the recovery backup. Never clear a gate
  merely to force completion.
- [x] Complete actual provider-enabled, cache-backed run 1 at
  2026-11-02 18:33:13–18:38:19 UTC (5m06s): all 610/813/730 source records
  added fresh, six raw-hash/row checks passed and parallel analytics report 1
  completed with 219 findings.
- [x] Complete repeat run 2/report 2: all 2,153 records unchanged, zero additions/
  updates/removals, both analytics caches reused and zero new provider wire
  requests. Both overall runs remain `PARTIAL`/exit 3 solely for provider
  incompleteness; Open Library's zero-target repeat still reports missing coverage.
- [x] Verify four database integrity checks, zero foreign-key violations and
  unchanged full SHA hashes for all original CSVs. Retain useful rebuilt databases.
- [x] Verify rebuilt library: 2,153 sources, 1,570 works, 1,828 editions,
  242 unresolved candidate links (not a bad-book count) and zero reading events.
- [x] Keep provider-disabled missing-Read/last-good/recovery acceptance explicitly
  separate from the final provider-enabled rebuild/repeat; do not claim those
  failure checks were rerun against the rebuilt production databases.
- [x] Preserve credentials/cache/gates and original inputs; root config intentionally
  removes obsolete `metadata.max_age_days`. Both providers remain enabled and
  weekly operation disabled.
- [ ] Complete provider enrichment only when authorized and operationally
  available. The saved Google error reports a 1,000-query daily project cap;
  the configured 10,000-book run budget does not override it or prove a reset.

Open Library's rebuild requested 2,153 targets: 1,958 complete and 195 partial
outcomes, 2,052 cache hits and 1,139 selected records. Google received one daily
429 and deferred 2,152 behind the persisted six-hour floor. Repeat cumulative
wire counters stayed at Google 6/Open Library 1,995. No gate was reset.
View/export the saved analysis offline using README's `status --json` commands;
`data\analytics-report.json` remains an ignored local report.

## Backend analytics

- [x] Keep pure `domain.analytics` separate from injected `AnalyticsService`,
  input reading and storage. Save capability inventories and exact compatible
  source/metadata inputs before calculating.
- [x] Save typed, hash-verified immutable taste/watchlist caches and atomic
  historical reports in ignored `analytics.sqlite3`; rebind provenance on reuse
  and retain last-good reports on failure. Status reads the full report offline.
- [x] Analyze all Read books independently of ratings; keep enjoyment comparisons
  rating-linked, show missingness/rating-availability bias and keep watchlist
  composition descriptive rather than recommendations.
- [x] Separate original-work/edition years and matched-edition language/work
  translation availability. Keep dated/review analyses unavailable without data.
- [x] Use known-feature-only comparisons, shrunk effects, author fragility,
  leakage-safe whole-work holdout, training-only same-cohort baselines and
  coauthor-component blocking. Resampling describes stability, not confidence.
- [x] Include full as-of date/year in cache keys. Support equal-volume yearly
  breadth and comparable current-rating cohorts only when reading dates exist.
- [x] Use versioned description themes/six-hunger mentions with quotes, without
  ratings dependence, genre proxies, personality claims or invented color scores.
- [x] Keep public content references separate from immutable observation lineage;
  include description provenance in semantic cache keys.
- [x] Share only selected identity-checked public work metadata across confirmed
  catalog links; never copy raw reader fields or other-record edition facts.
- [x] Use three workers at 64 or more taste works; main-process SQLite writes,
  serial small inputs and no pool on cache hits. Verify parity/failure retention.
- [x] Preserve the historical fixed 314-work before/after comparison: both MAEs
  worsened. More linked ratings/metadata do not establish prediction improvement.
- [x] Audit the rebuilt 576-work cohort: author-blocked MAE 0.214046 versus its
  own training-only baseline 0.203587 (one fallback); leave-one-work-out MAE
  0.209932 versus its own 0.203120 baseline. Neither establishes predictive gains.

The supplied Read CSV has no usable dated reading events or personal reviews.
No frontend, images, annual reviews, ranking or automated collection were added.

## Later and deferred

- [ ] Rank the current Goodreads watchlist with eligibility, reasons, confidence
  and exact input references.
- [ ] Keep personal/public annual reviews deferred until core pipelines work.
- [ ] Implement and validate an approved live acquisition route for both sources;
  preserve official-export/RSS/browser research in PLAN.md.
- [ ] Prove repeated complete same-account collection and unattended operation
  before explicit scheduling approval. Files/replay do not qualify.
- [ ] Add reliable retry/resume orchestration if needed, without resident service
  or broker. Do not activate Windows scheduling on this machine.
- [ ] Define reviewed backup/restore and history-retention policies without
  automatic user-data or backup deletion.
