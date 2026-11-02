# BookyStats

A Python 3.12+ tool that imports reading CSVs into local SQLite databases.
**`booky sync` processes configured files. It does not fetch Goodreads or
StoryGraph, sign into either source, or need a browser binary.**

Sync also saves backend analytics. Watchlist ranking, automatic source collection and scheduling
remain future work. `booky fetch` generates an explicit Goodreads browser-console
helper; it does not fetch source data from the terminal. No frontend is included.

## Run it

From the checkout in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\booky.exe fetch
.\.venv\Scripts\booky.exe sync
.\.venv\Scripts\booky.exe status
```

The three public commands are `fetch`, `sync` and `status`; `python -m bookystats` also works.
Bare `booky` shows help. `status` makes no network requests: it shows the selected
config path, each CSV filename and whether it is ready or missing, plus a saved
analytics summary. JSON status includes the complete saved report.

To inspect or export that report without fetching or recalculating:

```powershell
.\.venv\Scripts\booky.exe status
$status = .\.venv\Scripts\booky.exe status --json | ConvertFrom-Json
$status.analytics.taste.findings
$status.analytics.taste.capabilities
$status.analytics.taste.preferences
$status.analytics.watchlist.findings
$status.analytics | ConvertTo-Json -Depth 100 | Set-Content -Encoding utf8 .\data\analytics-report.json
```

The export is an ignored local file, not a frontend or another public command.

### Capture Goodreads CSVs

`booky fetch` writes `goodreads-export.txt` in the selected data directory and
prints links for the configured Goodreads account's Read and to-read shelves.
Open each link in your normal browser session and run the helper separately on
each shelf. It follows that shelf's normal pagination sequentially and downloads
one timestamped CSV only after finishing. Account changes, blocked requests,
malformed rows and unsafe pagination stop the capture without a partial download.
It does not bypass browser protections or prove complete account collection.

Keep the original exports. Point the configured file paths at the new CSVs, or
supply all three paths to `sync` using the advanced file flags below.
StoryGraph personal ratings still require your supplied export.
`fetch` makes no network requests and changes no input files or configuration.
The helper has fixture-based JavaScript tests; live browser behavior is not yet
verified against the current Goodreads site.

### Rebuild on another machine

After cloning the pushed repository, run the installation commands above with
Python 3.12+ and retain the configured CSVs. No previous databases are required:
`sync` creates the raw archive, processed library, metadata cache and analytics.
Supported CSV structures and explicit account/shelf configuration are required;
an arbitrary unrelated CSV cannot be inferred into reading history.

Configure Google authorization locally through normal interactive consent or an
API key. Credentials and virtual environments do not come from Git. Provider
data can change or be unavailable, so a fresh rebuild is not guaranteed to
reproduce an earlier catalog snapshot exactly. Google currently reports a daily
quota limit; changing machines does not reset a shared project/account quota.
Use `status` to diagnose missing CSV paths or inspect saved results offline.

## Configuration and input files

Root `config.json` contains nonsecret ByteMe profiles: StoryGraph `byte_me` and
Goodreads `79839274`. These identify accounts; they are not passwords or signed-in
sessions. No personal account defaults are built into the package.

An editable checkout's default `data` directory uses root `config.json`
automatically. Ignored `data\config.json` overrides it. Another data directory
stays isolated and needs its own configuration. Select it with `--data-dir PATH`
or `BOOKYSTATS_DATA_DIR` (the flag wins); non-editable installs otherwise use the
platform's user-data directory.

Configuration is flat JSON: `schema_version`, `accounts`, `files`,
`http_timeout_seconds`, `metadata` and `weekly` are top-level fields, with no
`settings` wrapper. Plain sync reads the exact paths in `files`. This excerpt
shows that section; keep the other fields in the existing config:

```json
{
  "files": {
    "storygraph_file": "inputs\\storygraph-library_2026-11-02_08-27-54Z.csv",
    "goodreads_watchlist_file": "inputs\\goodreads-watchlist_2026-11-02_08-27-54Z.csv",
    "goodreads_read_file": "inputs\\goodreads-read_2026-11-02_08-58-33Z.csv"
  }
}
```

Paths are relative to the **selected data directory**, not the config file or
working directory. Use `goodreads_file` instead of the two split Goodreads paths
for an official whole-library CSV; never mix whole-library and split inputs.
For another reader, use a separate data directory and their profile settings.
`BOOKYSTATS_STORYGRAPH_PROFILE` and `BOOKYSTATS_GOODREADS_PROFILE` override saved profiles.
CSV files do not independently prove account ownership.

The three supplied files were restored byte-for-byte from the raw archive:

| File under `data\inputs\` | Records |
| --- | ---: |
| `storygraph-library_2026-11-02_08-27-54Z.csv` | 1,054 |
| `goodreads-watchlist_2026-11-02_08-27-54Z.csv` | 813 |
| `goodreads-read_2026-11-02_08-58-33Z.csv` | 730 |

Their filename timestamps are original archive capture times in UTC, **not
proven export-generation times**. These three CSVs and their structures are fixed
inputs: improve parsing and metadata without editing them or requiring new exports.

The StoryGraph file contains **610 Read rows and 444 to-read rows**. All 1,054
rows remain archived byte-for-byte, but only explicit Read rows enter processed
StoryGraph ratings, matching and enrichment. A missing, empty or unknown Read
Status fails that source import rather than guessing; other healthy scopes can
still publish. StoryGraph status selects this scope only: Goodreads remains the
authority for reading history and current watchlist membership.

## What sync does

1. Saves each file's original bytes before parsing.
2. Checks and processes it without discarding unknown fields.
3. Saves each healthy source/shelf result independently.
4. Optionally looks up catalog metadata in Google Books and Open Library.
5. Calculates or reuses analytics from the saved source and metadata inputs.
6. Writes checks, saved reports and a local redacted log.

A missing or invalid file fails only its own scope; its last complete result
stays available. Normal sync never substitutes archived data for a missing path.
Metadata failures do not undo successful CSV imports. Processing does not
automatically delete inputs, archived data or backups.

Goodreads supplies Read/watchlist membership and personal history where the input
supports it. StoryGraph supplies personal ratings and matching identity from
explicit Read rows only;
its other fields stay raw-only. Community ratings never replace personal ratings.
Missing information is not zero, and uncertain book matches stay unresolved.
Browser-captured CSV genre/series labels are not verified catalog facts; their
original values stay in the archive and cannot drive analytics as trusted labels.

### Tomorrow's export

Each configured CSV is a **complete collection snapshot**, not a delta-only
patch file. For the same reader, retain the original and point the configured
path at the new full export for that scope. A file containing only new books
would replace that scope's membership rather than append to it.

Unchanged book identities reuse saved enrichment. New records and changed
identities can queue lookups; rating/status-only changes do not invalidate
provider metadata. Previously never-attempted records or due transient failures
may also queue, so this is not strictly “new rows only.” Successful lookups do
not refresh merely because a day passed, and saved provider gates still apply.
Analytics uses its own semantic/as-of cache: changed ratings, membership or
relevant metadata can recalculate affected components without repeating
unchanged provider lookups.

The files contain 2,597 raw rows; the active processed scopes contain **2,153**
records (610 StoryGraph Read, 730 Goodreads Read and 813 watchlist).
The library's works table also retains history, so its row count is not a count
of unique active books. StoryGraph has 603 personal ratings, all in its Read scope.
The clean rebuilt report has **576 of 730 Read works rating-linked (78.9%)**,
compared with 338 (46.3%) before these repairs: 238 additional links. All 603
StoryGraph Read ratings remain preserved; 27 remain unlinked rather than forcing
catalog, subtitle, coauthor or ambiguous candidates together.
This is linked-rating coverage, not a matching-accuracy score.
The supplied Read CSV has no usable dated reading events or personal reviews.
Importing every file row does not prove complete account coverage.

Matching can confirm reversible work-only links from reciprocal unique full
canonical titles and full authors across different or missing ISBNs. Active-scope,
series/volume/omnibus and selected-catalog conflict checks still apply. Edition
identity remains separate without a shared validated ISBN; synthetic record IDs
are never bibliographic identifiers. Shared-ISBN repairs also require compatible
title/author evidence and the conflict guards.

## Saved analytics

Reader and content analysis uses Goodreads Read books, including books without
ratings. It describes metadata coverage, page quartiles, first publication by
work separately from edition years, and known-feature combinations. It also
checks how representative the rating-linked subset is. Enjoyment comparisons
use only confirmed personal ratings, with support checks and adjusted means.

Watchlist output is descriptive: composition, missing information and differences
from Read. It does not learn a separate reader personality or recommend/rank books.

Reports use confirmed book matches and selected, identity-checked metadata.
Selected public work-level metadata can follow confirmed links across catalog
records, including StoryGraph-origin records. This never imports StoryGraph raw
reader fields or another record's edition facts. Alternative descriptions are
selected deterministically with their provenance retained.
Taste and watchlist results are cached separately; changing only the watchlist
does not repeat taste calculations. Reports retain their input references, and a
failed analysis leaves the last successful report available.
For larger inputs, profile, enjoyment and content calculations use three worker
processes; database writes stay in the main process. Small inputs and cache hits
avoid starting that pool.

Description analysis uses transparent, versioned rules, with evidence quotes for
themes and six reading-hunger content mentions. These describe the books, not
the reader's personality, and do not depend on ratings or use genre proxies.
No colors or official scores are guessed. It does not reproduce the official
[assessment](https://readyourcolor.com/assessment). Dated reading-history and
review-based findings remain unavailable for the supplied Read file.
The clean rebuilt Read report has 529 descriptions, 271 normalized-genre-known
works, 70 series-known works and 552 original-work publication years; 722 works
have page counts and 729 have formats. Before these repairs, coverage included
461 descriptions, 46 series-known works and 477 original-work years.
The versioned genre mapping uses 77 exact aliases across 25
families; raw subjects, marketing/classification labels and unmapped values are
not automatically genres. Original provider observations remain preserved, and
unknowns remain unknown. Consequently normalized genre coverage is intentionally
lower than earlier broad subject coverage. Quarantined CSV labels do not count.
The former 291 broad-subject-known works are not comparable with the new 271
normalized-genre-known works. Matched-edition language remains unknown for all
Read works; work-level translation availability cannot establish a language
preference.
Quotes use a separate public book reference without
changing the original CSV observation's file lineage. Reported theme/hunger
counts are text mentions, not whole-book labels or reader traits.

The engine now checks predictions by leaving out one whole work at a time,
without training on that work. It compares MAE/RMSE with a training-only mean
baseline and reports fallback use. It also supports equal-volume yearly genre
breadth and like-for-like comparisons of current ratings grouped by actual
reading year. The supplied data has no reading dates, so those dated findings
still need observations. Unknown features never count as negative examples.
On the current 576-work cohort, author-blocked MAE is 0.214046 versus its own
training-only mean baseline of 0.203587, with one fallback. Leave-one-work-out
MAE is 0.209932 versus its own 0.203120 baseline. Both predictors are worse than
their baselines: **coverage improved, but predictive accuracy gains are not
established.** These errors are not future recommendation accuracy. The earlier
fixed-314-work comparison remains historical evidence in PLAN.md; do not compare
different cohorts as an accuracy improvement.

To increase usable coverage, keep supplying full snapshots and improve
conservative identity evidence and validated provider fields when providers are
available. Inspect report capabilities and missingness before interpreting
results. More descriptions or rating links can enable more analysis, but cannot
prove better prediction. Evaluate predictive changes on the same held-out
cohort against a training-only baseline; do not lower matching safeguards to
inflate coverage. The offline commands above expose the saved analysis.

## Advanced file imports

Explicit file flags remain compatible:

```powershell
.\.venv\Scripts\booky.exe sync --storygraph-file "C:\Books\StoryGraph.csv" --goodreads-watchlist-file "C:\Books\Watchlist.csv" --goodreads-read-file "C:\Books\Read.csv"
```

Only this explicit mode may replay archived inputs for omitted file arguments.
`--goodreads-file PATH` accepts the alternative whole-library export.

Runs report `SUCCESS`, `PARTIAL` or `FAILED`. Exit codes: `0` success,
`3` partial/failed checks, `4` overlapping sync, `1` handled error, `130` interruption.

## Optional metadata

Google Books and Open Library are enabled by default; saved configuration can
disable either. The selected local book budget is 10,000 per provider per run,
not a guarantee of full coverage or permission to exceed provider limits.
The package default is 200. Successful and deterministic partial lookups are not
repeated merely because time passes. Identity or provider-implementation changes
make them eligible again. Retryable failures wait at least six hours after the
saved attempt, while durable provider/host gates may defer them longer. Legacy
`metadata.max_age_days` remains load-compatible but is ignored and omitted when
configuration is saved; it no longer schedules refreshes.
No lookups due does not mean full coverage: parked incomplete or ambiguous
attempts remain visible in the run receipt and active-scope metadata status.
Open Library needs no credentials. Lookups remain bounded and cached.
The CLI enables details for confirmed Open Library works. Optional-field
validation errors may leave other verified fields usable; identity problems,
truncation and unverified candidates still block selection.
Incomplete or contaminated batches are split into bounded narrower searches;
an incomplete or ambiguous individual search is not promoted into a match.
Read records are prioritized when the lookup budget is limited. Validated
prefix results survive a later cooldown or budget deferral.

Provider/host retry deadlines, interruption guards and wire-request counts now
persist across runs. Raw archive schema v3 retains allowlisted HTTP diagnostics
without credentials. Legacy captures keep unknown diagnostics; their missing
headers are not invented. A new process does not clear an active retry gate.
The saved Google rejection explicitly identifies a 1,000-query daily project
quota. The configured 10,000-book run budget does not override that cap.
An explicit structured daily-quota rejection requires a durable six-hour minimum
cooldown, respecting a longer provider deadline; it does not establish a reset
time. Unknown or generic quota failures must not be relabeled as daily exhaustion.

Google Books uses `GOOGLE_BOOKS_API_KEY` first, or local OAuth authorization.
Interactive sync can ask for client credentials and open normal Google consent.
Alternatively set `GOOGLE_BOOKS_CLIENT_ID` and `GOOGLE_BOOKS_CLIENT_SECRET` locally.
Noninteractive runs never prompt. A new machine needs its own local credentials
and consent, or an API key; credentials cannot ship in the repository.

Enable the Books API and configure its consent users. A Desktop OAuth client is
recommended; Web clients need the exact redirect
`http://127.0.0.1:8765/oauth2/callback`. Client credentials alone are not authorization.
Tokens are stored in ignored `google-books-oauth.json` under the data directory.
Refresh happens during sync, never status. `.env` files are not loaded automatically.
Never put keys, secrets, passwords, tokens or cookies in commits, logs or chat.

## Stored files

| Path | Purpose | Git policy |
| --- | --- | --- |
| Root `config.json` | Nonsecret profiles and settings | Versioned |
| Three supplied timestamped `data\inputs\*.csv` files | Configured source inputs | Versioned |
| `data\raw.sqlite3` | Original input bytes and full metadata responses | Ignored; retained locally |
| `data\library.sqlite3` | Processed results and history | Ignored; retained locally |
| `data\metadata.sqlite3` | Provider lookup cache and durable retry gates | Ignored; retained during the approved rebuild |
| `data\analytics.sqlite3` | Saved analytics and separate component caches (schema v2) | Ignored |
| `data\logs\`, `data\backups\`, profiles and credentials | Local runtime files | Ignored; never commit logs |
| `data\config.json` | Optional local override | Ignored |

Runtime files and folders are created when needed. Generated databases remain
local; the library already exceeds GitHub's regular-file size limit. Any explicit
database transfer needs suitable storage and closed SQLite connections; never
include WAL files or credentials.
Only the latest completed local log is kept. The application does not
automatically prune library history or delete raw data/backups.

## Validation and remaining work

The frozen-source final gate passed **760 Python tests and 51 JavaScript tests**,
Ruff lint/format over 90 Python files, strict mypy over 44 source files,
sdist/wheel builds and diff checks.

The actual provider-enabled, cache-backed clean rebuild completed as run 1
(2026-11-02 18:33:13–18:38:19 UTC; 5m06s). All three CSV imports completed:
610 StoryGraph Read, 813 watchlist and 730 Goodreads Read. All 1,054 StoryGraph
rows were archived, with 444 excluded from processing. Six raw-hash/row checks
passed. Analytics completed in parallel as report 1 with **219 findings**.
Repeat run 2 left all 2,153 records unchanged (zero additions/updates/removals),
reused both analytics caches and published report 2.

Both runs correctly returned `PARTIAL`/exit 3 solely for provider incompleteness,
not source-import or analytics failure. Open Library's rebuild requested 2,153
targets: 1,958 complete and 195 partial outcomes, 2,052 cache hits and 1,139
selected records. Google received one explicit daily-quota 429 and deferred
2,152 targets behind its persisted six-hour floor. Repeat made **zero new wire
requests to either provider**: cumulative counters stayed at Google 6/Open
Library 1,995. Open Library requested zero targets while still reporting
`metadata_coverage_incomplete`. **Full enrichment is not accepted.**

An isolated real-CSV acceptance run explicitly disabled providers and passed
source import, cached repeat, independent missing-Read failure with last-good
report retention, and recovery. That is source-only evidence, not fresh provider
coverage or complete account acquisition. Historical all-StoryGraph runs and
their counts remain labeled in PLAN.md.

The approved cleanup backed up all four databases at
`data\backups\before-clean-rebuild-20261102T183257Z` and removed only
raw/library/analytics databases. It retained `metadata.sqlite3`, provider
cache/retry gates, Google authorization and every original CSV byte. All four
databases passed integrity checks with zero foreign-key violations; all three
full CSV SHA hashes are unchanged. The rebuilt library contains 2,153 source
records, 1,570 works, 1,828 editions and 242 unresolved candidate links—not 242
bad books—and no reading events. Root config intentionally drops obsolete
`metadata.max_age_days`. New useful runtime databases stay local and ignored;
weekly operation remains disabled.

See [TODO.md](TODO.md) for next steps, [PLAN.md](PLAN.md) for detailed feature
requirements and historical evidence, and [CONTRIBUTING.md](CONTRIBUTING.md)
for development.
