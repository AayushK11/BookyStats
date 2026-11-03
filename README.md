# BookyStats

A local-first Python 3.12+ tool for understanding your reading library.
It imports Goodreads and StoryGraph CSVs, matches books, optionally enriches
catalog metadata, and saves evidence-backed analytics, watchlist recommendations
and a printable library report locally.

**CSV import, backend analytics, automatic metadata-quality diagnostics,
watchlist ranking and PDF reporting are implemented. A frontend, automatic
source collection, scheduling and annual reviews are not.**
Metadata coverage can remain partial; implemented prediction checks have not
established an improvement over their baselines.

## Start here

From the checkout in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\booky.exe status
.\.venv\Scripts\booky.exe sync
```

| Command | What it does | What it never does |
| --- | --- | --- |
| `booky status` | Shows configured CSV readiness, saved run state, analytics and verified report paths. JSON includes the full analytics report. | No network requests or recalculation. |
| `booky sync` | Archives configured CSVs, enriches metadata, calculates or reuses analytics, then generates quality diagnostics, recommendations and PDF/JSON reports. | No Goodreads/StoryGraph fetching, source browser, helper generation or scheduling. |
| `booky fetch` | Writes a manual Goodreads browser-console helper and prints configured shelf links. | No source requests, browser launch, input replacement or config changes. |

`python -m bookystats` also works. Bare `booky` shows help.
Runs exit after completing; there is no resident service.

Cloning restores the code, nonsecret root configuration and three fixed CSVs,
**not** local databases, metadata caches or credentials. On a new checkout,
`status` can correctly show no previous run until `sync` rebuilds the databases.
A fresh provider-enabled rebuild depends on authorization, availability and
quota; it need not reproduce an older provider snapshot exactly.

## Inputs and configuration

The editable checkout's default `data` directory uses root `config.json`.
Ignored `data\config.json` overrides it. An explicit different data directory
is isolated and needs its own configuration.

Select a directory with `--data-dir PATH` or `BOOKYSTATS_DATA_DIR`; the flag wins.
Non-editable installs otherwise use the platform's user-data directory.

Configuration is flat JSON with top-level `schema_version`, `accounts`, `files`,
`http_timeout_seconds`, `metadata` and `weekly`. Do not nest these under `settings`.
Root configuration versions the nonsecret ByteMe account identities; these are
profile references, not credentials. Other readers should use separate data
directories and their own accounts. Environment overrides are
`BOOKYSTATS_STORYGRAPH_PROFILE` and `BOOKYSTATS_GOODREADS_PROFILE`.

The supplied `files` section is:

```json
{
  "files": {
    "storygraph_file": "inputs\\storygraph-library_2026-11-02_08-27-54Z.csv",
    "goodreads_watchlist_file": "inputs\\goodreads-watchlist_2026-11-02_08-27-54Z.csv",
    "goodreads_read_file": "inputs\\goodreads-read_2026-11-02_08-58-33Z.csv"
  }
}
```

Paths resolve relative to the selected **data directory**, not the config file
or current working directory. Use `goodreads_file` instead of both split
Goodreads paths for an official whole-library export; never mix the modes.

| Supplied file | Archived rows | Active scope |
| --- | ---: | --- |
| StoryGraph library | 1,054 | 610 explicit Read rows; 603 personal ratings |
| Goodreads Read | 730 | Reading-library membership |
| Goodreads watchlist | 813 | Current to-read membership |

There are 2,597 archived rows and 2,153 active source records, **not** 2,153 unique
books. The 444 StoryGraph non-Read rows remain archived but are not matched or
enriched. Missing, empty or unknown StoryGraph Read Status fails its import scope.
Input filename timestamps are archive capture times, not proven export times.
The supplied CSV bytes and headers stay unchanged.

### Updating your library

Each configured CSV is a **complete collection snapshot**, not an append-only
list of new books. Keep the original and point the relevant configured path at
the next full snapshot for the same reader. A new snapshot replaces membership
in its scope; a new-books-only file would remove omitted memberships.

Each file is archived before parsing. A missing or invalid input fails only its
own scope; other healthy scopes can publish, and the failed scope retains its
last complete snapshot. Normal sync never substitutes an archived file for a
missing configured path. Metadata failure does not undo successful imports.
Normal sync does not delete user data or backups.

Advanced explicit file flags remain available:

```powershell
.\.venv\Scripts\booky.exe sync --storygraph-file "C:\Books\StoryGraph.csv" --goodreads-watchlist-file "C:\Books\Watchlist.csv" --goodreads-read-file "C:\Books\Read.csv"
```

Only explicit-file mode can replay archived inputs for omitted file arguments.

### Manual Goodreads capture

Run `booky fetch`, open the printed Read or to-read link in your normal browser,
and execute the generated `data\runtime\goodreads-export.txt` helper separately on each
shelf. It follows normal pagination sequentially and downloads a timestamped
CSV only after finishing. Account changes, blocks, malformed rows or unsafe
pagination stop capture without a partial download.

Keep the downloads and explicitly select their paths. StoryGraph still needs
its supplied export. The helper is fixture-tested; current live-site behavior
and complete account coverage have not been verified. It never bypasses browser
or source protections.

## What the analytics mean

Goodreads owns reading history, current watchlist and other personal fields.
StoryGraph supplies personal ratings and identity from explicit Read rows.
StoryGraph dates, reviews, statuses and other personal fields remain raw-only.
Provider community ratings never replace personal ratings.
Separately labeled **you versus Goodreads** comparisons are optional analytical
context; Goodreads scores do not train your preferences or watchlist ranking.

- **Reading profile:** analyzes all Read books, including unrated ones, using
  known metadata and explicit missingness.
- **Enjoyment:** compares confirmed personal ratings with support checks,
  adjusted effects and whole-work/connected-coauthor validation.
- **Content:** identifies description themes and six reading-appetite mentions
  with versioned rules and supporting quotes.
- **Watchlist:** describes composition, missingness and differences from Read.
  This descriptive analysis stays separate from the recommendation product below.

Read Your Color is [inspiration](https://readyourcolor.com/assessment), not a
reproduced assessment. Content mentions are not personality traits, official
scores or guessed colors; genres are not substitutes for description evidence.
An absent description is unknown, not evidence that a theme is absent.

### Reading appetites

The six supported dimensions are **wonder, surprise, intensity, meaning,
connection and clarity**. The report keeps three questions separate:

1. What do the available descriptions explicitly mention? Versioned rules
   produce overlapping content groups with quotes and public references.
2. How representative are books with linked personal ratings? Coverage and
   rated/unrated composition are reported before interpreting enjoyment.
3. Among sufficiently supported rated works with positive content evidence,
   how do current ratings differ? Associations and validation use known evidence
   and support gates, not unlabeled books as negative examples.

These are exploratory associations from incomplete catalog descriptions, not
validated whole-book labels or a psychological assessment. English lexical
rules can miss nuance and produce false positives. Thin or concentrated samples
remain unavailable; worse-than-baseline validation is retained rather than
hidden. Explicitly declared appetite labels remain separate from text-derived
evidence. The recommendation product must not present these mentions as an
official assessment or a calibrated probability of enjoyment.

Work first-publication year, edition publication year, reading dates and capture
timestamps are different facts. Available translations do not establish the
edition language or language actually read. Browser genre/series labels remain
unverified raw observations; normalized provider genres use exact versioned
aliases, retaining unmapped subjects as unknowns.

### Which dates can be used?

| Evidence in the supplied files | Coverage | Meaning |
| --- | --- | --- |
| Goodreads library-addition date | 730 Read and 813 watchlist records | Addition to the Goodreads library, not proof of reading or entry to the current shelf |
| Goodreads labeled completion dates | No trusted completion dates in the current supplied captures | Reading dates are not inferred from flattened row text or StoryGraph |
| Work/edition publication dates | Available for subsets | Catalog chronology, never personal reading history |
| Filename and observation timestamps | Capture provenance | When data was archived/observed, not when a book was read |

Unknown dates remain unknown. Current ratings grouped by a completion-date
cohort are **not historical ratings at that time**.

More linked ratings are not proof of more accurate matching or predictions.
Held-out errors must be compared with a training-only baseline on the same
cohort. Historical evaluated predictors did not establish predictive gains.

### View or export a saved report

After sync, open the PDF path printed in the terminal. The complete generated set
is under `data\reports\report-<id>\`: `library.pdf`, `analytics.json`,
`recommendations.json`, `metadata-quality.json` and a hash manifest.
`data\reports\latest.json` identifies the latest complete bundle.

All files in a bundle use the same pinned source/metadata manifest and as-of
timestamp. Files are staged together, verified and published before the latest
pointer changes. A failed stage retains the previous bundle; status explicitly
identifies a retained bundle when newer analytics exist. No report history,
input, database, credential or backup is automatically deleted.

The PDF is a reader-first portrait rather than a technical findings dump, with
a data-art cover, compact chapters, charts, rating tiers, Goodreads comparisons,
description-backed content evidence and watchlist context. It closes with
coverage and interpretation notes. Chapters are data-dependent; sparse evidence
is omitted rather than invented. The complete technical evidence, diagnostics
and full ranking remain in JSON. The layout targets 16–20 pages for a rich
library, not an inventory of every book or finding.

Embedded fonts provide portable glyph coverage, not universal script layout:
complex-script shaping and right-to-left layout are not enabled. The PDF
discloses those limits and displays unsupported glyphs as Unicode code points.

```powershell
$status = .\.venv\Scripts\booky.exe status --json | ConvertFrom-Json
$status.products.pdf_file
$status.products.recommendations_file
$status.products.metadata_quality_file
$status.analytics.taste.findings
$status.analytics.taste.capabilities
$status.analytics.taste.preferences
$status.analytics.watchlist.findings
$status.analytics.taste.findings | Where-Object metric_id -Like 'content.*'
$status.analytics.taste.findings | Where-Object metric_id -EQ 'read.completion_date_cohorts'
$status.analytics.watchlist.findings | Where-Object metric_id -EQ 'to-read.library_addition_profile'
.\.venv\Scripts\booky.exe status --json | Set-Content -Encoding utf8 .\data\status-report.json
```

This exports the full status object, with the report under `analytics`, without
PowerShell date coercion. It is an offline export, not another public command.
The generated JSON is local and ignored. Taste and watchlist components have separate semantic/as-of
caches; unchanged components are reused with current input references. Reports
pin source snapshots and selected identity-valid metadata. Failed analysis
retains the last successful report. Large uncached Read inputs use three worker
processes, with SQLite writes kept in the main process.

## Automatic recommendations and metadata quality

The configured CSVs are enough to run the pipeline without a correction queue,
selection command or report-export command. Ambiguous identities remain
unresolved; automation never means forcing a match or inventing missing facts.
Headless sync uses existing authorization only and never prompts.

The recommendation product ranks eligible current Goodreads watchlist works
using supported catalog/reading evidence. It keeps exclusions and insufficient
evidence explicit, explains reasons and missingness, and provides a varied
shortlist separately from the full deterministic ranking. Completed works and
uncertain overlaps with Read must not silently become recommendations.
Scores are transparent ordering heuristics, **not enjoyment probabilities or
proven recommendation accuracy**. Recommendation histories and immutable,
hash-verified caches live in `analytics.sqlite3`.

The quality report separates field coverage and unavailable states, selected
identity anchors, public-source provenance, cross-provider disagreements and
provider outcomes. It is an **automated consistency/coverage audit**, not a
measurement of factual accuracy against independently labeled books. Gaps stay
visible; neither a successful report nor zero pending requests proves complete
enrichment.

## Metadata, scale and provider limits

Google Books and Open Library are optional and enabled by default. Configuration
can disable either. Open Library needs no credentials. Google uses
`GOOGLE_BOOKS_API_KEY` first, otherwise local OAuth.

The default `metadata.strategy` is `open_library_first`: process Open Library,
then send Google only records still missing an identity-valid, nonempty public
description or a recognized genre family. These are deliberately bounded core
gaps; missing optional years, pages, series, languages or translations alone do
not trigger Google. Selected work metadata can be reused across confirmed active
work links, but not another record's edition facts.

Set `metadata.strategy` to `independent` to retain independent provider passes.
Google consent/provider initialization is deferred until due fallback targets
actually need it. Receipts distinguish `skipped_by_strategy`, `coverage_scope`,
`fallback_fields` and `fallback_unresolved`: a skipped lookup is not a successful
Google match or proof of complete metadata.

Successful cached public responses can be reused without age-only refetching,
including for new aliases, while retaining query compatibility, checksums,
original observation provenance and per-record identity validation. Open Library
also indexes verified cached work candidates across earlier queries, so an
equivalent canonical title/author can reuse existing evidence without another
request. Multiple plausible catalog works remain ambiguous; a narrower query
cache must not hide that ambiguity. Unique full-title/full-author matches can
select work-only public metadata without an ISBN, but never establish an edition
match or transfer edition facts.

Recognized genre aliases normalize exact catalog paths, including comma/slash
separators; this does not promote arbitrary subjects or browser labels to genres.
New Open Library work-detail requests target remaining description/genre gaps
and are capped at 40 per provider instance in a run. Cached details remain usable
after the cap; deferred books retain validated fields and visible retry state.
The cap bounds new work, not the number of books with complete metadata.

Open Library searches request the fields the adapter consumes rather than `fields=*`; the
complete returned response is still archived. Completed detail results are
checkpointed before the next record, retaining progress on interruption.

Interactive sync starts ordinary Google consent when needed. New machines need
local client credentials and visible consent, or an API key. Headless runs never
prompt. Optional environment variables are `GOOGLE_BOOKS_CLIENT_ID` and
`GOOGLE_BOOKS_CLIENT_SECRET`; `.env` files are not loaded automatically.
Enable the Books API and configure consent users. A Desktop OAuth client is
recommended; a Web client needs `http://127.0.0.1:8765/oauth2/callback`.
Tokens stay in ignored `data\credentials\google-books-oauth.json`. Never put credentials,
cookies or tokens in config, commits, fixtures, logs or chat.

The checkout's local limit is 10,000 books per provider per run; the package
default is 200. Neither overrides provider quota. Previous saved Google evidence
identified a 1,000-query daily project limit; its reset time was unknown.

Unchanged successful or deterministic partial/ambiguous/invalid attempts do not
refresh merely by age. New/changed identities, provider implementation changes,
never-attempted records and due transient retries can queue. Rating/status-only
changes do not invalidate metadata identity. Legacy `metadata.max_age_days`
loads compatibly but is ignored and omitted when saving.

Transient record retries wait at least six hours and honor longer durable
provider/host gates. Explicit structured Google daily-quota evidence also sets
at least a six-hour cooldown, not a promised reset. Generic quota errors do not
prove daily exhaustion. No due targets or no new requests does **not** mean full
coverage: parked partial outcomes stay visible.

### Would another catalog be better?

There is no demonstrated drop-in replacement yet. [Hardcover's API](https://docs.hardcover.app/api/getting-started/)
is the strongest future opt-in pilot: it supports GraphQL and currently documents
free-tier limits of 5,000 quota-counted top-level operations/day and 60/minute,
but requires a token and a representative identity/coverage benchmark. Aliases
and batching do not exempt top-level operations from its quota.
[Wikidata](https://www.wikidata.org/wiki/Wikidata:Data_access) can augment
identifiers and dates but is not a demonstrated replacement for descriptions
and genres. [Open Library dumps](https://openlibrary.org/developers/dumps) are a
legitimate bulk route; multi-GB indexing is disproportionate for this local
library. No new provider, credentials or bulk download is silently introduced.
Open Library's [API guidance](https://openlibrary.org/developers/api) favors
cached, low-volume requests and official dumps for genuine bulk workloads;
batching does not turn its public API into unlimited enrichment infrastructure.

The current changes reduce redundant work and improve recovery; they do not
promise a cheap full cold rebuild. Open Library remains sequential and paced.
Provider quality and coverage, not just request volume, determine whether an
alternative is actually better.

## Storage and operations

| Local path | Purpose |
| --- | --- |
| `data\inputs\` | Original configured CSV snapshots |
| `data\databases\raw.sqlite3` | Original CSV bytes and full provider responses with lineage |
| `data\databases\library.sqlite3` | Processed source snapshots, book/edition identities and run receipts |
| `data\databases\metadata.sqlite3` | Provider query cache, retry gates and wire counters |
| `data\databases\analytics.sqlite3` | Historical analytics/recommendation reports and immutable verified caches |
| `data\reports\` | Consistent PDF/JSON bundles and their atomic latest pointer |
| `data\logs\bookystats.log` | Append-only redacted progress, run outcomes and grouped diagnostic counts |
| `data\credentials\` | Private local Google authorization |
| `data\runtime\` | Sync lock and explicitly generated capture helper |
| `data\backups\` | Recovery copies; normal sync never deletes them |

Existing flat databases and Google credentials are recognized by offline status
without moving them. The next sync automatically organizes them under the sync
lock, checks SQLite integrity and checkpoints WAL before moving any database.
It preserves file contents, provider retry gates, reports and authorization;
conflicting locations fail explicitly instead of overwriting either file.
Interrupted file moves resume safely on the next sync. Nonsecret configuration
stays at its existing location, and CSV paths remain relative to `data`.

`booky status` opens databases read-only: it does not migrate, checkpoint or create
SQLite sidecars, and an older database shows as `upgrade_needed` until a sync
upgrades it. Before any schema upgrade the store takes a verified SQLite backup
under `data\backups\` and leaves the database unchanged if that backup or its
integrity check fails. Normal sync never drops historical tables or deletes backups.

SQLite may create `-wal` and `-shm` files alongside an active database. They hold
pending-checkpoint committed changes and coordination state, not spare copies.
Never delete or move them during use; SQLite normally cleans them up after its
last connection closes.

All runtime files above, credentials and generated report exports remain ignored.
Root `config.json` and the three supplied CSVs are versioned. Do not force-add
runtime databases; an explicit database transfer needs suitable storage and
closed connections, not WAL files or credentials.

| Exit code | Meaning |
| --- | --- |
| `0` | Success |
| `3` | Partial outcome or failed checks; inspect sources, metadata, analytics and report delivery separately |
| `4` | Overlapping sync |
| `1` | Handled error |
| `130` | Interrupted |

Scheduling remains disabled. Successful file imports do not prove complete
account acquisition or unattended access.

## Development and roadmap

[CONTRIBUTING.md](CONTRIBUTING.md) covers structure, literal policy and all
validation commands. [TODO.md](TODO.md) separates delivered work from remaining
tasks. [PLAN.md](PLAN.md) retains detailed requirements and historical acceptance
evidence; historical results are not a claim about this checkout's current data.
