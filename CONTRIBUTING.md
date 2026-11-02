# Contributing

Read [README.md](README.md) for use, [PLAN.md](PLAN.md) for feature requirements,
and [.github\copilot-instructions.md](.github/copilot-instructions.md) for the full
repository rules. Keep changes focused and documentation plain.

## Code layout

All package code lives under `src\bookystats`:

| Area | Responsibility |
| --- | --- |
| `cli` | Arguments, wiring and displayed output |
| `application` | Reusable sync, checks and `AnalyticsService` |
| `domain` | Models, protocols, dates, matching rules and analytics calculations |
| `adapters` | CSV parsing, metadata HTTP and Google authorization |
| `persistence` | Raw archive, processed library, shared payloads, metadata cache and analytics store |
| `runtime` | Config, locking, logs and retained disabled scheduling guards |

Keep CLI details out of application services and parsing out of storage. Reuse
`domain\interfaces.py`; a future HTTP API should call the same services.
Remove unused code, dependencies, fixtures and helpers rather than keeping future
scaffolding. Browser automation adapters and dependencies were removed. The three
commands are `fetch`, `sync` and `status`. `fetch` writes the packaged Goodreads
console helper; only explicit manual browser execution captures a shelf.
CSV operation has no source-browser dependency. Backend analytics runs after
metadata; automated source collection and ranking remain later work. No frontend,
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
- The three supplied CSVs have fixed structures. Do not edit them or require new
  headers/exports to support analysis; improve parsing and selected metadata.
- Goodreads owns history/watchlist data where supported; StoryGraph supplies
  personal ratings and matching identity only. Keep other StoryGraph fields raw-only.
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
- Keep provider/host retry gates durable across processes; preserve safe status,
  retry diagnostics and wire counts without credentials. Old captures remain
  unknown. Never reset a retry gate to make a run pass.
- Narrow incomplete/contaminated batches rather than relaxing individual matching.
  Preserve completed prefixes and report unattempted targets with their actual
  deferral cause. Prioritize authoritative Read records within limited budgets.
- Analytics inputs pin confirmed work IDs, compatible source snapshots and
  selected identity-checked metadata. StoryGraph contributes ratings only.
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
  descriptive composition/missingness, not recommendations.
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

## Validation

Source distributions include code, tests and documentation, not local inputs,
databases, account configuration, credentials or scratch files. Keep that boundary
when editing the build manifest.

Install development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

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
Linked-rating coverage is not matching accuracy. Compare held-out errors with a
baseline on the same cohort; never compare different cohort sizes as an accuracy
improvement or call the result future recommendation accuracy.
