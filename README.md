# BookyStats

Local-first reading-data ingestion for Python 3.12+. BookyStats collects your
accounts into a persistent local library; it is not yet a statistics application.

See the [architecture and detailed plan](PLAN.md#architecture) and
[delivery checklist](TODO.md). The current priority is manual CLI ingestion and
processing. Scheduled capture/auto-export comes next; analysis, ranking, and
annual reviews are later work.

## What it does

- **Raw capture:** archives supplied StoryGraph and Goodreads CSV files in SQLite
  before parsing. Original bytes and unmapped source columns are retained.
- **Processing:** normalizes reading history, ratings, reviews, dates, statuses,
  and book identities. All Goodreads export rows are retained, with watchlist
  membership derived from shelves. StoryGraph remains the reading-history authority.
- **Metadata:** Google Books with a key, Open Library without one, both, or neither.
  Matching is conservative and retains source provenance. New provider responses
  are archived before processing, separately from the disposable metadata cache.
  Unmapped provider fields remain in the raw archive; only validated catalog
  observations enter the processed metadata cache. No cover images are downloaded.
- **Durable storage:** SQLite holds the authoritative local library, observations,
  reading events, and sync history. Metadata responses have a separate cache.
  Complete source snapshots publish independently and atomically; an incomplete
  source never replaces its last complete snapshot. Repeated ingestion is idempotent,
  and processed snapshots retain raw-document and processing-version references.

Manual import requires no website login in BookyStats. A successfully processed
file is not proof of account ownership or full account coverage: exports may omit
fields. Unknown formats and missing data are reported rather than guessed.
Statistics, ranking, annual reviews, a website, an app, and an HTTP API are
**not implemented**. Real user exports still need reconciliation when supplied.

## Windows PowerShell setup

From this repository's root, with Python 3.12 installed (or substitute your newer
Python version):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\booky.exe status
```

Invoke the virtual-environment executables directly: activation and execution-policy
changes are unnecessary. `.\.venv\Scripts\python.exe -m bookystats` is equivalent to
`.\.venv\Scripts\booky.exe`.

## Import and reprocess

Download the official exports yourself, then supply their local paths:

```powershell
.\.venv\Scripts\booky.exe sync --storygraph-file "C:\Books\storygraph.csv" --goodreads-file "C:\Books\goodreads.csv" --metadata open-library
```

Both supplied files are archived before processing begins. You can supply one
new export at a time; the other source uses its latest archived file if available.
With no archived input, sync reports an error instead of contacting websites. Keep originals outside the
repository; they contain personal data.

The reader profiles are built in: StoryGraph `byte_me`
(`https://app.thestorygraph.com/profile/byte_me`) and Goodreads `79839274`
(`https://www.goodreads.com/user/show/79839274`). Override either with
`BOOKYSTATS_STORYGRAPH_PROFILE` / `BOOKYSTATS_GOODREADS_PROFILE`, or with the
`accounts` list in `config.json`. File arguments explicitly bind exports to these
configured accounts; the CSV itself does not independently prove their owner.
Use a separate data directory for a different reader.

Subsequent manual requests can process the saved exports without their original
file paths. Choose `none` for completely offline source processing, or a provider
to enrich the stored records:

```powershell
.\.venv\Scripts\booky.exe sync --metadata none --json
.\.venv\Scripts\booky.exe sync --metadata open-library --json
.\.venv\Scripts\booky.exe status --json
```

Provider selection applies to that invocation, not permanently to `config.json`.
Without `--metadata`, the configured defaults apply (Google Books enabled,
Open Library disabled). Selecting Google Books without a key reports
`not_configured`; it does not undo successful source processing.

The only public commands are `sync` and `status`:

| Option | Meaning |
| --- | --- |
| `--data-dir PATH` | Override the private local data directory. |
| `--json` | Print a structured receipt/status report. Prefer unattended sync for machine consumption. |
| `--storygraph-file PATH` | Archive and process a supplied StoryGraph CSV. |
| `--goodreads-file PATH` | Archive and process a supplied Goodreads CSV. |
| `--metadata none\|google-books\|open-library\|both` | Select enrichment, including a fully offline mode. |
| `--interactive` | Explicit opt-in to the earlier browser collector; not manual file processing. |
| `--unattended` | Do not prompt; plain sync still processes archived files, not fresh source data. |

Plain `sync` reprocesses stored files. File arguments cannot be mixed with
interactive or scheduled collection. `status` makes no source/provider requests;
it reads local data and, if registered, queries Windows Task Scheduler.

Inspect source and metadata results separately. Both account sources must complete
for a complete overall source result. Manual file processing always leaves
`account_sync_complete` false; it never creates scheduling evidence. One source can publish its own
snapshot, but the missing source keeps the overall run partial. Enabled metadata
that is unconfigured, failed, or deferred also makes the overall run partial without
undoing successful account ingestion. Sync exits `0` for complete, `3` for partial,
`4` for an existing sync lock, `1` for handled errors, and `130` for interruption.

## Configuration and private data

The default is `platformdirs.user_data_path("BookyStats", appauthor=False)`, normally
`%LOCALAPPDATA%\BookyStats` on Windows. `status` reports the resolved directory.
`--data-dir` takes precedence over `BOOKYSTATS_DATA_DIR`.

Within that directory:

- `config.json`: account and runtime settings; created by initial interactive setup.
- `raw.sqlite3`: original source exports and captured metadata responses, not a cache.
- `library.sqlite3`: the authoritative library, not a disposable cache.
- `metadata.sqlite3`: the separate metadata response cache.
- `profiles\<source>\<account-hash>`: persistent browser sessions.
- `stability.json` and `schedule.json`: scheduling evidence and registration receipt.

These stay outside the repository by default. Protect the directory and backups
with appropriate account permissions; do not commit databases, browser sessions,
profile URLs, or keys. Enabled metadata providers receive book lookup information.

| Environment variable | Purpose |
| --- | --- |
| `BOOKYSTATS_DATA_DIR` | Override the default data directory. |
| `BOOKYSTATS_STORYGRAPH_PROFILE` | Override the configured StoryGraph reader profile URL. |
| `BOOKYSTATS_GOODREADS_PROFILE` | Override the configured Goodreads reader profile URL. |
| `GOOGLE_BOOKS_API_KEY` | Supply the optional Google Books key locally. |

Profile environment overrides are not saved to `config.json`; `.env` files are not
automatically loaded. Prefer interactive setup for persisted account configuration.
Never paste API keys into chat, source files, or command history. A masked local
PowerShell prompt can supply a key for the current process and its children:

```powershell
$key = Read-Host "Google Books API key" -AsSecureString
$env:GOOGLE_BOOKS_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
Remove-Variable key
```

Google Books is enabled by default. A missing key is explicitly reported as
`not_configured`, not silently ignored. To run without metadata, merge this setting
into the existing `config.json`, preserving account and other settings:

```json
{
  "metadata": {
    "google_books": false,
    "open_library": false
  }
}
```

To opt into Open Library, set `metadata.open_library` to `true`. Metadata processing
is bounded by `metadata.max_books_per_run` (default 200); deferred work is reported
and subsequent syncs can continue it. `metadata.max_age_days` defaults to 30.
Google Books returns unprojected public volume records; Open Library uses its
documented `fields=*` search option. Full responses can be expensive, so existing
result/request limits, batching, cooldowns, and caching remain in force. This does
not mean downloading every edition in a provider's catalog or fetching cover images.
Unattempted and older attempts take priority so a failing book cannot monopolize
the budget. A provider cooldown defers further network lookups for that provider
in the current run rather than retrying immediately for every book.

## Later: automatic capture and weekly scheduling

This is **next in queue, not part of manual processing**. The earlier Windows
browser/scheduling code is retained, but live access is unresolved. Leave
`weekly.enabled` false; file imports and replay neither create stability evidence
nor register a task. The future automatic route must capture fresh data into the
raw archive before processing.

The retained activation gates require:

- Both StoryGraph and Goodreads configured.
- Two consecutive complete account runs for the same accounts and current Python
  implementation, with at least one unattended run.
- A latest receipt matching the database's latest run and no more than seven days old.
- An explicit weekday, time, and Windows time-zone ID matching the machine.

Activation is bound to the implementation, accounts, Python interpreter, and schedule.
If any change, scheduled collection refuses to start until revalidated. An unchanged,
already-enabled task must not be registered again on each run.

The task uses `InteractiveToken`: the Windows user must be signed in. It invokes
the installed Python environment, which must remain available. `$env:` values set
only in your current PowerShell session do **not** automatically reach Task
Scheduler; account configuration and any key must be available in the task's user
context. Browser sessions can expire or be rejected, so unattended source login is
not guaranteed. Scheduling has not been activated or verified against real accounts.

Setting `weekly.enabled` back to `false` makes scheduled invocations skip source
requests; it does not unregister the Windows task. Disable/remove the corresponding
`BookyStats-...` task in Windows Task Scheduler when retiring it.

## Recovery

- **Invalid export:** the raw bytes remain archived; supply a corrected export.
  Structural parsing failures do not replace the previous usable processed snapshot.
  Replaying a failed latest capture reports the failure again, not silent success.
- **Parser improvement:** run `sync --metadata none` to reprocess archived inputs
  without the original paths or any network requests.
- **Needs authentication:** rerun `sync --interactive` with the same data directory
  and correct owner. The login wait uses `browser_timeout_seconds` (default 45 seconds);
  if it expires, retry interactively.
- **Blocked source or changed layout:** inspect the receipt, stop rather than bypass
  protection, and retry only after the access/parser issue is resolved. There is
  no silent change of capture mode; manual exports must be explicitly supplied.
- **Partial collection or interruption:** retain `library.sqlite3`; the last complete
  snapshot for the affected source remains available. A healthy source may still
  have published independently. Rerun after correcting the reported issue.
- **Different account:** use a separate `--data-dir` and configure that account there.
  Each directory allows one account per source, and storage rejects silently
  replacing an already-bound account without blocking the other source. Do not
  copy sessions between owners.
- **Metadata cache failure:** account ingestion can still publish. Disabled providers
  do not open the cache; an enabled provider reports the cache error separately.
  Preserve `library.sqlite3` when repairing the separate metadata cache.
- **Overlapping sync:** let the active run finish before retrying; do not remove its
  lock while it is running.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and validation.
