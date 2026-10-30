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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\booky.exe status
```

`requirements.txt` pins the tested runtime versions and installs BookyStats itself
in editable mode; the allowed ranges live in `pyproject.toml`. Manual file imports
need nothing else. Only the optional browser collector also needs
`.\.venv\Scripts\python.exe -m playwright install chromium`.

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
With no archived input, sync reports an error instead of contacting websites. Keep the
downloaded CSVs outside the repository folder; their exact bytes are already archived
in `data\raw.sqlite3`.

## How to know it worked

Every sync ends with a **Checks** block, a **Result** line, and the path of its run log:

```text
Checks
  [ok]      storygraph raw copy: storygraph.csv was saved unchanged and matches the file you gave (fingerprint 4279558cf098, 181 bytes).
  [ok]      storygraph row counts: 1 rows in the file = 1 books processed = 1 books in the library.
  [ok]      goodreads raw copy: goodreads.csv was saved unchanged and matches the file you gave (fingerprint 32f629bb9de7, 145 bytes).
  [ok]      goodreads row counts: 1 rows in the file = 1 books processed = 1 books in the library.
Result: SUCCESS
Everything in the files was saved and checked.
Run log: ...\BookyStats\data\logs\2026-10-30_12-54-35Z_run1.log
```

1. **Raw copy:** the archived bytes are re-read and compared with the file you gave
   (sha256). A replay without file arguments reports which saved copy it reused.
2. **Row counts:** rows in the export = records processed = books now in the library.
3. **Result:** `SUCCESS` (all checks `[ok]`), `PARTIAL` (`[partial]`: a source export or
   metadata step is missing), or `FAILED` (`[FAILED]`: a file did not match or could
   not be processed). Anything other than `SUCCESS` exits with code `3`.
4. **Run log:** one file per sync in `data\logs`, named
   `<UTC time>_run<N>.log` (or `<UTC time>_failed.log` for a run that stopped with an
   error). It records the file names, sizes, sha256 fingerprints, every issue, and the
   same checks. Logs contain file names only, never full local paths, and keys are redacted.
5. **Afterwards:** `booky status` shows the data folder, database sizes, the latest log,
   the last run, and per-source counts without contacting any website.

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
undoing successful account ingestion. Sync exits `0` when the Result is `SUCCESS`,
`3` when it is `PARTIAL` or `FAILED`, `4` for an existing sync lock, `1` for handled
errors, and `130` for interruption.

## Configuration and private data

The default is the `data` folder in this checkout (`BookyStats\data`). Precedence:
`--data-dir`, then `BOOKYSTATS_DATA_DIR`, then the checkout `data` folder. A
non-editable install with no checkout falls back to
`platformdirs.user_data_path("BookyStats", appauthor=False)` (normally
`%LOCALAPPDATA%\BookyStats`). `status` reports the resolved folder.

Within that folder:

| Path | Contents | In git |
| --- | --- | --- |
| `raw.sqlite3` | Original source exports and captured metadata responses, not a cache. | Yes |
| `library.sqlite3` | The authoritative processed library, not a disposable cache. | Yes |
| `logs\*.log` | One log per sync. | Yes |
| `metadata.sqlite3` | The separate, rebuildable metadata response cache. | No |
| `config.json` | Account and runtime settings. | No |
| `profiles\<source>\<account-hash>` | Persistent browser sessions. | No |
| `stability.json`, `schedule.json`, `sync.lock` | Scheduling evidence, registration receipt, run lock. | No |

This repository is private, so the raw archive, library, and logs are committed
to keep the reading history versioned. After a successful import:

```powershell
git add data/raw.sqlite3 data/library.sqlite3 data/logs
git commit -m "Import reading exports"
```

Commit only after the sync has finished (no `library.sqlite3-wal` file next to it).
GitHub warns above 50 MB and rejects single files above 100 MB; `status` prints
both database sizes. Browser sessions, keys, and `config.json` are never committed.
Enabled metadata providers receive book lookup information.

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
