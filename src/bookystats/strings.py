# All first-party Python text and byte literals live here, including test values.
# Configuration files and source HTML/XML fixtures are declarative data, not code literals.
from __future__ import annotations

from typing import Final, Literal

# Live metadata run policy and regression cases.
META_RUN_LANGUAGE_PATTERN: Final = "[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*"
META_RUN_HALTED_MESSAGE: Final = (
    "Provider collection stopped after an authorization, quota, or request-budget failure; "
    "remaining books are deferred."
)
META_RUN_TEST_LANGUAGE: Final = "zh-CN"
META_RUN_TEST_TIMESTAMP: Final = "2025-07-02T00:00:00+02:00"
META_RUN_TEST_DATE: Final = "2025-07-02"
META_RUN_TEST_MALFORMED_WORK_KEY: Final = "/works/OL123M"

type InputKind = Literal["live", "file"]
INPUT_LIVE: Final = "live"
INPUT_FILE: Final = "file"
INPUT_KIND: Final = "input_kind"
INPUT_PROCESSING_VERSION: Final = "processing_version"
TERMINATION_VERIFIED: Final = "termination_verified"
INPUT_TEST_RAW_ID: Final = "fixture-capture"
INPUT_TEST_VERSION: Final = "fixture-v1"
INPUT_RAW_DOCUMENT_ID: Final = "raw_document_id"
CLI_STORYGRAPH_FILE: Final = "--storygraph-file"
CLI_GOODREADS_FILE: Final = "--goodreads-file"
CLI_METADATA: Final = "--metadata"
CLI_RAW_DATABASE: Final = "raw.sqlite3"
CLI_FILE_HELP: Final = "Archive and process an official CSV export for the configured account."
CLI_FILE_MODE_CONFLICT: Final = (
    "File input cannot be combined with interactive or scheduled capture."
)
CLI_STATUS_FILE_CONFLICT: Final = "File input is only valid for sync."
CLI_NO_RAW_INPUT: Final = (
    "No archived exports are available for the configured accounts. Supply "
    "a source export explicitly or configure its CSV path in config.json."
)
CLI_UNCONFIGURED_FILE: Final = "Configure the source account before supplying its export."
CLI_FILE_SCOPE: Final = (
    "File processing only: source account ownership and full account coverage are not verified."
)
CLI_RAW_ARCHIVE: Final = "raw_archive"
CLI_TEST_STORYGRAPH_NAME: Final = "storygraph.csv"
CLI_TEST_GOODREADS_NAME: Final = "goodreads.csv"
CLI_TEST_EXTRA_COLUMN: Final = "Unmapped Field"
CLI_TEST_EXTRA_VALUE: Final = "kept"
CLI_TEST_STORYGRAPH_CSV: Final = (
    "Title,Authors,ISBN/UID,Read Status,Star Rating,Review,Last Date Read,"
    "Read Count,Unmapped Field\n"
    'Matilda,Roald Dahl,9780140328721,read,4.25,"Great,\nreally great",2025-06-01,1,kept\n'
)
CLI_TEST_GOODREADS_CSV: Final = (
    "Book Id,Title,Author,ISBN13,Exclusive Shelf,My Rating,Date Read,My Review,Unmapped Field\n"
    "123,Matilda,Roald Dahl,9780140328721,to-read,0,,,kept\n"
)
CLI_TEST_BROKEN_CSV: Final = 'Title,Authors,ISBN/UID,Read Status\n"unterminated'
CLI_TEST_UNEXPECTED_NETWORK: Final = "Manual offline processing must not make network requests."
CLI_TEST_FETCH: Final = "fetch"
CLI_TEST_RECORD_LIVE: Final = "record_live_run"
CLI_TEST_ENABLE_WEEKLY: Final = "enable_weekly"
CLI_TEST_MANUAL_SCHEDULE: Final = (
    "Manual imports must not record live evidence or activate scheduling."
)
CLI_TEST_CAPTURE: Final = "capture"
CLI_TEST_REQUIRE_ACTIVATION: Final = "require_activation"
CLI_TEST_SCHEDULE_GUARD: Final = "Scheduled collection remained noninteractive."
CLI_TEST_GOOGLE_KEY: Final = "fixture-google-key"
CLI_TEST_METADATA_BODY: Final = (
    '{"totalItems":1,"items":[{"id":"fixture-volume","volumeInfo":{"title":"Matilda",'
    '"authors":["Roald Dahl"],"industryIdentifiers":[{"type":"ISBN_13",'
    '"identifier":"9780140328721"}],"description":"A synthetic catalog description.",'
    '"pageCount":240,"publishedDate":"1988","language":"en",'
    '"publisher":"Fixture Publisher","futureField":{"label":"kept"}}}]}'
)
PROVIDER_FULL_RESPONSE: Final = "full-public-records"
PROVIDER_ALL_FIELDS: Final = "*"
INPUT_MISSING_RAW_DOCUMENT: Final = (
    "A file snapshot must reference its stored raw document and processing version."
)

SOURCE_FOLDER: Final = "src"
PYTHON_PATTERN: Final = "*.py"
STRINGS_MODULE_FILE: Final = "strings.py"
CONSTANTS_MODULE_FILE: Final = "constants.py"
TYPE_CALLABLE: Final = "Callable"
TYPE_OPTIONAL: Final = "Optional"
TYPE_LITERAL: Final = "Literal"
TYPE_UNION: Final = "Union"
LITERAL_POLICY_LOCATION: Final = "{path}:{line}: {value!r}"
INTEGRATION_BOOK_ID: Final = "fixture-book"
INTEGRATION_NEW_BOOK_ID: Final = "fixture-next"
INTEGRATION_TITLE: Final = "Matilda"
INTEGRATION_NEW_TITLE: Final = "The Witches"
INTEGRATION_AUTHOR: Final = "Roald Dahl"
INTEGRATION_ISBN: Final = "9780140328721"
INTEGRATION_READ_DATE: Final = "2025-06-01"
INTEGRATION_STORYGRAPH_BOOK: Final = "https://app.thestorygraph.com/books/fixture-book"
INTEGRATION_GOODREADS_BOOK: Final = "https://www.goodreads.com/book/show/123"
INTEGRATION_METADATA_ID: Final = "fixture-volume"
INTEGRATION_METADATA_URL: Final = "https://www.googleapis.com/books/v1/volumes/fixture-volume"
RECORDS: Final = "records"
EXPECTED_COUNT: Final = "expected_count"
SNAPSHOT_REJECTED: Final = "snapshot_rejected"
PROVIDER_COOLDOWN: Final = "provider_cooldown"
PROVIDER_COOLDOWN_MESSAGE: Final = (
    "The provider requested a cooldown. Remaining metadata work is deferred; retry later."
)
INVALID_ACTIVATION: Final = "The saved weekly activation receipt is invalid."
SCHEDULE_REVALIDATION_REQUIRED: Final = (
    "Weekly execution is not validated for this implementation, account configuration, "
    "interpreter, or schedule. Complete the required syncs and activate the schedule again."
)
TASK_XML_READER: Final = "Get-Content -Raw -Encoding UTF8 -LiteralPath {path}"
REPLACE_ACCOUNT: Final = "replace_account"
METADATA_ENABLED: Final = "metadata_enabled"
ALTERNATE_READER: Final = "another-reader"
ALTERNATE_READER_PROFILE: Final = "https://app.thestorygraph.com/profile/another-reader"
ALTERNATE_SCHEDULE_TIME: Final = "10:00"
UNICODE_TEST_FOLDER: Final = "r\u00e9sum\u00e9"
POWERSHELL_XML_ROUNDTRIP: Final = (
    "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(({expression})))"
)
WINDOWS_ONLY_TEST_REASON: Final = "Requires Windows PowerShell for the UTF-8 XML reader."
TEST_SCHEDULING_FINGERPRINT: Final = "implementation_fingerprint"
TEST_UNEXPECTED_SERVICE_START: Final = "An unvalidated scheduled run started source collection."
MAX_ATTEMPTS: Final = "max_attempts"
LITERAL_CASE_FIELDS: Final = "name,source"
LITERAL_TEST_MODULE: Final = "other_module"
MISPLACED_TEXT_SOURCE: Final = "VALUE = 'not centralized'\n"
MISPLACED_NUMBER_SOURCE: Final = "VALUE = 42\n"
TEST_BUILD_SERVICE: Final = "_build_service"
WEEKLY: Final = "weekly"

FCNTL: Final = "fcntl"
FLOCK: Final = "flock"
LOCK_EX: Final = "LOCK_EX"
LOCK_NB: Final = "LOCK_NB"
LOCK_UN: Final = "LOCK_UN"
MSVCRT: Final = "msvcrt"
LOCKING: Final = "locking"
LK_NBLCK: Final = "LK_NBLCK"
LK_UNLCK: Final = "LK_UNLCK"

INIT_VERSION_TEXT: Final = "0.1.0"
HTML_PARSER: Final = "html.parser"
SPACE: Final = " "
EMPTY: Final = ""
NEEDS_AUTH: Final = "needs_auth"
HTTPS: Final = "https"
NT: Final = "nt"
PAGE: Final = "page"
GET: Final = "GET"
LOCATION: Final = "location"
FAILED: Final = "failed"
REDIRECT_LOOP: Final = "redirect_loop"
REDIRECT_LIMIT: Final = "redirect_limit"
CACHE_CHECKSUM_TEMPLATE: Final = "{v0:.17g}\x00{v1}"
CACHE_METADATACACHE_INIT_PRAGMA_QUICK_CHECK: Final = "PRAGMA quick_check"
OK: Final = "ok"
CACHE_METADATACACHE_INIT_METADATA_CACHE_IS_CORRUPT_REPAIR_OR_REMOVE: Final = (
    "Metadata cache is corrupt; repair or remove it."
)
CACHE_METADATACACHE_INIT_CREATE_TABLE_IF_NOT_EXISTS_METADATA_CACHE: Final = (
    "CREATE TABLE IF NOT EXISTS metadata_cache (\n                        provide"
    "r TEXT NOT NULL,\n                        cache_key TEXT NOT NULL,\n        "
    "                payload TEXT NOT NULL,\n                        expires_at R"
    "EAL NOT NULL,\n                        checksum TEXT NOT NULL,\n            "
    "            PRIMARY KEY (provider, cache_key)\n                    )"
)
CACHE_METADATACACHE_INIT_METADATA_CACHE_COULD_NOT_BE_OPENED_SAFELY: Final = (
    "Metadata cache could not be opened safely."
)
CACHE_METADATACACHE_DB_METADATA_CACHE_IS_CLOSED: Final = "Metadata cache is closed."
CACHE_METADATACACHE_KEY_ONLY_PUBLIC_METADATA_PROVIDERS_MAY_USE_THIS: Final = (
    "Only public metadata providers may use this cache."
)
CACHE_METADATACACHE_KEY_A_PUBLIC_CATALOG_CACHE_KEY_IS_REQUIRED: Final = (
    "A public catalog cache key is required."
)
CACHE_METADATACACHE_KEY_METADATA_CACHE_KEY_IS_NOT_VALID_UNICODE: Final = (
    "Metadata cache key is not valid Unicode."
)
METADATACACHE_GET_ROW_SELECT_PAYLOAD_AT_CHECKSUM_FROM_METADATA: Final = (
    "SELECT payload, expires_at, checksum FROM metadata_cache WHERE provider = ? AND cache_key = ?"
)
CACHE_METADATACACHE_GET_METADATA_CACHE_COULD_NOT_BE_READ_SAFELY: Final = (
    "Metadata cache could not be read safely."
)
CACHE_METADATACACHE_GET_METADATA_CACHE_CONTAINS_A_DAMAGED_ENTRY: Final = (
    "Metadata cache contains a damaged entry."
)
CACHE_METADATACACHE_GET_METADATA_CACHE_CONTAINS_INVALID_JSON: Final = (
    "Metadata cache contains invalid JSON."
)
CACHE_METADATACACHE_GET_METADATA_CACHE_CONTAINS_INVALID_CATALOG_DATA: Final = (
    "Metadata cache contains invalid catalog data."
)
CACHE_METADATACACHE_PUT_METADATA_CACHE_TTL_MUST_BE_A_NONNEGATIVE: Final = (
    "Metadata cache TTL must be a nonnegative integer."
)
COMMA: Final = ","
COLON: Final = ":"
CACHE_METADATACACHE_PUT_METADATA_CACHE_ONLY_FINITE_JSON_CATALOG: Final = (
    "Metadata cache accepts only finite JSON catalog data."
)
CACHE_METADATACACHE_PUT_INSERT_INTO_CACHE_PROVIDER_CACHE_KEY: Final = (
    "INSERT INTO metadata_cache (provider, cache_key, payload, expires_at, checks"
    "um) VALUES (?, ?, ?, ?, ?) ON CONFLICT(provider, cache_key) DO UPDATE SET pa"
    "yload = excluded.payload, expires_at = excluded.expires_at, checksum = exclu"
    "ded.checksum"
)
CACHE_METADATACACHE_PUT_METADATA_CACHE_COULD_NOT_BE_WRITTEN_SAFELY: Final = (
    "Metadata cache could not be written safely."
)
CACHE_METADATACACHE_CLOSE_METADATA_CACHE_COULD_NOT_BE_CLOSED_SAFELY: Final = (
    "Metadata cache could not be closed safely."
)
BOOKY: Final = "booky"
PARSER_RESULT_DESCRIPTION_READ_ONLY_READING_DATA_SYNC_REPORTS_READ: Final = (
    "Process configured reading-data CSVs. Status reads only local state."
)
COMMAND: Final = "command"
SYNC: Final = "sync"
FETCH: Final = "fetch"
STATUS: Final = "status"
FETCH_RESOURCE_PACKAGE: Final = "bookystats.adapters.exports"
FETCH_RESOURCE_FILE: Final = "goodreads_console.js"
FETCH_ACCOUNT_PLACEHOLDER: Final = "__BOOKYSTATS_GOODREADS_ACCOUNT_JSON__"
FETCH_HELPER_FILE: Final = "goodreads-export.txt"
FETCH_HELPER_PATH: Final = "helper_path"
FETCH_READ_URL: Final = "read_url"
FETCH_WATCHLIST_URL: Final = "watchlist_url"
FETCH_SCOPE_NOTICE: Final = "scope_notice"
FETCH_ACCOUNT_PATTERN: Final = r"[1-9][0-9]*"
FETCH_ACCOUNT_REQUIRED: Final = (
    "Configure a Goodreads profile with a numeric account ID before generating its helper."
)
FETCH_TEMPLATE_INVALID: Final = "The packaged Goodreads helper template is invalid."
FETCH_SCHEDULED_CONFLICT: Final = (
    "fetch generates a local helper; it cannot run as scheduled collection."
)
FETCH_SHELF_URL: Final = (
    "https://www.goodreads.com/review/list/{account_id}?shelf={shelf}&view=table&per_page=100"
)
FETCH_SCOPE_MESSAGE: Final = (
    "Manual Goodreads shelf capture only, not verified account completeness. "
    "No source requests, browser session, credentials or CSV inputs are changed by this command."
)
FETCH_INSTRUCTIONS: Final = (
    "Goodreads console helper: {path}\n"
    "Open Read: {read_url}\n"
    "Open watchlist: {watchlist_url}\n"
    "Run the helper separately on each shelf in your normal browser session. "
    "It downloads one CSV after that shelf's pages finish; source blocking stops it.\n"
    "Keep original exports. Update the configured CSV paths to refer to new files, or supply "
    "all required paths to sync with --storygraph-file, --goodreads-read-file and "
    "--goodreads-watchlist-file.\n"
    "StoryGraph ratings still require your supplied export. {scope_notice}"
)
CLI_PARSER_DATA_DIR: Final = "--data-dir"
CLI_PARSER_HELP_OVERRIDE_THE_PRIVATE_LOCAL_DATA_DIRECTORY: Final = (
    "Override the private local data directory."
)
CLI_PARSER_JSON: Final = "--json"
STORE_TRUE: Final = "store_true"
CLI_PARSER_HELP_PRINT_A_STRUCTURED_RECEIPT: Final = "Print a structured receipt."
CLI_PARSER_INTERACTIVE: Final = "--interactive"
CLI_PARSER_HELP_ALLOW_VISIBLE_ACCOUNT_SIGN_IN: Final = "Allow visible account sign-in."
CLI_PARSER_UNATTENDED: Final = "--unattended"
CLI_PARSER_HELP_NEVER_PROMPT_OR_WAIT_FOR_SIGN_IN: Final = "Never prompt or wait for sign-in."
CLI_PARSER_SCHEDULED: Final = "--scheduled"
CLI_SETUP_STORYGRAPH_READER_PROFILE_URL_BLANK_TO_SKIP: Final = (
    "StoryGraph reader profile URL (blank to skip): "
)
CLI_SETUP_GOODREADS_READER_PROFILE_URL_BLANK_TO_SKIP: Final = (
    "Goodreads reader profile URL (blank to skip): "
)
CLI_SETUP_NO_ACCOUNT_PROFILES_WERE_PROVIDED_NO_REQUESTS: Final = (
    "No account profiles were provided; no requests were made."
)
ACCOUNTS: Final = "accounts"
LIBRARY_SQLITE3: Final = "library.sqlite3"
APP_THESTORYGRAPH_COM: Final = "app.thestorygraph.com"
WWW_GOODREADS_COM: Final = "www.goodreads.com"
GOODREADS_COM: Final = "goodreads.com"
METADATA_SQLITE3: Final = "metadata.sqlite3"
GOOGLE_BOOKS_API_KEY: Final = "GOOGLE_BOOKS_API_KEY"
WWW_GOOGLEAPIS_COM: Final = "www.googleapis.com"
CLI_BUILD_SERVICE_USER_AGENT_BOOKYSTATS: Final = "BookyStats/0.1"
CLI_BUILD_SERVICE_TEMPLATE: Final = " ({v0})"
OPENLIBRARY_ORG: Final = "openlibrary.org"
CLI_PRINT_RECEIPT_LAST_GOOD_SOURCE_SNAPSHOTS_REMAIN_AVAILABLE_THIS: Final = (
    "Last good source snapshots remain available; this is not a complete account sync."
)
LIBRARY: Final = "library"
SOURCES: Final = "sources"
LAST_RUN: Final = "last_run"
STATE: Final = "state"
NOT_SYNCED: Final = "not_synced"
DATA_DIRECTORY: Final = "data_directory"
CONFIGURED_SOURCES: Final = "configured_sources"
SCHEDULE: Final = "schedule"
GOOGLE_BOOKS_KEY_CONFIGURED: Final = "google_books_key_configured"
CLI_PRINT_STATUS_BOOKYSTATS_STATUS_LOCAL_DATA_NO_SOURCE_REQUESTS: Final = (
    "BookyStats status (local data; no source requests)"
)
UNDERSCORE: Final = "_"
CLI_MAIN_WEEKLY_SCHEDULING_IS_DISABLED_NO_SOURCE_REQUESTS: Final = (
    "Weekly scheduling is disabled; no source requests were made."
)
CLI_MAIN_CONFIGURE_READER_PROFILE_URLS_IN_CONFIG_JSON: Final = (
    "Configure reader profile URLs in config.json or BOOKYSTATS_STORYGRAPH_PROFILE "
    "/ BOOKYSTATS_GOODREADS_PROFILE before syncing."
)
SCHEDULED: Final = "scheduled"
MANUAL: Final = "manual"
CLI_MAIN_A_LOCAL_DATA_CONFIGURATION_OR_RECORD_VALIDATION: Final = (
    "A local data, configuration, or record-validation operation failed. The run "
    "is not reported as successful; inspect the local status before retrying."
)
CLI_MAIN_SYNC_INTERRUPTED_NO_INCOMPLETE_SOURCE_SNAPSHOT_IS: Final = (
    "Sync interrupted; no incomplete source snapshot is reported as current."
)
AFTER: Final = "after"
MON: Final = "MON"
TUE: Final = "TUE"
WED: Final = "WED"
THU: Final = "THU"
FRI: Final = "FRI"
SAT: Final = "SAT"
SUN: Final = "SUN"
CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_EXPLICIT_BE_MON_THROUGH_SUN: Final = (
    "weekday must be MON through SUN"
)
CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_EXPLICIT_TIME_D_D: Final = "(?:[01]\\d|2[0-3]):[0-5]\\d"
CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_EXPLICIT_TIME_MUST_BE_HH_MM: Final = (
    "schedule time must be HH:MM"
)
CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_AN_EXPLICIT_DAY_TIME: Final = (
    "weekly scheduling requires an explicit day, time, and time zone"
)
CONFIG_SETTINGS_ONE_ACCOUNT_PER_SOURCE_CAN_HAVE_ONLY_ONE_READER: Final = (
    "each source can have only one reader in this database"
)
BOOKYSTATS_DATA_DIR: Final = "BOOKYSTATS_DATA_DIR"
BOOKYSTATS: Final = "BookyStats"
CONFIG_ACCOUNT_FROM_URL_MATCHED_PROFILE_A_ZA_Z0_A_ZA_Z0: Final = (
    "/profile/([A-Za-z0-9][A-Za-z0-9_.-]*)/?"
)
CONFIG_ACCOUNT_FROM_URL_MATCHED_USER_SHOW_D: Final = "/user/show/(\\d+)(?:-[^/]+)?/?"
CONFIG_ACCOUNT_FROM_URL_ONLY_STORYGRAPH_AND_GOODREADS_CAN_BE_READER: Final = (
    "Only StoryGraph and Goodreads can be reader accounts."
)
CONFIG_ACCOUNT_FROM_URL_TEMPLATE: Final = "Use a reader profile URL for {v0}."
CONFIG_ACCOUNT_FROM_URL_TEMPLATE_2: Final = (
    "The {v0} profile URL is not a valid HTTPS reader profile."
)
CONFIG_JSON: Final = "config.json"
CONFIG_LOAD_SETTINGS_CONFIG_JSON_IS_INVALID_CHECK_ITS_FIELDS: Final = (
    "config.json is invalid. Check its fields and profile URLs; existing data is unchanged."
)
BOOKYSTATS_STORYGRAPH_PROFILE: Final = "BOOKYSTATS_STORYGRAPH_PROFILE"
BOOKYSTATS_GOODREADS_PROFILE: Final = "BOOKYSTATS_GOODREADS_PROFILE"
ATOMIC_WRITE_PREFIX_TEMPLATE: Final = ".{v0}."
W: Final = "w"
UTF_8: Final = "utf-8"
NEWLINE: Final = "\n"
PROFILES: Final = "profiles"
GOODREADS_SAFE_URL_TEXT: Final = "?"
SHELF: Final = "shelf"
TO_READ: Final = "to-read"
PER_PAGE: Final = "per_page"
TITLE: Final = "title"
INVALID_DATE: Final = "invalid_date"
INVALID_NUMBER: Final = "invalid_number"
INVALID_ISBN: Final = "invalid_isbn"
ISBNS: Final = "isbns"
EDITION: Final = "edition"
READ: Final = "read"
CURRENTLY_READING: Final = "currently-reading"
INVALID_RECORD: Final = "invalid_record"
ID: Final = "id"
FALSE_2: Final = "false"
ISBN: Final = "isbn"
ADDED_AT: Final = "added_at"
READER: Final = "reader"
PUBLICATION_DATE: Final = "publication_date"
PAGE_COUNT: Final = "page_count"
COMMUNITY_RATING: Final = "community_rating"
WORK: Final = "work"
GOODREADS_PERSONAL_RATING: Final = "goodreads_personal_rating"
AUTHOR_NAME: Final = "author_name"
RATING: Final = "rating"
FIRST_PUBLICATION_YEAR: Final = "first_publication_year"
COMMUNITY_RATINGS_COUNT: Final = "community_ratings_count"
SHELF_POSITION: Final = "shelf_position"
SHELVES: Final = "shelves"
WATCHLIST: Final = "watchlist"
ACCEPT: Final = "Accept"
UTF_8_SIG: Final = "utf-8-sig"
REVIEW: Final = "review"
READING_EVENTS: Final = "reading_events"
READ_COUNT: Final = "read_count"
MOODS: Final = "moods"
PACE: Final = "pace"
TAGS: Final = "tags"
CONTENT_WARNINGS: Final = "content_warnings"
READING: Final = "reading"
PAUSED: Final = "paused"
DNF: Final = "dnf"
STARTED: Final = "started"
FINISHED: Final = "finished"
LANGUAGE: Final = "language"
EDITION_FORMAT: Final = "edition_format"
TRUE_2: Final = "true"
STYLE: Final = "style"
SCRIPT: Final = "script"
HYPHEN: Final = "-"
EXPORT: Final = "export"
SLASH: Final = "/"
BOOKS: Final = "books"
AUTHORS: Final = "authors"
TIME: Final = "time"
JSON: Final = "json"
COLLECTIONS: Final = "collections"
OBSERVATIONS: Final = "observations"
DETAIL_CHECKED_AT: Final = "detail_checked_at"
NEW: Final = "new"
VALUE: Final = "value"
DATES_PARSE_DATE_D_D_D: Final = "\\d{4}(?:-\\d{2}(?:-\\d{2})?)?"
DATES_PARSE_DATE_D_D_D_2: Final = "\\d{4}/\\d{2}/\\d{2}"
DATES_PARSE_DATE_D_D_D_T: Final = "\\d{4}-\\d{2}-\\d{2}T"
Z: Final = "Z"
DATES_PARSE_DATE_PARSED_TEXT: Final = "+00:00"
DATES_PARSE_DATE_B_D_Y: Final = "%B %d, %Y"
DATES_PARSE_DATE_B_D_Y_2: Final = "%b %d, %Y"
DATES_PARSE_DATE_D_B_Y: Final = "%d %B %Y"
DATES_PARSE_DATE_D_B_Y_2: Final = "%d %b %Y"
DATES_PARSE_DATE_B_Y: Final = "%B %Y"
DATES_PARSE_DATE_B_Y_2: Final = "%b %Y"
DATES_PARSE_DATE_Y_M: Final = "%Y-%m"
DATES_PARSE_DATE_MON_TUE_WED_THU_FRI_SAT_SUN: Final = "(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),? "
DATES_PARSE_DATE_UNSUPPORTED_SOURCE_DATE: Final = "unsupported source date"
DATES_PARSE_DATE_AMBIGUOUS_OR_UNSUPPORTED_SOURCE_DATE: Final = (
    "ambiguous or unsupported source date"
)
COLLECTION_FAILED: Final = "collection_failed"
IDENTIFIERS_NORMALIZE_ISBN_TEXT: Final = '="'
IDENTIFIERS_NORMALIZE_ISBN_TEXT_2: Final = '"'
IDENTIFIERS_NORMALIZE_ISBN_CANDIDATE_S: Final = "[\\s-]"
IDENTIFIERS_NORMALIZE_ISBN_D_DX: Final = "\\d{9}[\\dX]"
X: Final = "X"
IDENTIFIERS_NORMALIZE_ISBN_PREFIX_TEXT: Final = "978"
IDENTIFIERS_NORMALIZE_ISBN_D: Final = "97[89]\\d{10}"
NFKC: Final = "NFKC"
IDENTIFIERS_NORMALIZED_TEXT_W_S: Final = "[^\\w\\s]"
SYNC_LOCK: Final = "sync.lock"
LAYOUT_DATABASES: Final = "databases"
LAYOUT_CREDENTIALS: Final = "credentials"
LAYOUT_RUNTIME: Final = "runtime"
LAYOUT_CONFLICT: Final = (
    "Both legacy and organized locations contain {filename}; no file was overwritten."
)
LAYOUT_INVALID_FILE: Final = (
    "Cannot organize {filename}: expected a regular local file, not a directory or symbolic link."
)
LAYOUT_DATABASE_BUSY: Final = (
    "Cannot organize {filename} while another connection has active journal state. "
    "No database was moved; retry after that connection closes."
)
LAYOUT_DATABASE_INVALID: Final = (
    "Cannot organize {filename}: SQLite integrity validation failed. Existing files are retained."
)
LAYOUT_INVALID_NAME: Final = "Unsupported runtime database filename."
LAYOUT_MIGRATED: Final = (
    "Organized {count} legacy runtime files into databases/credentials; "
    "contents and history retained."
)
LAYOUT_CHECKPOINT: Final = "PRAGMA wal_checkpoint(TRUNCATE)"
LAYOUT_SQLITE_EXISTING_QUERY: Final = "?mode=rw"
LAYOUT_INTEGRITY: Final = "PRAGMA integrity_check"
LAYOUT_SQLITE_OK: Final = "ok"
LAYOUT_WAL_SUFFIX: Final = "-wal"
LAYOUT_SHM_SUFFIX: Final = "-shm"
LAYOUT_JOURNAL_SUFFIX: Final = "-journal"
LAYOUT_TEST_CREATE: Final = "CREATE TABLE retained (value INTEGER NOT NULL)"
LAYOUT_TEST_INSERT: Final = "INSERT INTO retained VALUES (?)"
LAYOUT_TEST_SELECT: Final = "SELECT value FROM retained"
LAYOUT_TEST_WAL: Final = "PRAGMA journal_mode=WAL"
LAYOUT_TEST_NO_CHECKPOINT: Final = "PRAGMA wal_autocheckpoint=0"
LAYOUT_TEST_BEGIN_READ: Final = "BEGIN"
LAYOUT_TEST_FAILURE: Final = "Injected migration interruption."
LAYOUT_TEST_RENAME: Final = "rename"
LAYOUT_TEST_CREDENTIALS: Final = b"synthetic-private-credential-fixture\n"
SYNCLOCK_ENTER_HANDLE_A_B: Final = "a+b"
LOCKING_SYNCLOCK_ENTER_BYTES: Final = b"\x00"
LOCKING_SYNCLOCK_ENTER_ANOTHER_BOOKYSTATS_SYNC_IS_RUNNING_FOR_THIS: Final = (
    "Another BookyStats sync is running for this data directory; no duplicate sync started."
)
MATCHING_TITLE_AUTHOR_KEY_TEXT: Final = "\x1f"
MATCHING_TITLE_AUTHOR_KEY_TEXT_2: Final = "\x1e"
MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_FULL_TITLES_DIFFER: Final = (
    "ISBN agrees but full titles differ"
)
MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_AUTHOR_SETS_DIFFER: Final = (
    "ISBN agrees but author sets differ"
)
MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_EDITION_LANGUAGE_OR_FORMAT: Final = (
    "ISBN agrees but edition language or format differs"
)
MATCHING_COMPARE_BOOKS_VALIDATED_ISBN_FULL_TITLE_AND_AUTHORS_AGREE: Final = (
    "Validated ISBN, full title, and authors agree"
)
MATCHING_COMPARE_BOOKS_SHARED_ISBN_LACKS_SUFFICIENT_TITLE_AND_AUTHOR: Final = (
    "Shared ISBN lacks sufficient title and author corroboration"
)
MATCHING_COMPARE_BOOKS_EXACT_TITLE_AND_AUTHORS_WITHOUT_A_SHARED: Final = (
    "Exact title and authors without a shared trustworthy identifier"
)
MATCHING_COMPARE_BOOKS_NO_CORROBORATED_IDENTITY_EVIDENCE: Final = (
    "No corroborated identity evidence"
)
FORBID: Final = "forbid"
MODELS_PARTIALDATE_VALID_DATE_DATE_MUST_HAVE_YYYY_YYYY_MM_OR: Final = (
    "date must have YYYY, YYYY-MM, or YYYY-MM-DD precision"
)
MODELS_PARTIALDATE_VALID_DATE_YEAR_IS_OUTSIDE_THE_SUPPORTED_RANGE: Final = (
    "year is outside the supported range"
)
MODELS_PARTIALDATE_VALID_DATE_MONTH_IS_OUTSIDE_THE_SUPPORTED_RANGE: Final = (
    "month is outside the supported range"
)
MODELS_PARTIALDATE_VALID_DATE_DAY_IS_OUTSIDE_THE_SUPPORTED_RANGE: Final = (
    "day is outside the supported range"
)
YEAR: Final = "year"
MONTH: Final = "month"
DAY: Final = "day"
MODELS_OBSERVATION_CONSISTENT_STATE_A_OBSERVATION_MUST_HAVE_A: Final = (
    "a present observation must have a value"
)
MODELS_OBSERVATION_CONSISTENT_STATE_CANNOT_CONTAIN_INVENTED_VALUES: Final = (
    "non-present observations cannot contain invented values"
)
MODELS_READINGEVENT_ORDERED_DATES_READING_START_IS_AFTER_ITS_FINISH: Final = (
    "reading start is after its finish"
)
URL: Final = "url"
MODELS_BOOKRECORD_ABSOLUTE_URL_BOOK_MUST_BE_ABSOLUTE_HTTPS_URLS: Final = (
    "book links must be absolute HTTPS URLs without credentials"
)
MODELS_ACCOUNT_VALID_PROFILE_PROFILE_MUST_BE_AN_UNCREDENTIALED_HTTPS: Final = (
    "profile URL must be an uncredentialed HTTPS URL on the source host"
)
MODELS_ACCOUNT_VALID_PROFILE_IDENTIFY_THE_CONFIGURED_READER: Final = (
    "Goodreads profile must identify the configured reader, not an author"
)
ACCOUNT_VALID_PROFILE_MATCH_PROFILE: Final = "/profile/([^/]+)/?"
MODELS_ACCOUNT_VALID_PROFILE_IDENTIFY_THE_CONFIGURED_READER_2: Final = (
    "StoryGraph profile must identify the configured reader"
)
MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_MUST_BE_RECONCILED_BEFORE: Final = (
    "duplicate source IDs must be reconciled before publication"
)
MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_RECORD_FROM_ANOTHER_SOURCE: Final = (
    "snapshot contains a record from another source"
)
MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_IDENTITY_AND_PAGINATION: Final = (
    "complete snapshots require verified identity and pagination"
)
MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_DIFFERS_FROM_THE_EXPECTED: Final = (
    "complete snapshot count differs from the expected work count"
)
MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_CANNOT_BE_PUBLISHED_AS: Final = (
    "failed field extraction cannot be published as complete"
)
CONTENT_TYPE: Final = "content-type"
ETAG: Final = "etag"
LAST_MODIFIED: Final = "last-modified"
RETRY_AFTER: Final = "retry-after"
CONTENT_LENGTH: Final = "content-length"
NET_VALIDATE_SOURCE_URL_NAVIGATION_THE_CONFIGURED_SOURCE_IS_NOT: Final = (
    "Navigation outside the configured source is not allowed."
)
UNSAFE_URL: Final = "unsafe_url"
HTTPCLIENT_INIT_USER_AGENT_BOOKYSTATS_PERSONAL_READING_DATA_LOOKUP: Final = (
    "BookyStats/0.1 (personal reading-data lookup)"
)
NET_HTTPCLIENT_INIT_INVALID_HTTP_TIMEOUT_OR_INTERVAL_CONFIGURATION: Final = (
    "invalid HTTP host, timeout, or interval configuration"
)
NET_HTTPCLIENT_INIT_HTTP_LIMITS_MUST_BE_POSITIVE: Final = "HTTP limits must be positive"
USER_AGENT: Final = "User-Agent"
NET_HTTPCLIENT_THROTTLE_THE_CONFIGURED_BUDGET_WAS_REACHED_COLLECTION: Final = (
    "The configured request budget was reached; collection is incomplete."
)
REQUEST_BUDGET_EXHAUSTED: Final = "request_budget_exhausted"
NET_HTTPCLIENT_REQUEST_SOURCE_RESPONSE_THE_CONFIGURED_SIZE_LIMIT: Final = (
    "Source response exceeds the configured size limit."
)
RESPONSE_TOO_LARGE: Final = "response_too_large"
EMPTY_BYTES: Final = b""
NET_HTTPCLIENT_REQUEST_THE_SOURCE_REQUEST_TIMED_OUT: Final = "The source request timed out."
REQUEST_TIMEOUT: Final = "request_timeout"
NET_HTTPCLIENT_REQUEST_THE_SOURCE_CONNECTION_FAILED: Final = "The source connection failed."
NETWORK_ERROR: Final = "network_error"
NET_HTTPCLIENT_FETCH_THE_SOURCE_REDIRECTED_IN_A_LOOP: Final = "The source redirected in a loop."
NET_HTTPCLIENT_FETCH_SOURCE_REQUEST_DID_NOT_RETURN_A_RESPONSE: Final = (
    "Source request did not return a response."
)
NO_RESPONSE: Final = "no_response"
NET_HTTPCLIENT_FETCH_SOURCE_REDIRECT_HAS_NO_DESTINATION: Final = (
    "Source redirect has no destination."
)
INVALID_REDIRECT: Final = "invalid_redirect"
NET_HTTPCLIENT_FETCH_THE_SOURCE_EXCEEDED_THE_REDIRECT_LIMIT: Final = (
    "The source exceeded the redirect limit."
)
GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES: Final = (
    "https://www.googleapis.com/books/v1/volumes"
)
RATE_LIMITED: Final = "rate_limited"
QUOTA_EXCEEDED: Final = "quota_exceeded"
HTTP_429: Final = "http_429"
HTTP_ERROR: Final = "http_error"
UNEXPECTED_CONTENT: Final = "unexpected_content"
INVALID_RESPONSE: Final = "invalid_response"
API_ERROR: Final = "api_error"
UNSAFE_REDIRECT: Final = "unsafe_redirect"
GOOGLE_BOOKS_REJECT_CONSTANT_NON_FINITE_JSON_NUMBERS_ARE_NOT_CATALOG: Final = (
    "Non-finite JSON numbers are not catalog data."
)
GOOGLE_BOOKS_TEXT_TEXT: Final = "\x00"
INVALID_METADATA_FIELD: Final = "invalid_metadata_field"
FIELDS_ISSUE_MESSAGE_TEMPLATE: Final = (
    "Google Books returned an invalid {v0} value; it was not used."
)
INDUSTRYIDENTIFIERS: Final = "industryIdentifiers"
TYPE: Final = "type"
IDENTIFIER: Final = "identifier"
OTHER: Final = "OTHER"
ISSN: Final = "ISSN"
ISBN_10: Final = "ISBN_10"
ISBN_13: Final = "ISBN_13"
PUBLISHEDDATE: Final = "publishedDate"
AVERAGERATING: Final = "averageRating"
RATINGSCOUNT: Final = "ratingsCount"
INCONSISTENT_RATING: Final = "inconsistent_rating"
GOOGLE_BOOKS_RATINGS_MESSAGE_GOOGLE_A_COMMUNITY_MEAN_WITHOUT: Final = (
    "Google Books supplied a community mean without a valid positive count."
)
INCOMPLETE_RATING: Final = "incomplete_rating"
GOOGLE_BOOKS_RATINGS_MESSAGE_GOOGLE_SUPPLIED_A_COMMUNITY_COUNT_BUT: Final = (
    "Google Books supplied a community count but no valid mean."
)
INVALID_VOLUME: Final = "invalid_volume"
GOOGLE_BOOKS_VOLUME_MESSAGE_GOOGLE_BOOKS_RETURNED_A_MALFORMED_VOLUME: Final = (
    "Google Books returned a malformed volume."
)
VOLUMEINFO: Final = "volumeInfo"
GOOGLE_BOOKS_VOLUME_A_ZA_Z0: Final = "[A-Za-z0-9_-]{1,128}"
GOOGLE_BOOKS_VOLUME_URL_TEMPLATE: Final = "https://books.google.com/books?id={v0}"
PROVIDER_ID: Final = "provider_id"
CATEGORIES: Final = "categories"
GENRES: Final = "genres"
GOOGLE_BOOKS_VOLUME_A_Z: Final = "[a-z]{2,3}"
PAGECOUNT: Final = "pageCount"
DESCRIPTION: Final = "description"
GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_REJECTED_THE_PUBLIC_CATALOG_REQUEST: Final = (
    "Google Books rejected the public catalog request."
)
GOOGLE_BOOKS_HTTP_PAYLOAD_CONTENT_TYPE_TEXT: Final = ";"
GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON: Final = "application/json"
GOOGLE_BOOKS_HTTP_PAYLOAD_JSON: Final = "+json"
GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_BOOKS_RETURNED_NON_JSON_CONTENT_NOT: Final = (
    "Google Books returned non-JSON content, not a catalog result."
)
GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_BOOKS_RETURNED_INVALID_JSON: Final = (
    "Google Books returned invalid JSON."
)
GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_RETURNED_AN_INVALID_RESULT_SHAPE: Final = (
    "Google Books returned an invalid result shape."
)
ERROR: Final = "error"
CODE: Final = "code"
RESOURCE_EXHAUSTED: Final = "RESOURCE_EXHAUSTED"
ERRORS: Final = "errors"
REASON: Final = "reason"
QUOTAEXCEEDED: Final = "quotaExceeded"
DAILYLIMITEXCEEDED: Final = "dailyLimitExceeded"
RATELIMITEXCEEDED: Final = "rateLimitExceeded"
USERRATELIMITEXCEEDED: Final = "userRateLimitExceeded"
GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_BOOKS_RETURNED_AN_API_ERROR_RATHER: Final = (
    "Google Books returned an API error rather than catalog data."
)
TOTALITEMS: Final = "totalItems"
ITEMS: Final = "items"
DUPLICATE_CANDIDATE: Final = "duplicate_candidate"
GOOGLE_BOOKS_SEARCH_PAYLOAD_MESSAGE_REPEATED_A_VOLUME_IDENTITY_IT: Final = (
    "Google Books repeated a volume identity; it was excluded."
)
CANDIDATES: Final = "candidates"
COMPLETE: Final = "complete"
GOOGLE_BOOKS_CACHED_METADATA_CACHE_CONTAINS_AN_INVALID_GOOGLE_BOOKS: Final = (
    "Metadata cache contains an invalid Google Books entry."
)
Q: Final = "q"
KEY: Final = "key"
FIELDS: Final = "fields"
MAXRESULTS: Final = "maxResults"
PRINTTYPE: Final = "printType"
PRETTYPRINT: Final = "prettyPrint"
GOOGLE_BOOKS_NOT_CONFIGURED: Final = "google_books_not_configured"
GOOGLEBOOKSPROVIDER_LOOKUP_QUERIES_TEMPLATE: Final = "isbn:{v0}"
GOOGLE_BOOKS_GOOGLEBOOKSPROVIDER_LOOKUP_TEMPLATE: Final = 'intitle:"{v0}" inauthor:"{v1}"'
INSUFFICIENT_IDENTITY: Final = "insufficient_identity"
LOOKUP_ISSUES_MESSAGE_CATALOG_LOOKUP_NEEDS_A_VALID_ISBN_OR: Final = (
    "Catalog lookup needs a valid ISBN or a usable title and author."
)
INVALID_INPUT_ISBN: Final = "invalid_input_isbn"
GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_AN_INVALID_ISBN_WAS_EXCLUDED_FROM: Final = (
    "An invalid input ISBN was excluded from lookup."
)
SEARCH_TRUNCATED: Final = "search_truncated"
GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_GOOGLE_RESULTS_WERE_BOUNDED_MORE: Final = (
    "Google Books candidate results were bounded; more may exist."
)
METADATA_CACHE_ERROR: Final = "metadata_cache_error"
LOOKUP_ISSUES_MESSAGE_THE_METADATA_CACHE_COULD_NOT_BE_USED: Final = (
    "The metadata cache could not be used safely; lookup failed."
)
METADATA_REQUEST_FAILED: Final = "metadata_request_failed"
LOOKUP_ISSUES_MESSAGE_GOOGLE_BOOKS_LOOKUP_FAILED_CHECK_THE_NETWORK: Final = (
    "Google Books lookup failed; check the network, key, or quota."
)
UNVERIFIED_CANDIDATES: Final = "unverified_candidates"
GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_CATALOG_NOT_VERIFY_AGAINST_THE: Final = (
    "Catalog identities did not verify against the ISBN or title/author."
)
METADATA_DEFERRED: Final = "metadata_deferred"
GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_ADDITIONAL_WERE_DEFERRED_TO_KEEP: Final = (
    "Additional ISBN searches were deferred to keep this lookup bounded."
)
SOURCE_ID: Final = "source_id"
OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON: Final = (
    "https://openlibrary.org/search.json"
)
FIELDS_ISSUE_MESSAGE_TEMPLATE_2: Final = (
    "Open Library returned an invalid {v0} value; it was not used."
)
RATINGS_AVERAGE: Final = "ratings_average"
RATINGS_COUNT: Final = "ratings_count"
OPEN_LIBRARY_RATINGS_MESSAGE_OPEN_SUPPLIED_A_COMMUNITY_MEAN_WITHOUT: Final = (
    "Open Library supplied a community mean without a valid positive count."
)
OPEN_LIBRARY_RATINGS_MESSAGE_OPEN_SUPPLIED_A_COMMUNITY_COUNT_BUT: Final = (
    "Open Library supplied a community count but no valid mean."
)
INVALID_WORK: Final = "invalid_work"
OPEN_LIBRARY_WORK_MESSAGE_OPEN_LIBRARY_RETURNED_A_MALFORMED_WORK: Final = (
    "Open Library returned a malformed work."
)
OPEN_LIBRARY_WORK_MATCH_WORKS_OL_D_W: Final = "(?:/works/)?(OL[1-9]\\d*W)"
OPEN_LIBRARY_WORK_URL_TEMPLATE: Final = "https://openlibrary.org/works/{v0}"
SUBJECT: Final = "subject"
LANGUAGES: Final = "languages"
NUMBER_OF_PAGES_MEDIAN: Final = "number_of_pages_median"
MEDIAN_PAGE_COUNT: Final = "median_page_count"
FIRST_PUBLISH_YEAR: Final = "first_publish_year"
OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_REJECTED_THE_PUBLIC_CATALOG_REQUEST: Final = (
    "Open Library rejected the public catalog request."
)
OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_LIBRARY_RETURNED_NON_JSON_CONTENT_NOT: Final = (
    "Open Library returned non-JSON content, not a catalog result."
)
OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_LIBRARY_RETURNED_INVALID_JSON: Final = (
    "Open Library returned invalid JSON."
)
OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_RETURNED_AN_INVALID_RESULT_SHAPE: Final = (
    "Open Library returned an invalid result shape."
)
OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_LIBRARY_RETURNED_AN_API_ERROR_RATHER: Final = (
    "Open Library returned an API error rather than catalog data."
)
NUMFOUND: Final = "numFound"
NUM_FOUND: Final = "num_found"
DOCS: Final = "docs"
START: Final = "start"
NUMFOUNDEXACT: Final = "numFoundExact"
OPEN_LIBRARY_SEARCH_PAYLOAD_MESSAGE_OPEN_REPEATED_A_WORK_IDENTITY_IT: Final = (
    "Open Library repeated a work identity; it was excluded."
)
OPEN_LIBRARY_CACHED_OL_D_W: Final = "OL[1-9]\\d*W"
OPEN_LIBRARY_CACHED_METADATA_CACHE_CONTAINS_AN_INVALID_OPEN_LIBRARY: Final = (
    "Metadata cache contains an invalid Open Library entry."
)
OPEN_LIBRARY_QUERY_TEXT: Final = "("
OPEN_LIBRARY_QUERY_OR: Final = " OR "
OPEN_LIBRARY_QUERY_TEXT_2: Final = ")"
OPEN_LIBRARY_QUERY_TEMPLATE: Final = '(title:"{v0}" AND author:"{v1}")'
FAILURE_ISSUE_MESSAGE_THE_METADATA_CACHE_COULD_NOT_BE_USED: Final = (
    "The metadata cache could not be used safely; no lookup was reported."
)
FAILURE_ISSUE_MESSAGE_OPEN_LIBRARY_FAILED_CHECK_CONNECTIVITY_OR: Final = (
    "Open Library lookup failed; check connectivity or provider limits."
)
OPEN_LIBRARY_RESULT_MESSAGE_ADDITIONAL_TERMS_WERE_DEFERRED_TO_BOUND: Final = (
    "Additional ISBN terms were deferred to bound the query."
)
OPEN_LIBRARY_RESULT_MESSAGE_OPEN_RETURNED_A_LIMITED_OR_APPROXIMATE: Final = (
    "Open Library returned a limited or approximate set; more may exist."
)
ISSUES_MESSAGE_LOOKUP_NEEDS_A_VALID_ISBN_OR_A: Final = (
    "Lookup needs a valid ISBN or a usable title and author."
)
ISSUES_MESSAGE_OPEN_LIBRARY_S_TARGETED_BATCH_BUDGET_IS: Final = (
    "Open Library's targeted batch budget is exhausted. Use cached data or explic"
    "itly select a smaller fallback set; bulk catalog harvesting is not supported"
    "."
)
LIMIT: Final = "limit"
LOOKUP_MANY_SEARCH_MESSAGE_SOME_IDENTITIES_DID_NOT_VERIFY_AGAINST: Final = (
    "Some catalog identities did not verify against the books."
)
REDACTION_REDACT_RESULT_REDACTED: Final = "[redacted]"
REDACTION_REDACT_RESULT_I_KEY_API_KEY_ACCESS_TOKEN_TOKEN: Final = (
    "(?i)([?&](?:key|api_key|access_token|token|cookie|remember_user_token)=)[^&\\s]+"
)
REDACTION_REDACT_RESULT_REDACTED_2: Final = "\\1[redacted]"
REDACTION_REDACT_I_BBEARER_S_A_ZA_Z0: Final = "(?i)\\bBearer\\s+[A-Za-z0-9._~+/\\-=]+"
REDACTION_REDACT_BEARER_REDACTED: Final = "Bearer [redacted]"
MONDAY: Final = "Monday"
TUESDAY: Final = "Tuesday"
WEDNESDAY: Final = "Wednesday"
THURSDAY: Final = "Thursday"
FRIDAY: Final = "Friday"
SATURDAY: Final = "Saturday"
SUNDAY: Final = "Sunday"
SCHEDULING_IMPLEMENTATION_FINGERPRINT_PY: Final = "*.py"
STABILITY_JSON: Final = "stability.json"
SCHEDULING_READ_HISTORY_THE_LOCAL_RECEIPT_IS_INVALID_WEEKLY: Final = (
    "The local stability receipt is invalid; weekly scheduling remains unavailable."
)
RUNS: Final = "runs"
SCHEDULING_REQUIRE_STABLE_BOTH_READER_MUST_BE_CONFIGURED_BEFORE: Final = (
    "Both reader accounts must be configured before weekly scheduling."
)
SCHEDULING_REQUIRE_STABLE_WEEKLY_TWO_CONSECUTIVE_COMPLETE_LIVE: Final = (
    "Weekly scheduling requires two consecutive complete live account syncs for t"
    "his implementation, including an unattended run."
)
RUN_ID: Final = "run_id"
SCHEDULING_REQUIRE_STABLE_THE_STABILITY_RECEIPT_DOES_NOT_MATCH_THE: Final = (
    "The stability receipt does not match the current database."
)
SCHEDULING_REQUIRE_STABLE_THE_COMPLETE_LIVE_SYNC_RECEIPT_IS_STALE: Final = (
    "The complete live sync receipt is stale; sync before scheduling."
)
SCHEDULING_TASK_NAME_TEMPLATE: Final = "BookyStats-{v0}"
SCHEDULING_TASK_XML_WEEKLY_SCHEDULING_IS_DISABLED_OR_LACKS_ITS: Final = (
    "Weekly scheduling is disabled or lacks its explicit day and time."
)
TASK: Final = "Task"
VERSION: Final = "version"
XMLNS: Final = "xmlns"
SCHEDULING_TASK_XML_TASK_TEXT: Final = "1.4"
SCHEDULING_TASK_XML_TASK_HTTP_SCHEMAS_MICROSOFT_COM_WINDOWS_MIT_TASK: Final = (
    "http://schemas.microsoft.com/windows/2004/02/mit/task"
)
REGISTRATIONINFO: Final = "RegistrationInfo"
SCHEDULING_TASK_XML_BOOKYSTATS_WEEKLY_ACCOUNT_INGESTION_REQUIRES: Final = (
    "BookyStats read-only weekly account ingestion. Requires the owning user's logged-in session."
)
DESCRIPTION_2: Final = "Description"
TRIGGERS: Final = "Triggers"
CALENDARTRIGGER: Final = "CalendarTrigger"
SCHEDULING_TASK_XML_Y_M_DT_H_M_S: Final = "%Y-%m-%dT%H:%M:%S"
STARTBOUNDARY: Final = "StartBoundary"
ENABLED: Final = "Enabled"
SCHEDULEBYWEEK: Final = "ScheduleByWeek"
SCHEDULING_TASK_XML_TEXT: Final = "1"
WEEKSINTERVAL: Final = "WeeksInterval"
DAYSOFWEEK: Final = "DaysOfWeek"
PRINCIPALS: Final = "Principals"
PRINCIPAL: Final = "Principal"
READER_2: Final = "Reader"
INTERACTIVETOKEN: Final = "InteractiveToken"
LOGONTYPE: Final = "LogonType"
LEASTPRIVILEGE: Final = "LeastPrivilege"
RUNLEVEL: Final = "RunLevel"
SETTINGS: Final = "Settings"
MULTIPLEINSTANCESPOLICY: Final = "MultipleInstancesPolicy"
IGNORENEW: Final = "IgnoreNew"
DISALLOWSTARTIFONBATTERIES: Final = "DisallowStartIfOnBatteries"
STOPIFGOINGONBATTERIES: Final = "StopIfGoingOnBatteries"
STARTWHENAVAILABLE: Final = "StartWhenAvailable"
RUNONLYIFNETWORKAVAILABLE: Final = "RunOnlyIfNetworkAvailable"
EXECUTIONTIMELIMIT: Final = "ExecutionTimeLimit"
PT4H: Final = "PT4H"
ACTIONS: Final = "Actions"
CONTEXT: Final = "Context"
EXEC: Final = "Exec"
COMMAND_2: Final = "Command"
SCHEDULING_TASK_XML_M: Final = "-m"
BOOKYSTATS_2: Final = "bookystats"
ARGUMENTS: Final = "Arguments"
WORKINGDIRECTORY: Final = "WorkingDirectory"
UNICODE: Final = "unicode"
POWERSHELL_EXE: Final = "powershell.exe"
SCHEDULING_POWERSHELL_COMPLETED_NOPROFILE: Final = "-NoProfile"
SCHEDULING_POWERSHELL_COMPLETED_NONINTERACTIVE: Final = "-NonInteractive"
SCHEDULING_POWERSHELL_COMPLETED_COMMAND: Final = "-Command"
SCHEDULING_POWERSHELL_WINDOWS_TASK_OPERATION_FAILED_THE_PRIOR: Final = (
    "Windows Task Scheduler operation failed; the prior schedule was not reported as updated."
)
SCHEDULING_PS_LITERAL_TEXT: Final = "'"
SCHEDULING_PS_LITERAL_TEXT_2: Final = "''"
SCHEDULING_ENABLE_WEEKLY_SET_AN_WEEKLY_SCHEDULE_BEFORE_REQUESTING: Final = (
    "Set an explicit weekly schedule before requesting activation."
)
SCHEDULING_ENABLE_WEEKLY_AUTOMATIC_CURRENTLY_SUPPORTS_WINDOWS: Final = (
    "Automatic local weekly scheduling currently supports Windows only."
)
SCHEDULING_ENABLE_WEEKLY_ZONE_STOP_GET_TIMEZONE_ID: Final = (
    "$ErrorActionPreference='Stop'; (Get-TimeZone).Id"
)
SCHEDULING_ENABLE_WEEKLY_THE_CONFIGURED_TIME_ZONE_MUST_MATCH: Final = (
    "The configured schedule time zone must match this Windows host's Get-TimeZone Id."
)
WEEKLY_TASK_XML: Final = "weekly-task.xml"
SCHEDULING_ENABLE_WEEKLY_TEMPLATE: Final = (
    "$ErrorActionPreference='Stop'; $xml = {v0}; Re"
    "gister-ScheduledTask -TaskName {v1} -Xml $xml -Force | Out-Null; (Get-Schedu"
    "ledTask -TaskName {v2}).TaskName"
)
SCHEDULE_JSON: Final = "schedule.json"
ENABLED_2: Final = "enabled"
CONFIGURED: Final = "configured"
NOT_REGISTERED: Final = "not_registered"
UNSUPPORTED_HOST: Final = "unsupported_host"
SCHEDULING_SCHEDULE_STATUS_OUTPUT_TEMPLATE: Final = (
    "$ErrorActionPreference='Stop'; $task = Get-ScheduledTask -TaskName {v0} -Err"
    "orAction SilentlyContinue; if ($null -eq $task) {{ Write-Output 'null' }} el"
    "se {{ $info = Get-ScheduledTaskInfo -TaskName {v1}; @{{ enabled=$task.Settin"
    "gs.Enabled; state=[string]$task.State; last_run=$info.LastRunTime.ToString('"
    "o'); next_run=$info.NextRunTime.ToString('o'); last_result=$info.LastTaskRes"
    "ult }} | ConvertTo-Json -Compress }}"
)
NULL: Final = "null"
TASK_MISSING: Final = "task_missing"
SCHEDULING_SCHEDULE_STATUS_WINDOWS_AN_UNREADABLE_SCHEDULE_STATUS: Final = (
    "Windows returned an unreadable schedule status."
)
SCHEDULING_SCHEDULE_STATUS_WINDOWS_AN_UNEXPECTED_SCHEDULE_STATUS: Final = (
    "Windows returned an unexpected schedule status."
)
STORAGE_SCHEMA_CREATE_TABLE_RUNS_ID_INTEGER_PRIMARY_KEY: Final = (
    "\nCREATE TABLE runs (\n    id INTEGER PRIMARY KEY,\n    trigger TEXT NOT NUL"
    "L,\n    state TEXT NOT NULL,\n    started_at TEXT NOT NULL,\n    finished_at"
    " TEXT\n);\nCREATE TABLE progress (\n    id INTEGER PRIMARY KEY,\n    run_id "
    "INTEGER NOT NULL REFERENCES runs(id),\n    source TEXT NOT NULL,\n    collec"
    "tion TEXT NOT NULL,\n    staged_at TEXT NOT NULL,\n    raw_json TEXT NOT NUL"
    "L\n);\nCREATE INDEX progress_run ON progress(run_id, source, collection);\nC"
    "REATE TABLE source_accounts (\n    source TEXT PRIMARY KEY,\n    account_id "
    "TEXT NOT NULL,\n    UNIQUE(source, account_id)\n);\nCREATE TABLE snapshots ("
    "\n    id INTEGER PRIMARY KEY,\n    run_id INTEGER NOT NULL REFERENCES runs(i"
    "d),\n    source TEXT NOT NULL,\n    account_id TEXT NOT NULL,\n    collectio"
    "n TEXT NOT NULL,\n    state TEXT NOT NULL,\n    started_at TEXT NOT NULL,\n "
    "   finished_at TEXT NOT NULL,\n    published INTEGER NOT NULL DEFAULT 0 CHEC"
    "K(published IN (0, 1)),\n    rejection_reason TEXT,\n    raw_json TEXT NOT N"
    "ULL\n);\nCREATE INDEX snapshots_identity ON snapshots(source, account_id, co"
    "llection, id);\nCREATE TABLE source_collections (\n    id INTEGER PRIMARY KE"
    "Y,\n    source TEXT NOT NULL,\n    account_id TEXT NOT NULL,\n    collection"
    " TEXT NOT NULL,\n    state TEXT NOT NULL,\n    last_attempt_at TEXT NOT NULL"
    ",\n    last_success_at TEXT,\n    last_attempt_snapshot_id INTEGER REFERENCE"
    "S snapshots(id),\n    active_snapshot_id INTEGER REFERENCES snapshots(id),\n"
    "    coverage_json TEXT NOT NULL DEFAULT '{}',\n    attempt_coverage_json TEX"
    "T NOT NULL DEFAULT '{}',\n    UNIQUE(source, account_id, collection),\n    U"
    "NIQUE(id, source, account_id)\n);\nCREATE TABLE works (\n    id INTEGER PRIM"
    "ARY KEY,\n    created_at TEXT NOT NULL\n);\nCREATE TABLE editions (\n    id "
    "INTEGER PRIMARY KEY,\n    work_id INTEGER NOT NULL REFERENCES works(id),\n  "
    "  created_at TEXT NOT NULL,\n    UNIQUE(id, work_id)\n);\nCREATE TABLE sourc"
    "e_records (\n    id INTEGER PRIMARY KEY,\n    source TEXT NOT NULL,\n    acc"
    "ount_id TEXT NOT NULL,\n    source_id TEXT NOT NULL,\n    work_id INTEGER NO"
    "T NULL REFERENCES works(id),\n    edition_id INTEGER NOT NULL,\n    match_st"
    "ate TEXT NOT NULL,\n    title_author_key TEXT NOT NULL,\n    semantic_hash T"
    "EXT NOT NULL,\n    identity_hash TEXT NOT NULL,\n    latest_json TEXT NOT NU"
    "LL,\n    first_seen TEXT NOT NULL,\n    last_seen TEXT NOT NULL,\n    last_s"
    "napshot_id INTEGER NOT NULL REFERENCES snapshots(id),\n    FOREIGN KEY(editi"
    "on_id, work_id) REFERENCES editions(id, work_id),\n    FOREIGN KEY(source, a"
    "ccount_id) REFERENCES source_accounts(source, account_id),\n    UNIQUE(sourc"
    "e, account_id, source_id),\n    UNIQUE(id, source, account_id)\n);\nCREATE I"
    "NDEX records_title_author ON source_records(title_author_key);\nCREATE TABLE"
    " record_identifiers (\n    record_id INTEGER NOT NULL REFERENCES source_reco"
    "rds(id),\n    isbn TEXT NOT NULL,\n    PRIMARY KEY(record_id, isbn)\n);\nCRE"
    "ATE INDEX identifiers_isbn ON record_identifiers(isbn);\nCREATE TABLE member"
    "ships (\n    collection_id INTEGER NOT NULL,\n    record_id INTEGER NOT NULL"
    ",\n    source TEXT NOT NULL,\n    account_id TEXT NOT NULL,\n    first_seen "
    "TEXT NOT NULL,\n    last_seen TEXT NOT NULL,\n    PRIMARY KEY(collection_id,"
    " record_id),\n    FOREIGN KEY(collection_id, source, account_id)\n        RE"
    "FERENCES source_collections(id, source, account_id),\n    FOREIGN KEY(record"
    "_id, source, account_id)\n        REFERENCES source_records(id, source, acco"
    "unt_id)\n);\nCREATE INDEX memberships_record ON memberships(record_id);\nCRE"
    "ATE TABLE snapshot_records (\n    id INTEGER PRIMARY KEY,\n    snapshot_id I"
    "NTEGER NOT NULL REFERENCES snapshots(id),\n    source_id TEXT NOT NULL,\n   "
    " record_id INTEGER REFERENCES source_records(id),\n    record_json TEXT NOT "
    "NULL,\n    UNIQUE(snapshot_id, source_id)\n);\nCREATE TABLE observations (\n"
    "    id INTEGER PRIMARY KEY,\n    snapshot_record_id INTEGER NOT NULL REFEREN"
    "CES snapshot_records(id),\n    field TEXT NOT NULL,\n    state TEXT NOT NULL"
    ",\n    scope TEXT NOT NULL,\n    value_json TEXT NOT NULL,\n    source_url T"
    "EXT NOT NULL,\n    observed_at TEXT NOT NULL\n);\nCREATE INDEX observations_"
    "record ON observations(snapshot_record_id);\nCREATE TABLE reading_events (\n"
    "    id INTEGER PRIMARY KEY,\n    record_id INTEGER NOT NULL REFERENCES sourc"
    "e_records(id),\n    event_key TEXT NOT NULL,\n    source_event_id TEXT,\n   "
    " event_json TEXT NOT NULL,\n    first_seen TEXT NOT NULL,\n    last_seen TEX"
    "T NOT NULL,\n    last_snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),"
    "\n    UNIQUE(record_id, event_key)\n);\nCREATE TABLE reading_observations ("
    "\n    id INTEGER PRIMARY KEY,\n    snapshot_record_id INTEGER NOT NULL REFER"
    "ENCES snapshot_records(id),\n    reading_event_id INTEGER NOT NULL REFERENCE"
    "S reading_events(id),\n    event_json TEXT NOT NULL,\n    UNIQUE(snapshot_re"
    "cord_id, reading_event_id)\n);\nCREATE TABLE match_candidates (\n    id INTE"
    "GER PRIMARY KEY,\n    record_id INTEGER NOT NULL REFERENCES source_records(i"
    "d),\n    target_record_id INTEGER NOT NULL REFERENCES source_records(id),\n "
    "   kind TEXT NOT NULL,\n    reason TEXT NOT NULL,\n    identifiers_json TEXT"
    " NOT NULL,\n    resolution TEXT NOT NULL,\n    first_snapshot_id INTEGER NOT"
    " NULL REFERENCES snapshots(id),\n    last_snapshot_id INTEGER NOT NULL REFER"
    "ENCES snapshots(id),\n    CHECK(record_id > target_record_id),\n    UNIQUE(r"
    "ecord_id, target_record_id)\n);\nCREATE INDEX candidates_target ON match_can"
    "didates(target_record_id);\nCREATE TABLE match_decisions (\n    id INTEGER P"
    "RIMARY KEY,\n    record_id INTEGER NOT NULL REFERENCES source_records(id),\n"
    "    candidate_id INTEGER REFERENCES match_candidates(id),\n    kind TEXT NOT"
    " NULL,\n    prior_work_id INTEGER NOT NULL REFERENCES works(id),\n    prior_"
    "edition_id INTEGER NOT NULL REFERENCES editions(id),\n    work_id INTEGER NO"
    "T NULL REFERENCES works(id),\n    edition_id INTEGER NOT NULL REFERENCES edi"
    "tions(id),\n    prior_resolution TEXT,\n    evidence_json TEXT NOT NULL,\n  "
    "  created_at TEXT NOT NULL,\n    reversed_by INTEGER REFERENCES match_decisi"
    "ons(id)\n);\nCREATE TABLE enrichment_attempts (\n    id INTEGER PRIMARY KEY,"
    "\n    record_id INTEGER NOT NULL REFERENCES source_records(id),\n    provide"
    "r TEXT NOT NULL,\n    state TEXT NOT NULL,\n    checked_at TEXT NOT NULL,\n "
    "   identity_hash TEXT NOT NULL,\n    raw_json TEXT NOT NULL,\n"
    "    implementation_version INTEGER NOT NULL DEFAULT 0\n);\nCREATE INDE"
    "X enrichment_record ON enrichment_attempts(record_id, provider, id);\nCREATE"
    " TABLE enrichment_candidates (\n    id INTEGER PRIMARY KEY,\n    attempt_id "
    "INTEGER NOT NULL REFERENCES enrichment_attempts(id),\n    provider_id TEXT N"
    "OT NULL,\n    kind TEXT NOT NULL,\n    reason TEXT NOT NULL,\n    selected I"
    "NTEGER NOT NULL CHECK(selected IN (0, 1)),\n    candidate_json TEXT NOT NULL"
    "\n);\nCREATE TABLE metadata_observations (\n    id INTEGER PRIMARY KEY,\n   "
    " candidate_id INTEGER NOT NULL REFERENCES enrichment_candidates(id),\n    fi"
    "eld TEXT NOT NULL,\n    state TEXT NOT NULL,\n    scope TEXT NOT NULL,\n    "
    "value_json TEXT NOT NULL,\n    source_url TEXT NOT NULL,\n    observed_at TE"
    "XT NOT NULL\n);\nCREATE TABLE enrichment_active (\n    record_id INTEGER NOT"
    " NULL REFERENCES source_records(id),\n    provider TEXT NOT NULL,\n    attem"
    "pt_id INTEGER NOT NULL REFERENCES enrichment_attempts(id),\n    candidate_id"
    " INTEGER NOT NULL REFERENCES enrichment_candidates(id),\n    last_success_at"
    " TEXT NOT NULL,\n    PRIMARY KEY(record_id, provider)\n);\n"
)
STORAGE_DATE_SNAPSHOT_TIMESTAMPS_MUST_INCLUDE_A_TIMEZONE: Final = (
    "Snapshot timestamps must include a timezone"
)
SOURCE_EVENT_ID: Final = "source_event_id"
STORAGE_EVENT_KEY_ID: Final = "id:"
STORAGE_EVENT_KEY_ANONYMOUS: Final = "anonymous:"
STORAGE_EVENT_OCCURRENCE_KEY: Final = "{key}:{occurrence}"
OBSERVED_AT: Final = "observed_at"
TITLE_AUTHOR: Final = "title_author"
STORAGE_INSERT_ID_SQLITE_DID_NOT_RETURN_AN_INSERTED_ROW: Final = (
    "SQLite did not return an inserted row ID"
)
STORAGE_DATABASE_INITIALIZE_PRAGMA_FOREIGN_KEYS_ON: Final = "PRAGMA foreign_keys = ON"
STORAGE_DATABASE_INITIALIZE_PRAGMA_BUSY_TIMEOUT: Final = "PRAGMA busy_timeout = 5000"
DATABASE_INITIALIZE_VERSION_PRAGMA_USER_VERSION: Final = "PRAGMA user_version"
DATABASE_INITIALIZE_APPLICATION_ID_PRAGMA_APPLICATION_ID: Final = "PRAGMA application_id"
STORAGE_DATABASE_INITIALIZE_UNSUPPORTED_BOOKYSTATS_DATABASE_SCHEMA: Final = (
    "Unsupported BookyStats database schema"
)
STORAGE_DATABASE_INITIALIZE_PRAGMA_JOURNAL_MODE_WAL: Final = "PRAGMA journal_mode = WAL"
STORAGE_DATABASE_INITIALIZE_BEGIN_IMMEDIATE: Final = "BEGIN IMMEDIATE"
DATABASE_INITIALIZE_TABLES_SELECT_NAME_FROM_SQLITE_MASTER_WHERE_TYPE: Final = (
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
)
STORAGE_DATABASE_INITIALIZE_REFUSING_UNRECOGNIZED_NONEMPTY_DATABASE: Final = (
    "Refusing to initialize an unrecognized nonempty database"
)
STORAGE_DATABASE_INITIALIZE_TEMPLATE: Final = "PRAGMA application_id = {v0}"
STORAGE_DATABASE_INITIALIZE_TEMPLATE_2: Final = "PRAGMA user_version = {v0}"
COMMIT: Final = "COMMIT"
BEGIN: Final = "BEGIN"
ROLLBACK: Final = "ROLLBACK"
DATABASE_OPEN_RUN_ROW_SELECT_FINISHED_AT_FROM_RUNS_WHERE_ID: Final = (
    "SELECT finished_at FROM runs WHERE id = ?"
)
STORAGE_DATABASE_OPEN_RUN_UNKNOWN_INGESTION_RUN: Final = "Unknown ingestion run"
FINISHED_AT: Final = "finished_at"
STORAGE_DATABASE_OPEN_RUN_THE_INGESTION_RUN_IS_ALREADY_FINISHED: Final = (
    "The ingestion run is already finished"
)
STORAGE_DATABASE_START_RUN_A_RUN_TRIGGER_IS_REQUIRED: Final = "A run trigger is required"
STORAGE_DATABASE_START_RUN_INSERT_INTO_RUNS_TRIGGER_STATE_STARTED_AT: Final = (
    "INSERT INTO runs(trigger, state, started_at) VALUES (?, ?, ?)"
)
STORAGE_DATABASE_STAGE_PROGRESS_PROGRESS_A_READER_SOURCE_AND_A: Final = (
    "Progress requires a reader source and a collection"
)
STORAGE_DATABASE_STAGE_PROGRESS_PROGRESS_RECORDS_FROM_ANOTHER_SOURCE: Final = (
    "Progress contains records from another source"
)
STORAGE_DATABASE_STAGE_PROGRESS_INSERT_RUN_ID_SOURCE_COLLECTION: Final = (
    "INSERT INTO progress(run_id, source, collection, staged_at, raw_json) VALUES (?, ?, ?, ?, ?)"
)
STORAGE_DATABASE_STAGE_PROGRESS_UPDATE_SET_STATE_LAST_ATTEMPT: Final = (
    "UPDATE source_collections SET state = ?, last_attempt_at = ? WHERE source = "
    "? AND collection = ? AND account_id = (SELECT account_id FROM source_account"
    "s WHERE source = ?)"
)
DATABASE_RAW_SNAPSHOT_SNAPSHOT_ID_SNAPSHOTS_RUN_ID_SOURCE_ACCOUNT: Final = (
    "INSERT INTO snapshots(run_id, source, account_id, collection, state, started"
    "_at, finished_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
DATABASE_RAW_SNAPSHOT_SNAPSHOT_RECORD_RECORDS_SNAPSHOT_ID_SOURCE: Final = (
    "INSERT INTO snapshot_records(snapshot_id, source_id, record_json) VALUES (?, ?, ?)"
)
STORAGE_DATABASE_RAW_SNAPSHOT_INSERT_SNAPSHOT_RECORD_ID_FIELD: Final = (
    "INSERT INTO observations(snapshot_record_id, field, state, scope, value_json"
    ", source_url, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
STORAGE_DATABASE_SAVE_SNAPSHOT_A_REQUIRES_A_READER_SOURCE_ACCOUNT: Final = (
    "A snapshot requires a reader source, account, and collection"
)
STORAGE_DATABASE_SAVE_SNAPSHOT_SNAPSHOT_START_IS_AFTER_ITS_FINISH: Final = (
    "Snapshot start is after its finish"
)
DATABASE_SAVE_SNAPSHOT_BINDING_SELECT_ID_FROM_SOURCE_ACCOUNTS_WHERE: Final = (
    "SELECT account_id FROM source_accounts WHERE source = ?"
)
ACCOUNT_ID: Final = "account_id"
DATABASE_SAVE_SNAPSHOT_REJECTION_SOURCE_USE_AN_EXPLICIT_RECONNECT: Final = (
    "Source account changed; use an explicit reconnect decision or a new database"
)
DATABASE_SAVE_SNAPSHOT_PREVIOUS_SELECT_AT_FROM_SOURCE_COLLECTIONS: Final = (
    "SELECT s.started_at FROM source_collections c JOIN snapshots s ON s.id = c.a"
    "ctive_snapshot_id WHERE c.source = ? AND c.account_id = ? AND c.collection ="
    " ?"
)
STARTED_AT: Final = "started_at"
DATABASE_SAVE_SNAPSHOT_REJECTION_A_SNAPSHOT_IS_ALREADY_ACTIVE: Final = (
    "A newer complete snapshot is already active"
)
STORAGE_DATABASE_SAVE_SNAPSHOT_INSERT_COLLECTIONS_SOURCE_ACCOUNT_ID: Final = (
    "INSERT INTO source_collections(source, account_id, collection, state, last_a"
    "ttempt_at, last_attempt_snapshot_id, attempt_coverage_json) VALUES (?, ?, ?,"
    " ?, ?, ?, ?) ON CONFLICT(source, account_id, collection) DO UPDATE SET state"
    " = excluded.state, last_attempt_at = excluded.last_attempt_at, last_attempt_"
    "snapshot_id = excluded.last_attempt_snapshot_id, attempt_coverage_json = exc"
    "luded.attempt_coverage_json"
)
STORAGE_DATABASE_SAVE_SNAPSHOT_UPDATE_SET_REJECTION_REASON_WHERE_ID: Final = (
    "UPDATE snapshots SET rejection_reason = ? WHERE id = ?"
)
STORAGE_DATABASE_SAVE_SNAPSHOT_INSERT_ACCOUNTS_SOURCE_ACCOUNT_ID: Final = (
    "INSERT INTO source_accounts(source, account_id) VALUES (?, ?) ON CONFLICT(source) DO NOTHING"
)
DATABASE_PUBLISH_COLLECTION_ID_SOURCE_COLLECTIONS_WHERE_SOURCE: Final = (
    "SELECT id FROM source_collections WHERE source = ? AND account_id = ? AND collection = ?"
)
RECORD_ID: Final = "record_id"
DATABASE_PUBLISH_PRIOR_MEMBERS_FROM_MEMBERSHIPS_WHERE_COLLECTION: Final = (
    "SELECT record_id FROM memberships WHERE collection_id = ?"
)
STORAGE_DATABASE_PUBLISH_UPDATE_SNAPSHOT_RECORDS_SET_RECORD_ID_WHERE: Final = (
    "UPDATE snapshot_records SET record_id = ? WHERE snapshot_id = ? AND source_id = ?"
)
STORAGE_DATABASE_PUBLISH_INSERT_INTO_COLLECTION_ID_RECORD_ID: Final = (
    "INSERT INTO memberships(collection_id, record_id, source, account_id, first_"
    "seen, last_seen) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(collection_id, record"
    "_id) DO UPDATE SET last_seen = excluded.last_seen"
)
DATABASE_PUBLISH_REMOVED_DELETE_FROM_WHERE_COLLECTION_ID_AND: Final = (
    "DELETE FROM memberships WHERE collection_id = ? AND record_id NOT IN (SELECT"
    " record_id FROM snapshot_records WHERE snapshot_id = ? AND record_id IS NOT "
    "NULL)"
)
STORAGE_DATABASE_PUBLISH_UPDATE_SNAPSHOTS_SET_PUBLISHED_WHERE_ID: Final = (
    "UPDATE snapshots SET published = 1 WHERE id = ?"
)
STORAGE_DATABASE_PUBLISH_UPDATE_SOURCE_SET_ACTIVE_SNAPSHOT_ID: Final = (
    "UPDATE source_collections SET active_snapshot_id = ?, last_success_at = ?, c"
    "overage_json = ? WHERE id = ?"
)
DATABASE_PUBLISH_UNRESOLVED_SELECT_COUNT_FROM_SOURCE_RECORDS_R_JOIN: Final = (
    "SELECT COUNT(*) FROM source_records r JOIN snapshot_records s ON s.record_id"
    " = r.id WHERE s.snapshot_id = ? AND r.match_state IN ('unresolved', 'conflic"
    "ting')"
)
DATABASE_NEW_IDENTITY_WORK_ID_INSERT_INTO_WORKS_CREATED_AT_VALUES: Final = (
    "INSERT INTO works(created_at) VALUES (?)"
)
DATABASE_NEW_IDENTITY_EDITION_ID_INSERT_EDITIONS_WORK_ID_CREATED_AT: Final = (
    "INSERT INTO editions(work_id, created_at) VALUES (?, ?)"
)
STORAGE_DATABASE_COMPARISON_ROWS_SELECT_SOURCE_RECORDS_WHERE_TITLE: Final = (
    "SELECT id FROM source_records WHERE title_author_key = ?"
)
STORAGE_DATABASE_COMPARISON_ROWS_FROM_RECORD_IDENTIFIERS_WHERE: Final = (
    "SELECT record_id FROM record_identifiers WHERE isbn = ?"
)
STORAGE_DATABASE_COMPARISON_ROWS_SELECT_ID_TARGET_RECORD_ID_FROM: Final = (
    "SELECT record_id, target_record_id FROM match_candidates WHERE record_id = ?"
    " OR target_record_id = ?"
)
TARGET_RECORD_ID: Final = "target_record_id"
STORAGE_DATABASE_COMPARISON_ROWS_SELECT_FROM_SOURCE_RECORDS_WHERE_ID: Final = (
    "SELECT * FROM source_records WHERE id = ?"
)
DATABASE_SAVE_RECORD_OLD_SELECT_FROM_SOURCE_RECORDS_WHERE_SOURCE_AND: Final = (
    "SELECT * FROM source_records WHERE source = ? AND account_id = ? AND source_id = ?"
)
DATABASE_SAVE_RECORD_RECORD_ID_SOURCE_RECORDS_SOURCE_ACCOUNT_ID: Final = (
    "INSERT INTO source_records(source, account_id, source_id, work_id, edition_i"
    "d, match_state, title_author_key, semantic_hash, identity_hash, latest_json,"
    " first_seen, last_seen, last_snapshot_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,"
    " ?, ?, ?, ?)"
)
UNRESOLVED: Final = "unresolved"
WORK_ID: Final = "work_id"
EDITION_ID: Final = "edition_id"
STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_TITLE_AUTHOR_KEY: Final = (
    "UPDATE source_records SET title_author_key = ?, semantic_hash = ?, identity_"
    "hash = ?, latest_json = ?, last_seen = ?, last_snapshot_id = ? WHERE id = ?"
)
STORAGE_DATABASE_SAVE_RECORD_DELETE_IDENTIFIERS_WHERE_RECORD_ID: Final = (
    "DELETE FROM record_identifiers WHERE record_id = ?"
)
STORAGE_DATABASE_SAVE_RECORD_INSERT_IDENTIFIERS_RECORD_ID_ISBN: Final = (
    "INSERT INTO record_identifiers(record_id, isbn) VALUES (?, ?)"
)
LATEST_JSON: Final = "latest_json"
STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION: Final = (
    "UPDATE source_records SET work_id = ?, edition_id = ? WHERE id = ?"
)
AUTOMATIC: Final = "automatic"
PENDING: Final = "pending"
SNAPSHOT_ID: Final = "snapshot_id"
IDENTIFIERS: Final = "identifiers"
SEMANTIC_HASH: Final = "semantic_hash"
DATABASE_SAVE_CANDIDATE_EXISTING_MATCH_CANDIDATES_WHERE_RECORD: Final = (
    "SELECT * FROM match_candidates WHERE record_id = ? AND target_record_id = ?"
)
STORAGE_AUTOMATIC_MATCH_HISTORY: Final = (
    "SELECT * FROM match_decisions WHERE candidate_id = ? AND kind = 'automatic' ORDER BY id"
)
STORAGE_LATER_ACCEPTED_MATCH: Final = (
    "SELECT 1 FROM match_decisions WHERE record_id = ? AND id > ?"
    " AND kind = 'accepted' AND reversed_by IS NULL LIMIT 1"
)
STORAGE_INVALIDATED_AUTOMATIC_MATCH: Final = "invalidated_automatic"
STORAGE_INVALIDATED_MATCH_REASON: Final = (
    "Previous automatic match no longer has corroborated evidence: {reason}"
)
DATABASE_SAVE_CANDIDATE_CURRENT_SELECT_ID_EDITION_ID_FROM_SOURCE: Final = (
    "SELECT work_id, edition_id FROM source_records WHERE id = ?"
)
DISMISSED: Final = "dismissed"
AUTO_CONFIRMED: Final = "auto_confirmed"
STORAGE_DATABASE_SAVE_CANDIDATE_INSERT_CANDIDATES_RECORD_ID_TARGET: Final = (
    "INSERT INTO match_candidates(record_id, target_record_id, kind, reason, iden"
    "tifiers_json, resolution, first_snapshot_id, last_snapshot_id) VALUES (?, ?,"
    " ?, ?, ?, ?, ?, ?) ON CONFLICT(record_id, target_record_id) DO UPDATE SET ki"
    "nd = excluded.kind, reason = excluded.reason, identifiers_json = excluded.id"
    "entifiers_json, last_snapshot_id = excluded.last_snapshot_id, resolution = C"
    "ASE WHEN match_candidates.resolution IN ('accepted', 'rejected') THEN match_"
    "candidates.resolution ELSE excluded.resolution END"
)
KIND: Final = "kind"
DATABASE_REFRESH_MATCH_STATE_MATCH_CANDIDATES_WHERE_RESOLUTION: Final = (
    "SELECT kind FROM match_candidates WHERE resolution = 'pending' AND (record_i"
    "d = ? OR target_record_id = ?)"
)
CONFLICTING: Final = "conflicting"
STORAGE_DATABASE_REFRESH_MATCH_STATE_SOURCE_RECORDS_WHERE_ID_AND: Final = (
    "SELECT 1 FROM source_records WHERE id != ? AND work_id = (SELECT work_id FRO"
    "M source_records WHERE id = ?) LIMIT 1"
)
CONFIRMED: Final = "confirmed"
STORAGE_DATABASE_REFRESH_MATCH_STATE_IDENTIFIERS_I_JOIN_SOURCE: Final = (
    "SELECT 1 FROM record_identifiers i JOIN source_records r ON r.id = i.record_"
    "id WHERE i.record_id = ? AND r.title_author_key != '' LIMIT 1"
)
INDEPENDENT: Final = "independent"
STORAGE_DATABASE_REFRESH_MATCH_STATE_RECORDS_SET_MATCH_STATE_WHERE: Final = (
    "UPDATE source_records SET match_state = ? WHERE id = ?"
)
STORAGE_DATABASE_DECISION_INSERT_INTO_DECISIONS_RECORD_ID_CANDIDATE: Final = (
    "INSERT INTO match_decisions(record_id, candidate_id, kind, prior_work_id, pr"
    "ior_edition_id, work_id, edition_id, prior_resolution, evidence_json, create"
    "d_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
DATABASE_SAVE_READINGS_SNAPSHOT_SNAPSHOT_RECORDS_WHERE_SNAPSHOT: Final = (
    "SELECT id FROM snapshot_records WHERE snapshot_id = ? AND source_id = ?"
)
STORAGE_DATABASE_SAVE_READINGS_A_READING_EVENT_ID_HAS_CONFLICTING: Final = (
    "A source reading-event ID has conflicting observations"
)
DATABASE_SAVE_READINGS_EXISTING_SELECT_EVENTS_WHERE_RECORD_ID: Final = (
    "SELECT * FROM reading_events WHERE record_id = ?"
)
EVENT_JSON: Final = "event_json"
EVENT_KEY: Final = "event_key"
DATABASE_SAVE_READINGS_EVENT_ID_READING_EVENTS_RECORD_ID_EVENT: Final = (
    "INSERT INTO reading_events(record_id, event_key, source_event_id, event_json"
    ", first_seen, last_seen, last_snapshot_id) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
STORAGE_DATABASE_SAVE_READINGS_UPDATE_EVENTS_SET_EVENT_KEY_EVENT: Final = (
    "UPDATE reading_events SET event_key = ?, event_json = ?, last_seen = ?, last"
    "_snapshot_id = ? WHERE id = ?"
)
STORAGE_DATABASE_SAVE_READINGS_OBSERVATIONS_SNAPSHOT_RECORD_ID: Final = (
    "INSERT INTO reading_observations(snapshot_record_id, reading_event_id, event"
    "_json) VALUES (?, ?, ?)"
)
DATABASE_FINISH_RUN_ROW_SELECT_STATE_FINISHED_AT_FROM_RUNS_WHERE: Final = (
    "SELECT state, finished_at FROM runs WHERE id = ?"
)
STORAGE_DATABASE_FINISH_RUN_A_FINISHED_RUN_CANNOT_CHANGE_STATE: Final = (
    "A finished run cannot change state"
)
STORAGE_DATABASE_FINISH_RUN_UPDATE_RUNS_SET_STATE_FINISHED_AT_WHERE: Final = (
    "UPDATE runs SET state = ?, finished_at = ? WHERE id = ?"
)
STORAGE_DATABASE_ACTIVE_RECORDS_SELECT_JSON_FROM_SOURCE_RECORDS: Final = (
    "SELECT r.latest_json FROM source_records r WHERE EXISTS (SELECT 1 FROM membe"
    "rships m WHERE m.record_id = r.id) ORDER BY r.source, r.account_id, r.source"
    "_id"
)
STORAGE_DATABASE_STATUS_SELECT_C_SELECT_COUNT_FROM_MEMBERSHIPS_M: Final = (
    "SELECT c.*, (SELECT COUNT(*) FROM memberships m WHERE m.collection_id = c.id"
    ") AS active_count FROM source_collections c ORDER BY c.source, c.account_id,"
    " c.collection"
)
SOURCE: Final = "source"
COLLECTION: Final = "collection"
LAST_ATTEMPT_AT: Final = "last_attempt_at"
LAST_SUCCESS_AT: Final = "last_success_at"
ACTIVE_COUNT: Final = "active_count"
COVERAGE: Final = "coverage"
LAST_ATTEMPT_COVERAGE: Final = "last_attempt_coverage"
ACTIVE_SNAPSHOT_ID: Final = "active_snapshot_id"
COVERAGE_JSON: Final = "coverage_json"
ATTEMPT_COVERAGE_JSON: Final = "attempt_coverage_json"
STORAGE_DATABASE_STATUS_SELECT_P_A_ACCOUNT_ID_R_STATE: Final = (
    "SELECT p.*, a.account_id, r.state FROM progress p JOIN runs r ON r.id = p.ru"
    "n_id LEFT JOIN source_accounts a ON a.source = p.source WHERE p.id = (SELECT"
    " MAX(p2.id) FROM progress p2 WHERE p2.source = p.source AND p2.collection = "
    "p.collection) AND NOT EXISTS (SELECT 1 FROM source_collections c WHERE c.sou"
    "rce = p.source AND c.collection = p.collection) ORDER BY p.source, p.collect"
    "ion"
)
STAGED_AT: Final = "staged_at"
DATABASE_STATUS_COUNTS_SELECT_COUNT_AS_SOURCE_RECORDS_COUNT_DISTINCT: Final = (
    "SELECT COUNT(*) AS source_records, COUNT(DISTINCT work_id) AS works, COUNT(D"
    "ISTINCT edition_id) AS editions, COALESCE(SUM(match_state IN ('unresolved', "
    "'conflicting')), 0) AS unresolved FROM source_records r WHERE EXISTS (SELECT"
    " 1 FROM memberships m WHERE m.record_id = r.id)"
)
DATABASE_STATUS_READING_EVENTS_SELECT_FROM_READING_EVENTS_E_WHERE: Final = (
    "SELECT COUNT(*) FROM reading_events e WHERE EXISTS (SELECT 1 FROM membership"
    "s m WHERE m.record_id = e.record_id)"
)
DATABASE_STATUS_ATTEMPTS_SELECT_COUNT_AS_TOTAL_MAX_CHECKED_AT: Final = (
    "SELECT COUNT(*) AS total, MAX(checked_at) AS last_attempt_at FROM enrichment"
    "_attempts WHERE provider = ?"
)
DATABASE_STATUS_SELECTED_SELECT_COUNT_AS_TOTAL_MAX_E_LAST: Final = (
    "SELECT COUNT(*) AS total, MAX(e.last_success_at) AS last_success_at FROM enr"
    "ichment_active e JOIN enrichment_attempts a ON a.id = e.attempt_id JOIN sour"
    "ce_records r ON r.id = e.record_id WHERE e.provider = ? AND a.identity_hash "
    "= r.identity_hash AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id "
    "= r.id)"
)
DATABASE_STATUS_CANDIDATES_SELECT_COUNT_ENRICHMENT_CANDIDATES_C_JOIN: Final = (
    "SELECT COUNT(*) FROM enrichment_candidates c JOIN enrichment_attempts a ON a"
    ".id = c.attempt_id WHERE a.provider = ?"
)
DATABASE_STATUS_UNRESOLVED_SELECT_COUNT_ENRICHMENT_ATTEMPTS_A_WHERE: Final = (
    "SELECT COUNT(*) FROM enrichment_attempts a WHERE a.provider = ? AND a.state "
    "= ? AND a.id = (SELECT MAX(a2.id) FROM enrichment_attempts a2 WHERE a2.recor"
    "d_id = a.record_id AND a2.provider = a.provider) AND EXISTS (SELECT 1 FROM m"
    "emberships m WHERE m.record_id = a.record_id) AND NOT EXISTS (SELECT 1 FROM "
    "enrichment_candidates c WHERE c.attempt_id = a.id AND c.selected = 1)"
)
ATTEMPTS: Final = "attempts"
SELECTED: Final = "selected"
TOTAL: Final = "total"
DATABASE_STATUS_LAST_SELECT_FROM_RUNS_ORDER_BY_ID_DESC: Final = (
    "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
)
METADATA: Final = "metadata"
SOURCE_RECORDS: Final = "source_records"
WORKS: Final = "works"
EDITIONS: Final = "editions"
STORAGE_DATABASE_PROVIDER_EXPECTED_A_METADATA_PROVIDER: Final = "Expected a metadata provider"
STORAGE_DATABASE_SAVE_ENRICHMENT_ENRICHMENT_TARGET_A_READER_SOURCE: Final = (
    "Enrichment must target a reader source"
)
STORAGE_DATABASE_SAVE_ENRICHMENT_CANDIDATE_FROM_ANOTHER_PROVIDER: Final = (
    "Enrichment contains a candidate from another provider"
)
DATABASE_SAVE_ENRICHMENT_RECORD_SELECT_R_FROM_SOURCE_RECORDS_R_JOIN: Final = (
    "SELECT r.* FROM source_records r JOIN source_accounts a ON a.source = r.sour"
    "ce AND a.account_id = r.account_id WHERE r.source = ? AND r.source_id = ?"
)
STORAGE_DATABASE_SAVE_ENRICHMENT_ENRICHMENT_NOT_BEEN_PUBLISHED_FOR: Final = (
    "Enrichment target has not been published for this source account"
)
DATABASE_SAVE_ENRICHMENT_ATTEMPT_ID_ATTEMPTS_RECORD_ID_PROVIDER: Final = (
    "INSERT INTO enrichment_attempts(record_id, provider, state, checked_at, iden"
    "tity_hash, raw_json, implementation_version) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
IDENTITY_HASH: Final = "identity_hash"
DATABASE_SAVE_ENRICHMENT_CANDIDATE_ID_CANDIDATES_ATTEMPT_ID_PROVIDER: Final = (
    "INSERT INTO enrichment_candidates(attempt_id, provider_id, kind, reason, sel"
    "ected, candidate_json) VALUES (?, ?, ?, ?, ?, ?)"
)
STORAGE_DATABASE_SAVE_ENRICHMENT_OBSERVATIONS_CANDIDATE_ID_FIELD: Final = (
    "INSERT INTO metadata_observations(candidate_id, field, state, scope, value_j"
    "son, source_url, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
STORAGE_DATABASE_SAVE_ENRICHMENT_INSERT_ACTIVE_RECORD_ID_PROVIDER: Final = (
    "INSERT INTO enrichment_active(record_id, provider, attempt_id, candidate_id,"
    " last_success_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(record_id, provider) DO"
    " UPDATE SET attempt_id = excluded.attempt_id, candidate_id = excluded.candid"
    "ate_id, last_success_at = excluded.last_success_at"
)
STORAGE_DATABASE_ENRICHMENT_TARGETS_LIMIT_CANNOT_BE_NEGATIVE: Final = (
    "Enrichment age and limit cannot be negative"
)
PUBLISHED: Final = "published"
REJECTION_REASON: Final = "rejection_reason"
RECORD: Final = "record"
RECORD_JSON: Final = "record_json"
STORAGE_DATABASE_RECORD_HISTORY_SELECT_S_R_RECORD_JSON_S_ID: Final = (
    "SELECT s.*, r.record_json, s.id AS snapshot_id FROM snapshots s JOIN snapsho"
    "t_records r ON r.snapshot_id = s.id WHERE s.source = ? AND s.account_id = ? "
    "AND r.source_id = ? ORDER BY s.id"
)
RAW_JSON: Final = "raw_json"
STORAGE_DATABASE_STAGED_PROGRESS_SELECT_JSON_FROM_PROGRESS_WHERE_RUN: Final = (
    "SELECT raw_json FROM progress WHERE run_id = ? ORDER BY id"
)
PROVIDER: Final = "provider"
STALE_IDENTITY: Final = "stale_identity"
CANDIDATE: Final = "candidate"
OBSERVED_IDENTITY: Final = "observed_identity"
CANDIDATE_JSON: Final = "candidate_json"
STORAGE_DATABASE_METADATA_FOR_SELECT_E_PROVIDER_E_LAST_SUCCESS_AT: Final = (
    "SELECT e.provider, e.last_success_at, a.identity_hash AS observed_identity, "
    "r.identity_hash, c.candidate_json FROM enrichment_active e JOIN enrichment_a"
    "ttempts a ON a.id = e.attempt_id JOIN enrichment_candidates c ON c.id = e.ca"
    "ndidate_id JOIN source_records r ON r.id = e.record_id WHERE r.source = ? AN"
    "D r.account_id = ? AND r.source_id = ? ORDER BY e.provider"
)
DATABASE_MATCH_CANDIDATES_ROWS_SELECT_C_ID_R_SOURCE_R_ACCOUNT: Final = (
    "SELECT c.id, r.source, r.account_id, r.source_id, r.work_id, r.edition_id, t"
    ".source AS target_source, t.account_id AS target_account_id, t.source_id AS "
    "target_source_id, t.work_id AS target_work_id, t.edition_id AS target_editio"
    "n_id, c.kind, c.reason, c.resolution, c.identifiers_json, (SELECT MAX(d.id) "
    "FROM match_decisions d WHERE d.candidate_id = c.id AND d.reversed_by IS NULL"
    " AND d.kind != 'undo') AS decision_id FROM match_candidates c JOIN source_re"
    "cords r ON r.id = c.record_id JOIN source_records t ON t.id = c.target_recor"
    "d_id WHERE (? OR c.resolution = 'pending') ORDER BY c.id"
)
IDENTIFIERS_JSON: Final = "identifiers_json"
STORAGE_DATABASE_REFRESH_AFTER_MAPPING_SET_RESOLUTION_PENDING_WHERE: Final = (
    "UPDATE match_candidates SET resolution = 'pending' WHERE resolution = 'auto_"
    "confirmed' AND (record_id = ? OR target_record_id = ?) AND EXISTS (SELECT 1 "
    "FROM source_records r JOIN source_records t ON t.id = match_candidates.targe"
    "t_record_id WHERE r.id = match_candidates.record_id AND (r.work_id != t.work"
    "_id OR r.edition_id != t.edition_id))"
)
DATABASE_RESOLVE_MATCH_CANDIDATE_SELECT_MATCH_CANDIDATES_WHERE_ID: Final = (
    "SELECT * FROM match_candidates WHERE id = ?"
)
RESOLUTION: Final = "resolution"
STORAGE_DATABASE_RESOLVE_MATCH_EXPECTED_A_PENDING_MATCH_CANDIDATE: Final = (
    "Expected a pending match candidate"
)
ACCEPTED: Final = "accepted"
REJECTED: Final = "rejected"
NOTE: Final = "note"
STORAGE_DATABASE_RESOLVE_MATCH_UPDATE_SET_RESOLUTION_WHERE_ID: Final = (
    "UPDATE match_candidates SET resolution = ? WHERE id = ?"
)
DATABASE_UNDO_MATCH_DECISION_SELECT_FROM_MATCH_DECISIONS_WHERE_ID: Final = (
    "SELECT * FROM match_decisions WHERE id = ?"
)
REVERSED_BY: Final = "reversed_by"
UNDO: Final = "undo"
STORAGE_DATABASE_UNDO_MATCH_EXPECTED_AN_UNREVERSED_MATCHING_DECISION: Final = (
    "Expected an unreversed matching decision"
)
DATABASE_UNDO_MATCH_LATER_SELECT_MATCH_DECISIONS_WHERE_RECORD_ID: Final = (
    "SELECT 1 FROM match_decisions WHERE record_id = ? AND id > ? AND reversed_by"
    " IS NULL AND kind != 'undo' LIMIT 1"
)
STORAGE_DATABASE_UNDO_MATCH_UNDO_LATER_MATCHING_DECISIONS_FIRST: Final = (
    "Undo later matching decisions first"
)
PRIOR_WORK_ID: Final = "prior_work_id"
PRIOR_EDITION_ID: Final = "prior_edition_id"
CANDIDATE_ID: Final = "candidate_id"
REVERTS: Final = "reverts"
STORAGE_DATABASE_UNDO_MATCH_UPDATE_DECISIONS_SET_REVERSED_BY_WHERE: Final = (
    "UPDATE match_decisions SET reversed_by = ? WHERE id = ?"
)
PRIOR_RESOLUTION: Final = "prior_resolution"
STORAGE_DATABASE_BACKUP_BACKUP_DESTINATION_MUST_BE_A_NEW_DISTINCT: Final = (
    "Backup destination must be a new, distinct file"
)
XB: Final = "xb"
SYNC_SYNCSERVICE_PROGRESS_THE_CONNECTOR_PROGRESS_FOR_A_DIFFERENT: Final = (
    "The connector emitted progress for a different source."
)
SOURCE_IDENTITY_MISMATCH: Final = "source_identity_mismatch"
SYNC_SYNCSERVICE_CHECK_SNAPSHOT_THE_COLLECTION_DOES_NOT_BELONG_TO: Final = (
    "The returned collection does not belong to the configured account and scope."
)
ISSUES: Final = "issues"
REQUIRED_FIELDS_UNVERIFIED: Final = "required_fields_unverified"
CHECK_SNAPSHOT_UPDATE_MESSAGE_SOURCE_CAPABILITIES_REMAIN_UNVERIFIED: Final = (
    "Required source capabilities remain unverified: "
)
CHECK_SNAPSHOT_UPDATE_MESSAGE_TEXT: Final = ", "
CONNECTOR_MISSING: Final = "connector_missing"
SOURCE_ISSUES_MESSAGE_NO_CONNECTOR_IS_CONFIGURED: Final = "No connector is configured."
INVALID_SOURCE_CONTRACT: Final = "invalid_source_contract"
SNAPSHOT_ISSUES_MESSAGE_SOURCE_RECORDS_VALIDATION_THE_PRIOR_SNAPSHOT: Final = (
    "Source records failed validation; the prior snapshot was retained."
)
METADATA_NOT_CONFIGURED: Final = "metadata_not_configured"
METADATA_ISSUES_MESSAGE_THIS_METADATA_PROVIDER_IS_ENABLED_BUT_HAS: Final = (
    "This metadata provider is enabled but has no usable credentials or configuration."
)
METADATA_IDENTITY_MISMATCH: Final = "metadata_identity_mismatch"
METADATA_ISSUES_MESSAGE_METADATA_RESULTS_NOT_MATCH_THEIR_REQUESTED: Final = (
    "Metadata results did not match their requested records; nothing was attached."
)
SYNCSERVICE_METADATA_MESSAGE_TEMPLATE: Final = (
    "{v0} records remain pending enrichment; account records are preserved."
)
ACCOUNT_MISSING: Final = "account_missing"
RUN_ISSUES_MESSAGE_THIS_READER_ACCOUNT_IS_NOT_CONFIGURED: Final = (
    "This reader account is not configured."
)
TESTS: Final = "tests"
FIXTURES: Final = "fixtures"
STORYGRAPH: Final = "storygraph"
BUILTINS_INPUT: Final = "builtins.input"
COOKIE: Final = "Cookie"
SET_COOKIE: Final = "Set-Cookie"
CONTENT_TYPE_2: Final = "Content-Type"
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_TEXT_HTML: Final = "text/html"
BOOKYSTATS_CACHE_UTC_TIMESTAMP: Final = "bookystats.persistence.cache._utc_timestamp"
CATALOG_SQLITE: Final = "catalog.sqlite"
TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN: Final = "isbn:9780140328721"
MATILDA: Final = "Matilda"
OTHER_2: Final = "Other"
TEST_CACHE_PERSISTENT_CACHE_IS_RETURNS_DETACHED_DATA_CHANGED_LOCALLY: Final = "Changed locally"
ABSENT: Final = "absent"
IDENTITY: Final = "identity"
FRESH: Final = "fresh"
TEST_CACHE_CORRUPT_DATABASE_AND_ENTRY_ARE_EXPLICIT_ERRORS_BYTES: Final = b"not sqlite DO-NOT-LEAK"
DO_NOT_LEAK: Final = "DO-NOT-LEAK"
TEST_CACHE_CORRUPT_DATABASE_AND_UPDATE_METADATA_CACHE_SET_PAYLOAD: Final = (
    "UPDATE metadata_cache SET payload = ?"
)
TEST_CACHE_CORRUPT_DATABASE_AND_CORRUPT_ERRORS_BROKEN_DO_NOT_LEAK: Final = (
    '{"broken":"DO-NOT-LEAK"}'
)
INVALID: Final = "invalid"
NAN: Final = "nan"
INF: Final = "inf"
TEST_CACHE_INVALID_JSON_DOES_NOT_REPLACE_A_GOOD_ENTRY_INF: Final = "-inf"
X_2: Final = "x"
VALID: Final = "valid"
TEST_CACHE_EXPIRY_TAMPERING_IS_NOT_CACHE_SET_EXPIRES_AT_EXPIRES: Final = (
    "UPDATE metadata_cache SET expires_at = expires_at + 1000"
)
TEST_CACHE_NON_ASCII_CHECKSUM_UPDATE_METADATA_CACHE_SET_CHECKSUM: Final = (
    "UPDATE metadata_cache SET checksum = ?"
)
TEST_CACHE_NON_ASCII_CHECKSUM_DAMAGE_IS_AN_OPERATIONAL_ERROR_TEXT: Final = "\u2603"
DO_NOT_PRINT_THIS: Final = "do-not-print-this"
TEST_CLI_UNATTENDED_WITHOUT_INPUT_UNATTENDED_EXECUTION_PROMPTED: Final = (
    "unattended execution prompted"
)
DISABLED: Final = "disabled"
TEST_CONFIG_SETTINGS_ROUND_TRIP_GOODREADS_COM_USER_SHOW_READER: Final = (
    "https://www.goodreads.com/user/show/123-reader"
)
API_KEY: Final = "api_key"
GOODREADS: Final = "goodreads"
TEST_CONFIG_INVALID_PROFILE_REJECTS_WWW_GOODREADS_COM_AUTHOR_SHOW: Final = (
    "https://www.goodreads.com/author/show/123"
)
TEST_CONFIG_INVALID_PROFILE_REJECTS_GOODREADS_COM_EVIL_EXAMPLE_USER: Final = (
    "https://www.goodreads.com.evil.example/user/show/123"
)
TEST_CONFIG_INVALID_PROFILE_REJECTS_WWW_GOODREADS_COM_USER_SHOW: Final = (
    "http://www.goodreads.com/user/show/123"
)
TEST_CONFIG_INVALID_PROFILE_REJECTS_GOODREADS_COM_USER_SHOW_KEY: Final = (
    "https://www.goodreads.com/user/show/123?key=private-value"
)
PRIVATE: Final = "private-value"
TEST_CONFIG_INVALID_CONFIG_DOES_NOT_ECHO_INPUT_UNKNOWN_PRIVATE: Final = (
    '{"unknown":"private-value"}'
)
TEST_CONFIG_WEEKLY_SCHEDULE_REQUIRES_EXPLICIT_TIME_TIME_TEXT: Final = "26:10"
UTC: Final = "UTC"
TEST_REJECTS_AN_ACCOUNT_FOR_A_APP_THESTORYGRAPH_COM_PROFILE_READER: Final = (
    "https://app.thestorygraph.com/profile/reader"
)
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4: Final = "9780140328721"
OWNED: Final = "owned"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_6: Final = "1988"
TEST_GOODREADS_INVALID_ISBN_IS_NOT_PROMOTED_TO_AN_IDENTIFIER_TEXT_2: Final = "1234567890123"
DATE: Final = "date"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT: Final = "2024"
TEST_GOOGLE_BOOKS_FAKEHTTP_FETCH_UNEXPECTED_METADATA_REQUEST: Final = "Unexpected metadata request"
TEST_GOOGLE_BOOKS_RESPONSE_URL_HTTPS_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES: Final = (
    "https://www.googleapis.com/books/v1/volumes?key=SECRET-RECEIPT-KEY"
)
TEST_GOOGLE_BOOKS_RESPONSE_HEADERS_APPLICATION_JSON_CHARSET_UTF: Final = (
    "application/json; charset=utf-8"
)
GOOGLE_BOOKS_JSON: Final = "google_books.json"
ORIGINAL_READER_BOOK_ID: Final = "original-reader-book-id"
TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL: Final = "Roald Dahl"
TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT: Final = "0140328726"
TEST_GOOGLE_BOOKS_BOOK_URL_THESTORYGRAPH_COM_BOOKS_ORIGINAL_READER: Final = (
    "https://app.thestorygraph.com/books/original-reader-book-id"
)
PRIVATE_READER_REVIEW: Final = "PRIVATE-READER-REVIEW"
SECRET_API_KEY: Final = "SECRET-API-KEY"
TESTVOLUME_1: Final = "testVolume_1"
TEST_GOOGLE_BOOKS_ISBN_SEARCH_EXTRACTS_HTTPS_BOOKS_GOOGLE_COM_BOOKS: Final = (
    "https://books.google.com/books?id=testVolume_1"
)
TEST_GOOGLE_BOOKS_ISBN_SEARCH_CATALOG_WITHOUT_PRIVATE_FIELDS_TEXT: Final = "1988-10"
TEST_GOOGLE_BOOKS_ISBN_SEARCH_PRIVATE_FIELDS_JUVENILE_FICTION: Final = "Juvenile Fiction"
TEST_GOOGLE_BOOKS_ISBN_SEARCH_FIELDS_SYNTHETIC_CATALOG_FIXTURE_NO: Final = (
    "Synthetic catalog fixture, not publisher copy ."
)
AUTHORIZATION: Final = "Authorization"
TEST_GOOGLE_BOOKS_APPLICATION_KEY_IS_EVEN_FOR_PUBLIC_DATA_TEXT: Final = "   "
TESTVOLUME_2: Final = "testVolume_2"
TEST_GOOGLE_BOOKS_ISBN_MISS_AMBIGUITY_INTITLE_MATILDA_INAUTHOR_R: Final = (
    'intitle:"matilda" inauthor:"roald dahl"'
)
TEST_GOOGLE_BOOKS_TITLE_ONLY_OR_NOT_A_VERIFIED_FALLBACK_SOMEONE_ELSE: Final = "Someone Else"
TEST_GOOGLE_BOOKS_ESCAPED_PARAMETERS_CANNOT_TITLE_THE_BOOK_KEY_OTHE: Final = (
    'The "Book" & /?key=other'
)
TEST_GOOGLE_BOOKS_ESCAPED_PARAMETERS_CANNOT_AUTHOR_ANNE_OR_O_NEIL_C: Final = (
    'Anne "OR" O\'Neil & Co'
)
TEST_ESCAPED_PARAMETERS_CANNOT_CHANGE_RESULT_API_KEY_PRIVATE_KEY: Final = "private&key"
TEST_GOOGLE_BOOKS_ESCAPED_PARAMETERS_CANNOT_INTITLE_THE_BOOK_KEY_OT: Final = (
    'intitle:"the book key other" inauthor:"anne or o neil co"'
)
TEST_GOOGLE_BOOKS_PUBLICATION_DATE_PRESERVES_SOURCE_PRECISION_TEXT: Final = "1988-10-01"
FIELD: Final = "field"
TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_NOT_FABRICATED_METRICS_TEXT: Final = "1988-02-30"
TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_NOT_FABRICATED_METRICS_TEXT_2: Final = "1988-2"
TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_NOT_FABRICATED_METRICS_T12_Z: Final = "1988-02-01T12:00:00Z"
EN: Final = "en"
FICTION: Final = "Fiction"
TEST_GOOGLE_BOOKS_WRONG_ENVELOPES_OF_BECOMING_EMPTY_RESULTS_TEXT: Final = "0"
FAILURE: Final = "failure"
MESSAGE: Final = "message"
TEST_GOOGLE_BOOKS_TRANSIENT_FAILURES_FAILED_HTTPS_WWW_GOOGLEAPIS_C: Final = (
    "Failed https://www.googleapis.com/books/v1/volumes?key=SECRET-API-KEY"
)
TEST_HTML_LOGIN_AND_UNSAFE_VOLUME_HTTPS_ACCOUNTS_GOOGLE_COM_LOGIN_KE: Final = (
    "https://accounts.google.com/login?key=SECRET"
)
TEST_HTML_LOGIN_AND_UNSAFE_VOLUME_CATALOG_SUCCESS_HTML_BODY_BYTES: Final = (
    b"<html>Sign in SECRET</html>"
)
SECRET: Final = "SECRET"
TEST_GOOGLE_BOOKS_HTML_LOGIN_AND_SUCCESS_UNSAFE_HTTPS_EVIL_EXAMPLE: Final = (
    "https://evil.example/?key=SECRET"
)
SECRET_KEY_ONE: Final = "SECRET-KEY-ONE"
SECRET_KEY_TWO: Final = "SECRET-KEY-TWO"
TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES: Final = b"SECRET-"
TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES_2: Final = b"DO-NOT-CACHE"
TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES_3: Final = b"PRIVATE-READER"
TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_SELECT_CACHE: Final = (
    "SELECT cache_key FROM metadata_cache"
)
TEST_STALE_CACHE_IS_REFETCHED_CACHED_MISSING_UPDATE_UNLISTED_TITLE: Final = "Unlisted title"
TEST_GOOGLE_BOOKS_CACHE_DAMAGE_IS_UPDATE_METADATA_CACHE_SET_PA: Final = (
    "UPDATE metadata_cache SET payload = '{}'"
)
TEST_GOOGLE_BOOKS_REPEATED_CONFIRMABLE_CANDIDATE_CONTRADICTORY: Final = (
    "Contradictory catalog identity"
)
TEST_GOOGLE_BOOKS_REAL_TRANSPORT_SECRET_PRIVATE_KEY_ANOTHER: Final = "PRIVATE&key=another?value"
PRIVATE_2: Final = "PRIVATE"
TEST_LOCKING_OVERLAPPING_SYNC_IS_CONCURRENT_SYNC_ACQUIRED_THE_LOCK: Final = (
    "a concurrent sync acquired the lock"
)
STORYGRAPH_RECORD: Final = "storygraph-record"
TEST_MATCHING_BOOK_HTTPS_APP_COM_BOOKS_STORYGRAPH_RECORD: Final = (
    "https://app.thestorygraph.com/books/storygraph-record"
)
VOLUME_ONE: Final = "volume-one"
TEST_MATCHING_CANDIDATE_HTTPS_BOOKS_GOOGLE_COM_BOOKS_ID_VOLUME: Final = (
    "https://books.google.com/books?id=volume-one"
)
ANOTHER_ID: Final = "another-id"
TEST_ISBN10_AND_ISBN13_CORROBORATE_SOURCE_IDS_MATCH_ISBNS_TEXT: Final = "0-14-032872-6"
CHANGES: Final = "changes"
TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR: Final = "A Different Author"
TEST_MATCHING_SHARED_ISBN_WITH_MATILDA_AND_OTHER_STORIES_OMNIBU: Final = (
    "Matilda and Other Stories: Omnibus"
)
TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_MATILDA_PART_TWO: Final = "Matilda, Part Two"
FR: Final = "fr"
AUDIOBOOK: Final = "audiobook"
PAPERBACK: Final = "paperback"
TEST_MATCHING_TITLE_AUTHOR_ONLY_AND_ARE_LIKELY_NOT_CONFIRMED_TEXT: Final = "9780140328722"
STORYGRAPH_UUID: Final = "storygraph-uuid"
TEST_MATCHING_FULL_TITLE_IS_NOT_MERGE_PARTS_TITLE_MATILDA_PART_ONE: Final = "Matilda: Part One"
TEST_MATCHING_FULL_TITLE_IS_NOT_MERGE_PARTS_TITLE_MATILDA_PART_TWO: Final = "Matilda: Part Two"
MATILDA_2: Final = "MATILDA"
TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE: Final = "Quentin Blake"
TEST_NORMALIZED_FULL_TITLES_AND_CAN_CORROBORATE_RIGHT_TITLE_MATILDA: Final = "  Matilda! "
OTHER_EDITION: Final = "other-edition"
TEST_MATCHING_METADATA_REQUIRES_CANDIDATE_AUTHORS_DIFFERENT_AUTHOR: Final = "Different Author"
TEST_UNRELATED_SEARCH_HITS_DO_NOT_UNRELATED_TITLE_AN_UNRELATED_WORK: Final = "An Unrelated Work"
TEST_UNRELATED_SEARCH_HITS_DO_EVIDENCE_UNRELATED_ISBNS_TEXT: Final = "9780306406157"
TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_MONTH_TEXT: Final = "2024-02"
TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_LEAP_DAY_FEBRUARY: Final = "February 29, 2024"
TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_TEXT: Final = "2024-02-29"
TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_TEXT_2: Final = "02/03/2024"
TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_TEXT_3: Final = "2023-02-29"
TEST_INVALID_READING_ORDER_IS_NOT_SILENTLY_NORMALIZED_STARTED_TEXT: Final = "2026-03-01"
TEST_INVALID_READING_ORDER_IS_NOT_SILENTLY_NORMALIZED_FINISHED_TEXT: Final = "2026-02-01"
TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT: Final = '="0061120081"'
TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2: Final = "9780061120084"
TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_3: Final = "978-0-06-112008-4"
TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_4: Final = "9780061120085"
FBDD6B7C_F512_47F2_AA94_D8BF0D5F5175: Final = "fbdd6b7c-f512-47f2-aa94-d8bf0d5f5175"
TEST_MODELS_MISSING_OBSERVATION_IS_THESTORYGRAPH_COM_BOOKS_EXAMPLE: Final = (
    "https://app.thestorygraph.com/books/example"
)
TEST_MODELS_COMPLETE_SNAPSHOT_REQUIRES_AND_IDENTITY_ACCOUNT_ID_TEXT: Final = "123"
TEST_REDIRECT_OUTSIDE_SOURCE_IS_HEADERS_HTTPS_OTHER_INVALID_PRIVATE: Final = (
    "https://other.invalid/private"
)
SOURCE_INVALID: Final = "source.invalid"
OUTSIDE: Final = "outside"
TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS: Final = (
    "https://source.invalid/books"
)
TEST_RETRY_AFTER_LARGE_DELAY_HAMMER_PROVIDER_HANDLE_HEADERS_TEXT: Final = "3600"
PRIVATE_3: Final = "private-test-value"
SET_COOKIE_2: Final = "set-cookie"
PRIVATE_SESSION: Final = "private-session"
TEST_TRANSIENT_ERROR_RETRIES_BUT_CONTAIN_KEY_HANDLE_CONTENT_BYTES: Final = b'{"items":[]}'
PRIVATE_4: Final = "private"
TEST_RESPONSE_BUDGET_AND_NETWORK_EXPLICIT_TRANSPORT_CONTENT_BYTES: Final = b"too large"
TEST_NET_RESPONSE_BUDGET_AND_NETWORK_ARE_EXPLICIT_MATCH_SIZE_LIMIT: Final = "size limit"
SECRET_IN_EXCEPTION: Final = "secret-in-exception"
SECRET_2: Final = "secret"
TEST_NET_UNSAFE_URLS_FAIL_BEFORE_REQUEST_HTTP_SOURCE_INVALID_BOOKS: Final = (
    "http://source.invalid/books"
)
TEST_NET_UNSAFE_URLS_FAIL_BEFORE_SOURCE_INVALID_EVIL_EXAMPLE_BOOKS: Final = (
    "https://source.invalid.evil.example/books"
)
TEST_NET_UNSAFE_URLS_FAIL_BEFORE_USER_PASSWORD_SOURCE_INVALID_BOOKS: Final = (
    "https://user:password@source.invalid/books"
)
TEST_NET_UNSAFE_URLS_FAIL_BEFORE_REQUEST_HTTPS_SOURCE_INVALID_BOOKS: Final = (
    "https://source.invalid:444/books"
)
TEST_NET_UNSAFE_URLS_FAIL_BEFORE_REQUEST_FILE_C_PRIVATE: Final = "file:///C:/private"
TEST_NET_UNSAFE_URLS_FAIL_UNSAFE_NAVIGATION_REACHED_THE_TRANSPORT: Final = (
    "unsafe navigation reached the transport"
)
OPEN_LIBRARY_JSON: Final = "open_library.json"
ORIGINAL_WATCHLIST_BOOK: Final = "original-watchlist-book"
TEST_OPEN_LIBRARY_BOOK_URL_HTTPS_WWW_GOODREADS_COM_BOOK_SHOW: Final = (
    "https://www.goodreads.com/book/show/123456"
)
PRIVATE_SHELF: Final = "PRIVATE-SHELF"
OL45883W: Final = "OL45883W"
TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_HTTPS_OPE: Final = (
    "https://openlibrary.org/works/OL45883W"
)
TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_TEXT: Final = "9780142410370"
ENG: Final = "eng"
FRE: Final = "fre"
TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_ISBN: Final = "(isbn:9780140328721)"
OL123W: Final = "OL123W"
TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_HITS_TO_KILL_A_MOCKINGBIRD: Final = "To Kill a Mockingbird"
TEST_OPEN_LIBRARY_DISTINCT_BOOKS_INDIVIDUAL_CACHE_HITS_HARPER_LEE: Final = "Harper Lee"
SECOND_ORIGINAL_ID: Final = "second-original-id"
TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_CACHE_HITS_ISBN_OR_ISBN: Final = (
    "(isbn:9780140328721) OR (isbn:9780061120084)"
)
TEST_HUGE_WATCHLIST_IS_ONE_THE_REMAINDER_BOOKS_UPDATE_TEMPLATE: Final = "Unknown book {v0}"
TEST_OPEN_LIBRARY_HUGE_WATCHLIST_DEFERS_THE_REMAINDER_TITLE: Final = "title:"
TEST_OPEN_LIBRARY_REPEATED_IDENTITY_NOT_REPEATED_NETWORK_WORK_ISBN: Final = "isbn:"
OTHER_3: Final = "other"
UNKNOWN: Final = "Unknown"
TEST_OPEN_LIBRARY_AMBIGUOUS_WORK_REMAIN_CANDIDATES_WORKS_OL123W: Final = "/works/OL123W"
TEST_TITLE_AUTHOR_SEARCH_IS_VERIFIED_ESCAPED_BOOK_UPDATE_MATILDA_OR: Final = 'Matilda " OR *:* &'
TEST_TITLE_AUTHOR_SEARCH_IS_VERIFIED_BOOK_UPDATE_ROALD_DAHL_CO: Final = 'Roald "Dahl" & Co'
TEST_OPEN_LIBRARY_TITLE_AUTHOR_SEARCH_TITLE_MATILDA_OR_AND_AUTHOR: Final = (
    '(title:"matilda or" AND author:"roald dahl co")'
)
TEST_OPEN_LIBRARY_TITLE_AUTHOR_SEARCH_IS_ESCAPED_NOT_THE_AUTHOR: Final = "Not the author"
TEST_OPEN_LIBRARY_MALFORMED_ENVELOPES_PROVIDER_ERROR_PRIVATE_TOKEN: Final = (
    "Provider error PRIVATE-TOKEN"
)
PRIVATE_TOKEN: Final = "PRIVATE-TOKEN"
TEST_OPEN_LIBRARY_TRANSIENT_FUTURE_INVOCATION_HTTPS_OPENLIBRARY: Final = (
    "https://openlibrary.org/search.json?token=PRIVATE-TOKEN"
)
TEST_HTML_AND_UNSAFE_WORK_LINKS_HTTPS_OPENLIBRARY_ORG_ACCOUNT_LOGIN: Final = (
    "https://openlibrary.org/account/login"
)
TEST_HTML_AND_UNSAFE_WORK_LINKS_EXPLICIT_FAILURES_HTML_BODY_BYTES: Final = (
    b"<html>Login PRIVATE-TOKEN</html>"
)
TEST_OPEN_LIBRARY_HTML_AND_UNSAFE_WORKS_OL123W_TOKEN_PRIVATE_TOKEN: Final = (
    "/works/OL123W?token=PRIVATE-TOKEN"
)
UNAVAILABLE: Final = "unavailable"
TEST_OPEN_LIBRARY_CACHE_IS_CATALOG_AND_CORRUPTION_IS_EXPLICIT_BYTES: Final = b"PRIVATE-SHELF"
TEST_OPEN_LIBRARY_INJECTED_TRANSPORT_AGENT_BOOKYSTATS_OPERATOR_E: Final = (
    "BookyStats/0.1 (operator@example.test)"
)
BOOKYSTATS_SCHEDULING_IMPLEMENTATION_FINGERPRINT: Final = (
    "bookystats.runtime.scheduling.implementation_fingerprint"
)
CURRENT: Final = "current"
TEST_SCHEDULING_WEEKLY_GATE_REQUIRES_EVIDENCE_MATCH_TWO_CONSECUTIVE: Final = "two consecutive"
OLD: Final = "old"
TEST_SCHEDULING_IMPLEMENTATION_OR_GATE_MATCH_CURRENT_DATABASE: Final = "current database"
TEST_SCHEDULING_IMPLEMENTATION_OR_GATE_MATCH_THIS_IMPLEMENTATION: Final = "this implementation"
STALE: Final = "stale"
SETTINGS_WEEKLY_TIME_TEXT: Final = "09:30"
PYTHON_EXE: Final = "python.exe"
T: Final = "t"
TEST_SCHEDULING_XML_USES_SAME_CLI_CATCHES_MISSED_RUNS_T_LOGONTYPE: Final = ".//t:LogonType"
TEST_SCHEDULING_XML_USES_SAME_MISSED_RUNS_T_STARTWHENAVAILABLE: Final = ".//t:StartWhenAvailable"
TEST_SCHEDULING_XML_USES_SAME_MISSED_RUNS_T_MULTIPLEINSTANCESPOLICY: Final = (
    ".//t:MultipleInstancesPolicy"
)
TEST_SCHEDULING_XML_USES_SAME_CATCHES_MISSED_RUNS_T_STARTBOUNDARY: Final = ".//t:StartBoundary"
TEST_SCHEDULING_XML_USES_SAME_CLI_AND_CATCHES_MISSED_RUNS_T09: Final = "2026-11-02T09:30:00"
TEST_SCHEDULING_XML_USES_SAME_CLI_MISSED_RUNS_ARGUMENTS_T_ARGUMENTS: Final = ".//t:Arguments"
TEST_STORAGE_START_T10: Final = "2026-10-01T10:00:00+00:00"
TEST_STORAGE_FINISH_T10: Final = "2026-10-01T10:02:00+00:00"
TEST_STORAGE_LATER_T10: Final = "2026-10-02T10:00:00+00:00"
TEST_STORAGE_LATER_FINISH_T10: Final = "2026-10-02T10:02:00+00:00"
STORAGE: Final = "storage"
CASE: Final = "case-"
LIBRARY_SQLITE: Final = "library.sqlite"
ONE_2: Final = "one"
TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE: Final = (
    "https://app.thestorygraph.com/books/one"
)
TEST_STORAGE_SNAPSHOT_ACCOUNT_ID_TEXT: Final = "42"
TEST: Final = "test"
VOLUME: Final = "volume"
TEST_STORAGE_METADATA_CANDIDATE_HTTPS_GOOGLE_COM_BOOKS_ID_VOLUME: Final = (
    "https://books.google.com/books?id=volume"
)
RETRY: Final = "retry"
TEST_STORAGE_NONCOMPLETE_EMPTY_ATTEMPT_ID_FROM_SNAPSHOTS_WHERE_PUB: Final = (
    "SELECT id FROM snapshots WHERE published = 0"
)
TWO_2: Final = "two"
TEST_COMPLETE_EMPTY_REMOVES_ONLY_SECOND_TITLE_DIFFERENT_WORK: Final = "Different Work"
THIRD: Final = "third"
TEST_STORAGE_COMPLETE_EMPTY_REMOVES_SELECT_ID_FROM_SOURCE_RECORDS: Final = (
    "SELECT id FROM source_records"
)
PARTIAL: Final = "partial"
TEST_STORAGE_PARTIAL_EVIDENCE_IS_DATA_SELECT_ID_FROM_OBSERVATIO: Final = (
    "SELECT id FROM observations"
)
READING_1: Final = "reading-1"
EVENT_STARTED_TEXT: Final = "2020"
EVENT_FINISHED_TEXT: Final = "2020-07"
TEST_STORAGE_REIMPORT_IGNORES_CHECK_READINGS_SELECT_ID_FROM_READING: Final = (
    "SELECT id FROM reading_observations"
)
TEST_STORAGE_READING_IDENTITIES: Final = (
    "SELECT id, event_key, source_event_id FROM reading_events ORDER BY id"
)
TEST_STORAGE_CHANGED_SOURCE: Final = "changed_source"
TEST_STORAGE_RETRY_STATE: Final = "retry_state"
TEST_STORAGE_FIXED_CLOCK: Final = "utc_now"
OLD_READ: Final = "old-read"
OLD_EVENT_FINISHED_TEXT: Final = "2015-03"
TEST_CURRENT_RATING_AND_REVIEW_RATINGS_REVIEW_ORIGINAL_REVIEW: Final = "Original review"
UPDATED_UPDATE_UPDATE_RECONSIDERED_REVIEW: Final = "Reconsidered review"
TEST_STORAGE_CURRENT_RATING_AND_REVIEW_RATINGS_SELECT_ID_FROM_RE: Final = (
    "SELECT id FROM reading_events"
)
TEST_STORAGE_CURRENT_RATING_AND_READING_RATINGS_PERSISTED_EVENT_S: Final = (
    "SELECT event_json FROM reading_events"
)
JSON_2: Final = "value_json"
TEST_STORAGE_CURRENT_RATING_AND_READING_RATINGS_SELECT_JSON: Final = (
    "SELECT value_json FROM observations WHERE field = ? ORDER BY id"
)
FIRST: Final = "first"
EVENTS_FINISHED_TEXT: Final = "2019"
SECOND: Final = "second"
EVENTS_FINISHED_TEXT_2: Final = "2024-05"
COUNT_ONLY: Final = "count-only"
TEST_REREADS_ARE_EXPLICIT_EVENTS_NOT_ONLY_COUNT_TITLE_OTHER_BOOK: Final = "Other Book"
STARTED_STARTED_TEXT: Final = "2026-09-10"
FINISHED_UPDATE_TEXT: Final = "2026-09-20"
TEST_STORAGE_VALID_CROSS_SOURCE_IDENTITY_ID_FROM_MATCH_DECISIONS_W: Final = (
    "SELECT id FROM match_decisions WHERE kind = 'automatic'"
)
TEST_SHARED_ISBN_WITH_CONFLICTING_CONFLICTING_AUTHORS_NOT_ROALD_DAHL: Final = "Not Roald Dahl"
CONFLICT_POSITION: Final = "conflict_position"
CONFLICT: Final = "conflict"
LIKELY: Final = "likely"
TEST_EXACT_TITLE_AUTHOR_REQUIRES_DECISION_ID_NOTE_READER_CONFIRMED: Final = "Reader confirmed"
UNREVERSED: Final = "unreversed"
DECISION_ID: Final = "decision_id"
TEST_STORAGE_SOURCE_IDS_ARE_NAMESPACED_WORK_ID_EDITION_ID_FIRST_SEE: Final = (
    "SELECT work_id, edition_id, first_seen FROM source_records"
)
TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_TITLE_DIFFERENT_BOOK: Final = "Different Book"
TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_AUTHORS_OTHER_AUTHOR: Final = "Other Author"
TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_CHANGED_TITLE_CORRECTED_TITLE: Final = "Corrected Title"
TEST_STORAGE_SOURCE_IDS_ARE_NAMESPACED_WORK_ID_EDITION_ID_FIRST_SEEN: Final = (
    "SELECT work_id, edition_id, first_seen FROM source_records WHERE source = ?"
)
FOREIGN_ACCOUNT: Final = "foreign-account"
FOREIGN: Final = "foreign"
ANOTHER_READER: Final = "another-reader"
TEST_STORAGE_ACCOUNT_CHANGE_IS_ACCOUNT_ID_FROM_SOURCE_ACCOUN: Final = (
    "SELECT account_id FROM source_accounts"
)
DIFFERENT_ACCOUNT: Final = "different-account"
DIFFERENT: Final = "different"
NEWER: Final = "newer"
IDENTITY_VERIFIED: Final = "identity_verified"
BAD_CALLER: Final = "bad-caller"
TEST_STORAGE_COMPLETE_MODEL_COPY_ANY_REMOVAL_MATCH_VERIFIED_IDENTITY: Final = "verified identity"
TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_IDENTITY_FAIL_AFTER_ONE_INJECT: Final = (
    "Injected publication failure"
)
TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_AND_IDENTITY_SAVE_RECORD: Final = "_save_record"
ROLLBACK_2: Final = "rollback"
INJECTED: Final = "Injected"
TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_IDENTITY_SELECT_ID_FROM_SNAPSH: Final = (
    "SELECT id FROM snapshots"
)
SAME: Final = "same"
EVENTS_FINISHED_TEXT_3: Final = "2021"
CONFLICTING_EVENTS: Final = "conflicting-events"
TEST_STORAGE_CONFLICTING_EXPLICIT_MATCH_CONFLICTING_OBSERVATIONS: Final = "conflicting observations"
EVENTS_FINISHED_TEXT_4: Final = "2021-06"
EVENTS_FINISHED_RAW_JUNE: Final = "June 2021"
EVENTS_FINISHED_TEXT_5: Final = "2022-05-04"
EVENTS_FINISHED_RAW_MAY: Final = "May 4, 2022"
ORIGINAL_ADDED_AT_TEXT: Final = "2018-03"
ORIGINAL_ADDED_AT_RAW_MARCH: Final = "March 2018"
MISSING_ADDED: Final = "missing-added"
TEST_PRECISION_DATES_AND_SOURCE_MISSING_ADDED_TITLE_ANOTHER_WORK: Final = "Another Work"
TEST_STORAGE_PRECISION_DATES_AND_SOURCE_SELECT_FIRST_SEEN_FROM_SO: Final = (
    "SELECT first_seen FROM source_records WHERE source_id = ?"
)
TEST_STORAGE_SQL_METACHARACTERS_REMAIN_DROP_TABLE_SOURCE_RECORDS: Final = (
    "'; DROP TABLE source_records; --"
)
TEST_SQL_METACHARACTERS_REMAIN_DATA_ORIGINAL_TITLE_O_REILLY: Final = "O'Reilly "
RESUME: Final = "resume"
NEXT_PAGE: Final = "next-page"
FOREIGN_KEYS: Final = "foreign_keys"
JOURNAL_MODE: Final = "journal_mode"
WAL: Final = "wal"
BUSY_TIMEOUT: Final = "busy_timeout"
USER_VERSION: Final = "user_version"
TEST_STORAGE_RESTART_BACKUP_PRAGMAS_AND_STATUS_JSON_PRAGMA: Final = "PRAGMA "
BACKUP_SQLITE: Final = "backup.sqlite"
TEST_STORAGE_RESTART_BACKUP_PRAGMAS_STATUS_JSON_MATCH_NEW_DISTINCT: Final = "new, distinct"
TEST_STORAGE_CONFIDENT_METADATA_IS_SCOPE_SOURCE_URL_FROM_METADATA: Final = (
    "SELECT scope, source_url FROM metadata_observations"
)
TEST_STORAGE_AMBIGUOUS_AND_FAILED_SELECTION_SELECT_ID_FROM_ENRICHM: Final = (
    "SELECT id FROM enrichment_candidates WHERE selected = 1"
)
GOOGLE_BOOKS: Final = "google_books"
TEST_STORAGE_TITLE_ONLY_PROVIDER_KIND_FROM_ENRICHMENT_CANDIDATES: Final = (
    "SELECT kind FROM enrichment_candidates"
)
TEST_STORAGE_PROVIDER_READER_FIELDS_ARE_SELECT_ID_FROM_METADATA_OBS: Final = (
    "SELECT id FROM metadata_observations"
)
TEST_METADATA_REFRESH_TRACKS_IDENTITY_TITLE_MATILDA_A_DIFFERENT_EDIT: Final = (
    "Matilda: A Different Edition"
)
NEGATIVE: Final = "negative"
MISSING: Final = "missing"
TEST_STORAGE_PROVIDER_AND_TARGET_WRITES_MATCH_NOT_BEEN_PUBLISHED: Final = "not been published"
TEST_STORAGE_PROVIDER_AND_TARGET_WRITES_MATCH_ANOTHER_PROVIDER: Final = "another provider"
TEST_STORAGE_PROVIDER_AND_TARGET_SELECT_ID_FROM_ENRICHMENT_ATTEMPTS: Final = (
    "SELECT id FROM enrichment_attempts"
)
GRIEF: Final = "grief"
TEST_SYNC_ACCOUNTS_PROFILE_URL_HTTPS_WWW_GOODREADS_COM_USER_SHOW: Final = (
    "https://www.goodreads.com/user/show/123"
)
TEST_SYNC_AUTHREQUIREDCONNECTOR_COLLECT_SIGN_IN_TO_THE_SOURCE_AGAIN: Final = (
    "Sign in to the source again."
)
AUTHENTICATION_REQUIRED: Final = "authentication_required"
CAPABILITIES: Final = "capabilities"
SOMEONE_ELSE: Final = "someone_else"
DIFFERENT_BOOK: Final = "different-book"
TEST_METADATA_CANNOT_ATTACH_TO_A_DIFFERENT_RECORD_SOURCE_ID_TEXT: Final = "1234"
TEST_METADATA_CANNOT_ATTACH_TO_A_DIFFERENT_RECORD_TITLE_A_BOOK: Final = "A book"
TEST_METADATA_CANNOT_ATTACH_TO_A_HTTPS_WWW_GOODREADS_COM_BOOK_SHOW: Final = (
    "https://www.goodreads.com/book/show/1234"
)
UNRELATED: Final = "unrelated"
OPEN_LIBRARY: Final = "open_library"
BLOCKED: Final = "blocked"
NOT_CONFIGURED: Final = "not_configured"
INTERRUPTED: Final = "interrupted"
PRESENT: Final = "present"
EMPTY_2: Final = "empty"
UNSUPPORTED: Final = "unsupported"
DID_NOT_FINISH: Final = "did-not-finish"
UNKNOWN_2: Final = "unknown"

ObservationScope = Literal["reader", "work", "edition"]

DatePrecision = Literal["year", "month", "day"]

IMPORT_TITLE: Final = "Title"
IMPORT_PROCESSING_VERSION: Final = "csv-v6-storygraph-supplemental-completion"
IMPORT_AUTHOR: Final = "Author"
IMPORT_AUTHORS: Final = "Authors"
IMPORT_BOOK_ID: Final = "Book Id"
IMPORT_AUTHOR_SORT: Final = "Author l-f"
IMPORT_ADDITIONAL_AUTHORS: Final = "Additional Authors"
IMPORT_ISBN: Final = "ISBN"
IMPORT_ISBN13: Final = "ISBN13"
IMPORT_UID: Final = "ISBN/UID"
IMPORT_MY_RATING: Final = "My Rating"
IMPORT_AVERAGE_RATING: Final = "Average Rating"
IMPORT_PUBLISHER: Final = "Publisher"
IMPORT_BINDING: Final = "Binding"
IMPORT_PAGES: Final = "Number of Pages"
IMPORT_YEAR: Final = "Year Published"
IMPORT_ORIGINAL_YEAR: Final = "Original Publication Year"
IMPORT_DATE_READ: Final = "Date Read"
IMPORT_DATE_ADDED: Final = "Date Added"
IMPORT_BOOKSHELVES: Final = "Bookshelves"
IMPORT_POSITIONS: Final = "Bookshelves with positions"
IMPORT_EXCLUSIVE_SHELF: Final = "Exclusive Shelf"
IMPORT_MY_REVIEW: Final = "My Review"
IMPORT_SPOILER: Final = "Spoiler"
IMPORT_PRIVATE_NOTES: Final = "Private Notes"
IMPORT_READ_COUNT: Final = "Read Count"
IMPORT_OWNED_COPIES: Final = "Owned Copies"
IMPORT_FORMAT: Final = "Format"
IMPORT_READ_STATUS: Final = "Read Status"
IMPORT_LAST_DATE_READ: Final = "Last Date Read"
IMPORT_DATES_READ: Final = "Dates Read"
IMPORT_STAR_RATING: Final = "Star Rating"
IMPORT_REVIEW: Final = "Review"
IMPORT_MOODS: Final = "Moods"
IMPORT_PACE: Final = "Pace"
IMPORT_TAGS: Final = "Tags"
IMPORT_WARNINGS: Final = "Content Warnings"
IMPORT_PUBLISHER_FIELD: Final = "publisher"
IMPORT_ORIGINAL_PUBLICATION_FIELD: Final = "original_publication_date"
IMPORT_AUTHOR_SORT_FIELD: Final = "author_sort_name"
IMPORT_PRIVATE_NOTES_FIELD: Final = "private_notes"
IMPORT_SPOILER_FIELD: Final = "review_contains_spoilers"
IMPORT_OWNED_COPIES_FIELD: Final = "owned_copies"
IMPORT_POSITIONS_FIELD: Final = "shelf_positions"
IMPORT_IDENTITY_FIELD: Final = "import_identity_kind"
IMPORT_NATIVE_IDENTITY: Final = "native"
IMPORT_ISBN_IDENTITY: Final = "isbn"
IMPORT_SYNTHETIC_IDENTITY: Final = "synthetic"
IMPORT_ISBN_ID: Final = "isbn:{isbn}"
IMPORT_SYNTHETIC_ID: Final = "synthetic:{digest}"
IMPORT_EVENT_ID: Final = "{source_id}:finished:{date}"
IMPORT_GOODREADS_URL: Final = "https://www.goodreads.com/book/show/{source_id}"
IMPORT_STORYGRAPH_URL: Final = "https://app.thestorygraph.com/books/{source_id}"
IMPORT_INTEGER_PATTERN: Final = r"[0-9]+"
IMPORT_DECIMAL_PATTERN: Final = r"[0-9]+(?:\.[0-9]+)?"
IMPORT_ISBN_WRAPPER_PATTERN: Final = r'="([^"]*)"'
IMPORT_ISBN_SHAPE_PATTERN: Final = r"(?:[0-9]{9}[0-9Xx]|[0-9]{13})"
IMPORT_UID_PATTERN: Final = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"
IMPORT_LIST_SEPARATOR_PATTERN: Final = r"\s*[,;]\s*"
IMPORT_POSITION_PATTERN: Final = r"(.+?)\s+\(#([0-9]+)\)"
IMPORT_YEAR_TEMPLATE: Final = "{year:04d}"
IMPORT_NUL: Final = "\x00"
IMPORT_QUOTE: Final = '"'
IMPORT_CARRIAGE_RETURN: Final = "\r"
IMPORT_ENCODING_ERROR: Final = "export_encoding_unsupported"
IMPORT_SCHEMA_ERROR: Final = "export_schema_unsupported"
IMPORT_CSV_ERROR: Final = "export_csv_malformed"
IMPORT_SOURCE_ERROR: Final = "export_source_mismatch"
IMPORT_ACCOUNT_ERROR: Final = "export_account_mismatch"
IMPORT_DUPLICATE_ID: Final = "export_duplicate_identity"
IMPORT_UNKNOWN_COLUMN: Final = "export_unmapped_column"
IMPORT_UNKNOWN_STATUS: Final = "export_unknown_status"
IMPORT_SYNTHETIC_NOTICE: Final = "export_synthetic_identity"
IMPORT_HISTORY_INCOMPLETE: Final = "export_history_incomplete"
IMPORT_HISTORY_CONFLICT: Final = "export_history_conflict"
IMPORT_UNKNOWN_NUMBER: Final = "export_unknown_numeric_value"
IMPORT_ENCODING_MESSAGE: Final = "The export must be UTF-8 CSV, optionally with a UTF-8 BOM."
IMPORT_SOURCE_MESSAGE: Final = "The raw document source does not match the configured account."
IMPORT_ACCOUNT_MESSAGE: Final = "The raw document account does not match the configured account."
IMPORT_SCHEMA_MESSAGE: Final = (
    "The export needs nonblank, unique headers, Title, and an Author/Authors or "
    "source identifier column."
)
IMPORT_CSV_MESSAGE: Final = "The export contains malformed CSV quoting or record structure."
IMPORT_WIDTH_MESSAGE: Final = (
    "Export record {row} has {actual} fields; the header defines {expected}. No rows were imported."
)
IMPORT_INVALID_MESSAGE: Final = "Export record {row} has an invalid {field} field."
IMPORT_DUPLICATE_MESSAGE: Final = (
    "Export records {first} and {second} have the same source identity; "
    "separate rows cannot be safely reconciled."
)
IMPORT_UNKNOWN_COLUMN_MESSAGE: Final = (
    "Export column {column} is preserved verbatim in raw_fields but has no typed mapping."
)
IMPORT_UNKNOWN_STATUS_MESSAGE: Final = (
    "Export record {row} has an unrecognized reading status; its original value is preserved."
)
IMPORT_SYNTHETIC_MESSAGE: Final = (
    "Export record {row} lacks a native ID or valid ISBN. Its deterministic source-local "
    "identity is synthetic, not evidence of a cross-source match."
)
IMPORT_HISTORY_INCOMPLETE_MESSAGE: Final = (
    "Export record {row} reports more reads than dated events. Undated reads were not invented."
)
IMPORT_UNKNOWN_NUMBER_MESSAGE: Final = (
    "Export record {row} uses zero for {field}; this is unavailable metadata, not a known value."
)
IMPORT_FILE_COMPLETE_MESSAGE: Final = (
    "The complete offline export was parsed; account identity was not verified."
)
IMPORT_STATUS_TO_READ: Final = "to read"
IMPORT_STATUS_CURRENT: Final = "currently reading"
IMPORT_STATUS_DNF: Final = "did not finish"
IMPORT_STATUS_DNF_APOSTROPHE: Final = "didn't finish"
IMPORT_BOOLEAN_YES: Final = "yes"
IMPORT_BOOLEAN_NO: Final = "no"
IMPORT_BOOLEAN_ONE: Final = "1"
IMPORT_BOOLEAN_ZERO: Final = "0"

TEST_IMPORT_DOCUMENT_ID: Final = "synthetic-raw-document"
TEST_IMPORT_ORIGIN: Final = "synthetic-fixture.csv"
TEST_IMPORT_CAPTURED_AT: Final = "2026-10-30T10:00:00+00:00"
TEST_IMPORT_CSV_MEDIA: Final = "text/csv"
TEST_IMPORT_READER: Final = "export-reader"
TEST_IMPORT_STORYGRAPH_PROFILE: Final = "https://app.thestorygraph.com/profile/export-reader"
TEST_IMPORT_GOODREADS_READER: Final = "123"
TEST_IMPORT_GOODREADS_PROFILE: Final = "https://www.goodreads.com/user/show/123"
TEST_IMPORT_OTHER_READER: Final = "456"
TEST_IMPORT_TITLE: Final = "A Synthetic Book"
TEST_IMPORT_OTHER_TITLE: Final = "A Different Synthetic Book"
TEST_IMPORT_AUTHOR: Final = "Ada Example"
TEST_IMPORT_SECOND_AUTHOR: Final = "Bea Example"
TEST_IMPORT_REVIEW: Final = 'First line, with a comma.\nSecond line has "quotes".'
TEST_IMPORT_UNKNOWN_HEADER: Final = "Future Detail"
TEST_IMPORT_UNKNOWN_VALUE: Final = " original, spelling \nunchanged "
TEST_IMPORT_UNKNOWN_SPELLING: Final = "  FuTuRe Detail  "
TEST_IMPORT_NATIVE_ID: Final = "101"
TEST_IMPORT_SECOND_ID: Final = "102"
TEST_IMPORT_THIRD_ID: Final = "103"
TEST_IMPORT_UID: Final = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TEST_IMPORT_ISBN: Final = "9780140328721"
TEST_IMPORT_ISBN_WRAPPED: Final = '="0140328726"'
TEST_IMPORT_EMPTY_WRAPPER: Final = '=""'
TEST_IMPORT_FORMULA: Final = '=SUM("0140328726")'
TEST_IMPORT_BAD_WRAPPER: Final = '="0140328726"+""'
TEST_IMPORT_INVALID_ISBN: Final = "9780140328720"
TEST_IMPORT_INVALID_ISBN_X: Final = "030640615X"
TEST_IMPORT_OTHER_ISBN: Final = "9780306406157"
TEST_IMPORT_RATING: Final = "4"
TEST_IMPORT_QUARTER_RATING: Final = "4.25"
TEST_IMPORT_COMMUNITY_RATING: Final = "3.75"
TEST_IMPORT_ZERO: Final = "0"
TEST_IMPORT_TWO: Final = "2"
TEST_IMPORT_ONE: Final = "1"
TEST_IMPORT_PAGES: Final = "240"
TEST_IMPORT_YEAR: Final = "2020"
TEST_IMPORT_MONTH: Final = "2024-03"
TEST_IMPORT_DATE: Final = "2025-04-06"
TEST_IMPORT_DATE_SLASH: Final = "2025/04/06"
TEST_IMPORT_DATE_TEXT: Final = "April 6, 2025"
TEST_IMPORT_HISTORY: Final = "2024-03, 2025/04/06"
TEST_IMPORT_RANGE_HISTORY: Final = "2024/01/01-2024/01/31, 2025/04/01-2025/04/06"
TEST_IMPORT_DUPLICATE_HISTORY: Final = "2025-04-06, 2025-04-06"
TEST_IMPORT_INVALID_HISTORY: Final = "2025-02-30, 2025-04-06"
TEST_IMPORT_OVERLAPPING_HISTORY: Final = "2025, 2025-04-06"
TEST_IMPORT_INVALID_DATE: Final = "2025-02-30"
TEST_IMPORT_AMBIGUOUS_DATE: Final = "04/06/2025"
TEST_IMPORT_INVALID_NUMBER: Final = "not-a-number"
TEST_IMPORT_NEGATIVE_NUMBER: Final = "-1"
TEST_IMPORT_NAN: Final = "NaN"
TEST_IMPORT_HIGH_RATING: Final = "6"
TEST_IMPORT_FRACTIONAL_COUNT: Final = "1.5"
TEST_IMPORT_NON_QUARTER_RATING: Final = "4.3"
TEST_IMPORT_UNKNOWN_STATUS: Final = "an unfamiliar source status"
TEST_IMPORT_PUBLISHER: Final = "Example Press"
TEST_IMPORT_PAPERBACK: Final = "Paperback"
TEST_IMPORT_SORT_AUTHOR: Final = "Example, Ada"
TEST_IMPORT_SHELVES: Final = "favorites, owned"
TEST_IMPORT_FAVORITES: Final = "favorites"
TEST_IMPORT_SHELF_POSITIONS: Final = "to-read (#7), favorites (#2)"
TEST_IMPORT_BROKEN_POSITIONS: Final = "to-read (position seven)"
TEST_IMPORT_MOODS: Final = "hopeful, reflective"
TEST_IMPORT_PACE: Final = "medium"
TEST_IMPORT_NOTES: Final = "Synthetic private notes only."
TEST_IMPORT_BLANK_HEADER: Final = "Title,Author,\n"
TEST_IMPORT_DUPLICATE_HEADER: Final = "Title,Author,Title\n"
TEST_IMPORT_CASE_DUPLICATE_HEADER: Final = "Title,Author, title \n"
TEST_IMPORT_NO_SCHEMA: Final = "Name,Writer\n"
TEST_IMPORT_NO_GOODREADS_AUTHOR: Final = "Title,Book Id\nA Synthetic Book,101\n"
TEST_IMPORT_NO_STORYGRAPH_AUTHOR: Final = (
    "Title,ISBN/UID,Read Status\nA Synthetic Book,aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee,read\n"
)
TEST_IMPORT_PARAM_SOURCE_BODY: Final = "source,body"
TEST_IMPORT_EXTRA_FIELD: Final = "Title,Author\nA,Writer,extra\n"
TEST_IMPORT_MISSING_FIELD: Final = "Title,Author\nA\n"
TEST_IMPORT_BLANK_RECORD: Final = "Title,Author\n\n"
TEST_IMPORT_UNTERMINATED_QUOTE: Final = 'Title,Author\n"Unfinished,Writer\n'
TEST_IMPORT_BAD_QUOTE: Final = 'Title,Author\nUn"quoted,Writer\n'
TEST_IMPORT_AFTER_QUOTE: Final = 'Title,Author\n"A"extra,Writer\n'
TEST_IMPORT_INVALID_UTF8: Final = b"\xff\xfeTitle,Author\n"
TEST_IMPORT_NUL_BODY: Final = b"Title,Author\nA\x00,Writer\n"
TEST_IMPORT_PARAM_SOURCE: Final = "source"
TEST_IMPORT_PARAM_BODY_CODE: Final = "body,code"
TEST_IMPORT_PARAM_HEADER_VALUE: Final = "header,value"
TEST_IMPORT_PARAM_RATING_STATE_VALUE: Final = "source,rating,state,expected"

RAW_OPEN_ERROR: Final = "The raw archive could not be opened safely."
RAW_UNSUPPORTED_ERROR: Final = "The database is not a supported BookyStats raw archive."
RAW_CORRUPT_ERROR: Final = "The raw archive contains a damaged capture or payload."
RAW_READ_ERROR: Final = "The raw archive could not be read safely."
RAW_WRITE_ERROR: Final = "The raw capture could not be stored safely."
RAW_CLOSE_ERROR: Final = "The raw archive could not be closed safely."
RAW_CLOSED_ERROR: Final = "The raw archive is closed."
RAW_MISSING_ERROR: Final = "The requested raw capture does not exist."
RAW_INVALID_ERROR: Final = "Raw captures require a source, account, bytes, and provenance."
RAW_FILE_ERROR: Final = "The export file could not be read for raw capture."
RAW_PROVIDER_ERROR: Final = "Only public catalog metadata fetches may use the recording adapter."
RAW_PROVENANCE_ERROR: Final = "The metadata response has invalid URL provenance."
RAW_CREDENTIAL_ERROR: Final = (
    "Raw capture refused: the metadata response echoes a supplied credential."
)
RAW_CATALOG_ACCOUNT: Final = "raw:public-catalog-metadata"
RAW_CSV_MEDIA_TYPE: Final = "text/csv"
RAW_BINARY_MEDIA_TYPE: Final = "application/octet-stream"
RAW_CSV_SUFFIX: Final = ".csv"
RAW_AT: Final = "@"
RAW_SEMICOLON: Final = ";"
RAW_EQUALS: Final = "="
RAW_QUOTES: Final = "\"'"
RAW_BASIC: Final = "basic"
RAW_COOKIE: Final = "cookie"
RAW_AUTHORIZATION: Final = "authorization"
RAW_SECRET_NAME_PATTERN: Final = "[^a-z0-9]"
RAW_SECRET_KEY: Final = "key"
RAW_SECRET_TOKEN: Final = "token"
RAW_SECRET_SECRET: Final = "secret"
RAW_SECRET_PASSWORD: Final = "password"
RAW_SECRET_PASSWD: Final = "passwd"
RAW_SECRET_AUTH: Final = "auth"
RAW_SECRET_AUTHENTICATION: Final = "authentication"
RAW_SECRET_CREDENTIAL: Final = "credential"
RAW_SECRET_CREDENTIALS: Final = "credentials"
RAW_SECRET_USERNAME: Final = "username"
RAW_UTF_16_LE: Final = "utf-16-le"
RAW_UTF_16_BE: Final = "utf-16-be"
RAW_PRAGMA_APPLICATION: Final = "PRAGMA application_id"
RAW_PRAGMA_VERSION: Final = "PRAGMA user_version"
RAW_PRAGMA_APPLICATION_SET: Final = "PRAGMA application_id = {value}"
RAW_PRAGMA_VERSION_SET: Final = "PRAGMA user_version = {value}"
RAW_PRAGMA_FOREIGN_KEYS: Final = "PRAGMA foreign_keys = ON"
RAW_PRAGMA_SYNCHRONOUS: Final = "PRAGMA synchronous = FULL"
RAW_PRAGMA_INTEGRITY: Final = "PRAGMA quick_check"
RAW_PRAGMA_FOREIGN_CHECK: Final = "PRAGMA foreign_key_check"
RAW_BEGIN: Final = "BEGIN IMMEDIATE"
RAW_SCHEMA_OBJECTS: Final = (
    "SELECT type, name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
)
RAW_TABLE_TYPE: Final = "table"
RAW_INDEX_TYPE: Final = "index"
RAW_PAYLOAD_TABLE: Final = "raw_payloads"
RAW_CAPTURE_TABLE: Final = "raw_captures"
RAW_CAPTURE_INDEX: Final = "raw_capture_account"
RAW_PAYLOAD_SCHEMA: Final = (
    "CREATE TABLE raw_payloads (sha256 TEXT PRIMARY KEY NOT NULL, body BLOB NOT NULL)"
)
RAW_CAPTURE_SCHEMA: Final = (
    "CREATE TABLE raw_captures (sequence INTEGER PRIMARY KEY, "
    "id TEXT NOT NULL UNIQUE, source TEXT NOT NULL, account_id TEXT NOT NULL, "
    "media_type TEXT NOT NULL, origin TEXT NOT NULL, captured_at TEXT NOT NULL, "
    "sha256 TEXT NOT NULL REFERENCES raw_payloads(sha256), checksum TEXT NOT NULL, "
    "collection TEXT NOT NULL)"
)
RAW_INDEX_SCHEMA: Final = (
    "CREATE INDEX raw_capture_account ON raw_captures(source, account_id, sequence DESC)"
)
RAW_INSERT_PAYLOAD: Final = (
    "INSERT INTO raw_payloads(sha256, body) VALUES (?, ?) ON CONFLICT(sha256) DO NOTHING"
)
RAW_SELECT_PAYLOAD: Final = "SELECT body FROM raw_payloads WHERE sha256 = ?"
RAW_INSERT_CAPTURE: Final = (
    "INSERT INTO raw_captures(sequence, id, source, account_id, media_type, origin, captured_at, "
    "sha256, collection, checksum) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
RAW_SELECT_CAPTURE: Final = (
    "SELECT c.sequence, c.id, c.source, c.account_id, p.body, c.media_type, c.origin, "
    "c.captured_at, c.sha256, c.checksum, c.collection FROM raw_captures c "
    "LEFT JOIN raw_payloads p ON p.sha256 = c.sha256 "
)
RAW_GET_CAPTURE: Final = RAW_SELECT_CAPTURE + "WHERE c.id = ?"
RAW_LATEST_CAPTURE: Final = (
    RAW_SELECT_CAPTURE + "WHERE c.source = ? AND c.account_id = ? AND c.collection = ? "
    "ORDER BY c.sequence DESC LIMIT 1"
)
RAW_CHECK_SCHEMA: Final = RAW_SELECT_CAPTURE + "LIMIT 0"
RAW_HASH_PATTERN: Final = "[0-9a-f]{64}"

TEST_RAW_FILENAME: Final = "raw.sqlite3"
TEST_RAW_FILE: Final = "export.csv"
TEST_RAW_PRIVATE_FOLDER: Final = "private-folder"
TEST_RAW_ACCOUNT: Final = "raw-test-reader"
TEST_RAW_OTHER_ACCOUNT: Final = "raw-other-reader"
TEST_RAW_PROFILE: Final = "https://app.thestorygraph.com/profile/raw-test-reader"
TEST_RAW_MALFORMED: Final = b'Title,Author\r\n"unfinished,\xff\x00\x80\r\n'
TEST_RAW_NEXT_BODY: Final = b"Title,Author\r\nAnother,Someone\r\n"
TEST_RAW_BOM_BODY: Final = b"\xef\xbb\xbfTitle,Author\r\nExact,Bytes\r\n"
TEST_RAW_UNKNOWN_BODY: Final = b"\x00\xff\xfe\x80\x81\r\n"
TEST_RAW_MISSING: Final = "missing-capture"
TEST_RAW_OTHER_ORIGIN: Final = "another.csv"
TEST_RAW_CLOCK: Final = "bookystats.persistence.raw.utc_now"
TEST_RAW_FIRST_TIME: Final = "2026-10-30T10:00:00+00:00"
TEST_RAW_SECOND_TIME: Final = "2026-10-30T10:01:00+00:00"
TEST_RAW_PARAM_BODY: Final = "body"
TEST_RAW_PARAM_SOURCE: Final = "source"
TEST_RAW_PARAM_SQL: Final = "sql"
TEST_RAW_PARAM_ECHO: Final = "echo"
TEST_RAW_PAYLOAD_COUNTS: Final = "SELECT COUNT(*) FROM raw_payloads"
TEST_RAW_CAPTURE_COUNTS: Final = "SELECT COUNT(*) FROM raw_captures"
TEST_RAW_TAMPER_BODY: Final = "UPDATE raw_payloads SET body = X'626164'"
TEST_RAW_TAMPER_ACCOUNT: Final = "UPDATE raw_captures SET account_id = 'other'"
TEST_RAW_TAMPER_SOURCE: Final = "UPDATE raw_captures SET source = 'goodreads'"
TEST_RAW_TAMPER_TIME: Final = "UPDATE raw_captures SET captured_at = '2026-10-31T10:00:00+00:00'"
TEST_RAW_TAMPER_CHECKSUM: Final = "UPDATE raw_captures SET checksum = 'not-a-checksum'"
TEST_RAW_REMOVE_PAYLOAD: Final = "DELETE FROM raw_payloads"
TEST_RAW_FOREIGN_SCHEMA: Final = "CREATE TABLE unrelated (id INTEGER)"
TEST_RAW_NEW_VERSION: Final = "PRAGMA user_version = 999"
TEST_RAW_FOREIGN_APPLICATION: Final = "PRAGMA application_id = 999"
TEST_RAW_CORRUPT_FILE: Final = b"not a database; never echo private contents"
TEST_RAW_PROVIDER_URL: Final = "https://www.googleapis.com/books/v1/volumes"
TEST_RAW_PROVIDER_PRIVATE_URL: Final = (
    "https://fixture-user:fixture-password@www.googleapis.com/books/v1/volumes"
    "?key=fixture-url-key#fixture-fragment"
)
TEST_RAW_METADATA_BODY: Final = (
    b'{"items":[{"id":"fixture-volume","unknown":{"raw":[1,null,{"extra":true}]}}]}'
)
TEST_RAW_METADATA_INVALID: Final = b'{"error":"not finished"\xff\x00'
TEST_RAW_MEDIA_TYPE: Final = "application/json"
TEST_RAW_RESPONSE_COOKIE: Final = "fixture-response-cookie"
TEST_RAW_REQUEST_KEY: Final = "fixture-parameter-key"
TEST_RAW_AUTH: Final = "Bearer fixture-header-token"
TEST_RAW_AUTH_TOKEN: Final = "fixture-header-token"
TEST_RAW_REQUEST_COOKIE: Final = "session=fixture-cookie-token; other=fixture-cookie-two"
TEST_RAW_COOKIE_TOKEN: Final = "fixture-cookie-token"
TEST_RAW_COOKIE_TWO: Final = "fixture-cookie-two"
TEST_RAW_URL_KEY: Final = "fixture-url-key"
TEST_RAW_URL_USER: Final = "fixture-user"
TEST_RAW_URL_PASSWORD: Final = "fixture-password"
TEST_RAW_FRAGMENT: Final = "fixture-fragment"
TEST_RAW_QUERY: Final = "isbn:9780140328721"
TEST_RAW_ECHO_TEMPLATE: Final = '{{"error":"request contained {value}"}}'
TEST_RAW_TRANSPORT_ERROR: Final = "Fixture transport failed."
TEST_RAW_INSERT_ABORT: Final = (
    "CREATE TRIGGER fail_capture BEFORE INSERT ON raw_captures "
    "BEGIN SELECT RAISE(ABORT, 'fixture failure'); END"
)
RAW_QUERY_START_INDEX: Final = "startIndex"
RAW_QUERY_MAX_RESULTS: Final = "maxResults"
RAW_QUERY_BIBKEYS: Final = "bibkeys"
RAW_QUERY_FORMAT: Final = "format"
RAW_QUERY_JSCMD: Final = "jscmd"
RAW_QUERY_OFFSET: Final = "offset"
TEST_RAW_PARAM_STATUS: Final = "status"
TEST_RAW_UNKNOWN_QUERY: Final = "unknown-request-value"
TEST_RAW_OPEN_LIBRARY_URL: Final = "https://openlibrary.org/api/books"
TEST_RAW_BIBKEYS: Final = "ISBN:9780140328721"
TEST_RAW_DATA: Final = "data"
TEST_RAW_SEARCH_URL: Final = "https://openlibrary.org/search.json"
RAW_NEXT_SEQUENCE: Final = "SELECT COALESCE(MAX(sequence), 0) + 1 FROM raw_captures"
TEST_RAW_TAMPER_SEQUENCE: Final = "UPDATE raw_captures SET sequence = sequence + 100"

# Run verification: the checks printed after every manual sync.
SUCCESS: Final = "success"
VERIFICATION: Final = "verification"
LOG_FILE: Final = "log_file"
VERIFY_NAME_RAW_COPY: Final = "raw_copy"
VERIFY_NAME_PROCESSING: Final = "processing"
VERIFY_NAME_ROW_COUNTS: Final = "row_counts"
VERIFY_MARKER_OK: Final = "[ok]"
VERIFY_MARKER_PARTIAL: Final = "[partial]"
VERIFY_MARKER_FAILED: Final = "[FAILED]"
VERIFY_EXPLANATION_SUCCESS: Final = "Everything in the files was saved and checked."
VERIFY_EXPLANATION_PARTIAL: Final = (
    "Nothing failed, but not everything is finished. See the checks above."
)
VERIFY_EXPLANATION_FAILED: Final = "Something did not work. See the checks above and the run log."
VERIFY_NOT_CONFIGURED: Final = (
    "No reader account is configured for this source, so nothing was checked."
)
VERIFY_MISSING_EXPORT: Final = "No export has been added yet. Add one with {flag}."
VERIFY_RAW_COPY_NEW: Final = (
    "{origin} was saved unchanged and matches the file you gave "
    "(fingerprint {digest}, {size} bytes)."
)
VERIFY_RAW_COPY_REPLAY: Final = (
    "Reused the saved copy of {origin} from {captured} (fingerprint {digest}, {size} bytes)."
)
VERIFY_RAW_COPY_UNREADABLE: Final = "The saved copy could not be read back intact."
VERIFY_RAW_COPY_DIFFERS: Final = "The saved copy is not identical to the export that was processed."
VERIFY_RAW_COPY_FILE_CHANGED: Final = "The saved copy does not match the file on disk."
VERIFY_RAW_COPY_FILE_UNREADABLE: Final = (
    "The original file could not be read again to compare it with the saved copy."
)
VERIFY_ISSUE: Final = "{code}: {message}"
VERIFY_PROCESSING_FAILED: Final = "The source input could not be processed. {reason}"
VERIFY_PROCESSING_NO_ISSUE: Final = "The source finished as {state} without a reported reason."
VERIFY_ROWS_MATCH: Final = (
    "{rows} rows in the file = {records} books processed = {library} books in the library."
)
VERIFY_ROWS_DIFFER: Final = (
    "The file has {rows} rows, but {records} books were processed and {library} are in the library."
)
VERIFY_ROWS_UNCOUNTABLE: Final = "The saved copy could not be counted: {message}"
VERIFY_METADATA_OK: Final = "{processed} lookups completed."
VERIFY_METADATA_PARTIAL: Final = "{state}: {reason}"
VERIFY_METADATA_NO_ISSUE: Final = "{processed} lookups completed, {deferred} deferred."

# Console and run-log report lines.
REPORT_RUN_HEADING: Final = "Sync {run_id}: {state}"
REPORT_SOURCE_LINE: Final = "  {source}/{collection}: {state}; {records} records, {pages} pages"
REPORT_PUBLICATION_LINE: Final = (
    "    {added} added, {updated} updated, {unchanged} unchanged, "
    "{removed} removed from current collection"
)
REPORT_ISSUE_LINE: Final = "    {code}: {message}"
REPORT_REPEATED_ISSUE_LINE: Final = "    {code}: {message} ({count} occurrences)"
REPORT_MORE_ISSUES_LINE: Final = "    {count} additional issues (grouped in the run log)."
REPORT_METADATA_LINE: Final = (
    "  {provider}: {state}; {processed} lookups completed, {deferred} deferred"
)
REPORT_METADATA_CORE_SCOPE: Final = (
    "    Core-gap fallback: {skipped} source records skipped by strategy; "
    "{unresolved} still lack core coverage. This is not full provider coverage."
)
REPORT_CHECKS_HEADING: Final = "Checks"
REPORT_CHECK_LINE: Final = "  {marker:<9} {source} {name}: {detail}"
REPORT_RESULT_LINE: Final = "Result: {result}"
REPORT_RUN_LOG_LINE: Final = "Run log: {path}"

# Readable status report.
LATEST_LOG: Final = "latest_log"
LIBRARY_DATABASE: Final = "library_database"
RAW_ARCHIVE_BYTES: Final = "raw_archive_bytes"
LIBRARY_BYTES: Final = "library_bytes"
STATUS_DATA_FOLDER_LINE: Final = "Data folder: {path}"
STATUS_RAW_ARCHIVE_LINE: Final = "Raw archive: {location}"
STATUS_LIBRARY_DATABASE_LINE: Final = "Library database: {location}"
STATUS_LATEST_LOG_LINE: Final = "Latest log: {location}"
STATUS_LAST_RUN_LINE: Final = "Last run: {value}"
STATUS_LAST_RUN_VALUE: Final = "#{run_id} {state}"
STATUS_LOCATION_WITH_SIZE: Final = "{path} ({size})"
STATUS_SIZE: Final = "{megabytes:.1f} MB"
STATUS_NOT_CREATED: Final = "not created yet"
STATUS_NONE_YET: Final = "none yet"
STATUS_NONE_LINE: Final = "  none yet"
STATUS_SOURCES_HEADING: Final = "COLLECTIONS"
STATUS_SOURCE_LINE: Final = "  {source:<12} {collection:<10} {state:<14} {count:>11,}"
STATUS_NEVER: Final = "never"
STATUS_UNKNOWN: Final = "unknown"
STATUS_LIBRARY_COUNTS_LINE: Final = (
    "Saved library: {entries:,} entries | {works:,} works | {events:,} dated reading events"
)
STATUS_METADATA_HEADING: Final = "METADATA"
STATUS_METADATA_LINE: Final = "  {provider:<14} {matched:>8,} {unmatched:>10,}  {success}"
STATUS_SCHEDULE_LINE: Final = "Weekly schedule: {state}"
STATUS_GOOGLE_KEY_LINE: Final = "Google Books access: {state}"
STATUS_KEY_SET: Final = "API key configured"
STATUS_KEY_NOT_SET: Final = "not configured"

# Clear invocation, live progress and orderly source teardown.
CLI_COMPACT_USAGE: Final = "%(prog)s {fetch,sync,status} [options]"
CLI_OPTIONAL_COMMAND: Final = "?"
CLI_QUICK_HELP: Final = (
    "BookyStats\n\n"
    "  booky fetch    Write the Goodreads browser-console helper\n"
    "  booky sync     Process configured CSV files\n"
    "  booky status   Show saved local results\n\n"
    "Run booky --help for advanced options."
)
CLI_METADATA_PROGRESS: Final = (
    "  {source}: checking stored-library metadata {completed:,}/{total:,} "
    "(network timeout {timeout:g}s)."
)
STATUS_SOURCE_HEADER: Final = "  Source       Shelf      Last attempt    Saved books"
STATUS_METADATA_HEADER: Final = "  Provider        Matched  Unresolved  Last success"
STATUS_RETAINED_SNAPSHOTS: Final = (
    "  Action needed: one or more fetches did not complete.\n"
    "  Saved books are retained complete snapshots, not proof this attempt fetched fresh data."
)
GOOGLE_BOOKS_OAUTH_SAVED: Final = "google_books_oauth_saved"
STATUS_OAUTH_SAVED: Final = "OAuth file saved (not checked by status)"

# Run logs written to <data folder>\logs.
LOGS_FOLDER: Final = "logs"
EXCLUSIVE_CREATE_MODE: Final = "x"
RUNLOG_PATTERN: Final = "*.log"
RUNLOG_NAME_PATTERN: Final = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z_(?:run\d+|failed)(?:_\d+)?\.log"
TEST_REPORTING_UNMANAGED_LOG: Final = "notes.log"
RUNLOG_STAMP_FORMAT: Final = "%Y-%m-%d_%H-%M-%SZ"
RUNLOG_FILE_NAME: Final = "{stamp}_run{run_id}.log"
RUNLOG_FAILED_FILE_NAME: Final = "{stamp}_failed.log"
RUNLOG_FAILURE_TYPE: Final = "{type} (details withheld because they can contain private data)"

# Default data folder inside a source checkout (tracked in git).
CHECKOUT_DATA_FOLDER: Final = "data"
PYPROJECT_FILE: Final = "pyproject.toml"
TEST_ISOLATED_DATA_FOLDER: Final = "isolated-data"
TEST_RAW_BASIC_HEADER: Final = "Basic {value}"
TEST_RAW_BASIC_TEMPLATE: Final = "{username}:{password}"
TEST_RAW_SPECIAL_SECRET: Final = "fixture-parameter-with&punctuation"
TEST_RAW_ESCAPE_CASES: Final = "body,secret"
TEST_RAW_UTF16_ECHO: Final = TEST_RAW_REQUEST_KEY.encode(RAW_UTF_16_LE)
TEST_RAW_JSON_ECHO: Final = b'"fixture-parameter-with\\u0026punctuation"'
TEST_RAW_HTML_ECHO: Final = b"fixture-parameter-with&amp;punctuation"
TEST_RAW_URL_ECHO: Final = b"fixture-parameter-with%26punctuation"
RAW_UNICODE_ESCAPE_PATTERN: Final = rb"\\u([0-9a-fA-F]{4})"
RAW_SURROGATEPASS: Final = "surrogatepass"
TEST_RAW_FETCH_METHOD: Final = "fetch"

# Explicit browser-export shelf intake.
CLI_GOODREADS_WATCHLIST_FILE: Final = "--goodreads-watchlist-file"
CLI_GOODREADS_READ_FILE: Final = "--goodreads-read-file"
CLI_SHELF_FILE_HELP: Final = "Archive a Goodreads browser-export CSV for this shelf."
CLI_GOODREADS_SCOPE_CONFLICT: Final = (
    "Use either --goodreads-file for a whole library or the explicit watchlist/read flags, "
    "not both. Archived whole-library and shelf inputs must use separate data directories."
)
IMPORT_BROWSER_URL: Final = "Goodreads_URL"
IMPORT_BROWSER_DETAILS: Final = "Row_Details"
IMPORT_BROWSER_PUBLICATION: Final = "Publication_Date"
IMPORT_BROWSER_AVERAGE: Final = "Average_Rating"
IMPORT_BROWSER_RATINGS: Final = "Ratings_Count"
IMPORT_BROWSER_REVIEWS: Final = "Reviews_Count"
IMPORT_BROWSER_COVER: Final = "Cover_URL"
IMPORT_BROWSER_SERIES_NUMBER: Final = "Series_Number"
SERIES: Final = "series"
IMPORT_BROWSER_URL_PATTERN: Final = r"/book/show/([0-9]+)(?:[.-][^/?#]*)?/?"
IMPORT_BROWSER_SCOPE_ERROR: Final = (
    "Browser-export CSVs require --goodreads-watchlist-file or --goodreads-read-file; "
    "the CSV itself does not identify its shelf."
)
IMPORT_BROWSER_UNMAPPED: Final = "browser_field_unmapped"
IMPORT_BROWSER_UNMAPPED_MESSAGE: Final = (
    "Export record {row}: {field} could not be mapped safely; its original text is retained."
)
IMPORT_STORYGRAPH_INVALID_IDENTIFIER: Final = (
    "Export record {row} has an invalid ISBN/UID. It is retained raw-only; the rating uses "
    "source-local identity and is not matched through this identifier."
)
IMPORT_BROWSER_PAGES: Final = "Pages"
IMPORT_BROWSER_EDITION_PUBLISHED_PATTERN: Final = (
    r"(?<!First )Published (?P<value>[A-Za-z]+ [0-9]{1,2}, [0-9]{4}|[A-Za-z]+ [0-9]{4}|[0-9]{4})"
    r"(?: Book details|$)"
)
TEST_BROWSER_EXPORT_SORT_AUTHOR: Final = "Example, Ada"
IMPORT_BROWSER_SCOPE_NOTICE: Final = "browser_capture_scope"
IMPORT_BROWSER_SCOPE_MESSAGE: Final = (
    "User-supplied browser capture: shelf membership is explicitly supplied, not independently "
    "verified. Fixed-page collection and best-effort enrichment do not prove account completeness. "
    "Row_Details has flattened review/date text; personal reviews and reading-event dates "
    "are not inferred from it."
)
IMPORT_STORYGRAPH_SCOPE_NOTICE: Final = "storygraph_ratings_only"
IMPORT_STORYGRAPH_SCOPE_MESSAGE: Final = (
    "Only explicitly Read StoryGraph rows supply personal ratings and matching identity. "
    "Read status selects the import scope but is not published as reading history. "
    "Explicit Last Date Read supplies separately attributed supplemental completion dates "
    "through confirmed work links, never replacing Goodreads history. All other source "
    "fields, including reviews and other reading dates, remain raw-only."
)
STORYGRAPH_READ_SCOPE_INVALID_CODE: Final = "storygraph_read_scope_unknown"
STORYGRAPH_READ_SCOPE_INVALID_MESSAGE: Final = (
    "StoryGraph row {row} has an empty or unknown Read Status; the prior Read-only "
    "snapshot is retained rather than guessing which records belong in scope."
)
STORYGRAPH_READ_SCOPE_EXCLUDED_CODE: Final = "storygraph_non_read_excluded"
STORYGRAPH_READ_SCOPE_EXCLUDED_MESSAGE: Final = (
    "{count} non-Read StoryGraph rows remain in the raw archive and are excluded "
    "from processed ratings, matching and enrichment."
)
STORYGRAPH_READ_SCOPE_VERIFY_MATCH: Final = (
    "{total} archived CSV rows: {rows} explicit Read rows = {records} books processed "
    "= {library} books in the library; {excluded} non-Read rows excluded."
)
STORYGRAPH_READ_SCOPE_VERIFY_DIFFER: Final = (
    "{total} archived CSV rows contain {rows} explicit Read rows, but {records} books "
    "were processed and {library} are in the library; {excluded} non-Read rows excluded."
)
STORYGRAPH_READ_SCOPE_TEST_MISSING_CSV: Final = "Title,Authors\nA Synthetic Book,Ada Example\n"
IMPORT_BROWSER_ISBN_PATTERN: Final = r" isbn (?P<value>\S+) isbn13 "
IMPORT_BROWSER_ISBN13_PATTERN: Final = r" isbn13 (?P<value>\S+) asin "
IMPORT_BROWSER_PAGES_PATTERN: Final = r" num pages (?P<value>[0-9]+) pp avg rating "
IMPORT_BROWSER_RATING_PATTERN: Final = r" avg rating (?P<value>[0-5](?:\.[0-9]+)?) num ratings "
IMPORT_BROWSER_RATINGS_PATTERN: Final = r" num ratings (?P<value>[0-9]+(?:,[0-9]{3})*) date pub "
IMPORT_BROWSER_ADDED_PATTERN: Final = (
    r" date added (?P<value>[A-Za-z]+ [0-9]{1,2}, [0-9]{4}) owned "
)
IMPORT_BROWSER_FORMAT_PATTERN: Final = r" owned format (?P<value>.+?) actions view(?: |$)"
IMPORT_BROWSER_POSITION_PATTERN: Final = r"^checkbox position (?P<value>[0-9]+) cover title "
IMPORT_BROWSER_FIRST_PUBLISHED_PATTERN: Final = (
    r"First published (?P<value>[A-Za-z]+ [0-9]{1,2}, [0-9]{4}|[A-Za-z]+ [0-9]{4}|[0-9]{4})"
    r"(?: Book details|$)"
)
IMPORT_BROWSER_PAGE_DETAILS_PATTERN: Final = r"^(?P<value>[0-9]+) pages,"
IMPORT_BROWSER_GENRE_SEPARATOR: Final = "|"
IMPORT_BROWSER_FIRST_PUBLICATION: Final = "first_publication_date"
RAW_MIGRATE_COLLECTION: Final = (
    "ALTER TABLE raw_captures ADD COLUMN collection TEXT NOT NULL DEFAULT 'library'"
)
RAW_LEGACY_SELECT: Final = (
    "SELECT c.sequence, c.id, c.source, c.account_id, p.body, c.media_type, c.origin, "
    "c.captured_at, c.sha256, c.checksum FROM raw_captures c "
    "LEFT JOIN raw_payloads p ON p.sha256 = c.sha256"
)
RAW_MIGRATE_CHECKSUM: Final = "UPDATE raw_captures SET checksum = ? WHERE id = ?"
TEST_BROWSER_EXPORT_URL: Final = "https://www.goodreads.com/book/show/101-a-synthetic-book"
TEST_BROWSER_EXPORT_DETAILS: Final = (
    "checkbox position 7 cover title A Synthetic Book author Example, Ada "
    "isbn 0140328726 isbn13 9780140328721 asin 0140328726 num pages 240 pp "
    "avg rating 3.75 num ratings 12,345 date pub April 6, 2025 "
    "date pub edition April 6, 2025 my rating 1 of 5 stars2 of 5 stars3 of 5 stars"
    "4 of 5 stars5 of 5 stars review None notes Notes are private! comments 0 "
    "votes 0 # times read 1 date started not set date read not set "
    "date added Mar 03, 2024 owned format Paperback actions view"
)
TEST_BROWSER_EXPORT_PUBLICATION: Final = (
    "240 pages, PaperbackFirst published April 6, 2025 Book details & editions"
)
TEST_BROWSER_EXPORT_GENRES: Final = "Fiction | Fantasy | Fiction"
TEST_BROWSER_EXPORT_BAD_URL: Final = "https://example.invalid/book/show/101"
TEST_BROWSER_EXPORT_BAD_PAGES: Final = "unavailable pages"
TEST_BROWSER_EXPORT_READ_NAME: Final = "read.csv"
TEST_BROWSER_EXPORT_WATCH_NAME: Final = "watchlist.csv"
TEST_BROWSER_EXPORT_DESCRIPTION: Final = "A synthetic catalog description."
TEST_RAW_LEGACY_SCHEMA: Final = (
    "CREATE TABLE raw_payloads (sha256 TEXT PRIMARY KEY NOT NULL, body BLOB NOT NULL);"
    "CREATE TABLE raw_captures (sequence INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, "
    "source TEXT NOT NULL, account_id TEXT NOT NULL, media_type TEXT NOT NULL, "
    "origin TEXT NOT NULL, captured_at TEXT NOT NULL, sha256 TEXT NOT NULL "
    "REFERENCES raw_payloads(sha256), checksum TEXT NOT NULL);"
    "CREATE INDEX raw_capture_account ON raw_captures(source, account_id, sequence DESC);"
    "PRAGMA user_version = 1;"
)
TEST_RAW_LEGACY_INSERT: Final = (
    "INSERT INTO raw_captures(sequence,id,source,account_id,media_type,origin,captured_at,"
    "sha256,checksum) VALUES (?,?,?,?,?,?,?,?,?)"
)
TEST_RAW_TAMPER_COLLECTION: Final = "UPDATE raw_captures SET collection = 'read'"
TEST_BROWSER_EXPORT_BAD_DETAILS: Final = "unstructured source text"
TEST_BROWSER_EXPORT_FALSE_SERIES: Final = "52"
TEST_BROWSER_EXPORT_GENRES_EXPECTED: Final = "Fiction"
TEST_BROWSER_EXPORT_FANTASY: Final = "Fantasy"
TEST_BROWSER_EXPORT_DATE_ADDED: Final = "2024-03-03"

# Structured Goodreads browser export.
CLI_GOODREADS_EXPORT_SCRIPT: Final = "--goodreads-export-script"
GOODREADS_EXPORT_VERSION: Final = "booky-goodreads-shelf-v1"
GOODREADS_EXPORT_VERSION_HEADER: Final = "Export_Version"
GOODREADS_EXPORT_REVIEW: Final = "Review_Text"
GOODREADS_EXPORT_REVIEW_STATE: Final = "Review_State"
GOODREADS_EXPORT_READ: Final = "Date_Read"
GOODREADS_EXPORT_READ_STATE: Final = "Date_Read_State"
GOODREADS_EXPORT_STARTED: Final = "Date_Started"
GOODREADS_EXPORT_STARTED_STATE: Final = "Date_Started_State"
GOODREADS_EXPORT_SOURCE_URL: Final = "Source_URL"
GOODREADS_EXPORT_CAPTURED_AT: Final = "Captured_At"
GOODREADS_EXPORT_COLLECTION: Final = "Collection"
GOODREADS_EXPORT_COLLECTION_STATE: Final = "Collection_State"
GOODREADS_EXPORT_DATE_READ_FIELD: Final = "date_read"
GOODREADS_EXPORT_DATE_STARTED_FIELD: Final = "date_started"
GOODREADS_EXPORT_SOURCE_PATTERN: Final = r"/review/list/([1-9]\d*)(?:-[^/]*)?"
GOODREADS_EXPORT_QUERY_SORT: Final = "sort"
GOODREADS_EXPORT_QUERY_ORDER: Final = "order"
GOODREADS_EXPORT_QUERY_VIEW: Final = "view"
TEST_GOODREADS_EXPORT_SOURCE_URL: Final = (
    "https://www.goodreads.com/review/list/123?shelf=read&per_page=100&page=1"
)
TEST_GOODREADS_EXPORT_OTHER_URL: Final = "https://www.goodreads.com/review/list/456?shelf=read"
TEST_GOODREADS_EXPORT_BAD_DATE: Final = "2025-02-30"
TEST_GOODREADS_EXPORT_BAD_STATE: Final = "maybe"
TEST_GOODREADS_EXPORT_PARAMETER_FIELD_VALUE: Final = "header,value"
TEST_GOODREADS_EXPORT_PARAMETER_STATE: Final = "state"
TEST_GOODREADS_EXPORT_INCOMPLETE: Final = "incomplete"

# Reporting and logging regressions.
VERIFY_RAW_COPY_LINEAGE_DIFFERS: Final = (
    "The saved copy does not match the source, account, collection, or raw lineage of this run."
)
RUNLOG_COLLISION_NAME: Final = "{stem}_{sequence:06d}{suffix}"
TEST_REPORTING_SOURCE_FIELDS: Final = "state,publication,expected"
TEST_REPORTING_METADATA_FIELDS: Final = "state,issues,expected"
TEST_REPORTING_RAW_FIELDS: Final = "statement"
TEST_REPORTING_COUNT_FIELDS: Final = "count"
TEST_REPORTING_LINEAGE_FIELDS: Final = "field,value"
TEST_REPORTING_RESULT_FIELDS: Final = "result"
TEST_REPORTING_LIMIT_FIELDS: Final = "limit,shown"
TEST_REPORTING_CHECKOUT_ROOT: Final = "_checkout_root"
TEST_REPORTING_USER_DATA_PATH: Final = "user_data_path"
TEST_REPORTING_FILE_ATTRIBUTE: Final = "__file__"
TEST_REPORTING_FIXTURE_CSV: Final = (
    b"Book Id,Title,Author\n42,Synthetic reporting book,Synthetic author\n"
)
TEST_REPORTING_EMPTY_CSV: Final = b"Book Id,Title,Author\n"
TEST_REPORTING_INVALID_CSV: Final = b"\xff"
TEST_REPORTING_CHANGED_CSV: Final = b"changed after capture"
TEST_REPORTING_ACCOUNT: Final = "reporting-reader"
TEST_REPORTING_OTHER_ACCOUNT: Final = "different-reader"
TEST_REPORTING_OTHER_RAW_ID: Final = "different-raw-document"
TEST_REPORTING_RAW_DATABASE: Final = "reporting-raw.sqlite3"
TEST_REPORTING_PRIVATE_DIRECTORY: Final = "private-exports"
TEST_REPORTING_FILE: Final = "reporting-export.csv"
TEST_REPORTING_PRIVATE_PATH: Final = r"C:\Users\private-reader\exports\reporting-export.csv"
TEST_REPORTING_FIRST_TIME: Final = "2026-11-02T08:00:00+00:00"
TEST_REPORTING_SECOND_TIME: Final = "2026-11-02T08:00:01+00:00"
TEST_REPORTING_OFFSET_TIME: Final = "2026-11-02T13:30:00+05:30"
TEST_REPORTING_ISSUE_ONE: Final = "synthetic_first"
TEST_REPORTING_ISSUE_TWO: Final = "synthetic_second"
TEST_REPORTING_ISSUE_THREE: Final = "synthetic_third"
TEST_REPORTING_MESSAGE_ONE: Final = "First synthetic issue."
TEST_REPORTING_MESSAGE_TWO: Final = "Second synthetic issue."
TEST_REPORTING_MESSAGE_THREE: Final = "Third synthetic issue."
TEST_REPORTING_SECRET: Final = "synthetic-reporting-secret"
TEST_REPORTING_KEY_SECRET: Final = "synthetic-key-secret"
TEST_REPORTING_BEARER_SECRET: Final = "synthetic-bearer-secret"
TEST_REPORTING_SECRET_MESSAGE: Final = (
    "Synthetic failure: synthetic-reporting-secret "
    "https://example.invalid/?key=synthetic-key-secret Bearer synthetic-bearer-secret"
)
TEST_REPORTING_FAILURE: Final = "Synthetic pre-run failure."
TEST_REPORTING_OLDER_LOG: Final = "2099-01-01_00-00-00Z_run9.log"
TEST_REPORTING_NEWER_LOG: Final = "2000-01-01_00-00-00Z_failed.log"
TEST_REPORTING_NOT_LOG: Final = "notes.txt"
TEST_REPORTING_DIRECTORY_LOG: Final = "2999-01-01_00-00-00Z_run1.log"
TEST_REPORTING_CHECKOUT: Final = "synthetic-checkout"
TEST_REPORTING_ENV_DIRECTORY: Final = "environment-data"
TEST_REPORTING_OVERRIDE_DIRECTORY: Final = "explicit-data"
TEST_REPORTING_PLATFORM_DIRECTORY: Final = "platform-data"
TEST_REPORTING_INSTALLED_DIRECTORY: Final = "site-packages"
TEST_REPORTING_MODULE_FILE: Final = "config.py"
RUNTIME_FOLDER: Final = "runtime"
TEST_REPORTING_MEGABYTE: Final = "1.0 MB"
TEST_REPORTING_TEXT_COUNT: Final = "1"
TEST_REPORTING_PUBLICATION: Final = "publication"
TEST_REPORTING_TWO_ROW_CSV: Final = (
    b"Book Id,Title,Author\n42,Synthetic reporting book,Synthetic author\n"
    b"43,Another synthetic book,Synthetic author\n"
)

# Processed-storage compaction.
TEST_PAYLOAD_MEMORY: Final = ":memory:"
TEST_PAYLOAD_SQL_PARAM: Final = "sql"
STORAGE_PAYLOAD_PREFIX: Final = "payload:"
STORAGE_PAYLOAD_SCHEMA: Final = (
    "CREATE TABLE processed_payloads (sha256 TEXT PRIMARY KEY NOT NULL, "
    "body BLOB NOT NULL, size INTEGER NOT NULL CHECK(size >= 0))"
)
STORAGE_PAYLOAD_INSERT: Final = (
    "INSERT INTO processed_payloads(sha256, body, size) VALUES (?, ?, ?) "
    "ON CONFLICT(sha256) DO NOTHING"
)
STORAGE_PAYLOAD_SELECT: Final = "SELECT body, size FROM processed_payloads WHERE sha256 = ?"
STORAGE_PAYLOAD_COUNTS: Final = "SELECT COUNT(*) FROM processed_payloads"
STORAGE_PAYLOAD_DAMAGED: Final = (
    "A processed payload is missing, invalid, or damaged. No replacement snapshot was published."
)
STORAGE_MIGRATE_SELECT_PROGRESS: Final = "SELECT id, raw_json FROM progress ORDER BY id"
STORAGE_MIGRATE_UPDATE_PROGRESS: Final = "UPDATE progress SET raw_json = ? WHERE id = ?"
STORAGE_MIGRATE_SELECT_SNAPSHOTS: Final = "SELECT id, raw_json FROM snapshots ORDER BY id"
STORAGE_MIGRATE_UPDATE_SNAPSHOTS: Final = "UPDATE snapshots SET raw_json = ? WHERE id = ?"
STORAGE_MIGRATE_SELECT_RECORDS: Final = "SELECT id, record_json FROM snapshot_records ORDER BY id"
STORAGE_MIGRATE_UPDATE_RECORDS: Final = "UPDATE snapshot_records SET record_json = ? WHERE id = ?"
STORAGE_MIGRATE_SELECT_ACTIVE: Final = "SELECT id, latest_json FROM source_records ORDER BY id"
STORAGE_MIGRATE_UPDATE_ACTIVE: Final = "UPDATE source_records SET latest_json = ? WHERE id = ?"
STORAGE_MIGRATE_SELECT_ATTEMPTS: Final = "SELECT id, raw_json FROM enrichment_attempts ORDER BY id"
STORAGE_MIGRATE_UPDATE_ATTEMPTS: Final = "UPDATE enrichment_attempts SET raw_json = ? WHERE id = ?"
STORAGE_MIGRATE_SELECT_CANDIDATES: Final = (
    "SELECT id, candidate_json FROM enrichment_candidates ORDER BY id"
)
STORAGE_MIGRATE_UPDATE_CANDIDATES: Final = (
    "UPDATE enrichment_candidates SET candidate_json = ? WHERE id = ?"
)
STORAGE_COMPACT: Final = "VACUUM"
STORAGE_CHECKPOINT: Final = "PRAGMA wal_checkpoint(TRUNCATE)"
TEST_PAYLOAD_TEXT: Final = "A repeated synthetic catalog description. "
TEST_PAYLOAD_KEY: Final = "synthetic-description"
TEST_PAYLOAD_CORRUPT: Final = "UPDATE processed_payloads SET body = X'00' WHERE sha256 = ?"
TEST_PAYLOAD_REMOVE: Final = "DELETE FROM processed_payloads WHERE sha256 = ?"
TEST_PAYLOAD_BAD_SIZE: Final = "UPDATE processed_payloads SET size = size + 1 WHERE sha256 = ?"
TEST_STORAGE_FORCE_LEGACY: Final = "PRAGMA user_version = 1"
TEST_STORAGE_DROP_PAYLOADS: Final = "DROP TABLE processed_payloads"
TEST_STORAGE_CORRUPT_LEGACY: Final = "UPDATE source_records SET latest_json = 'invalid-json'"
TEST_STORAGE_PAYLOAD_TABLE_COUNT: Final = (
    "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'processed_payloads'"
)

# One-command sync.
CLI_TEST_ENSURE_TOKEN: Final = "ensure_access_token"
CLI_TEST_ISATTY: Final = "isatty"
CLI_TEST_RETIRED_OPTION: Final = "option"
CLI_TEST_INTERACTIVE_PARAMETER: Final = "interactive"
OAUTH_AUTHORIZATION_REQUIRED_CODE: Final = "google_books_authorization_required"
VERIFY_CAPTURE_MISSING: Final = "Fresh collection has no archived capture manifest."
DETAIL: Final = "detail"
VERIFY_CAPTURE_RAW: Final = (
    "Fresh collection archived and verified: {pages} original pages "
    "(manifest fingerprint {digest})."
)
VERIFY_CAPTURE_COUNTS: Final = (
    "{records} books processed; {library} published; advertised source count {expected}."
)

# Google Books OAuth.
OAUTH_FILE: Final = "google-books-oauth.json"
OAUTH_CLIENT_ID: Final = "client_id"
OAUTH_CLIENT_SECRET: Final = "client_secret"
OAUTH_CLIENT_ID_ENV: Final = "GOOGLE_BOOKS_CLIENT_ID"
OAUTH_CLIENT_SECRET_ENV: Final = "GOOGLE_BOOKS_CLIENT_SECRET"
OAUTH_CLIENT_ID_PROMPT: Final = "Google Books OAuth client ID (hidden): "
OAUTH_CLIENT_SECRET_PROMPT: Final = "Google Books OAuth client secret (hidden): "
OAUTH_ACCESS_TOKEN: Final = "access_token"
OAUTH_REFRESH_TOKEN: Final = "refresh_token"
OAUTH_EXPIRES_AT: Final = "expires_at"
OAUTH_EXPIRES_IN: Final = "expires_in"
OAUTH_TOKEN_TYPE: Final = "token_type"
OAUTH_BEARER: Final = "Bearer"
OAUTH_BEARER_HEADER: Final = "Bearer {token}"
OAUTH_AUTHORIZATION_HEADER: Final = "Authorization"
OAUTH_TOKEN_ENDPOINT: Final = "https://oauth2.googleapis.com/token"
OAUTH_TOKEN_HOST: Final = "oauth2.googleapis.com"
OAUTH_AUTHORIZATION_ENDPOINT: Final = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_BOOKS_SCOPE: Final = "https://www.googleapis.com/auth/books"
OAUTH_POST: Final = "POST"
OAUTH_STATE: Final = "state"
OAUTH_CODE: Final = "code"
OAUTH_ERROR: Final = "error"
OAUTH_GRANT_TYPE: Final = "grant_type"
OAUTH_AUTHORIZATION_CODE: Final = "authorization_code"
OAUTH_SCOPE: Final = "scope"
OAUTH_RESPONSE_TYPE: Final = "response_type"
OAUTH_REDIRECT_URI_KEY: Final = "redirect_uri"
OAUTH_CODE_CHALLENGE: Final = "code_challenge"
OAUTH_CODE_CHALLENGE_METHOD: Final = "code_challenge_method"
OAUTH_CODE_VERIFIER: Final = "code_verifier"
OAUTH_S256: Final = "S256"
OAUTH_ACCESS_TYPE: Final = "access_type"
OAUTH_OFFLINE: Final = "offline"
OAUTH_PROMPT: Final = "prompt"
OAUTH_CONSENT: Final = "consent"
OAUTH_BASE64_PADDING: Final = b"="
OAUTH_ASCII: Final = "ascii"
OAUTH_LOOPBACK_HOST: Final = "127.0.0.1"
OAUTH_LOOPBACK_AUTHORITY: Final = "127.0.0.1:{port}"
OAUTH_CALLBACK_PATH: Final = "/oauth2/callback"
OAUTH_REDIRECT_URI: Final = "http://127.0.0.1:{port}/oauth2/callback"
OAUTH_HOST_HEADER: Final = "Host"
OAUTH_CALLBACK_CONTENT_TYPE: Final = "text/plain; charset=utf-8"
OAUTH_CACHE_CONTROL: Final = "Cache-Control"
OAUTH_NO_STORE: Final = "no-store"
OAUTH_CALLBACK_BODY: Final = (
    b"Return to BookyStats for the authorization result. You can close this browser tab."
)
OAUTH_FAILURE: Final = (
    "Google Books authorization failed or expired. No credentials were replaced. "
    "Check the OAuth client setup and exact redirect "
    "http://127.0.0.1:8765/oauth2/callback, then rerun booky sync in a terminal "
    "to complete browser consent when authorization is required."
)
OAUTH_SETUP_REQUIRED: Final = (
    "Run booky sync in an interactive terminal for hidden OAuth credential prompts, "
    "or set GOOGLE_BOOKS_CLIENT_ID and GOOGLE_BOOKS_CLIENT_SECRET locally. "
    "Client credentials alone do not authorize access; browser consent is required."
)
OAUTH_CLI_OPTION: Final = "--google-books-auth"
OAUTH_PROVIDER_REQUIRED: Final = (
    "Google Books requires GOOGLE_BOOKS_API_KEY or browser consent initiated by "
    "booky sync. OAuth client credentials alone are not authorization."
)
OAUTH_ISSUE_CODE: Final = "google_books_oauth_failed"
OAUTH_QUERY_SEPARATOR: Final = "?"
OAUTH_WARNING_ERROR: Final = "error"
OAUTH_TEST_CLIENT_ID: Final = "synthetic-client.apps.googleusercontent.com"
OAUTH_TEST_CLIENT_SECRET: Final = "synthetic-oauth-client-secret"
OAUTH_TEST_ACCESS_TOKEN: Final = "synthetic-access-token"
OAUTH_TEST_NEW_ACCESS_TOKEN: Final = "synthetic-refreshed-access-token"
OAUTH_TEST_REFRESH_TOKEN: Final = "synthetic-refresh-token"
OAUTH_TEST_CODE: Final = "synthetic-authorization-code"
OAUTH_TEST_STATE: Final = "synthetic-state"
OAUTH_TEST_CALLBACK_PARAMETER: Final = "path"
OAUTH_TEST_FAILURE_MATCH: Final = "Google Books authorization failed"
OAUTH_TEST_STATE_MISMATCH: Final = "/oauth2/callback?state=wrong&code=synthetic-code"
OAUTH_TEST_STATE_MISSING: Final = "/oauth2/callback?code=synthetic-code"
OAUTH_TEST_STATE_DUPLICATE: Final = (
    "/oauth2/callback?state=synthetic-state&state=synthetic-state&code=synthetic-code"
)
OAUTH_TEST_CODE_DUPLICATE: Final = (
    "/oauth2/callback?state=synthetic-state&code=first-code&code=second-code"
)
OAUTH_TEST_CODE_MISSING: Final = "/oauth2/callback?state=synthetic-state"
OAUTH_TEST_DENIED: Final = "/oauth2/callback?state=synthetic-state&error=access_denied"
OAUTH_TEST_WRONG_PATH: Final = "/other?state=synthetic-state&code=synthetic-code"
OAUTH_TEST_RECEIVE_ATTRIBUTE: Final = "_receive_code"
OAUTH_TEST_SERVER_ATTRIBUTE: Final = "ThreadingHTTPServer"
OAUTH_TEST_MONOTONIC_ATTRIBUTE: Final = "monotonic"
OAUTH_TEST_OTHER_URL: Final = "https://openlibrary.org/"
OAUTH_TEST_HEADER_INJECTION: Final = "synthetic-token\r\nInjected: synthetic-value"
OAUTH_BEARER_PATTERN: Final = r"[A-Za-z0-9._~+/-]+=*"

# Automatic Google authorization.
OAUTH_INVALID_GRANT: Final = "invalid_grant"
OAUTH_AUTHORIZATION_REQUIRED: Final = (
    "Google Books authorization is required. Run booky sync in an interactive "
    "terminal and complete the visible browser consent."
)
OAUTH_TEST_UNAVAILABLE_PROMPT: Final = "Unexpected credential prompt"
OAUTH_TEST_UNAVAILABLE_BROWSER: Final = "Unexpected browser authorization"
OAUTH_TEST_DAMAGED_CREDENTIALS: Final = "{broken"
OAUTH_TEST_REFRESH_FAILURE_PARAMETER: Final = "failure_mode"
OAUTH_TEST_REFRESH_FAILURE_SERVER: Final = "server"
OAUTH_TEST_REFRESH_FAILURE_NETWORK: Final = "network"
OAUTH_TEST_REFRESH_FAILURE_OTHER: Final = "other"
OAUTH_TEST_REFRESH_FAILURE_BAD_BODY: Final = "bad_body"
OAUTH_TEST_REFRESH_FAILURE_BAD_STATUS: Final = "bad_status"

# Automatic source acquisition.
AUTO_CAPTURE_HTML_MEDIA_TYPE: Final = "text/html"
AUTO_CAPTURE_MANIFEST_MEDIA_TYPE: Final = "application/vnd.bookystats.source-capture+json"
AUTO_CAPTURE_DOCUMENTS: Final = "documents"
AUTO_CAPTURE_AT: Final = "captured_at"
AUTO_CAPTURE_SHA256: Final = "sha256"
AUTO_CAPTURE_LATEST_BY_MEDIA_TYPE: Final = (
    RAW_SELECT_CAPTURE + "WHERE c.source = ? AND c.account_id = ? AND c.collection = ? "
    "AND c.media_type = ? ORDER BY c.sequence DESC LIMIT 1"
)
AUTO_CAPTURE_RECORD_COUNT: Final = "record_count"
AUTO_CAPTURE_PAGES_SEEN: Final = "pages_seen"
OAUTH_TEST_INTERACTIVE_PARAMETER: Final = "interactive"
OAUTH_TEST_ENVIRONMENT_PARAMETER: Final = "use_environment"

# Configured CSV ingestion.
CSV_INPUTS: Final = "csv_inputs"
CSV_INPUT_PATH: Final = "path"
CSV_INPUT_EXISTS: Final = "exists"
CSV_INPUT_NOT_CONFIGURED_CODE: Final = "csv_input_not_configured"
CSV_INPUT_NOT_CONFIGURED: Final = (
    "Set the {source}/{collection} CSV path in config.json under files. "
    "Live source fetching is disabled; no archived file was substituted."
)
CSV_INPUT_UNAVAILABLE_CODE: Final = "csv_input_unavailable"
CSV_INPUT_UNAVAILABLE: Final = (
    "Cannot read or archive {filename}. Check the configured CSV path and file access. "
    "No archived file was substituted; the last complete snapshot is retained."
)
STATUS_CSV_HEADING: Final = "CSV inputs (no live source fetching)"
STATUS_CSV_LINE: Final = "  {source}/{collection}: {filename} [{state}]"
STATUS_CSV_NOT_CONFIGURED: Final = "path not configured"
STATUS_CSV_READY: Final = "ready"
STATUS_CSV_MISSING: Final = "missing"
CSV_FILES_KEY: Final = "files"
CSV_TEST_BROWSER_GET: Final = "get"
CSV_TEST_FAILURE_PARAMETER: Final = "failure"
CSV_CONFIGURATION_PATH: Final = "configuration_file"
STATUS_CSV_CONFIGURATION: Final = "  Config: {path}"
CSV_INPUT_FOREIGN_PATH: Final = (
    "CSV paths must be relative to the data directory or absolute paths for this machine. "
    "Use relative paths to share configuration across machines."
)

# Analytics input and reporting.
AN_APPETITE: Final = "appetite"
AN_DECLARED: Final = "declared"
AN_SCOPE: Final = "{source}/{collection}"
AN_READ_SCOPE: Final = "goodreads/read"
AN_PUBLISHED: Final = "published"
AN_ATTEMPT_ID: Final = "attempt_id"
AN_CHECKED_AT: Final = "checked_at"
AN_INPUT_ACCOUNT_ERROR: Final = "Analytics account settings do not match the saved library."
AN_INPUT_INCOMPLETE: Final = "Analytics needs complete, compatible saved source snapshots."
AN_INPUT_LINEAGE_ERROR: Final = "Analytics input references are incomplete or inconsistent."
AN_NO_READ_DATA: Final = "analytics_read_missing"
AN_NO_READ_DATA_MESSAGE: Final = (
    "No Goodreads Read collection is available for reading preferences."
)
AN_INPUT_ACCOUNTS: Final = "SELECT source, account_id FROM source_accounts ORDER BY source"
AN_INPUT_SNAPSHOTS: Final = (
    "SELECT c.source, c.account_id, c.collection, c.state, c.active_snapshot_id, "
    "s.raw_json, s.published FROM source_collections c "
    "JOIN snapshots s ON s.id = c.active_snapshot_id ORDER BY c.source, c.collection"
)
AN_INPUT_RECORDS: Final = (
    "SELECT r.*, c.collection FROM source_records r "
    "JOIN memberships m ON m.record_id = r.id "
    "JOIN source_collections c ON c.id = m.collection_id "
    "ORDER BY r.source, r.source_id, c.collection"
)
AN_INPUT_METADATA: Final = (
    "SELECT e.record_id, e.provider, e.attempt_id, e.candidate_id, a.checked_at, c.candidate_json "
    "FROM enrichment_active e JOIN enrichment_attempts a ON a.id = e.attempt_id "
    "JOIN enrichment_candidates c ON c.id = e.candidate_id "
    "JOIN source_records r ON r.id = e.record_id "
    "WHERE a.identity_hash = r.identity_hash AND c.selected = 1 "
    "ORDER BY e.record_id, e.provider"
)
AN_UNKNOWN_DIMENSION: Final = "Unknown reading-appetite dimension."
AN_INVALID_PREFERENCES: Final = "Declared preferences need known dimensions and values from 0 to 1."
AN_WORK_ID: Final = "work:{work_id}"
AN_CALCULATION_VERSION: Final = "analytics-v7-reader-first-storygraph-ratings"
AN_SUPPORTED: Final = "supported"
AN_SUBSET: Final = "subset"
AN_NEEDS_ENRICHMENT: Final = "needs_enrichment"
AN_NEEDS_OBSERVATIONS: Final = "needs_observations"
AN_UNSUPPORTED: Final = "unsupported"
AN_TASTE: Final = "taste"
AN_WATCHLIST: Final = "watchlist"
AN_WONDER: Final = "wonder"
AN_SURPRISE: Final = "surprise"
AN_INTENSITY: Final = "intensity"
AN_MEANING: Final = "meaning"
AN_CONNECTION: Final = "connection"
AN_CLARITY: Final = "clarity"
AN_WATCHLIST_SCOPE: Final = "goodreads/to-read"
AN_SOURCE_COUNTS: Final = "source_counts"
AN_PERSONAL_RATING_RECORDS: Final = "personal_rating_records"
AN_ACCOUNT_FINGERPRINT: Final = "account_fingerprint"
AN_CALCULATION_VERSION_KEY: Final = "calculation_version"
AN_TASTE_KEY: Final = "taste_key"
AN_AS_OF_DATE: Final = "as_of_date"
AN_EVIDENCE: Final = "evidence"
AN_CONTENT_EVIDENCE: Final = "content_evidence"
MC_TARGET_DEFERRED: Final = "metadata_target_deferred"
AN_BOOK_LABELS: Final = "book_labels"
AN_SOURCE_SNAPSHOT_IDS: Final = "source_snapshot_ids"
AN_ANALYTICS: Final = "analytics"
AN_DATABASE: Final = "analytics.sqlite3"
AN_FAILED_CODE: Final = "analytics_failed"
AN_SKIPPED_CODE: Final = "analytics_skipped"
AN_SKIPPED_MESSAGE: Final = (
    "Analytics was not updated because a source did not complete; the last report is retained."
)
AN_RECEIPT_LINE: Final = (
    "Analytics: {state}; report {report_id}, {findings} findings; "
    "{rated}/{read} Read works have a confirmed personal rating."
)
AN_REUSE_LINE: Final = "  Reused calculations: taste={taste}, watchlist={watchlist}."
AN_STATUS_LINE: Final = "Analytics: report {report_id}, saved {created_at}."
STATUS_ANALYTICS_METRIC_ID: Final = "metric_id"
STATUS_ANALYTICS_SAMPLE_SIZE: Final = "sample_size"
STATUS_ANALYTICS_COUNTS: Final = (
    "  Read works: {read}; personal-rating linked: {rated}; watchlist works: {watchlist}."
)
STATUS_ANALYTICS_COUNT: Final = "{count:,}"
STATUS_ANALYTICS_CONTENT: Final = (
    "  Catalog-content appetite mentions: {known}/{read} Read works have usable descriptions."
)
STATUS_ANALYTICS_APPETITE: Final = "    {dimension}: {count} works with supported text mentions."
STATUS_ANALYTICS_NO_APPETITE: Final = "    No appetite mention group meets the evidence threshold."
STATUS_ANALYTICS_SCOPE: Final = (
    "  Content mentions are not personality traits or official Read Your Color scores. "
    "Use status --json for quotes, capabilities and limitations."
)
STATUS_ANALYTICS_COMPLETIONS: Final = (
    "  Selected completion-date evidence: {count}/{read} Read works "
    "(Goodreads first; StoryGraph supplemental)."
)
STATUS_ANALYTICS_ADDITIONS: Final = (
    "  Library-addition dates: {read_dates}/{read} Read; {watch_dates}/{watchlist} watchlist. "
    "Addition dates are not reading dates."
)
PROD_PRODUCTS: Final = "products"
PROD_FAILED_CODE: Final = "products_failed"
PROD_FAILED_MESSAGE: Final = (
    "Report generation failed ({error_type}); the previous bundle is retained."
)
PROD_SKIPPED_CODE: Final = "products_skipped"
PROD_SKIPPED_MESSAGE: Final = (
    "Recommendations, quality and PDF were not published because current analytics "
    "did not complete. "
    "The last complete report bundle remains available."
)
PROD_RUN_STARTED: Final = "Run {run_id} started."
PROD_STAGE_SOURCES: Final = "Stage: importing configured CSV snapshots."
PROD_STAGE_METADATA: Final = "Stage: {provider} metadata enrichment."
PROD_STAGE_RECONCILE: Final = "Stage: reconciling confirmed catalog identities."
PROD_STAGE_ANALYTICS: Final = "Stage: calculating or reusing reading analytics."
PROD_STAGE_PRODUCTS: Final = "Stage: metadata quality, watchlist recommendations and PDF report."
PROD_STAGE_RESULT: Final = "Stage {stage}: {state}."
PROD_STAGE_FINISHED: Final = "Run {run_id} finished: {state}."
PROD_ANALYTICS_STAGE: Final = "analytics"
PROD_REPORTS_FOLDER: Final = "reports"
PROD_BUNDLE_NAME: Final = "report-{report_id}"
PROD_PENDING_PREFIX: Final = ".pending-report-"
PROD_LATEST_FILE: Final = "latest.json"
PROD_MANIFEST_FILE: Final = "manifest.json"
PROD_ANALYTICS_FILE: Final = "analytics.json"
PROD_RECOMMENDATIONS_FILE: Final = "recommendations.json"
PROD_QUALITY_FILE: Final = "metadata-quality.json"
PROD_PDF_FILE: Final = "library.pdf"
PROD_BUNDLE: Final = "bundle"
PROD_FILES: Final = "files"
PROD_HASHES: Final = "hashes"
PROD_RECEIPT: Final = "receipt"
PROD_INPUT_MISMATCH: Final = "Product generation requires the exact saved analytics input manifest."
PROD_INVALID_BUNDLE: Final = (
    "The saved report bundle is incomplete, inconsistent or fails integrity checks."
)
PROD_REPORT_LINE: Final = (
    "Reports #{report_id}: {state}; {ranked} ranked, {shortlisted} shortlisted, "
    "{unrankable} without enough evidence, {excluded} excluded."
)
PROD_PDF_LINE: Final = "  Library PDF: {path}"
PROD_QUALITY_LINE: Final = "  Metadata quality: {path}"
PROD_RECOMMENDATIONS_LINE: Final = "  Watchlist recommendations: {path}"
PROD_RETAINED_LINE: Final = (
    "  Retained report bundle; newer analytics have not been published to PDF."
)
PROD_OUTPUT_DIRECTORY: Final = "output_directory"
PROD_PDF_PATH: Final = "pdf_file"
PROD_QUALITY_PATH: Final = "metadata_quality_file"
PROD_RECOMMENDATIONS_PATH: Final = "recommendations_file"
PROD_MANIFEST_PATH: Final = "manifest_file"
PROD_TEST_JSON: Final = "{}"
PROD_TEST_PDF: Final = b"%PDF-1.7\nSynthetic bundle persistence fixture.\n"
PROD_TEST_CORRUPT: Final = b"corrupt"
PROD_TEST_FAILURE: Final = "Injected report output failure."
PROD_TEST_FILENAME: Final = "filename"
PROD_TEST_ATOMIC_WRITE: Final = "atomic_write"
PROD_INVALID_PROVIDER_STATUS: Final = "Saved provider diagnostics have an invalid structure."
PROD_TEST_SOURCE_FAILURE: Final = "source_failure"
AN_CREATED_AT: Final = "created_at"
AN_SOURCE_IDS: Final = "source_ids"
AN_FINDINGS: Final = "findings"
AN_REPORT_ID: Final = "report_id"
AN_TEST_OVERLAP: Final = "overlap"
AN_TEST_OUTPUT_KIND: Final = "output_kind"
AN_TEST_UNICODE: Final = "Murakami \u014d"
AN_TEST_ASCII: Final = "ascii"
AN_TEST_STDOUT: Final = "sys.stdout"
AN_TEST_FIELD_STATE: Final = "field_state"

# Analytics calculations.
AN_PROFILE_FIRST_PUBLICATION: Final = "read.structure.first_publication_years"
AN_PROFILE_FIRST_PUBLICATION_NOTE: Final = (
    "Original-work first-publication years are distinct from edition years and reading dates. "
    "Only explicit, valid work-level publication evidence is used; missing years stay unknown."
)
AN_PROFILE_WATCH_COMPOSITION: Final = "watchlist.composition.{feature}"
AN_PROFILE_METADATA: Final = "read.profile.metadata_quality"
AN_PROFILE_METADATA_NOTE: Final = (
    "Coverage measures available evidence, not factual accuracy. Source counts overlap when "
    "multiple sources support one work. Unverified capture labels are retained as evidence, "
    "never counted as confirmed book attributes. Descriptions are catalog text, not reviews. "
    "Singular language describes matched-edition language, not proof of language actually read; "
    "plural languages reports work-level catalog availability across editions separately."
)
AN_PROFILE_UNVERIFIED_PREFIX: Final = "unverified_capture_"
AN_PROFILE_UNVERIFIED_WORKS: Final = "works_with_unverified_capture_labels"
AN_PROFILE_SOURCE_COUNTS: Final = "supporting_source_work_counts"
AN_PROFILE_STATE_COUNTS: Final = "field_state_work_counts"
AN_EXECUTION_MODE: Final = "execution_mode"
AN_EXECUTION_PARALLEL: Final = "parallel"
AN_EXECUTION_SERIAL: Final = "serial"
AN_EXECUTION_CACHED: Final = "cached"
AN_EXECUTION_LINE: Final = "  Analysis execution: {mode}."
AN_CAPABILITIES: Final = "capabilities"
AN_TEST_PARALLEL_THRESHOLD_ATTRIBUTE: Final = "AN_PARALLEL_MIN_WORKS"
AN_TEST_CONTENT_JOB_ATTRIBUTE: Final = "build_content_analysis"
AN_BIAS_METRIC: Final = "ratings.availability.{feature}"
AN_BIAS_AVAILABLE: Final = "personal_rating_available"
AN_BIAS_UNAVAILABLE: Final = "personal_rating_unavailable_or_conflicting"
AN_BIAS_NOTE: Final = (
    "Compares known book features with and without a linked personal rating. Availability "
    "depends on source coverage, matching, missing ratings and conflicts; this is not proof "
    "of intentional rating selection. Each known work has total fractional weight one. "
    "Missing features are excluded, not treated as negative labels. A difference warns "
    "against generalizing rated-subset enjoyment to the whole library."
)
AN_METADATA_ORIGIN: Final = "{source}:{source_id}"
AN_CALC_STRUCTURE_PAGES: Final = "read.structure.page_counts"
AN_CALC_STRUCTURE_PUBLICATION: Final = "read.structure.edition_publication_years"
AN_CALC_RECURRING: Final = "read.profile.recurring_attributes"
AN_CALC_RECURRING_CAPABILITY: Final = "read.profile.recurring_attributes.{kind}"
AN_CALC_PAIR_LENGTH: Final = "genre_by_page_length"
AN_CALC_PAIR_FORMAT: Final = "genre_by_edition_format"
AN_CALC_PAIR_GENRES: Final = "genre_pairs"
AN_CALC_RECURRING_NOTE: Final = (
    "Rating-independent observed co-occurrences, not psychological traits, enjoyment, "
    "causality, or hypothesis tests. At most six most-exposed observed genres and three "
    "formats are considered; at most four combinations per kind pass the configured "
    "unique-work support minimum. Each kind has its own known-feature denominator. "
    "Tags overlap, so combinations are not disjoint and shares need not sum to one. "
    "Source taxonomy quality, contamination, and missing labels can limit interpretation."
)
AN_CALC_PROFILE_NOTE: Final = (
    "Rating-independent unique completed-work profile, including works with unknown personal "
    "ratings. Membership counts may overlap; each known work contributes total fractional "
    "weight one across its observed labels. Repetition means multiple distinct works with "
    "the same explicit label, not inferred rereads, series order, or author geography. "
    "Labels summarize the supplied taxonomy; they do not establish its accuracy."
)
AN_CALC_PAGES_NOTE: Final = (
    "Known positive edition page counts only; missing/failed/unsupported pages are not zero. "
    "Quartiles use inclusive linear interpolation at (N-1)*p; one observation yields equal "
    "quartiles. Edition page counts are not observed pages read or active reading duration."
)
AN_CALC_PUBLICATION_NOTE: Final = (
    "Edition publication years only, not original-work publication, reading dates, book ages, "
    "or reading-era preferences. Missing/failed/unsupported edition years remain unknown; "
    "no publication year is inferred from reading, capture dates, or work-level metadata."
)
AN_CALC_MEMBERSHIP: Final = "unique_work_membership_counts"
AN_CALC_REPEATED_LABELS: Final = "labels_repeated_across_distinct_works"
AN_CALC_REPEATED_WORKS: Final = "known_works_with_any_repeated_label"
AN_CALC_SINGLETON_LABELS: Final = "labels_observed_on_only_one_work"
AN_CALC_QUARTILE_LOW: Final = "first_quartile"
AN_CALC_QUARTILE_HIGH: Final = "third_quartile"
AN_CALC_QUANTILE_METHOD: Final = "inclusive"
AN_CALC_EDITION_YEARS: Final = "edition_publication_year_counts"
AN_CALC_CANDIDATES: Final = "bounded_combinations_examined"
AN_CALC_COMBINATIONS: Final = "supported_observed_combinations"
AN_CALC_LEFT_LABEL: Final = "first_label"
AN_CALC_RIGHT_LABEL: Final = "second_label"
AN_CALC_MIN_SUPPORT: Final = "minimum_unique_work_support"
AN_CALC_COMPOSITION_DISTANCE: Final = "jensen_shannon_distance_base_2"
AN_CALC_COMPOSITION_GAPS: Final = "largest_supported_fractional_share_gaps"
AN_CALC_READ_MISSING: Final = "read_missing_feature_count"
AN_CALC_WATCH_MISSING: Final = "watchlist_missing_feature_count"
AN_CALC_READ_LABEL_SUPPORT: Final = "read_unique_work_label_support"
AN_CALC_WATCH_LABEL_SUPPORT: Final = "watchlist_unique_work_label_support"
AN_CALC_WATCH_ENJOYMENT: Final = "watchlist.enjoyment.{feature}"
AN_CALC_COMPOSITION_NOTE: Final = (
    "Rating-independent comparison of observed book facts, not enjoyment or recommendations. "
    "Within each population, missing/empty/failed/unsupported features are excluded; each "
    "known work splits weight equally among its labels. Jensen-Shannon distance uses base-2 "
    "logs and lies in [0,1]; unavailable populations have unknown distance, not zero. Gaps "
    "require minimum known support in both populations and minimum combined label support; "
    "at most five largest absolute category-share gaps are shown, never book rankings. "
    "Metadata coverage and taxonomy quality are separate from composition differences."
)
AN_CALC_COMPOSITION_REASON: Final = (
    "Composition uses available book facts in both Read and Watchlist, independent of "
    "personal ratings or supported enjoyment preferences; inspect both missing-feature counts."
)
AN_CALC_COMPLEMENT: Final = "known_feature_complement"
AN_CALC_COMPLEMENT_BOOKS: Final = "complement_supporting_books"
AN_CALC_SHRUNK_EFFECT: Final = "adjusted_group_minus_adjusted_complement"
AN_CALC_HIGH_LIFT: Final = "high_rating_rate_ratio_vs_complement"
AN_CALC_HIGH_DIFFERENCE: Final = "high_rating_rate_difference_vs_complement"
AN_CALC_COMPARISON_SUPPORTED: Final = "comparison_has_minimum_rated_support"
AN_CALC_INDEPENDENT_AUTHORS: Final = "distinct_known_authors"
AN_CALC_COMPARISON_LOO: Final = "leave_one_author_out_group_complement_differences"
AN_CALC_COMPARISON_NOTE: Final = (
    "Complement includes only works with known comparison features, excluding the group; "
    "missing labels are not confirmed absences. Means shrink to the completed-work mean. "
    "This global shrinkage prior uses all eligible rated completed works, including "
    "works with unavailable comparison features. "
    "All comparisons are exploratory, correlated, and uncorrected for multiple comparisons, "
    "not formal tests or causal effects. Known authors are support clusters, "
    "not independent trials."
)
AN_CALC_VALIDATION: Final = "read.validation.leave_one_work_out"
AN_CALC_VALIDATION_SIGNAL: Final = "read.validation.categorical_signal"
AN_CALC_VALIDATION_NOTE: Final = (
    "Retrospective leave-one-confirmed-work-out validation of the rated Read subset only, "
    "not future recommendation accuracy. Each fold fits only other works: global mean and "
    "categorical group means with minimum support after holdout. Label predictions average "
    "within feature dimensions, then equally across supported dimensions; no signal falls "
    "back to the training-only mean. Predictions are bounded to 0..5. MAE/RMSE and baseline "
    "use identical held-out works. Metadata, selected ratings, authors, and series can be "
    "correlated; this is not temporal or independent-author validation. No parameter tuning, "
    "confidence interval, watchlist score, or future-accuracy claim is made."
)
AN_CALC_VALIDATION_NEED: Final = (
    "Need at least thirty linked rated completed unique works; categorical signal additionally "
    "needs the configured minimum rated group size after excluding each held-out work."
)
AN_CALC_MAE: Final = "mean_absolute_error"
AN_CALC_RMSE: Final = "root_mean_squared_error"
AN_CALC_BASELINE_ERRORS: Final = "training_only_mean_baseline_errors"
AN_CALC_PREDICTOR_ERRORS: Final = "categorical_predictor_errors"
AN_CALC_MAE_GAIN: Final = "baseline_minus_predictor_mae"
AN_CALC_RMSE_GAIN: Final = "baseline_minus_predictor_rmse"
AN_CALC_ADVANTAGE: Final = "lower_mae_than_baseline"
AN_CALC_DIMENSIONS: Final = "feature_dimension_evaluations"
AN_CALC_SIGNAL: Final = "works_with_supported_categorical_signal"
AN_CALC_SIGNAL_COVERAGE: Final = "signal_share_of_rated_completed_works"
AN_CALC_SIGNAL_SUBSET: Final = "same_work_signal_subset_evaluation"
AN_CALC_FALLBACK: Final = "baseline_fallback_works"
AN_CALC_TRAINING_MIN: Final = "minimum_group_size_after_holdout"
AN_CALC_TRAINING: Final = "training"
AN_CALC_COHORT_YEARS: Final = "eligible_observed_calendar_years"
AN_CALC_COHORTS: Final = "year_cohorts"
AN_CALC_SAMPLE_VOLUME: Final = "equal_sample_volume"
AN_CALC_EXPECTED_LABELS: Final = "expected_distinct_genre_labels"
AN_CALC_OBSERVED_LABELS: Final = "observed_distinct_genre_labels"
AN_CALC_TAG_DENSITY: Final = "mean_explicit_genre_labels_per_known_work"
AN_CALC_RAREFACTION_NOTE: Final = (
    "Each work enters its earliest observed exact-day completed event year once. Partial-date "
    "events do not assign these cohorts. Only calendar years before the explicit as-of year "
    "and at most six latest eligible years are compared, with at least ten genre-known works "
    "per year. Expected distinct labels use uniform sampling without replacement at the "
    "smallest included known-work count: sum[1 - choose(N-frequency,m)/choose(N,m)]. "
    "This controls observed work volume, not tag density, overlapping taxonomy, metadata "
    "changes, incomplete exports, selection bias, or account-history completeness."
)
AN_CALC_RAREFACTION_NEED: Final = (
    "Need two completed calendar-year cohorts with at least ten unique genre-known works "
    "and exact-day finished events in each; year/month-only dates do not meet this design."
)
AN_CALC_CHANGE_NOTE: Final = (
    "Current authoritative ratings grouped by earliest observed exact-day completion year, "
    "not historical ratings or rating revisions. The latest two eligible completed-year "
    "cohorts require ten genre-known rated works each and at least two shared exact genre-label "
    "sets with configured minimum rated support per year. Exact label sets form disjoint "
    "strata; pooled rated-work shares in shared strata are fixed weights for both years. "
    "Standardized differences are descriptive, not causal taste change. Selection, taxonomy "
    "changes, author/series mix, omitted attributes, rereading, and later rating revisions "
    "remain possible explanations. No significance tests or historical preference claims."
)
AN_CALC_CHANGE_NEED: Final = (
    "Need two completed-year exact-day dated rated cohorts and two shared genre-label-set "
    "strata with sufficient rated support; current undated ratings cannot establish change."
)
AN_CALC_BEFORE: Final = "earlier_year"
AN_CALC_AFTER: Final = "later_year"
AN_CALC_STRATA: Final = "shared_disjoint_genre_label_sets"
AN_CALC_WEIGHT: Final = "pooled_rated_work_weight"
AN_CALC_STANDARDIZED: Final = "standardized_current_rating_mean"
AN_CALC_STANDARDIZED_HIGH: Final = "standardized_current_high_rating_share"
AN_CALC_STANDARDIZED_DELTA: Final = "later_minus_earlier_standardized_mean"
AN_CALC_STANDARDIZED_HIGH_DELTA: Final = "later_minus_earlier_standardized_high_rating_share"
AN_CALC_RAW_DELTA: Final = "later_minus_earlier_unstandardized_comparable_mean"
AN_CALC_SHARED_COVERAGE: Final = "shared_strata_coverage"
AN_CALC_TEST_OLD_FINISH: Final = "2023-02-01"
AN_CALC_TEST_AS_OF: Final = "2025-01-01T00:00:00+00:00"
AN_CALC_SUPPORTING_BOOKS: Final = "supporting_books"
AN_CALC_TEST_EARLY_PARTIAL: Final = "2022"
AN_CALC_TEST_LANGUAGE: Final = "synthetic-language"
AN_CALC_RATED_KNOWN: Final = "rated_genre_known_count"
AN_CALC_EXCLUSIONS: Final = "analysis_exclusion_counts"
AN_CALC_UNDATED_EXCLUDED: Final = "no_full_day_completed_prior_year_cohort"
AN_CALC_COHORT_EXCLUDED: Final = "thin_or_older_than_selected_cohorts"
AN_CALC_MISSING_LABEL_EXCLUDED: Final = "genre_missing_within_selected_cohorts"
AN_CALC_LANGUAGE_EN: Final = "en"
AN_CALC_LANGUAGE_ENG: Final = "eng"
AN_CALC_LANGUAGE_NOTE: Final = (
    "Matched-edition language is not proof of language actually read. Work-level catalog "
    "language availability across editions is separate and never supplies this feature. "
    "English ISO en/eng aliases are grouped together without changing raw observations. "
    "Other taxonomy/ISO alias normalization remains an input-extraction responsibility; "
    "different unmapped codes alone are not evidence of distinct reader tastes."
)
AN_CALC_FIELD_STATES_FIELD: Final = "field_states"
AN_CALC_READ_COUNT: Final = "read.unique_works"
AN_CALC_WATCH_COUNT: Final = "watchlist.unique_works"
AN_CALC_SOURCE_COUNTS: Final = "sources.record_counts"
AN_CALC_RATING_RECORDS: Final = "sources.personal_rating_records"
AN_CALC_RATINGS: Final = "read.personal_ratings"
AN_CALC_FAVORITES: Final = "read.favorites"
AN_CALC_RATED_COUNT: Final = "read.rated_works"
AN_CALC_GROUP: Final = "read.feature.{feature}.{label}"
AN_CALC_BREADTH: Final = "read.breadth.{feature}"
AN_CALC_CONDITIONAL: Final = "read.conditional.genre_length.{genre}.{length}"
AN_CALC_PROVIDER: Final = "read.community.{provider}"
AN_CALC_REVIEW: Final = "reviews.mentions.{theme}"
AN_CALC_PERIOD: Final = "read.finished.{precision}.{period}"
AN_CALC_DURATION: Final = "read.duration_days"
AN_CALC_DNF: Final = "library.explicit_dnf"
AN_CALC_APPETITE: Final = "read.appetite.{dimension}"
AN_CALC_WATCH_FEATURE: Final = "watchlist.feature.{feature}"
AN_CALC_PREFERENCE_KEY: Final = "{feature}:{label}"
AN_CALC_WATCH_MISMATCH: Final = "watchlist.preference_mismatch"
AN_CALC_WATCH_AGE: Final = "watchlist.backlog_age"
AN_CALC_WATCH_MOVEMENT: Final = "watchlist.movement"
AN_CALC_CONDITIONS: Final = "conditional_preferences"
AN_CALC_REVIEWS: Final = "review_themes"
AN_CALC_TIME: Final = "reading_time_trends"
AN_CALC_TASTE_CHANGE: Final = "comparable_group_taste_changes"
AN_CALC_REVISIONS: Final = "rating_revisions"
AN_CALC_YEAR_BREADTH: Final = "comparable_volume_yearly_breadth"
AN_CALC_SERIES_ORDER: Final = "series_start_versus_continuation"
AN_CALC_DNF_REASONS: Final = "explicit_dnf_reasons"
AN_CALC_COMMUNITY: Final = "named_provider_community_agreement"
AN_CALC_MOOD_PACE: Final = "mood_and_pace_preferences"
AN_CALC_FAMILIARITY: Final = "author_familiarity_conditionals"
AN_CALC_REREADS: Final = "dated_rereading"
AN_CALC_APP_DECLARED: Final = "appetite.declared.{dimension}"
AN_CALC_APP_EXPOSURE: Final = "appetite.exposure.{dimension}"
AN_CALC_APP_ENJOYMENT: Final = "appetite.enjoyment.{dimension}"
AN_CALC_POP_READ: Final = "unique_completed_works"
AN_CALC_POP_WATCH: Final = "unique_current_watchlist_works"
AN_CALC_POP_LIBRARY: Final = "unique_confirmed_works"
AN_CALC_POP_RECORDS: Final = "source_records_not_unique_works"
AN_CALC_POP_READER: Final = "explicit_reader_preferences"
AN_CALC_UNIT_WORKS: Final = "works"
AN_CALC_UNIT_SUMMARY: Final = "descriptive_summary"
AN_CALC_UNIT_RATING: Final = "personal_stars_0_to_5"
AN_CALC_UNIT_DAYS: Final = "elapsed_calendar_days"
AN_CALC_RELIABLE: Final = "descriptive"
AN_CALC_WEAK: Final = "weak"
AN_CALC_EXPLORATORY: Final = "exploratory_association"
AN_CALC_NO_INFERENCE: Final = (
    "Descriptive associations, not causal effects or population estimates; "
    "ratings may be a selected subset."
)
AN_CALC_THIN: Final = (
    "Too few rated works or concentrated/missing author or series coverage; "
    "not a reliable general preference."
)
AN_CALC_SINGLE: Final = "One rated work cannot establish consistency."
AN_CALC_PRIOR_NOTE: Final = (
    "Adjusted mean uses (rating total + prior strength * completed-work mean) / "
    "(rated group size + prior strength); no formal significance."
)
AN_CALC_MULTILABEL: Final = (
    "Labels may overlap; prevalence uses unique works, concentration uses fractional "
    "label membership among known works."
)
AN_CALC_REVIEW_NOTE: Final = (
    "Exact keyword mentions only; excerpts preserve negation and context. "
    "No sentiment, enjoyment, or DNF reason is inferred."
)
AN_CALC_TIME_NOTE: Final = (
    "Only explicit completed reading-event dates; each work counts once per period. "
    "Current ratings are not historical ratings."
)
AN_CALC_DURATION_NOTE: Final = (
    "Exact-day start/finish pairs only; duplicate date pairs count once per work; "
    "elapsed calendar days, not active reading time."
)
AN_CALC_DNF_NOTE: Final = (
    "Explicit DNF works only; absence is unknown without a source DNF scope. "
    "No low-rating or review-based DNF inference."
)
AN_CALC_APP_NOTE: Final = (
    "Six independent public-concept dimensions, not a normalized score, personality "
    "assessment, or reproduction of proprietary assessment. Explicit labels only."
)
AN_CALC_WATCH_NOTE: Final = (
    "Composition and descriptive supported preference deltas only; "
    "not book scores, ranking, or next-read recommendations."
)
AN_CALC_SCOPE_NOTE: Final = (
    "Source record totals do not establish unique-work counts, linked completed ratings, "
    "account completeness, or unattended collection."
)
AN_CALC_NO_RATINGS: Final = (
    "Supply authoritative personal ratings linked to completed works; "
    "missing or conflicted ratings remain unknown."
)
AN_CALC_NEED_FEATURES: Final = (
    "Supply supported explicit catalog labels for this feature; "
    "missing labels are not negative labels."
)
AN_CALC_NEED_SUPPORT: Final = (
    "More rated unique works with diverse authors/series are needed; "
    "inspect coverage and concentration."
)
AN_CALC_NEED_REVIEWS: Final = (
    "Supply Goodreads personal review text with provenance; raw provider descriptions "
    "and StoryGraph attributes are not personal reviews."
)
AN_CALC_NEED_DATES: Final = (
    "Supply real reading-event dates with retained precision; "
    "capture/import timestamps cannot substitute."
)
AN_CALC_NEED_REVISIONS: Final = (
    "Need dated historical personal-rating observations; current ratings cannot identify revisions."
)
AN_CALC_NEED_COMPARABLE: Final = (
    "Needs comparable longitudinal reading groups, selection/coverage controls, "
    "and observation-time ratings; current-rating summaries are not taste change."
)
AN_CALC_NEED_YEAR_BREADTH: Final = (
    "Needs a prespecified comparable-volume yearly design; raw distinct-label counts "
    "across unequal years are not comparable."
)
AN_CALC_NEED_ORDER: Final = (
    "Verified series positions and reading order are unavailable; "
    "series names alone cannot distinguish starting from continuing."
)
AN_CALC_NEED_DNF_REASONS: Final = (
    "Only explicit supplied personal explanations support reasons; "
    "keyword mentions do not establish why a book was abandoned."
)
AN_CALC_NEED_COMMUNITY: Final = (
    "Need matched authoritative personal and named-provider community ratings "
    "on a documented 0-to-5 scale."
)
AN_CALC_NEED_APP_LABELS: Final = (
    "Supply explicit, provenance-backed book labels for this dimension; "
    "no genre/description-to-appetite heuristic is used."
)
AN_CALC_NEED_DECLARATION: Final = (
    "Supply this independent declared dimension as an explicit value from zero to one."
)
AN_CALC_NEED_ADDED: Final = (
    "Input has no source-backed watchlist added date; "
    "reading and capture dates cannot identify backlog age."
)
AN_CALC_NEED_MOVEMENT: Final = (
    "Need comparable historical source snapshots with explicit additions/removals; "
    "current membership is not movement."
)
AN_CALC_NEED_MOOD: Final = (
    "No authoritative supported mood/pace labels; StoryGraph non-rating fields remain raw-only."
)
AN_CALC_NEED_FAMILIARITY: Final = (
    "Needs real chronological history and prespecified subject familiarity; "
    "current author membership cannot establish familiarity at reading time."
)
AN_CALC_NEED_REREADS: Final = (
    "Need distinct identified dated completed events; different precision or "
    "import duplicates do not establish rereading."
)
AN_CALC_AVAILABLE_REASON: Final = (
    "Calculated only for the available unique-work subset; "
    "see denominators, missingness, provenance, and limitations."
)
AN_CALC_N: Final = "count"
AN_CALC_TOTAL: Final = "population_count"
AN_CALC_KNOWN: Final = "known_feature_count"
AN_CALC_MISSING: Final = "missing_feature_count"
AN_CALC_RATED: Final = "rated_count"
AN_CALC_RATING_MISSING: Final = "missing_or_conflicted_rating_count"
AN_CALC_COVERAGE: Final = "rating_coverage"
AN_CALC_MEAN: Final = "mean"
AN_CALC_MEDIAN: Final = "median"
AN_CALC_STDEV: Final = "population_standard_deviation"
AN_CALC_MIN: Final = "minimum"
AN_CALC_MAX: Final = "maximum"
AN_CALC_HISTOGRAM: Final = "rating_histogram"
AN_CALC_ADJUSTED: Final = "adjusted_mean"
AN_CALC_PRIOR: Final = "prior_strength"
AN_CALC_HIGH_COUNT: Final = "high_rated_count"
AN_CALC_HIGH_SHARE: Final = "high_rated_share_of_rated_group"
AN_CALC_FAVORITE_SHARE: Final = "share_of_all_rated_favorites"
AN_CALC_THRESHOLD: Final = "high_rating_threshold"
AN_CALC_PREVALENCE: Final = "share_of_all_completed_works"
AN_CALC_KNOWN_PREVALENCE: Final = "share_of_known_feature_works"
AN_CALC_AUTHOR_KNOWN: Final = "rated_works_with_authors"
AN_CALC_SERIES_KNOWN: Final = "rated_works_with_series"
AN_CALC_AUTHOR_SHARE: Final = "largest_author_share_of_known_rated_works"
AN_CALC_SERIES_SHARE: Final = "largest_series_share_of_known_rated_works"
AN_CALC_LEAVE_AUTHOR: Final = "leave_one_author_out_means"
AN_CALC_LABELS: Final = "labels"
AN_CALC_HHI: Final = "fractional_membership_hhi"
AN_CALC_EFFECTIVE: Final = "effective_number_of_labels"
AN_CALC_SHARES: Final = "fractional_membership_shares"
AN_CALC_LENGTH: Final = "page_length"
AN_CALC_SHORT: Final = "under_200_pages"
AN_CALC_MEDIUM: Final = "200_to_399_pages"
AN_CALC_LONG: Final = "400_or_more_pages"
AN_CALC_GENRE_BASELINE: Final = "genre_only_mean"
AN_CALC_LENGTH_BASELINE: Final = "length_only_mean"
AN_CALC_EXCERPT: Final = "exact_review"
AN_CALC_EVIDENCE: Final = "review_evidence"
AN_CALC_BOOK: Final = "book_id"
AN_CALC_THEME: Final = "theme"
AN_CALC_DECLARED: Final = "declared_preference"
AN_CALC_EXPOSURE: Final = "exposure_share_of_explicitly_labeled_works"
AN_CALC_ENJOYMENT: Final = "enjoyment"
AN_CALC_PROVIDER_NAME: Final = "provider"
AN_CALC_PROVIDER_MEAN: Final = "provider_mean"
AN_CALC_DELTA: Final = "mean_personal_minus_provider"
AN_CALC_PROVIDER_SCALE: Final = "provider_scale"
AN_CALC_PROVIDER_SCALE_VALUE: Final = "0_to_5"
AN_CALC_READ_SHARE: Final = "read_share_of_known"
AN_CALC_WATCH_SHARE: Final = "watchlist_share_of_known"
AN_CALC_COMPOSITION_DELTA: Final = "watchlist_minus_read_share"
AN_CALC_PREFERENCE_DELTA: Final = "supported_adjusted_rating_delta"
AN_CALC_UNSUPPORTED_LABELS: Final = "labels_without_supported_enjoyment"
AN_CALC_WATCH_KNOWN: Final = "watchlist_known_count"
AN_CALC_READ_KNOWN: Final = "read_known_count"
AN_CALC_DURATIONS: Final = "duration_days"
AN_CALC_EVENT_COUNT: Final = "distinct_exact_date_pairs"
AN_CALC_REREAD_COUNT: Final = "additional_identified_completed_events"
AN_CALC_THEME_CHARACTER: Final = "character_development"
AN_CALC_THEME_EMOTION: Final = "emotional_impact"
AN_CALC_THEME_PROSE: Final = "prose"
AN_CALC_THEME_PACING: Final = "pacing"
AN_CALC_THEME_WORLD: Final = "world_building"
AN_CALC_THEME_RELATIONSHIPS: Final = "relationships"
AN_CALC_THEME_IDEAS: Final = "ideas_and_learning"
AN_CALC_THEME_PREDICTABLE: Final = "predictability"
AN_CALC_THEME_ENDING: Final = "ending_satisfaction"
AN_CALC_THEME_REPETITION: Final = "repetition"
AN_CALC_THEME_NARRATION: Final = "narration"
AN_CALC_THEME_LENGTH: Final = "length"
AN_CALC_PATTERN_CHARACTER: Final = r"\bcharacter(?:s| development| growth)?\b"
AN_CALC_PATTERN_EMOTION: Final = r"\b(?:emotional|emotion|moving|moved|cry|cried|tears)\b"
AN_CALC_PATTERN_PROSE: Final = r"\b(?:prose|writing style|lyrical|sentences)\b"
AN_CALC_PATTERN_PACING: Final = r"\b(?:pacing|pace|slow|fast.paced)\b"
AN_CALC_PATTERN_WORLD: Final = r"\b(?:world.building|worldbuilding|setting)\b"
AN_CALC_PATTERN_RELATIONSHIPS: Final = r"\b(?:relationships?|friendship|romance|family)\b"
AN_CALC_PATTERN_IDEAS: Final = r"\b(?:ideas?|learned|learning|insight|thought.provoking)\b"
AN_CALC_PATTERN_PREDICTABLE: Final = r"\b(?:predictable|predictability|unpredictable|twist)\b"
AN_CALC_PATTERN_ENDING: Final = r"\b(?:ending|conclusion|finale)\b"
AN_CALC_PATTERN_REPETITION: Final = r"\b(?:repetition|repetitive|repeated|repeats)\b"
AN_CALC_PATTERN_NARRATION: Final = r"\b(?:narration|narrator|audiobook|voice)\b"
AN_CALC_PATTERN_LENGTH: Final = r"\b(?:length|long|short|pages)\b"
AN_CALC_TEST_KEY: Final = "test-calculation"
AN_CALC_TEST_ACCOUNT: Final = "synthetic-account"
AN_CALC_TEST_HASH: Final = "synthetic-settings-hash"
AN_CALC_TEST_GENRE: Final = "fantasy"
AN_CALC_TEST_OTHER: Final = "history"
AN_CALC_TEST_AUTHOR: Final = "Synthetic Author"
AN_CALC_TEST_AUTHOR_FORMAT: Final = "Synthetic Author {index}"
AN_CALC_TEST_PROVIDER: Final = "google_books"
AN_CALC_TEST_REVIEW: Final = "The pacing was not good. The ending was predictable."
AN_CALC_TEST_YEAR: Final = "2024"
AN_CALC_TEST_START: Final = "2024-01-01"
AN_CALC_TEST_FINISH: Final = "2024-01-11"
AN_CALC_TEST_MONTH: Final = "2024-01"
AN_CALC_RATING_CONFLICT: Final = "rating_conflict"
AN_CALC_UNCERTAINTY: Final = "uncertainty"
AN_CALC_FEATURE_ENJOYMENT: Final = "read.enjoyment.{feature}"
AN_CALC_CONDITIONAL_NOTE: Final = (
    "Exploratory genre-by-page-length summaries only: at most six most-exposed genres, "
    "lexical tie-break, three fixed length bands. Rated support and concentration gates "
    "apply; no significance tests or causal claims."
)
AN_CALC_PROVIDER_NOTE: Final = (
    "Paired matched works only, separately by named provider on a validated 0-to-5 scale; "
    "no universal consensus or cross-provider pooling."
)
AN_CALC_APPETITE_LABELS: Final = "appetite"
AN_CALC_REVIEW_POP: Final = "unique_works_with_supplied_personal_reviews"
AN_CALC_FAVORITE_CONCENTRATION: Final = "read.favorites.concentration"
AN_CALC_KNOWN_STATES: Final = "input_field_state_counts"
AN_CALC_LIMITATIONS: Final = "limitations"
AN_CALC_POP_HISTORY: Final = "unique_confirmed_completed_or_explicit_dnf_works"
AN_CALC_EVIDENCE_FIELD: Final = "evidence"
AN_CALC_LOO_RANGE: Final = "leave_one_author_out_delta_range"
AN_CALC_LOO_NOTE: Final = (
    "Leave-one-author-out checks retain the completed-work baseline and require minimum "
    "rated support after exclusion; sign reversals weaken general preferences."
)
AN_CALC_ADDED: Final = "source_added_date"
AN_CALC_PRECISION: Final = "source_date_precision"
AN_CALC_AS_OF: Final = "analysis_as_of_calendar_date"
AN_CALC_AGE_DAYS: Final = "age_calendar_days"
AN_CALC_AGE_NOTE: Final = (
    "Age uses source-backed watchlist added dates and the explicit analysis as-of "
    "calendar date, not reading or capture dates. Year/month precision is preserved "
    "without invented days. Future or missing dates have unknown ages; no rediscovery ranking."
)
AN_CALC_DURATION_MEAN_NOTE: Final = (
    "Mean and median summarize per-work mean durations with equal weight per work; "
    "distinct exact-day pairs are retained separately."
)
AN_CALC_THIN_GROUPS: Final = "read.feature.{feature}.insufficient_consistency_support"
AN_CALC_TEST_FINISH_LATER: Final = "2024-02-01"
AN_CALC_TEST_ADDED_FIELD: Final = "added_at"
AN_CALC_TEST_SNAPSHOTS_FIELD: Final = "snapshots"
AN_CALC_TEST_MANIFEST_FIELD: Final = "manifest"
AN_CALC_TEST_FEATURES_FIELD: Final = "features"
AN_CALC_AS_OF_FIELD: Final = "as_of"
AN_CALC_AXIS_FEELING: Final = "appetite.axes.feeling_thinking"
AN_CALC_AXIS_GROUNDED: Final = "appetite.axes.grounded_imaginative"
AN_CALC_AXIS_NOTE: Final = (
    "No explicit axis observations or public validated scoring weights are available; "
    "six independent appetite labels do not establish feeling/thinking or "
    "grounded/imaginative coordinates."
)

# Analytics persistence.
AN_STORE_ERROR: Final = (
    "Analytics storage could not be used safely. Close other users of analytics.sqlite3, "
    "then remove this rebuildable analytics database and run sync again."
)
AN_STORE_CLOSED: Final = "Analytics storage is closed. Open a new AnalyticsStore."
AN_STORE_COLLISION: Final = (
    "An analytics cache key identifies different results. Rebuild analytics.sqlite3 "
    "and check the calculation version and input fingerprint."
)
AN_STORE_KEY_PATTERN: Final = r"[0-9a-f]{64}"
AN_STORE_FOREIGN_KEYS: Final = "PRAGMA foreign_keys = ON"
AN_STORE_FOREIGN_KEYS_CHECK: Final = "PRAGMA foreign_keys"
AN_STORE_INTEGRITY: Final = "PRAGMA integrity_check"
AN_STORE_FK_CHECK: Final = "PRAGMA foreign_key_check"
AN_STORE_APP_ID: Final = "PRAGMA application_id"
AN_STORE_VERSION: Final = "PRAGMA user_version"
AN_STORE_SET_APP_ID: Final = "PRAGMA application_id = 1112752462"
AN_STORE_SET_VERSION: Final = "PRAGMA user_version = 2"
AN_STORE_BEGIN: Final = "BEGIN IMMEDIATE"
AN_STORE_SCHEMA: Final = (
    "SELECT type, name, tbl_name, sql FROM sqlite_master "
    "WHERE name NOT GLOB 'sqlite_*' ORDER BY name"
)
AN_STORE_HAS_SCHEMA: Final = "SELECT 1 FROM sqlite_master LIMIT 1"
AN_STORE_COMPONENT_TABLE: Final = "analysis_components"
AN_STORE_REPORT_TABLE: Final = "analysis_reports"
AN_STORE_TABLE: Final = "table"
AN_STORE_CREATE_COMPONENTS: Final = (
    "CREATE TABLE analysis_components ("
    "cache_key TEXT PRIMARY KEY NOT NULL, kind TEXT NOT NULL, "
    "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
)
AN_STORE_CREATE_REPORTS: Final = (
    "CREATE TABLE analysis_reports ("
    "report_id INTEGER PRIMARY KEY AUTOINCREMENT, taste_key TEXT NOT NULL "
    "REFERENCES analysis_components(cache_key), watchlist_key TEXT NOT NULL "
    "REFERENCES analysis_components(cache_key), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
)
AN_STORE_GET_COMPONENT: Final = (
    "SELECT cache_key, kind, payload, payload_hash FROM analysis_components WHERE cache_key = ?"
)
AN_STORE_ALL_COMPONENTS: Final = (
    "SELECT cache_key, kind, payload, payload_hash FROM analysis_components"
)
AN_STORE_INSERT_COMPONENT: Final = (
    "INSERT INTO analysis_components(cache_key, kind, payload, payload_hash) VALUES (?, ?, ?, ?)"
)
AN_STORE_INSERT_REPORT: Final = (
    "INSERT INTO analysis_reports(taste_key, watchlist_key, payload, payload_hash) "
    "VALUES (?, ?, ?, ?)"
)
AN_STORE_ALL_REPORTS: Final = (
    "SELECT report_id, taste_key, watchlist_key, payload, payload_hash FROM analysis_reports"
)
AN_STORE_LATEST: Final = AN_STORE_ALL_REPORTS + " ORDER BY report_id DESC LIMIT 1"
AN_STORE_REPORT_ID: Final = "report_id"
AN_STORE_TASTE: Final = "taste"
AN_STORE_WATCHLIST: Final = "watchlist"
AN_STORE_TEST_FILENAME: Final = "analytics.sqlite3"
AN_STORE_TEST_ACCOUNT: Final = "synthetic-account-fingerprint"
AN_STORE_TEST_TIME: Final = "2026-01-02T03:04:05+00:00"
AN_STORE_TEST_ACCOUNT_ID: Final = "synthetic-reader"
AN_STORE_TEST_SETTINGS: Final = "synthetic-settings-hash"
AN_STORE_TEST_RAW: Final = "synthetic-raw-document"
AN_STORE_TEST_METRIC: Final = "synthetic-metric"
AN_STORE_TEST_UNIT: Final = "books"
AN_STORE_TEST_RELIABILITY: Final = "supported"
AN_STORE_TEST_LABEL: Final = "synthetic"
AN_STORE_TEST_KEYS: Final = "a", "b", "c"
AN_STORE_TEST_BAD_KEY: Final = "not-a-sha256"
AN_STORE_TEST_COMPONENT_COUNT: Final = "SELECT COUNT(*) FROM analysis_components"
AN_STORE_TEST_REPORT_COUNT: Final = "SELECT COUNT(*) FROM analysis_reports"
AN_STORE_TEST_BAD_HASH: Final = "UPDATE analysis_components SET payload_hash = ?"
AN_STORE_TEST_BAD_REPORT_HASH: Final = "UPDATE analysis_reports SET payload_hash = ?"
AN_STORE_TEST_BAD_PAYLOAD: Final = (
    "UPDATE analysis_components SET payload = ?, payload_hash = ? WHERE cache_key = ?"
)
AN_STORE_TEST_BAD_BINDING: Final = "UPDATE analysis_reports SET taste_key = watchlist_key"
AN_STORE_TEST_BAD_SCHEMA: Final = "CREATE TABLE unexpected (value TEXT)"
AN_STORE_TEST_FUTURE_VERSION: Final = "PRAGMA user_version = 4"
AN_STORE_TEST_WRONG_APP: Final = "PRAGMA application_id = 12"
AN_STORE_TEST_FAIL_INSERT: Final = (
    "CREATE TRIGGER reject_report BEFORE INSERT ON analysis_reports "
    "BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END"
)
AN_STORE_TEST_CORRUPTION_PARAMETER: Final = "statement"
AN_STORE_TEST_COMPONENT_KEY: Final = "key"
AN_STORE_TEST_BAD_FK: Final = "UPDATE analysis_reports SET taste_key = ?"
AN_STORE_TEST_CORRUPT_BYTES: Final = b"not a SQLite database"
AN_STORE_TEST_TAMPER_REPORT: Final = "UPDATE analysis_reports SET payload = ?, payload_hash = ?"
AN_STORE_TEST_REUSED: Final = "taste_reused"
AN_STORE_TEST_PREFERENCES: Final = "preferences"
AN_STORE_TEST_MANIFEST: Final = "manifest"
AN_STORE_TEST_VERSION: Final = "calculation_version"
AN_STORE_TEST_GET_REPORT: Final = "SELECT payload FROM analysis_reports"
AN_STORE_TEST_ORDERED_REPORTS: Final = AN_STORE_ALL_REPORTS + " ORDER BY report_id"
AN_STORE_COMPONENT_KEY: Final = "key"
AN_STORE_FINDINGS: Final = "findings"
AN_STORE_SNAPSHOT_IDS: Final = "source_snapshot_ids"
AN_STORE_TEST_SNAPSHOTS: Final = "snapshots"
AN_STORE_TEST_SNAPSHOT_ID: Final = "snapshot_id"

# DQ_CAPTURE: browser observations without book-scoped capture evidence.
DQ_CAPTURE_UNVERIFIED_GENRES: Final = "unverified_capture_genres"
DQ_CAPTURE_UNVERIFIED_SERIES: Final = "unverified_capture_series"
DQ_CAPTURE_UNVERIFIED_SERIES_NUMBER: Final = "unverified_capture_series_number"
DQ_CAPTURE_UNVERIFIED_CODE: Final = "unverified_browser_capture"
DQ_CAPTURE_UNVERIFIED_MESSAGE: Final = (
    "Export record {row}: {field} has no book-scoped capture evidence. The captured value is "
    "retained as an unverified observation and raw field, not confirmed book metadata."
)
DQ_CAPTURE_TEST_GENRES: Final = "Navigation category | Fiction | Navigation category"
DQ_CAPTURE_TEST_SERIES: Final = "Explore collections"
DQ_CAPTURE_TEST_UNKNOWN: Final = "unknown"
DQ_CAPTURE_TEST_LABEL_PARAMETERS: Final = "header,field,unverified"
DQ_CAPTURE_TEST_STATE_PARAMETERS: Final = "value,state"

# MATCH_UPGRADE: conservative identity normalization, index maintenance and tests.
MATCH_UPGRADE_SERIES_PATTERN: Final = (
    r"\s+\((?P<series>[^()#]+?),\s*#(?P<number>\d+(?:\.\d+)?)\)\s*$"
)
MATCH_REPAIR_SERIES_SUFFIX: Final = r"\s+\((?P<series>[^()]+)\)\s*$"
MATCH_REPAIR_SERIES_ITEM: Final = r"(?P<series>[^()#;]+?),?\s*#(?P<number>\d+(?:\.\d+)?)"
MATCH_REPAIR_AMPERSAND: Final = " & "
MATCH_REPAIR_AND: Final = " and "
MATCH_REPAIR_VOLUME: Final = r"\bvolume\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b"
MATCH_REPAIR_ONE: Final = "one"
MATCH_REPAIR_TWO: Final = "two"
MATCH_REPAIR_THREE: Final = "three"
MATCH_REPAIR_FOUR: Final = "four"
MATCH_REPAIR_FIVE: Final = "five"
MATCH_REPAIR_SIX: Final = "six"
MATCH_REPAIR_SEVEN: Final = "seven"
MATCH_REPAIR_EIGHT: Final = "eight"
MATCH_REPAIR_NINE: Final = "nine"
MATCH_REPAIR_TEN: Final = "ten"
MATCH_REPAIR_VOLUME_PREFIX: Final = "volume "
MATCH_REPAIR_PRUNE_MEMBERS: Final = (
    "DELETE FROM memberships WHERE collection_id = ? AND record_id NOT IN "
    "(SELECT r.id FROM source_records r JOIN snapshot_records s ON s.source_id = r.source_id "
    "WHERE s.snapshot_id = ? AND r.source = ? AND r.account_id = ?)"
)
MATCH_REPAIR_ACTIVE_RECORD: Final = (
    "SELECT r.* FROM source_records r WHERE r.id = ? "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = r.id)"
)
MATCH_REPAIR_PENDING_ACTIVE: Final = (
    "SELECT c.kind FROM match_candidates c WHERE c.resolution = 'pending' "
    "AND (c.record_id = ? OR c.target_record_id = ?) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = c.record_id) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = c.target_record_id)"
)
MATCH_REPAIR_TEST_PLAIN: Final = "Paws and Prejudice"
MATCH_REPAIR_TEST_SERIES: Final = "Paws & Prejudice (Hearts of Alaska #2)"
MATCH_REPAIR_TEST_MULTISERIES: Final = (
    "Paws and Prejudice (Hearts of Alaska, #2; Northern Stories, #23)"
)
MATCH_REPAIR_TEST_CONFLICT: Final = "Paws and Prejudice (Hearts of Alaska #3; Northern Stories #23)"
MATCH_REPAIR_TEST_OMNIBUS: Final = "Paws and Prejudice (Hearts of Alaska #1-2)"
MATCH_REPAIR_TEST_VOLUME_WORD: Final = "Heartstopper: Volume Four (Heartstopper, #4)"
MATCH_REPAIR_TEST_VOLUME_DIGIT: Final = "Heartstopper Volume 4"
MATCH_REPAIR_TEST_VOLUME_OTHER: Final = "Heartstopper Volume 2"
MATCH_REPAIR_TEST_PARAMETERS: Final = "left_title,right_title"
MATCH_REPAIR_TEST_MALFORMED: Final = "Paws and Prejudice (Hearts of Alaska #2, 3)"
MATCH_REPAIR_TEST_ANNOTATION: Final = "Paws and Prejudice (Study Guide)"
MATCH_REPAIR_ACTIVE_WORK_PEER: Final = (
    "SELECT 1 FROM source_records r WHERE r.id != ? "
    "AND r.work_id = (SELECT work_id FROM source_records WHERE id = ?) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = r.id) LIMIT 1"
)
MATCH_REPAIR_WORK_AUTOMATIC: Final = "bibliography_work_automatic"
MATCH_REPAIR_WORK_REASON: Final = (
    "Reciprocally unique active cross-source full title and complete authors agree; "
    "edition identity remains separate and unconfirmed"
)
MATCH_REPAIR_WORK_LOST: Final = (
    "Bibliographic work linkage lost current, unique, compatible identity evidence"
)
MATCH_REPAIR_IDENTITY_PROOFS: Final = "identity_proofs"
MATCH_REPAIR_POLICY: Final = "identity-work-v1"
MATCH_REPAIR_POLICY_KEY: Final = "identity_policy"
MATCH_REPAIR_CONFIRM_CANDIDATE: Final = (
    "UPDATE match_candidates SET resolution = ? WHERE id = ? "
    "AND resolution NOT IN ('accepted', 'rejected')"
)
MATCH_REPAIR_CANDIDATE_ORDER: Final = " ORDER BY c.id"
MATCH_REPAIR_CANDIDATE_ACTIVE_ORDER: Final = (
    " AND (? OR (EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = c.record_id) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = c.target_record_id))) "
    "ORDER BY c.id"
)
MATCH_REPAIR_CURRENT_PROVIDER_CANDIDATES: Final = (
    "SELECT a.record_id, c.candidate_json, c.selected FROM enrichment_attempts a "
    "JOIN source_records r ON r.id = a.record_id "
    "JOIN enrichment_candidates c ON c.attempt_id = a.id "
    "WHERE a.provider = ? AND a.identity_hash = r.identity_hash "
    "AND a.id = (SELECT MAX(n.id) FROM enrichment_attempts n "
    "WHERE n.record_id = a.record_id AND n.provider = a.provider "
    "AND n.identity_hash = r.identity_hash)"
)
MATCH_REPAIR_COLLECTION_ITEM: Final = (
    r"(?P<series>[^()#;]+?),?\s*#"
    r"(?P<number>\d+(?:\.\d+)?(?:\s*(?:-|,)\s*\d+(?:\.\d+)?)*)"
)
MATCH_REPAIR_NUMBERED_TITLE: Final = (
    r"^(?P<title>.+?)\s+(?:(?P<marker>vol|volume)\s+)?"
    r"(?P<number>\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x)$"
)
MATCH_REPAIR_VOLUME_MARKER: Final = "marker"
MATCH_REPAIR_ROMAN_ONE: Final = "i"
MATCH_REPAIR_ROMAN_TWO: Final = "ii"
MATCH_REPAIR_ROMAN_THREE: Final = "iii"
MATCH_REPAIR_ROMAN_FOUR: Final = "iv"
MATCH_REPAIR_ROMAN_FIVE: Final = "v"
MATCH_REPAIR_ROMAN_SIX: Final = "vi"
MATCH_REPAIR_ROMAN_SEVEN: Final = "vii"
MATCH_REPAIR_ROMAN_EIGHT: Final = "viii"
MATCH_REPAIR_ROMAN_NINE: Final = "ix"
MATCH_REPAIR_ROMAN_TEN: Final = "x"
MATCH_REPAIR_MULTIPLICATION: Final = "\u00d7"
MATCH_REPAIR_LETTER_X: Final = " x "
MATCH_REPAIR_ALTERNATE_PREFIX: Final = "work-title:"
MATCH_REPAIR_VOLUME_KEY_PREFIX: Final = "numbered-work:"
MATCH_REPAIR_ISBN_KEY_PREFIX: Final = "edition-isbn:"
MATCH_REPAIR_CORROBORATED_REASON: Final = (
    "Shared validated ISBN corroborates compatible full title and nonconflicting author sets; "
    "work only, edition identity remains separate"
)
MATCH_REPAIR_VOLUME_REASON: Final = (
    "Exact numbered-volume title and complete authors agree across uniquely paired sources; "
    "edition identifiers remain distinct"
)
MATCH_REPAIR_POLICY_CORROBORATED: Final = "identity-work-v2-corroboration"
MTX_CATALOG_CONFLICT: Final = (
    "Current identity-validated catalog work identities conflict; automatic ISBN linkage "
    "cannot establish a shared work or edition"
)
MTX_CATALOG_RECORD_FILTER: Final = " AND a.record_id IN ({placeholders})"
MTX_SQL_PLACEHOLDER: Final = "?"
MTX_ACTIVE_IDENTITY_GROUPS: Final = (
    "SELECT r.* FROM source_records r WHERE r.id IN (?, ?) OR "
    "(r.work_id IN (SELECT work_id FROM source_records WHERE id IN (?, ?)) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = r.id))"
)
MTX_UPDATE_CATALOG_CONFLICT: Final = (
    "UPDATE match_candidates SET kind = 'conflicting', reason = ? WHERE id = ?"
)
MATCH_REPAIR_TEST_COLLECTION: Final = "Matilda (Library, #1-3)"
MATCH_REPAIR_TEST_OTHER_COLLECTION: Final = "Matilda (Library, #1-2)"
MATCH_REPAIR_TEST_MULTI_VOLUME: Final = "Matilda (Library, #0.5, 2.5, 2.6)"
MATCH_REPAIR_TEST_UNICODE_VOLUME: Final = "Example Family, Vol. \u2161"
MATCH_REPAIR_TEST_NUMBERED_VOLUME: Final = "Example Family 2"
MATCH_REPAIR_TEST_OTHER_VOLUME: Final = "Example Family 3"
MATCH_REPAIR_TEST_MULTIPLICATION_VOLUME: Final = "Example\u00d7Family 2"
MATCH_REPAIR_TEST_LETTER_VOLUME: Final = "Example x Family, Vol. 2"
MATCH_REPAIR_TEST_ACCENT_TITLE: Final = "Matild\u00e1"
MATCH_UPGRADE_ARTICLE_PATTERN: Final = r"^(?P<title>.+),\s*(?P<article>The|An|A)$"
MATCH_UPGRADE_ISBN_LABEL_PATTERN: Final = r"^ISBN(?:-(?P<width>1[03]))?\s*:?\s*(?=\d)"
MATCH_UPGRADE_ISBN_WIDTH_GROUP: Final = "width"
MATCH_UPGRADE_SERIES_GROUP: Final = "series"
MATCH_UPGRADE_NUMBER_GROUP: Final = "number"
MATCH_UPGRADE_TITLE_GROUP: Final = "title"
MATCH_UPGRADE_ARTICLE_GROUP: Final = "article"
MATCH_UPGRADE_UNICODE_FORM: Final = "NFKD"
MATCH_UPGRADE_COMBINING_CATEGORY: Final = "Mn"
MATCH_UPGRADE_LATIN_PREFIX: Final = "LATIN "
MATCH_UPGRADE_SERIES_CONFLICT: Final = "Shared ISBN has contradictory numbered-series identity"
MATCH_UPGRADE_NORMALIZED_ISBN: Final = (
    "Validated ISBN, structurally normalized full title, and normalized authors agree"
)
MATCH_UPGRADE_SUBTITLE_CANDIDATE: Final = (
    "Compatible title/subtitle and authors suggest a work; edition identity is unproved"
)
MATCH_UPGRADE_AUTHOR_CANDIDATE: Final = (
    "Shared ISBN and compatible title have incomplete or differing author evidence"
)
MATCH_UPGRADE_INDEX_ROWS: Final = "SELECT id, title_author_key, latest_json FROM source_records"
MATCH_UPGRADE_INDEX_KEY: Final = "title_author_key"
MATCH_UPGRADE_INDEX_UPDATE: Final = "UPDATE source_records SET title_author_key = ? WHERE id = ?"
MATCH_UPGRADE_OTHER_WORK_MEMBER: Final = (
    "SELECT 1 FROM source_records WHERE work_id = ? AND id != ? LIMIT 1"
)
MATCH_UPGRADE_PRIOR_DECISION: Final = (
    "SELECT 1 FROM match_decisions d LEFT JOIN match_candidates c ON c.id = d.candidate_id "
    "WHERE d.record_id = ? OR c.record_id = ? OR c.target_record_id = ? LIMIT 1"
)
MATCH_REPAIR_RECOVERY_DECISIONS: Final = (
    "SELECT d.*, c.target_record_id FROM match_decisions d "
    "JOIN match_candidates c ON c.id = d.candidate_id "
    "WHERE d.record_id IN (?, ?) OR c.record_id IN (?, ?) "
    "OR c.target_record_id IN (?, ?) ORDER BY d.id"
)
MATCH_UPGRADE_TEST_TITLE: Final = "A Game of Thrones"
MATCH_UPGRADE_TEST_SERIES_TITLE: Final = "A Game of Thrones (A Song of Ice and Fire, #1)"
MATCH_UPGRADE_TEST_OTHER_NUMBER: Final = "A Game of Thrones (A Song of Ice and Fire, #2)"
MATCH_UPGRADE_TEST_AUTHOR: Final = "George R.R. Martin"
MATCH_UPGRADE_TEST_SPACED_AUTHOR: Final = "George R. R. Martin"
MATCH_UPGRADE_TEST_COMPACT_AUTHOR: Final = "George RR Martin"
MATCH_UPGRADE_TEST_SUBTITLE: Final = "A Game of Thrones: An Illustrated Edition"
MATCH_UPGRADE_TEST_OTHER_SUBTITLE: Final = "A Game of Thrones: A Study Guide"
MATCH_UPGRADE_TEST_SORTED_TITLE: Final = "Stargazer's Sister, The"
MATCH_UPGRADE_TEST_ARTICLE_TITLE: Final = "The Stargazer\u2019s Sister"
MATCH_UPGRADE_TEST_ACCENT_AUTHOR: Final = "Genzaburō Yoshino"
MATCH_UPGRADE_TEST_PLAIN_AUTHOR: Final = "Genzaburo Yoshino"
MATCH_UPGRADE_TEST_PAREN_TITLE: Final = "A Game of Thrones (Part Two)"
MATCH_UPGRADE_TEST_OMNIBUS: Final = "A Game of Thrones (A Song of Ice and Fire, #1-3)"
MATCH_UPGRADE_TEST_ISBN_LABEL: Final = "ISBN9789365693393"
MATCH_UPGRADE_TEST_ISBN_VALUE: Final = "9789365693393"
MATCH_UPGRADE_TEST_ISBN10_LABEL: Final = "ISBN-10: 0140328726"
MATCH_UPGRADE_TEST_INVALID_LABEL: Final = "UID9789365693393"
MATCH_UPGRADE_TEST_INVALID_CHECK: Final = "ISBN9789365693394"
MATCH_UPGRADE_TEST_WRONG_WIDTH: Final = "ISBN-10: 9789365693393"
MATCH_UPGRADE_TEST_IDENTITIES: Final = (
    "SELECT id, work_id, edition_id, identity_hash FROM source_records ORDER BY id"
)
MATCH_UPGRADE_TEST_DECISIONS: Final = "SELECT id FROM match_decisions ORDER BY id"
MATCH_UPGRADE_TEST_LEGACY_KEY: Final = "UPDATE source_records SET title_author_key = ? WHERE id = ?"
MATCH_UPGRADE_TEST_COMPARE_ATTRIBUTE: Final = "compare_books"
MATCH_UPGRADE_TEST_NORMALIZED_PARAMETERS: Final = "left_title,right_title,left_author,right_author"
MATCH_UPGRADE_TEST_TITLE_PARAMETERS: Final = "title,kind"
MATCH_UPGRADE_TEST_ISBN_PARAMETERS: Final = "value,expected"
MATCH_UPGRADE_TEST_VOICED_AUTHOR: Final = "カズオ"
MATCH_UPGRADE_TEST_UNVOICED_AUTHOR: Final = "カスオ"
MATCH_UPGRADE_PROVIDER_WORK_PATTERN: Final = r"OL[1-9]\d*W"
MATCH_UPGRADE_PROVIDER_AUTOMATIC: Final = "provider_work_automatic"
MATCH_UPGRADE_PROVIDER_INVALIDATED: Final = "provider_work_invalidated"
MATCH_UPGRADE_WORK_CONFIRMED: Final = "work_confirmed"
MATCH_UPGRADE_PROVIDER_REASON: Final = (
    "Independently confirmed current Open Library work IDs agree; editions remain distinct"
)
MATCH_UPGRADE_PROVIDER_LOST: Final = (
    "Provider work linkage lost current, unique, compatible identity evidence"
)
MATCH_UPGRADE_DEPENDENCY_LOST: Final = "Automatic edition linkage depended on a remapped target"
MATCH_UPGRADE_ATTEMPT_ID: Final = "attempt_id"
MATCH_UPGRADE_EVIDENCE_JSON: Final = "evidence_json"
MATCH_UPGRADE_LAST_SNAPSHOT_ID: Final = "last_snapshot_id"
MATCH_UPGRADE_WORK_PROOFS: Final = "work_proofs"
MATCH_UPGRADE_ALL_RECORDS: Final = "SELECT * FROM source_records ORDER BY id"
MATCH_UPGRADE_ACTIVE_RECORD_IDS: Final = "SELECT DISTINCT record_id FROM memberships"
MATCH_UPGRADE_WORK_SELECTED: Final = (
    "SELECT e.record_id, e.attempt_id, e.candidate_id, a.identity_hash, c.candidate_json "
    "FROM enrichment_active e JOIN enrichment_attempts a ON a.id = e.attempt_id "
    "JOIN enrichment_candidates c ON c.id = e.candidate_id AND c.attempt_id = a.id "
    "JOIN source_records r ON r.id = e.record_id "
    "WHERE e.provider = ? AND a.provider = e.provider AND a.record_id = e.record_id "
    "AND c.selected = 1 AND c.kind = 'confirmed' AND a.identity_hash = r.identity_hash "
    "AND a.id = (SELECT MAX(n.id) FROM enrichment_attempts n "
    "WHERE n.record_id = e.record_id AND n.provider = e.provider "
    "AND n.identity_hash = r.identity_hash)"
)
MATCH_UPGRADE_ATTEMPT_CANDIDATES: Final = (
    "SELECT selected, candidate_json FROM enrichment_candidates WHERE attempt_id = ? ORDER BY id"
)
MATCH_UPGRADE_SELECTED: Final = "selected"
MATCH_UPGRADE_DECISIONS: Final = (
    "SELECT * FROM match_decisions WHERE kind = ? AND reversed_by IS NULL ORDER BY id DESC"
)
MATCH_UPGRADE_RESET_WORK_CANDIDATE: Final = (
    "UPDATE match_candidates SET kind = 'likely', reason = ?, resolution = 'pending' "
    "WHERE id = ? AND resolution NOT IN ('accepted', 'rejected')"
)
MATCH_UPGRADE_TEST_PROVIDER_WORK: Final = "OL12345W"
MATCH_UPGRADE_TEST_OTHER_WORK: Final = "OL54321W"
MATCH_UPGRADE_TEST_ALTERNATE_ISBN: Final = "9780306406157"

# META_COVERAGE: provider evidence and optional-field recovery.
META_COVERAGE_SERIES_NAME: Final = "series_name"
META_COVERAGE_SERIES_POSITION: Final = "series_position"
META_COVERAGE_SERIES_POSITIONS: Final = "series_positions"
META_COVERAGE_TEST_SERIES: Final = "Synthetic Catalog Series"
META_COVERAGE_TEST_POSITION: Final = "1.5"
META_COVERAGE_TEST_BAD_POSITION: Final = "position unavailable"
META_COVERAGE_POSITION_PATTERN: Final = r"\d+(?:\.\d+)?"
META_COVERAGE_TEST_ISSUE_CODE: Final = "issue_code"
META_COVERAGE_TEST_FAILED_FIELD: Final = "failed_field"
META_COVERAGE_WORK_DETAIL_URL: Final = "https://openlibrary.org/works/{identifier}.json"
META_COVERAGE_WORK_CACHE_KEY: Final = "work-detail:{identifier}"
META_COVERAGE_BODY: Final = "response_body"
META_COVERAGE_CAPTURED_AT: Final = "captured_at"
META_COVERAGE_CAPTURE_ID: Final = "raw_capture_id"
META_COVERAGE_ORIGIN: Final = "response_origin"
META_COVERAGE_SUBJECTS: Final = "subjects"
META_COVERAGE_FIRST_PUBLISH_DATE: Final = "first_publish_date"
META_COVERAGE_FIRST_PUBLICATION_DATE: Final = "first_publication_date"
META_COVERAGE_TEXT_TYPE: Final = "/type/text"
META_COVERAGE_WORK_TYPE: Final = "/type/work"
META_COVERAGE_DETAIL_FAILED: Final = "metadata_work_details_failed"
META_COVERAGE_DETAIL_CONFLICT: Final = "metadata_work_field_conflict"
META_COVERAGE_DETAIL_FAILED_MESSAGE: Final = (
    "Open Library work details unavailable ({code}); verified search fields retained."
)
META_COVERAGE_CONFLICT_MESSAGE: Final = (
    "Open Library search and work details disagree for {field}; both observations retained."
)
META_COVERAGE_IMPLEMENTATION_COLUMN: Final = "implementation_version"
META_COVERAGE_ATTEMPT_COLUMNS: Final = "PRAGMA table_info(enrichment_attempts)"
META_COVERAGE_MIGRATE_IMPLEMENTATION: Final = (
    "ALTER TABLE enrichment_attempts ADD COLUMN implementation_version INTEGER NOT NULL DEFAULT 0"
)
META_COVERAGE_TEST_OLD_IMPLEMENTATION: Final = (
    "UPDATE enrichment_attempts SET implementation_version = 0"
)
META_COVERAGE_TEST_DROP_IMPLEMENTATION: Final = (
    "ALTER TABLE enrichment_attempts DROP COLUMN implementation_version"
)
META_COVERAGE_TEST_SCHEMA_TWO: Final = "PRAGMA user_version = 2"
META_COVERAGE_CACHE_HIT: Final = "cache_hit"
META_COVERAGE_SOURCE_URL: Final = "source_url"
META_COVERAGE_WORK_FIXTURE: Final = "open_library_work.json"
META_COVERAGE_TEST_FIRST_DATE: Final = "1988-10"
META_COVERAGE_TEST_FIRST_YEAR: Final = "1988"
META_COVERAGE_TEST_DETAILS_TEXT: Final = "A synthetic public catalog description, not a review."
META_COVERAGE_TEST_UNKNOWN_KEY: Final = "future_catalog_field"
META_COVERAGE_TEST_UNKNOWN_VALUE: Final = "Preserved verbatim."
META_COVERAGE_TEST_BAD_DATE: Final = "circa an unknown century"
META_COVERAGE_TEST_DATE_PARAM: Final = "published"
META_COVERAGE_TEST_ADDITIONAL_SUBJECT: Final = "Adventure fiction"
META_COVERAGE_TEST_PRECISE_DATE: Final = "1988-10-01"
META_COVERAGE_TEST_OTHER_MONTH: Final = "1988-09"
META_COVERAGE_TEST_OTHER_YEAR: Final = "1987"
META_COVERAGE_TEST_DATE_CONFLICT_PARAMS: Final = "published,expected_conflict"
META_COVERAGE_SERIES_MEMBERSHIPS: Final = "series_memberships"
META_COVERAGE_SERIES_ID: Final = "series_id"
META_COVERAGE_MEMBERSHIP_POSITION: Final = "position"
META_COVERAGE_SERIES_REFERENCE_PATTERN: Final = r"/series/(OL\d+L)"
META_COVERAGE_TEST_SERIES_REFERENCE: Final = "/series/OL123L"
META_COVERAGE_TEST_SERIES_ID: Final = "OL123L"
META_COVERAGE_TEST_BAD_SERIES_REFERENCE: Final = "/series/OL123W"

# CONTENT_ANALYSIS: internal catalog-text rules, not an assessment or preference model.
CONTENT_ANALYSIS_VERSION: Final = "catalog-mentions-v1"
CONTENT_ANALYSIS_THEMES: Final = "content.themes.{collection}"
CONTENT_ANALYSIS_HUNGERS: Final = "content.hunger_mentions.{collection}"
CONTENT_ANALYSIS_UNIT: Final = "distinct_work_catalog_mentions"
CONTENT_ANALYSIS_RELIABILITY: Final = "descriptive_lexical_evidence"
CONTENT_ANALYSIS_RULE_VERSION: Final = "rule_version"
CONTENT_ANALYSIS_RULE_PATTERN: Final = "rule_pattern"
CONTENT_ANALYSIS_GROUPS: Final = "supported_mentions"
CONTENT_ANALYSIS_KNOWN: Final = "known_public_descriptions"
CONTENT_ANALYSIS_MISSING: Final = "missing_description_states"
CONTENT_ANALYSIS_UNVERIFIED: Final = "unverified_public_provenance"
CONTENT_ANALYSIS_UNMATCHED: Final = "known_descriptions_without_rule_match"
CONTENT_ANALYSIS_COUNT: Final = "mentioned_works"
CONTENT_ANALYSIS_SHARE: Final = "share_of_known_descriptions"
CONTENT_ANALYSIS_PROOF: Final = "proof"
CONTENT_ANALYSIS_WORK: Final = "work_id"
CONTENT_ANALYSIS_WORKS: Final = "supporting_work_ids"
CONTENT_ANALYSIS_SOURCE: Final = "source"
CONTENT_ANALYSIS_FIELD: Final = "field"
CONTENT_ANALYSIS_SCOPE: Final = "scope"
CONTENT_ANALYSIS_URL: Final = "public_source_url"
CONTENT_ANALYSIS_QUOTE: Final = "excerpt"
CONTENT_ANALYSIS_MATCH: Final = "matched_text"
CONTENT_ANALYSIS_THRESHOLD: Final = "minimum_support"
CONTENT_ANALYSIS_AS_OF: Final = "as_of"
CONTENT_ANALYSIS_SUPPRESSED: Final = "below_support_families"
CONTENT_ANALYSIS_MYSTERY: Final = "mystery_and_crime"
CONTENT_ANALYSIS_RELATIONSHIPS: Final = "relationships"
CONTENT_ANALYSIS_WORLDS: Final = "imagined_worlds"
CONTENT_ANALYSIS_IDEAS: Final = "ideas_and_learning"
CONTENT_ANALYSIS_ADVERSITY: Final = "danger_and_adversity"
CONTENT_ANALYSIS_MYSTERY_PATTERN: Final = r"\b(?:murder|detective|crime|mystery|investigation)\b"
CONTENT_ANALYSIS_RELATIONSHIPS_PATTERN: Final = (
    r"\b(?:friendship|family|families|marriage|romance|relationships|lovers)\b"
)
CONTENT_ANALYSIS_WORLDS_PATTERN: Final = (
    r"\b(?:magic|magical|dragons?|alien worlds?|distant planets?|imaginary worlds?)\b"
)
CONTENT_ANALYSIS_IDEAS_PATTERN: Final = (
    r"\b(?:science|scientific|philosophy|history|learning|research|mathematics)\b"
)
CONTENT_ANALYSIS_ADVERSITY_PATTERN: Final = r"\b(?:survival|danger|war|battle|peril|threat|chase)\b"
CONTENT_ANALYSIS_WONDER_PATTERN: Final = (
    r"\b(?:sense of wonder|wondrous|magical|magic|dragons?|alien worlds?|distant planets?)\b"
)
CONTENT_ANALYSIS_SURPRISE_PATTERN: Final = (
    r"\b(?:plot twists?|unexpected|unpredictable|shocking revelations?|astonishing discoveries)\b"
)
CONTENT_ANALYSIS_INTENSITY_PATTERN: Final = (
    r"\b(?:suspense|suspenseful|thrilling|thriller|terrifying|peril|high stakes)\b"
)
CONTENT_ANALYSIS_MEANING_PATTERN: Final = (
    r"\b(?:meaning of life|purpose|moral dilemmas?|mortality|existential|philosophy)\b"
)
CONTENT_ANALYSIS_CONNECTION_PATTERN: Final = (
    r"\b(?:friendship|family|families|belonging|relationships|empathy|marriage)\b"
)
CONTENT_ANALYSIS_CLARITY_PATTERN: Final = (
    r"\b(?:explains?|explanation|understanding|practical guide|step.by.step|how to)\b"
)
CONTENT_ANALYSIS_NEGATION_PATTERN: Final = (
    r"\b(?:no|not|never|without|neither|nor|isn['\u2019]t|doesn['\u2019]t|lack(?:s|ing)?)\b"
)
CONTENT_ANALYSIS_CLAUSE_PATTERN: Final = r"[.!?;:\n]"
CONTENT_ANALYSIS_HTML_PATTERN: Final = r"<[^>]*>"
CONTENT_ANALYSIS_SPACE_PATTERN: Final = r"\s+"
CONTENT_ANALYSIS_PUBLIC_URL_PATTERN: Final = (
    r"https://(?:(?:www\.)?goodreads\.com/book/show/\d+"
    r"|(?:www\.)?googleapis\.com/books/v1/volumes(?:/[^/?#]+)?"
    r"|books\.google\.com/books"
    r"|(?:www\.)?openlibrary\.org/(?:works/[^/?#]+|books/[^/?#]+|search\.json))"
    r"(?:[/?#]|$)"
)
CONTENT_ANALYSIS_LIMIT: Final = (
    "Counts explicit English catalog-description word-family matches, not inferred book facts "
    "or reader preferences. Multi-label families overlap; unmentioned is not absent. "
    "Public/publisher marketing may exaggerate content; these are not reviews."
    " Only the first 50,000 description characters are scanned; excerpts and proof counts "
    "are bounded and do not enumerate all supporting works."
)
CONTENT_ANALYSIS_HUNGER_LIMIT: Final = (
    "Read Your Color (https://readyourcolor.com/) uses a self-report assessment with six "
    "hungers and Heart/Head, Roots/Wings axes. These internal lexical rules reproduce no "
    "validated weights, colors or axes and infer no psychology, needs or appetite scores."
)
CONTENT_ANALYSIS_LANGUAGE_LIMIT: Final = (
    "English lexical rules only; a nearby negator in the preceding clause suppresses a "
    "match conservatively. This is not semantic negation, topic modeling or validated NLP."
)
CONTENT_ANALYSIS_SUPPORTED: Final = "Supported catalog mentions meet the distinct-work threshold."
CONTENT_ANALYSIS_THIN: Final = (
    "No word family meets minimum distinct-work support; no content signal is established."
)
CONTENT_ANALYSIS_UNKNOWN: Final = "Known public description evidence is insufficient."
CONTENT_ANALYSIS_TEST_TEXT: Final = (
    "A magical world of dragons. An unexpected plot twist brings suspense. "
    "Family friendship and belonging meet philosophy and purpose. "
    "A practical guide explains science and understanding."
)
CONTENT_ANALYSIS_TEST_NEGATED: Final = (
    "No magic or dragons here. Without suspense or peril. A familyless criminality."
)
CONTENT_ANALYSIS_TEST_UNMATCHED: Final = "A quiet catalog introduction."
CONTENT_ANALYSIS_TEST_URL: Final = "https://www.goodreads.com/book/show/123"
CONTENT_ANALYSIS_TEST_FILE_URL: Final = "file:///synthetic/reading.csv"
CONTENT_ANALYSIS_TEST_PRIVATE_URL: Final = (
    "https://www.goodreads.com/book/show/123?key=private-value#private-fragment"
)
CONTENT_ANALYSIS_TEST_REPEATED: Final = "Magic, magic, dragons, magical dragons."
CONTENT_ANALYSIS_TEST_UNVERIFIED: Final = "unverified_capture_genres"
CONTENT_ANALYSIS_TEST_GOOGLE_URL: Final = "https://www.googleapis.com/books/v1/volumes/test-volume"
CONTENT_ANALYSIS_TEST_OPEN_LIBRARY_URL: Final = "https://openlibrary.org/works/OL123W"
CONTENT_ANALYSIS_TEST_PROVIDER_PARAMETERS: Final = "source,url"

# AV: deterministic author-blocked retrospective validation.
AV_VALIDATION: Final = "read.validation.author_blocked"
AV_SIGNAL_CAPABILITY: Final = "read.validation.author_blocked_categorical_signal"
AV_STATE: Final = "evaluation_state"
AV_AVAILABLE: Final = "evaluated"
AV_SMALL: Final = "insufficient_known_author_rated_works"
AV_NO_TRAINING: Final = "no_author_disjoint_training"
AV_NO_SIGNAL: Final = "no_supported_categorical_signal"
AV_COMPONENTS: Final = "known_author_connected_components"
AV_LARGEST_COMPONENT: Final = "largest_component_works"
AV_KNOWN: Final = "known_author_rated_works"
AV_UNKNOWN: Final = "excluded_unknown_author_rated_works"
AV_NO_TRAINING_WORKS: Final = "works_without_author_disjoint_training"
AV_FOLDS: Final = "folds"
AV_FOLD: Final = "fold"
AV_TRAINING_WORKS: Final = "training_works"
AV_TRAINING_MEAN: Final = "training_only_rating_mean"
AV_MINIMUM_WORKS: Final = "minimum_known_author_rated_works"
AV_MAXIMUM_FOLDS: Final = "maximum_folds"
AV_STABILITY: Final = "paired_cluster_resampling_stability"
AV_STABILITY_RANGE: Final = "central_95_percent_resampled_mae_gain_range"
AV_LOWER: Final = "lower"
AV_UPPER: Final = "upper"
AV_DRAWS: Final = "draws"
AV_SEED: Final = "seed"
AV_MIN_COMPONENTS: Final = "minimum_evaluable_components"
AV_STABILITY_SMALL: Final = "insufficient_evaluable_components_or_works"
AV_NEED: Final = (
    "Need thirty linked rated Read works with known authors and two author-connected "
    "components. Categorical signal needs minimum group support in author-disjoint training."
)
AV_NOTE: Final = (
    "Deterministic retrospective grouped holdout, not temporal validation or future "
    "recommendation accuracy. Normalized known coauthors connect transitively; whole "
    "components are allocated largest-first to at most five size-balanced folds, "
    "breaking ties by work ID and fold index. Every evaluated work is held out once. "
    "Unknown-author works are excluded from both training and evaluation. Known names "
    "use whitespace/case normalization, not verified person identities or alias resolution. "
    "Training-only categorical means and baseline use the same held-out cohort; no signal "
    "falls back to that baseline. Settings are unchanged, with no tuning to observed errors. "
    "Series, metadata and other dependencies can remain across folds."
)
AV_STABILITY_NOTE: Final = (
    "Fixed-seed paired resampling of author components with replacement, preserving their "
    "observed paired losses and unequal work counts; each draw reports work-weighted "
    "baseline-minus-predictor MAE. The central 95% resampled range is descriptive stability "
    "of these fixed out-of-fold losses, not a population confidence interval: models are "
    "not refitted, fold training overlaps and components need not be independent. "
    "At least ten evaluable components, thirty evaluated works and categorical signal "
    "are required. Negative gains and ranges crossing zero are retained."
)
AV_TEST_AUTHOR_A: Final = " Shared Author "
AV_TEST_AUTHOR_A_NORMALIZED: Final = "shared author"
AV_TEST_AUTHOR_B: Final = "Second Author"
AV_TEST_AUTHOR_C: Final = "Third Author"
AV_TEST_BRIDGE: Final = "  SECOND   author "
AV_TEST_AUTHORS_FIELD: Final = "authors"
AV_LANGUAGE_SCOPE: Final = "required_observation_scope"
AV_LANGUAGE_INTERPRETATION: Final = "language_interpretation"
AV_MATCHED_EDITION_LANGUAGE: Final = (
    "Matched-edition language; not proof of the language actually read."
)
AV_WORK_LANGUAGE_AVAILABILITY: Final = (
    "Work-level catalog language availability across editions, not matched-edition language."
)
AV_TEST_SCOPE_PARAMETERS: Final = "field,scope,eligible"

# Durable provider transport reliability.
DR_RETRY_AT: Final = "retry_at"
DR_STATUS_CODE: Final = "status_code"
DR_HEADERS: Final = "headers"
DR_WIRE_ATTEMPTS: Final = "wire_attempts"
DR_FAILURES: Final = "failures"
DR_ERROR_CODE: Final = "error_code"
DR_HTTP_RETRYABLE: Final = "http_retryable"
DR_REQUEST_PENDING: Final = "request_pending"
DR_RETRY_SCHEMA: Final = (
    "CREATE TABLE IF NOT EXISTS metadata_retry_state "
    "(provider TEXT NOT NULL, host_key TEXT NOT NULL, payload TEXT NOT NULL, "
    "checksum TEXT NOT NULL, PRIMARY KEY(provider, host_key))"
)
DR_RETRY_SELECT: Final = (
    "SELECT payload, checksum FROM metadata_retry_state WHERE provider = ? AND host_key = ?"
)
DR_RETRY_INSERT: Final = (
    "INSERT INTO metadata_retry_state(provider, host_key, payload, checksum) VALUES (?, ?, ?, ?) "
    "ON CONFLICT(provider, host_key) DO UPDATE SET "
    "payload=excluded.payload, checksum=excluded.checksum"
)
DR_RETRY_READ_ERROR: Final = "Provider retry state could not be read safely."
DR_RETRY_WRITE_ERROR: Final = "Provider retry state could not be written safely."
DR_RETRY_CONFIG_ERROR: Final = "A retry-state store requires an explicit public metadata provider."
DR_COOLDOWN_MESSAGE: Final = "Provider host is deferred until UTC timestamp {deadline}."
DR_RAW_MIGRATE: Final = "ALTER TABLE raw_captures ADD COLUMN http_metadata TEXT"
DR_RAW_INSERT: Final = (
    "INSERT INTO raw_captures(sequence, id, source, account_id, media_type, origin, captured_at, "
    "sha256, collection, checksum, http_metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
DR_RAW_SELECT: Final = (
    "SELECT c.sequence, c.id, c.source, c.account_id, p.body, c.media_type, c.origin, "
    "c.captured_at, c.sha256, c.checksum, c.collection, c.http_metadata FROM raw_captures c "
    "LEFT JOIN raw_payloads p ON p.sha256 = c.sha256 "
)
DR_RAW_GET: Final = DR_RAW_SELECT + "WHERE c.id = ?"
DR_RAW_LATEST: Final = (
    DR_RAW_SELECT + "WHERE c.source = ? AND c.account_id = ? AND c.collection = ? "
    "ORDER BY c.sequence DESC LIMIT 1"
)
DR_RAW_LATEST_MEDIA: Final = (
    DR_RAW_SELECT + "WHERE c.source = ? AND c.account_id = ? AND c.collection = ? "
    "AND c.media_type = ? ORDER BY c.sequence DESC LIMIT 1"
)
DR_RAW_CHECK: Final = DR_RAW_SELECT + "LIMIT 0"
DR_TEST_RETRY_SECONDS: Final = "3600"
DR_TEST_RETRY_PARAMETERS: Final = "status,headers,delay"
DR_TEST_FAILURE: Final = "failure"
DR_TEST_BODY_ABORT: Final = "body_abort"
DR_TEST_BODY_LIMIT: Final = "body_limit"
DR_TEST_OTHER_HOST: Final = "other.invalid"
DR_TEST_OTHER_URL: Final = "https://other.invalid/books"
DR_TEST_DROP_METADATA: Final = "ALTER TABLE raw_captures DROP COLUMN http_metadata"
DR_TEST_TAMPER_METADATA: Final = "UPDATE raw_captures SET http_metadata = '{}'"
DR_TEST_TAMPER_RETRY: Final = (
    "UPDATE metadata_retry_state SET payload = replace(payload, '3600', '7200')"
)

# MQ: matching identity freshness.
MQ_IDENTITY_PARAMETERS: Final = "field,original_value,changed_value"

# Exact analytical genre-family vocabulary; provider observations remain unchanged.
ANALYTIC_CATEGORY_VERSION: Final = "genre-families-v2-catalog-paths"
ENR_CATALOG_KEYS: Final = (
    "SELECT cache_key FROM metadata_cache WHERE provider = ? ORDER BY cache_key"
)
ENR_CATALOG_KEY: Final = "local-catalog"
ENR_CATEGORY_PATH_SEPARATOR: Final = " / "
ENR_CATEGORY_FICTION_GENERAL: Final = "fiction / general"
ENR_CATEGORY_CHILDRENS_FICTION: Final = "children's fiction"
ENR_CATEGORY_JUVENILE_FICTION: Final = "juvenile fiction"
ENR_CATEGORY_YOUNG_ADULT_FICTION: Final = "young adult fiction"
ENR_CATEGORY_LOVE_STORIES: Final = "love stories"
ENR_CATEGORY_CONTEMPORARY_ROMANCE: Final = "fiction / romance / contemporary"
ENR_CATEGORY_HISTORICAL_GENERAL: Final = "fiction / historical / general"
ENR_CATEGORY_LITERARY_GENERAL: Final = "fiction / literary / general"
ENR_CATEGORY_TEST_PATH: Final = "Fiction, Fantasy, General"
ENR_CATEGORY_TEST_FALSE_PATH: Final = "Fiction, Imaginary Category, General"
ENR_TEST_SERIES_TITLE: Final = "Matilda (School, #1)"
ENR_DETAIL_DEFERRED: Final = "metadata_detail_deferred"
ENR_DETAIL_DEFERRED_MESSAGE: Final = (
    "Additional work details were deferred after the bounded catalog request allowance. "
    "Validated cached fields are retained; a later eligible sync can continue."
)
QUEUE_SAME_IDENTITY: Final = "queue_same_identity"
RD_METRIC: Final = "read.reader_summary"
COMMA_SPACE: Final = ", "
RD_WATCH_GENRES_KEY: Final = "watchlist_genres"
RD_FAMILIAR_KEY: Final = "watchlist_familiar_authors"
RD_NEW_KEY: Final = "watchlist_new_authors"
RD_UNKNOWN_AUTHORS_KEY: Final = "watchlist_unknown_authors"
RD_READ_EXAMPLES: Final = "A few books from your Read shelf, whether rated or not"
RD_BOOK_REFERENCE: Final = "{title} — {authors}"
RD_DUPLICATE: Final = "Reader summary requires unique confirmed works."
REC_TEST_PREVIOUS_ANALYSIS_VERSION: Final = "analytics-previous-test-version"
RD_SHORT: Final = "Under 200 pages"
RD_MEDIUM: Final = "200-399 pages"
RD_LONG: Final = "400 pages or more"
RD_GROUP_NOTE: Final = (
    "All Read works count toward your reading profile. Rating comparisons use only your "
    "linked, unconflicted StoryGraph ratings. Small groups are pulled toward your overall "
    "average; a pattern needs at least {minimum} ratings. Genre and author effects can overlap."
)
RD_TITLE: Final = "Your reading life"
RD_DECK: Final = "The books behind your taste. The possibilities on your shelf."
RD_COVER_NOTE: Final = (
    "A portrait of the library you supplied, not a personality test. Start with the patterns "
    "that have broad support; treat the thinner parts of the picture as open questions."
)
RD_AS_OF: Final = "Library snapshot · {date}"
RD_DATE_FORMAT: Final = "%d %B %Y"
RD_CONTENTS: Final = "Inside your reading life"
RD_COVER_COUNTS: Final = "{read:,} books read · {watch:,} waiting on your watchlist"
RD_COVER_RATING: Final = (
    "{rated:,} Read books have usable personal ratings from StoryGraph. "
    "Public Goodreads ratings appear only in separately labeled comparisons."
)
RD_COVER_HIGHLIGHT: Final = (
    "Your typical recorded book is {pages} pages. Your Read shelf spans {authors:,} named "
    "authors. Neither number depends on whether you rated the books."
)
RD_HIGHLIGHTS: Final = "A few things that make this shelf yours"
RD_REPEAT_CONTRAST: Final = (
    "Most read is not always most loved. You read {most_count} books by {most_author}; "
    "among authors with repeated ratings, {best_author} stands out "
    "({best_average}/5 across {best_count} ratings). This comparison allows for small "
    "samples rather than picking an author from one exceptional book."
)
RD_LENGTH_HIGHLIGHT: Final = (
    "Your strongest repeated length group is {label}: {count} ratings averaging "
    "{average}/5, against your overall {baseline}/5. That is a pattern in these books, "
    "not proof that length caused the difference."
)
RD_SECTION_SHAPE: Final = "The shape of your shelf"
RD_SECTION_GENRES: Final = "The worlds you spend time in"
RD_SECTION_RATINGS: Final = "What you have loved"
RD_SECTION_AUTHORS: Final = "The authors you return to"
RD_SECTION_PREFERENCES: Final = "What tends to work for you"
RD_SECTION_APPETITES: Final = "Your reading appetites"
RD_SECTION_TIME: Final = "Your reading through time"
RD_SECTION_WATCH: Final = "The possibilities ahead"
RD_SECTION_SHORTLIST: Final = "Ten possibilities to consider"
RD_SECTION_SHORTLIST_MORE: Final = "More from your shortlist"
RD_SECTION_COVERAGE: Final = "How much of the picture can we see?"
RD_SECTION_NOTES: Final = "A few things worth knowing"
RD_SHAPE_INTRO: Final = (
    "Your reading profile includes every completed book, not just the ones with ratings. "
    "Book length describes editions in the supplied data; it is not a measure of reading time."
)
RD_LENGTH_SUMMARY: Final = (
    "Page counts are available for {known:,} of {total:,} Read books. "
    "The middle recorded length is {pages} pages."
)
RD_GENRE_INTRO: Final = (
    "These are recognized genre families from identity-checked public catalogs. A book can "
    "belong to several families, so the bars are overlapping book counts, not slices of a pie."
)
RD_GENRE_COVERAGE: Final = (
    "We can describe genres for {known:,} of your {total:,} Read books ({percent}). "
    "The other {missing:,} are unknown here—not books without a genre."
)
RD_GENRE_CAUTION: Final = (
    "The biggest known category is not necessarily your favorite. Broad 'fiction' labels "
    "are less informative than a specific genre. Missing catalog data can change this picture."
)
RD_RATINGS_INTRO: Final = (
    "These are your current StoryGraph ratings, on a five-point scale. No Goodreads personal "
    "ratings or public community averages are used. Unrated and conflicting works stay out "
    "of rating calculations, but remain in your reading profile."
)
RD_RATING_SUMMARY: Final = (
    "{rated:,} of {total:,} Read books are rated without conflict ({percent}). "
    "Your average is {average}/5; the middle rating is {median}/5."
)
RD_FAVORITES: Final = "{count:,} books meet your {threshold}/5 high-rating threshold."
RD_FAVORITE_EXAMPLES: Final = "A few of your highly rated books"
RD_FAVORITES_NOTE: Final = (
    "Examples are ordered by your rating, then title. This is a sample of your high-rated "
    "shelf, not a claim that the first example is your single favorite."
)
RD_BOOK_RATING: Final = "{title} — {authors} · your rating: {rating}/5"
RD_AUTHORS_INTRO: Final = (
    "Returning to an author shows reading investment. Enjoyment is a separate question, "
    "so the table keeps books read and books rated alongside your average."
)
RD_AUTHOR_CONCENTRATION: Final = (
    "Your most-read named author accounts for {count:,} of {total:,} Read books. "
    "Several books in one series or by one author are related experiences, not independent votes."
)
RD_PREFERENCES_INTRO: Final = (
    "Where do your ratings run above your usual level? These comparisons are descriptive, "
    "not forecasts. They can reflect author or series overlap as well as the named category."
)
RD_BASELINE: Final = "Your comparison point is {average}/5 across {rated:,} rated Read books."
RD_SIGNAL: Final = (
    "{label}: {count} ratings, average {average}/5; cautious comparison {adjusted}/5 "
    "({difference} against your overall average)."
)
RD_NO_SIGNAL: Final = (
    "There is not enough repeated, rated evidence to make a useful comparison here. "
    "We would rather leave this open than turn one or two books into a preference."
)
RD_APPETITE_INTRO: Final = (
    "Inspired by reading-appetite ideas: wonder, surprise, intensity, meaning, connection "
    "and clarity. These describe what public book descriptions explicitly mention. "
    "They are not official colors, psychological traits or a replacement for your own labels. "
    "A group's current rating average is descriptive, not proof of preference."
)
RD_APPETITE_SUPPORT: Final = "{label} · explicit description evidence in {count} Read books"
RD_APPETITE_ABSENT: Final = (
    "{label} · not enough supported description evidence. This does not mean you dislike it."
)
RD_APPETITE_RATING: Final = "Your current average: {average}/5 across {count} linked ratings."
RD_QUOTE: Final = "From {title}: “{quote}”"
RD_PROOF_LINK: Final = "Public description source"
RD_TIME_INTRO: Final = (
    "This timeline uses actual supplied completion dates only. Goodreads dates take precedence; "
    "confirmed StoryGraph completion dates can fill a gap and remain separately attributed."
)
RD_TIME_COVERAGE: Final = (
    "Usable completion dates cover {known:,} of {total:,} Read books. Undated books are not "
    "assigned a year. A short or incomplete current year is not evidence that you read less."
)
RD_TIME_NOTE: Final = (
    "These counts describe the dated subset, not a complete annual reading record. Ratings "
    "attached to older reading years are today's ratings, not historical rating snapshots. "
    "Publication dates and library-addition dates are not completion dates."
)
RD_WATCH_INTRO: Final = (
    "Your watchlist is a set of possibilities, not a task list. Familiar authors and "
    "unfamiliar authors offer different kinds of exploration; neither is automatically better."
)
RD_WATCH_SUMMARY: Final = (
    "{familiar:,} watchlist books include an author on your Read shelf; {new:,} have named "
    "authors not on that shelf. Author information is missing for {unknown:,}."
)
RD_RECOMMENDATION_COUNTS: Final = (
    "{ranked:,} watchlist books have enough evidence to order. "
    "{unknown:,} remain without a score; {excluded:,} are excluded by eligibility checks. "
    "Missing information is not a negative review."
)
RD_SHORTLIST_INTRO: Final = (
    "A varied starting point from your own watchlist, based on your StoryGraph ratings and "
    "shared, verified book features. The ordering is a heuristic—not a probability of enjoyment. "
    "Only your ten-item shortlist is shown; the full ranking stays in recommendations.json."
)
RD_REC_TITLE: Final = "{rank:02d} · {title}"
RD_REC_SIGNAL: Final = "Shared {feature}: {label} · {count} supporting rated books"
RD_REC_CAUTION: Final = "Some shared features also occur in books you rated lower."
RD_REC_MISSING: Final = (
    "Some supporting information is still missing. A good-looking match is not a complete picture."
)
RD_REC_EXAMPLE: Final = "A connection on your Read shelf: {title} ({rating}/5)."
RD_COVERAGE_INTRO: Final = (
    "There is no single honest 'coverage score'. Different questions need different facts. "
    "This table shows what is available, so you can judge each conclusion on its actual support."
)
RD_COVERAGE_VALUE: Final = "{known:,}/{total:,} · {percent}"
RD_PERCENT: Final = "{value:.0%}"
RD_NUMBER: Final = "{value:.2f}"
RD_DIFFERENCE: Final = "{value:+.2f}"
RD_COVERAGE_GAP: Final = (
    "The weakest parts of this picture are {fields}. More API retries cannot guarantee "
    "these facts exist or identify the edition you actually read."
)
RD_QUALITY_NOTICE: Final = (
    "The automatic quality audit also found consistency issues. Full counts and explanations "
    "are retained in metadata-quality.json; coverage alone does not establish correctness."
)
RD_NOTES: Final = (
    "This report is deliberately selective. analytics.json retains all calculated results, "
    "recommendations.json retains every ranking and abstention, and metadata-quality.json "
    "retains detailed completeness and consistency evidence. They belong to the same saved run."
)
RD_SOURCES_NOTE: Final = (
    "Goodreads supplies your Read/watchlist membership and supported reading history. "
    "StoryGraph supplies your personal ratings and separately attributed completion dates. "
    "Public catalogs supply identity-checked book facts. A complete CSV import does not prove "
    "that an account export is complete."
)
RD_VALIDATION_NOTE: Final = (
    "Historical prediction checks have not established reliable future enjoyment accuracy. "
    "The shortlist is an explainable discovery aid, not a validated recommendation model."
)
RD_MISSING_NOTE: Final = (
    "Unknown does not mean zero, dislike or absence. An available translation does not tell "
    "us which language you read. Work-level first publication is not an edition's publication date."
)
RD_HEADER_CATEGORY: Final = "Reading pattern"
RD_HEADER_READ: Final = "Books read"
RD_HEADER_RATED: Final = "Books rated"
RD_HEADER_AVERAGE: Final = "Your average /5"
RD_HEADER_YEAR: Final = "Completion year"
RD_HEADER_GR_DATES: Final = "Goodreads dates"
RD_HEADER_SG_DATES: Final = "StoryGraph dates"
RD_HEADER_FIELD: Final = "What we know"
RD_HEADER_WATCH: Final = "Watchlist"
RD_AUTHOR: Final = "author"
RD_GENRE: Final = "genre"
RD_APPETITE: Final = "reading appetite"
RD_PUBLICATION: Final = "First-publication year"
RD_DESCRIPTION: Final = "Public description"
RD_GENRES: Final = "Recognized genre family"
RD_LANGUAGE: Final = "Edition language"
RD_PAGES: Final = "Page count"
RD_SERIES: Final = "Verified series"
RD_SECTION_CROWD: Final = "You and the crowd"
RD_CROWD_INTRO: Final = (
    "Your StoryGraph rating and the public Goodreads average answer different questions. "
    "Their difference can reveal interesting disagreements; it does not make either side "
    "right. These comparisons do not supply your personal ratings or drive the shortlist."
)
RD_CROWD_SUMMARY: Final = (
    "{count:,} Read books have both scores. On this matched subset, your rating is "
    "{difference} stars relative to the Goodreads average."
)
RD_CROWD_HIGHER: Final = "You rated these higher"
RD_CROWD_LOWER: Final = "You rated these lower"
RD_CROWD_ITEM: Final = (
    "{title} · you {personal}/5 · Goodreads {community}/5 · difference {difference}"
)
RD_CROWD_COUNT: Final = "Public Goodreads rating count: {count:,}."
RD_CROWD_UNKNOWN_COUNT: Final = "The public rating sample size is unavailable."
RD_CROWD_NOTE: Final = (
    "Public averages describe different readers, and their counts vary. The examples below "
    "are observed differences, not statistical outliers or proof of unusually discerning taste."
)
RD_RATING_VOCABULARY: Final = (
    "Your most-used rating is {rating}/5: {count:,} books ({percent} of your rated shelf). "
    "That is useful context when a small difference between groups looks dramatic."
)
RD_READ_VS_WATCH: Final = "Your known Read shelf and your known watchlist"
RD_WATCH_GENRE_NOTE: Final = (
    "Counts overlap across genres. A category missing from the known Read subset is not "
    "proof that you have never tried it."
)
RD_HEADER_COMMUNITY: Final = "Goodreads average"
RD_HEADER_SUPPORT: Final = "Supporting ratings"
RD_MAX_PDF_PAGES: Final = "The reader report exceeded its page budget."
ANALYTIC_CATEGORY_FIELD: Final = "analytical_genres"
ANALYTIC_CATEGORY_FICTION: Final = "fiction"
ANALYTIC_CATEGORY_NONFICTION: Final = "nonfiction"
ANALYTIC_CATEGORY_NON_FICTION: Final = "non-fiction"
ANALYTIC_CATEGORY_NON_FICTION_SPACED: Final = "non fiction"
ANALYTIC_CATEGORY_FANTASY: Final = "fantasy"
ANALYTIC_CATEGORY_FANTASY_FICTION: Final = "fantasy fiction"
ANALYTIC_CATEGORY_EPIC_FANTASY: Final = "epic fantasy"
ANALYTIC_CATEGORY_HIGH_FANTASY: Final = "high fantasy"
ANALYTIC_CATEGORY_URBAN_FANTASY: Final = "urban fantasy"
ANALYTIC_CATEGORY_DARK_FANTASY: Final = "dark fantasy"
ANALYTIC_CATEGORY_FICTION_FANTASY: Final = "fiction / fantasy / general"
ANALYTIC_CATEGORY_FICTION_EPIC_FANTASY: Final = "fiction / fantasy / epic"
ANALYTIC_CATEGORY_SCIENCE_FICTION: Final = "science fiction"
ANALYTIC_CATEGORY_SCI_FI: Final = "sci-fi"
ANALYTIC_CATEGORY_SCI_FI_SPACED: Final = "sci fi"
ANALYTIC_CATEGORY_SPACE_OPERA: Final = "space opera"
ANALYTIC_CATEGORY_CYBERPUNK: Final = "cyberpunk"
ANALYTIC_CATEGORY_FICTION_SCIENCE_FICTION: Final = "fiction / science fiction / general"
ANALYTIC_CATEGORY_MYSTERY: Final = "mystery"
ANALYTIC_CATEGORY_MYSTERY_FICTION: Final = "mystery fiction"
ANALYTIC_CATEGORY_DETECTIVE_MYSTERY: Final = "detective and mystery stories"
ANALYTIC_CATEGORY_MYSTERIES: Final = "mysteries"
ANALYTIC_CATEGORY_DETECTIVE_FICTION: Final = "detective fiction"
ANALYTIC_CATEGORY_MYSTERY_DETECTIVE: Final = "mystery and detective stories"
ANALYTIC_CATEGORY_FICTION_MYSTERY: Final = "fiction / mystery & detective / general"
ANALYTIC_CATEGORY_CRIME: Final = "crime fiction"
ANALYTIC_CATEGORY_THRILLER: Final = "thriller"
ANALYTIC_CATEGORY_THRILLERS: Final = "thrillers"
ANALYTIC_CATEGORY_SUSPENSE_FICTION: Final = "suspense fiction"
ANALYTIC_CATEGORY_PSYCHOLOGICAL_THRILLER: Final = "psychological thriller"
ANALYTIC_CATEGORY_FICTION_THRILLER: Final = "fiction / thrillers / general"
ANALYTIC_CATEGORY_HORROR: Final = "horror"
ANALYTIC_CATEGORY_HORROR_FICTION: Final = "horror fiction"
ANALYTIC_CATEGORY_HORROR_TALES: Final = "horror tales"
ANALYTIC_CATEGORY_FICTION_HORROR: Final = "fiction / horror"
ANALYTIC_CATEGORY_ROMANCE: Final = "romance"
ANALYTIC_CATEGORY_ROMANCE_FICTION: Final = "romance fiction"
ANALYTIC_CATEGORY_ROMANTIC_FICTION: Final = "romantic fiction"
ANALYTIC_CATEGORY_CONTEMPORARY_ROMANCE: Final = "contemporary romance"
ANALYTIC_CATEGORY_HISTORICAL_ROMANCE: Final = "historical romance"
ANALYTIC_CATEGORY_PARANORMAL_ROMANCE: Final = "paranormal romance"
ANALYTIC_CATEGORY_FICTION_ROMANCE: Final = "fiction / romance / general"
ANALYTIC_CATEGORY_HISTORICAL_FICTION: Final = "historical fiction"
ANALYTIC_CATEGORY_FICTION_HISTORICAL: Final = "fiction / historical / general"
ANALYTIC_CATEGORY_LITERARY_FICTION: Final = "literary fiction"
ANALYTIC_CATEGORY_FICTION_LITERARY: Final = "fiction / literary"
ANALYTIC_CATEGORY_SHORT_STORIES: Final = "short stories"
ANALYTIC_CATEGORY_SHORT_FICTION: Final = "short fiction"
ANALYTIC_CATEGORY_FICTION_SHORT_STORIES: Final = "fiction / short stories (single author)"
ANALYTIC_CATEGORY_POETRY: Final = "poetry"
ANALYTIC_CATEGORY_DRAMA: Final = "drama"
ANALYTIC_CATEGORY_PLAYS: Final = "plays"
ANALYTIC_CATEGORY_COMICS: Final = "comics and graphic novels"
ANALYTIC_CATEGORY_GRAPHIC_NOVELS: Final = "graphic novels"
ANALYTIC_CATEGORY_COMIC_BOOKS: Final = "comic books"
ANALYTIC_CATEGORY_MANGA: Final = "manga"
ANALYTIC_CATEGORY_BIOGRAPHY: Final = "biography"
ANALYTIC_CATEGORY_BIOGRAPHIES: Final = "biographies"
ANALYTIC_CATEGORY_BIOGRAPHY_AUTOBIOGRAPHY: Final = "biography & autobiography / general"
ANALYTIC_CATEGORY_MEMOIR: Final = "memoir"
ANALYTIC_CATEGORY_MEMOIRS: Final = "memoirs"
ANALYTIC_CATEGORY_AUTOBIOGRAPHY: Final = "autobiography"
ANALYTIC_CATEGORY_AUTOBIOGRAPHIES: Final = "autobiographies"
ANALYTIC_CATEGORY_HISTORY: Final = "history"
ANALYTIC_CATEGORY_HISTORY_GENERAL: Final = "history / general"
ANALYTIC_CATEGORY_SCIENCE: Final = "science"
ANALYTIC_CATEGORY_SCIENCE_GENERAL: Final = "science / general"
ANALYTIC_CATEGORY_PHILOSOPHY: Final = "philosophy"
ANALYTIC_CATEGORY_PHILOSOPHY_GENERAL: Final = "philosophy / general"
ANALYTIC_CATEGORY_PSYCHOLOGY: Final = "psychology"
ANALYTIC_CATEGORY_PSYCHOLOGY_GENERAL: Final = "psychology / general"
ANALYTIC_CATEGORY_ESSAYS: Final = "essays"
ANALYTIC_CATEGORY_TRUE_CRIME: Final = "true crime"
ANALYTIC_CATEGORY_SELF_HELP: Final = "self-help"
ANALYTIC_CATEGORY_SELF_HELP_SPACED: Final = "self help"
ANALYTIC_CATEGORY_SELF_HELP_GENERAL: Final = "self-help / general"
ANALYTIC_CATEGORY_TRAVEL: Final = "travel writing"
ANALYTIC_CATEGORY_TEST_PARAMETERS: Final = "labels,expected"
ANALYTIC_CATEGORY_TEST_BESTSELLER: Final = "New York Times bestseller"
ANALYTIC_CATEGORY_TEST_LARGE_PRINT: Final = "Large type books"
ANALYTIC_CATEGORY_TEST_CLASSIFICATION: Final = "FIC009020"
ANALYTIC_CATEGORY_TEST_DDC: Final = "823.914"
ANALYTIC_CATEGORY_TEST_LCC: Final = "PR6068.O93"
ANALYTIC_CATEGORY_TEST_CATALOG_TAG: Final = "accessible book"
ANALYTIC_CATEGORY_TEST_SUBSTRING: Final = "fantasy football"
ANALYTIC_CATEGORY_TEST_SPACING: Final = "  SCIENCE   FICTION  "

QUEUE_ELIGIBLE_ATTEMPTS_SQL: Final = (
    "SELECT r.latest_json, a.raw_json, a.checked_at, "
    "(a.identity_hash = r.identity_hash) AS queue_same_identity, "
    "(a.id IS NULL OR a.identity_hash != r.identity_hash "
    "OR a.implementation_version != ?) AS queue_invalidated "
    "FROM source_records r LEFT JOIN enrichment_attempts a ON a.id = "
    "(SELECT MAX(a2.id) FROM enrichment_attempts a2 "
    "WHERE a2.record_id = r.id AND a2.provider = ?) "
    "WHERE EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = r.id) "
    "AND (a.id IS NULL OR a.identity_hash != r.identity_hash "
    "OR a.implementation_version != ? OR "
    "(a.state != ? AND julianday(a.checked_at) <= julianday(?))) "
    "ORDER BY (a.id IS NOT NULL), a.checked_at, a.id, "
    "r.source, r.account_id, r.source_id"
)
QUEUE_INVALIDATED: Final = "queue_invalidated"
QUEUE_TEST_ATTEMPT_OLD_TIMESTAMP: Final = (
    "UPDATE enrichment_attempts SET checked_at = '2020-01-01T00:00:00+00:00'"
)
QUEUE_TEST_FIXED_TIME: Final = "2026-01-01T00:00:00+00:00"
QUEUE_TEST_BEFORE_RETRY: Final = "2026-01-01T05:59:59+00:00"
QUEUE_TEST_RETRY_DUE: Final = "2026-01-01T06:00:00+00:00"
QUEUE_LEGACY_MAX_AGE_DESCRIPTION: Final = (
    "Accepted for legacy configuration compatibility; elapsed age does not enqueue metadata."
)
QUEUE_LEGACY_MAX_AGE_KEY: Final = "max_age_days"
QUEUE_GOOGLE_ERROR_DETAILS: Final = "details"
QUEUE_GOOGLE_QUOTA_UNIT: Final = "quota_unit"
QUEUE_GOOGLE_DETAIL_TYPE: Final = "@type"
QUEUE_GOOGLE_ERROR_INFO: Final = "type.googleapis.com/google.rpc.ErrorInfo"
QUEUE_GOOGLE_DAILY_UNIT_PREFIX: Final = "1/d/"
QUEUE_GOOGLE_DAILY_FIXTURE: Final = "google_daily_quota.json"
QUEUE_GOOGLE_LEGACY_DAILY_FIXTURE: Final = "google_legacy_daily_quota.json"
QUEUE_GOOGLE_UNKNOWN_QUOTA_FIXTURE: Final = "google_unknown_quota.json"
QUEUE_DAILY_TEST_PARAMETERS: Final = "fixture_name,status,retry_header,expected_delay"
QUEUE_DAILY_SCOPE_TEST_PARAMETERS: Final = "fixture_name,status,provider,host,url"
QUEUE_DAILY_LONG_RETRY_HEADER: Final = "86400"
QUEUE_INCOMPLETE: Final = "incomplete"
QUEUE_ATTEMPT_STATES: Final = "attempt_states"
QUEUE_NO_LOOKUPS_DUE_CODE: Final = "metadata_coverage_incomplete"
QUEUE_NO_LOOKUPS_DUE_MESSAGE: Final = (
    "No new lookups are due; {count} active latest metadata attempts remain incomplete "
    "or have unresolved candidates. Saved partial fields and failure evidence are retained."
)
QUEUE_STATUS_ATTEMPTS_SQL: Final = (
    "SELECT COUNT(*) AS total, MAX(a.checked_at) AS last_attempt_at "
    "FROM enrichment_attempts a WHERE a.provider = ? AND EXISTS "
    "(SELECT 1 FROM memberships m WHERE m.record_id = a.record_id)"
)
QUEUE_STATUS_CANDIDATES_SQL: Final = (
    "SELECT COUNT(*) FROM enrichment_candidates c "
    "JOIN enrichment_attempts a ON a.id = c.attempt_id "
    "WHERE a.provider = ? AND EXISTS "
    "(SELECT 1 FROM memberships m WHERE m.record_id = a.record_id)"
)
QUEUE_STATUS_LATEST_STATES_SQL: Final = (
    "SELECT a.state, COUNT(*) AS total, SUM(a.state != ? OR "
    "(EXISTS (SELECT 1 FROM enrichment_candidates c WHERE c.attempt_id = a.id) "
    "AND NOT EXISTS (SELECT 1 FROM enrichment_candidates c "
    "WHERE c.attempt_id = a.id AND c.selected = 1))) AS incomplete "
    "FROM enrichment_attempts a WHERE a.provider = ? "
    "AND a.id = (SELECT MAX(n.id) FROM enrichment_attempts n "
    "WHERE n.record_id = a.record_id AND n.provider = a.provider) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = a.record_id) "
    "GROUP BY a.state"
)
QUEUE_STATUS_UNRESOLVED_SQL: Final = (
    "SELECT COUNT(*) FROM enrichment_attempts a WHERE a.provider = ? "
    "AND a.id = (SELECT MAX(n.id) FROM enrichment_attempts n "
    "WHERE n.record_id = a.record_id AND n.provider = a.provider) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = a.record_id) "
    "AND (a.state != ? OR NOT EXISTS "
    "(SELECT 1 FROM enrichment_candidates c WHERE c.attempt_id = a.id AND c.selected = 1))"
)

# ANX: positive-only catalog appetite evidence and associations.
ANX_VERSION: Final = "catalog-appetite-associations-v2"
ANX_FEATURE: Final = "catalog_appetite_mentions"
ANX_ENJOYMENT: Final = "content.appetite.enjoyment.read.{dimension}"
ANX_EXPOSURE: Final = "content.appetite.exposure.read"
ANX_AVAILABILITY: Final = "content.appetite.rating_availability.read"
ANX_VALIDATION: Final = "content.appetite.validation.author_blocked"
ANX_VALIDATION_SIGNAL: Final = "content.appetite.validation.author_blocked_signal"
ANX_READ_MEMBERSHIP: Final = "analytical_read_membership"
ANX_POLICY: Final = "catalog_appetite_policy"
ANX_POSITIVE: Final = "positive_mention_works"
ANX_UNMATCHED: Final = "verified_descriptions_without_appetite_evidence"
ANX_UNKNOWN: Final = "missing_or_unverified_descriptions"
ANX_ASSOCIATION: Final = "association"
ANX_BASELINE: Final = "positive_evidence_cohort_rating_mean"
ANX_DIFFERENCE: Final = "shrunk_difference_from_positive_cohort"
ANX_INDEPENDENT: Final = "rated_author_connected_components"
ANX_NOTE: Final = (
    "Internal English catalog-description rules supply positive content-mention evidence, "
    "not reader appetite, personality, colors or official assessment scores. Unmatched or "
    "unverified descriptions are unknown, never negative examples. Exposure uses all Read "
    "works independently of ratings; multi-label shares overlap. Enjoyment associations "
    "and baselines use only the positive-evidence rated cohort, not unmatched books. "
    "Current ratings are observational associations, not causal effects or predictions "
    "of future recommendations. Explicit user labels and declared preferences stay separate."
)
ANX_SUPPORT_NOTE: Final = (
    "Enjoyment requires minimum rated-work support, known authors, multiple connected "
    "author components and no dominant author; otherwise association remains unavailable."
)
ANX_TEST_CONNECTION: Final = "A story of friendship and belonging."
ANX_TEST_INTENSITY: Final = "A suspenseful story with high stakes."
ANX_TEST_UNMATCHED: Final = "A quiet journey through ordinary days."
ANX_FEATURES: Final = "features"
ANX_UNCERTAINTY: Final = "uncertainty"
ANX_LIMITATIONS: Final = "limitations"
ANX_ADDITION_DATES: Final = "library_addition_dates"
ANX_LIBRARY_ADDITIONS: Final = "{collection}.library_addition_profile"
ANX_COMPLETION_COHORTS: Final = "read.completion_date_cohorts"
ANX_COHORTS: Final = "date_year_cohorts"
ANX_DATE_PRECISIONS: Final = "date_precisions"
ANX_AGE_SUMMARY: Final = "day_precision_library_age_days"
ANX_FUTURE_DATES: Final = "excluded_future_dates"
ANX_INVALID_AS_OF: Final = "as_of_date_unavailable"
ANX_DATE_ORIGIN: Final = "completion_date_origin"
ANX_AUTHORITATIVE_DATE: Final = "goodreads_authoritative"
ANX_SUPPLEMENTAL_DATE: Final = "storygraph_supplemental"
ANX_SELECTED_DATES: Final = "selected_completion_dates"
ANX_CONFLICTING_DATES: Final = "conflicting_supplemental_completion_dates"
ANX_CURRENT_RATINGS: Final = "current_ratings_by_completion_date_cohort"
ANX_SUPPLEMENTAL_STATES: Final = "supplemental_observation_states"
ANX_ADDITION_NOTE: Final = (
    "Goodreads library-addition dates describe when a book was added to the library, "
    "not reading dates or guaranteed entry into its current shelf. Day-precision dates "
    "alone support library age; partial dates remain in precision/year composition. "
    "Future dates are excluded. This is snapshot composition, not an annual review."
)
ANX_COMPLETION_NOTE: Final = (
    "One distinct work contributes once, using its earliest supplied authoritative "
    "Goodreads completion when present, preserving precision. Only without any such "
    "completion may a consistent explicit StoryGraph completion supply a supplemental "
    "date; conflicting supplemental values remain unavailable. This never changes "
    "Goodreads reading events or status and does not prove first reading or complete "
    "history. Cohort ratings are current ratings grouped by the selected completion "
    "year, not historical ratings. Sources, precision, exclusions and evidence remain "
    "separate; small rated cohorts have no rating summary. Stable field/event proof is "
    "stored with the finding; current capture and immutable CSV lineage are supplied by "
    "the report manifest and rebound source snapshot IDs, not copied capture timestamps."
)
ANX_TEST_EARLIER_DATE: Final = "2023-02-01"
ANX_TEST_LATER_DATE: Final = "2024-02-01"
ANX_TEST_AS_OF: Final = "2025-01-01T00:00:00+00:00"
ANX_TEST_FUTURE_DATE: Final = "2026-02-01"
ANX_SOURCE_URL: Final = "source_url"
ANX_COMPLETION_COUNTS: Final = "source_scope_completion_date_states"
ANX_MATCHED_DATES: Final = "matched_present_supplemental_date_records"
ANX_PRECEDENCE: Final = "goodreads_completion_precedence_works"

ENR_OPEN_LIBRARY_SEARCH_FIELDS: Final = (
    "key,title,author_name,isbn,subject,language,number_of_pages_median,"
    "first_publish_year,ratings_average,ratings_count,series_name,series_position"
)
ENR_ALLOW_EXPIRED_PARAMETER: Final = "allow_expired"
ENR_STREAM_FAILURE_PARAMETER: Final = "cooldown"

DTX_SUPPLEMENTAL_COMPLETION_DATE: Final = "supplemental_completion_date"
DTX_SUPPLEMENTAL_COMPLETION_DATES: Final = "supplemental_completion_dates"
DTX_INVALID_COMPLETION_CODE: Final = "storygraph_completion_date_invalid"
DTX_INVALID_COMPLETION_MESSAGE: Final = (
    "Export record {row}: {field} is not a supported date. The original value remains raw; "
    "its supplemental completion date is unavailable."
)
DTX_INVALID_SUPPLEMENTAL_MODEL: Final = (
    "Supplemental completion dates require matching reader-scoped StoryGraph date evidence."
)
DTX_SUPPLEMENTAL_LINEAGE: Final = (
    "Supplemental StoryGraph Last Date Read; never replaces Goodreads reading history."
)
DTX_TEST_DATE_PARAMETERS: Final = "value,state,precision"
DTX_TEST_DAY: Final = "2024-02-29"
DTX_TEST_MONTH: Final = "2024-02"
DTX_TEST_YEAR: Final = "2024"
DTX_TEST_INVALID_DATE: Final = "2023-02-29"
DTX_TEST_UNKNOWN_DATE: Final = "unknown"
DTX_TEST_OTHER_DATE: Final = "2023-12-31"
DTX_OBSERVATION: Final = "observation"
DTX_SCOPE: Final = "scope"
DTX_SOURCE_COMPLETION_DATES_PRESENT: Final = "storygraph.read_scope_completion_dates.present"
DTX_SOURCE_COMPLETION_DATES_EMPTY: Final = "storygraph.read_scope_completion_dates.empty"
DTX_SOURCE_COMPLETION_DATES_UNSUPPORTED: Final = (
    "storygraph.read_scope_completion_dates.unsupported"
)
DTX_SOURCE_COMPLETION_DATES_UNAVAILABLE: Final = (
    "storygraph.read_scope_completion_dates.unavailable"
)

type MetadataStrategy = Literal["open_library_first", "independent"]
ENR_STRATEGY_OPEN_LIBRARY_FIRST: Final = "open_library_first"
ENR_STRATEGY_INDEPENDENT: Final = "independent"
ENR_STRATEGY: Final = "strategy"
ENR_FALLBACK_SKIPPED: Final = "fallback_skipped"
ENR_FALLBACK_FIELDS: Final = "fallback_fields"
ENR_OBSERVATION_SCOPE: Final = "scope"
ENR_STRATEGY_TEST_PARAMETERS: Final = "strategy,stale"
ENR_FALLBACK_UNRESOLVED: Final = "fallback_unresolved"
ENR_GAPS_REMAIN_CODE: Final = "fallback_fields_unresolved"
ENR_GAPS_REMAIN_MESSAGE: Final = (
    "{count} active source records still lack selected identity-valid public descriptions "
    "or recognized genre families; fallback completion does not prove full provider coverage."
)
ENR_SKIPPED_BY_STRATEGY: Final = "skipped_by_strategy"
ENR_COVERAGE_SCOPE: Final = "coverage_scope"
ENR_LOOKUP_COVERAGE_SCOPE: Final = "provider_lookup_outcomes"
ENR_CORE_COVERAGE_SCOPE: Final = "bounded_core_fields"
ENR_SELECTED_WORK_METADATA_SQL: Final = (
    "SELECT r.latest_json, e.provider, c.candidate_json FROM source_records t "
    "JOIN source_records r ON r.work_id = t.work_id "
    "JOIN enrichment_active e ON e.record_id = r.id "
    "JOIN enrichment_attempts a ON a.id = e.attempt_id "
    "JOIN enrichment_candidates c ON c.id = e.candidate_id "
    "WHERE t.source = ? AND t.account_id = ? AND t.source_id = ? "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = t.id) "
    "AND EXISTS (SELECT 1 FROM memberships m WHERE m.record_id = r.id) "
    "AND a.identity_hash = r.identity_hash AND c.selected = 1 "
    "ORDER BY r.id, e.provider"
)
ENR_SETUP_ISSUE_PARAMETER: Final = "setup_issue"

PDF_INVALID_REPORT: Final = "PDF reporting requires a structured saved report."
PDF_PIN_MISMATCH: Final = "PDF inputs must share the saved analytics manifest, report ID and as-of."
PDF_INVALID_ARTIFACT: Final = "PDF generation did not produce a complete document."
PDF_STAGING_NAME: Final = ".{name}.{token}.staging"
PDF_EXCLUSIVE_BINARY: Final = "xb"
PDF_MAGIC: Final = b"%PDF-"
PDF_KEY_AS_OF: Final = "as_of"
PDF_KEY_MANIFEST: Final = "manifest"
PDF_KEY_ANALYSIS_ID: Final = "analysis_report_id"
PDF_KEY_RANKED: Final = "ranked"
PDF_KEY_UNRANKABLE: Final = "unrankable"
PDF_KEY_EXCLUDED: Final = "excluded"
PDF_KEY_SHORTLIST: Final = "shortlist"
PDF_KEY_SCORE: Final = "ranking_score"
PDF_KEY_SUPPORTING: Final = "supporting_books"
PDF_KEY_IDENTITY_TIER: Final = "identity_tier"
PDF_KEY_FEATURE_TIER: Final = "feature_tier"
PDF_KEY_PREFERENCE_TIER: Final = "preference_tier"
PDF_KEY_LIMITATIONS: Final = "limitations"
PDF_KEY_COVERAGE: Final = "coverage"
PDF_KEY_SCOPE: Final = "scope"
PDF_KEY_POPULATION: Final = "population"
PDF_KEY_AVAILABLE: Final = "available"
PDF_KEY_MISSING: Final = "missing"
PDF_KEY_STATES: Final = "states"
PDF_KEY_IDENTITY: Final = "identity"
PDF_KEY_DIAGNOSTICS: Final = "diagnostics"
PDF_KEY_COUNT: Final = "count"
PDF_KEY_PROVIDER_STATUS: Final = "provider_status"
PDF_KEY_POLICY: Final = "policy_version"
PDF_KEY_SCHEMA: Final = "schema_version"
PDF_KEY_REASONS: Final = "reasons"
PDF_KEY_MISMATCHES: Final = "mismatches"
PDF_KEY_MISSINGNESS: Final = "missingness"
PDF_FONT: Final = "BookyNoto"
PDF_FONT_BOLD: Final = "BookyNotoBold"
PDF_FONT_DEVANAGARI: Final = "BookyNotoDevanagari"
PDF_FONT_CJK: Final = "BookyNotoCJK"
PDF_FONT_REGULAR_FILE: Final = "NotoSans-Regular.ttf"
PDF_FONT_BOLD_FILE: Final = "NotoSans-Bold.ttf"
PDF_FONT_DEVANAGARI_FILE: Final = "NotoSansDevanagari-Regular.ttf"
PDF_FONT_CJK_FILE: Final = "NotoSansSC-VF.ttf"
PDF_FONT_SPAN: Final = '<font name="{font}">{text}</font>'
PDF_UNSUPPORTED_GLYPH: Final = "[U+{code:04X}]"
PDF_FONTS_FOLDER: Final = "fonts"
PDF_STYLE_TITLE: Final = "pdf-title"
PDF_STYLE_KICKER: Final = "pdf-kicker"
PDF_STYLE_DECK: Final = "pdf-deck"
PDF_STYLE_H1: Final = "pdf-section"
PDF_STYLE_H2: Final = "pdf-heading"
PDF_STYLE_H3: Final = "pdf-subheading"
PDF_STYLE_BODY: Final = "pdf-body"
PDF_STYLE_NOTE: Final = "pdf-note"
PDF_STYLE_CELL: Final = "pdf-cell"
PDF_STYLE_TABLE_HEAD: Final = "pdf-table-head"
PDF_STYLE_TOC: Final = "pdf-toc"
PDF_INK: Final = "#172B3A"
PDF_NAVY: Final = "#183749"
PDF_TEAL: Final = "#188B86"
PDF_PALE: Final = "#F0F6F6"
PDF_MUTED: Final = "#536B78"
PDF_BACKGROUND: Final = "BACKGROUND"
PDF_TEXT_COLOR: Final = "TEXTCOLOR"
PDF_VALIGN: Final = "VALIGN"
PDF_TOP: Final = "TOP"
PDF_ROW_BACKGROUNDS: Final = "ROWBACKGROUNDS"
PDF_LEFT_PADDING: Final = "LEFTPADDING"
PDF_RIGHT_PADDING: Final = "RIGHTPADDING"
PDF_TOP_PADDING: Final = "TOPPADDING"
PDF_BOTTOM_PADDING: Final = "BOTTOMPADDING"
PDF_LINE_BELOW: Final = "LINEBELOW"
PDF_ALIGN_LEFT: Final = "LEFT"
PDF_TRUNCATED: Final = " … [display abbreviated]"
PDF_DOT: Final = "."
PDF_LABEL_SEPARATOR: Final = " / "
PDF_UNKNOWN: Final = "Unknown / unavailable"
PDF_YES: Final = "Yes"
PDF_NO: Final = "No"
PDF_EMPTY: Final = "None observed"
PDF_DECIMAL: Final = "{value:.3f}"
PDF_INLINE_SEPARATOR: Final = "; "
PDF_KEY_VALUE: Final = "{key}: {value}"
PDF_MORE: Final = " … (+{count} entries)"
PDF_FIELD_COUNT: Final = "{count} structured fields"
PDF_BOOKMARK: Final = "booky-section-{index}"
PDF_SEQUENCE: Final = "pdf-sections"
PDF_TOC_ENTRY: Final = "TOCEntry"
PDF_TEMPLATE: Final = "library-report"
PDF_EYEBROW: Final = "BOOKYSTATS  /  YOUR LIBRARY, IN CONTEXT"
PDF_TITLE: Final = "A reading life"
PDF_SUBTITLE: Final = "Library portrait · evidence-led insights · what to read next"
PDF_AUTHOR: Final = "BookyStats"
PDF_AS_OF: Final = "Pinned analysis as of {value}"
PDF_SUMMARY_READ: Final = "Read works"
PDF_SUMMARY_WATCH: Final = "Watchlist works"
PDF_SUMMARY_RATED: Final = "Read with ratings"
PDF_SUMMARY_METADATA: Final = "Selected provider records"
PDF_SUMMARY_NOTE: Final = (
    "Counts describe unique confirmed works in the supplied snapshots, not a verified complete "
    "account. Every Read work contributes to the library portrait, whether rated or not."
)
PDF_READING_GUIDE: Final = "How to read this report"
PDF_GUIDE: Final = (
    "Start with coverage, then separate the shape of your library from rating-linked associations. "
    "Content mentions are supported by public-description excerpts. The watchlist shortlist "
    "explains both evidence and gaps; a ranking score is not a predicted rating."
)
PDF_EVIDENCE_NOTICE: Final = (
    "Generated locally from pinned inputs and saved reports. No source requests, browser session "
    "or credentials are needed to render this document."
)
PDF_NAVIGATION: Final = "Contents"
PDF_SECTION_INVENTORY: Final = "01  Library portrait"
PDF_SECTION_STRUCTURE: Final = "Pages, formats and publication years"
PDF_SECTION_DATES: Final = "02  Reading dates and cohorts"
PDF_SECTION_ENJOYMENT: Final = "03  Ratings and enjoyment evidence"
PDF_SECTION_CONTENT: Final = "04  Themes and six appetites"
PDF_SECTION_WATCHLIST: Final = "05  Watchlist and explained shortlist"
PDF_SECTION_QUALITY: Final = "06  Automated metadata quality"
PDF_SECTION_APPENDIX: Final = "07  Statistics, limitations and provenance"
PDF_ALL_READ_NOTE: Final = (
    "The denominator below is all Read works, not only the rated subset. Available fields are "
    "not interchangeable: selected edition facts do not describe every edition of a work."
)
PDF_RATING_LABEL: Final = "Usable personal rating"
PDF_PAGES_LABEL: Final = "Selected edition pages"
PDF_EDITION_YEAR: Final = "Edition publication year"
PDF_WORK_YEAR: Final = "Work first-publication year"
PDF_DESCRIPTION_LABEL: Final = "Description text (provenance audited below)"
PDF_GENRES_LABEL: Final = "Recognized genre families"
PDF_FORMAT_LABEL: Final = "Selected edition format"
PDF_LANGUAGE_LABEL: Final = "Selected edition language"
PDF_FIELD_LABEL: Final = "Field"
PDF_AVAILABLE_LABEL: Final = "Available"
PDF_MISSING_LABEL: Final = "Missing / conflicting"
PDF_KNOWN_LABEL: Final = "Known works"
PDF_MINIMUM_LABEL: Final = "Minimum"
PDF_MEDIAN_LABEL: Final = "Median"
PDF_MAXIMUM_LABEL: Final = "Maximum"
PDF_TOTAL_LABEL: Final = "Known page sum"
PDF_PAGES_UNAVAILABLE: Final = "Page statistics are unavailable: no selected edition page counts."
PDF_PAGES_NOTE: Final = (
    "Known page sum is an inventory statistic, not pages actually read; editions, rereads and "
    "missing page counts prevent that inference. "
    "Work first-publication and edition years remain separate."
)
PDF_LANGUAGE_NOTE: Final = (
    "Edition language is separate from work-level translation availability. Neither proves "
    "the language actually read or a language preference."
)
PDF_CHART_NOTE: Final = (
    "Top {shown} of {total} observed categories; counts are distinct works per label. "
    "Multilabel totals can exceed the population."
)
PDF_NO_OBSERVATIONS: Final = "No supported observations are available for this section."
PDF_DATE_CAVEAT: Final = (
    "Only explicit dates support dated cohorts. Missing dates are not inferred from capture time. "
    "Goodreads completion dates take precedence; any permitted StoryGraph supplement is separately "
    "labeled with source and precision. Ratings shown by completion year are CURRENT ratings, "
    "not ratings recorded at that historical time. Addition dates are not reading dates."
)
PDF_RATINGS_CAVEAT: Final = (
    "Personal ratings are separate from provider community ratings. Missing or conflicting "
    "ratings are not zeroes. Coverage and selection differences matter: a linked-rating share "
    "is not a matching-accuracy estimate."
)
PDF_RATING_BUCKET: Final = "{value:g} stars"
PDF_RATING_DISTRIBUTION: Final = "Observed personal-rating distribution"
PDF_VALIDATION_CAVEAT: Final = (
    "Held-out errors require the same cohort and training-only baselines. Connected coauthors "
    "stay together where grouped validation is available. Component-resampling ranges describe "
    "stability, not confidence or future recommendation accuracy."
)
PDF_CONTENT_CAVEAT: Final = (
    "Themes and the six supported appetite labels—wonder, surprise, intensity, meaning, connection "
    "and clarity—describe explicit content mentions, not personality. Rules are versioned and "
    "supported mentions include public-description quotes. No official colors, assessment weights "
    "or genre-to-personality proxies are used. A missing mention is not a negative example."
)
PDF_CONTENT_PREFIX: Final = "content."
PDF_MENTION_TITLE: Final = "{label} — {count} supported works"
PDF_QUOTE: Final = "{work}: “{quote}”"
PDF_LINK: Final = '<link href="{url}" color="#188B86">{label}</link>'
PDF_WATCHLIST_CAVEAT: Final = (
    "Composition describes the current watchlist; the separately generated shortlist orders "
    "eligible candidates using transparent saved evidence. Sparse, ambiguous or excluded records "
    "remain visible in the counts rather than receiving invented scores."
)
PDF_WATCHLIST_GENRES: Final = "Watchlist composition: known genre families"
PDF_RANKED_LABEL: Final = "Rankable"
PDF_UNRANKABLE_LABEL: Final = "Unrankable"
PDF_EXCLUDED_LABEL: Final = "Excluded"
PDF_SHORTLIST: Final = "Your explained shortlist"
PDF_NO_SHORTLIST: Final = (
    "No evidence-supported shortlist is available; no order has been invented."
)
PDF_SHORTLIST_TITLE: Final = "{rank}. {title}  |  score {score}"
PDF_AUTHORS: Final = "Authors: {value}"
PDF_SCORE_NOTE: Final = "Ranking score, not enjoyment probability or a guaranteed future rating."
PDF_REASONS_LABEL: Final = "Why it appears"
PDF_MISMATCHES_LABEL: Final = "Counter-evidence and mismatches"
PDF_MISSINGNESS_LABEL: Final = "What remains unknown"
PDF_EXAMPLE_TITLE: Final = "Supporting Read example"
PDF_EXAMPLE_RATING: Final = "Current personal rating"
PDF_WORK_ID_LABEL: Final = "Work ID"
PDF_EVIDENCE_TIERS: Final = (
    "Evidence tiers — identity: {identity}; features: {features}; preference: {preference}."
)
PDF_QUALITY_CAVEAT: Final = (
    "An automated audit checks completeness, provenance and internal consistency. It cannot "
    "establish bibliographic accuracy or independently verify every provider match. Unknown, "
    "unsupported, empty and failed states stay distinct; there is no invented aggregate score."
)
PDF_POPULATION_LABEL: Final = "Population"
PDF_SCOPE_LABEL: Final = "Scope"
PDF_STATES_LABEL: Final = "Observed states"
PDF_IDENTITY_AUDIT: Final = "Identity and provider agreement"
PDF_DIAGNOSTICS: Final = "Consistency findings and actionable gaps"
PDF_CODE_LABEL: Final = "Finding"
PDF_COUNT_LABEL: Final = "Count"
PDF_MESSAGE_LABEL: Final = "Explanation"
PDF_PROVIDER_STATUS: Final = "Provider outcomes and durable deferrals"
PDF_DETAIL_KEY: Final = "Statistic"
PDF_DETAIL_VALUE: Final = "Observed value"
PDF_FINDING_CONTEXT: Final = (
    "Population: {population} · sample: {sample} · missing: {missing} · "
    "reliability: {reliability} · baseline: {baseline}"
)
PDF_UNCERTAINTY: Final = "Uncertainty, support and method details"
PDF_FINDINGS_BOUNDED: Final = (
    "Displayed {shown} of {total} findings in stable summary-first order. "
    "The saved analytics report "
    "retains the complete structured findings."
)
PDF_CAPABILITIES: Final = "Capability and missingness inventory"
PDF_CAPABILITY_STATE: Final = "State"
PDF_CAPABILITY_COVERAGE: Final = "Coverage"
PDF_CAPABILITY_REASON: Final = "Reason"
PDF_FRACTION: Final = "{known} / {total}"
PDF_OTHER_STATISTICS: Final = "Additional computed statistics"
PDF_INVENTORY_SAMPLE: Final = "Read inventory reference"
PDF_INVENTORY_BOUND: Final = (
    "First {shown} of {total} Read works in stable title order; this is a bounded reference, "
    "not the analysis sample. All Read works contribute to applicable statistics."
)
PDF_TITLE_LABEL: Final = "Title"
PDF_AUTHORS_LABEL: Final = "Authors"
PDF_RATING_SHORT_LABEL: Final = "Rating"
PDF_PAGES_SHORT_LABEL: Final = "Pages"
PDF_YEARS_LABEL: Final = "Work / edition year"
PDF_YEARS: Final = "{work} / {edition}"
PDF_PROVENANCE: Final = "Pinned snapshots and calculation versions"
PDF_SOURCE_LABEL: Final = "Source"
PDF_COLLECTION_LABEL: Final = "Collection"
PDF_SNAPSHOT_LABEL: Final = "Snapshot"
PDF_RECORDS_LABEL: Final = "Records"
PDF_CAPTURED_LABEL: Final = "Saved at"
PDF_VERSION_INFO: Final = (
    "Analytics: {analytics}; settings digest: {settings}; saved analytics report: {report}; "
    "ranking policy: {recommendation}; quality schema: {quality}."
)
PDF_LIMITATIONS: Final = "Interpretation limits"
PDF_LIMIT_SOURCE: Final = (
    "A complete file import does not establish a complete or current account collection."
)
PDF_LIMIT_MISSING: Final = (
    "Unavailable fields remain unknown. Unknown content is never treated as dislike."
)
PDF_LIMIT_LABELS: Final = (
    "Unverified browser genre/series labels are not trusted analytic features."
)
PDF_LIMIT_PROVIDERS: Final = (
    "Source acceptance and analytics success do not establish full provider coverage. Deferred "
    "requests and durable retry gates are not reset to force completion."
)
PDF_LIMIT_DISPLAY: Final = (
    "Large nested statistics and evidence lists are explicitly abbreviated for readability; "
    "saved typed reports retain full details. Tables paginate, and only approved public "
    "description references become links."
)
PDF_LIMIT_FONT: Final = (
    "Embedded Noto fonts provide glyph coverage, which is separate from correct script layout. "
    "Complex-script shaping and right-to-left (RTL) layout are not enabled; Devanagari and RTL "
    "text may render incorrectly despite available glyphs. Unsupported glyphs are explicitly "
    "shown as Unicode code points, not silently dropped."
)
PDF_ISSUE: Final = "{code}: {message}"
PDF_FOOTER: Final = "BOOKYSTATS  ·  LOCAL LIBRARY REPORT"
PDF_PAGE: Final = "Page {page}"
PDF_CONTROL_REGEX: Final = r"[\x00-\x1f]"
PDF_STRUCTURE_PREFIX: Final = "read.structure."
PDF_ENJOYMENT_PREFIX: Final = "read.enjoyment."
PDF_RATINGS_PREFIX: Final = "ratings."
PDF_VALIDATION_PREFIX: Final = "read.validation."
PDF_DATE_TOKEN: Final = "cohort"
PDF_YEAR_TOKEN: Final = "year"
PDF_COMPLETION_TOKEN: Final = "completion"
PDF_ADDITIONS_TOKEN: Final = "addition"
PDF_PERSONAL_PREFIX: Final = "read.personal_ratings"
PDF_FEATURE_PREFIX: Final = "read.feature."
PDF_TEST_FILENAME: Final = "library.pdf"
PDF_TEST_ACCOUNT: Final = "synthetic-pdf-reader"
PDF_TEST_HASH: Final = "synthetic-pdf-hash"
PDF_TEST_SOURCE: Final = "work:1"
PDF_TEST_DATE: Final = "2026-11-03T00:00:00+00:00"
PDF_TEST_OTHER_DATE: Final = "2026-11-02T00:00:00+00:00"
PDF_TEST_UNICODE: Final = "Murakami ō — café · Привет · λ"
PDF_TEST_CJK: Final = "本の図書館"
PDF_TEST_AUTHOR: Final = "Synthetic Author"
PDF_TEST_LONG_TITLE: Final = (
    "{index:03d} Murakami ō — café · Привет · λ 本の図書館 "
    "A substantially long title with <untrusted markup> & a long explanatory subtitle that wraps "
    "through multiple lines without clipping the title, rating, year or surrounding table rows."
)
PDF_TEST_TITLE_FIRST: Final = "000 Murakami"
PDF_TEST_TITLE_LAST: Final = "039 Murakami"
PDF_TEST_PREVIOUS: Final = b"previous-good-pdf"
PDF_TEST_FAILURE: Final = "injected PDF rendering failure"
PDF_TEST_RENDER_ATTRIBUTE: Final = "render_pdf"
PDF_TEST_STAGING_PATTERN: Final = "*.staging"
PDF_TEST_RESOURCES: Final = "/Resources"
PDF_TEST_FONT_RESOURCE: Final = "/Font"
PDF_TEST_DESCRIPTOR: Final = "/FontDescriptor"
PDF_TEST_FONT_FILE: Final = "/FontFile2"
PDF_TEST_ACTION: Final = "/A"
PDF_TEST_URI: Final = "/URI"
PDF_TEST_ANNOTATIONS: Final = "/Annots"
PDF_TEST_QUOTE: Final = "A story of friendship and enduring connection."
PDF_TEST_URL: Final = "https://www.goodreads.com/book/show/12345"
PDF_TEST_REASON: Final = "Shares a supported feature with rated Read examples."
PDF_TEST_GAP: Final = "Missing work first-publication year; retained as unknown."
PDF_TEST_QUALITY_CODE: Final = "synthetic_metadata_missing"
PDF_KEY_POPULATION_NAME: Final = "population_name"
PDF_KEY_SOURCES: Final = "sources"
PDF_KEY_WORK_IDS: Final = "work_ids"
PDF_KEY_COMPONENTS: Final = "components"
PDF_KEY_FEATURE: Final = "feature"
PDF_KEY_LABEL: Final = "label"
PDF_KEY_CONTRIBUTION: Final = "contribution"
PDF_KEY_SAMPLE_SIZE: Final = "sample_size"
PDF_SCOPE_POPULATION: Final = "{scope} / {population}"
PDF_STATE_SOURCES: Final = "{states}; sources: {sources}"
PDF_DIAGNOSTIC_DETAIL: Final = "{message} Affected work IDs (bounded): {works}"
PDF_WORK_REFERENCE: Final = "{work} — {title}"
PDF_COMPONENT_FEATURE: Final = "Feature"
PDF_COMPONENT_LABEL: Final = "Observed label"
PDF_COMPONENT_CONTRIBUTION: Final = "Ranking contribution"
PDF_COMPONENT_SUPPORT: Final = "Rated support"
PDF_EOF: Final = b"%%EOF"
PDF_TEST_REPLACE_ATTRIBUTE: Final = "replace"
PDF_UNAVAILABLE_SUMMARY: Final = "Metrics awaiting sufficient observations"
PDF_UNAVAILABLE_METRIC: Final = "Metric (no eligible sample)"
PDF_CAPABILITY_GROUP_NOTE: Final = (
    "Metrics with identical state, coverage and explanation are grouped. These are capability "
    "limits, not zero-valued findings. Complete definitions and details remain in analytics.json."
)
PDF_TEST_LONG_WORD: Final = "unbroken"
PDF_TEST_GROUP_METRIC: Final = "read.feature.authors.synthetic-{index}"
PDF_TEST_VALIDATION_PROOF: Final = "Essential held-out evaluation summary retained."
MQ_REPORT_VERSION: Final = "metadata-quality-v1"
MQ_REPORT_ALL: Final = "all"
MQ_REPORT_INPUT_MISMATCH: Final = (
    "Metadata quality requires the same pinned manifest and as-of time as the analytics report."
)
MQ_REPORT_PROVIDER_DISCREPANCY: Final = "cross_provider_discrepancy"
MQ_REPORT_UNBACKED: Final = "selected_value_without_scoped_evidence"
MQ_REPORT_UNTRUSTED: Final = "selected_value_without_trusted_provenance"
MQ_REPORT_RATING_CONFLICT: Final = "personal_rating_conflict"
MQ_REPORT_YEAR_ORDER: Final = "first_publication_after_edition"
MQ_REPORT_PROVIDER_ORIGIN: Final = "provider_origin_mismatch"
MQ_REPORT_READER_CONTAMINATION: Final = "reader_field_contamination"
MQ_REPORT_UNVERIFIED_LABELS: Final = "unverified_browser_labels"
MQ_REPORT_PROVIDER_DISCREPANCY_MESSAGE: Final = (
    "Selected providers differ on a catalog title/author or work first-publication year. "
    "This is an automated discrepancy, not proof either provider is wrong; "
    "edition naming can differ."
)
MQ_REPORT_UNBACKED_MESSAGE: Final = (
    "A selected analysis value lacks matching present evidence in its required scope."
)
MQ_REPORT_UNTRUSTED_MESSAGE: Final = (
    "A selected value has evidence but no recognized authoritative source/public provider origin."
)
MQ_REPORT_RATING_CONFLICT_MESSAGE: Final = (
    "Conflicting personal ratings remain unresolved; no rating was invented."
)
MQ_REPORT_YEAR_ORDER_MESSAGE: Final = (
    "Work first-publication year follows the selected edition year; inspect retained provenance."
)
MQ_REPORT_PROVIDER_ORIGIN_MESSAGE: Final = (
    "A public-provider observation does not reference its selected canonical provider identity."
)
MQ_REPORT_READER_CONTAMINATION_MESSAGE: Final = (
    "Evidence contains a provider reader-scope field or a disallowed StoryGraph reader field."
)
MQ_REPORT_UNVERIFIED_LABELS_MESSAGE: Final = (
    "Browser genre/series labels remain unverified observations, not trusted analytical features."
)
MQ_REPORT_LIMIT_AUTOMATED: Final = (
    "Coverage and consistency are automated diagnostics, not independently verified accuracy. "
    "Independent verification is unknown; no aggregate quality score is assigned."
)
MQ_REPORT_LIMIT_IDENTITY: Final = (
    "Inputs contain confirmed catalog works and selected identity-valid metadata only. "
    "Identifier-anchor coverage is the presence of validated ISBN observations, "
    "not matching accuracy; "
    "unselected candidates and independent ground truth are not available in this snapshot."
)
MQ_REPORT_LIMIT_PROVIDERS: Final = (
    "Cross-provider comparisons use normalized catalog titles/authors (including edition identity) "
    "and work first-publication years. Agreement can share upstream errors; "
    "title/author differences "
    "may be legitimate edition naming. Different descriptions, subjects and edition facts are not "
    "automatically conflicts. Provider status is current caller-supplied context, not pinned book "
    "evidence or fetched by this report."
)
MQ_REPORT_LIMIT_SCOPE: Final = (
    "Edition language is not language actually read; "
    "work translations cannot fill edition language. "
    "Missing values remain unknown, and unrated Read works stay in the coverage population."
)
MQ_REPORT_LIMIT_COVERAGE: Final = (
    "Coverage counts selected analysis values. Source counts show works with supporting trusted "
    "evidence, may overlap, and can be lower than coverage "
    "when diagnostics identify unsupported values."
)
MQ_REPORT_TEST_GOODREADS_ID: Final = "123"
MQ_REPORT_TEST_GOODREADS_URL: Final = "https://www.goodreads.com/book/show/123"
MQ_REPORT_TEST_CSV_ORIGIN: Final = "file:///synthetic-library.csv"
MQ_REPORT_TEST_OTHER_DESCRIPTION: Final = "An alternative public catalog synopsis."
MQ_REPORT_TEST_LANGUAGE_URL: Final = "https://www.goodreads.com/book/show/123?token=redacted"
MQ_REPORT_KEY_SETTINGS_HASH: Final = "settings_hash"

REC_POLICY_VERSION: Final = "watchlist-baseline-v1"
REC_RANKED: Final = "ranked"
REC_UNRANKABLE: Final = "unrankable"
REC_EXCLUDED: Final = "excluded"
REC_SCORE_LABEL: Final = "Ranking score, not a probability of enjoyment"
REC_CONFIRMED: Final = "confirmed catalog work"
REC_POSSIBLE: Final = "possible Read overlap; not a confirmed identity link"
REC_SUPPORTED: Final = "shared selected evidence"
REC_LIMITED: Final = "limited evidence"
REC_ABSENT: Final = "unavailable"
REC_AUTHOR: Final = "author familiarity"
REC_NO_SIGNAL: Final = (
    "No shared feature with an unconflicted personally rated Read work; abstained."
)
REC_READ: Final = "Confirmed completed/Read work; excluded from start-next suggestions."
REC_ACTIVE: Final = "Currently reading; excluded from start-next suggestions."
REC_RECONSIDER: Final = "Paused or DNF; kept separate from start-next suggestions."
REC_UNRELEASED_WORK: Final = "Known original publication is in a future year."
REC_UNRELEASED_EDITION: Final = (
    "Known selected edition publication is in a future year; "
    "other editions are not assumed available."
)
REC_POSSIBLE_READ: Final = (
    "Unresolved possible match to a Read work; no identity link was inferred."
)
REC_UNKNOWN_STATUS: Final = "Watchlist membership conflicts with an unknown/current reading state."
REC_UNKNOWN_PUBLICATION: Final = (
    "Original publication year is unknown; availability is not established."
)
REC_UNKNOWN_EDITION: Final = "Selected edition publication year is unknown."
REC_UNKNOWN_GENRE: Final = "No supported normalized genre metadata."
REC_UNKNOWN_APPETITE: Final = (
    "No shared explicit appetite labels; content mentions are not personal appetite labels."
)
REC_UNKNOWN_SERIES: Final = (
    "No verified provider series evidence; no reading-order prerequisite is inferred."
)
REC_NO_RATING: Final = "No unconflicted personal ratings on confirmed Read works."
REC_SUPPORT: Final = "Shared {feature}: {label}; {count} personally rated Read work(s)."
REC_MISMATCH: Final = (
    "Shared {feature}: {label} also occurs in {count} Read work(s) rated below 3/5."
)
REC_FAMILIAR: Final = (
    "Author occurs in confirmed Read history; familiarity alone does not establish enjoyment."
)
REC_LIMITATIONS: Final = (
    "Transparent retrospective baseline, not a learned or validated enjoyment probability. "
    "Only confirmed Read personal ratings and features available for both Read and unread works "
    "inform scores. Community ratings, candidate ratings, reviews, and unrated books are not "
    "negative examples. Unknown fields are not penalties. Current source snapshots do not "
    "establish complete account coverage. Year-only publication dates do not establish "
    "within-year release availability."
)
REC_COMPATIBILITY_ERROR: Final = (
    "Recommendation inputs and analytics must pin the same manifest and as-of date."
)
REC_STORE_ERROR: Final = (
    "Recommendation storage failed integrity or compatibility validation; "
    "last-good reports are retained."
)
REC_STORE_CLOSED: Final = "Recommendation storage is closed."
REC_KEY: Final = "key"
REC_POLICY: Final = "policy_version"
REC_AS_OF: Final = "as_of"
REC_MANIFEST: Final = "manifest"
REC_ANALYSIS_REPORT_ID: Final = "analysis_report_id"
REC_REUSED: Final = "reused"
REC_REPORT_ID: Final = "report_id"
REC_SNAPSHOT_IDS: Final = "source_snapshot_ids"
REC_CREATED_AT: Final = "created_at"
REC_BOOKS: Final = "books"
REC_ACCOUNT: Final = "account"
REC_FEATURES: Final = "features"
REC_AUTHOR_NAMES: Final = "authors"
REC_WORK_ID: Final = "work_id"
REC_RATING: Final = "rating"
REC_TITLE: Final = "title"
REC_STATUS: Final = "status"
REC_COLLECTIONS: Final = "collections"
REC_EVENTS: Final = "reading_events"
REC_YEAR: Final = "publication_year"
REC_ORIGINAL_YEAR: Final = "first_publication_year"
REC_ADDED_AT: Final = "added_at"
REC_ISSUES: Final = "issues"
REC_SOURCE_IDS: Final = "source_ids"
REC_TOKEN_MATCH: Final = "match"
REC_TOKEN_AMBIGUOUS: Final = "ambig"
REC_TOKEN_UNRESOLVED: Final = "unresolved"
REC_TOKEN_CONFLICT: Final = "conflict"
REC_CREATE_CACHE: Final = (
    "CREATE TABLE IF NOT EXISTS recommendation_cache ("
    "cache_key TEXT PRIMARY KEY NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
)
REC_CREATE_REPORTS: Final = (
    "CREATE TABLE IF NOT EXISTS recommendation_reports ("
    "report_id INTEGER PRIMARY KEY AUTOINCREMENT, cache_key TEXT NOT NULL "
    "REFERENCES recommendation_cache(cache_key), analysis_report_id INTEGER "
    "REFERENCES analysis_reports(report_id), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)"
)
REC_GET_CACHE: Final = (
    "SELECT cache_key, payload, payload_hash FROM recommendation_cache WHERE cache_key = ?"
)
REC_INSERT_CACHE: Final = "INSERT INTO recommendation_cache VALUES (?, ?, ?)"
REC_INSERT_REPORT: Final = (
    "INSERT INTO recommendation_reports(cache_key, analysis_report_id, payload, payload_hash) "
    "VALUES (?, ?, ?, ?)"
)
REC_LATEST: Final = (
    "SELECT report_id, cache_key, analysis_report_id, payload, payload_hash "
    "FROM recommendation_reports "
    "ORDER BY report_id DESC LIMIT 1"
)
REC_TEST_AUTHOR: Final = "Recommendation author"
REC_TEST_OTHER_AUTHOR: Final = "Other recommendation author"
REC_TEST_GENRE: Final = "fantasy"
REC_TEST_OTHER_GENRE: Final = "history"
REC_TEST_AS_OF: Final = "2026-11-03T00:00:00+00:00"
REC_TEST_FUTURE_AS_OF: Final = "2027-11-03T00:00:00+00:00"
REC_TEST_CORRUPT: Final = "UPDATE recommendation_cache SET payload_hash = ? WHERE cache_key = ?"
REC_TEST_COUNT: Final = "SELECT COUNT(*) FROM recommendation_cache"
REC_TEST_UPDATE: Final = "UPDATE recommendation_reports SET payload_hash = ?"
REC_TEST_BAD_HASH: Final = "0"
REC_REASONS: Final = "reasons"
REC_IDENTITY_TIER: Final = "identity_tier"
REC_RANKING_SCORE: Final = "ranking_score"
REC_MISMATCHES: Final = "mismatches"
REC_COMPONENTS: Final = "components"
REC_SUPPORTING_BOOKS: Final = "supporting_books"
REC_FEATURE_TIER: Final = "feature_tier"
REC_PREFERENCE_TIER: Final = "preference_tier"
REC_RANKED_FIELD: Final = "ranked"
REC_UNRANKABLE_FIELD: Final = "unrankable"
REC_EXCLUDED_FIELD: Final = "excluded"
REC_SHORTLIST_FIELD: Final = "shortlist"
REC_SCHEMA: Final = (
    "SELECT name, sql FROM sqlite_master WHERE name IN "
    "('recommendation_cache', 'recommendation_reports') ORDER BY name"
)
REC_CACHE_TABLE: Final = "recommendation_cache"
REC_REPORT_TABLE: Final = "recommendation_reports"
REC_IF_NOT_EXISTS: Final = "IF NOT EXISTS "
REC_SNAPSHOTS: Final = "snapshots"
REC_SETTINGS_HASH: Final = "settings_hash"
REC_SET_VERSION: Final = "PRAGMA user_version = 3"
REC_LEGACY_VERSION: Final = "PRAGMA user_version = 2"
REC_ALL_CACHE: Final = "SELECT cache_key, payload, payload_hash FROM recommendation_cache"
REC_ALL_REPORTS: Final = (
    "SELECT report_id, cache_key, analysis_report_id, payload, payload_hash "
    "FROM recommendation_reports"
)
REC_DROP_REPORTS: Final = "DROP TABLE recommendation_reports"
REC_DROP_CACHE: Final = "DROP TABLE recommendation_cache"
REC_LEGACY_CONTENT: Final = (
    "SELECT cache_key, kind, payload, payload_hash FROM analysis_components ORDER BY cache_key"
)
REC_LEGACY_REPORTS: Final = "SELECT * FROM analysis_reports ORDER BY report_id"
REC_POSSIBLE_READ_MATCHES: Final = "possible_read_matches"
REC_PENDING_MATCHES: Final = (
    "SELECT id, record_id, target_record_id FROM match_candidates "
    "WHERE resolution = 'pending' ORDER BY id"
)
REC_TARGET_RECORD_ID: Final = "target_record_id"
REC_POSSIBLE_TARGETS: Final = "possible_targets"
REC_TEST_PENDING: Final = (
    "INSERT INTO match_candidates(record_id, target_record_id, kind, reason, identifiers_json, "
    "resolution, first_snapshot_id, last_snapshot_id) "
    "VALUES (?, ?, 'likely', 'synthetic possible match', '[]', 'pending', ?, ?)"
)
REC_TEST_RECORDS: Final = "SELECT id, source_id FROM source_records WHERE source = ? ORDER BY id"
REC_TEST_SNAPSHOT: Final = "SELECT MAX(id) FROM snapshots"
REC_COMMUNITY_RATINGS: Final = "community_ratings"
REC_RATING_CONFLICT: Final = "rating_conflict"
REC_CALCULATION_VERSION: Final = "calculation_version"
REC_ANALYTICS_SETTINGS: Final = "settings"
REC_PUBLICATION_DATES: Final = "publication_dates"
REC_TEST_FUTURE_DAY: Final = "2026-12-01"
REC_TEST_FUTURE_MONTH: Final = "2026-12"
REC_TEST_CURRENT_YEAR: Final = "2026"
REC_TEST_SERIES: Final = "Verified recommendation series"
REC_TEST_PUBLICATION: Final = "date,scope,field,reason"

LOG_FILE_NAME: Final = "bookystats.log"
LOG_APPEND_MODE: Final = "a"
LOG_RUN_START: Final = "=== RUN START {time} UTC | trigger: {trigger} ==="
LOG_RUN_END: Final = "=== RUN END {time} UTC | outcome: {outcome} ==="
LOG_EVENT: Final = "[{time} UTC] {message}"
LOG_FAILURE_TRIGGER: Final = "failure"
LOG_ALREADY_FINISHED: Final = "Cannot append progress to a finished run."
LOG_SYMLINK_ERROR: Final = "Refusing to append the operational log through a symbolic link."
LOG_SECRET_QUERY_PATTERN: Final = (
    r"(?i)([?&](?:api[-_]?key|access[-_]?token|refresh[-_]?token|id[-_]?token|"
    r"client[-_]?secret|password|secret|signature|authorization|auth|"
    r"cookie|remember_user_token)=)[^&\s]+"
)
LOG_SECRET_HEADER_PATTERN: Final = (
    r"(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie|"
    r"""x-api-key)["']?\s*[:=]\s*["']?)[^\r\n]+"""
)
LOG_SECRET_VALUE_PATTERN: Final = (
    r"""(?i)(\b(?:client_secret|refresh_token|access_token|id_token|"""
    r"""api_key|password)\b["']?\s*[:=]\s*["']?)[^"'&\s,;}]+"""
)
LOG_SECRET_USERINFO_PATTERN: Final = r"(?i)(https?://)[^/\s@]+@"
LOG_TEST_PROVIDER_MESSAGE: Final = (
    "https://provider.invalid/books?refresh_token=private-refresh&client_secret=private-client\n"
    "Authorization: Basic private-basic\nCookie: session=private-cookie\n"
    '{"access_token": "private-json"}\n'
    "{'Authorization': 'Basic private-dict'}\n"
    "headers={'Cookie': 'private-dict-cookie'}\n"
    "https://private-user:private-password@provider.invalid/books"
)
LOG_TEST_REFRESH: Final = "private-refresh"
LOG_TEST_CLIENT: Final = "private-client"
LOG_TEST_BASIC: Final = "private-basic"
LOG_TEST_COOKIE: Final = "private-cookie"
LOG_TEST_JSON: Final = "private-json"
LOG_TEST_USER: Final = "private-user"
LOG_TEST_PASSWORD: Final = "private-password"
LOG_TEST_DICT: Final = "private-dict"
LOG_ANALYTICS_SCOPE: Final = "analytics"
LOG_DELIVERY_SCOPE: Final = "delivery"

LOG2_SOURCE: Final = "Source {source}/{collection}: {state}; {records:,} active records."
LOG2_PRODUCTS: Final = (
    "Reports: {state}; PDF and JSON bundle published for analytics report {report_id}."
)
LOG2_PRODUCTS_RETAINED: Final = (
    "Reports: {state}; no new bundle published; any last-good bundle retained."
)
LOG2_METADATA_PROGRESS: Final = "Metadata {source}: {completed:,}/{total:,} books ({percent}%)."
LOG2_PATH_PATTERN: Final = r"""(?i)(?<![\w:/])(?:[a-z]:[\\/]|\\\\[^\\\s]+\\)[^\r\n"'<>|]*"""
LOG2_NOTICE_EXPLANATION: Final = (
    "Expected import notices are counted without row examples; original fields remain archived."
)
LOG2_TEST_LARGE_TOTAL: Final = "total"
LOG2_TEST_PRIVATE_PATH_MESSAGE: Final = (
    'Cannot read "Q:\\private\\reader\\inputs\\library.csv"; check the configured input.'
)
LOG2_TEST_ZERO_TIMEOUT: Final = "timeout"
LOG2_TEST_SYMLINK: Final = "is_symlink"
LOG2_TEST_PROGRESS_FINISHED: Final = "2,153/2,153 books (100%)"
LOG2_SOURCE_RETAINED: Final = (
    "Source {source}/{collection}: {state}; no complete replacement; "
    "any last-good snapshot retained."
)

# Plain-language run outcome: causes, safe retry times, lookups and next actions.
OUTCOME_DURATION_SECONDS: Final = "{seconds:.1f} s"
OUTCOME_DURATION_MINUTES: Final = "{minutes}m {seconds:02d}s"
OUTCOME_DURATION_HOURS: Final = "{hours}h {minutes:02d}m {seconds:02d}s"
OUTCOME_TIME_UNKNOWN: Final = "an unknown time"
OUTCOME_INSTANT: Final = "{local} ({utc} UTC)"
OUTCOME_SECONDS: Final = "seconds"
OUTCOME_UTC_FORMAT: Final = "%Y-%m-%d %H:%M:%S"
OUTCOME_EPOCH_PATTERN: Final = r"UTC timestamp (\d{9,11}(?:\.\d+)?)"
OUTCOME_GOOGLE_BOOKS: Final = "Google Books"
OUTCOME_OPEN_LIBRARY: Final = "Open Library"
OUTCOME_BOOK_ONE: Final = "{count} book"
OUTCOME_BOOKS: Final = "{count:,} books"
OUTCOME_NEEDS_ATTENTION: Final = "needs_attention"
OUTCOME_HEADLINE: Final = "Outcome: {state} (exit code {exit_code}) after {duration}"
OUTCOME_COMPLETE: Final = (
    "Result: {finished} of {total} source imports completed; nothing needs attention."
)
OUTCOME_CAUSE_LINE: Final = "Why: {text}"
OUTCOME_MORE: Final = "Why: {count} further causes are not listed here."
OUTCOME_NEXT_LINE: Final = "Next: {action}"
OUTCOME_LOOKUPS: Final = (
    "Lookups: {provider} {state}; {processed:,} of {requested:,} books processed, "
    "{deferred:,} deferred, {hits:,} from cache, {network}."
)
OUTCOME_NETWORK: Final = "{count:,} network requests"
OUTCOME_NETWORK_ONE: Final = "1 network request"
OUTCOME_NETWORK_UNKNOWN: Final = "network requests not measured"
OUTCOME_PAUSED: Final = "{provider} is paused until {until}{reason}{waiting}."
OUTCOME_AFTER_HTTP: Final = " after HTTP {status}"
OUTCOME_AFTER_PENDING: Final = " after a request that did not finish"
OUTCOME_WAITING: Final = "; {waiting} waiting"
OUTCOME_BUDGET: Final = "{provider} used this run's lookup allowance; {waiting} waiting."
OUTCOME_SIGN_IN: Final = "{provider} needs Google sign-in or an API key; {waiting} waiting."
OUTCOME_ACCESS_FAILED: Final = "{provider} sign-in or key access failed."
OUTCOME_CACHE_ERROR: Final = "The {provider} lookup cache could not be read."
OUTCOME_EARLIER_PAUSE: Final = (
    "{provider} lookups were deferred by a provider pause that has since ended; {waiting} waiting."
)
OUTCOME_DEFERRED: Final = "{provider} deferred {waiting}."
OUTCOME_PARKED: Final = (
    "{provider} has no further lookups due; earlier incomplete lookups stay parked "
    "until the record or provider changes."
)
OUTCOME_PROVIDER_STATE: Final = "{provider} ended {state}."
OUTCOME_SOURCES: Final = (
    "{count} of {total} source imports did not complete ({names}); "
    "the last complete snapshot is kept."
)
OUTCOME_SOURCE_NAME: Final = "{source}/{collection} {state}"
OUTCOME_VERIFICATION: Final = (
    "Verification ended {result}; {failed} of {total} checks did not pass ({names})."
)
OUTCOME_VERIFICATION_SHORT: Final = "Verification ended {result}."
OUTCOME_STAGE: Final = (
    "{stage} ended {state}; nothing new was published and any earlier good result is kept."
)
OUTCOME_ANALYTICS: Final = "Analytics"
OUTCOME_REPORTS: Final = "Reports"
OUTCOME_LOG_INCOMPLETE: Final = "The run log is incomplete ({reason})."
OUTCOME_UNSPECIFIED: Final = (
    "The run did not finish cleanly and no more specific cause was recorded."
)
OUTCOME_ACTION_PAUSED: Final = (
    "Run booky sync again after {until}; the provider may still ask for more waiting."
)
OUTCOME_ACTION_BUDGET: Final = "Run booky sync again to continue the remaining lookups."
OUTCOME_ACTION_SIGN_IN: Final = (
    "Run booky sync in an interactive terminal to sign in, or set {key}."
)
OUTCOME_ACTION_NOTHING: Final = (
    "Nothing to do now; these books are retried only when their records or lookup rules change."
)
OUTCOME_ACTION_SOURCES: Final = (
    "Fix the input named above (or configure the account), then run booky sync again."
)
OUTCOME_ACTION_VERIFICATION: Final = "Review the failed checks above, then run booky sync again."
OUTCOME_ACTION_STAGE: Final = (
    "Run booky sync again; if it repeats, read the run log for the stage error."
)
OUTCOME_ACTION_LOG: Final = (
    "Check free space and permissions for the data\\logs folder, then run booky sync again."
)
OUTCOME_ACTION_GENERIC: Final = "Run booky sync again; if the cause repeats, read the run log."
OUTCOME_ACTION_FAILED: Final = "Fix the cause above, then run booky sync again."
OUTCOME_ACTION_INTERRUPTED: Final = "Run booky sync again; sources that already completed are kept."

# Append-only operational run log (format 2).
OPLOG_START_TOKEN: Final = "=== RUN START"
OPLOG_END_TOKEN: Final = "=== RUN END"
OPLOG_START: Final = "=== RUN START {instant} | trigger: {trigger} ==="
OPLOG_END: Final = (
    "=== RUN END {instant} | run: {run_id} | outcome: {state} | "
    "exit code: {exit_code} | duration: {duration} ==="
)
OPLOG_VERSION_LINE: Final = "Version: {version} | log format: {format}"
OPLOG_EVENT: Final = "[{stamp}] {message}"
OPLOG_NO_RUN: Final = "none"
OPLOG_INDENT: Final = "  "
OPLOG_DEEP_INDENT: Final = "    "
OPLOG_EXAMPLE_INDENT: Final = "      "
OPLOG_SUMMARY_HEADING: Final = "Run summary:"
OPLOG_RUN_LINE: Final = "Run {run_id}: {state}."
OPLOG_SOURCES: Final = (
    "Sources: {complete} of {total} imports complete; {records:,} records in complete imports."
)
OPLOG_FILE_SCOPE: Final = "File imports do not verify account completeness."
OPLOG_SOURCE_LINE: Final = (
    "{source}/{collection}: {state}; {records:,} records ({added:,} added, "
    "{updated:,} updated, {unchanged:,} unchanged, {removed:,} removed)."
)
OPLOG_SOURCE_UNPUBLISHED: Final = (
    "{source}/{collection}: {state}; no new snapshot published; any last-good snapshot is kept."
)
OPLOG_CORE: Final = (
    "{provider} core-gap fallback: {unresolved:,} records still missing description/genre "
    "evidence; {skipped:,} strategy skips (not provider matches)."
)
OPLOG_ANALYTICS: Final = (
    "Analytics: {state}; report {report_id}, {read:,} Read works, {rated:,} rating-linked; "
    "calculations reused: taste {taste}, watchlist {watchlist}."
)
OPLOG_YES: Final = "yes"
OPLOG_NO: Final = "no"
OPLOG_VERIFICATION: Final = "Verification: {result}; {passed} of {total} checks passed."
OPLOG_VERIFICATION_NONE: Final = "Verification: not run."
OPLOG_CHECK_LINE: Final = "{name} {result}: {detail}"
OPLOG_CHECKS_MORE: Final = "{count} further checks did not pass and are not listed here."
OPLOG_ISSUES_HEADING: Final = (
    "Issues (every occurrence is counted; at most {limit} examples per kind):"
)
OPLOG_ISSUES_NONE: Final = "Issues: none."
OPLOG_ISSUE_COUNT: Final = "{scope} | {code}: {count:,} occurrences"
OPLOG_ISSUE_COUNT_ONE: Final = "{scope} | {code}: 1 occurrence"
OPLOG_ISSUE_EXAMPLE: Final = "Example: {message}"
OPLOG_TRUNCATED: Final = "... [message shortened]"
OPLOG_TIME_HEADING: Final = "Time spent by stage:"
OPLOG_TIME_LINE: Final = "{duration:>9}  {stage}"
OPLOG_TIME_OTHER: Final = "Other (start-up, verification, summary)"
OPLOG_STAGE_PREFIX: Final = "Stage: "
OPLOG_PERIOD: Final = "."
OPLOG_RUN_ID_FIELD: Final = "{run_id}"
OPLOG_STATE_FIELD: Final = "{state}"
OPLOG_DIGITS: Final = r"(\d+)"
OPLOG_WORD: Final = r"\w+"
OPLOG_START_STRIP: Final = " ="
OPLOG_UNTERMINATED: Final = (
    "Notice: the log shows no RUN END for the previous run ({start}); "
    "it may have been interrupted or killed."
)
OPLOG_DEGRADED: Final = (
    "Log notice: {count:,} lines could not be written during this run ({reason})."
)
OPLOG_START_FAILED: Final = "The run log could not be opened ({reason})."
OPLOG_WARNING: Final = (
    "Warning: the run log is incomplete ({reason}); the final outcome will say so."
)
OPLOG_SUMMARY_WARNING: Final = (
    "Warning: the last-run summary could not be saved ({reason}); status may show an older run."
)
OPLOG_FAILURE_NOT_LOGGED: Final = (
    "Warning: this failure could not be recorded in the run log ({reason}); "
    "the message above is the only record."
)
OPLOG_SYNC_NOT_STARTED: Final = "The sync was not started."
OPLOG_NO_RECEIPT: Final = "The run ended without a final receipt."
OPLOG_INTERRUPTED: Final = (
    "The run was interrupted before it finished; completed source snapshots are kept."
)
OPLOG_UNEXPECTED: Final = (
    "Unexpected {type} at {module}:{line} in {function}; "
    "details are withheld because they can contain private data."
)
OPLOG_UNEXPECTED_BARE: Final = (
    "Unexpected {type}; details are withheld because they can contain private data."
)
OPLOG_MODULE_KEY: Final = "__name__"
OPLOG_MODULE_PREFIX: Final = "bookystats"
OPLOG_URL_QUERY_PATTERN: Final = r"(?i)(https?://[^\s?#]+)\?[^\s#]*"
OPLOG_URL_QUERY_REPLACEMENT: Final = r"\1?[query removed]"
OPLOG_READ_BINARY: Final = "rb"
OPLOG_BACKSLASHREPLACE: Final = "backslashreplace"
OPLOG_RECONFIGURE: Final = "reconfigure"
OPLOG_ANALYTICS_FAILED: Final = (
    "Analytics calculation failed ({error_type}); the previous report is retained."
)

# Saved last-run summary shown by offline status.
RUNSUM_FILE_NAME: Final = "last-run.json"
RUNSUM_KEY: Final = "run_summary"
RUNSUM_FINISHED_KEY: Final = "finished_utc"
RUNSUM_LINES_KEY: Final = "lines"
RUNSUM_GATES_KEY: Final = "gates"
RUNSUM_PROVIDER_KEY: Final = "provider"
RUNSUM_RETRY_KEY: Final = "retry_at_utc"
RUNSUM_TIME_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
RUNSUM_ATTEMPT_LINE: Final = "Last sync attempt, finished {finished}:"
RUNSUM_TEXT_LINE: Final = "  {text}"
RUNSUM_GATE_ACTIVE: Final = (
    "Retry gate after that attempt: {provider} until {until}, in {remaining}; "
    "the provider may still refuse."
)
RUNSUM_GATE_PASSED: Final = (
    "Retry gate after that attempt: {provider} until {until}; "
    "that time has passed, and the provider may still refuse."
)

# Logging, outcome and last-run summary tests.
TEST_OPLOG_APPEND_ATTRIBUTE: Final = "_append"
TEST_OPLOG_RUN_ATTRIBUTE: Final = "run"
TEST_OPLOG_DISK_FULL: Final = "disk full"
TEST_OPLOG_LEGACY_TEXT: Final = "legacy history line\n"
TEST_OPLOG_PERSONAL: Final = "personal-review-text"
TEST_OPLOG_API_KEY: Final = "private-api-key"
TEST_OPLOG_URL_USER: Final = "private-url-user"
TEST_OPLOG_URL_PASSWORD: Final = "private-url-password"
TEST_OPLOG_URL_HOST: Final = "books.invalid"
TEST_OPLOG_URL_MESSAGE: Final = (
    "Request to https://private-url-user:private-url-password@books.invalid/volumes"
    "?q=personal-review-text&key=private-api-key failed."
)
TEST_OPLOG_PATH_FRAGMENT: Final = "library.csv"
TEST_OPLOG_CLOCK_INSTANT: Final = "2026-11-02 13:30:00+05:30 (2026-11-02 08:00:00 UTC)"
TEST_OPLOG_LOCAL_STAMP: Final = "2026-11-02 13:30:00+05:30"
TEST_OPLOG_GATE_INSTANT: Final = "2026-11-03 18:19:24+05:30 (2026-11-03 12:49:24 UTC)"
TEST_OPLOG_DEFERRED_TEXT: Final = (
    "Provider host is deferred until 2026-11-03 18:19:24+05:30 (2026-11-03 12:49:24 UTC)."
)
TEST_OPLOG_SECONDS_TEXT: Final = "12.3 s"
TEST_OPLOG_MINUTES_TEXT: Final = "9m 08s"
TEST_OPLOG_HOURS_TEXT: Final = "1h 02m 05s"
TEST_OPLOG_ZERO_TEXT: Final = "0.0 s"
TEST_OPLOG_WHY: Final = "Why:"
TEST_OPLOG_PAUSED_WORDS: Final = "is paused until"
TEST_OPLOG_QUOTA: Final = "quota"
TEST_OPLOG_RESET: Final = "reset"
TEST_OPLOG_FILLER: Final = "synthetic noise "
TEST_OPLOG_FINISHED_UTC: Final = "2026-11-03T12:00:00Z"
TEST_OPLOG_STATUS_NOW: Final = "2026-11-03T18:00:00+05:30"
TEST_OPLOG_ACTIVE_RETRY: Final = "2026-11-03T12:49:24Z"
TEST_OPLOG_PASSED_RETRY: Final = "2026-11-03T11:00:00Z"
TEST_OPLOG_NOT_JSON: Final = "not json"
TEST_OPLOG_SCHEME: Final = "://"
TEST_OPLOG_INTERRUPTED_END: Final = "| outcome: interrupted | exit code: 130 |"
TEST_OPLOG_FAILED_END: Final = "| outcome: failed | exit code: 1 |"
TEST_OPLOG_VALUE_ERROR: Final = "ValueError"
TEST_OPLOG_TRIGGER_FIELD: Final = "trigger"
TEST_OPLOG_RUN_ID_FIELD: Final = "run_id"
TEST_OPLOG_OUTCOME_FIELD: Final = "outcome"
TEST_OPLOG_EXIT_FIELD: Final = "exit_code"
TEST_OPLOG_DURATION_FIELD: Final = "duration_seconds"
TEST_OPLOG_NETWORK_FIELD: Final = "network_requests"
TEST_OPLOG_SCHEMA_FIELD: Final = "schema_version"
TEST_OPLOG_CLOCK_UTC: Final = "2026-11-02T08:00:00Z"
TEST_OPLOG_QUERY_REMOVED: Final = "[query removed]"
TEST_OPLOG_UNTERMINATED_FRAGMENT: Final = "the log shows no RUN END for the previous run"
TEST_OPLOG_PROBE_FRAME: Final = "in RunProbe._read;"
TEST_OPLOG_EXAMPLE_PREFIX: Final = "Example: "
TEST_OPLOG_DISTINCT: Final = "distinct synthetic message {number}"
TEST_OPLOG_REPLACE_ATTRIBUTE: Final = "replace"
TEST_OPLOG_PARTIAL_END: Final = "| outcome: partial | exit code: 3 |"
TEST_OPLOG_ATTEMPT_PREFIX: Final = "Last sync attempt, finished "
TEST_OPLOG_FINISHED_INSTANT: Final = "2026-11-03 17:30:00+05:30 (2026-11-03 12:00:00 UTC)"
TEST_OPLOG_PASSED_INSTANT: Final = "2026-11-03 16:30:00+05:30 (2026-11-03 11:00:00 UTC)"
TEST_OPLOG_REMAINING_TEXT: Final = "19m 24s"
TEST_OPLOG_UTC_FRAGMENT: Final = "2026-11-03 12:49:24 UTC"

# Shared cross-lane analysis contract.
EVIDENCE_TIER_DECLARED: Final = "declared"
EVIDENCE_TIER_SINGLE_SOURCE: Final = "single_source"
EVIDENCE_TIER_CORROBORATED: Final = "corroborated"
EVIDENCE_TIER_CONFLICTING: Final = "conflicting"
