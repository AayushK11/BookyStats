# Contributing

Read [README.md](README.md) for use, [PLAN.md](PLAN.md) for feature requirements,
and [.github\copilot-instructions.md](.github/copilot-instructions.md) for the full
repository rules. Keep changes focused and documentation plain.

## Code layout

All package code lives under `src\bookystats`:

| Area | Responsibility |
| --- | --- |
| `cli` | Arguments, wiring and displayed output |
| `application` | Reusable sync, enrichment, analytics and product orchestration |
| `domain` | Typed contracts, dates, matching, metadata/reader rules and recommendation evidence |
| `adapters` | CSV parsing, metadata HTTP, Google authorization and PDF rendering |
| `persistence` | Raw/library/cache stores, analytics/recommendation history and atomic report bundles |
| `runtime` | Config, locking, logs and retained disabled scheduling guards |

Keep CLI details out of application services and parsing out of storage. Reuse
`domain\interfaces.py`; a future HTTP API should call the same services.
Remove unused code, dependencies, fixtures and helpers rather than keeping future
scaffolding. Browser automation adapters and dependencies were removed. The three
commands are `fetch`, `sync` and `status`. `fetch` writes the packaged Goodreads
console helper; only explicit manual browser execution captures a shelf.
CSV operation has no source-browser dependency. Backend analytics runs after
metadata; recommendations, quality diagnostics and PDF/JSON delivery follow
successful analytics automatically. Automated source collection remains later work. No frontend,
broker or new spec/documentation folders are needed.

Tests mirror the code areas. Put shared builders in `tests\support` and sanitized
fixtures in `tests\fixtures`. Add focused tests for changed behavior.

## Rules that protect the data

- Plain sync reads exact paths from the top-level JSON `files` object, relative to the selected data
  directory. Never fetch sources or replay the archive for missing configured
  files. Only advanced explicit file mode can replay omitted inputs.
- Config JSON is flat: `schema_version`, `accounts`, `files`,
  `http_timeout_seconds`, `metadata` and `weekly` are top-level fields. Do not add
  a `settings` wrapper to examples or saved config.
- Do not mix Goodreads whole-library and split Read/watchlist CSVs. Archive each
  file before parsing; publish healthy scopes separately and keep the last
  complete result for a failed scope.
- Each input is a complete collection snapshot, not an append/delta patch.
  Point its configured path at the next full export for the same reader.
- The three supplied CSVs have fixed structures. Do not edit them or require new
  headers/exports to support analysis; improve parsing and selected metadata.
- Goodreads owns history/watchlist data where supported; StoryGraph supplies
  personal ratings and matching identity from explicit Read rows only. StoryGraph
  dates, reviews, statuses and other personal fields remain raw-only.
  Its Read
  Status selects that import scope, not authoritative history. Preserve all rows
  in the raw archive; keep other StoryGraph fields raw-only.
  Require Read Status: missing, empty or unknown values fail that scope rather
  than guessing. Report raw rows separately from active processed records.
- Preserve every supplied byte/field and full metadata responses. Do not invent
  dates, zeroes, reviews or identity links. A complete file is not proof of a
  complete account.
- Flattened `Row_Details` does not establish personal reviews/ratings or reading
  dates. Browser-captured genre/series labels and script-derived series numbers
  are untrusted. A helper version alone does not establish verified field capture;
  preserve originals without promoting them into trusted analytics features.
- Keep the library separate from the metadata cache. Resolve compressed payload
  references through library/payload APIs, not SQL JSON functions.
- Keep metadata outcomes separate from source success. Validate lookup identity
  before saving results, and save validated sequential results before the next lookup.
- Default to Open Library first and Google only for remaining selected,
  identity-valid public-description/recognized-genre gaps. Optional metadata
  alone must not trigger fallback. Keep `metadata.strategy=independent` for
  explicit independent passes. Strategy skips are not provider matches; report
  bounded core coverage separately from full provider coverage. Defer Google
  authorization until due fallback targets need it.
- Reuse verified cached Open Library works across compatible query identities.
  Preserve ambiguity across the local catalog; an exact-query cache is not
  permission to choose one of several plausible works. Work-only catalog
  matching never establishes an edition. Bound new detail requests while
  continuing to use cached evidence after the allowance is exhausted.
- Do not schedule metadata by age. Unchanged successful or deterministic partial,
  ambiguous and invalid attempts stay parked; new records, changed identity or
  provider implementation can become eligible. Load legacy `metadata.max_age_days`
  only for compatibility; omit it on save. Retryable record failures wait at least
  six hours, and a longer durable host/provider gate still wins. Keep parked
  coverage outcomes visible instead of reporting falsely complete enrichment.
  Rating/status-only changes do not invalidate provider identity. Never-attempted
  records and due transient retries may also queue; do not promise strictly
  new-row-only work. Analytics retains separate semantic/as-of cache rules.
- Keep provider/host retry gates durable across processes; preserve safe status,
  retry diagnostics and wire counts without credentials. Old captures remain
  unknown. Never reset a retry gate to make a run pass.
- Narrow incomplete/contaminated batches rather than relaxing individual matching.
  Preserve completed prefixes and report unattempted targets with their actual
  deferral cause. Prioritize authoritative Read records within limited budgets.
- Recognize Google daily exhaustion only from explicit structured provider
  evidence, not generic 403/429 or quota wording. Persist at least a six-hour
  cooldown and honor longer Retry-After deadlines; do not promise a reset time
  or equate the local book budget with the provider's project quota.
- Keep reciprocal unique full-title/full-author repairs reversible and work-only.
  Use active records, discriminating series/volume/omnibus guards and selected
  catalog conflict vetoes. Do not merge editions without shared validated ISBN
  evidence or treat synthetic IDs as identifiers. Shared-ISBN repairs also need
  compatible title/author evidence and conflict checks; a candidate count is not
  a count of bad books.
- Analytics inputs pin confirmed work IDs, compatible source snapshots and
  selected identity-checked metadata. StoryGraph contributes ratings only;
  its dates and other personal fields remain raw-only.
- Selected public provider work metadata may follow confirmed catalog-work links,
  including StoryGraph-origin records. Never reuse their raw reader fields or
  another record's edition facts. Choose alternative descriptions deterministically
  and preserve the selected evidence.
- Keep calculation code in `domain.analytics`; inject `AnalyticsService` into
  `SyncService`. Cache taste and watchlist inputs separately and rebind reused
  results to the current source references.
- Use `AnalyticsStore` for typed, hash-checked immutable cache entries and atomic
  historical reports. Keep `analytics.sqlite3` ignored. A failure retains the
  last successful report; status only reads saved results.
- Unknown features are not negative examples. Leave whole works out of predictive
  validation; fit the mean baseline only on training data and disclose fallbacks.
  Compare years at equal volume and comparable feature mix when evidence allows.
  Current ratings grouped by reading year are not historical ratings.
- Keep connected coauthors together in grouped validation; use training-only
  same-cohort baselines and explicit unavailable/fallback states. Component
  resampling ranges describe stability, not confidence or future accuracy.
- Include the complete as-of date, including its year, in cache keys. Language
  aliases may share a group, but retain their original values and provenance.
- Keep edition-scoped language separate from work-level translation availability.
  The latter cannot fill missing edition language or support a language preference;
  neither proves the language the reader actually read.
- Keep deep reader/content analysis on Read, independent of rating availability.
  Separate work first-publication years from edition years, and show how the
  rating-linked sample differs from all Read books. Watchlist output is
  descriptive composition/missingness. Keep recommendations in their separate
  service, with conservative eligibility, evidence and explicit abstentions.
- Normalize genres using the versioned exact-alias family policy. Preserve raw
  provider subjects and unmapped unknowns; do not turn marketing/classification
  labels or browser observations into trusted genres or personality evidence.
- `content_analysis` uses versioned, transparent rules and description quotes.
  Six-hunger mentions describe content, not personality/colors/official scores;
  never substitute genre proxies for that evidence.
- Input-only `AnalysisEvidence.public_url` supplies a valid public book reference
  from the current Goodreads record. Never rewrite observation `source_url` or
  immutable CSV lineage to make content evidence pass validation.
- Include `description_provenance` in semantic cache keys: changing the public
  reference invalidates content; observation/capture time alone does not.
- For at least 64 taste works, profile/enjoyment/content use three worker
  processes. Watch comparison follows enjoyment. Only the main process writes
  SQLite; small inputs run serially and cache hits start no pool. Keep serial/
  parallel parity and failed-worker last-report retention tested.
- Recommendation and quality products use the exact saved analytics manifest
  and as-of timestamp. An uncertain possible-Read overlap is an abstention,
  never a forced match or a human correction requirement. Scores are ordering
  heuristics, not calibrated enjoyment probabilities.
- Publish PDF/JSON products as a hash-verified immutable bundle. Change the
  latest pointer only after every output succeeds; keep the last-good bundle
  on failure. Reject inconsistent manifests and corrupt files explicitly.
- Keep the PDF reader-facing and bounded; retain the full evidence and raw
  diagnostic codes in JSON. Personal rating statistics use StoryGraph only.
  Goodreads comparisons stay separate from preference and ranking inputs.
- Preserve historical recommendation calculation versions when unbinding
  provenance. Include that version in new semantic keys; a calculation upgrade
  must neither rewrite immutable caches nor make historical reports unreadable.
- Append incremental progress and bounded diagnostic examples with complete
  issue-code counts to `logs\bookystats.log`. Redact every line, retain earlier
  sessions, and never truncate logs or delete historical outputs during sync.

Root `config.json` holds nonsecret ByteMe identities/settings, not package defaults
or authenticated sessions. The default editable data directory uses it unless
ignored `data\config.json` overrides it; other data directories stay isolated.
Tests must use synthetic accounts and their own data directory.

## Credentials and local files

New machines need local Google client credentials and visible consent, or an API
key. Never commit secrets, passwords, tokens, cookies or `google-books-oauth.json`.
Google authorization/refresh happens only during sync; status stays offline.
Noninteractive sync must not prompt. See README for setup.

The three supplied timestamped CSVs and nonsecret root config are versioned.
Generated databases, logs, caches, profiles, credentials and backups stay ignored
and local. The library exceeds GitHub's regular-file size limit; do not force-add
runtime databases for a normal code delivery. Any explicit database transfer
needs suitable storage and closed connections. **Never commit logs.** Create
runtime folders/files only when needed.

Normal sync must not delete user data or backups. Any owner-requested reset is
a separate, explicit operation, not an automatic retention policy.

Storage safety lives in `persistence\inspection.py`, `integrity.py` and
`backup.py`, with status wiring in `cli\storage_status.py`:

- `booky status` is read-only. It must not migrate, checkpoint, write a journal or
  create `-wal`/`-shm` files; an older store is reported as `upgrade_needed`.
  `open_read_only` uses SQLite `immutable` only for a WAL database with no
  sidecars and rechecks stability afterwards. Never use it with live WAL data and
  never unlink WAL/SHM files by hand.
- Before a schema migration or explicit maintenance, create a SQLite online-backup
  copy under `data\backups\<UTC>-<store>-<reason>\` with a SHA-256 manifest and
  verify it; a failed integrity check or backup raises `StoreMigrationBlocked`
  and leaves the database unchanged. Backups are never pruned automatically and
  `restore_backup` never overwrites. Migrations must be additive and must not
  drop historical tables or delete rows.
- Opening a store checks identity, version and structure but does not decode all
  history. Latest/selected reads verify what they use; the comprehensive path is
  `verify_store`, `AnalyticsStore.verify_history` and
  `RecommendationStore.verify_history`.
- Current versions: library v4, analytics v3 (v2 readable until upgraded), raw v3
  and metadata v1 (application id `0x42594D44`). Cover changes with
  `tests\persistence\test_storage_safety.py` and scratch copies, never live data.

Runtime path resolution lives in `runtime\layout.py`: databases belong under
`databases`, OAuth under `credentials`, and locks/helpers under `runtime`.
Status recognizes legacy flat paths read-only. `SyncLock` checks the legacy
lock and migrates known files before a new sync opens stores; preserve bytes,
checkpoint/close SQLite first, reject conflicts and make partial moves resumable.
Do not bypass the layout helpers in CLI/OAuth wiring or relocate live databases.
Keep nonsecret config, configured inputs, report bundles and logs unchanged.

## Validation

Source distributions include code, tests and documentation, not local inputs,
databases, account configuration, credentials or scratch files. Keep that boundary
when editing the build manifest.

Install development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,cpu]"
```

The `cpu` and `cuda` extras are mutually exclusive runtime installations; do not
install both. Use a separate environment with `.[dev,cuda]` for NVIDIA work.
The CUDA profile pins ONNX Runtime 1.26.0 (CUDA 12/cuDNN 9); compatible local
drivers and libraries remain prerequisites, not dependencies Booky installs.
Unit tests inject provider availability and fallback; only a real CUDA model
smoke test establishes hardware execution. See README for installation choices.

Start with tests for the changed module. After Python changes include:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_literal_policy.py
```

For cross-cutting changes run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m build
```

The console helper uses browser JavaScript, not a Node dependency at runtime.
For its fixture-based development checks, use Node 20+:

```powershell
node --check src\bookystats\adapters\exports\goodreads_console.js
node --test tests\adapters\exports\test_goodreads_console.cjs
```

Keep the helper packaged in both distributions. Scope it to the configured
Goodreads account and current Read/to-read shelf; use sequential pagination,
stop on blocked or inconsistent capture, and never download a partial success.
Fixture checks do not establish live Goodreads DOM compatibility.

All first-party Python text/bytes, including tests and docstrings, belong in
`strings.py`. Other fixed values/declarations belong in `constants.py`; their
text components still come from `strings.py`. Only `None` and `Ellipsis` used as
type syntax are exempt. Do not weaken the literal-policy test. Reuse existing tools.

Keep fixture, local-browser and live evidence separate. Live checks need explicit
opt-in; a pytest marker alone does not exclude them. CSV/source-only E2E must
explicitly disable enrichment and cannot establish full provider coverage.
Historical test counts do not prove the latest changes passed.
Separate source/analytics acceptance from the overall run outcome: a provider-
enabled rebuild can finish both while honestly returning partial for incomplete
metadata. On a repeat, compare saved wire counters as well as requested targets;
zero new requests does not establish full coverage. Keep provider-disabled
failure/recovery evidence distinct from provider-enabled rebuild/repeat evidence.
Linked-rating coverage is not matching accuracy. Compare held-out errors with a
baseline on the same cohort; never compare different cohort sizes as an accuracy
improvement or call the result future recommendation accuracy.
