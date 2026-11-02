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
supports it. StoryGraph supplies personal ratings and matching identity only;
its other fields stay raw-only. Community ratings never replace personal ratings.
Missing information is not zero, and uncertain book matches stay unresolved.
Browser-captured CSV genre/series labels are not verified catalog facts; their
original values stay in the archive and cannot drive analytics as trusted labels.

The accepted imports contain 2,597 source records. The library's works table also
retains history, so its row count is not a count of unique active books.
StoryGraph has 603 personal ratings. The verified current Read input has 730
works and 338 confirmed personal-rating links (46.3%), up from 314 before the
latest enrichment pass and 122 before the earlier matching upgrade.
This is linked-rating coverage, not a matching-accuracy score.
The supplied Read CSV has no usable dated reading events or personal reviews.
Importing every file row does not prove complete account coverage.

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
Current trusted Read coverage includes 461 descriptions, 291 genre/subject-known
works, 46 series-known works and 477 original-work publication years. Before the
latest pass these were 286, 9, 2 and 277 respectively. Quarantined CSV genre
labels do not count. Matched-edition language remains unknown for all Read works;
319 have work-level translation availability, which is not a language preference.
Quotes use a separate public book reference without
changing the original CSV observation's file lineage. Reported theme/hunger
counts are text mentions, not whole-book labels or reader traits.

The engine now checks predictions by leaving out one whole work at a time,
without training on that work. It compares MAE/RMSE with a training-only mean
baseline and reports fallback use. It also supports equal-volume yearly genre
breadth and like-for-like comparisons of current ratings grouped by actual
reading year. The supplied data has no reading dates, so those dated findings
still need observations. Unknown features never count as negative examples.
The corrected before/after comparison uses the same 314 unchanged ratings, 201
author components and identical five folds, with stable Goodreads-ID ordering.
The 24 new links are excluded from that accuracy comparison. Work-held-out MAE
worsened from 0.19820 to 0.20273 (baseline 0.20325). Author-blocked MAE worsened
from 0.20130 to 0.20613, now above its 0.20309 training-only baseline.
The resampled gain range [-0.007761, 0.001611] crosses zero and describes
stability, not a confidence interval. **Coverage improved; predictive accuracy
did not.** These retrospective errors are not future recommendation accuracy.

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
The package default is 200, with 30-day freshness.
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
| `data\metadata.sqlite3` | Replaceable metadata lookup cache | Ignored |
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

The latest integrated gate passed **695 Python tests and 51 JavaScript tests**,
Ruff lint/format over 87 Python files, strict mypy over 43 source files,
sdist/wheel builds and diff checks.
The approved reset removed old databases/runtime files, preserved the exact
CSV/root-config hashes and saved Google authorization, and rebuilt the environment.
New useful databases created by E2E are retained.

The actual guarded provider run 12 completed parallel analytics. Open Library
reported 2,333 completed outcomes across 2,561 targets, 2,250 candidates and no
deferred targets; field/identity issues remain explicitly partial.
There are 1,228 selected metadata references in the pinned inputs, all Open
Library, including 597 Read-origin references. Candidates are not selected
reference counts. Google returned HTTP 429 on its first lookup with an explicit
daily quota error; its actual reset time is unknown. **Full enrichment is not
accepted.** This run archived 1,618 Open Library responses, all HTTP 200.

Installed-CLI runs 8–11 passed parallel recalculation, unchanged repeat with both
caches reused, missing-Read-path failure with last-good report retention, and
recovery with both caches reused. Input/config hashes and latest archived source
bytes remain unchanged. The temporary override is removed: both providers are
enabled by root config, and weekly operation is disabled.

Final v5 runs 13–16 repeated these checks with the enriched input: parallel
recalculation, both caches reused on repeat, missing-Read failure retaining the
last report, and recovery with both caches reused. Final report 13 has 2,151
findings and 338/730 rated Read works. All 2,597 rows and original/raw source
bytes stayed unchanged. Providers were explicitly disabled for these checks;
actual fresh-provider evidence is the separate guarded run 12.

Offline replay is not fresh provider coverage. The earlier failure's HTTP
status and retry deadline remain unknown. Calculator
`analytics-v5-scoped-language-validation` now separates work translation
availability from matched-edition language in features and coverage.
The 24 newly rating-linked works passed 48 provider-proof checks with the same
Open Library work ID on both source records; no existing ratings changed or were
lost. This is evidence consistency, not independently measured match precision.

See [TODO.md](TODO.md) for next steps, [PLAN.md](PLAN.md) for detailed feature
requirements and historical evidence, and [CONTRIBUTING.md](CONTRIBUTING.md)
for development.
