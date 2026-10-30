# BookyStats

Local-first reading-data ingestion for Python 3.12+. BookyStats collects your
accounts into a persistent local library; it is not yet a statistics application.

See [the detailed product and delivery plan](PLAN.md) for the full five-phase
roadmap, statistical methods, recommendation design, both annual reviews, and
acceptance criteria. Its status note distinguishes implemented work from future
features and unresolved live-access requirements.

## What it does

- **StoryGraph:** collects reading history, personal ratings and reviews, rereads,
  and reading status from the owner's normal browser-accessible pages.
- **Goodreads:** collects the to-read/watchlist shelf using native RSS or normal
  browser pages. Goodreads is not the authority for your personal reading ratings.
- **Optional metadata:** Google Books enrichment with an API key; Open Library is
  available but disabled by default. Matching is conservative and retains source
  provenance rather than treating every candidate as the same book or edition.
- **Durable storage:** SQLite holds the authoritative local library, observations,
  reading events, and sync history. Metadata responses have a separate cache.
  Complete source snapshots publish independently and atomically; an incomplete
  source never replaces its last complete snapshot. Repeated ingestion is idempotent.

Collection does not use CSV/export workflows or silently fall back to exports.
Sign-in happens only in a visible, ordinary browser; there is no credential or
bot-protection bypass. Statistics, ranking, annual reviews, a website, an app, and
an HTTP API are **not implemented**. Real-account ingestion and scheduled operation
have not been live-verified; fixture and local-browser checks do not prove that a
particular account or current source layout will work.

## Windows PowerShell setup

From this repository's root, with Python 3.12 installed (or substitute your newer
Python version):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\booky.exe status
```

Invoke the virtual-environment executables directly: activation and execution-policy
changes are unnecessary. `.\.venv\Scripts\python.exe -m bookystats` is equivalent to
`.\.venv\Scripts\booky.exe`.

## First sync and subsequent runs

```powershell
.\.venv\Scripts\booky.exe sync --interactive
```

The reader profiles are built in: StoryGraph `byte_me`
(`https://app.thestorygraph.com/profile/byte_me`) and Goodreads `79839274`
(`https://www.goodreads.com/user/show/79839274`). Override either with
`BOOKYSTATS_STORYGRAPH_PROFILE` / `BOOKYSTATS_GOODREADS_PROFILE`, or with the
`accounts` list in `config.json`; an explicitly empty list prompts for profile URLs
during interactive setup. Use profile URLs, not book or shelf URLs. When
authentication is requested, sign in as the configured
owner in the browser window, never in the console or chat. Sessions are retained
in separate source/account browser profiles.

Run interactive setup from a terminal on your signed-in desktop. An automation
runner's browser window may not be visible in your desktop session. Later runs
reuse the saved session, but the source may expire it or require sign-in again.

```powershell
.\.venv\Scripts\booky.exe sync --unattended --json
.\.venv\Scripts\booky.exe status --json
```

The only public commands are `sync` and `status`:

| Option | Meaning |
| --- | --- |
| `--data-dir PATH` | Override the private local data directory. |
| `--json` | Print a structured receipt/status report. Prefer unattended sync for machine consumption. |
| `--interactive` | Allow visible browser sign-in. |
| `--unattended` | Never prompt or wait for sign-in; use an existing session where required. |

The two mode flags are mutually exclusive. Without either, sync is interactive
when attached to a terminal. `status` makes no source/provider requests; it reads
local data and, if registered, queries Windows Task Scheduler.

Inspect source and metadata results separately. Both account sources must complete
for `account_sync_complete` to be true. One configured source can publish its own
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
Unattempted and older attempts take priority so a failing book cannot monopolize
the budget. A provider cooldown defers further network lookups for that provider
in the current run rather than retrying immediately for every book.

## Optional weekly scheduling

Scheduling is Windows-only and **disabled by default**. Registration requires:

- Both StoryGraph and Goodreads configured.
- Two consecutive complete account runs for the same accounts and current Python
  implementation, with at least one unattended run.
- A latest receipt matching the database's latest run and no more than seven days old.
- An explicit weekday, time, and Windows time-zone ID matching the machine.

Keep `weekly.enabled` false while establishing those runs. Then edit the existing
`config.json`: set `weekly.enabled` to `true`, choose `weekly.weekday` (`MON` through
`SUN`) and `weekly.time` (`HH:mm`), and set `weekly.timezone` to the exact output of
`(Get-TimeZone).Id`. A subsequent ordinary `booky sync` attempts registration after
checking the current run and eligibility; setting the flag alone does not register
a task. Check `booky status` afterward.

Activation is bound to the implementation, accounts, Python interpreter, and schedule.
If any change, scheduled collection refuses to start until revalidated. An unchanged,
already-enabled task is not registered again on every manual sync.

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

- **Needs authentication:** rerun `sync --interactive` with the same data directory
  and correct owner. The login wait uses `browser_timeout_seconds` (default 45 seconds);
  if it expires, retry interactively.
- **Blocked source or changed layout:** inspect the receipt, stop rather than bypass
  protection, and retry only after the access/parser issue is resolved. No export
  fallback is available.
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
