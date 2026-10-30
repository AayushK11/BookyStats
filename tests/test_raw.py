from __future__ import annotations

import base64
import hashlib
import sqlite3
from collections.abc import Iterator, Mapping
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import BookyError, ConnectorError
from bookystats.interfaces import HttpResponse
from bookystats.models import Account, BookRecord, Source, SyncState
from bookystats.providers.google_books import GoogleBooksProvider
from bookystats.raw import RawDocument, RawStore, RawStoreError, RecordingFetcher


@pytest.fixture
def archive(tmp_path: Path) -> Iterator[RawStore]:
    store = RawStore(tmp_path / S.TEST_RAW_FILENAME)
    try:
        yield store
    finally:
        store.close()


def _capture(
    archive: RawStore,
    *,
    source: Source = Source.STORYGRAPH,
    account_id: str = S.TEST_RAW_ACCOUNT,
    body: bytes = S.TEST_RAW_MALFORMED,
    origin: str = S.TEST_RAW_FILE,
) -> RawDocument:
    return archive.capture(source, account_id, body, media_type=S.RAW_CSV_MEDIA_TYPE, origin=origin)


class FixtureFetcher:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, str] | None, Mapping[str, str] | None]] = []

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        self.calls.append((url, params, headers))
        return self.response


def _response(
    body: bytes = S.TEST_RAW_METADATA_BODY,
    *,
    status: int = C.INTERFACES_PAGEDOCUMENT_STATUS_CODE,
    url: str = S.TEST_RAW_PROVIDER_PRIVATE_URL,
) -> HttpResponse:
    return HttpResponse(
        url=url,
        status_code=status,
        headers=C.TEST_RAW_RESPONSE_HEADERS,
        body=body,
    )


def _book() -> BookRecord:
    return BookRecord(
        source=Source.STORYGRAPH,
        source_id=S.INTEGRATION_BOOK_ID,
        title=S.INTEGRATION_TITLE,
        url=S.INTEGRATION_STORYGRAPH_BOOK,
        isbns=C.TEST_RAW_ISBNS,
    )


@pytest.mark.parametrize(S.TEST_RAW_PARAM_BODY, C.TEST_RAW_BODIES)
def test_file_capture_retains_original_bytes_without_parsing(
    archive: RawStore, tmp_path: Path, body: bytes
) -> None:
    path = tmp_path / S.TEST_RAW_PRIVATE_FOLDER / S.TEST_RAW_FILE
    path.parent.mkdir()
    path.write_bytes(body)
    account = Account(
        source=Source.STORYGRAPH,
        account_id=S.TEST_RAW_ACCOUNT,
        profile_url=S.TEST_RAW_PROFILE,
    )
    document = archive.capture_file(account, path)
    path.unlink()
    assert document.body == body
    assert document.sha256 == hashlib.sha256(body).hexdigest()
    assert document.origin == path.name
    assert document.media_type == S.RAW_CSV_MEDIA_TYPE
    assert document.source == account.source
    assert document.account_id == account.account_id
    assert archive.get(document.id) == document


def test_reopen_replay_and_latest_preserve_old_capture(
    archive: RawStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_RAW_CLOCK, lambda: S.TEST_RAW_FIRST_TIME)
    first = _capture(archive)
    monkeypatch.setattr(S.TEST_RAW_CLOCK, lambda: S.TEST_RAW_SECOND_TIME)
    second = _capture(archive, body=S.TEST_RAW_NEXT_BODY)
    archive.close()
    reopened = RawStore(tmp_path / S.TEST_RAW_FILENAME)
    try:
        assert reopened.get(first.id) == first
        assert reopened.get(second.id) == second
        assert reopened.latest(Source.STORYGRAPH, S.TEST_RAW_ACCOUNT) == second
        assert first.captured_at == S.TEST_RAW_FIRST_TIME
        assert second.captured_at == S.TEST_RAW_SECOND_TIME
    finally:
        reopened.close()


def test_payload_deduplication_keeps_source_account_and_capture_lineage(
    archive: RawStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_RAW_CLOCK, lambda: S.TEST_RAW_FIRST_TIME)
    first = _capture(archive)
    monkeypatch.setattr(S.TEST_RAW_CLOCK, lambda: S.TEST_RAW_SECOND_TIME)
    repeat = _capture(archive, origin=S.TEST_RAW_OTHER_ORIGIN)
    alternate_account = _capture(archive, account_id=S.TEST_RAW_OTHER_ACCOUNT)
    alternate_source = _capture(archive, source=Source.GOODREADS)
    assert first.id != repeat.id
    assert first.captured_at != repeat.captured_at
    assert archive.get(first.id) == first
    assert archive.latest(Source.STORYGRAPH, S.TEST_RAW_ACCOUNT) == repeat
    assert archive.latest(Source.STORYGRAPH, S.TEST_RAW_OTHER_ACCOUNT) == alternate_account
    assert archive.latest(Source.GOODREADS, S.TEST_RAW_ACCOUNT) == alternate_source
    assert archive.latest(Source.GOODREADS, S.TEST_RAW_OTHER_ACCOUNT) is C.NONE
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        assert connection.execute(S.TEST_RAW_PAYLOAD_COUNTS).fetchone()[C.ZERO] == C.ONE
        assert connection.execute(S.TEST_RAW_CAPTURE_COUNTS).fetchone()[C.ZERO] == C.FOUR


@pytest.mark.parametrize(S.TEST_RAW_PARAM_SQL, C.TEST_RAW_TAMPERING)
def test_damaged_capture_or_missing_payload_fails_explicitly(
    archive: RawStore, tmp_path: Path, sql: str
) -> None:
    document = _capture(archive)
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        connection.execute(sql)
    with pytest.raises(RawStoreError, match=S.RAW_CORRUPT_ERROR):
        archive.get(document.id)


def test_corrupt_duplicate_is_not_silently_reused(archive: RawStore, tmp_path: Path) -> None:
    _capture(archive)
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        connection.execute(S.TEST_RAW_TAMPER_BODY)
    with pytest.raises(RawStoreError, match=S.RAW_CORRUPT_ERROR):
        _capture(archive)
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        assert connection.execute(S.TEST_RAW_CAPTURE_COUNTS).fetchone()[C.ZERO] == C.ONE


def test_latest_validates_capture_order_integrity(archive: RawStore, tmp_path: Path) -> None:
    _capture(archive)
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        connection.execute(S.TEST_RAW_TAMPER_SEQUENCE)
    with pytest.raises(RawStoreError, match=S.RAW_CORRUPT_ERROR):
        archive.latest(Source.STORYGRAPH, S.TEST_RAW_ACCOUNT)


@pytest.mark.parametrize(S.TEST_RAW_PARAM_SQL, C.TEST_RAW_UNSUPPORTED)
def test_unknown_database_is_rejected_without_reinitializing(tmp_path: Path, sql: str) -> None:
    path = tmp_path / S.TEST_RAW_FILENAME
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    original = path.read_bytes()
    with pytest.raises(RawStoreError, match=S.RAW_UNSUPPORTED_ERROR):
        RawStore(path)
    assert path.read_bytes() == original


def test_corrupt_database_is_not_overwritten_or_echoed(tmp_path: Path) -> None:
    path = tmp_path / S.TEST_RAW_FILENAME
    path.write_bytes(S.TEST_RAW_CORRUPT_FILE)
    with pytest.raises(RawStoreError, match=S.RAW_OPEN_ERROR):
        RawStore(path)
    assert path.read_bytes() == S.TEST_RAW_CORRUPT_FILE


def test_future_raw_schema_is_rejected(archive: RawStore, tmp_path: Path) -> None:
    document = _capture(archive)
    archive.close()
    path = tmp_path / S.TEST_RAW_FILENAME
    with sqlite3.connect(path) as connection:
        connection.execute(S.TEST_RAW_NEW_VERSION)
    original = path.read_bytes()
    with pytest.raises(RawStoreError, match=S.RAW_UNSUPPORTED_ERROR):
        RawStore(path)
    assert path.read_bytes() == original
    assert document.body in original


def test_capture_rolls_back_payload_if_capture_insert_fails(
    archive: RawStore, tmp_path: Path
) -> None:
    original = _capture(archive)
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        connection.execute(S.TEST_RAW_INSERT_ABORT)
    with pytest.raises(RawStoreError, match=S.RAW_WRITE_ERROR):
        _capture(archive, body=S.TEST_RAW_NEXT_BODY)
    assert archive.get(original.id) == original
    with sqlite3.connect(tmp_path / S.TEST_RAW_FILENAME) as connection:
        assert connection.execute(S.TEST_RAW_PAYLOAD_COUNTS).fetchone()[C.ZERO] == C.ONE
        assert connection.execute(S.TEST_RAW_CAPTURE_COUNTS).fetchone()[C.ZERO] == C.ONE


def test_missing_file_document_and_closed_archive_fail_explicitly(
    archive: RawStore, tmp_path: Path
) -> None:
    account = Account(
        source=Source.STORYGRAPH,
        account_id=S.TEST_RAW_ACCOUNT,
        profile_url=S.TEST_RAW_PROFILE,
    )
    with pytest.raises(RawStoreError, match=S.RAW_FILE_ERROR):
        archive.capture_file(account, tmp_path / S.TEST_RAW_FILE)
    with pytest.raises(RawStoreError, match=S.RAW_MISSING_ERROR):
        archive.get(S.TEST_RAW_MISSING)
    archive.close()
    archive.close()
    with pytest.raises(RawStoreError, match=S.RAW_CLOSED_ERROR):
        _capture(archive)
    with pytest.raises(RawStoreError, match=S.RAW_CLOSED_ERROR):
        archive.latest(Source.STORYGRAPH, S.TEST_RAW_ACCOUNT)


@pytest.mark.parametrize(S.TEST_RAW_PARAM_STATUS, C.TEST_RAW_HTTP_STATUSES)
def test_recording_preserves_full_response_and_only_safe_lookup_provenance(
    archive: RawStore, tmp_path: Path, status: int
) -> None:
    response = _response(status=status)
    http = FixtureFetcher(response)
    recorder = RecordingFetcher(http, archive, source=Source.GOOGLE_BOOKS)
    params = C.TEST_RAW_GOOGLE_PARAMS
    headers = C.TEST_RAW_REQUEST_HEADERS
    assert (
        recorder.fetch(S.TEST_RAW_PROVIDER_PRIVATE_URL, params=params, headers=headers) is response
    )
    assert http.calls[C.ZERO][C.ZERO] == S.TEST_RAW_PROVIDER_PRIVATE_URL
    assert http.calls[C.ZERO][C.ONE] is params
    assert http.calls[C.ZERO][C.TWO] is headers
    document = archive.latest(Source.GOOGLE_BOOKS, S.RAW_CATALOG_ACCOUNT)
    assert document is not C.NONE
    assert document.body == response.body
    assert document.media_type == S.TEST_RAW_MEDIA_TYPE
    parsed = urlsplit(document.origin)
    assert parse_qs(parsed.query) == C.TEST_RAW_EXPECTED_GOOGLE_QUERY
    assert parsed.username is C.NONE and parsed.password is C.NONE
    assert not parsed.fragment
    archive.close()
    disk = (tmp_path / S.TEST_RAW_FILENAME).read_bytes()
    for secret in C.TEST_RAW_DISK_SECRETS:
        assert secret.encode(S.UTF_8) not in disk


def test_open_library_allowlisted_lookup_survives_transport_url_sanitization(
    archive: RawStore,
) -> None:
    http = FixtureFetcher(_response(url=S.TEST_RAW_OPEN_LIBRARY_URL))
    params = C.TEST_RAW_OPEN_LIBRARY_PARAMS
    RecordingFetcher(http, archive, source=Source.OPEN_LIBRARY).fetch(
        S.TEST_RAW_OPEN_LIBRARY_URL, params=params
    )
    document = archive.latest(Source.OPEN_LIBRARY, S.RAW_CATALOG_ACCOUNT)
    assert document is not C.NONE
    assert parse_qs(urlsplit(document.origin).query) == {
        key: [value] for key, value in params.items() if key != S.KEY
    }


def test_open_library_search_lookup_is_preserved(archive: RawStore) -> None:
    http = FixtureFetcher(_response(url=S.TEST_RAW_SEARCH_URL))
    RecordingFetcher(http, archive, source=Source.OPEN_LIBRARY).fetch(
        S.TEST_RAW_SEARCH_URL, params=C.TEST_RAW_GOOGLE_PARAMS
    )
    document = archive.latest(Source.OPEN_LIBRARY, S.RAW_CATALOG_ACCOUNT)
    assert document is not C.NONE
    assert parse_qs(urlsplit(document.origin).query) == C.TEST_RAW_EXPECTED_GOOGLE_QUERY


def test_recording_precedes_provider_parse_failure(archive: RawStore) -> None:
    http = FixtureFetcher(_response(S.TEST_RAW_METADATA_INVALID))
    provider = GoogleBooksProvider(
        RecordingFetcher(http, archive, source=Source.GOOGLE_BOOKS),
        api_key=S.TEST_RAW_REQUEST_KEY,
    )
    result = provider.lookup(_book())
    assert result.state == SyncState.FAILED
    document = archive.latest(Source.GOOGLE_BOOKS, S.RAW_CATALOG_ACCOUNT)
    assert document is not C.NONE
    assert document.body == S.TEST_RAW_METADATA_INVALID


@pytest.mark.parametrize(S.TEST_RAW_PARAM_ECHO, C.TEST_RAW_ECHOES)
def test_credential_echo_is_rejected_instead_of_redacting_raw(
    archive: RawStore, tmp_path: Path, echo: str
) -> None:
    body = S.TEST_RAW_ECHO_TEMPLATE.format(value=echo).encode(S.UTF_8)
    http = FixtureFetcher(_response(body))
    recorder = RecordingFetcher(http, archive, source=Source.GOOGLE_BOOKS)
    with pytest.raises(RawStoreError, match=S.RAW_CREDENTIAL_ERROR):
        recorder.fetch(
            S.TEST_RAW_PROVIDER_PRIVATE_URL,
            params=C.TEST_RAW_GOOGLE_PARAMS,
            headers=C.TEST_RAW_REQUEST_HEADERS,
        )
    assert archive.latest(Source.GOOGLE_BOOKS, S.RAW_CATALOG_ACCOUNT) is C.NONE
    archive.close()
    assert echo.encode(S.UTF_8) not in (tmp_path / S.TEST_RAW_FILENAME).read_bytes()


@pytest.mark.parametrize(S.TEST_RAW_ESCAPE_CASES, C.TEST_RAW_ESCAPE_CASES)
def test_encoded_credential_echo_is_rejected(archive: RawStore, body: bytes, secret: str) -> None:
    recorder = RecordingFetcher(
        FixtureFetcher(_response(body)), archive, source=Source.GOOGLE_BOOKS
    )
    with pytest.raises(RawStoreError, match=S.RAW_CREDENTIAL_ERROR):
        recorder.fetch(S.TEST_RAW_PROVIDER_URL, params={S.KEY: secret})
    assert archive.latest(Source.GOOGLE_BOOKS, S.RAW_CATALOG_ACCOUNT) is C.NONE


@pytest.mark.parametrize(S.TEST_RAW_PARAM_ECHO, C.TEST_RAW_BASIC_ECHOES)
def test_basic_authorization_components_are_not_archived(archive: RawStore, echo: str) -> None:
    credentials = S.TEST_RAW_BASIC_TEMPLATE.format(
        username=S.TEST_RAW_URL_USER, password=S.TEST_RAW_URL_PASSWORD
    )
    header = S.TEST_RAW_BASIC_HEADER.format(
        value=base64.b64encode(credentials.encode(S.UTF_8)).decode(S.UTF_8)
    )
    recorder = RecordingFetcher(
        FixtureFetcher(_response(echo.encode(S.UTF_8))), archive, source=Source.GOOGLE_BOOKS
    )
    with pytest.raises(RawStoreError, match=S.RAW_CREDENTIAL_ERROR):
        recorder.fetch(S.TEST_RAW_PROVIDER_URL, headers={S.AUTHORIZATION: header})
    assert archive.latest(Source.GOOGLE_BOOKS, S.RAW_CATALOG_ACCOUNT) is C.NONE


def test_recording_failure_does_not_return_unarchived_response(archive: RawStore) -> None:
    http = FixtureFetcher(_response())
    recorder = RecordingFetcher(http, archive, source=Source.GOOGLE_BOOKS)
    archive.close()
    with pytest.raises(RawStoreError, match=S.RAW_CLOSED_ERROR) as error:
        recorder.fetch(S.TEST_RAW_PROVIDER_URL)
    assert isinstance(error.value, BookyError)
    assert len(http.calls) == C.ONE


def test_provider_does_not_mislabel_raw_failure_as_network_error(archive: RawStore) -> None:
    provider = GoogleBooksProvider(
        RecordingFetcher(FixtureFetcher(_response()), archive, source=Source.GOOGLE_BOOKS),
        api_key=S.TEST_RAW_REQUEST_KEY,
    )
    archive.close()
    with pytest.raises(RawStoreError, match=S.RAW_CLOSED_ERROR):
        provider.lookup(_book())


def test_transport_failure_is_not_converted_to_a_capture(
    archive: RawStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed(
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        raise ConnectorError(S.TEST_RAW_TRANSPORT_ERROR)

    http = FixtureFetcher(_response())
    monkeypatch.setattr(http, S.TEST_RAW_FETCH_METHOD, failed)
    recorder = RecordingFetcher(http, archive, source=Source.GOOGLE_BOOKS)
    with pytest.raises(ConnectorError, match=S.TEST_RAW_TRANSPORT_ERROR):
        recorder.fetch(S.TEST_RAW_PROVIDER_URL)
    assert archive.latest(Source.GOOGLE_BOOKS, S.RAW_CATALOG_ACCOUNT) is C.NONE


@pytest.mark.parametrize(S.TEST_RAW_PARAM_SOURCE, C.TEST_RAW_READER_SOURCES)
def test_recording_adapter_cannot_enable_reader_account_capture(
    archive: RawStore, source: Source
) -> None:
    http = FixtureFetcher(_response())
    with pytest.raises(RawStoreError, match=S.RAW_PROVIDER_ERROR):
        RecordingFetcher(http, archive, source=source)
    assert not http.calls
