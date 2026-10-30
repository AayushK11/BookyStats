# BookyStats TODO

The target architecture and detailed requirements live in [PLAN.md](PLAN.md).
This checklist tracks delivery, not just code written. Initial scope is manual
CLI ingestion and processing; later pipelines are not part of that scope.

## Architecture

- [x] Save the four-stage architecture and database-handoff diagram.
- [x] Set manual exports and explicitly invoked CLI processing as the initial priority.
- [x] Queue scheduled capture/auto-export next; defer analysis, ranking, and annual reviews.

## Raw capture

- [x] Store original StoryGraph and Goodreads export bytes in SQLite before parsing.
- [x] Preserve source/account binding, capture time, hashes, and prior captures.
- [x] Retain malformed input for diagnosis without publishing it as processed data.
- [x] Detect archive corruption and reject unsupported database schemas explicitly.
- [x] Archive full enrichment responses without recording authentication headers or echoed request credentials.

## Processing and enrichment

- [x] Parse both export formats, including quoting, multiline reviews, and ISBN wrappers.
- [x] Retain every supplied column, including currently unmapped fields.
- [x] Preserve all Goodreads export rows and derive watchlist membership from shelves.
- [x] Keep personal/community ratings separate and StoryGraph reading authority intact.
- [x] Preserve date precision, rereads where represented, and explicit missing/unsupported states.
- [x] Reject malformed or conflicting input without silently dropping rows.
- [x] Reuse conservative work/edition matching and preserve source provenance.
- [x] Connect Google Books/Open Library enrichment to raw response capture and processed storage.
- [x] Link processed snapshots to raw document IDs and processing versions.
- [x] Reprocess archived input without the original files or fresh account access.
- [x] Keep repeated imports idempotent and preserve the last usable snapshot on failure.
- [x] Distinguish complete-file processing from verified complete-account collection.

## CLI and structure

- [x] Provide explicit file input, replay, and metadata-provider selection through the CLI.
- [x] Keep manual processing from opening source browsers or qualifying as weekly-run evidence.
- [x] Keep all Python strings/bytes in `strings.py` and other constants in `constants.py`.
- [x] Keep implementation in the existing package and tests grouped by module.
- [x] Update operation/development documentation without adding loose helper scripts.

## Verification

- [x] Run focused raw-storage, parsing, replay, CLI, and enrichment regressions.
- [x] Run the full test suite, literal-policy checks, Ruff, strict mypy, and package build.
- [x] Check the final changes against this checklist and the architecture.
- [ ] Process the user's actual exports and reconcile supplied rows/fields when files arrive.

## Next: automatic acquisition

- [x] Research non-manual capture and auto-export options with cited evidence in `PLAN.md`.
- [ ] Select and validate authorized capture routes for both sources.
- [ ] Feed automated captures into the same raw database boundary.
- [ ] Validate unattended execution, then expose/configure weekly scheduling through the CLI.
- [ ] Do not treat replaying an old export as fresh weekly ingestion.

## Later

- [ ] Build reusable analysis and preference-weight snapshots from processed data.
- [ ] Rank the processed Goodreads watchlist using cached weights and explanations.
- [ ] Add personal Year in Review and Calendar Year in Books after the core pipelines.
