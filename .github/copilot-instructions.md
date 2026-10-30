# Repository instructions

## Scope and structure

- This is a Python 3.12+ local-first ingestion package. Public commands are only
  `booky sync` and `booky status`; `--scheduled` is private task-runner plumbing.
- Keep CLI, application service, domain contracts, adapters, and storage separate.
  Reuse `interfaces.py` protocols; keep service logic reusable by a future HTTP API.
- Follow the four-stage architecture in `PLAN.md`: raw capture, processing and
  enrichment, cached analysis, then watchlist ranking. Implement only capture and
  processing now. Manual exports come first; automatic capture comes next.
- P0 is manually supplied exports and explicitly invoked CLI processing.
  Weekly scheduling/cron and auto-export are next in queue, not part of P0.
  Do not add a website, background pipeline service, or broker for these stages.
- Use meaningful names, plain modular folders, and tests organized by module.
- Keep the detailed phased product roadmap in the root `PLAN.md`. Do not add
  spec, plan, forge, or process-paperwork folders, or phase labels to implementation
  modules.
- Do not implement images, a frontend, statistics, ranking, or annual reviews now.

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

- StoryGraph owns personal history, ratings, reviews, rereads, and status.
  Goodreads supplies the to-read/watchlist, not authoritative personal ratings.
  Keep personal and community ratings separate.
- Preserve unknown/unavailable, empty, unsupported, and failed states; do not
  turn missing data into zero or invent dates. Retain date precision, observation
  scope, account identity, and source provenance.
- Match books/editions conservatively. Ambiguous candidates are not confirmed
  matches. Keep repeats idempotent and source snapshot publication independently
  atomic; partial/failed collection must retain the last complete source snapshot.
- Keep the authoritative library separate from the metadata cache. Isolate
  account browser profiles and reject accidental account replacement.
- Share the service's lazy Playwright runtime across connectors, but keep
  browser contexts and persistent profiles separate by source/account.
- Accept explicitly supplied official exports and store original bytes in the
  raw database before parsing. Preserve unknown source fields and full provider
  responses; make processed snapshots replayable with raw lineage.
- A complete file import is not a verified complete account collection and must
  never qualify as unattended/weekly collection evidence.
- Keep manual files and normal-browser/RSS capture explicit; never silently fall
  back between them. Sign-in is ordinary visible-browser interaction only.
  Do not bypass credential controls, bot protection, navigation guards, or downloads.
- Protect keys, cookies, profiles, databases, and personal payloads. Do not put
  credentials in chat, logs, fixtures, or source. Status must not fetch source data.
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
