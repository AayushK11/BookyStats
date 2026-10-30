# Contributing

Read [README.md](README.md) for supported behavior and limitations, and
`.github\copilot-instructions.md` for repository invariants. Keep changes focused
on the local ingestion package; do not add unrequested products or process paperwork.

## Module boundaries

All application modules live under `src\bookystats`:

| Module | Responsibility |
| --- | --- |
| `cli.py`, `__main__.py` | Argument parsing, dependency wiring, console output, exit codes. |
| `sync.py` | Application service: coordinate account ingestion and metadata enrichment. |
| `interfaces.py` | Protocols for source, metadata, transport, progress, and storage adapters. |
| `models.py`, `dates.py`, `identifiers.py`, `matching.py` | Data contracts, date precision, identity normalization, conservative matching. |
| `connectors\` | StoryGraph account data and Goodreads to-read collection. |
| `raw.py`, `imports.py` | Durable original-input archive and offline export parsing. |
| `verify.py`, `report.py`, `runlog.py` | Post-sync checks, console/status report lines, per-run log files. |
| `providers\` | Optional Google Books and Open Library metadata. |
| `browser.py`, `net.py` | Guarded browser/HTTP access and bounded requests. |
| `storage.py`, `cache.py` | Authoritative SQLite library and separate metadata cache. |
| `config.py`, `locking.py`, `scheduling.py` | Local settings, sync exclusion, guarded Windows scheduling. |
| `errors.py`, `redaction.py` | Explicit failures and sensitive-value redaction. |
| `strings.py`, `constants.py` | Centralized literals and shared fixed policy declarations. |

Keep console concerns out of the application service, and parsing out of storage.
Use the existing protocols to inject adapters in tests. Raw files must be committed
before parsing; manual file completion is not verified account completeness.
Use [TODO.md](TODO.md) to track the current scope and remaining acceptance checks.
This separation is intended
to support a future HTTP API; no HTTP API currently exists.

## Development

Use the virtual environment from the README; install development dependencies with:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Start with tests for the changed module, including the literal-policy check after
Python changes, for example:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_sync.py tests\test_literal_policy.py
```

For cross-cutting changes and before submitting, run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m build
```

Mypy is strict. Reuse existing dependencies and tools; do not add tooling just to
avoid an existing check.

`.github\workflows\ci.yml` runs these checks on Ubuntu with Python 3.12 and Windows
with Python 3.13, including the local Chromium tests. It uses no account credentials.

## Test boundaries

- Keep tests organized by module under `tests`, with sanitized source fixtures in
  `tests\fixtures`. Add focused regression cases for changed behavior, not tests of
  trivial constants or accessors.
- `tests\conftest.py` points `BOOKYSTATS_DATA_DIR` at a temporary folder for every
  test, so tests never write to the checkout `data` folder.
- Fixture/transport tests and the runtime integration test do not validate real
  account access. The runtime integration test uses real local persistence with
  injected source and metadata adapters.
- The `browser`-marked tests exercise real Chromium against a local test server
  and verify shared-driver lifecycle with isolated profiles, not source access.
  Install Chromium as documented in the README; these tests skip if the browser
  is unavailable. Run them alone with
  `.\.venv\Scripts\python.exe -m pytest -q -m browser`.
- Real-account/provider checks require explicit opt-in and authorized local
  configuration. Never hide them in the default test run; a `live` marker by itself
  does not prevent pytest from running a test.
- Never commit credentials, session cookies, private profile data, or live payloads.
  Distinguish fixture, local-browser, and live evidence in reports; do not claim
  unattended authentication or scheduled execution from mocked tests.

All first-party Python literals, including those in tests, follow the centralization
rules in `.github\copilot-instructions.md`. `tests\test_literal_policy.py` enforces
the literal placement; do not weaken or bypass it. Update directly related
documentation when behavior changes.
