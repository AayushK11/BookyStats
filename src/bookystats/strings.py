# All first-party Python text and byte literals live here, including test values.
# Configuration files and source HTML/XML fixtures are declarative data, not code literals.
from __future__ import annotations

from typing import Final, Literal

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
TEST_BROWSER_CLASS_NAME: Final = "BrowserClient"
NAME: Final = "name"
DEFAULT_STORYGRAPH_ACCOUNT: Final = "byte_me"
DEFAULT_STORYGRAPH_PROFILE: Final = "https://app.thestorygraph.com/profile/byte_me"
DEFAULT_GOODREADS_ACCOUNT: Final = "79839274"
DEFAULT_GOODREADS_PROFILE: Final = "https://www.goodreads.com/user/show/79839274"

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
BROWSER_LOGIN_PATH_SIGN_IN_LOG_IN_LOGIN: Final = "/(?:sign[_-]?in|log[_-]?in|login)(?:/|$)"
BROWSER_EXPORT_PATH_EXPORTS_EXPORTING_DOWNLOADS: Final = (
    "(?:^|[/_.-])(?:exports?|exporting|downloads?)(?:[/_.-]|$)"
)
HTML_PARSER: Final = "html.parser"
SPACE: Final = " "
EMPTY: Final = ""
BROWSER_PAGE_ACCESS_PROBLEM_CHALLENGE_CHALLENGE_RUNNING_CF_TURNSTILE: Final = (
    "#challenge-form, #cf-challenge-running, .cf-turnstile, .g-recaptcha, iframe["
    "src*='challenges.cloudflare.com'], iframe[src*='/recaptcha/']"
)
BROWSER_PAGE_ACCESS_PROBLEM_JUST_A_MOMENT: Final = "just a moment"
BROWSER_PAGE_ACCESS_PROBLEM_ATTENTION_REQUIRED: Final = "attention required"
BROWSER_PAGE_ACCESS_PROBLEM_VERIFY_YOU_ARE_HUMAN: Final = "verify you are human"
BROWSER_PAGE_ACCESS_PROBLEM_THE_SOURCE_BLOCKED_ACCESS_OR_PRESENTED_A: Final = (
    "The source blocked access or presented a challenge. No bypass was attempted."
)
SOURCE_BLOCKED: Final = "source_blocked"
BROWSER_PAGE_ACCESS_PROBLEM_FORM_INPUT_TYPE_PASSWORD: Final = "form input[type='password']"
BROWSER_PAGE_ACCESS_PROBLEM_THE_NEEDS_AN_AUTHENTICATED_OWNER_SESSION: Final = (
    "The source needs an authenticated owner session. Run interactive login, then retry."
)
NEEDS_AUTH: Final = "needs_auth"
BROWSER_PAGE_ACCESS_PROBLEM_THE_AN_UNSUCCESSFUL_PAGE_RESPONSE: Final = (
    "The source returned an unsuccessful page response."
)
SOURCE_HTTP_ERROR: Final = "source_http_error"
BROWSER_BROWSERCLIENT_INIT_A_Z0_A_Z0_A_Z0: Final = "[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?"
BROWSER_BROWSERCLIENT_INIT_TEXT: Final = ".."
BROWSER_BROWSERCLIENT_INIT_ALLOWED_HOSTS_CONTAIN_EXACT_LOWERCASE_DNS: Final = (
    "allowed_hosts must contain exact lowercase DNS hostnames"
)
BROWSER_BROWSERCLIENT_INIT_TIMEOUT_SECONDS_MUST_BE_BETWEEN_ZERO_AND: Final = (
    "timeout_seconds must be between zero and one hour"
)
HTTPS: Final = "https"
BROWSERCLIENT_CHECKED_URL_VALID_X00_X20: Final = "[\\x00-\\x20\\\\]"
BROWSER_BROWSERCLIENT_CHECKED_URL_REFUSED_OUTSIDE_THE_CONFIGURED: Final = (
    "Browser navigation was refused outside the configured HTTPS source."
)
UNSAFE_NAVIGATION: Final = "unsafe_navigation"
BROWSER_BROWSERCLIENT_CHECKED_URL_EXPORT_DOWNLOAD: Final = "(?:^|&)(?:export|download)(?:=|&|$)"
BROWSER_BROWSERCLIENT_CHECKED_URL_DOWNLOAD_NAVIGATION_IS_DISABLED: Final = (
    "Export and download navigation is disabled."
)
EXPORT_DISABLED: Final = "export_disabled"
BROWSER_BROWSERCLIENT_PREPARE_PROFILE_THE_PROFILE_MUST_NOT_BE: Final = (
    "The dedicated browser profile must not be a symbolic link."
)
UNSAFE_PROFILE: Final = "unsafe_profile"
NT: Final = "nt"
BROWSER_BROWSERCLIENT_PREPARE_PROFILE_THE_PROFILE_COULD_NOT_BE: Final = (
    "The dedicated browser profile could not be opened. Check its permissions."
)
PROFILE_UNAVAILABLE: Final = "profile_unavailable"
BROWSER_BROWSERCLIENT_START_THIS_BROWSER_SESSION_IS_CLOSED: Final = (
    "This browser session is closed."
)
BROWSER_CLOSED: Final = "browser_closed"
PLAYWRIGHT_SYNC_API: Final = "playwright.sync_api"
BROWSER_BROWSERCLIENT_START_BOOKYSTATS_BROWSER_DEPENDENCIES: Final = (
    "Playwright is unavailable. Install BookyStats browser dependencies and run '"
    "python -m playwright install chromium' once before retrying."
)
BROWSER_DEPENDENCIES_MISSING: Final = "browser_dependencies_missing"
BLOCK: Final = "block"
BROWSER_BROWSERCLIENT_START_TEXT: Final = "**/*"
PAGE: Final = "page"
BROWSERCLIENT_START_CODE_EXECUTABLE_DOESN_T_EXIST: Final = "Executable doesn't exist"
BROWSER_NOT_INSTALLED: Final = "browser_not_installed"
BROWSER_START_FAILED: Final = "browser_start_failed"
BROWSERCLIENT_START_MESSAGE_CHROMIUM_IS_NOT_INSTALLED_RUN_PYTHON_M: Final = (
    "Chromium is not installed. Run 'python -m playwright install chromium' once before retrying."
)
BROWSERCLIENT_START_MESSAGE_THE_BROWSER_COULD_NOT_START_CHECK_THE: Final = (
    "The browser could not start. Check the browser installation and profile lock."
)
BROWSER_BROWSERCLIENT_START_THE_BROWSER_PROCESS_COULD_NOT_BE_STARTED: Final = (
    "The browser process could not be started."
)
DOWNLOAD: Final = "download"
POST: Final = "POST"
BROWSER_BROWSERCLIENT_GUARD_REQUEST_AN_DOWNLOAD_REQUEST_WAS_BLOCKED: Final = (
    "An export or download request was blocked."
)
GET: Final = "GET"
HEAD: Final = "HEAD"
OPTIONS: Final = "OPTIONS"
BLOCKEDBYCLIENT: Final = "blockedbyclient"
LOCATION: Final = "location"
BROWSER_BROWSERCLIENT_GUARD_REQUEST_A_REQUIRING_FORM_RESUBMISSION_IS: Final = (
    "A login redirect requiring form resubmission is not supported."
)
LOGIN_REDIRECT_UNSUPPORTED: Final = "login_redirect_unsupported"
ATTACHMENT: Final = "attachment"
CONTENT_DISPOSITION: Final = "content-disposition"
BROWSER_BROWSERCLIENT_GUARD_REQUEST_A_FILE_DOWNLOAD_WAS_BLOCKED: Final = (
    "A file download was blocked."
)
BROWSERCLIENT_GUARD_REQUEST_THE_SOURCE_PAGE_TIMED_OUT: Final = "The source page timed out."
BROWSER_TIMEOUT: Final = "browser_timeout"
TIMEDOUT: Final = "timedout"
BROWSERCLIENT_GUARD_REQUEST_THE_BROWSER_COULD_NOT_LOAD_THE_SOURCE: Final = (
    "The browser could not load the source page."
)
BROWSER_OPERATION_FAILED: Final = "browser_operation_failed"
FAILED: Final = "failed"
BROWSER_BROWSERCLIENT_NAVIGATE_A_BROWSER_REDIRECT_REPEATED: Final = "A browser redirect repeated."
REDIRECT_LOOP: Final = "redirect_loop"
DOMCONTENTLOADED: Final = "domcontentloaded"
BROWSER_BROWSERCLIENT_NAVIGATE_THE_REDIRECT_LIMIT_WAS_REACHED: Final = (
    "The browser redirect limit was reached."
)
REDIRECT_LIMIT: Final = "redirect_limit"
FORM: Final = "form"
ACTION: Final = "action"
BROWSER_BROWSERCLIENT_OWNER_LOGIN_TEMPLATE: Final = (
    "Sign in in the visible source browser window. BookyStats will wait at most {"
    "v0:g} seconds. Do not enter credentials in this console."
)
BROWSER_BROWSERCLIENT_OWNER_LOGIN_OWNER_WAS_NOT_COMPLETED_WITHIN_THE: Final = (
    "Owner login was not completed within the bounded wait. Run interactive login again."
)
LOGIN_WAIT_EXPIRED: Final = "login_wait_expired"
ATTACHED: Final = "attached"
BROWSER_BROWSERCLIENT_FETCH_THE_BROWSER_STOPPED_OR_COULD_NOT_LOAD: Final = (
    "The browser stopped or could not load the source page."
)
BROWSER_BROWSERCLIENT_CLOSE_THE_BROWSER_SESSION_COULD_NOT_BE_CLOSED: Final = (
    "The browser session could not be closed cleanly."
)
BROWSER_CLOSE_FAILED: Final = "browser_close_failed"
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
    "Read-only reading-data sync. Reports read the local database, not the websites."
)
COMMAND: Final = "command"
SYNC: Final = "sync"
STATUS: Final = "status"
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
CLI_BUILD_SERVICE_PROGRESS_TEMPLATE: Final = "{v0}: {v1}, {v2} pages checked"
CLI_PRINT_RECEIPT_TEMPLATE: Final = "Sync {v0}: {v1}"
CLI_PRINT_RECEIPT_TEMPLATE_2: Final = "  {v0}: {v1}; {v2} records, {v3} pages"
CLI_PRINT_RECEIPT_TEMPLATE_3: Final = (
    "    {v0} added, {v1} updated, {v2} unchanged, {v3} removed from current collection"
)
CLI_PRINT_RECEIPT_TEMPLATE_4: Final = "    {v0}: {v1}"
CLI_PRINT_RECEIPT_TEMPLATE_5: Final = "    {v0} additional issues in the stored receipt."
CLI_PRINT_RECEIPT_TEMPLATE_6: Final = "  {v0}: {v1}; {v2} lookups completed, {v3} deferred"
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
CLI_PRINT_STATUS_TEMPLATE: Final = "{v0}: {v1}"
CLI_MAIN_WEEKLY_SCHEDULING_IS_DISABLED_NO_SOURCE_REQUESTS: Final = (
    "Weekly scheduling is disabled; no source requests were made."
)
CLI_MAIN_CONFIGURE_READER_PROFILE_URLS_IN_CONFIG_JSON: Final = (
    "Configure reader profile URLs in config.json or BOOKYSTATS_STORYGRAPH_PROFIL"
    "E / BOOKYSTATS_GOODREADS_PROFILE, then run booky sync. No exports are needed"
    "."
)
SCHEDULED: Final = "scheduled"
MANUAL: Final = "manual"
UNATTENDED: Final = "unattended"
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
GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM: Final = "https://www.goodreads.com"
GOODREADS_ATOM_HTTP_WWW_W3_ORG_ATOM: Final = "{http://www.w3.org/2005/Atom}"
GOODREADS_READER_PATH_USER_SHOW_REVIEW_LIST_RSS: Final = (
    "/(?:user/show|review/list(?:_rss)?)/([0-9]+)(?:-[^/]+)?/?"
)
GOODREADS_BOOK_PATH_BOOK_SHOW: Final = "/book/show/([0-9]+)(?:[.-][^/]+)?/?"
GOODREADS_REVIEW_PATH_REVIEW_SHOW: Final = "/review/show/[0-9]+/?"
GOODREADS_AUTHOR_PATH_AUTHOR_SHOW: Final = "/author/show/[0-9]+(?:[.-][^/]+)?/?"
GOODREADS_LOGIN_PATHS_USER_SIGN_IN: Final = "/user/sign_in"
GOODREADS_LOGIN_PATHS_USER_SIGN_UP: Final = "/user/sign_up"
GOODREADS_LOGIN_PATHS_USER_NEW: Final = "/user/new"
GOODREADS_LOGIN_PATHS_AP_SIGNIN: Final = "/ap/signin"
GOODREADS_TEXT_A_ZA_Z_W_S: Final = "</?[a-zA-Z][\\w:-]*(?:\\s|/?>)"
GOODREADS_TEXT_SCRIPT_STYLE: Final = "script, style"
UNSAFE_LINK: Final = "unsafe_link"
GOODREADS_SAFE_URL_GOODREADS_SUPPLIED_AN_INVALID_SOURCE_LINK: Final = (
    "Goodreads supplied an invalid source link."
)
HTTP: Final = "http"
GOODREADS_SAFE_URL_A_GOODREADS_LINK_LEFT_THE_PERMITTED_SOURCE: Final = (
    "A Goodreads link left the permitted source host."
)
GOODREADS_SAFE_URL_TEXT: Final = "?"
GOODREADS_QUERY_GOODREADS_SUPPLIED_AN_INVALID_QUERY_STRING: Final = (
    "Goodreads supplied an invalid query string."
)
SHELF: Final = "shelf"
TO_READ: Final = "to-read"
WRONG_COLLECTION: Final = "wrong_collection"
GOODREADS_SHELF_QUERY_GOODREADS_DID_NOT_RETURN_THE_REQUESTED_TO: Final = (
    "Goodreads did not return the requested to-read shelf."
)
LIST_RSS: Final = "list_rss"
LIST: Final = "list"
PER_PAGE: Final = "per_page"
GOODREADS_COLLECTION_URL_TEMPLATE: Final = "{v0}/review/{v1}/{v2}?{v3}"
ACCOUNT_MISMATCH: Final = "account_mismatch"
GOODREADS_CHECK_DOCUMENT_URL_GOODREADS_A_DIFFERENT_READER_S_PAGE: Final = (
    "Goodreads returned a different reader's page."
)
GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST_RSS: Final = "/review/list_rss/"
GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST: Final = "/review/list/"
UNEXPECTED_PAGE: Final = "unexpected_page"
GOODREADS_CHECK_DOCUMENT_URL_GOODREADS_RETURNED_AN_UNEXPECTED_PAGE: Final = (
    "Goodreads returned an unexpected page."
)
GOODREADS_CHECK_ACCESS_IS_HTML_S_XML_S_DOCTYPE_S_HTML_HTML: Final = (
    "\\s*(?:<\\?xml[^>]*>\\s*)?<(?:!doctype\\s+html|html|head|body|form)\\b"
)
GOODREADS_CHECK_ACCESS_CHALLENGE_VERIFY_THAT_YOU_ARE_HUMAN: Final = "verify that you are human"
GOODREADS_CHECK_ACCESS_CHALLENGE_UNUSUAL_TRAFFIC: Final = "unusual traffic"
GOODREADS_CHECK_ACCESS_CHALLENGE_ACCESS_DENIED: Final = "access denied"
GOODREADS_CHECK_ACCESS_CHALLENGE_CHECKING_YOUR_BROWSER: Final = "checking your browser"
GOODREADS_CHECK_ACCESS_CHALLENGE_ENABLE_AND_COOKIES_TO_CONTINUE: Final = (
    "enable javascript and cookies to continue"
)
GOODREADS_CHECK_ACCESS_CHALLENGE_SECURITY_CHALLENGE: Final = "security challenge"
GOODREADS_CHECK_ACCESS_CHALLENGE_REQUEST_BLOCKED: Final = "request blocked"
GOODREADS_CHECK_ACCESS_IFRAME_SRC_CAPTCHA_G_RECAPTCHA_H_CAPTCHA: Final = (
    "iframe[src*='captcha'], .g-recaptcha, .h-captcha, #challenge-form"
)
GOODREADS_CHECK_ACCESS_GOODREADS_BLOCKED_NO_ALTERNATIVE_ROUTE_WAS: Final = (
    "Goodreads blocked access. No alternative route was attempted."
)
ACCESS_BLOCKED: Final = "access_blocked"
GOODREADS_CHECK_ACCESS_PRIVATE_THIS_PROFILE_IS_PRIVATE: Final = "this profile is private"
GOODREADS_CHECK_ACCESS_PRIVATE_THIS_USER_S_PROFILE_IS_PRIVATE: Final = (
    "this user's profile is private"
)
GOODREADS_CHECK_ACCESS_PRIVATE_THIS_MEMBER_S_PROFILE_IS_PRIVATE: Final = (
    "this member's profile is private"
)
GOODREADS_CHECK_ACCESS_PRIVATE_ONLY_VISIBLE_TO_FRIENDS: Final = "only visible to friends"
GOODREADS_CHECK_ACCESS_PRIVATE_SIGN_IN_TO_VIEW_THIS: Final = "sign in to view this"
GOODREADS_CHECK_ACCESS_PRIVATE_LOG_IN_TO_VIEW_THIS: Final = "log in to view this"
GOODREADS_CHECK_ACCESS_LOGIN_FORM_INPUT_TYPE_PASSWORD: Final = "input[type='password']"
GOODREADS_CHECK_ACCESS_GOODREADS_CONFIGURED_READER_S_ORDINARY: Final = (
    "Goodreads requires the configured reader's ordinary signed-in browser session."
)
GOODREADS_CHECK_ACCESS_GOODREADS_RSS_UNAVAILABLE_AN_ORDINARY_SIGNED: Final = (
    "Goodreads RSS is unavailable; an ordinary signed-in browser is needed."
)
RSS_UNAVAILABLE: Final = "rss_unavailable"
GOODREADS_CHECK_ACCESS_GOODREADS_COULD_NOT_SERVE_THE_REQUESTED_PAGE: Final = (
    "Goodreads could not serve the requested page."
)
LINK: Final = "link"
HREF: Final = "href"
GOODREADS_RSS_IDENTITY_LINKS_TEMPLATE: Final = "{v0}link"
REL: Final = "rel"
SELF: Final = "self"
GOODREADS_RSS_IDENTITY_THE_RSS_CHANNEL_IDENTIFIES_A_DIFFERENT_READER: Final = (
    "The RSS channel identifies a different reader."
)
TITLE: Final = "title"
GOODREADS_RSS_IDENTITY_BOOKSHELF_S_TO_READ_S: Final = "bookshelf:\\s*to-read\\s*$"
IDENTITY_UNVERIFIED: Final = "identity_unverified"
GOODREADS_RSS_IDENTITY_THE_RSS_CHANNEL_DOES_NOT_IDENTIFY_THE: Final = (
    "The RSS channel does not identify the configured Goodreads reader."
)
GOODREADS_RSS_IDENTITY_THE_RSS_CHANNEL_DOES_NOT_IDENTIFY_THE_2: Final = (
    "The RSS channel does not identify the to-read shelf."
)
GOODREADS_RSS_COUNT_HTTP_A9_COM_SPEC_OPENSEARCH: Final = "http://a9.com/-/spec/opensearch/1.1/"
GOODREADS_RSS_COUNT_HTTP_A9_COM_SPEC_OPENSEARCH_2: Final = "http://a9.com/-/spec/opensearch/1.0/"
GOODREADS_RSS_COUNT_TEMPLATE: Final = "{{{v0}}}totalResults"
GOODREADS_RSS_COUNT_TEXT: Final = "[0-9]{1,18}"
INVALID_COUNT: Final = "invalid_count"
GOODREADS_RSS_COUNT_THE_RSS_SHELF_COUNT_IS_INVALID: Final = "The RSS shelf count is invalid."
CONFLICTING_COUNT: Final = "conflicting_count"
GOODREADS_RSS_COUNT_GOODREADS_REPORTED_CONFLICTING_SHELF_COUNTS: Final = (
    "Goodreads reported conflicting shelf counts."
)
FIELDS_BAD_MESSAGE_TEMPLATE: Final = "Goodreads supplied an invalid or ambiguous {v0}."
INVALID_DATE: Final = "invalid_date"
FIELDS_NUMBER_PATTERN_TEXT: Final = "[0-9]+(?:\\.[0-9]+)?"
FIELDS_NUMBER_PATTERN_TEXT_2: Final = "(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)"
INVALID_NUMBER: Final = "invalid_number"
INVALID_ISBN: Final = "invalid_isbn"
FIELDS_ISBNS_MESSAGE_GOODREADS_SUPPLIED_AN_INVALID_ISBN: Final = (
    "Goodreads supplied an invalid ISBN."
)
ISBNS: Final = "isbns"
EDITION: Final = "edition"
READ: Final = "read"
CURRENTLY_READING: Final = "currently-reading"
MEMBERSHIP_CONFLICT: Final = "membership_conflict"
GOODREADS_SHELVES_A_GOODREADS_ROW_CONTRADICTS_TO_READ_MEMBERSHIP: Final = (
    "A Goodreads row contradicts to-read membership."
)
BOOK_ID: Final = "book_id"
GOODREADS_RSS_RECORD_TEXT: Final = "[0-9]+"
INVALID_RECORD: Final = "invalid_record"
GOODREADS_RSS_RECORD_A_GOODREADS_RSS_ITEM_HAS_NO_VALID: Final = (
    "A Goodreads RSS item has no valid book ID or title."
)
BOOK: Final = "book"
ID: Final = "id"
BOOK_ID_MISMATCH: Final = "book_id_mismatch"
GOODREADS_RSS_RECORD_A_GOODREADS_RSS_ITEM_S_BOOK_IDS: Final = (
    "A Goodreads RSS item's book IDs disagree."
)
GUID: Final = "guid"
ISPERMALINK: Final = "isPermaLink"
FALSE_2: Final = "false"
GOODREADS_RSS_RECORD_A_GOODREADS_RSS_ITEM_LINKS_TO_A: Final = (
    "A Goodreads RSS item links to a different resource."
)
GOODREADS_RSS_RECORD_URL_TEMPLATE: Final = "{v0}/book/show/{v1}"
ISBN: Final = "isbn"
ISBN13: Final = "isbn13"
ADDED_AT: Final = "added_at"
USER_DATE_ADDED: Final = "user_date_added"
READER: Final = "reader"
PUBLICATION_DATE: Final = "publication_date"
BOOK_PUBLISHED: Final = "book_published"
PAGE_COUNT: Final = "page_count"
GOODREADS_RSS_RECORD_BOOK_NUM_PAGES: Final = "book/num_pages"
COMMUNITY_RATING: Final = "community_rating"
AVERAGE_RATING: Final = "average_rating"
WORK: Final = "work"
GOODREADS_PERSONAL_RATING: Final = "goodreads_personal_rating"
USER_RATING: Final = "user_rating"
USER_SHELVES: Final = "user_shelves"
AUTHOR_NAME: Final = "author_name"
GOODREADS_CELL_TEMPLATE: Final = "td.field.{v0} .value"
GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_USER_SIGN_OUT: Final = "/user/sign_out"
GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_GOODREADS_COM_USER_SIGN_OUT: Final = (
    "https://www.goodreads.com/user/sign_out"
)
GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_GOODREADS_COM_USER_SIGN_OUT_2: Final = (
    "https://goodreads.com/user/sign_out"
)
GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF: Final = "a[href]"
TR: Final = "tr"
BOOKALIKE: Final = "bookalike"
ARIA_LABEL: Final = "aria-label"
GOODREADS_BROWSER_IDENTITY_OWN_MY_BOOKS: Final = "my books"
GOODREADS_BROWSER_IDENTITY_OWN_MY_PROFILE: Final = "my profile"
PROFILE: Final = "profile"
GOODREADS_BROWSER_IDENTITY_OWN_VIEW_PROFILE: Final = "view profile"
GOODREADS_BROWSER_IDENTITY_THE_BROWSER_IS_SIGNED_IN_TO_A: Final = (
    "The browser is signed in to a different Goodreads account."
)
AUTH_IDENTITY_UNVERIFIED: Final = "auth_identity_unverified"
GOODREADS_BROWSER_IDENTITY_THE_BROWSER_PAGE_DOES_NOT_VERIFY_THE: Final = (
    "The browser page does not verify the configured signed-in Goodreads reader."
)
GOODREADS_BROWSER_IDENTITY_H1_H2: Final = "h1, h2"
GOODREADS_BROWSER_IDENTITY_THE_HEADING_IDENTIFIES_ANOTHER_READER: Final = (
    "The bookshelf heading identifies another reader."
)
GOODREADS_BROWSER_COUNT_TEXT_TEXT: Final = "\u200e"
GOODREADS_BROWSER_COUNT_TEXT_TEXT_2: Final = "\u200f"
GOODREADS_BROWSER_COUNT_MATCH_TO_READ_TO_READ_WANT_TO_READ: Final = (
    "(?:to-read|to read|want to read)\\s*\\(([0-9,]+)\\)"
)
GOODREADS_BROWSER_COUNT_THE_IDENTIFIES_ANOTHER_GOODREADS_READER: Final = (
    "The shelf count identifies another Goodreads reader."
)
GOODREADS_BROWSER_COUNT_GOODREADS_SUPPLIED_INVALID_SHELF_BOOK_COUNT: Final = (
    "Goodreads supplied an invalid shelf book count."
)
UNSAFE_PAGINATION: Final = "unsafe_pagination"
GOODREADS_NEXT_LINK_GOODREADS_PAGINATION_THE_CONFIGURED_READER_S: Final = (
    "Goodreads pagination left the configured reader's shelf."
)
PAGINATION_NO_PROGRESS: Final = "pagination_no_progress"
GOODREADS_NEXT_LINK_GOODREADS_PAGINATION_DID_NOT_ADVANCE_BY_ONE: Final = (
    "Goodreads pagination did not advance by one page."
)
GOODREADS_NEXT_LINK_TEXT: Final = "[0-9]{1,3}"
GOODREADS_NEXT_LINK_GOODREADS_PAGINATION_EXCEEDED_THE_PER_PAGE_LIMIT: Final = (
    "Goodreads pagination exceeded the per-page limit."
)
NEXT: Final = "next"
GOODREADS_BROWSER_NEXT_EXPLICITLY_NEXT_NEXT_S_U203A: Final = "next(?:\\s*[\\u203a\xbb>\u2192]+)?"
GOODREADS_BROWSER_NEXT_PAGE: Final = "page="
RATING: Final = "rating"
GOODREADS_BROWSER_RATING_STARS_STATICSTARS_STATICSTAR: Final = ".staticStars .staticStar"
P10: Final = "p10"
CLASS: Final = "class"
P0: Final = "p0"
GOODREADS_BROWSER_RATING_TEXT: Final = "[0-5]"
GOODREADS_BROWSER_RECORD_A_GOODREADS_SHELF_ROW_HAS_NO_BOOK: Final = (
    "A Goodreads shelf row has no book title link."
)
GOODREADS_BROWSER_RECORD_A_GOODREADS_SHELF_ROW_HAS_NO_VALID: Final = (
    "A Goodreads shelf row has no valid book ID or title."
)
AUTHOR: Final = "author"
DATE_ADDED: Final = "date_added"
GOODREADS_BROWSER_RECORD_ADDED_SPAN_SPAN_TITLE: Final = "span[title]"
DATE_PUB: Final = "date_pub"
FIRST_PUBLICATION_YEAR: Final = "first_publication_year"
DATE_PUB_EDITION: Final = "date_pub_edition"
NUM_PAGES: Final = "num_pages"
GOODREADS_BROWSER_RECORD_PAGES_S_PP_PAGES_S: Final = "\\s*(?:pp|pages)\\.?\\s*$"
AVG_RATING: Final = "avg_rating"
COMMUNITY_RATINGS_COUNT: Final = "community_ratings_count"
NUM_RATINGS: Final = "num_ratings"
SHELF_POSITION: Final = "shelf_position"
POSITION: Final = "position"
SHELVES: Final = "shelves"
GOODREADS_BROWSER_RECORD_SHELF: Final = "shelf="
GOODREADS_BROWSER_RECORD_A_SHELF_ROW_IDENTIFIES_A_DIFFERENT_READER: Final = (
    "A shelf row identifies a different reader."
)
GOODREADS_BROWSER_RECORD_A_GOODREADS_ROW_HAS_AN_INVALID_SHELF: Final = (
    "A Goodreads row has an invalid shelf link."
)
FORMAT: Final = "format"
GOODREADS_GOODREADSCONNECTOR_INIT_MAX_PAGES_BE_A_POSITIVE_INTEGER: Final = (
    "max_pages must be a positive integer"
)
GOODREADS_GOODREADSCONNECTOR_COLLECT_GOODREADS_READER_ACCOUNT: Final = (
    "GoodreadsConnector requires a Goodreads reader account"
)
COUNT_MISMATCH: Final = "count_mismatch"
GOODREADSCONNECTOR_COLLECT_MESSAGE_THE_COUNT_DOES_NOT_MATCH: Final = (
    "The collected book count does not match the Goodreads shelf count."
)
WATCHLIST: Final = "watchlist"
REVIEWS: Final = "reviews"
ORIGINAL_SHELF_TRANSITION_DATE: Final = "original_shelf_transition_date"
GOODREADS_GOODREADSCONNECTOR_WALK_GOODREADS_A_TRANSPORT_OR_ENCODING: Final = (
    "Goodreads collection had a transport or encoding failure."
)
TRANSPORT_ERROR: Final = "transport_error"
SHELF_CHANGED: Final = "shelf_changed"
GOODREADSCONNECTOR_WALK_MESSAGE_THE_COUNT_CHANGED_DURING_PAGING: Final = (
    "The Goodreads shelf count changed during paging."
)
DUPLICATE_RECORD: Final = "duplicate_record"
GOODREADSCONNECTOR_WALK_MESSAGE_A_GOODREADS_OCCURRED_MORE_THAN_ONCE: Final = (
    "A Goodreads book occurred more than once while paging."
)
EMPTY_PAGE_GAP: Final = "empty_page_gap"
GOODREADS_GOODREADSCONNECTOR_WALK_AN_EMPTY_PAGE_STILL_LINKS_ONWARD: Final = (
    "An empty Goodreads page still links onward."
)
EMPTY_SHELF_UNVERIFIED: Final = "empty_shelf_unverified"
GOODREADS_GOODREADSCONNECTOR_WALK_AN_INITIAL_BROWSER_TABLE_HAS_NO: Final = (
    "An initial empty browser table has no verified zero-book shelf count."
)
GOODREADSCONNECTOR_WALK_MESSAGE_GOODREADS_PAGE_OR_SUPPLIED_NO: Final = (
    "Goodreads repeated a page or supplied no new usable books."
)
RSS: Final = "RSS"
BROWSER: Final = "browser"
GOODREADSCONNECTOR_WALK_MESSAGE_TEMPLATE: Final = "Checked Goodreads {v0} page {v1}."
PAGE_LIMIT: Final = "page_limit"
GOODREADSCONNECTOR_WALK_MESSAGE_GOODREADS_THE_CONFIGURED_PAGE_LIMIT: Final = (
    "Goodreads collection reached the configured page limit."
)
GOODREADSCONNECTOR_RSS_PAGE_URL_TEMPLATE: Final = "{v0}/review/list_rss/{v1}"
ACCEPT: Final = "Accept"
RSS_PAGE_RESPONSE_HEADERS_APPLICATION_RSS_XML_APPLICATION_XML_Q: Final = (
    "application/rss+xml, application/xml;q=0.9"
)
PAGE_TOO_LARGE: Final = "page_too_large"
GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_THE_RESPONSE_SIZE_LIMIT: Final = (
    "Goodreads RSS exceeded the response-size limit."
)
UTF_8_SIG: Final = "utf-8-sig"
REPLACE: Final = "replace"
UNSAFE_XML: Final = "unsafe_xml"
GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_A_FORBIDDEN_XML_DECLARATION: Final = (
    "Goodreads RSS contained a forbidden XML declaration."
)
MALFORMED_XML: Final = "malformed_xml"
GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_GOODREADS_NOT_WELL_FORMED_XML: Final = (
    "Goodreads RSS was not well-formed XML."
)
RSS_2: Final = "rss"
CHANNEL: Final = "channel"
UNSUPPORTED_FEED: Final = "unsupported_feed"
GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_RETURN_A_RECOGNIZED_RSS: Final = (
    "Goodreads did not return a recognized RSS channel."
)
ITEM: Final = "item"
GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_GOODREADS_THE_BOOK_PAGE_LIMIT: Final = (
    "Goodreads RSS exceeded the 100-book page limit."
)
GOODREADS_GOODREADSCONNECTOR_BROWSER_PAGE_THE_RESPONSE_SIZE_LIMIT: Final = (
    "Goodreads HTML exceeded the response-size limit."
)
GOODREADSCONNECTOR_BROWSER_PAGE_TABLE_TABLE_BOOKS: Final = "table#books"
TR_BOOKALIKE: Final = "tr.bookalike"
GOODREADSCONNECTOR_BROWSER_PAGE_BODY_TABLE_BOOKS_TBODY_BOOKSBODY: Final = (
    "table#books tbody#booksBody"
)
UNKNOWN_MARKUP: Final = "unknown_markup"
GOODREADS_GOODREADSCONNECTOR_BROWSER_PAGE_TABLE_WAS_NOT_RECOGNIZED: Final = (
    "The Goodreads shelf table was not recognized."
)
GOODREADS_GOODREADSCONNECTOR_BROWSER_PAGE_THE_BOOK_PAGE_LIMIT: Final = (
    "Goodreads HTML exceeded the 100-book page limit."
)
STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM: Final = "https://app.thestorygraph.com"
STORYGRAPH_BOOK_PATH_BOOKS_A_ZA_Z0_A_ZA_Z0: Final = "/books/([A-Za-z0-9][A-Za-z0-9_-]*)/?$"
STORYGRAPH_PROFILE_PATH_PROFILE: Final = "/profile/([^/]+)/?$"
BOOKS_READ: Final = "books-read"
REVIEW: Final = "review"
READING_EVENTS: Final = "reading_events"
READ_COUNT: Final = "read_count"
MOODS: Final = "moods"
PACE: Final = "pace"
TAGS: Final = "tags"
CONTENT_WARNINGS: Final = "content_warnings"
STORYGRAPH_STATUS_NAMES_BOOKS_READ: Final = "books read"
STORYGRAPH_STATUS_NAMES_CURRENTLY_READING: Final = "currently reading"
READING: Final = "reading"
PAUSED: Final = "paused"
STORYGRAPH_STATUS_NAMES_PAUSED_BOOKS: Final = "paused books"
STORYGRAPH_STATUS_NAMES_DID_NOT_FINISH: Final = "did not finish"
STORYGRAPH_STATUS_NAMES_DIDN_T_FINISH: Final = "didn't finish"
DNF: Final = "dnf"
STORYGRAPH_STATUS_NAMES_TO_READ: Final = "to read"
STORYGRAPH_STATUS_NAMES_TO_BE_READ: Final = "to be read"
STORYGRAPH_LABELS_STAR_RATING: Final = "star rating"
STORYGRAPH_LABELS_WRITTEN_REVIEW: Final = "written review"
MOOD: Final = "mood"
PACING: Final = "pacing"
STORYGRAPH_LABELS_CONTENT_WARNINGS: Final = "content warnings"
STORYGRAPH_LABELS_READ_COUNT: Final = "read count"
STORYGRAPH_LABELS_TIMES_READ: Final = "times read"
STORYGRAPH_LABELS_READING_STATUS: Final = "reading status"
STARTED: Final = "started"
STORYGRAPH_LABELS_STARTED_ON: Final = "started on"
STORYGRAPH_LABELS_START_DATE: Final = "start date"
STORYGRAPH_LABELS_DATE_STARTED: Final = "date started"
FINISHED: Final = "finished"
STORYGRAPH_LABELS_FINISHED_ON: Final = "finished on"
STORYGRAPH_LABELS_FINISH_DATE: Final = "finish date"
STORYGRAPH_LABELS_DATE_FINISHED: Final = "date finished"
STORYGRAPH_LABELS_DATE_READ: Final = "date read"
STORYGRAPH_LABELS_ISBN: Final = "isbn 13"
STORYGRAPH_LABELS_ISBN_2: Final = "isbn 10"
LANGUAGE: Final = "language"
EDITION_FORMAT: Final = "edition_format"
HIDDEN: Final = "hidden"
ARIA_HIDDEN: Final = "aria-hidden"
TRUE_2: Final = "true"
STORYGRAPH_VISIBLE_DISPLAY_S_S_NONE_VISIBILITY_S_S: Final = (
    "(?:display\\s*:\\s*none|visibility\\s*:\\s*hidden)"
)
STYLE: Final = "style"
SCRIPT: Final = "script"
TEMPLATE: Final = "template"
STORYGRAPH_LABEL_S: Final = "\\s+"
HYPHEN: Final = "-"
STORYGRAPH_LABEL_TEXT: Final = " :"
STORYGRAPH_FIELD_LABEL_PERSONAL_YOUR: Final = "your "
STORYGRAPH_FIELD_LABEL_PERSONAL_MY: Final = "my "
STORYGRAPH_SAFE_URL_A_STORYGRAPH_LINK_LEFT_THE_APPROVED_HTTPS: Final = (
    "A StoryGraph link left the approved HTTPS origin."
)
UNSAFE_SOURCE_LINK: Final = "unsafe_source_link"
STORYGRAPH_SAFE_URL_EXPORTS_DOWNLOADS: Final = "(?:^|[/_.-])(?:exports?|downloads?)(?:[/_.-]|$)"
EXPORT: Final = "export"
STORYGRAPH_SAFE_URL_STORYGRAPH_EXPORT_DOWNLOAD_LINKS_ARE_DISABLED: Final = (
    "StoryGraph export and download links are disabled."
)
SLASH: Final = "/"
STORYGRAPH_IDENTITY_HAS_LOGOUT_LOG_OUT: Final = "log out"
LOGOUT: Final = "logout"
STORYGRAPH_IDENTITY_HAS_LOGOUT_SIGN_OUT: Final = "sign out"
STORYGRAPH_IDENTITY_HAS_LOGOUT_USERS_SIGN_OUT: Final = "/users/sign_out"
A: Final = "a"
NAV: Final = "nav"
HEADER: Final = "header"
ROLE: Final = "role"
NAVIGATION: Final = "navigation"
STORYGRAPH_IDENTITY_YOUR_PROFILE: Final = "your profile"
STORYGRAPH_IDENTITY_THE_AUTHENTICATED_OWNER_DOES_NOT_MATCH: Final = (
    "The authenticated StoryGraph owner does not match the configured account."
)
WRONG_ACCOUNT: Final = "wrong_account"
STORYGRAPH_IDENTITY_THE_AUTHENTICATED_STORYGRAPH_OWNER_COULD_NOT_BE: Final = (
    "The authenticated StoryGraph owner could not be verified. Use interactive ow"
    "ner login; unknown account markup must be verified before collection."
)
OWNER_IDENTITY_UNAVAILABLE: Final = "owner_identity_unavailable"
USER: Final = "user"
USERNAME: Final = "username"
USER_ID: Final = "user_id"
ACCOUNT: Final = "account"
OWNER: Final = "owner"
BOOKS: Final = "books"
AUTHORS: Final = "authors"
USERS: Final = "users"
NEXT_LINK: Final = "next_link"
GET_2: Final = "get"
DATA_METHOD: Final = "data-method"
DATA_TURBO_METHOD: Final = "data-turbo-method"
STORYGRAPH_DISCOVER_SURFACES_LABEL_S_D_S: Final = "\\s*[\\[(]?\\d+[\\])]?\\s*$"
STORYGRAPH_DISCOVER_SURFACES_NO_PAUSED_BOOKS_PAUSED_BOOKS_YOU_HAVE: Final = (
    "(?:no paused books|0 paused books|you have no books paused)[.!]?"
)
STORYGRAPH_DISCOVER_SURFACES_NO_DID_NOT_FINISH_BOOKS_DID_NOT: Final = (
    "(?:no did not finish books|0 did not finish books|no dnf books)[.!]?"
)
P: Final = "p"
H1: Final = "h1"
H2: Final = "h2"
H3: Final = "h3"
TRIX_CONTENT: Final = "trix-content"
AVERAGE_STAR_RATING: Final = "average-star-rating"
ITEMPROP: Final = "itemprop"
REVIEWBODY: Final = "reviewBody"
COMMENTTEXT: Final = "commentText"
ARTICLE: Final = "article"
SECTION: Final = "section"
H4: Final = "h4"
COMMUNITY: Final = "community"
DT: Final = "dt"
DD: Final = "dd"
TIME: Final = "time"
DATETIME: Final = "datetime"
LI: Final = "li"
SPAN: Final = "span"
OUTPUT: Final = "output"
STORYGRAPH_PAIRS_MATCH_N_S: Final = "([^:\\n]{1,40}):\\s*(.*)"
UNRATED: Final = "unrated"
STORYGRAPH_RATING_NOT_RATED: Final = "not rated"
STORYGRAPH_RATING_NO_RATING: Final = "no rating"
NONE_2: Final = "none"
STORYGRAPH_RATING_MATCH_YOUR_MY_STAR_RATING_S_D_D: Final = (
    "(?:(?:your |my )?(?:star )?rating:?\\s*)?(\\d+(?:\\.\\d+)?)\\s*(?:(?:/|out o"
    "f)\\s*5)?\\s*(?:stars?)?"
)
DIV: Final = "div"
H5: Final = "h5"
H6: Final = "h6"
STORYGRAPH_OWNER_REGIONS_EXPLICIT_RATING_READING_HISTORY_READING: Final = (
    "(?:your|my) (?:review|rating|reading history|reading activity|reading journa"
    "l|book details|tags|content warnings)"
)
STORYGRAPH_OWNER_REGIONS_AUTHORED_ITEMPROP_REVIEWBODY: Final = "[itemprop='reviewBody']"
STORYGRAPH_OWNER_REGIONS_AUTHORED_READING_HISTORY: Final = "reading history"
STORYGRAPH_OWNER_REGIONS_A_PERSONAL_SECTION_BELONGS_TO_ANOTHER: Final = (
    "A personal StoryGraph section belongs to another reader."
)
REVIEW_OWNER_MISMATCH: Final = "review_owner_mismatch"
TABLE: Final = "table"
TH: Final = "th"
TD: Final = "td"
DL: Final = "dl"
STORYGRAPH_EVENTS_B_NO_READING_HISTORY_NO_READS_YET: Final = (
    "\\b(?:no reading history|no reads yet|no reading events)\\b"
)
UNKNOWN_READING_STATUS: Final = "unknown_reading_status"
STORYGRAPH_EVENTS_MESSAGE_A_READING_STATUS_WAS_NOT_RECOGNIZED: Final = (
    "A reading-history status was not recognized."
)
INVALID_READING_DATE: Final = "invalid_reading_date"
STORYGRAPH_EVENTS_MESSAGE_A_READING_EVENT_HAS_AN_INVALID_AMBIGUOUS: Final = (
    "A reading event has an invalid, ambiguous, or reversed date."
)
JSON: Final = "json"
STORYGRAPH_PERSONAL_ITEMPROP_RATINGVALUE_ARIA_LABEL: Final = (
    "[itemprop='ratingValue'], [aria-label]"
)
RATINGVALUE: Final = "ratingValue"
STORYGRAPH_PERSONAL_D_D_OUT_OF_STARS: Final = "\\d+(?:\\.\\d+)? (?:out of 5 )?stars?"
STORYGRAPH_PERSONAL_BODY_TRIX_CONTENT: Final = ".trix-content"
STORYGRAPH_PERSONAL_B_NO_WRITTEN_REVIEW_YOU_HAVEN_T: Final = (
    "\\b(?:no written review|you haven't written a review|you have not written a review)\\b"
)
STORYGRAPH_PERSONAL_COUNT_BREAD_D_TIMES_B: Final = "\\bread (\\d+) times?\\b"
INVALID_PERSONAL_RATING: Final = "invalid_personal_rating"
STORYGRAPH_PERSONAL_MESSAGE_THE_VISIBLE_PERSONAL_RATING_COULD_NOT_BE: Final = (
    "The visible personal rating could not be interpreted safely."
)
STORYGRAPH_PERSONAL_D: Final = "\\d+"
INVALID_READ_COUNT: Final = "invalid_read_count"
STORYGRAPH_PERSONAL_MESSAGE_THE_VISIBLE_READ_COUNT_COULD_NOT: Final = (
    "The visible personal read count could not be interpreted."
)
STORYGRAPH_PERSONAL_EMPTY_NO_TAGS: Final = "no tags"
STORYGRAPH_PERSONAL_EMPTY_NO_CONTENT_WARNINGS: Final = "no content warnings"
STORYGRAPH_PERSONAL_EMPTY_NO_MOODS: Final = "no moods"
STORYGRAPH_PERSONAL_ENTRIES_N: Final = "[,;\\n]"
STATUSES: Final = "statuses"
COLLECTIONS: Final = "collections"
RAW_STATUS: Final = "raw_status"
OBSERVATIONS: Final = "observations"
DETAIL_CHECKED_AT: Final = "detail_checked_at"
STORYGRAPH_MERGE_UPDATE_TEXT: Final = "; "
STORYGRAPH_BOOK_CARD_BOOK_TITLE_AUTHOR_AND_SERIES: Final = ".book-title-author-and-series"
STORYGRAPH_PERSONAL_LINKS_YOUR_REVIEW: Final = "your review"
STORYGRAPH_PERSONAL_LINKS_MY_REVIEW: Final = "my review"
STORYGRAPH_PERSONAL_LINKS_VIEW_YOUR_REVIEW: Final = "view your review"
STORYGRAPH_PERSONAL_LINKS_READ_YOUR_REVIEW: Final = "read your review"
STORYGRAPH_PERSONAL_LINKS_YOUR_READING_HISTORY: Final = "your reading history"
STORYGRAPH_PERSONAL_LINKS_MY_READING_HISTORY: Final = "my reading history"
STORYGRAPH_PERSONAL_LINKS_YOUR_READING_JOURNAL: Final = "your reading journal"
STORYGRAPH_PERSONAL_LINKS_YOUR_READING_ACTIVITY: Final = "your reading activity"
HISTORY: Final = "history"
STORYGRAPH_PERSONAL_LINKS_YOUR_BOOK_DETAILS: Final = "your book details"
STORYGRAPH_PERSONAL_LINKS_MY_BOOK_DETAILS: Final = "my book details"
DETAILS: Final = "details"
EDIT: Final = "edit"
NEW: Final = "new"
DELETE: Final = "delete"
STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_READ_BOOKS: Final = ".read-books"
STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_TO_READ_BOOKS: Final = ".to-read-books"
STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_PAUSED_BOOKS_READ_BOOKS: Final = ".paused-books, .read-books"
MAIN: Final = "main"
STORYGRAPH_STORYGRAPHCONNECTOR_LIST_PAGE_CONTAINER_WAS_MISSING: Final = (
    "The expected StoryGraph collection container was missing or ambiguous."
)
COLLECTION_LAYOUT_UNAVAILABLE: Final = "collection_layout_unavailable"
BOOK_IDENTITY_MISSING: Final = "book_identity_missing"
STORYGRAPHCONNECTOR_LIST_PAGE_MESSAGE_A_ENTRY_LACKED_A_BOOK_IDENTITY: Final = (
    "A list entry lacked a book identity or title."
)
STORYGRAPHCONNECTOR_LIST_PAGE_AUTHORS_AUTHORS: Final = "/authors/"
STORYGRAPH_STORYGRAPHCONNECTOR_LIST_PAGE_B_BOOKS_BOOKS_NO_READS_YET: Final = (
    "\\b(?:no books|0 books|no reads yet|haven't (?:read|added)|have not (?:read|added))\\b"
)
STORYGRAPH_STORYGRAPHCONNECTOR_LIST_PAGE_CONTAINER_DID_NOT_PROVIDE: Final = (
    "An empty StoryGraph container did not provide an explicit empty-list state."
)
EMPTY_COLLECTION_UNVERIFIED: Final = "empty_collection_unverified"
STORYGRAPHCONNECTOR_NEXT_CANDIDATES_A_NEXT_LINK_HREF_A_REL_NEXT: Final = (
    "a#next_link[href], a[rel~='next'][href]"
)
ARIA_DISABLED: Final = "aria-disabled"
STORYGRAPH_STORYGRAPHCONNECTOR_NEXT_STORYGRAPH_LINKS_WERE_AMBIGUOUS: Final = (
    "StoryGraph pagination links were ambiguous."
)
PAGINATION_AMBIGUOUS: Final = "pagination_ambiguous"
STORYGRAPH_STORYGRAPHCONNECTOR_NEXT_A_CHANGED_COLLECTION_OR_ACCOUNT: Final = (
    "A pagination link changed collection or account."
)
PAGINATION_OWNER_MISMATCH: Final = "pagination_owner_mismatch"
HISTORY_PAGINATION_LIMIT: Final = "history_pagination_limit"
STORYGRAPHCONNECTOR_DETAIL_MESSAGE_THE_PAGE_LIMIT_WAS_REACHED: Final = (
    "The reading-history page limit was reached."
)
VALUE: Final = "value"
DETAIL_LINK_LIMIT: Final = "detail_link_limit"
STORYGRAPHCONNECTOR_DETAIL_MESSAGE_LINKS_REMAIN_UNVERIFIED: Final = (
    "Additional personal detail links remain unverified."
)
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_A_LINK_CHANGED_READER_IDENTITY: Final = (
    "A personal link changed reader identity."
)
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_A_CHANGED_BOOK_IDENTITY: Final = (
    "A book detail redirect changed book identity."
)
BOOK_IDENTITY_MISMATCH: Final = "book_identity_mismatch"
STORYGRAPHCONNECTOR_DETAIL_ASSOCIATED_IDS_BOOK_AND_SERIES_A_HREF: Final = (
    ".book-title-author-and-series a[href]"
)
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_THE_DID_NOT_VERIFY_BOTH: Final = (
    "The personal page did not verify both reader and book."
)
PERSONAL_PAGE_IDENTITY_UNAVAILABLE: Final = "personal_page_identity_unavailable"
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_A_HISTORY_PAGE_REPEATED: Final = (
    "A reading-history page repeated."
)
HISTORY_REPEATED_PAGE: Final = "history_repeated_page"
STORYGRAPHCONNECTOR_DETAIL_MESSAGE_A_VISIBLE_ISBN_FAILED_VALIDATION: Final = (
    "A visible ISBN failed validation."
)
STORYGRAPHCONNECTOR_DETAIL_TAGS_BOOK_PAGE_TAG_SECTION_SPAN: Final = ".book-page-tag-section span"
BOOK_TAGS: Final = "book_tags"
STORYGRAPHCONNECTOR_DETAIL_COMMUNITY_AVERAGE_STAR_RATING: Final = ".average-star-rating"
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_PAGINATION_WAS_AMBIGUOUS: Final = (
    "Reading-history pagination was ambiguous."
)
HISTORY_PAGINATION_AMBIGUOUS: Final = "history_pagination_ambiguous"
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_READING_CHANGED_ITS_SURFACE: Final = (
    "Reading-history pagination changed its surface."
)
HISTORY_PAGINATION_IDENTITY: Final = "history_pagination_identity"
STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_READING_REPEATED_A_CURSOR: Final = (
    "Reading-history pagination repeated a cursor."
)
HISTORY_REPEATED_CURSOR: Final = "history_repeated_cursor"
COLLECT_PROGRESS_MESSAGE_TEMPLATE: Final = "Collected {v0} distinct books from {v1} list pages."
STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_A_STORYGRAPH_ACCOUNT: Final = (
    "StoryGraph requires a StoryGraph account."
)
WRONG_SOURCE: Final = "wrong_source"
STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_THE_CHANGED_ACCOUNT_IDENTITY: Final = (
    "The profile redirect changed account identity."
)
STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_TEMPLATE: Final = "{v0}/{v1}/{v2}"
PAGINATION_LIMIT: Final = "pagination_limit"
STORYGRAPHCONNECTOR_COLLECT_MESSAGE_THE_PAGE_LIMIT_WAS_REACHED: Final = (
    "The configured collection-page limit was reached."
)
PAGINATION_REPEATED_CURSOR: Final = "pagination_repeated_cursor"
STORYGRAPHCONNECTOR_COLLECT_MESSAGE_A_PAGINATION_CURSOR_REPEATED: Final = (
    "A StoryGraph pagination cursor repeated."
)
STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_A_ACCOUNT_OR_COLLECTION: Final = (
    "A collection redirect changed account or collection."
)
STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_COLLECTION_PAGE_CONTENT: Final = (
    "StoryGraph repeated collection-page content."
)
PAGINATION_REPEATED_PAGE: Final = "pagination_repeated_page"
STORYGRAPHCONNECTOR_COLLECT_CURSOR_TEMPLATE: Final = "{v0}:{v1}"
COLLECTION_NOT_EXPOSED: Final = "collection_not_exposed"
STORYGRAPHCONNECTOR_COLLECT_MESSAGE_TEMPLATE: Final = (
    "The {v0} collection or an explicit empty state was not exposed."
)
READING_EVENTS_INCOMPLETE: Final = "reading_events_incomplete"
STORYGRAPHCONNECTOR_COLLECT_MESSAGE_THE_COUNT_DIFFERS_FROM_THE: Final = (
    "The personal read count differs from the exposed completed reading events; n"
    "o dates were synthesized."
)
STORYGRAPHCONNECTOR_COLLECT_CAPABILITIES_TEMPLATE: Final = "collection.{v0}"
OWNER_IDENTITY: Final = "owner_identity"
COVERAGE_INCOMPLETE: Final = "coverage_incomplete"
STORYGRAPHCONNECTOR_COLLECT_MESSAGE_COLLECTION_COVERAGE_REMAIN: Final = (
    "Required private fields or collection coverage remain unverified; missing va"
    "lues are not empty values."
)
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
GOOGLE_BOOKS_FIELDS_TOTALITEMS_TITLE_AUTHORS_INDUSTRYIDENTIFIERS: Final = (
    "totalItems,items(id,volumeInfo(title,authors,industryIdentifiers,description"
    ",categories,language,pageCount,publishedDate,averageRating,ratingsCount))"
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
LOOKUP_ISSUES_MESSAGE_GOOGLE_BOOKS_REQUIRES_AN_APPLICATION_API_KEY: Final = (
    "Google Books requires an application API key for catalog lookup."
)
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
OPEN_LIBRARY_FIELDS_KEY_TITLE_AUTHOR_NAME_ISBN_SUBJECT_LANGUAGE: Final = (
    "key,title,author_name,isbn,subject,language,first_publish_year,number_of_pag"
    "es_median,ratings_average,ratings_count"
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
TASK_NAME: Final = "task_name"
ENABLED_AT: Final = "enabled_at"
WEEKDAY: Final = "weekday"
TIMEZONE: Final = "timezone"
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
    "   identity_hash TEXT NOT NULL,\n    raw_json TEXT NOT NULL\n);\nCREATE INDE"
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
    "tity_hash, raw_json) VALUES (?, ?, ?, ?, ?, ?)"
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
DATABASE_ENRICHMENT_TARGETS_ROWS_SELECT_JSON_FROM_SOURCE_RECORDS: Final = (
    "SELECT r.latest_json FROM source_records r LEFT JOIN enrichment_attempts a O"
    "N a.id = (SELECT MAX(a2.id) FROM enrichment_attempts a2 WHERE a2.record_id ="
    " r.id AND a2.provider = ?) WHERE EXISTS (SELECT 1 FROM memberships m WHERE m"
    ".record_id = r.id) AND (a.id IS NULL OR a.state != ? OR a.checked_at < ? OR "
    "a.identity_hash != r.identity_hash)"
    " ORDER BY (a.id IS NOT NULL), a.checked_at, a.id,"
    " r.source, r.account_id, r.source_id LIMIT ?"
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
TEST_BROWSER_ORIGIN_TEMPLATE: Final = "https://{v0}"
TEST_BROWSER_URL_TEMPLATE: Final = "{v0}/profile/alice"
TEST_BROWSER_LOGIN_HTML_FORM_ACTION_USERS_SIGN_IN_INPUT: Final = (
    '<html><form action="/users/sign_in"><input type="password"></form></html>'
)
TEST_BROWSER_AUTHENTICATED_HTML_NAV_A_HREF_PROFILE_ALICE_YOUR: Final = (
    '<html><nav><a href="/profile/alice">Your profile</a></nav></html>'
)
PAGE_INIT_ABOUT_BLANK: Final = "about:blank"
TEST_BROWSER_PAGE_GOTO_HTTPS_EXAMPLE_INVALID_TOKEN_DO_NOT_LOG: Final = (
    "https://example.invalid/?token=DO-NOT-LOG"
)
IMPORT_MODULE: Final = "import_module"
TEST_BROWSER_DRIVER_PREPARE_PROFILE: Final = "_prepare_profile"
TESTS: Final = "tests"
FIXTURES: Final = "fixtures"
STORYGRAPH: Final = "storygraph"
UNUSED_PROFILE: Final = "unused-profile"
USER_DATA_DIR: Final = "user_data_dir"
HEADLESS: Final = "headless"
ACCEPT_DOWNLOADS: Final = "accept_downloads"
SERVICE_WORKERS: Final = "service_workers"
CHROMIUM_SANDBOX: Final = "chromium_sandbox"
TIMEOUT: Final = "timeout"
MAX_REDIRECTS: Final = "max_redirects"
HTML: Final = "html"
TEST_BROWSER_UNATTENDED_AUTH_AND_TITLE_JUST_A_MOMENT_TITLE: Final = (
    "<title>Just a moment...</title>"
)
BUILTINS_INPUT: Final = "builtins.input"
TEST_BROWSER_UNATTENDED_AUTH_AND_PROMPT_NO_CONSOLE_INPUT_PERMITTED: Final = (
    "No console input permitted"
)
PRIVATE_CONTENT: Final = "private-content"
TEST_INTERACTIVE_OWNER_LOGIN_IS_NAVIGATION_LOGGED_IN_TEMPLATE: Final = "{v0}/home"
TEST_BROWSER_INTERACTIVE_OWNER_NAVIGATION_VISIBLE_SOURCE_BROWSE: Final = "visible source browser"
MONOTONIC: Final = "monotonic"
TEST_BROWSER_INTERACTIVE_CHALLENGE_IS_CHALLENGE_FORM_CHALLENGE_FORM: Final = (
    '<form id="challenge-form">Challenge</form>'
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_THESTORYGRAPH_COM_PROFILE_ALICE: Final = (
    "http://app.thestorygraph.com/profile/alice"
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_APP_THESTORYGRAPH_COM_EVIL_EXAMPLE: Final = (
    "https://app.thestorygraph.com.evil.example/"
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_EVIL_EXAMPLE: Final = "https://evil.example/"
TEST_BROWSER_UNSAFE_URLS_REJECTED_HTTPS_APP_THESTORYGRAPH_COM: Final = (
    "https://app.thestorygraph.com:444/"
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_PASSWORD_APP_THESTORYGRAPH_COM: Final = (
    "https://user:password@app.thestorygraph.com/"
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_APP_THESTORYGRAPH_COM_EVIL_EXAMPLE_2: Final = (
    "https://app.thestorygraph.com\\@evil.example/"
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_HTTPS_APP_THESTORYGRAPH_COM_2: Final = (
    "https://app.thestorygraph.com./"
)
TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_MALFORMED: Final = "https://[malformed"
TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_TEMPLATE: Final = "{v0}/exports"
TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_TEMPLATE_2: Final = "{v0}/%65xport"
TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_TEMPLATE_3: Final = "{v0}/books?download=true"
TEST_BROWSER_SAFE_REDIRECT_SEPARATELY_VALIDATED_REDIRECTED_TEMPLATE: Final = (
    "{v0}/profile/alice?ref=normal"
)
TEST_EXTERNAL_REDIRECT_IS_BLOCKED_BEFORE_HTTPS_EVIL_EXAMPLE_TOKEN_DO: Final = (
    "https://evil.example/?token=DO-NOT-LOG"
)
DO_NOT_LOG: Final = "DO-NOT-LOG"
TEST_BROWSER_LATER_REDIRECT_HOP_HOST_VALIDATION_SECOND_TEMPLATE: Final = "{v0}/intermediate"
TEST_BROWSER_EXPORT_SUBRESOURCES_ARE_BLOCKED_EXPORT_TEMPLATE: Final = "{v0}/export?format=csv"
TEST_BROWSER_EXPORT_SUBRESOURCES_ARE_BLOCKED_MUTATION_TEMPLATE: Final = "{v0}/reviews/new"
TEST_EXPORT_SUBRESOURCES_MUTATIONS_AND_HEADERS_ATTACHMENT_FILENAME_L: Final = (
    "attachment; filename=library.csv"
)
TEST_BROWSER_ONLY_DISCOVERED_OWNER_LOGIN_FORM_CAN_SUBMIT_TEMPLATE: Final = "{v0}/users/sign_in"
TEST_BROWSER_BROWSER_ERRORS_ARE_TYPED_RAW_MESSAGES_TOKEN_DO_NOT_LOG: Final = "token=DO-NOT-LOG"
TEST_BROWSER_BROWSER_ERRORS_ARE_TYPED_MESSAGES_COOKIES_DO_NOT_LOG: Final = "cookies=DO-NOT-LOG"
TEST_BROWSER_MISSING_DEPENDENCIES_INSTALLED_UNAVAILABLE_SECRET_DEPEN: Final = (
    "secret dependency path"
)
TEST_BROWSER_MISSING_DEPENDENCIES_INSTALLED_PLAYWRIGHT_INSTALL_CHROM: Final = (
    "playwright install chromium"
)
TEST_BROWSER_MISSING_BROWSER_BINARY_IS_ERROR_EXECUTABLE_DOESN_T_EXIS: Final = (
    "Executable doesn't exist at private-user-directory"
)
PRIVATE_USER_DIRECTORY: Final = "private-user-directory"
CLOSED: Final = "closed"
TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_INSTALL_CHROMIUM_WITH: Final = (
    "Install Chromium with python -m playwright install chromium for this check"
)
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_BOOKY: Final = "booky_test=1"
COOKIE: Final = "Cookie"
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_START: Final = "/start"
LOCATION_2: Final = "Location"
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_PAGE: Final = "/page"
SET_COOKIE: Final = "Set-Cookie"
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_BOOKY_PATH_MAX: Final = (
    "booky_test=1; Path=/; Max-Age=3600; HttpOnly"
)
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_UNSAFE: Final = "/unsafe"
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_DO_GET_HTTPS_EVIL_EXAMPLE_T: Final = (
    "https://evil.example/?token=never-follow"
)
HANDLER_DO_GET_BODY_BYTES: Final = b"<html><body><main>Local browser fixture</main></body></html>"
CONTENT_TYPE_2: Final = "Content-Type"
TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_TEXT_HTML: Final = "text/html"
CONTENT_LENGTH_2: Final = "Content-Length"
TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_SERVER_TEXT: Final = "127.0.0.1"
TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_ORIGIN_TEMPLATE: Final = "http://127.0.0.1:{v0}"
TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_PROFILE_TEMPLATE: Final = ".browser-check-{v0}"
TEST_BROWSER_REAL_BROWSER_LOCAL_NETWORK_LOCAL_ONLY_LOCAL_FIXTU: Final = (
    "Local fixture redirect refused."
)
TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_CHECKED_URL: Final = "_checked_url"
TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_DOCUMENT_TEMPLATE: Final = "{v0}/start"
TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_TEMPLATE: Final = "{v0}/page"
TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_TEMPLATE_2: Final = "{v0}/unsafe"
BOOKYSTATS_CACHE_UTC_TIMESTAMP: Final = "bookystats.cache._utc_timestamp"
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
TEST_CLI_UNATTENDED_WITHOUT_ACCOUNTS_NEVER_PROMPTS_NO_EXPORTS: Final = "No exports"
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
TEST_GOODREADS_FEED_IDENTITY_TEMPLATE: Final = "{v0}/review/list/4242?shelf={v1}"
TEST_GOODREADS_FEED_TEMPLATE: Final = (
    '<rss version="2.0"><channel><title>Reader&apos;s bookshelf: {v0}</title><lin'
    "k>{v1}</link>{v2}</channel></rss>"
)
TEST_GOODREADS_ITEM_BOOK_ID_TEXT: Final = "1001"
TEST_GOODREADS_ITEM_TITLE_TOILES: Final = "\xc9toiles"
TEST_GOODREADS_ITEM_TEMPLATE: Final = (
    "<item><book_id>{v0}</book_id><title>{v1}</title><author_name>Jos\xe9 \xc1lva"
    "res</author_name>{v2}</item>"
)
TEST_GOODREADS_WITH_COUNT_CHANNEL: Final = "</channel>"
TEST_GOODREADS_WITH_COUNT_TEMPLATE: Final = (
    '<opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1'
    '.1/">{v0}</opensearch:totalResults></channel>'
)
TEST_GOODREADS_FAKEHTTP_FETCH_UNEXPECTED_HTTP_FETCH: Final = "unexpected HTTP fetch"
TEST_GOODREADS_FAKEHTTP_FETCH_APPLICATION_RSS_XML: Final = "application/rss+xml"
TEST_GOODREADS_FAKEBROWSER_FETCH_UNEXPECTED_BROWSER_FETCH: Final = "unexpected browser fetch"
TEST_GOODREADS_ACCOUNT_ACCOUNT_ID_TEXT: Final = "4242"
TEST_GOODREADS_ACCOUNT_PROFILE_URL_TEMPLATE: Final = "{v0}/user/show/4242-reader"
TEST_GOODREADS_INVALID_PAGE_LIMIT_FETCH_MATCH_POSITIVE_INTEGER: Final = "positive integer"
TEST_REJECTS_AN_ACCOUNT_FOR_A_APP_THESTORYGRAPH_COM_PROFILE_READER: Final = (
    "https://app.thestorygraph.com/profile/reader"
)
TEST_GOODREADS_REJECTS_AN_ACCOUNT_SOURCE_MATCH_GOODREADS_READER: Final = "Goodreads reader"
RSS_FIRST_XML: Final = "rss-first.xml"
RSS_SECOND_XML: Final = "rss-second.xml"
RSS_EMPTY_XML: Final = "rss-empty.xml"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT: Final = "1002"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_2: Final = "1003"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_3: Final = "100"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_TEMPLATE: Final = (
    "{v0}/review/list_rss/4242"
)
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_RBITA_CAF: Final = "\xd3rbita & caf\xe9"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_EMPTY_TAIL_MAR_A_S_ENZ: Final = "Mar\xeda S\xe1enz"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4: Final = "9780140328721"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_FICCI_N: Final = "ficci\xf3n"
OWNED: Final = "owned"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_5: Final = "2026-07-27"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_MON_JUL: Final = (
    "Mon, 27 Jul 2026 20:47:23 -0700"
)
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_EMPTY_TAIL_THE_QUIET_MAP: Final = "The Quiet Map"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_6: Final = "1988"
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_KEY: Final = "key="
TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TOKEN: Final = "token="
TEST_GOODREADS_COMMON_HTTP_CLIENT_NETWORK_RESPOND_REVIEW_LIST_RSS: Final = "/review/list_rss/4242"
TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_BOOKS_OR_AUTHOR_ID_TEMPLATE: Final = (
    "{v0}/author/show/4242-reader"
)
TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_BOOKS_OR_AUTHOR_ID_TEMPLATE_2: Final = (
    "{v0}/review/list/999?shelf=to-read"
)
TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_WWW_GOODREADS_COM_EVIL_INVA: Final = (
    "https://www.goodreads.com.evil.invalid/review/list/4242?shelf=to-read"
)
TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_WWW_GOODREADS_COM_EVIL_INVA_2: Final = (
    "https://www.goodreads.com@evil.invalid/review/list/4242?shelf=to-read"
)
TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_OR_AUTHOR_ID_JAVASCRIPT_ALERT: Final = "javascript:alert(1)"
TEST_GOODREADS_MISSING_CHANNEL_READER_CHANNEL_TITLE_READER_S_BOOKSH: Final = (
    "<rss><channel><title>Reader's bookshelf: to-read</title>"
)
TEST_GOODREADS_MISSING_CHANNEL_READER_IDENTITY_XML_CHANNEL_RSS: Final = "</channel></rss>"
TEST_GOODREADS_CONFLICTING_ATOM_SELF_IS_REJECTED_XML_LIST_RSS: Final = "list_rss/4242"
TEST_GOODREADS_CONFLICTING_ATOM_SELF_IS_REJECTED_XML_LIST_RSS_2: Final = "list_rss/999"
COUNT: Final = "count"
TEST_GOODREADS_BOOK_PAGE_COUNT_IS_NEVER_ID_NUM_PAGES_NUM_PAGES_BOOK: Final = (
    "<book id='1001'><num_pages>9876</num_pages></book>"
)
TEST_GOODREADS_ACCESS_BLOCK_IS_NOT_HTML_BODY_ACCESS_DENIED_BODY_HTML: Final = (
    "<html><body>Access denied</body></html>"
)
BROWSER_EMPTY_HTML: Final = "browser-empty.html"
CHALLENGE: Final = "challenge"
TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_VERIFY_YOU_ARE_HUMAN_BO: Final = (
    "<html><body>Verify you are human</body></html>"
)
TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_BODY_FORM_ID_CHALLENGE_FORM: Final = (
    "<html><body><form id='challenge-form'>Continue</form></body></html>"
)
TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_DIV_CLASS_H_CAPTCHA_DIV: Final = (
    "<html><body><div class='h-captcha'></div></body></html>"
)
TEST_GOODREADS_A_BOOK_TITLE_IS_HTML_ACCESS_DENIED_HTML_DESCRIPT: Final = (
    "<description><![CDATA[<html>Access denied</html>]]></description>"
)
TEST_A_BOOK_TITLE_IS_NOT_AN_ACCESS_BLOCK_XML_TITLE_ACCESS_DENIED: Final = "Access Denied"
BODY: Final = "body"
TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_THIS_PROFILE_IS_PRIVATE_BODY: Final = (
    "<html><body>This profile is private</body></html>"
)
TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_INPUT_TYPE_PASSWORD_FORM_HTML: Final = (
    "<html><form><input type='password'></form></html>"
)
TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_BODY_SIGN_IN_BODY_HTML: Final = (
    "<html><body>Sign in</body></html>"
)
TEST_GOODREADS_PRIVATE_OR_REQUIRES_ORDINARY_AUTH_TEMPLATE: Final = "{v0}/user/sign_in"
TEST_GOODREADS_ARBITRARY_HTML_OR_HTML_BODY_SOMETHING_CHANGED: Final = (
    "<html><body>Something changed</body></html>"
)
TEST_GOODREADS_ARBITRARY_HTML_OR_IS_NOT_GENUINE_UNAVAILABILITY_RSS: Final = "<rss>"
DECLARATION: Final = "declaration"
TEST_GOODREADS_DTD_AND_ENTITIES_WITHOUT_EXPANSION_DOCTYPE_RSS: Final = "<!DOCTYPE rss>"
TEST_GOODREADS_DTD_AND_ENTITIES_ARE_RSS_ENTITY_XXE_SYSTEM_FILE_C: Final = (
    '<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>'
)
TEST_GOODREADS_DTD_AND_ENTITIES_ARE_RSS_ENTITY_ONE_ABC_ENTITY_TWO: Final = (
    '<!DOCTYPE rss [<!ENTITY one "abc"><!ENTITY two "&one;&one;">]>'
)
TEST_GOODREADS_INVALID_XML_ENCODING_EXPOSING_PAYLOAD_RESULT_BYTES: Final = b"\xff\xfe\x00"
TEST_GOODREADS_XML_ENCODING_DECLARATION_XML_XML_VERSION_ENCODING_ISO: Final = (
    '<?xml version="1.0" encoding="ISO-8859-1"?>'
)
ISO_8859_1: Final = "iso-8859-1"
TEST_GOODREADS_BLOCK_STATUS_SURVIVES_CHALLENGE_REDIRECT_RESULT_BYTES: Final = b"\xff"
TEST_BLOCK_STATUS_SURVIVES_INVALID_REDIRECT_RESULT_URL_TEMPLATE: Final = "{v0}/sorry"
TEST_BROWSER_REDIRECT_TO_CHALLENGE_NOT_UNKNOWN_MARKUP_URL_TEMPLATE: Final = "{v0}/challenge"
DESTINATION: Final = "destination"
TEST_GOODREADS_UNEXPECTED_FINAL_URL_IS_EVIL_INVALID_REVIEW_LIST_RSS: Final = (
    "https://evil.invalid/review/list_rss/4242"
)
TEST_GOODREADS_UNEXPECTED_FINAL_URL_IS_GOODREADS_COM_REVIEW_LIST_RSS: Final = (
    "https://www.goodreads.com:8443/review/list_rss/4242"
)
TEST_GOODREADS_UNEXPECTED_FINAL_URL_REJECTED_BEFORE_RECORDS_TEMPLATE: Final = (
    "{v0}/review/list_rss/999"
)
TEST_GOODREADS_UNEXPECTED_FINAL_URL_REJECTED_BEFORE_RECORDS_TEMPLATE_2: Final = (
    "{v0}/author/show/4242"
)
TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_HTTPS_EVIL_INVALID_BOOK_SHOW: Final = (
    "https://evil.invalid/book/show/1001"
)
TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_HTTPS_WWW_GOODREADS_COM_EVIL: Final = (
    "https://www.goodreads.com.evil.invalid/book/show/1001"
)
TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_DISCARD_OTHER_ROWS_TEMPLATE: Final = "{v0}/book/show/9999"
TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_OTHER_ROWS_XML_TEMPLATE: Final = "<link>{v0}</link>"
EVIL_INVALID: Final = "evil.invalid"
TEST_GOODREADS_FEED_FAILURE_KEEPS_HTTP_GOODREADS_REQUEST_TIMED: Final = (
    "Goodreads request timed out."
)
TEST_GOODREADS_PROGRESS_PERSISTENCE_FAILING_CALLBACK_THE_LOCAL: Final = (
    "The local progress store is unavailable."
)
TEST_GOODREADS_PROGRESS_PERSISTENCE_MATCH_LOCAL_PROGRESS_STORE: Final = "local progress store"
TEST_GOODREADS_INVALID_ISBN_IS_NOT_PROMOTED_TO_AN_IDENTIFIER_TEXT: Final = "9780140328720"
NOT_AN_ISBN: Final = "not-an-isbn"
TEST_GOODREADS_INVALID_ISBN_IS_NOT_PROMOTED_TO_AN_IDENTIFIER_TEXT_2: Final = "1234567890123"
TEST_GOODREADS_INVALID_ISBN_IS_NOT_TO_AN_IDENTIFIER_RESULT_TEMPLATE: Final = "<isbn>{v0}</isbn>"
DATE: Final = "date"
EXPECTED: Final = "expected"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT: Final = "2024"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_2: Final = "2024-06"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_JUNE: Final = "June 2024"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_JUN: Final = "Jun 02, 2024"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_3: Final = "2024-06-02"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_T23: Final = "2024-06-02T23:59:00-07:00"
TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_RESULT_TEMPLATE: Final = (
    "<user_date_added>{v0}</user_date_added>"
)
TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_TEXT: Final = "04/05/2024"
TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_TEXT_2: Final = "2024-02-31"
TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_MAY: Final = "May 4"
YESTERDAY: Final = "yesterday"
TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_OBSERVATION_DATE_MON_JUL: Final = (
    "Mon, 27 Jul 9999999999999999999 20:47:23 -0700"
)
TEST_GOODREADS_ZERO_PAGE_COUNT_AND_XML_BOOK_NUM_PAGES_NUM_PAGE: Final = (
    "<book><num_pages>0</num_pages></book><user_rating>0</user_rating>"
)
RAW: Final = "raw"
NAN_2: Final = "NaN"
TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_IS_ISSUE_NOT_A_CRASH_TEXT: Final = "-1"
INFINITY: Final = "Infinity"
TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_IS_ISSUE_NOT_A_CRASH_TEXT_2: Final = "9"
TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_NOT_A_CRASH_XML_TEMPLATE: Final = (
    "<book><num_pages>{v0}</num_pages></book>"
)
TEST_GOODREADS_MULTIPLE_AUTHORS_PRESERVE_THE_FRAN_OISE_NO_L_AUTHOR: Final = (
    "<author_name>Fran\xe7oise No\xebl</author_name><author_name>Jos\xe9 \xc1lvares</author_name>"
)
TEST_GOODREADS_MULTIPLE_AUTHORS_PRESERVE_SOURCE_SPELLING_JOS_LVARES: Final = "Jos\xe9 \xc1lvares"
TEST_GOODREADS_MULTIPLE_AUTHORS_PRESERVE_THE_SPELLING_FRAN_OISE_NO_L: Final = "Fran\xe7oise No\xebl"
BROWSER_TABLE_HTML: Final = "browser-table.html"
BROWSER_FRAGMENT_HTML: Final = "browser-fragment.html"
TEST_GOODREADS_BROWSER_FALLBACK_COLLECTS_MEMBERSHIP_S_ENZ_MAR_A: Final = "S\xe1enz, Mar\xeda"
HARDCOVER: Final = "Hardcover"
TEST_GOODREADS_BROWSER_FALLBACK_MATCHES_FEED_MEMBERSHIP_TEXT: Final = "2020-06"
TEST_GOODREADS_BROWSER_FALLBACK_MATCHES_FEED_MEMBERSHIP_TEXT_2: Final = "2"
TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_FIRST_TO_READ: Final = "to-read (3)"
TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_EMPTY_TO_READ: Final = "to-read (0)"
TEST_GOODREADS_BROWSER_REJECTS_LOGGED_IN_A_HREF_REVIEW_LIST_MY_BO: Final = (
    '<a href="/review/list/4242">My Books</a>'
)
TEST_GOODREADS_BROWSER_REJECTS_LOGGED_IN_A_HREF_REVIEW_LIST_MY_BO_2: Final = (
    '<a href="/review/list/999">My Books</a>'
)
TEST_GOODREADS_BROWSER_REQUIRES_AUTH_IS_CORRECT_HTML_MY_BOOKS: Final = "My Books"
TEST_GOODREADS_BROWSER_REQUIRES_AUTH_IS_CORRECT_HTML_PUBLIC_BOOKS: Final = "Public books"
PROFILE_2: Final = "Profile"
TEST_GOODREADS_BROWSER_LOGIN_OR_PRIVATE_FORM_INPUT_TYPE_PASSWORD_FOR: Final = (
    "<html><body><form><input type='password'></form></body></html>"
)
TEST_GOODREADS_BROWSER_LOGIN_OR_PRIVATE_THIS_MEMBER_S_PROFILE_IS: Final = (
    "<html><body>This member's profile is private.</body></html>"
)
REPLACEMENT: Final = "replacement"
TEST_GOODREADS_UNKNOWN_BROWSER_MARKUP_SHELF_MAIN_NEW_INTERFACE_MAIN: Final = (
    "<main>New interface</main>"
)
TEST_GOODREADS_UNKNOWN_BROWSER_MARKUP_IS_BOOKS_TBODY_ID_BOOKSBODY_TR: Final = (
    '<table id="books"><tbody id="booksBody"><tr class="new-layout"><td>A book</t'
    "d></tr></tbody></table>"
)
TEST_GOODREADS_UNKNOWN_BROWSER_MARKUP_CLASS_TABLE_STACKED_TBODY: Final = (
    '<table id="books" class="table stacked"><tbody id="booksBody"></tbody></table>'
)
NEXT_URL: Final = "next_url"
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_HTTPS_EVIL_INVALID_REVIEW: Final = (
    "https://evil.invalid/review/list/4242?shelf=to-read&amp;page=2"
)
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ: Final = (
    "/review/list/999?shelf=to-read&amp;page=2"
)
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_READ_AM: Final = (
    "/review/list/4242?shelf=read&amp;page=2"
)
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ_2: Final = (
    "/review/list/4242?shelf=to-read&amp;page=1"
)
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ_3: Final = (
    "/review/list/4242?shelf=to-read&amp;page=2&amp;per_page=500"
)
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ_4: Final = (
    "/review/list/4242?shelf=to-read&amp;page=2&amp;per_page="
)
TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_HTML_REVIEW_LIST_SHELF_TO: Final = (
    "/review/list/4242?shelf=to-read&amp;page=2&amp;per_page=100&amp;token=not-a-real-secret"
)
TEST_GOODREADS_BROWSER_REPEATED_PAGE_BE_COMPLETE_SECOND_REL_NEXT: Final = 'rel="next"'
TEST_GOODREADS_BROWSER_REPEATED_PAGE_BE_COMPLETE_SECOND_REL_PREV: Final = 'rel="prev"'
TEST_GOODREADS_BROWSER_REPEATED_PAGE_CANNOT_BE_COMPLETE_SECOND_NEXT: Final = "next \xbb"
PREVIOUS: Final = "previous"
TEST_GOODREADS_NUMBER_NAMED_CUSTOM_PAGINATION_LINK_HTML_TO_READ: Final = "to-read (1)"
TEST_GOODREADS_NUMBER_NAMED_CUSTOM_A_PAGINATION_LINK_HTML_ASIDE: Final = "</aside>"
TEST_GOODREADS_NUMBER_NAMED_CUSTOM_SHELF_HTML_A_HREF_REVIEW_LIST_SH: Final = (
    '<a href="/review/list/4242?shelf=2">2</a></aside>'
)
TEST_GOODREADS_BROWSER_CHANGING_SHELF_AUTHORITATIVE_CHANGED_TO_READ: Final = "to-read (4)"
TEST_GOODREADS_BROWSER_FETCHER_COMPLETED_PAGES_SESSION_EXPIRED: Final = "Session expired."
TEST_GOODREADS_BROWSER_FETCHER_COMPLETED_PAGES_ACCESS_BLOCKED: Final = "Access blocked."
TEST_GOODREADS_BROWSER_FETCHER_COMPLETED_PAGES_BROWSER_TIMEOUT: Final = "Browser timeout."
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
IMAGE: Final = "image"
USERINFO: Final = "userInfo"
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
TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_TEXT_2: Final = "*"
COVER: Final = "cover"
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
    "bookystats.scheduling.implementation_fingerprint"
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
TEST_STORYGRAPH_READ_TEMPLATE: Final = "{v0}/books-read/alice"
TEST_STORYGRAPH_CURRENT_TEMPLATE: Final = "{v0}/currently-reading/alice"
TEST_STORYGRAPH_PAUSED_TEMPLATE: Final = "{v0}/paused/alice"
TEST_STORYGRAPH_DNF_TEMPLATE: Final = "{v0}/did-not-finish/alice"
TEST_STORYGRAPH_BOOK_TEMPLATE: Final = "{v0}/books/book-a-id"
ALICE: Final = "alice"
TEST_STORYGRAPH_OWNED_TEMPLATE: Final = (
    '<html><body><nav><a href="/profile/{v0}" aria-label="Your profile">Profile</'
    'a><a href="/users/sign_out">Sign out</a></nav><main>{v1}</main></body></html'
    ">"
)
READ_BOOKS: Final = "read-books"
TEST_STORYGRAPH_EMPTY_TEMPLATE: Final = '<div class="{v0}"><p>No books in this list.</p></div>'
TEST_STORYGRAPH_FAKEBROWSER_FETCH_TEMPLATE: Final = "Unexpected fixture request: {v0}"
PROFILE_HTML: Final = "profile.html"
READ_PAGE_HTML: Final = "read_page.html"
PAUSED_BOOKS: Final = "paused-books"
BOOK_HTML: Final = "book.html"
BOOK_A_ID: Final = "book-a-id"
TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_PRESERVED_THE_FIRST_BOOK: Final = "The First Book"
TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_ARE_PRESERVED_AUTHOR_ONE: Final = "Author One"
TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_OWNER_S_OWN_REVIEW: Final = "owner's own review"
TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_PRESERVED_SOMEONE_ELSE_S: Final = "Someone else's"
REFLECTIVE: Final = "reflective"
HOPEFUL: Final = "hopeful"
SLOW: Final = "slow"
FAVOURITES: Final = "favourites"
GRIEF: Final = "grief"
READ_ONE: Final = "read-one"
READ_TWO: Final = "read-two"
TEST_STORYGRAPH_SOURCE_STRUCTURES_REREADS_ARE_PRESERVED_TEXT: Final = "2025-04"
HIDDEN_BOOK: Final = "hidden-book"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS: Final = "0 stars"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS_2: Final = "0.25 stars"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_TEXT: Final = "4.75 / 5"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_BLANK_RATINGS_NOT_RATED: Final = "Not rated"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS_3: Final = "4.3 stars"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_BLANK_RATINGS_SIX_STARS: Final = "six stars"
TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS_4: Final = "4.25 stars"
TEST_STORYGRAPH_COMMUNITY_AVERAGE_AND_FIELDS_DIV_CLASS_STANDARD: Final = (
    '<div class="standard-pane"><span class="average-star-rating">4.25</span></di'
    'v><section><h2>Community reviews</h2><article itemprop="review"><a href="/pr'
    'ofile/bob">bob</a><span itemprop="ratingValue">5</span><div class="trix-cont'
    'ent"><p>Your rating: 1</p>Not yours.</div></article></section>'
)
DOCUMENT: Final = "document"
TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_INPUT_TYPE_PASSWORD_FORM: Final = (
    '<form><input type="password"></form>'
)
DENIED: Final = "Denied"
TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_ARE_REQUIRED_RATE_LIMITED: Final = "Rate limited"
TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_ARE_REQUIRED_H1_ALICE_H1: Final = "<h1>alice</h1>"
BOB: Final = "bob"
TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_H1_A_HREF_PROFILE_ALICE: Final = (
    '<h1>alice</h1><a href="/profile/alice">alice</a>'
)
TEST_STORYGRAPH_WRONG_OWNER_MID_COLLECTION_BOOKS_DIV_CLASS_READ_BOOK: Final = (
    '<div class="read-books"></div>'
)
SOURCE_2: Final = "source_value"
TEST_STORYGRAPH_INVALID_AMBIGUOUS_OR_READING_DATES_ARE_FAILED_TEXT: Final = "03/04/2024"
TEST_STORYGRAPH_INVALID_AMBIGUOUS_OR_READING_DATES_ARE_FAILED_TEXT_2: Final = "2030-01-01"
TEST_STORYGRAPH_INVALID_AMBIGUOUS_OR_READING_DATES_ARE_FAILED_TEXT_3: Final = "2024-01-02"
TEST_STORYGRAPH_READ_COUNT_DOES_NOT_INVENT_COUNT_DT_READ_COUNT_DT_DD: Final = (
    "<dt>Read count</dt><dd>2"
)
TEST_STORYGRAPH_READ_COUNT_DOES_NOT_INVENT_COUNT_DT_READ_COUNT_DT_DD_2: Final = (
    "<dt>Read count</dt><dd>5"
)
TEST_STORYGRAPH_UNKNOWN_OPTIONAL_FIELDS_DT_DD_REFLECTIVE_HOPEFUL: Final = (
    "<dt>Moods</dt><dd>reflective, hopeful</dd>"
)
TEST_STORYGRAPH_DUPLICATE_APPEARANCES_MERGE_HISTORY_CLASS_READ_BOOKS: Final = 'class="read-books"'
TEST_STORYGRAPH_DUPLICATE_APPEARANCES_HISTORY_CLASS_PAUSED_BOOKS: Final = 'class="paused-books"'
TEST_STORYGRAPH_DISCOVERED_DNF_AND_PAUSED_SECTION_H2_YOUR_REVIEW_H: Final = (
    "<section><h2>Your review</h2><dl><dt>Rating</dt><dd></dd><dt>Review</dt><dd>"
    "</dd></dl></section><section><h2>Your reading history</h2><p>No reads yet</p"
    "></section>"
)
BOOK_B_ID: Final = "book-b-id"
TEST_STORYGRAPH_DISCOVERED_DNF_AND_NOT_CLASSIFIED_AS_READ_TEMPLATE: Final = "{v0}/books/book-b-id"
COLLECTION_PAUSED: Final = "collection.paused"
COLLECTION_DID_NOT_FINISH: Final = "collection.did-not-finish"
TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_IS_SAFE_NEXT_URL_TEMPLATE: Final = (
    "{v0}?page=2&cursor=sensitive-token"
)
TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN: Final = "</main>"
TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_A_ID_NEXT_LINK_DATA_REMO: Final = (
    '<a id="next_link" data-remote="true" href="?page=2&amp;cursor=sensitive-toke'
    'n">More...</a></main>'
)
TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_BOOK_B: Final = "Book B"
SENSITIVE_TOKEN: Final = "sensitive-token"
REPEAT_CURSOR: Final = "repeat_cursor"
TEST_STORYGRAPH_PAGINATION_REPETITION_RECORDS_TARGET_TEMPLATE: Final = "{v0}?page=2"
TEST_STORYGRAPH_PAGINATION_REPETITION_AND_RETAINS_RECORDS_TEMPLATE: Final = (
    '<a id="next_link" href="{v0}">More...</a></main>'
)
PAGINATION_REPEATED: Final = "pagination_repeated"
TEST_STORYGRAPH_CAPPED_WALK_IS_PARTIAL_ID_NEXT_LINK_HREF_PAGE_MORE: Final = (
    '<a id="next_link" href="?page=2">More...</a></main>'
)
TARGET: Final = "target"
TEST_STORYGRAPH_UNSAFE_OR_CROSS_OWNER_EXAMPLE_BOOKS_READ_ALICE_PA: Final = (
    "https://evil.example/books-read/alice?page=2"
)
TEST_STORYGRAPH_UNSAFE_OR_CROSS_LINK_IS_NEVER_REQUESTED_TEMPLATE: Final = (
    "{v0}/books-read/bob?page=2"
)
TEST_STORYGRAPH_UNSAFE_OR_CROSS_LINK_IS_NEVER_REQUESTED_TEMPLATE_2: Final = (
    "{v0}/books-read/alice?page=2&user=bob"
)
TEST_STORYGRAPH_UNSAFE_OR_CROSS_LINK_IS_NEVER_REQUESTED_TEMPLATE_3: Final = "{v0}/exports/alice"
TEST_STORYGRAPH_DETAIL_FAILURE_KEEPS_LIST_DETAILS_A_HREF_REVIEWS_REV: Final = (
    '<a href="/reviews/review-a" aria-label="Your review">Your review</a></main>'
)
TEST_STORYGRAPH_DETAIL_FAILURE_KEEPS_DETAILS_SOURCE_TIMED_OUT: Final = "Source timed out."
TEST_STORYGRAPH_DETAIL_FAILURE_OTHER_COLLECTED_DETAILS_TEMPLATE: Final = "{v0}/reviews/review-a"
TEST_STORYGRAPH_MISSING_AUTH_MID_DETAIL_STATE_A_HREF_REVIEWS_REVI: Final = (
    '<a href="/reviews/review-a">Your review</a></main>'
)
TEST_STORYGRAPH_MISSING_AUTH_MID_EXPLICIT_STATE_NEEDS_OWNER_LOGIN: Final = "Needs owner login."
TEST_STORYGRAPH_DISCOVERED_REVIEW_CANNOT_HREF_REVIEWS_REVIEW_B_YOU: Final = (
    '<a href="/reviews/review-b">Your review</a>'
)
TEST_STORYGRAPH_DISCOVERED_REVIEW_CANNOT_ARTICLE_ITEMPROP_REVIEW_A_H: Final = (
    '<article itemprop="review"><a href="/profile/bob">bob</a><a href="/books/boo'
    'k-a-id">The First Book</a><span itemprop="ratingValue">5</span><div itemprop'
    '="reviewBody">Bob secret review</div></article>'
)
TEST_STORYGRAPH_DISCOVERED_REVIEW_ANOTHER_READERS_TEXT_TEMPLATE: Final = "{v0}/reviews/review-b"
TEST_STORYGRAPH_DISCOVERED_REVIEW_CANNOT_TEXT_BOB_SECRET_REVIEW: Final = "Bob secret review"
TEST_STORYGRAPH_HISTORY_PAGE_TEMPLATE: Final = (
    '<section><h2>Your reading history</h2><a href="/books/book-a-id">The First B'
    "ook</a><table><tr><th>Started</th><th>Finished</th><th>Status</th></tr><tr i"
    'd="{v0}"><td></td><td>{v1}</td><td>Read</td></tr></table></section>'
)
TEST_STORYGRAPH_DISCOVERED_PERSONAL_DISTINCT_EVENTS_HISTORY_TEMPLATE: Final = (
    "{v0}/reading-history/example"
)
TEST_STORYGRAPH_DISCOVERED_PERSONAL_DISTINCT_EVENTS_TEMPLATE: Final = (
    "<section><h2>Your review</h2><dl><dt>Rating</dt><dd>0</dd><dt>Review</dt><dd"
    '></dd></dl></section><a href="{v0}">Your reading history</a>'
)
EVENT_1: Final = "event-1"
TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT: Final = "2024-01-01"
TEST_STORYGRAPH_DISCOVERED_PERSONAL_HISTORY_EVENTS_A_REL_NEXT_H: Final = (
    '<a rel="next" href="?page=2">Next</a>'
)
EVENT_2: Final = "event-2"
TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT_2: Final = "2025-01-01"
TEST_STORYGRAPH_REPEATED_HISTORY_IS_AND_RETAINS_FIRST_EVENT_TEMPLATE: Final = (
    '<a href="{v0}">Your reading history</a>'
)
TEST_STORYGRAPH_EXPORT_LINKS_ARE_IGNORED_A_HREF_EXPORT_EXPORT_AL: Final = (
    '<a href="/export">Export all data</a></main>'
)
TEST_STORYGRAPH_PROGRESS_FAILURE_IS_SUCCESS_FAIL_STORAGE_UNAVAILABLE: Final = "Storage unavailable"
TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_EMPTY_COLLECTION_EVIDENCE_ARTICLE: Final = "</article>"
TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_SUPPLY_EVIDENCE_SECTION_H2_YOUR_R: Final = (
    '<section><h2>Your review</h2><div class="trix-content"><p>No paused books</p'
    "><p>No dnf books</p></div></section></article>"
)
TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_EVIDENCE_IMPOSTOR_MAIN_ARTICLE_A: Final = (
    '<main><article><a aria-label="Your profile" href="/profile/alice">Your profi'
    "le</a></article></main>"
)
TEST_STORYGRAPH_NESTED_OTHER_READER_HEADING_ITEMPROP_REVIEW_A_HREF_P: Final = (
    '<article itemprop="review"><a href="/profile/bob">bob</a><section><h2>Your r'
    'eview</h2><dl><dt>Rating</dt><dd>5</dd></dl><div class="trix-content">Bob pr'
    "ivate text</div></section></article>"
)
TEST_STORYGRAPH_NESTED_OTHER_READER_OWNER_REVIEW_BOB_PRIVATE_TEXT: Final = "Bob private text"
EVENT_ID: Final = "event_id"
TEST_STORYGRAPH_SAME_EVENT_OBSERVED_NOT_DUPLICATED_ID_REAL_EVENT: Final = ' id="real-event"'
TEST_STORYGRAPH_SAME_EVENT_OBSERVED_WITH_LIST_HISTORY_SECTION_H2_YO: Final = (
    "<section><h2>Your reading history</h2><table><tr><th>Finished</th><th>Status"
    "</th></tr><tr><td>January 1, 2024</td><td>Read</td></tr></table></section>"
)
TEST_STORYGRAPH_SAME_EVENT_OBSERVED_TEXT_IS_NOT_DUPLICATED_TEMPLATE: Final = (
    "<section><h2>Your reading history</h2><table><tr><th>Finished</th><th>Status"
    "</th></tr><tr{v0}><td>2024-01-01</td><td>Read</td></tr></table></section>"
)
REAL_EVENT: Final = "real-event"
TEST_STORYGRAPH_TWO_ACTUAL_SAME_DAY_SECTION_H2_YOUR_READING_HI: Final = (
    "<section><h2>Your reading history</h2><table><tr><th>Finished</th><th>Status"
    "</th></tr><tr><td>2024-01-01</td><td>Read</td></tr><tr><td>2024-01-01</td><t"
    "d>Read</td></tr></table></section>"
)
TEST_STORYGRAPH_MUTATING_PERSONAL_LINK_REVIEWS_REVIEW_A_DATA_TURBO: Final = (
    '<a href="/reviews/review-a" data-turbo-method="delete">Your review</a></main>'
)
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
