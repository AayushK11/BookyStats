# BookyStats

Delivery progress is tracked in [TODO.md](TODO.md).

## How to read this plan

[README.md](README.md) is the user guide and
[CONTRIBUTING.md](CONTRIBUTING.md) is the development guide. This document keeps
the detailed product requirements and dated evidence in one place. A requirement
below is not an implemented feature unless the current delivery record says so.

| Start here | Purpose |
| --- | --- |
| [Architecture](#architecture) | Current local-first pipeline, data boundaries and invariants |
| [Delivery scope](#delivery-scope) | Implemented versus deferred scope |
| [Recorded acceptance](#current-repair-acceptance-and-provider-gaps) | Historical code/data checks and known provider gaps |
| [Identity matching](#10-identity-matching) | Matching requirements and difficult cases |
| [Metadata](#14-metadata-enrichment-and-caching) | Provider, caching and large-library requirements |
| [Analytics](#phase-2--understand-the-data-and-build-the-statistical-engine) | Questions, supported evidence and statistical safeguards |
| [Reading appetites](#21-read-your-color-inspired-dimensions) | Read Your Color inspired scope, not an official assessment |
| [Watchlist ranking](#phase-3--rank-the-goodreads-watchlist) | Explainable recommendation requirements |
| [Annual reviews](#phase-4--her-year-in-review) | Deferred personal/public annual products |

Historical acceptance describes the environment and inputs at that time.
Runtime databases are not versioned; use offline `booky status` to establish
what actually exists in the current checkout.

## Production hardening — 2026-11-03

### Current implementation handoff — 2026-11-03

Matching/enrichment, analytics, storage, logging and the versioned reader-report
implementation are integrated on the local main branch. The integrated
code-level gate passed 1,199 Python tests, Ruff lint/format and strict mypy. The
owner stopped the clean-slate E2E and independent review before execution.
Consequently this integration has no fresh real-data coverage, accuracy,
repeat-run, migration or generated-report evidence. Earlier acceptance sections
below are dated historical records for prior code; they do not validate this
integration or describe its current output.

Current data boundary: StoryGraph provides personal ratings and matching
identity from explicit Read rows; its dates, reviews, statuses and other
personal fields remain raw-only. Goodreads remains authoritative for reading
history and watchlist. Do not treat stored report-8 counts as current results
from the integrated code.

The owner requested coordinated improvements to matching, metadata scalability,
backend analytics, reading-appetite analysis, available dates and documentation.
This section records the current scope; acceptance is recorded only after the
integrated code and real-CSV checks finish.

- **Matching:** improve correctness, not a target link count. Contradictory
  selected catalog identities must veto or reverse automatic ISBN links.
  Preserve human decisions, ambiguity and separate work/edition evidence.
- **Metadata:** Open Library first, with Google used for remaining declared
  core gaps: selected identity-valid public description or recognized genre
  family. Optional years/pages/series/languages/translations alone do not trigger
  fallback. Retain independent provider mode for explicit compatibility.
  Retain both enabled providers and the configured local budget,
  settled public evidence, durable gates and honest partial coverage. Investigate
  alternative catalogs without adding an unverified dependency or treating
  batching as a quota exemption.
- **Analytics:** connect description-backed appetite evidence with separately
  gated enjoyment analysis; disclose rating availability and use leakage-safe,
  same-cohort validation. Fix semantic-cache invalidation when analytical
  membership changes.
- **Dates:** use Goodreads library-addition dates for descriptive library age,
  never as reading or guaranteed shelf-entry dates. The owner explicitly
  authorized StoryGraph completion dates as supplemental evidence, retaining
  source lineage and precision and never overriding Goodreads dates. Other
  StoryGraph personal fields remain raw-only.
- **Presentation:** keep three commands and the existing modular architecture.
  Make offline status useful and root documentation readable. No frontend,
  ranking, annual review, source automation or scheduler is added here.

Alternative-provider decision: Hardcover is a future opt-in coverage pilot,
not an installed replacement. Its documented token/quota model still requires
a benchmark. Wikidata can augment structured identifiers/dates; official Open
Library dumps are a bulk option whose storage/indexing cost is disproportionate
for this library. See README for links and operational details.

### Hardening acceptance

- **Code:** 815 Python and 51 JavaScript tests passed; Ruff lint/format over 92
  Python files, strict mypy over 45 source files, sdist/wheel builds and diff
  checks passed. New coverage includes contradictory catalog/ISBN repairs,
  settled-cache reuse, streamed-prefix retention, fallback scope/auth, date
  authority/precision and immutable-cache repeat regressions.
- **Real supplied CSVs, providers explicitly disabled:** all 2,153 active source
  records imported; 730 Read works, 813 watchlist works, 577 linked ratings and
  278 usable descriptions remained the same as the source-only baseline.
  The upgraded report contains 180 findings and 406 usable supplemental dates
  from 423 explicit StoryGraph completion dates. Raw date totals, linked usable
  totals, missingness and origin are separate; no Goodreads event was invented.
- **Recovery:** the frozen-policy repeat reused taste and watchlist caches;
  missing configured Read input retained 730 prior records and report 3;
  restored configuration completed as report 4 with both caches reused.
- **Separate live catalog smoke:** a synthetic public-book fixture produced a
  selected Open Library lookup from real search/detail responses. Adding a
  confirmed cross-source alias and then repeating left durable wire attempts at
  2, 2 and 2. Google was disabled. This proves neither complete provider coverage
  nor real/unattended source collection.
- **Integrity:** seven isolated SQLite databases passed full integrity and
  foreign-key checks; all three original CSV SHA-256 hashes are unchanged.
  A source-only real-data report is exported to ignored
  `data\analytics-report.json`; default databases were not silently replaced.

The cold provider-enabled full-library rebuild was not repeated for this
acceptance. Sequential catalog requests, remaining missingness and provider
quotas still apply; Hardcover's actual identity-valid coverage needs a pilot.
Richer analytics and stronger correctness tests do not establish matching
accuracy, predictive improvement or recommendation accuracy.

## Automatic product delivery

The owner subsequently authorized watchlist recommendations, an automatic
metadata-quality audit, a comprehensive PDF library report and persistent
understandable logging. Processing uses the existing configured CSVs; automatic
Goodreads/StoryGraph acquisition and scheduling remain deferred.

The pipeline must run without human correction/selection queues. This means
abstaining on uncertain identities or insufficient evidence, not relaxing
matching checks. Quality reports quantify coverage, provenance and consistency;
no independently labeled factual-accuracy benchmark has been established.
Recommendations must disclose eligibility, ordering evidence, exclusions,
missingness and uncertainty; their scores are not enjoyment probabilities.

Successful analytics feeds all downstream products from the exact same pinned
input manifest and as-of timestamp. `data\reports\report-<id>` contains the PDF,
analytics/recommendation/quality JSON and a file-hash manifest. Publication of
`reports\latest.json` happens only after the entire bundle succeeds. Failures
retain the last complete bundle; corrupt or mismatched bundles fail explicitly.
Recommendation histories/caches share the strictly versioned analytics database.
`data\logs\bookystats.log` appends redacted stage progress and bounded examples
with complete grouped issue counts; sync never deletes older logs or reports.

The approved one-off cleanup removed generated/test artifacts, not implementation
files, original CSVs, configuration, credentials or provider retry state.
Current integrated validation and real provider-enabled acceptance are recorded
below only after execution; earlier source-only results remain historical.

### Automatic delivery validation

- The final integrated code gate passed 883 Python tests and 51 JavaScript tests,
  Ruff lint/format over 113 files, strict mypy over 57 source files and both
  package builds. The 69-file wheel and 136-file sdist include the console
  helper, packaged fonts and licenses, but exclude runtime data and credentials.
- A separate real-CSV acceptance explicitly disabled both metadata providers.
  Initial sync, unchanged repeat, missing configured Read failure and restored
  recovery behaved correctly. It retained 2,153 active source records across
  the 610/730/813 scopes, 730 Read works and 813 watchlist works. Source-only
  evidence ranked 110 works, abstained on 703 and produced a ten-item shortlist.
  Repeat/recovery reused both analytics components and recommendations.
- The failed Read scope did not replace its 730-record snapshot or the latest
  complete product bundle. Recovery published a coherent new bundle with exact
  matching manifests/as-of timestamps across all products. All three isolated
  databases passed full integrity and foreign-key checks.
- The source-only PDF had 111 pages and 166,541 extracted characters. Local
  raster inspection of pages 1/3/56/111 found readable tables and pagination;
  no extracted text baselines fell outside the page bounds. This is separate
  from provider-enabled PDF acceptance and complex-script rendering checks.
- The real default provider-enabled rebuild and relocated unchanged repeat
  completed source imports, analytics and products. Both overall receipts were
  honestly partial: Open Library had parked/incomplete outcomes, and Google's
  first request was rate-limited. No daily-exhaustion claim is supported.
- Default report 2 pins 730 Read works, 813 watchlist works, 574 linked
  unconflicted ratings and 230 findings. Its recommendations rank 318 works,
  shortlist ten and abstain on 495; ranked works were checked against Read,
  possible-Read overlaps, watchlist membership and known future publication.
  All products share exactly the saved manifest/as-of; both analytics components
  and recommendations reused on repeat.
- Durable catalog counters stayed **Open Library 1,521 -> 1,521** and
  **Google 1 -> 1**. Retry deadlines, failure counts and diagnostic codes stayed
  unchanged. Zero new catalog requests does not establish full enrichment.
- All four production databases passed full SQLite integrity and foreign-key
  checks. Original CSV hashes were unchanged. Physical reorganization preserved
  database and OAuth bytes exactly and did not clear retry state or history.
- The final `data\reports\report-2\library.pdf` has 150 pages and 239,763 extracted
  characters. Pages 1/3/76/150 were locally raster-inspected; no extracted text
  baselines were outside MediaBox. Font limitations explicitly disclose disabled
  complex-script shaping/RTL; correct extraction alone does not prove shaping.

### Organized runtime layout

The owner requested a cleaner data directory. Known runtime files now belong in
`databases`, private OAuth in `credentials`, and locks/generated capture helpers
in `runtime`; `inputs`, `reports` and `logs` retain their existing roles.
Nonsecret config and input path resolution are unchanged.

Offline status recognizes legacy flat files without moving them. Sync takes the
modern and any legacy lock, validates/checkpoints all legacy SQLite databases,
then atomically renames individual known files without overwriting destinations.
Partial moves are resumable. Existing-only status connections prevent a rename
race from creating an empty replacement database. The actual four databases and
OAuth file moved byte-for-byte only after the cold rebuild closed its handles.
The data root has no loose files; normal sync never deletes report/input history.

## Reader-first revision — 2026-11-03

The owner rejected the first PDF as too technical and requested a deep personal,
engaging report. The chosen presentation is roughly 12–20 pages, with complete
technical evidence in JSON and free/local metadata sources only. StoryGraph
remains the sole personal-rating authority. The owner explicitly allowed
separately labeled Goodreads community comparisons; they must never train
personal preferences or recommendation scoring.

The revision adds a typed reader summary and an editorial PDF: all-Read shelf
shape, favorites and rating vocabulary, community differences, returning authors,
supported genre/length comparisons, six description-backed appetites, actual
completion-date cohorts, watchlist familiarity/composition and a ten-item
shortlist. It does not reproduce an official assessment or infer personality.
The full inventory, diagnostics, prediction checks and ranking remain in JSON.
The supplied library's PDF is 15 pages rather than 150.
Final bundle `data\reports\report-8` passed text-baseline and per-glyph content
frame checks, with no footer overlap. Cover, appetite, shortlist and coverage
pages were raster-inspected; report history remains immutable.

Enrichment reuses verified Open Library candidates across canonical query
identities and normalizes exact catalog genre paths. Unique work-only
title/author matches may select public work facts without establishing an edition
match. Ambiguous catalog works remain unselected. New detail requests target
remaining core gaps and stop after 40 per provider instance; cached details
remain usable. Existing transient floors and host retry gates still win.

The real run exposed two compatibility/correctness regressions, now covered by
tests: historical recommendation caches must preserve their calculation version,
and weak unselected title-only catalog candidates must not veto an independent
reciprocal bibliography link. Strong ISBN ambiguity and selected catalog
conflicts still veto. An automatically withdrawn bibliography link may recover
only for the same unchanged pair with current compatible evidence and no human
override. All seven temporarily withdrawn personal-rating links recovered
automatically; the final total is again 574.

### Recorded second-pass acceptance

- 912 Python tests and 51 JavaScript tests passed, with Ruff lint/format over
  115 files, strict mypy over 58 source files and sdist/wheel builds. Package
  boundary checks covered a 70-file wheel and 138-file source archive.
- Sources retain 2,597 archived input rows and 2,153 active source records,
  including 730 Read and 813 watchlist works. All three original CSV hashes
  are unchanged. Personal rating evidence remains StoryGraph-only.
- Saved analytics contains 232 findings and 574 linked unconflicted ratings.
  The recommendation product ranks 359 works, shortlists ten and abstains on
  454; all ranked IDs passed current-watchlist, completed-work, possible-Read
  overlap and known-future-work checks. No independent usefulness gain is claimed.
- Recognized genres increased from 271 to 329 Read works and 248 to 297
  watchlist works: only 45.1% and 36.5% respectively. Descriptions increased
  to 535/730 and 609/813. Series remains 70/730 and 8/813; edition-language
  coverage remains zero. This is measured recovery, not complete enrichment.
- Provider-enabled source imports, analytics and products completed, but the
  overall receipt remains partial. Google's generic rate-limit cooldown was
  preserved; no daily-exhaustion or reset-time claim is supported.
- The unchanged repeat reused taste, watchlist and recommendation caches.
  Durable counters stayed Open Library 1,666 and Google 1: zero new provider
  requests. Both complete metadata coverage and catalog accuracy remain unproven.
- All four production databases passed full SQLite integrity/foreign-key checks.
  Product manifests/as-of timestamps, file hashes and saved reports agree.
  No original CSV, credential, old report or provider gate was reset.
- Separate provider-disabled real-CSV initial/repeat/failure/recovery checks
  passed. The failed Read scope retained its last complete bundle; recovery
  reused all caches. A final source-only repeat also passed under the final
  matching policy. This is separate evidence, not provider acceptance.
- Logging now appends compact stages, roughly five-percent progress updates,
  complete grouped issue counts and bounded redacted actionable examples.
  Expected import notices do not dump row examples or duplicate the full report.

The immediate remaining product problem is reliable metadata acquisition and
coverage evaluation, not more PDF pages. A genuine bulk/index route needs its
storage and coverage benchmark before adoption; the public API is not unlimited
bulk infrastructure. Independent matching and recommendation evaluation,
verified live acquisition, unattended evidence, backup/restore and any explicit
scheduling approval remain separate future work.

## Architecture

Exactly four named pipelines: **ingestion / processing / analytics / watchlist**.
Each command saves data to SQLite and exits; no always-running service or broker
is needed. Plain `booky sync` processes configured CSVs without source fetching
or a source browser. Analytics runs after metadata, followed by separate quality,
recommendation and PDF/JSON delivery services.
Live acquisition, retry/resume orchestration and scheduling are deferred, not
gates before analytics. Future triggers should reuse the same application
services. Do not activate Windows scheduling on this machine. Real-account
source acquisition and full provider coverage remain unproven.

```text
Manual command (future external triggers reuse the same application services)
    |
[ingestion: now]  <-- exact top-level files CSV paths; legacy explicit file flags
    | Goodreads Read + to-read; StoryGraph personal ratings
    | supplied file bytes archived before parsing: data\databases\raw.sqlite3
    v
[processing: now] <-- Google Books + Open Library enabled by default
    | provider query cache: data\databases\metadata.sqlite3
    | full provider HTTP responses: data\databases\raw.sqlite3 (separate source/type)
    | processed snapshots + payloads + run receipts: data\databases\library.sqlite3
    v
[analytics: now, backend only]
    | saved reports + separate taste/watchlist caches: data\databases\analytics.sqlite3
    v
[watchlist: now]
      rankings, eligibility, explanations + immutable caches: data\databases\analytics.sqlite3
      quality + analytics/recommendations JSON + PDF: data\reports\report-<id>\
      atomic verified latest pointer: data\reports\latest.json

Run log: data\logs\bookystats.log (append-only progress + grouped diagnostics)
Backups, when created: data\backups\
No automatic deletion of originals, raw data, library, or backups.
Logs and report history are retained; sync never automatically deletes them.
```

These are data boundaries, not separate servers. Metadata providers can be
disabled in configuration. Their full responses share `raw.sqlite3` with source
originals but stay separately identified; their lookup cache is a different
database. They never supply authoritative personal history or ratings.

Config is flat JSON: `schema_version`, `accounts`, `files`,
`http_timeout_seconds`, `metadata` and `weekly` are top-level fields. There is no
`settings` wrapper. Plain `booky sync` reads exact paths in `files`: `storygraph_file`,
`goodreads_watchlist_file`, `goodreads_read_file`, or alternative official
whole-library `goodreads_file`. Never mix whole-library and split Goodreads inputs.
Paths resolve relative to the selected **data directory**, not the config file's
location or cwd. Each file is archived before parsing; missing/invalid input fails
its own scope, healthy scopes publish independently, and failed scopes retain
their last complete snapshots. Normal sync never fetches Goodreads/StoryGraph,
starts a source browser, or substitutes archived inputs for missing paths.
Legacy explicit file flags remain advanced compatibility mode; only explicit
mode can replay unspecified archived inputs. Internal replay is not a freshness claim.

Each configured file represents its complete collection snapshot, not a
delta-only append patch. For a later export of the same reader, point the
configured path at the new full file. Membership publication replaces that
scope; providing only newly added books would remove omitted memberships.
Unchanged identities reuse provider outcomes. New/changed identities,
never-attempted records and due transient failures can queue; rating/status-only
changes do not invalidate provider metadata. Analytics independently applies its
semantic/as-of cache rules to changed ratings, membership and selected metadata.

Nonsecret root `config.json` versions ByteMe identities (StoryGraph `byte_me`,
Goodreads `79839274`) and settings. The editable checkout's default data directory
uses it automatically unless ignored `data\config.json` overrides it. Explicit
other data directories remain isolated. Profile identifiers are not passwords or
authenticated sessions. Local status shows the actual config path plus each CSV
filename and ready/missing state.

Three inputs were restored byte-exact from the immutable archive:
`data\inputs\storygraph-library_2026-11-02_08-27-54Z.csv` (1,054 records),
`data\inputs\goodreads-watchlist_2026-11-02_08-27-54Z.csv` (813), and
`data\inputs\goodreads-read_2026-11-02_08-58-33Z.csv` (730). Filename stamps are
original archive capture UTC times, not proven export-generation times.
These three CSVs and their structures are fixed. Do not edit them or require
replacement exports; improve processing and metadata against the existing inputs.

StoryGraph processing is scoped to the 610 explicit Read rows in its 1,054-row
file. The other 444 to-read rows remain in the immutable raw archive, not active
processed matching/enrichment inputs. Missing or unknown Read Status fails the
source scope and retains its previous snapshot. Status is used only to select
the StoryGraph import scope; it does not supply authoritative reading history.
Goodreads still owns the 730 Read and 813 watchlist memberships. Verification
reports total archived rows, excluded non-Read rows and active Read rows separately.

Sync detects a terminal and handles first-use Google client prompts/browser
consent automatically when needed, reusing an API key or valid/refreshed OAuth
where available. Advanced interaction overrides remain available; headless cron
never prompts and reports required authorization instead. Ordinary status stays
local. Archive hashes prove integrity, not full account coverage, and the current
implementation work is not evidence that live collection or consent succeeded.

| Pipeline | Responsibility | Stored output |
|---|---|---|
| **ingestion — now** | Exact configured CSV paths on plain sync; legacy explicit flags for advanced import/replay. Archive bytes before parsing; verify stored hashes, account/scope, and file completeness without claiming account completeness. Never silently replay missing configured paths. | Immutable source originals, source/account binding, capture time, content hash, and collection lineage. |
| **processing — now** | Parse, validate, apply authority, conservatively match identities, and enrich through default-enabled Google Books and Open Library with a separate query cache. | Independently published source/scope snapshots, structured books/editions, Goodreads history/reviews/watchlist, StoryGraph personal ratings, and metadata provenance/coverage. |
| **analytics — now** | Read pinned compatible snapshots, confirmed work IDs and selected identity-valid metadata after enrichment. Calculate supported findings; reuse taste/watchlist components separately. | Saved reports, preference weights, capability/coverage evidence and exact input references in ignored `data\analytics.sqlite3`. |
| **watchlist — now** | Conservatively filter the current Goodreads watchlist, use supported personal-rating signals and retain uncertainty/abstentions. | Deterministic ranking, varied shortlist, score components, evidence tiers and exact pinned inputs; no calibrated enjoyment probabilities. |

### Saved inputs, reuse and future orchestration

The analytics input reader pins an input manifest: the exact source snapshot IDs,
accounts, observation dates, original-data references, metadata coverage and
relevant data/code/config hashes. Reject missing required inputs or unacceptable
age differences. If an older or partial set is allowed, state its limits.
Never silently combine mismatched generations.

Reuse analysis and preference weights when relevant inputs are unchanged.
Watchlist-only changes must not repeat taste analysis. Keep prior results with
their original input list and freshness labels when new results are blocked.
Save checks and a run report for success, partial success or failure.

`domain.analytics` and pure `content_analysis` own calculations. The reusable `AnalyticsService` is injected
into `SyncService` after metadata. StoryGraph contributes ratings only; its
dates and other personal fields remain raw-only. Selected metadata must pass
identity checks and work links must be confirmed. Reused
components receive the current input references without changing cached values.
Selected public provider work metadata follows confirmed catalog-work links,
including StoryGraph-origin records. It never imports their raw personal/reader
fields or another record's edition facts. Alternative descriptions are chosen
deterministically with source evidence retained.

`AnalyticsStore` saves typed, hash-verified immutable component caches and
publishes historical reports atomically in ignored `data\analytics.sqlite3`
(schema v2). Taste and watchlist components have separate cache keys, including
the complete as-of date/year. An analytics
failure keeps the last successful report. Status reads that report offline:
JSON includes the full report and human output gives a summary.

Input-only `AnalysisEvidence.public_url` comes from the current Goodreads book
record's public URL, separately from immutable observation `source_url`/CSV
lineage. Content validates public source, scope and text before using that
reference. Its semantic cache key includes `description_provenance`: a public
reference change invalidates content; observation/capture time alone does not.

The current calculator version is `analytics-v6-conservative-genres`; the CSV parser
version is `csv-v5-storygraph-read-scope`. For at least 64 taste works, three worker
processes calculate profile, enjoyment and content; watch comparison follows
enjoyment. Only the main process writes SQLite. Small inputs run serially and
cache hits start no pool. Serial/parallel parity and failed-worker retention of
the last report are tested.

Validation also uses at most five deterministic size-balanced folds, keeping
transitively connected coauthors together. Unknown-author works do not supply
training or test evidence for this check. Both predictor and baseline fit only
training works and evaluate identical held-out works. A fixed-seed 500-draw
paired author-component resampling range requires at least 30 works and 10
components. It describes stability, not a confidence interval or future accuracy;
missing training/signal and fallback use are reported explicitly.

Metadata retrieval splits incomplete or contaminated query batches into
bounded narrower groups, retaining the existing individual identity/ambiguity
gates. Validated prefixes survive later deferrals. Goodreads Read records take
priority within a limited book budget. Provider/host retry deadlines,
interruption guards and wire counts are durable; raw schema v3 stores only safe
HTTP diagnostics alongside the unchanged body. Unknown legacy status/headers
remain unknown. Authentication, cookie and token data must never be archived.

Future retry/resume orchestration must:

- Save dependencies, attempts and task states: pending, running, success,
  partial, failed or skipped, with reasons.
- Use one reader/database lock; keep network work outside short write transactions.
- Publish validated scopes independently and retain last-good results on failure.
- Bound transient retries. Before resuming, verify accounts, code versions and
  saved outputs; restart unfinished work. Authentication/validation failures need
  correction. An interrupted transaction is not a published result.

This future engine is not required before analytics. File hashes and archive
replay prove neither fresh acquisition nor unattended account access.

### Storage growth, retention, and recovery

Keep the authoritative library, immutable raw archive, and disposable provider
query cache distinct. Source originals **and full provider HTTP responses** are
durable documents in `data\raw.sqlite3`, separated by source/type and lineage;
sharing that file does not make providers authoritative personal sources.
`data\metadata.sqlite3` is the separate, disposable query cache.

The compressed, content-addressed processed-payload migration is complete:
`data\library.sqlite3` shrank from 85,012,480 to 16,625,664 bytes
(81.1 to 15.9 MiB). Logical row hashes matched for all 20 legacy tables and
the raw archive was unchanged. The migration created an ignored backup at
`data\backups\library-v1-before-payloads.sqlite3`; the later one-off cleanup
approval includes ignored backups.

Completed replay run 4 reported all 1,054 StoryGraph rows and 813 Goodreads rows
unchanged. No new per-record payloads were added; only two new collection payloads
were added (2,680 to 2,682 total payloads). The library subsequently measured
20,606,976 bytes (about 19.7 MiB), reflecting legitimate observation/snapshot audit
growth rather than a repeat of per-record JSON duplication. Normalized
observations still grow; a bounded retention/compaction policy remains future
work, not permission to prune them recklessly.

| Artifact | Ownership and deletion behavior |
|---|---|
| Three supplied timestamped `data\inputs\*.csv` files | Restored byte-exact from the raw archive and intended versioned. The earlier bounded removal of duplicate downloads does not authorize deleting current configured inputs. |
| Root `config.json` | Versioned nonsecret ByteMe identities and settings, not credentials. |
| `data\raw.sqlite3` | Ignored durable original exports and complete provider HTTP responses. No automatic deletion. |
| `data\library.sqlite3` | Ignored processed snapshots, shared payloads, observations, original-data references and run reports. No automatic deletion or pruning. |
| `data\metadata.sqlite3` | Local/ignored provider query cache and durable retry state, not the response archive or library. No age-driven refresh or background purge; retain it during the approved rebuild. |
| `data\logs\*.log` | Local/ignored redacted reports; never commit logs. Group identical rendered issues with counts, keep the latest completed log and remove older generated logs only after writing its replacement. |
| `data\backups\` | Ignored recovery copies; included in the owner's separate one-off cleanup approval. Normal sync does not delete backups. |
| `data\analytics.sqlite3` | Ignored analytics reports and separate taste/watchlist caches, schema v2. Created when needed. |
| Future watchlist rankings | Not implemented; no ranking output store is created. |

Create runtime files/folders when needed. Version the three supplied timestamped
CSVs and nonsecret root config. All generated databases, logs, caches, profiles,
credentials and backups stay local/ignored; the library exceeds GitHub's regular-
file size limit. Never force-add runtime databases or commit logs.

The owner's separate empty-database reset and fresh E2E are tracked in TODO.md.
That reset is not normal sync or an automatic retention policy.

Future retention must be an explicit, reviewed archive/backup policy: identify
what can be reconstructed, preserve all referenced raw/payload lineage, define
retention windows and export/archive locations, and verify restore before any
pruning. Database backups must be SQLite-consistent and include the matching raw
archive, manifests, receipts, and required configuration/version references.
Protect local payloads, profiles, and credentials; logs contain references and
counts, not personal payloads or secrets. Do not delete raw data or automatically
prune history to conceal duplicate processed storage.

Implemented subset: status opens stores read-only and reports `upgrade_needed`;
each schema upgrade first writes a SQLite-API backup to
`data\backups\<UTC>-<store>-pre-migration\` with a SHA-256 manifest and refuses to
change the database if integrity or backup verification fails. This is not the
full retention/restore policy above.

### Data rules

- **Raw means original:** retain every supplied source field, including fields
  that today's parser does not understand. Retain full provider HTTP responses
  with provenance in `data\raw.sqlite3` as separate source/type documents before
  selecting fields. They are processing inputs, not Goodreads/StoryGraph exports;
  `data\metadata.sqlite3` is only their separate query cache.
- **Processing is replayable:** parser, cleansing, or matching improvements
  operate on the stored raw data without another account fetch.
- **Completeness is explicit:** importing every row of a file does not prove that
  the export contains every account field. Preserve missing, unsupported,
  conflicting, and failed values separately; confirmed empty is distinct from
  unavailable, unsupported, or failed. Preserve every supplied row/field raw.
  Never invent zeroes, dates, or personal history.
- **Keep provenance and authority:** Goodreads owns the current watchlist,
  reading history, reviews, status, and other personal data. StoryGraph contributes
  personal ratings and identity needed to match them. The owner-approved
  exception also permits explicit completion dates as supplemental evidence,
  retaining StoryGraph provenance/precision and requiring confirmed work links.
  They never override Goodreads dates or become Goodreads reading events.
  Other supplied fields
  remain raw-only. Never substitute community averages for personal ratings or
  merge editions on a title guess.
- **Publish safely:** retain the last usable processed snapshot when new input
  cannot be parsed or validated. Store failed-run evidence without publishing it.
  Publish Goodreads `to-read` and `read` independently; one scope must not erase
  the other.
- **Reuse derived work:** compare relevant input content and pipeline/configuration
  versions before recalculating. A changed watchlist can reuse unchanged taste
  weights; changed reading history invalidates affected analysis and rankings.
- **Read from the database:** viewing statistics or recommendations must not
  trigger fresh scraping or an unconditional analysis run.

### Delivery scope

**One command, one workflow:** `booky sync` processes the configured CSV paths,
with optional Google Books/Open Library enrichment enabled by current
package/local configuration. The local metadata budget is 10,000 books per run.
CSV ownership is configured, not independently verified by a file. No source
sign-in/browser, helper-generation, or separate metadata-mode command is required.

**Current position:** configured CSV processing and backend analytics are
implemented. Final queue/matching fixes passed the frozen-source gate: 760 Python
and 51 JavaScript tests, Ruff lint/format over 90 Python files, strict mypy over
44 source files, sdist/wheel builds and diff checks. The approved clean rebuild
and unchanged repeat passed source/analytics acceptance with 219 findings and
576/730 rating-linked Read works. Both runs correctly remain partial solely for
provider incompleteness. Provider enrichment remains
partial, including an explicit saved Google daily-project-quota rejection.
Source/browser automation code, dependencies, fixtures and unused shared
declarations were removed; the explicit manual console helper remains.
Source live acquisition, durable orchestration and external cron remain deferred.
No website, frontend, broker, resident pipeline service, images or local schedule
is requested. **Personal Year in Review and Calendar Year in Books remain deferred.**

This latest CSV-first decision supersedes the earlier browser-default direction.
Historical manual acceptance, migration, refactor and browser-fixture evidence
remain useful but do not replace current acceptance evidence below.
The detailed feature research below remains the reference for backend analytics,
later ranking, and deferred annual reviews.

## Automatic capture research

Historical research recorded on 2026-10-30. Live acquisition is now deferred;
these candidates are future requirements/research, not current CLI modes, proof
of live access, or silent fallbacks. Existing browser collection
attempts did not complete. The Goodreads RSS request already used the correct
numeric account ID and `shelf=to-read`; its HTTP 404 remains unexplained.

| Candidate | Evidence and limits | Next decision |
|---|---|---|
| **Goodreads official auto-export** | The library export is described by a [third-party guide](https://gist.github.com/kaayru/87385f85ec577b8e3d9613ecb09c90ca). It could feed the existing CSV processor unchanged. Download timing, session lifetime, frequency limits, and unattended operation have not been verified here. | A promising first candidate to validate against the owner's actual export flow; not a claim that a weekly job already works. |
| **StoryGraph official auto-export** | [Ryot's import guide](https://docs.ryot.io/importing/storygraph) and [Endleaf's guide](https://getendleaf.com/blog/how-to-export-your-storygraph-data/) describe export generation and email notification. These are third-party descriptions. Whether email access is essential, or an on-page link can be polled, remains unknown. | Inspect the manually supplied file and owner-visible flow before designing acquisition. Do not assume mailbox access or that login resolves the existing block. |
| **Goodreads native RSS** | A [third-party account](https://www.jordankatzen.com/posts/notes/goodreads-rss/) documents the feed mechanism. This is separate from the old developer API. This reader's feed failed; pagination and large-shelf completeness remain unverified. No fixed row cap is established by this research. | Compare accessible feed pages with known export counts before making RSS authoritative. Surface failures explicitly. |
| **Owner-authorized page capture** | Historical browser adapters parsed fixtures, but real-account acquisition was unresolved. Saved sessions can expire. An ordinary-browser visit does not explain another client's block. Unused adapters were removed. | A future implementation needs access/field-coverage checks; preserve source controls and report reauthentication needs. |
| **Historical manual browser helper** | The earlier user-run JavaScript generator is retired. Later Python collection was fixture-tested but is no longer the CLI default; unused scaffolding is not a retention goal. | Preserve acceptance evidence from supplied files without presenting retired helpers as unattended collectors or required setup steps. |
| **Official account API/OAuth** | StoryGraph's [API roadmap request](https://roadmap.thestorygraph.com/features/posts/an-api) remains the relevant public reference. Comments about export omissions are user testimony, not official field guarantees. Goodreads' [archived API page](https://web.archive.org/web/20210301235127/https://www.goodreads.com/api) describes historical access, not a new-app integration available today. | No usable public account-API integration was established. Do not treat private partner integrations or internal endpoints as an available public API. |

Before implementation, confirm the actual export schemas and owner-visible
download behavior, evaluate the applicable source terms (including
[Goodreads' terms](https://www.goodreads.com/about/terms)), and measure whether an
authorized session can complete repeat captures. Exact ownership, field coverage,
pagination, export readiness, and failure behavior matter more than a scraper's
feature list. No security-control evasion, credential extraction, remote sharing
of browser sessions, or silent fallback is part of this plan.

The earlier evaluation order favored official auto-export, then RSS or authorized
page capture; the subsequent browser-default direction is also superseded.
The current default is configured CSV processing. No acquisition route may
silently replace it, and missing configured paths must not trigger archive replay.
Only after a route and deployment host are reliable should an explicitly approved
external cron trigger invoke the shared workflow. Do not register a task on this
machine. Future acquisition must remain explicitly chosen rather than replacing
the current CSV contract implicitly.

## Status and later decisions — 2026-11-02

The detailed roadmap below preserves the earlier feature research, with intake
and delivery order revised to match the architecture above. It is **not a
statement that every capability exists or that real-account collection has
succeeded**.

| Phase | Current position |
|---|---|
| 1 — Collection and persistence | The fixed inputs contain 2,597 raw rows; current active scopes contain 610 StoryGraph Read, 730 Goodreads Read and 813 watchlist records (2,153 total). Final rebuild/repeat passed source acceptance, preserving metadata cache/retry gates, credentials and original CSV bytes. Earlier all-StoryGraph runs remain historical evidence. |
| 2 — Statistical engine | All-Read profile, enjoyment/content, descriptive watchlist comparison and three-worker calculations are implemented. The frozen-source 760-test gate passed. Clean run 1/report 1 calculated 219 findings; run 2/report 2 reused both caches. Current Read has 576 rating links, 529 descriptions and 552 original-work years. No ranking is implemented. |
| 3 — Watchlist recommendations | Planned; not implemented. |
| 4 — Personal Year in Review | Deferred; not implemented. |
| 5 — Calendar Year in Books | Deferred; not implemented. |

### Decisions made after this plan was written

- **Centralized literals:** every first-party Python string/byte literal, including
  tests, belongs in `src\bookystats\strings.py`; other fixed values belong in
  `src\bookystats\constants.py`. Keep modules and folders plain and modular.
  The repository instructions define the exact policy and type-syntax exceptions.
- **Revised source authority:** Goodreads is authoritative for the current
  watchlist and reading history/status/other personal data. StoryGraph supplies
  only personal ratings and matching identity, never processed reviews, statuses,
  dates, or rereads. This supersedes the earlier StoryGraph-history design.
- **Scoped manual inputs:** retain official whole-library `--goodreads-file`;
  use `--goodreads-watchlist-file` and `--goodreads-read-file` for supplied browser
  CSVs with `Goodreads_URL` and `Row_Details`. Archive scoped captures separately,
  migrate raw schema v1 to v2, and publish read/to-read snapshots independently.
  Validate labeled row metadata; do not infer personal assessments or reading
  dates from flattened UI text or trust script-derived `Series_Number`.
- **Configured reader profiles:** personal account IDs and URLs are configuration,
  not package defaults. Nonsecret root `config.json` versions the ByteMe accounts
  and settings for the editable checkout's default data directory; ignored local
  `data\config.json` overrides it. Other data directories stay isolated.
  Environment overrides remain available. These identifiers do not grant private access.
- **Current commands and output:** only `booky fetch`, `booky sync` and
  `booky status` are public commands. `fetch` generates the Goodreads console
  helper for explicit manual shelf capture; it makes no source requests or
  configuration changes. Terminal and JSON output exist. CSV reporting below is a future output
  idea, distinct from the now-approved manual export input.
- **Credentials:** the current Google Books connector reads its optional key from
  `GOOGLE_BOOKS_API_KEY`, not from `config.json`; an authorized OAuth session is
  reused/refreshed automatically during sync as fallback. Interactive sync handles
  first-use client prompts and normal browser consent; headless execution reports
  required authorization without prompting. New machines need local client
  credentials and visible consent (or an API key); credentials cannot be shipped
  in the repository. Any future source-browser sessions must remain local and
  isolated by source/account; current CSV operation needs no source browser.
- **Provider policy:** Google Books and Open Library are enabled by default;
  advanced configuration may disable either. Google uses an API key first, then
  valid/refreshed OAuth; local credentials are never committed.
  Both connectors are implemented.
  Hardcover, awards datasets, and other public-year sources below remain research
  or future integration options, not installed or verified dependencies.
- **Retained Windows scheduling code:** existing code remains disabled and
  unregistered; it is not the recommended deployment target. Its guards require
  both accounts, two consecutive complete account runs including an unattended
  run, consistent implementation/account fingerprints, recent evidence matching
  the database, and an explicitly chosen weekday, time, and Windows time zone.
  Activation also binds subsequent scheduled execution to the implementation,
  accounts, interpreter, and schedule. These retained guards do not establish an
  external cron deployment. The target is external cron invoking the same
  application workflow as a manual command; host deployment, equivalent safety
  gates, and unattended execution still need design/implementation verification.
- **Layered refactor:** the approved module layout in
  [The application structure](#3-the-application-structure) is implemented.
  Historical integrated evidence includes the earlier 658-test gate, followed by
  the 663-test gate, with Ruff lint/format, strict mypy and package build.
  Neither is a claim about the new CSV-default suite count or E2E.
  No old compatibility shims
  or empty future folders are retained.
- **Google Books OAuth:** the local implementation passed 84 focused tests and
  mypy/Ruff checks before the layered move. That is fixture/local implementation
  evidence, not completed human consent or live provider access. Integrated
  post-refactor validation passed at that point.

### Current repair acceptance and provider gaps

- The frozen-source final gate passed **760 Python and 51 JavaScript tests**,
  Ruff lint/format over 90 Python files, strict mypy over 44 source files,
  sdist/wheel builds and diff checks.
- Actual provider-enabled, cache-backed clean run 1 completed at
  2026-11-02 18:33:13–18:38:19 UTC (5m06s). All 610/813/730 source records
  added fresh; all 1,054 StoryGraph rows were archived, with 444 excluded.
  Six raw-hash/row checks passed. Parallel report 1 has 219 findings; repeat
  run 2/report 2 reused both caches with all 2,153 records unchanged and zero
  additions/updates/removals. Both runs correctly returned `PARTIAL`/exit 3
  solely for provider incompleteness, not source or analytics failure.
- Final Read coverage is 576/730 rating links (78.9%), compared with 338/730
  (46.3%) before repairs: +238 links, not matching accuracy. All 603 StoryGraph
  Read ratings remain preserved; 27 remain unlinked under catalog/subtitle/
  coauthor/ambiguity safeguards. Metadata covers 529 descriptions, 552 original-
  work years, 271 normalized-genre-known works, 70 series-known works, 722 page
  counts and 729 formats. Matched-edition language remains unknown for all works.
- Genres use `genre-families-v1`: 77 exact aliases across 25 families. Preserve
  provider subjects and unmapped unknowns; broad subject/marketing/classification
  labels are not automatically genres. This intentionally lowers coverage
  relative to the historical broad-subject counts below; the old 291 and new
  271 are not comparable coverage measures.
- Reversible reciprocal unique full-title/full-author work links use active
  records, discriminating series/volume/omnibus guards and selected-catalog
  conflict vetoes. Editions stay separate without shared validated ISBN
  evidence; synthetic record IDs are never bibliographic identifiers.
- Open Library's rebuild requested 2,153 targets: 1,958 complete and 195 partial
  outcomes, 2,052 cache hits and 1,139 selected records. Google received one
  daily-quota 429 and deferred 2,152 behind the persisted six-hour floor.
  Repeat made zero new wire requests to either provider: cumulative counters
  stayed at Google 6/Open Library 1,995. Open Library requested zero targets
  while still reporting `metadata_coverage_incomplete`; no gate was reset.
- The 576-work cohort's author-blocked MAE is 0.214046 versus its own training-
  only mean baseline 0.203587 (one fallback); leave-one-work-out MAE is 0.209932
  versus its own 0.203120 baseline. Neither establishes predictive gains; do
  not compare different cohorts as an accuracy improvement.
- Isolated real-CSV acceptance explicitly disabled providers and passed cached
  repeat, missing-Read failure/last-good retention and restored-config recovery.
  This proves neither fresh provider enrichment nor complete account acquisition.
- The approved cleanup backed up all four databases at
  `data\backups\before-clean-rebuild-20261102T183257Z` and removed only raw/
  library/analytics, retaining `metadata.sqlite3` cache/retry gates, credentials
  and every original CSV byte. All four databases passed integrity checks with
  zero foreign-key violations; all three full CSV SHA hashes are unchanged.
  Rebuilt library totals are 2,153 sources, 1,570 works, 1,828 editions and
  242 unresolved candidate links—not 242 bad books—with zero reading events.
  Root config intentionally removes obsolete `metadata.max_age_days`; the
  earlier recovery backup also remains retained. View/export the full saved
  report offline with README's `status --json` commands; generated reports
  remain ignored local files.

### Historical acceptance before Read-only/queue/matching repairs

The following all-StoryGraph runs used 1,054 active StoryGraph rows and 2,597
active source records. Those counts and their reports are historical, not the
current 610-row StoryGraph scope or 2,153 active-record population. They are
retained as recorded rather than retroactively rewritten.

**Historical code gate:** the full gate passed **695 pytest tests and 51
JavaScript tests**, Ruff lint/format over 87 Python files, strict mypy over 43
source files, sdist/wheel builds and diff checks.

The second-pass matching audit covered 1,024 pairs: 609 confirmed ISBN links
(270 exact and 339 normalized), plus 415 unresolved pairs, with a deterministic
review sample of 77. No safe recall relaxation was justified. This is
identifier/evidence consistency, not independently labelled matching precision.
An edition-observation freshness correction leaves all 2,597 actual identity
hashes unchanged.

Before the new provider pass, the 314-rated-work cohort formed 201 author
components (largest 14 works). Author-blocked MAE was 0.2034619353 versus
0.2037709036 for the training-only baseline; RMSE was 0.3684661653 versus
0.3701117527. Two of five folds had worse MAE, and the paired resampling gain
range [-0.0064641234, 0.0053374033] crossed zero. The roughly 0.15% MAE advantage
does not establish robust prediction. The input and metrics are saved locally
for an unchanged-cohort comparison after enrichment.

These are pre-correction metrics. A scope audit found that work-level available
translation languages were being promoted to matched-edition language features.
The saved baseline has no supported matched-edition languages; ten works have
work-language availability only. The v5 correction is integrated and both baseline
and final validation were recomputed under that same policy, as detailed below.

The guarded second-pass provider run 12 finished with complete parallel analytics
and partial metadata. Open Library reported 2,333 completed outcomes across
2,561 targets, 2,250 candidates and zero deferred targets. Its 1,618 archived
responses were all HTTP 200; invalid/ambiguous field or identity evidence remains
partial. Google returned HTTP 429 on its first request with an explicit daily
quota limit; its reset time is unknown. No quota controls were reset or bypassed.

The corrected v5 comparison pins 314 unchanged ratings and stable Goodreads IDs,
with identical 201 author components and five folds. There are 24 new links,
zero lost links and zero changed existing ratings. The new pairs share selected
Open Library work IDs, with 48 fresh, selected, lineage-valid provider proofs.
Their source titles/authors already agreed (10 exact, 14 structurally normalized),
but no pair shared a source ISBN. Editions remain separate. This is consistency
evidence, not independent matching precision.

Installed-CLI v5 acceptance passed: run 13/report 11 recalculated 2,151 findings
in parallel for 338/730 rated Read works; run 14 reused both caches. Missing-Read
run 15 completed the other two scopes and retained report 12. Recovery run 16
reused both caches and left final report 13. All 2,597 rows stayed unchanged.
Original CSV/root-config hashes and latest archived source bytes are identical;
saved authorization remains present and the temporary override is removed.
Providers were explicitly disabled for these replay/failure checks; actual
provider evidence is run 12. Root defaults enable both providers and keep weekly
operation disabled.

| Same-cohort error | Before enrichment | After enrichment | Training-only baseline |
|---|---:|---:|---:|
| Work-held-out MAE | 0.198203 | 0.202728 | 0.203252 |
| Work-held-out RMSE | 0.360597 | 0.361620 | 0.369090 |
| Author-blocked MAE | 0.201299 | 0.206135 | 0.203094 |
| Author-blocked RMSE | 0.366480 | 0.368907 | 0.369220 |

Both MAEs worsened. Author-blocked MAE now exceeds its baseline, with a
baseline-minus-predictor resampled gain range [-0.007761, 0.001611] crossing zero.
This range describes stability, not a confidence interval. These canonical v5
folds differ from older work-ID ordering; compare these two results only, not the
full 338-rated cohort against the former 314-rated cohort.

| Trusted Read coverage | Before | After |
|---|---:|---:|
| Read works | 730 | 730 |
| Personal-rating links | 314 | 338 |
| Descriptions | 286 | 461 |
| Genre/subject-known works | 9 | 291 |
| Series-known works | 2 | 46 |
| Matched-edition language | 0 | 0 |
| Work-language availability | 10 | 319 |
| Page counts | 722 | 722 |
| Original-work publication years | 277 | 477 |
| Edition publication years | 7 | 7 |
| Rating conflicts | 0 | 0 |
| Selected references, all pinned inputs | 19 | 1,228 |
| Selected references associated with Read origins | 11 | 597 |

Calculator `analytics-v5-scoped-language-validation` excludes work-language
availability from edition-language preferences/predictions while retaining its
evidence and separate coverage. The following details retain the earlier
acceptance baseline and historical pre-correction metrics.

The approved reset removed old databases, runtime files, environment, cache and
temporary files, preserving the exact three CSV/root-config hashes and saved
Google authorization. The environment was recreated. New useful databases
created by E2E are retained; the current data directory is not empty.

Fresh actual run 1 imported all 2,597 rows (1,054 StoryGraph, 813 watchlist,
730 Read) and completed parallel analytics with 400 findings and 314 rated Read
works. Finding counts are observations, not fixed targets.
That historical trusted Read input contained:

| Coverage | Works/observations |
|---|---:|
| Read works | 730 |
| Confirmed personal-rating links | 314 |
| Accepted description evidence | 286 |
| Missing description evidence | 444 |
| Trusted genre-known works | 9 |
| Page counts | 722 |
| Edition publication years | 7 |
| Original-work publication years | 277 |
| Supported matched-edition languages | 0 |
| Work-language availability | 10 |
| Conflicting personal ratings | 0 |
| Selected metadata references | 19 |

Raw quarantined browser genres are not trusted coverage. Content now accepts
all 286 descriptions using the separate public reference; file lineage remains
unchanged. Historical word-rule mention counts were relationships 19,
mystery/crime 5 and danger/adversity 5; hunger-content mentions are connection 9
and intensity 6. These are mentions, not complete book classifications, reader
traits, colors or official assessment scores.

Rating-linked coverage increased from 122 to 314 (+192), or 16.7% to 43.0%.
That is coverage, not a measured matching-accuracy percentage.
Held-out validation on the **same 314-work cohort** gave:

| Error | Model | Training-only mean baseline |
|---|---:|---:|
| MAE | 0.19845504492669255 | 0.20325186707637174 |
| RMSE | 0.36070751448382343 | 0.36908996676479056 |

MAE was lower by 0.004796822149679192 (2.36%). The older 122-work cohort is
different; this is not an apples-to-apples improvement over that older result,
a matching-accuracy estimate or future recommendation accuracy.

Provider coverage remains **partial**:

- Google Books hit `rate_limited` on its first lookup and deferred 2,596.
- Open Library persisted 140 outcomes, selected 19 records and deferred 2,457.
  One archived search reported `InternalServerError`, followed by 20 `http_error`
  record outcomes and process-local backoff. Nineteen work-detail URLs were validated.
  This does not prove Open Library quota exhaustion.
- Exact HTTP status, Retry-After/deadline and wire-request counts were not saved,
  so those historical details must remain unknown.

Installed-CLI offline acceptance used a temporary metadata-disabled config:
final run 8 recalculated in parallel with 400 findings and 314/730 rated Read
works; run 9 reported all 2,597 unchanged and reused both caches. Run 10 changed
only the configured Read path, failed that scope while StoryGraph/watchlist
completed, and retained report 8. Run 11 recovered all source scopes, reused both
caches and reported all 2,597 unchanged, leaving final report 9.
Inputs were never renamed or changed; original CSV/root-config hashes and each
latest raw source's bytes remain identical. The temporary `data\config.json`
override has been removed. Root defaults enable both providers and keep weekly
operation disabled. Those checks made no additional provider calls.
These checks accept source/analytics replay and retention, not complete enrichment.
The new durable retry/diagnostic implementation does not retrospectively
recover missing evidence or establish unattended collection reliability.

Metadata processing has a schema/version refresh to v3, narrow recovery of
otherwise verified fields when optional-field validation fails, and optional
confirmed-work details enabled by the CLI. Identity checks and truncation/
unverified/duplicate blockers remain. Archived network-disabled replay includes
multiple captures and is not normal-run coverage or accuracy evidence; no gain
from it is claimed. Confirmed provider-work reconciliation and alternate-edition
links are implemented; current actual coverage is recorded above.

**Earlier evidence:** deeper-math ownership tests passed 30 cases. After recreating
the virtual environment, the full integrated gate passed **535 tests**, Ruff
lint/format over 84 files, strict mypy over 41 source files, sdist/wheel builds
and diff checks.

Configured CSV acceptance passed all 2,597 rows and byte hashes, an unchanged
repeat and independent failure retention; local run 10 passed. An interim actual
analytics run reported 730 Read books, 122 confirmed personal-rating links
(about 16.7%), 603 StoryGraph rating records and 305 Read books with genres.
That genre count predates the stricter browser-label capture gate and is not
current verified genre coverage. Finding counts are dynamic, not an acceptance constant.

Bounded live metadata run 12 made 40 attempts per provider and selected 13 Google
Books and 6 Open Library results, with no provider-wide failures. Full run 13 was
stopped at the owner's request for a clean reset; full coverage is not accepted.
The requested cleanup is complete: all four databases and old ignored runtime
files were deleted, including the old virtual environment, profiles, backups and
logs. Google authorization was retained. The environment was recreated and
dependencies restored. Immediately before E2E, `data` contained only the inputs
and saved authorization; all three CSV SHA-256 values were unchanged and root
config was retained.

Installed `booky sync --unattended --json` finished from empty databases as run 1,
with the 10,000-book provider budget and no source browser. It exited 3:

- All 2,597 source records and six raw SHA/row-count checks passed.
- Analytics completed for 730 Read books and 122 confirmed personal ratings.
  It produced 569 findings in this run; that count is an observation, not a fixed target.
- Google Books hit `rate_limited` on its first lookup, then deferred 2,596.
- Open Library attempted all 2,597, completed 1,553, returned 2,245 candidates
  and used 295 cache hits, with zero deferred. Recorded issues included 109
  `invalid_metadata_field`, 60 `invalid_work`, 120 `search_truncated` and 979
  `unverified_candidates`; these are issue counts, not an additive book total.

That run's provider coverage was **partial**, not accepted as complete. The
subsequent archive-only diagnosis checked provider gaps versus parser bugs without
network requests. Replay checks used a temporary metadata-disabled override to
avoid further Google requests; these are separate from fresh provider acceptance.
That historical run was followed by the approved reset and latest acceptance
recorded above; it is not the final run's provider coverage.

**Historical evidence:** the bounded unattended live CLI diagnostic on
2026-11-02 (run 9) was **partial**:
all three collection attempts encountered source challenges. Existing counts
remained 730 Goodreads Read, 813 watchlist and 1,054 StoryGraph rows. One Google
lookup reported `invalid_metadata_field`; one Open Library lookup completed.
An OAuth credential file existed during that probe, but neither a saved file nor
a completed lookup proves complete metadata coverage. The 10,000-book budget was saved;
diagnostic limits were applied in memory only.

Separately, the earlier installed-executable export-processing E2E rebuilt all
2,597 records in isolated storage with raw-byte verification and metadata
disabled. The prior full gate passed 663 tests, Ruff lint/format, strict mypy and
package build. That 663-test gate is historical, not the current suite count.
Source-only tests explicitly disable enrichment and cannot prove full provider coverage.
That implementation closed source contexts before enrichment and saved verified
sequential metadata results per book. These historical checks do not require
retaining now-unused source/browser code.

**Deferred acquisition research:** future work may investigate official exports
through the owner's ordinary signed-in browser, with explicit human-action
states. This is not the selected next pipeline. Do not equate personal Edge
authentication with a separate application's isolated
Chromium profiles, copy cookies, attach to personal profiles implicitly, bypass
challenges, or silently replay stale files.
The [Goodreads export guide](https://gist.github.com/kaayru/87385f85ec577b8e3d9613ecb09c90ca)
describes `review/import`, asynchronous generation and a generated CSV link.
The [StoryGraph guide](https://getendleaf.com/blog/how-to-export-your-storygraph-data/)
describes Manage Account -> Manage Your Data -> Export StoryGraph Library.
These are third-party descriptions, not verified account/API contracts.
Comments on the [StoryGraph API roadmap](https://roadmap.thestorygraph.com/features/posts/an-api)
also describe manual emailed exports, conflicting with direct-download guidance.
Public access to the app export page returned 403; the current signed-in UI,
delivery timing and unattended feasibility remain unverified. No official export
adapter is implemented or claimed working.

Offline manual acceptance on 2026-11-02 succeeded (run 2), archiving both originals
and publishing 813 Goodreads watchlist books and 603 personal ratings from 1,054
StoryGraph rows. No StoryGraph reading events or other personal facts were
published. Three invalid StoryGraph ISBNs were reported and retained raw-only:
ratings survived, but those identifiers were not used for matching.

The watchlist yielded 665 valid ISBN identities; all 813 books had community
ratings/counts and dates added. Coverage included 812 formats, 806 positive page
counts, 515 descriptions and genre sets, 261 series labels, 498 first-publication
dates, and 16 edition-publication dates. No language values were present.
These are observed file-processing results, not independently verified account
completeness. Replay run 4 subsequently reported all 1,054 StoryGraph rows and
813 Goodreads rows unchanged; remaining final cross-cutting checks are tracked
separately. The verified migration and storage measurements are recorded above.
Run 5 then completed the supplied Goodreads Read import: 730 Read books were
added; all 813 watchlist books and 1,054 StoryGraph rows were unchanged. Read and
watchlist membership overlap was zero. There were 2,597 active source records;
the works table then had 2,469 rows, including retained history. That table count
is not a count of unique active books and may differ after a clean rebuild.
These are stored-import observations, not a
verified complete live-account collection.

All 730 Read memberships are authoritative. Of the 603 StoryGraph personal
ratings, 122 were conservatively linked to Read books; the other 608 Read books
remain without a confirmed personal-rating link, whether unrated or ambiguous.
No speculative matches were made. Read coverage includes 493 valid ISBNs,
722 page counts, 278 descriptions/genre sets, and community ratings for all 730.
The original flattened CSV supplied no usable dated reading events or personal
reviews, so both counts remain zero: Read membership is not a dated completion
event, and community ratings are not personal ratings.

Automatic collection has not succeeded against the configured accounts.
StoryGraph blocked the attempted collection. The anonymous Goodreads RSS request
for `79839274` returned HTTP 404; the browser path reached sign-in, but its window
was not visible to the user in the automation runner and collection did not finish.
This does not establish that all Goodreads feeds are unavailable, that this
profile is private, or that signing in will resolve StoryGraph's block.

Anonymous collection can only use genuinely public, accessible data. A saved
owner session may support later unattended runs, but it can expire or be rejected.
Neither route may claim a complete account snapshot without evidence. Manual
exports are now the configured default input route, not a hidden fallback.
No access-control workaround is permitted.

The historical manual import, unchanged replay run 4, and Read acceptance run 5
have succeeded. Current configured CSV/source/analytics acceptance and offline
follow-up checks have also passed; complete provider enrichment remains open.
Authorized repeat/unattended source collection remains a future gate only.
Fixtures cannot substitute for that evidence. External links below preserve the
planning research references; their continued availability and suitability must
be checked before relying on them.

The earlier guarded Goodreads browser seam covered only `to-read`; it did not
provide raw HTML recording or complete two-shelf acquisition. Python raw-first
collectors for `read`/`to-read` and StoryGraph ratings replaced that limited
route and the manual JavaScript generator in the earlier fixture-tested
browser-default contract, now superseded by configured CSV sync. Those unused
adapters, browser dependencies and fixtures have been removed. Historical
fixtures do not establish live completeness or unattended authentication.
The old script's capped pagination and flattened personal fields
remain historical limitations of those supplied files.

Use [README.md](README.md) for current operation,
[CONTRIBUTING.md](CONTRIBUTING.md) for development, and
[repository instructions](.github/copilot-instructions.md) for implementation
rules. The remainder preserves the agreed detailed roadmap.

---

**Current intake is exact configured CSV paths on plain sync.** Legacy explicit
file flags remain advanced compatibility mode. Processing is followed by the
implemented backend analytics pipeline; watchlist ranking comes later. Live
fetching is a deferred requirement, not a runtime dependency. Read the retained
roadmap below with this current contract; historical evidence remains labeled.

The five phases remain:

```text
Fetch and persist data
        ↓
Understand the data and generate statistics
        ↓
Recommend from her Goodreads watchlist
        ↓
Produce her Year in Review
        ↓
Produce a standalone Calendar Year in Books
```

## 1. Decisions we have settled

| Area | Decision |
|---|---|
| Language | **Python**, primarily for the statistical and recommendation work |
| Initial interface | Exactly **`booky fetch`**, **`booky sync`** and **`booky status`** |
| Database | **SQLite**, persisted across runs |
| StoryGraph access | Configured supplied CSV for personal ratings/identity; live acquisition deferred |
| Goodreads access | Explicit console helper via `fetch`; configured split Read/to-read CSVs or alternative official whole-library CSV; never mix the modes |
| Source authority | Goodreads watchlist/history; StoryGraph ratings and matching identity only; other StoryGraph fields remain raw-only |
| Metadata | Google Books and Open Library enabled by default; API-key priority, automatic interactive OAuth setup when needed |
| Exports | Default configured input; preserve original bytes before parsing, never silently replay missing paths |
| Refresh cadence | On-demand CSV processing now; weekly automatic acquisition requires later approval and evidence |
| Normal reads | Use the database, not fresh scraping |
| Future clients | Website and app call an API built over the same application services |
| Current presentation | Terminal and JSON output; CSV is input, reporting is future work |
| External writes | None: no changing ratings, shelves, reviews, or watchlist membership |
| AI dependency | None required for initial ingestion or core statistics |

The website and app influence how we structure the code, but they do not justify building a web server, authentication system, or multi-user infrastructure now.

---

# Phase 1 — Direct collection, persistence, and reliable synchronization

## 2. What Phase 1 must achieve

The first usable version should:

- Connect to the correct StoryGraph and Goodreads accounts.
- Retrieve all accessible records within the agreed account scope.
- Capture StoryGraph personal ratings, never confuse them with community data.
- Preserve Goodreads personal data, reading dates, and rereads only where explicitly represented.
- Identify the same book across services.
- Save everything useful in SQLite.
- Fetch missing book metadata.
- Detect changes on subsequent runs.
- Explain incomplete collection or unavailable fields.
- Eventually run weekly without needing routine intervention.

**Configured CSV ingestion, analytics and offline follow-up checks are accepted;
complete provider enrichment remains open.**
The direct/live collection requirements in this phase are retained future work,
not the current command contract or prerequisites for implemented backend analytics.
Historical real-export acceptance does not replace current provider/follow-up checks.

A library list containing book names is not enough. We need to establish access to the actual information the later phases depend on.

---

## 3. The application structure

The [architecture diagram](#architecture) is the authoritative stage layout.
Keep capture, raw storage, processing/enrichment, processed storage, analysis,
and ranking separate. Local execution can orchestrate these stages without a
message broker or separate hosted services.

The important boundary is between **application logic** and **how it is invoked**.

The CLI should not contain the synchronization or statistical logic. A future API should call the same services, not run shell commands and parse their printed output.

### Layered package layout

The package root is `src\bookystats`. The following fully qualified module paths
describe the implemented layered structure. Unused source/browser code was removed:

| Area | Modules and responsibility |
|---|---|
| Root | `bookystats.__init__`, `bookystats.__main__`, `bookystats.strings`, `bookystats.constants`: entry points and the existing centralized literal/policy declarations. |
| CLI | `bookystats.cli.commands`, `bookystats.cli.report`: parsing/wiring, rendering, and exit codes. |
| Application | `bookystats.application.sync`, `bookystats.application.verification`, plus the injected `AnalyticsService`: reusable sync, checks and report calculation/reuse. |
| Domain | `bookystats.domain.models`, `bookystats.domain.interfaces`, `bookystats.domain.errors`, `bookystats.domain.dates`, `bookystats.domain.identifiers`, `bookystats.domain.matching`, `bookystats.domain.analytics`: contracts, dates, identity policy and pure analytics calculations. |
| Metadata adapters | `bookystats.adapters.metadata` owns catalog lookups. Historical source/browser modules and dependencies were removed. |
| Export adapters | `bookystats.adapters.exports.csv_import` owns the default configured CSV path and legacy explicit file flags. |
| Transport/auth adapters | `bookystats.adapters.http` (formerly net), `bookystats.adapters.google_oauth`: bounded HTTP and explicit local consent/token handling. No source-browser runtime dependency for CSV processing. |
| Persistence | `bookystats.persistence.library`, `bookystats.persistence.raw`, `bookystats.persistence.payloads`, `bookystats.persistence.cache`, plus the analytics input reader and `AnalyticsStore`: library, originals, shared payloads, provider cache and saved analytics. |
| Runtime | `bookystats.runtime.config`, `bookystats.runtime.locking`, `bookystats.runtime.scheduling`, `bookystats.runtime.runlog`, `bookystats.runtime.redaction`: local lifecycle, disabled scheduling, logs, and privacy. |

Tests mirror implemented areas; shared `tests\conftest.py` and
`tests\test_literal_policy.py` remain global, source fixture data stays in
`tests\fixtures`, and shared builders live in `tests\support`. Remove builders
and fixtures used only by deleted adapters rather than preserving dead scaffolding. CLI command tests
are in `tests\cli\test_commands.py`; integration tests are in
`tests\application\test_integration.py`. The console target is
`bookystats.cli.commands:main`. Do not retain old flat-module
compatibility shims, move literals out of the root shared modules, or create
empty watchlist/future folders.

`bookystats.runtime.runlog` accepts injected, rendered report lines; it does not
import CLI reporting. CLI concerns stay out of application/domain/persistence
logic. The existing public commands and persistence semantics must survive the
move; final validation requires targeted and cross-cutting checks
as documented in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 4. Source connectors

### StoryGraph

**Plain-sync input:** the configured supplied CSV, archived before parsing.
Advanced explicit file import remains available. Normal sync does not access
StoryGraph. Live acquisition is deferred and unverified.

The processed contract is deliberately narrow: book identity and her personal
rating only. Reviews, reading history, dates, status, rereads, moods, pace, and
other attributes in the export stay in the original raw payload and do not become
processed facts. A row is not a reading event merely because it appears here.

The [existing StoryGraph scraper reference](https://github.com/Tzahi12345/storygraph-api)
may inform identity/rating acquisition, but does not establish authorized
access or alter this authority policy. Extraction must distinguish:

- Her personal rating from the community average.
- A work from a particular edition.
- An unrated book from a rating that could not be retrieved.

Manual files and automatic collection are explicit modes. An automatic run must
not pretend an old export is fresh account data or silently change intake modes.

### Goodreads

Plain sync reads configured `goodreads_watchlist_file` (`to-read`) and
`goodreads_read_file` (`read`) CSVs. Alternatively configure `goodreads_file`
for a supplied official whole-library CSV; derive membership from its shelves.
Never mix whole-library and split inputs. Legacy flags `--goodreads-file`,
`--goodreads-watchlist-file`, and `--goodreads-read-file` remain advanced explicit
mode. Preserve all rows/columns, retain separate raw captures and
independently atomic snapshots. The supplied watchlist is the current watchlist;
Goodreads Read is authoritative history, not StoryGraph's export.

Validated labeled `Row_Details` can supply ISBN, pages, community rating/counts,
date added, and format. Do not infer personal ratings, reviews, or reading-event
dates from flattened UI text. The `booky-goodreads-shelf-v1` contract does not
establish verified genre/series capture. Nonempty browser genre/series labels
become `UNAVAILABLE` as canonical facts, with verbatim raw observations
`unverified_capture_genres`, `unverified_capture_series` and
`unverified_capture_series_number`, plus `unverified_browser_capture` issues.
Empty/absent fields retain `EMPTY`/`UNSUPPORTED` states. Trusted selected metadata
may supply labels separately; the browser helper's version alone cannot.
No new domain state is needed, and no covers are downloaded.

Historical alternatives include a paginated shelf feed when accessible and
complete. The [Goodreads RSS client](https://github.com/icco/goodreads)
demonstrates such a public-shelf route, but the current default is configured
CSV processing; RSS is not a silent fallback and its real-account
behavior remains unverified.

The connector should collect:

- Goodreads book identifier and link.
- Title and authors.
- ISBNs when present.
- Watchlist membership.
- Recorded date added.
- Custom shelves.
- Shelf ordering, if accessible.
- Available edition metadata.
- Reading status and other personal history only where the input explicitly
  represents it; a read-shelf observation alone supplies no reading-event date.

Her profile should not have to become public. A private profile needs an appropriate authenticated route.

### Shared connector rule

A connector must return more than records. It must also report:

- Which account it accessed.
- Which collection it traversed.
- Whether pagination ended normally.
- Whether any pages or records failed.
- Which fields it supports.
- Which values were unavailable.
- When collection started and finished.

“Received some books” is not equivalent to “successfully synchronized the library.”

---

## 5. Configuration, optional enrichment auth, and future source authentication

The current CSV path binds files to configured accounts; a file does not
independently prove ownership. No source session or browser is needed.
The source setup steps below are deferred live-acquisition requirements, not
instructions for current CSV sync.

### StoryGraph setup

- Open a dedicated BookyStats browser session.
- Let the account owner sign in normally.
- Verify that the authenticated account is the intended one.
- Store the session locally for reuse.
- Discover the accessible identity and personal-rating surfaces only.

### Goodreads setup

- Record the correct reader profile identifier.
- Check whether the required shelf feed is accessible.
- Use an authenticated browser session if necessary.
- Verify account identity before importing private reading information.

A Goodreads author ID must not be mistaken for a reader profile ID.

### Credential handling

- Google Books credentials stay in local configuration or environment variables.
- Browser session state stays in a user-private application directory.
- Tokens, cookies, and authorization headers never enter source control or logs.
- The script should not require passwords to be pasted into a configuration file.

### Google Books authorization during sync

Plain `booky sync` reuses an API key or a valid/refreshed OAuth session. When
authorization is needed in an interactive terminal, it prompts for client ID/
secret and opens normal browser consent; no one-time auth command is required.
`GOOGLE_BOOKS_CLIENT_ID` / `GOOGLE_BOOKS_CLIENT_SECRET` may be supplied locally;
sensitive prompts are hidden. A Desktop client is recommended. A Web client requires
the exact registered redirect URI `http://127.0.0.1:8765/oauth2/callback`.
The Google Books scope is `https://www.googleapis.com/auth/books`; BookyStats
uses it for metadata reads only, not account-source acquisition or library writes.

Client credentials alone are not authenticated access: actual human browser
consent is still required. The selected data directory's ignored
`google-books-oauth.json` is written atomically with private-file protections;
never commit or log it. An API key takes priority and valid/refreshed OAuth is the
fallback. Consent and refresh occur only during sync. TTY detection is the normal
interaction default; advanced `--interactive` / `--unattended` overrides remain.
Headless cron never prompts or launches consent and reports needs-auth when
required. Ordinary status remains local/non-networking. No live Google
authentication success is claimed.

### Reauthentication

A persistent session does not mean permanent access.

When authentication expires:

- Mark the source as needing authentication.
- Keep the last valid data.
- Do not interpret a login page as an empty collection.
- Allow the next interactive run to reconnect.
- Ensure an unattended run does not sit waiting forever for input.

Normal login or browser challenges may require human interaction. We will not introduce stealth, challenge-bypass, or proxy-rotation machinery.

---

## 6. Define the collection scope explicitly

“Fetch all data” needs an accountable definition.

### Required account data

| Category | Target |
|---|---|
| StoryGraph identities | Identity needed to conservatively match personal ratings |
| Personal ratings | StoryGraph only; distinguish unrated from unavailable |
| Personal reviews and other attributes | Goodreads only where explicitly represented; never StoryGraph processed facts |
| Reading events | Goodreads dates and rereads only where explicitly represented |
| Reading states | Goodreads read/current/paused/DNF and other explicitly supported states |
| Goodreads watchlist | Every accessible active watchlist entry |
| Watchlist context | Shelves, dates added, ordering, and identifiers where available |

### Separate enrichment scope

Descriptions, genres, publication dates, series, and lengths are additional metadata.

They are useful, but a missing description must not prevent a book from being stored.

### Capability states

For each source field, distinguish:

| State | Meaning |
|---|---|
| **Supported and present** | Retrieved successfully |
| **Supported but empty** | The source genuinely has no value |
| **Unavailable for this record** | The source does not expose it here |
| **Unsupported by the connector** | We have not implemented or established extraction |
| **Failed to retrieve** | An error prevented collection |

This distinction is essential. Otherwise a broken selector can turn an entire collection into “unrated books.”

---

## 7. The first full synchronization

Plain sync must read exact configured CSV paths and archive their original bytes
before parsing, then validate scope/counts, process, and independently publish
each complete file/scope snapshot with raw lineage. Missing/invalid scopes retain
last complete snapshots; no automatic archive replay or source fetching occurs.
Provider enrichment has
separate provenance and coverage; it must not prevent a valid source snapshot
from being retained. Internal/advanced explicit replay need not require the
original download path or website access, but normal sync requires its configured files.

The following source-discovery steps are requirements for a future live capture
stage, not current CSV behavior; they still need implementation and live evidence.
Normalization, matching, publication and receipts also apply to CSV processing.

### Establish identity

Confirm which reader each connection represents before collecting or updating data.

### Enumerate collections

Traverse all relevant pages or feed pages.

Record:

- Page progress.
- Source identifiers.
- Pagination state.
- Available totals.
- Normal termination versus unexpected truncation.

### Retrieve personal details

Fetch the fields needed beyond the collection listing.

Prioritize correctness over assuming that every visible star value is her rating.

### Commit raw capture

Save source content and collection evidence before parsing or cleansing.
Processing consumes this durable boundary, not in-memory fetch results alone.

### Normalize records

Convert source-specific representations into common structures while retaining the original values and provenance.

### Reconcile book identities

Link records that demonstrably refer to the same work or edition.

Keep ambiguous cases visible.

### Persist account observations

Save validated records and the evidence needed to explain the collection.

### Publish a usable snapshot

Commit the completed source/scope snapshot independently. Future downstream
calculations consume only a declared compatible input manifest, not whichever
source snapshots happen to be latest when each query executes.

### Enrich metadata

Fetch missing information using default-enabled Google Books and Open Library
with bounded work and caching; honor advanced provider-disable configuration.
Record incomplete coverage separately; the future
input manifest pins the metadata observations used.

### Produce a receipt

Report what was collected, what changed, and what remains incomplete.

The first run may take substantially longer than later runs. We should not promise a completion time before seeing the size of the library and the source’s pagination behavior.

---

## 8. Pagination and completeness

This is a central correctness concern, particularly for a large watchlist.

The collector must handle:

- Explicit next-page links.
- Feed page parameters.
- Infinite scrolling where that is the supported interface.
- Repeated pages.
- Empty responses.
- Provider-imposed page or row caps.
- A collection changing while it is being traversed.

### Evidence of completeness

Use the evidence available from each source:

- Pagination terminated normally.
- No page failed.
- No unexplained repetition occurred.
- Retrieved identifiers reconcile with available collection totals.
- Totals are being compared in the correct units.

For example, a source’s “reads” total may count rereads while its list contains unique books. Those numbers must not be compared as though they mean the same thing.

A traversal stopped by a configured limit is **partial**, not complete.

### Resuming interrupted work

Resume only when the checkpoint is still meaningful.

An offset into a changing collection may no longer point to the same records. Where necessary:

- Re-enumerate membership safely.
- Reuse already collected book details.
- Resume detail fetching by stable source identifiers.

Idempotent persistence makes replay safe: processing the same record again does not create duplicates.

---

## 9. Canonical data model

The database should preserve several distinct concepts.

| Entity | Purpose |
|---|---|
| **Source account** | Which reader and service the data belongs to |
| **Work** | The underlying book |
| **Edition** | A particular format, language, publisher, or ISBN |
| **Source record** | The service-specific identity and original observations |
| **Reading event** | A particular reading attempt or completion |
| **Personal assessment** | StoryGraph personal rating or explicitly represented Goodreads review; never a StoryGraph review |
| **Watchlist membership** | Whether a Goodreads entry is currently on the watchlist |
| **Metadata observation** | A provider’s value and when it was obtained |
| **Match decision** | How source identities were connected |
| **Sync run** | Collection progress, outcomes, and freshness |
| **Derived result** | A statistic or recommendation tied to particular inputs |

These are logical entities. They do not all need separate elaborate subsystems on day one.

### Work versus edition

A paperback and audiobook may represent the same work but have different:

- Length measurements.
- Narrators.
- Translators.
- Publication dates.
- Publishers.
- ISBNs.

Work-level matching should not erase edition-level information.

### Reading event versus current state

A book may have:

- Been completed previously.
- Been reread later.
- Currently be in progress again.

A single current status cannot replace the reading history.

### Assessment versus reading event

If the source exposes one current rating for the book, store that fact.

Do not duplicate it into invented historical ratings for every reread.

---

## 10. Identity matching

### Matching order

1. Previously confirmed mappings.
2. Valid ISBN matches with consistency checks.
3. Explicit cross-provider identifiers.
4. Supported title-and-author matches.
5. Candidate matches awaiting resolution.

Current work-level repair accepts reciprocal unique full canonical titles and
full authors across missing/different ISBNs only with active-scope,
series/volume/omnibus discrimination and selected-catalog conflict checks.
Links remain reversible. Do not infer edition identity from those work links:
editions require shared validated ISBN evidence. Synthetic record IDs cannot
establish bibliographic identity.

### Required checks

- Validate ISBN structure and checksum.
- Preserve ISBN-10 and ISBN-13 relationships correctly.
- Do not interpret arbitrary StoryGraph UIDs as ISBNs.
- Distinguish translators, editors, narrators, and authors where possible.
- Keep original titles for display.
- Normalize punctuation and spacing only for matching.
- Use verified alternate titles rather than guessing translations.

### Difficult cases

Explicitly handle:

- Omnibuses and their component books.
- Short stories versus collections.
- Revised editions.
- Abridged audio editions.
- Different works with identical titles.
- Authors sharing a name.
- Series labels embedded in titles.

### Match outcomes

Use understandable states:

- Confirmed.
- Likely but unconfirmed.
- Unresolved.
- Conflicting.

Do not present a heuristic matching score as a calibrated probability.

Manual corrections must survive later syncs and remain reversible.

---

## 11. Provenance and time

For important values, retain:

- Source.
- Source record identifier.
- Scope: reader, work, or edition.
- Value.
- Observation time.
- Source-provided effective time, if available.
- Whether it was extracted, normalized, or inferred.

### Keep different timestamps separate

| Timestamp | Meaning |
|---|---|
| **Source date added** | When the service says the book was added |
| **First observed locally** | When BookyStats first saw it |
| **Last checked** | When the connector last examined it |
| **Source update time** | When the source says it changed, if exposed |
| **Last successful collection** | When the relevant collection completed successfully |

First observed locally must not become the date she originally became interested in a book.

### Preserve date precision

A year-only date remains year-only.

A month-only date remains month-only.

Date-only reading records should not be shifted through time zones as though they were precise UTC events.

Operational timestamps can use UTC, while report calendar boundaries use an explicitly defined reporting time zone.

---

## 12. Detecting changes on later syncs

Later syncs need to detect more than newly added books.

| Change | Required behavior |
|---|---|
| New completed book | Add the work/edition and reading information |
| Revised rating | Record the new assessment observation |
| Edited review | Preserve the changed review and observation time |
| Reread | Add a separate event if the source exposes it |
| Changed reading status | Update current state without destroying history |
| New watchlist entry | Add membership and source context |
| Removed watchlist entry | Mark membership inactive after reliable reconciliation |
| Changed edition | Preserve the relationship without creating an unrelated work |
| Corrected metadata | Update the selected value while retaining provenance |

### Incremental collection where reliable

Use change timestamps, feeds, or collection-level indicators only when they genuinely cover the fields we care about.

A new-book feed may not report:

- An edited review on an older book.
- A changed old rating.
- A removed shelf entry.
- Corrected reading dates.

### Reconciliation where necessary

Where there is no trustworthy change signal, revisit enough of the collection and detail pages to establish current state.

**Caching does not remove this requirement.**

We should optimize duplicate work, but not claim a fully current account after checking only its newest books.

---

## 13. Database updates and partial failure

### Stage before publishing

Collection should not overwrite the current usable dataset with half a run.

A suitable approach is:

1. Collect and validate observations in a staging run.
2. Track completeness for each source and collection.
3. Publish validated snapshots atomically.
4. Retain the previous usable snapshot when a required stage fails.

Network activity should not hold a long SQLite write transaction open.

### Independent source outcomes

StoryGraph can fail while Goodreads succeeds.

The run should report that accurately rather than declaring everything failed or everything current.

Downstream outputs must know which source snapshots they are using.
Independent publication is not permission to implicitly mix their generations.
Future analysis must first commit the compatible manifest described in the
opening architecture; failure to satisfy required freshness/coverage blocks new
derived outputs, not the independent successful source publication.

For example:

- Historical statistics may remain usable from the last Goodreads Read snapshot,
  with personal-rating coverage tied separately to the StoryGraph snapshot and
  the original manifest/freshness labels retained.
- Watchlist recommendations can use older reading history only when the declared
  compatibility policy permits it and the manifest explicitly records the age/skew;
  otherwise the new ranking is blocked and prior rankings remain visibly dated.

### Removal rules

Never remove local membership because:

- Authentication expired.
- A page failed.
- Pagination stopped early.
- A feed returned an error.
- The collector encountered an unexpected layout.

Only a sufficiently complete reconciliation can establish that an entry is absent.

Keep historical membership observations rather than deleting the book itself.

---

## 14. Metadata enrichment and caching

Google Books and Open Library are both enabled by default. Google Books uses
an API key or valid/refreshed OAuth; first interactive sync handles normal
client prompts/consent if required, while headless runs report needs-auth.
Advanced configuration may disable a provider. Both serve processing only; they do not supply
authoritative personal account facts. Retain their full HTTP responses in
`data\raw.sqlite3` under separate provider source/type documents and use
`data\metadata.sqlite3` for disposable query caching.

### Google Books

An optional locally supplied key is useful for:

- ISBN and title/author lookup.
- Descriptions.
- Categories.
- Publication information.
- Page counts.
- Language.
- Available community ratings.

It does not authenticate StoryGraph or Goodreads.

Use the [documented public-data API-key flow](https://developers.google.com/books/docs/v1/using). The project’s actual quota should be read from its configuration rather than assumed.

### Open Library

Useful for work/edition relationships, identifiers, subjects, and bibliographic information.

Its [API guidelines](https://openlibrary.org/developers/api) explicitly discourage bulk per-book harvesting. A large library needs permitted batching, reuse, and an appropriate bulk route where necessary—not simply thousands of individually throttled requests.

### Hardcover

Optional enrichment for richer catalog information, series, aggregate reception, and audio duration.

Use a catalog-read token and respect the current [API contract](https://docs.hardcover.app/api/getting-started/). The connector should not need access to other users’ private libraries.

### Current queue and cache policy

Time alone never schedules a metadata refresh. New records, changed identity or
changed provider implementations can become eligible; unchanged successful and
deterministic partial/ambiguous/invalid attempts stay parked. Persist those
outcomes in receipts and active-scope status: no due requests does not establish
complete coverage. Legacy `metadata.max_age_days` loads compatibly but is ignored,
omitted on save and removed from root config.

Retryable record failures wait at least six hours after the saved attempt;
durable provider/host gates may wait longer. Explicit structured Google daily-
quota evidence requires a durable six-hour minimum cooldown, respecting longer
Retry-After deadlines. Generic quota errors are not daily-exhaustion evidence.
The saved rejection reports a 1,000-query daily project cap; the configured
10,000-book run budget cannot override it and does not establish a reset time.
Never reset a gate to force completion, including during rebuild/recovery.

The following field-level distinctions are future refresh considerations, not
an implemented age-based refresh scheduler:

| Field type | Refresh behavior |
|---|---|
| Stable identifiers | Reuse unless conflicting or corrected |
| Descriptions and classifications | Revisit only through explicit future policy or changed evidence, not age alone |
| Publication and edition details | Cache, but allow corrections |
| Community ratings and counts | Keep dated observations; future current-reception analysis needs explicit refresh policy |
| Personal ratings and reviews | Follow the account synchronization policy |

Cache age and successful retrieval are separate concepts. A failed refresh must not reset the freshness timestamp.
Cache reuse does not run a background purge or delete the durable provider-
response archive.

### Large-library behavior

Account collection and metadata enrichment have separate completion states.

We can have:

- A complete Goodreads watchlist.
- A complete supplied Goodreads Read file and StoryGraph rating file.
- Incomplete metadata enrichment.

That is a useful, honest state—not a failed project and not “everything complete.”

---

## 15. External weekly trigger once stable

### The scheduled operation

A future external cron job and a manual command invoke the same CLI/application
services: ingestion, processing, analytics, and watchlist. They differ only in
trigger and explicit run inputs, not business logic. Analytics is implemented;
watchlist ranking is not. Existing private Windows `--scheduled` plumbing is retained
disabled/unregistered, not assumed portable or ready for external cron.
Current plain `booky sync` processes configured CSVs without source access.
A future acquisition/cron workflow needs separate implementation and approval;
CSV imports and raw replay are not fresh weekly account-collection evidence.
Cron does not make source sessions or required Google authorization valid.

It should:

1. Acquire the reader/database lock and validate activation fingerprints before
   any account access.
2. Acquire each intended source/scope explicitly, saving original bytes and dated
   acquisition evidence.
3. Parse, validate, authority-filter, and publish successful scopes independently;
   failed/missing scopes keep their last good snapshot.
4. Perform bounded metadata refresh with both default providers, respecting
   advanced disable settings and recording separate coverage/authentication needs.
5. Once implemented, commit a compatible input manifest; block dependent tasks
   when its required inputs fail validation or freshness checks.
6. Once implemented, reuse or refresh analysis, saved preference weights, and
   rankings only when their relevant input/version/configuration keys change.
7. Verify committed results, record a durable receipt/log including partial,
   failed, and skipped task outcomes, release the lock, and exit.

### Activation criteria

Do not enable the schedule merely because one interactive run succeeded.

Before activation, establish that:

- The collector can traverse the complete intended collections.
- A repeated run does not create duplicates.
- Older edited records are detected.
- Failures do not erase data.
- Interrupted work can recover.
- Sessions are reusable.
- The actual scheduled execution context works.
- An unattended run handles expired authentication without hanging.
- Both configured accounts have two consecutive complete same-account,
  same-implementation runs including unattended evidence, with recent consistent
  receipts matching stored snapshots.
- The explicitly chosen external host, cron expression/time zone, interpreter,
  account identities, and implementation are bound to verified run configuration;
  configuration changes invalidate incompatible activation evidence.

This does not require waiting several weeks. Controlled fixtures can establish
recovery logic, but cannot replace complete real-account repeat/unattended
evidence. Complete manual files and replays never satisfy those acquisition gates.

### External cron deployment — future, not this machine

Choose an external cron-capable host only when deployment is explicitly approved.
It must have durable local storage, the supported runtime, protected configuration
and account access, tested backups, and a verified unattended acquisition route.
No Windows Task Scheduler registration or local-machine scheduling is wanted.
Do not add a scheduler dependency, broker, or always-running pipeline process.

It should not depend on a Copilot conversation remaining open.

Choose the cron cadence and time zone explicitly; define missed-run behavior so
an unavailable host cannot silently appear current. Keep manual and cron entry
paths bound to the same application services and compatible data/configuration.

Browser execution also needs to work in that environment. A connector that only works during an interactive desktop session is not yet a proven unattended connector.

### Prevent overlapping runs

Manual and scheduled runs must not update the same account simultaneously.

Use one lock across acquisition, publication, and future manifest/derived-output
commits per reader/database, with a clear “already running” skipped outcome rather
than launching duplicate crawls. Verify ownership before recovering an abandoned
lock; never steal a live run's lock.

### Failure behavior

- Transient failures receive bounded retries.
- Expired authentication requires reconnection.
- Unsupported page changes stop the affected extraction path.
- Last good data remains readable.
- The next run resumes or safely reconciles again.
- No failure triggers an export-based fallback.

---

## 16. What weekly snapshots make possible

Snapshots are useful beyond recovery.

They can eventually support:

- Changes to personal ratings.
- Revisions to reviews.
- Observed watchlist additions and removals.
- Changes in recommendation rankings.
- Community reception movement.
- Prospective recommendation evaluation.

But weekly observations are not a complete event stream.

A book added and removed between two syncs may never be observed. A rating change may only be known to have occurred between two observations unless the source supplies an exact update time.

Reports must describe **observed changes**, not claim perfect historical event coverage.

Snapshots begin when we start collecting them. They do not reconstruct earlier years automatically.

---

## 17. `booky status`

The status command should read the database without contacting external services.

It should answer:

| Area | Information |
|---|---|
| Configuration and input files | Actual selected config path, each configured CSV filename and ready/missing state |
| Connections | Configured, usable, or needing authentication |
| Freshness | Last successful collection for each source |
| Completeness | Complete, partial, unresolved, or unsupported portions |
| Library | Source records, resolved works, editions, reading events |
| Watchlist | Active membership and unresolved identities |
| Personal data | Rating, review, and date coverage |
| Metadata | Coverage for descriptions, genres, series, length, publication dates |
| Recent run | Added, updated, removed-from-shelf, unchanged, and failed records |
| Scheduling | Whether enabled, last outcome, and next expected run when available |

This should be concise enough to use routinely, with more detailed structured information available internally.

No new command family is needed for every subsystem.

---

## 18. CSV milestone and deferred live completion

Current CSV acceptance requires exact configured paths, raw-first integrity,
independently atomic scopes, retention on missing/invalid inputs, no source
browser/fetching or archive fallback, local status and installed-command real-input
E2E. Enrichment-disabled source acceptance is not provider acceptance.

The broader deferred live-collection deliverables are:

- Working direct source connectors.
- Persistent SQLite storage.
- A unified, source-aware library.
- Repeatable synchronization.
- Accurate completeness and freshness reporting.
- Resumable metadata enrichment.
- A verified unattended path before weekly scheduling is enabled.

The important correctness cases include revised old ratings, edited reviews, rereads, private profiles, pagination failures, unknown statuses, ambiguous books, and interrupted runs.

Those cases should be exercised using controlled data and fixtures—not by automatically altering her real reading history.

---

# Phase 2 — Understand the data and build the statistical engine

This **backend** pipeline is implemented and integrated, not a frontend or a new
acquisition mode. The detailed requirements below still include deeper work;
only supported findings may be produced. The implemented baseline includes a
capability inventory: current exports provide 730 Read memberships but no usable
dated reading events or personal reviews. The latest actual Read input has
314 confirmed personal-rating links across 730 works in an earlier acceptance;
those counts are historical, not the current coverage.
Unlinked Read books are not automatically unrated. StoryGraph
moods, pace and other non-rating attributes remain raw-only under current
authority rules; do not silently promote them to fill an analytics feature.
Optional provider coverage must be measured independently of source-only E2E.

Reader and content analysis uses all Read books, independent of rating availability:

- Reading profile, page quartiles and distinct-work first-publication years,
  kept separate from edition-year observations.
- Known-feature combinations, metadata quality and a rating-availability
  representativeness audit, not a profile restricted to rated books.
- Versioned description themes and six-hunger **content mentions**, with evidence
  quotes. These do not infer reader personality, colors or official scores,
  depend on ratings, or use genre proxies.
- Descriptive watchlist composition/missingness and a fractionally weighted
  Read/watchlist comparison (Jensen–Shannon divergence), not recommendations.

Enjoyment calculations separately use confirmed ratings for exposure/enjoyment
comparisons, shrunk means, group support, conditions and provider-specific
community comparisons. The current combined implementation passed the full
644-test gate and actual/offline analytics acceptance:

- Complements use only known features: unknown does not mean negative.
- Effects and rating lifts are shrunk for small samples, with author-fragility checks.
- Predictive validation leaves out a whole work at a time to prevent leakage.
  MAE/RMSE are compared with a training-only mean baseline; fallback use is explicit.
- Yearly genre breadth uses equal-volume rarefaction rather than rewarding larger years.
- Shared-stratum standardized comparisons use **current** ratings grouped by
  actual reading year, not invented historical ratings.
- `en`/`eng` share a language group while original values/provenance remain saved.
- Matched-edition language requires edition-scoped evidence. Work-level
  translation availability stays separate and cannot fill missing edition
  language or establish the language actually read.
- Cache keys include the full as-of date/year.

The Goodreads files have no authoritative dated reading events. StoryGraph
completion dates remain raw-only and cannot supplement missing reading history.
Library-addition and publication dates remain different facts. Review analyses
remain gated. Implementation tests do not fill data gaps; full provider
enrichment remains incomplete.

## 19. Let the collected data determine the analyses

The first statistical output is a capability inventory.

| Classification | Meaning |
|---|---|
| Supported | Required fields are available |
| Supported for a subset | The result can be calculated with a stated denominator |
| Needs enrichment | A catalog field is missing |
| Needs more observations | Future snapshots or more reading history are required |
| Unsupported | The available data cannot honestly answer it |

This should identify which advanced ideas are practical before we build them.

The aim is not to produce fifty weak metrics. It is to produce a smaller set of interesting, defensible findings and expand as the evidence improves.

---

## 20. The statistical questions worth pursuing

### Enjoyment versus exposure

A category she reads often is not automatically a category she enjoys most.

Compare:

- How much of her reading belongs to it.
- Her rating distribution within it.
- Its frequency among higher-rated books.
- Whether the result depends on one author or series.

This can distinguish familiar habits from reliable enjoyment.

### Conditional preferences

Single labels are often too broad.

Potential questions:

- Does slow pacing work better when a book is character-focused?
- Does she enjoy long books more in some categories than others?
- Does a familiar author change her tolerance for unfamiliar subjects?
- Are certain combinations associated with stronger ratings than either feature alone?

These analyses need adequate support. We should not manufacture conclusions from one or two books.

### Review-supported preferences

Ratings tell us whether she enjoyed a book. Reviews may explain why.

Candidate themes:

- Character development.
- Emotional impact.
- Prose.
- Pacing.
- World-building.
- Relationships.
- Ideas and learning.
- Predictability.
- Ending satisfaction.
- Repetition.
- Narration.
- Length.

Every extracted theme should retain supporting text and its source book.

### Taste changes

Compare earlier and later reading while distinguishing:

- Changes in the books selected.
- Changes in ratings within comparable groups.
- Changes in metadata coverage.
- Later revisions to old ratings.

A different genre mix can change the overall average without any category becoming more enjoyable.

### Author and series reliability

Explore:

- Consistency rather than only average rating.
- Whether an author’s apparent strength rests on one book.
- Differences between starting and continuing series.
- Concentration of favorites within a small set of authors.

### Reading breadth

Use consistent classifications to describe how concentrated or varied her reading is.

Where comparing years with different numbers of books, use a comparable-volume approach rather than allowing a larger year to appear broader merely because it contains more observations.

### Watchlist mismatch

Current output only describes watchlist composition, missing information and
differences from Read. Preference-based candidate assessment belongs to later
recommendation work. That later work may compare the watchlist with supported
preferences from reading.

This can reveal:

- Categories heavily represented in the backlog but weakly supported by enjoyment.
- Strong preferences with surprisingly few candidates.
- Older entries that still fit well.
- Areas where she has too little experience to draw a conclusion.

### Community agreement

Compare her ratings with a named provider’s community ratings on matched books.

Do not combine all platforms into an invented universal consensus.

### DNF patterns

Keep DNF separate from low ratings.

Where available, distinguish explicit reasons such as:

- Wrong timing.
- Pacing.
- Writing style.
- Content.
- Lack of interest.

A blank rating on an abandoned book is not a zero-star rating.

---

## 21. Read Your Color-inspired dimensions

Use the idea of reading appetites to go beyond genre.

The [Read Your Color site](https://readyourcolor.com) and public
[assessment](https://readyourcolor.com/assessment) describe a heart/head and
roots/wings compass, plus six hungers: wonder, surprise, intensity, meaning,
connection and clarity. The assessment uses attraction to blurbs and statements,
not historic genre counts. No validated official scoring weights are available here.

For BookyStats:

- A reader can value several dimensions simultaneously.
- The dimensions do not need to sum to 100%.
- They are not a diagnosis or permanent identity.
- We do not claim to reproduce the site’s assessment.
- Do not guess colors, derive personality from genre counts, or invent official weights.
- The implemented inspired view uses explicit supported appetite labels only;
  unsupported dimensions remain unavailable.

Maintain three views:

| View | What it describes |
|---|---|
| Declared preferences | What she explicitly says she wants |
| Reading exposure | Characteristics present in books she reads |
| Enjoyment associations | Characteristics associated with her ratings |

Disagreement between those views can be useful.

### Label quality matters

Book-level labels can come from:

- Her explicit answers.
- Provider classifications.
- Well-defined interpretation of descriptions.
- Optional local text analysis.

Each label needs an origin and an appropriate reliability description.

If the data supports mood and pace but not a nuanced “meaning” dimension, report mood and pace. Do not invent the rest to complete a profile.

---

## 22. Statistical methods and safeguards

### Define the population

Every metric should identify whether it uses:

- Unique works.
- Reading events.
- Rated completed books.
- All completed books.
- Current watchlist entries.
- A specific time period.

Rereads should not silently change the denominator.

### Preserve missing values

Missing ratings, unknown page counts, and absent genres do not become zero.

### Adjust thin samples

A category with one five-star book should not automatically beat a category with many consistently strong books.

A transparent adjusted mean can use:

```text
adjusted mean =
(group rating total + prior strength × overall mean)
÷
(group sample size + prior strength)
```

The adjustment must be documented. It is not a device for making results look impressive.

### Describe uncertainty appropriately

Use intervals or stability checks where their assumptions are reasonable.

Where evidence is too limited, say so rather than rendering a precise-looking percentage.

Repeated books from one series or author may require grouped treatment rather than assuming every observation is independent.

### Avoid finding patterns by sheer volume

If we examine hundreds of combinations, some will look impressive by chance.

Use a manageable set of planned comparisons, report support, and distinguish exploratory findings from patterns that remain stable under further data.

### Separate association from causation

“Higher ratings among books with this characteristic” is supportable.

“This characteristic causes her enjoyment” generally is not.

---

## 23. A common result format

Each statistical finding should carry:

- A stable metric identifier.
- The population.
- Time period.
- Value and unit.
- Comparison baseline.
- Sample size.
- Missing-data count.
- Reliability or uncertainty information.
- Supporting book identifiers.
- Calculation version.
- Source snapshot references.
- Relevant limitations.

Human-readable text is generated from that result.

CSV, JSON, and a future API should not independently recalculate the same metric.

### Phase 2 completion

The statistical engine should produce meaningful findings that can be traced to records and calculations.

Unsupported ideas remain visible in the capability inventory rather than being implemented as guesses.

---

# Phase 3 — Rank the Goodreads watchlist

## 24. Candidate eligibility

The primary candidate pool is her active Goodreads watchlist.

Before scoring:

- Exclude confirmed completed works unless rereads are explicitly included later.
- Keep currently reading books out of a “start next” list.
- Separate paused and DNF reconsideration candidates.
- Collapse duplicate editions appropriately.
- Flag unresolved possible matches to already-read books.
- Exclude known unreleased titles from immediate-next-read suggestions.
- Apply explicit language, format, length, and content constraints when supported.

Series position should not automatically imply a mandatory prerequisite. Companion books, prequels, and optional novellas need different treatment.

Unknown metadata must remain visible. A book with unknown length cannot be confidently described as satisfying a strict page limit.

---

## 25. Build the recommender in layers

### Transparent baseline

Start with:

- Similarity to previously enjoyed books.
- Similarity to explicitly disliked books.
- Supported genre, mood, pace, and other preference associations.
- Author or series familiarity.
- Explicit current-reading preferences.
- Known conflicts and constraints.

Community popularity is a secondary signal, not the main objective.

### Learned ranking

Once the data supports it, evaluate a regularized model using shared book metadata and text features.

The model should earn its place by improving over the simpler baseline.

Do not add a large model merely because recommendations sound like an AI problem.

### Align training and prediction features

This is especially important.

We cannot train using her post-reading answers for a book and then assume the same answers exist for unread candidates.

Use features available for both historical and unread books. Her personal reviews and answers can help form her preference profile, but the target book’s future personal review is unavailable.

---

## 26. Recommendation modes

The engine can eventually support several purposes without needing separate implementations.

| Mode | Purpose |
|---|---|
| **Best fit** | Strongest match to established preferences |
| **Explore** | A supported departure from familiar reading |
| **Rediscover** | Promising older watchlist entries |
| **Current appetite** | Match an explicitly requested reading experience |
| **Constraints** | Work within supported length, format, language, or series preferences |

These are future capabilities, not commands we need to add now.

“Explore” should mean different from her own history—not universally strange, difficult, or experimental.

---

## 27. Full ranking versus a useful shortlist

Produce both:

- A ranked view of the eligible watchlist.
- A shortlist with sensible variety.

A purely sorted list can fill its first ten positions with one author or series.

Shortlist selection can account for author, series, category, length, and reading appetite while preserving strong personal fit.

Unrankable records should remain present with reasons. They should not disappear from the output or receive arbitrary low scores that imply dislike.

---

## 28. Explain every recommendation

Each result should include:

| Information | Purpose |
|---|---|
| Book and edition identity | Avoid recommending the wrong work |
| Main supporting reasons | Show the strongest evidence |
| Relevant books she enjoyed | Make the match concrete |
| Potential mismatch | Explain why it might not work |
| Missing information | Expose uncertainty |
| Recommendation mode | Explain the selection objective |
| Original watchlist context | Preserve date added and source priority where available |

Confidence has separate components:

- Correct identity.
- Sufficient metadata.
- Sufficient evidence about her preferences.

A single unexplained “92% match” hides those differences.

If we expose an internal ranking score, label it as a ranking score—not a probability of enjoyment.

---

## 29. Evaluate without misleading ourselves

Use time-ordered evaluation when dates and history permit.

Protect against:

- Using the target book’s own review to predict its rating.
- Splitting rereads of the same work across training and evaluation.
- Treating unread books as dislikes.
- Using future publication or award information in a purported historical prediction.
- Pretending today’s watchlist was the watchlist years ago.

With only current source observations, early evaluation may be retrospective rather than a faithful historical simulation.

Useful measures include:

- Whether higher-rated held-out books rank above lower-rated ones.
- Ranking quality within the observed evaluation set.
- Performance on unfamiliar authors.
- Candidate coverage.
- Shortlist variety.
- Stability when small amounts of data change.

Future recommendation snapshots allow more honest prospective evaluation.

A book recommended and later read is evidence of sequence—not proof that the recommendation caused the choice.

### Phase 3 completion

The engine should produce an explainable watchlist ranking with correct eligibility, traceable evidence, and useful handling of uncertainty.

---

# Phase 4 — Her Year in Review

## 30. Define the personal year

The main population is:

> Books she completed during the selected calendar year, regardless of their publication year.

Report unique works and recorded completions separately.

Additional sections can cover starting, pausing, abandoning, or continuing books only when the source provides suitable dated information.

A report for the current year is labeled year-to-date.

---

## 31. Personal annual report contents

| Section | Contents |
|---|---|
| **The year in numbers** | Works, completions, rereads, rated books, new-to-her authors |
| **Favorites** | Highest-rated books, ties, and review-supported reasons |
| **Unexpected successes** | Strong results outside established expectations |
| **Taste profile** | Supported characteristics associated with enjoyment |
| **What changed** | Comparisons with earlier reading |
| **Reading sequence** | Runs of authors, series, categories, or supported moods |
| **Exploration** | New-to-her authors, categories, languages, and publication eras |
| **Returning favorites** | Rereads and continued authors or series |
| **Watchlist movement** | Observed additions, removals, and completed watchlist books |
| **Unfinished reading** | Separate treatment of DNF, paused, and ongoing books |
| **Personal distinctions** | Review-supported highlights such as prose or emotional impact |
| **Next reads** | Recommendations from the existing watchlist |

### Unexpected favorites

A surprise should be measured against an appropriate prior expectation, not simply defined as “a highly rated book in an unfamiliar genre.”

If a sound comparison is unavailable, use a modest descriptive label instead.

---

## 32. Personal annual measurement rules

### Pages

Where edition data permits, report **pages in completed books**.

Do not present this as exact pages actively read during the year. Some books cross calendar boundaries, and partial reading may be unknown.

### Audio

Report known edition duration separately from actual listening time.

### Reading duration

Start and finish dates support elapsed calendar duration, not active reading hours.

### Daily activity

Completion dates support “books finished on this day,” not daily reading streaks.

### Ratings

If only current ratings are available, report current ratings of books completed that year.

Weekly snapshots can improve future historical accuracy, but do not repair earlier missing history.

### Year-over-year comparisons

Compare equivalent periods where possible and show differences in coverage.

A larger or better-enriched dataset can create apparent changes that do not reflect a real change in reading.

### Phase 4 completion

The personal review should reuse the statistical engine, apply correct calendar boundaries, and avoid inventing activity or historical assessments.

---

# Phase 5 — Calendar Year in Books

## 33. A genuinely standalone public report

The general annual review should work without her account.

Its core dataset and report should contain public catalog and aggregate information only.

Personalization is a later join:

```text
Public annual dataset
        ↓
General Year in Books
        ↓
Optional comparison with her history and watchlist
        ↓
New personalized discoveries
```

---

## 34. Separate the different meanings of “this year”

| Cohort | Meaning |
|---|---|
| **Published that year** | Works with an eligible first publication in the selected year |
| **New in a language or market** | Relevant translations or new availability |
| **Awarded that year** | Books receiving awards during that calendar year |
| **Read during that year** | Requires suitable dated activity data |
| **Popular when observed** | Current or rolling reception and activity |

These cannot be mixed into one unlabeled leaderboard.

A reprint is not automatically a new work. A translation can be a significant new release without changing the original work’s publication year.

---

## 35. Keep publication year and observation date separate

An annual report has two independent time dimensions:

- Which year the books belong to.
- When their reception was measured.

This is valid:

> Books first published in 2025, using reception observed in October 2026.

This requires historical evidence:

> The highest-rated books at the end of 2025.

Open Library’s yearly trending feed is a rolling 365-day window. Hardcover’s [documented trending queries](https://docs.hardcover.app/api/graphql/schemas/books/) also use windows.

Neither is a substitute for arbitrary January-to-December activity.

Weekly snapshots will improve future analysis, but only from the point collection begins.

---

## 36. Build a declared annual dataset

Candidate sources can include:

- Catalog queries for the release cohort.
- Source-specific reception and readership aggregates.
- Award winners and shortlists.
- Relevant translations and other verified categories.

Do not discover candidates only through trending lists. That would make finding lesser-known books difficult by construction.

Each dataset should record:

- Providers.
- Retrieval periods.
- Publication eligibility rules.
- Language or market scope.
- Candidate counts.
- Duplicate resolution.
- Missing or conflicting publication information.
- Known coverage limitations.

The report describes the books captured by its sources—not every book published worldwide.

### Awards

Record the award, category, year, work, status, and supporting source.

Keep winner, shortlist, and longlist states separate.

Do not transfer an author-level award onto all their books.

Services whose current access has not been established, including a possible NYT integration, remain optional rather than required dependencies.

---

## 37. Public annual report sections

| Section | Purpose |
|---|---|
| **The release landscape** | Describe the eligible cohort |
| **Highly rated with meaningful support** | Avoid tiny-sample winners |
| **Widely read within a named source** | Show readership without claiming global reach |
| **Less-known, well-received books** | Surface credible discoveries |
| **Category standouts** | Highlight books within supported classifications |
| **Divided reader reception** | Use rating distributions when available |
| **Award highlights** | Winners and selected shortlists |
| **Notable translations** | Where language and release information support inclusion |
| **Verified debuts** | Only where debut status is established |
| **Older books attracting new interest** | Only with suitable time-based evidence |
| **Personal discovery appendix** | Optional recommendations missing from her library |

---

## 38. Public ranking rules

### Popularity and reception are different

Reader counts, rating counts, mean ratings, and awards measure different things.

There should not be one unexplained “best book” score combining them.

### Adjust for thin samples

Where suitable raw means and counts are available, use transparent shrinkage toward a relevant comparison mean.

Do not blindly apply a second adjustment to a provider score that is already adjusted.

### Keep communities separate

Do not add reader counts across providers as though every reader is unique.

Do not average platform ratings into an invented universal consensus.

Source-specific rankings can be compared, but their identities must remain visible.

### Define lesser-known books explicitly

Use a documented audience-size criterion within the source.

Then require enough reception evidence to avoid one-review winners.

“Lesser-known” is a measurable classification. “Unfairly overlooked” is a stronger judgment that the data may not establish.

### Polarization requires distributions

An average alone cannot show whether readers are divided.

Omit the section when the required distribution is unavailable.

### Account for publication timing

Early-year books have had more opportunity to accumulate readership.

Make this visible or use comparable release cohorts. Do not manufacture a precise time adjustment without sufficient historical data.

---

## 39. Turn the annual report into useful discoveries

After the public report exists:

1. Match its books to her unified library.
2. Identify books already read.
3. Identify books already on Goodreads.
4. Select genuinely new candidates.
5. Apply the recommendation engine.

Each discovery should explain both:

- Why it belongs in the annual roundup.
- Why it may suit her.

It should include identifiers and source links, but it will not automatically add books to Goodreads.

### Phase 5 completion

The annual report should be independently useful, calendar-aware, source-labeled, and capable of producing personalized discoveries without confusing public and private data.

---

# Shared engineering and delivery rules

## 40. Technology and dependencies

### Initial core

- Python.
- SQLite.
- Configured CSV ingestion; no source-browser runtime dependency.
- HTTPX for optional metadata API requests.
- Typed internal records.
- A small CLI entry point.

Use standard-library functionality where it is sufficient.

### Add later

- A separately approved live acquisition route and only the dependencies it needs.
- NumPy and SciPy for statistical calculations.
- pandas if it materially simplifies tabular analysis.
- scikit-learn when a learned recommender is justified.
- Optional local text processing only after simpler approaches are assessed.

Do not install or scaffold every future dependency at the start.

There is no need for a vector database, message queue, cloud cluster, or external language-model service initially.

---

## 41. Persistence and future database migration

SQLite is the actual persistent store—not an expendable cache.

Keep database-specific code separate from the statistics and recommendation logic.

For a future hosted multi-user product, PostgreSQL is a sensible candidate. That migration will include schema, query, concurrency, and operational work; it is not merely changing a connection string.

A website for one reader does not automatically require abandoning SQLite.

Keep generated databases, logs, caches, profiles, backups and credentials outside
source control. Preserve the useful local databases; the library exceeds GitHub's
regular-file size limit. Version the three supplied CSVs and nonsecret root
config. Any explicit database transfer needs suitable storage rather than a
normal Git commit. Code remains in:

```text
Q:\repos\TIMTS\BookyStats
```

Backups should use SQLite’s supported backup mechanism rather than blindly copying an actively changing database.

---

## 42. A future API layer without building it now

The application services should already return structured results.

Later, an HTTP layer can expose operations such as:

- Reading stored library data.
- Retrieving statistics.
- Requesting recommendations.
- Reading annual reports.
- Starting and checking a synchronization job.

Long-running synchronization should run as a job, not keep a website request open while a browser traverses thousands of records.

The future frontend should never need to know whether a fact came from an API, RSS, or a browser page. It receives the fact together with its source and freshness.

Multi-user authentication, tenancy, and hosted scheduling are later work—not hidden assumptions that the local script already solves.

---

## 43. Reproducibility

Each derived run should reference:

- Source snapshot identifiers.
- Metadata observations.
- Calculation version.
- Feature definitions.
- Model version where applicable.
- Configuration.
- Random seed where relevant.
- Time period and cutoff.

Identical inputs and settings should reproduce the same results.

Refreshing a timestamp alone should not trigger unnecessary model retraining. A changed review, rating, identity match, or relevant metadata field may.

A changed historical record can legitimately change a regenerated annual report. The report version should make that explainable.

---

## 44. What we deliberately will not build yet

- A website or app.
- A public HTTP service.
- Extra commands for features that do not exist.
- Images, charts, PDFs, or social cards.
- Automatic external writes.
- Multi-user social comparison.
- A universal reader personality score.
- Population percentiles without population data.
- Daily activity statistics without activity records.
- A large-model dependency for basic arithmetic or ingestion.
- An export workflow hidden behind automation.

---

## 45. Implementation order within the agreed phases

| Milestone | Concrete outcome |
|---|---|
| **Configured CSV ingestion and processing — accepted** | Fixed inputs, raw-first bytes, independent scope publication and last-good retention passed actual and offline repeat/cache/missing-file/recovery checks. Provider completeness is separate. |
| **Advanced explicit files and internal replay — retain** | Preserve legacy explicit flags/replay, supplied rows/fields and raw lineage; only explicit mode may replay unspecified archived inputs. |
| **Statistical capability inventory — implemented** | Pin compatible processed inputs and classify analyses as supported, subset-only, enrichment-dependent, observation-dependent or unsupported. |
| **Backend statistical engine — accepted** | All-Read profile, enjoyment/content, descriptive watchlist comparison, separate caches, offline status and three-worker calculations passed the 644-test gate plus actual/offline CLI acceptance. Dated/review capabilities remain evidence-gated. |
| **Watchlist ranking** | Generate explainable next-book recommendations |
| **Live acquisition — deferred** | Implement and validate an approved route, account binding, full scope coverage, repeats and unattended evidence; do not keep dead browser scaffolding speculatively. |
| **Durable task engine and external cron — deferred** | Add persisted dependencies/retry/resume and verify unattended execution before explicitly enabling an agreed external cadence. Not a prerequisite for backend analytics. |
| **Personal annual review — deferred** | Assemble a correct reading-year report |
| **Public annual review — deferred** | Build the calendar-year report and discovery bridge |

**Remaining: complete provider enrichment when authorized and operationally
available; watchlist ranking later. Live acquisition, durable orchestration, scheduling and annual
reviews remain deferred. No frontend or new documentation/spec folders are requested.**
