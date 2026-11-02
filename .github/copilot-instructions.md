# Repository instructions

## Scope and structure

- This is a Python 3.12+ local-first ingestion package. Public commands are only
  `booky fetch`, `booky sync` and `booky status`; `--scheduled` is private task-runner plumbing.
- Keep CLI, application service, domain contracts, adapters, and storage separate.
  Reuse `domain\interfaces.py` protocols; keep service logic reusable by a future HTTP API.
- Follow the four-stage architecture in `PLAN.md`: raw capture, processing and
  enrichment, cached analysis, then watchlist ranking. Plain `booky sync` processes
  exact configured CSV paths; it never fetches Goodreads/StoryGraph or starts a
  source browser. Backend analytics is implemented after metadata; ranking,
  automatic live source acquisition and scheduling remain future work.
  `fetch` only writes the Goodreads browser-console helper for explicit manual
  Read/watchlist capture. It must not make source requests, change input paths,
  launch browsers or expose credentials.
- Keep manual invocation reusable by future triggers. Do not
  require metadata-selection or separate OAuth setup commands. Helper generation
  belongs only to the explicitly requested `fetch` command, never implicitly to sync.
  Google consent starts automatically when needed in interactive sync; headless
  runs never prompt. Explicit file flags retain legacy advanced compatibility;
  only explicit mode can replay unspecified archived inputs. Normal sync never
  substitutes archived inputs for missing configured paths. Durable task
  orchestration and cron deployment remain deferred.
  Do not add a website, background pipeline service, or broker for these stages.
- Use meaningful names, plain modular folders, and tests organized by module.
- Remove obsolete code and keep `TODO.md` a current, evidence-based checklist.
- Keep personal account IDs/URLs in configuration, never package defaults.
  Nonsecret root `config.json` versions ByteMe identities (`byte_me`, Goodreads
  `79839274`) and settings for the editable checkout's default data directory.
  Ignored `data\config.json` can override it; explicit other data directories
  remain isolated. These identifiers are not passwords or authenticated sessions.
  Tests supply synthetic accounts explicitly.
- Read exact paths from the top-level JSON `files` object: `storygraph_file`,
  `goodreads_watchlist_file`, `goodreads_read_file`, or alternative official
  whole-library `goodreads_file`; never mix whole-library and split inputs.
  Resolve paths relative to the selected data directory, not config location/cwd.
  Local status shows the actual config path and each CSV filename/ready-missing state.
- The three supplied CSVs and their structures are fixed. Do not change their
  bytes/headers or require replacement exports; improve processing and metadata.
- Config JSON is flat: `schema_version`, `accounts`, `files`,
  `http_timeout_seconds`, `metadata` and `weekly` are top-level fields, never
  nested under `settings`.
- Keep the detailed phased product roadmap in the root `PLAN.md`. Do not add
  spec, plan, forge, or process-paperwork folders, or phase labels to implementation
  modules.
- Follow the analytics evidence, capability inventory and caching/input-list
  requirements in PLAN.md. Keep `domain.analytics` separate from the injected
  `AnalyticsService` and the input reader/store. Pin confirmed work IDs, compatible
  current snapshots and selected identity-valid metadata. Cache taste/watchlist
  separately, rebind provenance on reuse and retain last-good reports on failure.
  Store typed, hash-verified immutable caches and atomic historical reports in
  ignored `analytics.sqlite3`; status reads saved reports offline. Do not add
  images, a frontend, ranking or annual reviews as part of that backend work.
- Reader/content analysis uses all Read books, not only rated ones. Watchlist
  analysis stays descriptive composition/missingness, not recommendations.
  Keep work first-publication and edition years separate; audit rating availability.
- Selected public provider work metadata may follow confirmed catalog-work links,
  including StoryGraph-origin records. Do not copy raw reader fields or
  other-record edition facts. Keep alternative-description selection deterministic.
- Keep edition-scoped language separate from work-level translation availability;
  neither proves the language actually read. Available translations cannot fill
  missing edition language or support a language preference.
- Content themes/six-hunger mentions require versioned rules and description
  evidence quotes, without ratings dependence, genre proxies or personality claims.
- Keep input-only `AnalysisEvidence.public_url` separate from immutable
  observation `source_url`/CSV lineage. Use the current Goodreads public book
  reference, validating public source, scope and text. Content semantic keys
  include `description_provenance`; public-reference changes invalidate content,
  observation/capture-time changes alone do not.
- At 64 or more taste works, use three worker processes for profile/enjoyment/
  content, then watch comparison after enjoyment. Keep SQLite writes in the main
  process, serial small inputs and no pool on cache hits; preserve parity and
  last-report retention when a worker fails.

## Mandatory literal policy

- **Every first-party Python text/byte literal belongs in
  `src\bookystats\strings.py`, including tests, docstrings, SQL, selectors, URLs,
  keys, messages, formatting templates, and annotation text.**
- Other fixed Python values, enums, fixed collections, compiled patterns, and
  compiler-sensitive shared policy declarations belong in
  `src\bookystats\constants.py`. Their text/byte components still come from
  `strings.py`. Runtime numbers, booleans, `None`, and `Ellipsis` are not exemptions.
- Use the existing `strings as S` and `constants as C` imports and meaningful
  shared names. Do not scatter additional constants modules.
- Only `None` and `Ellipsis` used as type syntax are exempt.
  `tests\test_literal_policy.py` mechanically enforces literal placement.
  Do not bypass it, move literals into helper files, or weaken its checks.
- Declarative manifests/configuration and source HTML/XML/JSON fixtures remain
  data; they do not need conversion into Python constants.

## Data integrity and safety

- Goodreads owns the current to-read/watchlist and reading history, status, and
  other personal data. StoryGraph supplies only personal ratings and identity
  needed to match them. Its reviews, status, dates, rereads, and other attributes
  stay raw-only; do not publish them as processed facts. Keep personal ratings
  separate from Goodreads/provider community ratings.
- Preserve unknown/unavailable, empty, unsupported, and failed states; do not
  turn missing data into zero or invent dates. Retain date precision, observation
  scope, account identity, and source provenance.
- Match books/editions conservatively. Ambiguous candidates are not confirmed
  matches. Keep repeats idempotent and source snapshot publication independently
  atomic by source/collection; Goodreads read and to-read snapshots must not replace
  one another. Partial/failed collection retains its last complete snapshot.
- Keep the authoritative library separate from the metadata cache. Isolate
  account browser profiles and reject accidental account replacement.
- Browser automation code and dependencies were removed. Do not reintroduce
  unused scaffolding. The explicit console helper must stay scoped to the
  configured Goodreads account and shelf, stop on blocks/malformed or partial
  capture, preserve unknowns and use ordinary browser downloads. Automatic live
  collection remains future work; never bypass source or browser protections.
- Optional Google Books/Open Library enrichment retains enabled package/local
  configuration and this user's local 10,000-book run budget. Report provider
  failures/deferrals separately; source-only acceptance proves no full enrichment.
- Persist provider/host retry gates and safe HTTP diagnostics across processes.
  Preserve unknown legacy diagnostics; never reset gates to force completion.
  Refine incomplete/contaminated batches without relaxing individual identity
  checks, retain successful prefixes, and prioritize authoritative Read records.
- Accept explicitly supplied official exports and scoped Goodreads browser CSVs;
  keep whole-library, watchlist, and read input modes explicit. Store original bytes in the
  raw database before parsing. Preserve unknown source fields and full provider
  responses; make processed snapshots replayable with raw lineage.
- Archive each configured CSV before parsing. Missing/invalid input fails its
  own scope; healthy scopes publish independently and failed scopes retain their
  last complete snapshots.
- Version the three supplied timestamped `data\inputs\*.csv` files and nonsecret
  root config. Keep generated databases local and ignored; the library exceeds
  GitHub's regular-file size limit. Do not force-add runtime databases for normal
  code delivery.
  Input filename stamps are original archive capture UTC times, not proven export
  generation times. Logs, metadata cache, analytics DB, profiles, credentials and backups stay
  ignored. Create runtime files/folders when needed; never commit logs.
- Normal sync must not automatically delete user data or backups. Any explicit
  owner reset is separate; keep its current scope in TODO.md, not evergreen rules.
- Validate labeled browser-row metadata conservatively. Do not infer personal
  ratings, reviews, or reading-event dates from flattened UI text, or trust a
  script's `Series_Number` when description text can contaminate it.
  Browser genre/series labels stay unverified raw observations, not trusted
  analytics features; a helper version does not prove those fields were captured
  correctly. Preserve empty/unsupported states rather than inventing values.
- A complete file import is not a verified complete account collection and must
  never qualify as unattended/weekly collection evidence.
- Keep manual files and normal-browser/RSS capture explicit; never silently fall
  back between them. Sign-in is ordinary visible-browser interaction only.
  Do not bypass credential controls, bot protection, navigation guards, or downloads.
- Protect keys, cookies, profiles, databases, and personal payloads. Do not put
  credentials in chat, logs, fixtures, or source. Status must not fetch source data.
  New machines require local Google client credentials and visible consent (or
  an API key). Never ship secrets, passwords, tokens, cookies or ignored
  `google-books-oauth.json` in the repository.
- Preserve scheduling gates: explicit Windows weekday/time/timezone, both accounts,
  consecutive complete same-account/same-implementation runs including unattended
  evidence, and receipt freshness/consistency. Check activation fingerprints before
  scheduled collection. Never activate scheduling implicitly.

## Validation and reporting

- Reuse existing tools/dependencies. Run the smallest relevant tests first,
  including the literal-policy test for Python edits.
- For cross-cutting changes, run the full pytest suite, Ruff lint and format checks,
  strict mypy, and package build using the commands in `CONTRIBUTING.md`.
- Add focused tests for changed behavior and update directly related documentation;
  avoid unrelated cleanup and duplicate implementation prose.
- Separate fixture, local-browser, and real-account evidence. Never fabricate
  live-validation claims or assume an unattended source session will work.
- Explicitly disable enrichment in CSV/source-only E2E; its success is not proof
  of full provider enrichment or account completeness. Report passed full
  validation separately from running or pending real E2E.
- Read Your Color is inspiration, not a reproduced assessment. Use explicit
  supported appetite labels, not guessed colors, genre-derived personality or
  invented official weights. Unknown features are not negative examples.
  Hold out whole works and fit predictive baselines on training data only.
  Dated cohort findings need actual reading dates; current ratings grouped by
  reading year are not historical ratings. Cache keys include the full as-of date/year.
- Report linked-rating coverage separately from matching accuracy. Held-out
  errors need same-cohort baselines and do not establish recommendation accuracy.
  Do not call provider backoff quota exhaustion without saved evidence.
- Keep connected coauthors together in grouped validation and fit baselines on
  training data only. Component-resampling ranges describe stability, not
  confidence or future accuracy. Compare saved baseline/final inputs under the
  same policy and cohort; disclose fallbacks and metadata missingness.
