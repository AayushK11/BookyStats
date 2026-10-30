from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

import pytest

from bookystats import cli
from bookystats import constants as C
from bookystats import strings as S
from bookystats.config import MetadataSettings, Settings
from bookystats.interfaces import SourceConnector
from bookystats.models import (
    Account,
    BookRecord,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    MetadataCandidate,
    Observation,
    PartialDate,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
)
from tests.test_sync import AuthRequiredConnector, FixtureConnector, accounts, complete_snapshot


def _snapshot(account: Account, *, changed: bool) -> CollectionSnapshot:
    personal = account.source == Source.STORYGRAPH
    url = S.INTEGRATION_STORYGRAPH_BOOK if personal else S.INTEGRATION_GOODREADS_BOOK
    record = BookRecord(
        source=account.source,
        source_id=S.INTEGRATION_NEW_BOOK_ID if changed else S.INTEGRATION_BOOK_ID,
        title=S.INTEGRATION_NEW_TITLE if changed else S.INTEGRATION_TITLE,
        authors=(S.INTEGRATION_AUTHOR,),
        url=url,
        status=ReadingStatus.READ if personal else ReadingStatus.TO_READ,
        isbns=() if changed else (S.INTEGRATION_ISBN,),
        observations=(
            Observation(
                field=S.RATING,
                value=C.INTEGRATION_RATING,
                state=FieldState.PRESENT,
                scope=S.READER,
                source_url=url,
            ),
            Observation(
                field=S.REVIEW,
                state=FieldState.EMPTY,
                scope=S.READER,
                source_url=url,
            ),
        )
        if personal
        else (),
        reading_events=(
            ReadingEvent(
                finished=PartialDate(value=S.INTEGRATION_READ_DATE),
                status=ReadingStatus.READ,
            ),
        )
        if personal
        else (),
    )
    return complete_snapshot(account).model_copy(
        update={S.RECORDS: (record,), S.EXPECTED_COUNT: C.ONE}
    )


class FixtureMetadata:
    def __init__(self) -> None:
        self.calls: list[tuple[Source, str]] = []

    def lookup(self, book: BookRecord) -> EnrichmentResult:
        self.calls.append((book.source, book.source_id))
        candidates = ()
        if book.isbns:
            candidates = (
                MetadataCandidate(
                    provider=Source.GOOGLE_BOOKS,
                    provider_id=S.INTEGRATION_METADATA_ID,
                    title=book.title,
                    authors=book.authors,
                    isbns=book.isbns,
                    url=S.INTEGRATION_METADATA_URL,
                    observations=(
                        Observation(
                            field=S.PAGE_COUNT,
                            value=C.INTEGRATION_PAGE_COUNT,
                            state=FieldState.PRESENT,
                            scope=S.EDITION,
                            source_url=S.INTEGRATION_METADATA_URL,
                        ),
                    ),
                ),
            )
        return EnrichmentResult(
            source_id=book.source_id, state=SyncState.COMPLETE, candidates=candidates
        )


@pytest.mark.parametrize(S.REPLACE_ACCOUNT, (C.FALSE, C.TRUE))
def test_real_runtime_persists_restarts_and_keeps_good_data_on_partial_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replace_account: bool
) -> None:
    monkeypatch.delenv(S.GOOGLE_BOOKS_API_KEY, raising=C.FALSE)
    settings = Settings(accounts=accounts())
    provider = FixtureMetadata()
    for iteration in range(C.THREE):
        provider.calls.clear()
        if iteration == C.TWO and replace_account:
            replacement = Account(
                source=Source.STORYGRAPH,
                account_id=S.ALTERNATE_READER,
                profile_url=S.ALTERNATE_READER_PROFILE,
            )
            settings = settings.model_copy(
                update={S.ACCOUNTS: (replacement, settings.accounts[C.ONE])}
            )
        connectors: dict[Source, SourceConnector] = {
            account.source: FixtureConnector(
                _snapshot(
                    account,
                    changed=iteration == C.TWO and account.source == Source.GOODREADS,
                )
            )
            for account in settings.accounts
        }
        if iteration == C.TWO and not replace_account:
            connectors[Source.STORYGRAPH] = AuthRequiredConnector()
        with ExitStack() as stack:
            service = cli._build_service(tmp_path, settings, stack, interactive=C.FALSE)
            service.connectors = connectors
            service.providers = {Source.GOOGLE_BOOKS: provider}
            receipt = service.run(interactive=C.FALSE)
            records = service.store.active_records()
            assert len(records) == C.TWO
            if iteration < C.TWO:
                assert receipt.state == SyncState.COMPLETE
                assert receipt.account_sync_complete
                if iteration == C.ZERO:
                    assert provider.calls
                else:
                    assert not provider.calls
                    assert all(
                        source.publication is not C.NONE and source.publication.unchanged == C.ONE
                        for source in receipt.sources
                    )
            else:
                assert receipt.state == SyncState.PARTIAL
                assert receipt.sources[C.ZERO].state == (
                    SyncState.FAILED if replace_account else SyncState.NEEDS_AUTH
                )
                assert receipt.sources[C.ONE].state == SyncState.COMPLETE
                assert {(book.source, book.source_id) for book in records} == {
                    (Source.STORYGRAPH, S.INTEGRATION_BOOK_ID),
                    (Source.GOODREADS, S.INTEGRATION_NEW_BOOK_ID),
                }
                personal = next(book for book in records if book.source == Source.STORYGRAPH)
                assert personal.reading_events[C.ZERO].finished == PartialDate(
                    value=S.INTEGRATION_READ_DATE
                )
                assert (
                    next(value.value for value in personal.observations if value.field == S.RATING)
                    == C.INTEGRATION_RATING
                )
    status = cli._status(tmp_path, settings)
    library = status[S.LIBRARY]
    assert isinstance(library, dict)
    assert library[S.SOURCE_RECORDS] == C.TWO
    assert library[S.READING_EVENTS] == C.ONE


@pytest.mark.parametrize(S.METADATA_ENABLED, (C.FALSE, C.TRUE))
def test_bad_optional_cache_does_not_block_account_ingestion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metadata_enabled: bool
) -> None:
    monkeypatch.setenv(S.GOOGLE_BOOKS_API_KEY, S.DO_NOT_PRINT_THIS)
    cache_path = tmp_path / S.METADATA_SQLITE3
    cache_path.write_text(S.INTEGRATION_TITLE, encoding=S.UTF_8)
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=metadata_enabled, open_library=C.FALSE),
    )
    with ExitStack() as stack:
        service = cli._build_service(tmp_path, settings, stack, interactive=C.FALSE)
        service.connectors = {
            account.source: FixtureConnector(complete_snapshot(account))
            for account in settings.accounts
        }
        receipt = service.run(interactive=C.FALSE)
        assert receipt.account_sync_complete
        assert all(source.publication is not C.NONE for source in receipt.sources)
        if metadata_enabled:
            assert receipt.state == SyncState.PARTIAL
            assert receipt.metadata[C.ZERO].state == SyncState.FAILED
            assert receipt.metadata[C.ZERO].issues[C.ZERO].code == S.METADATA_CACHE_ERROR
        else:
            assert receipt.state == SyncState.COMPLETE
            assert receipt.metadata == ()
        assert S.DO_NOT_PRINT_THIS not in receipt.model_dump_json()
    assert cache_path.read_text(encoding=S.UTF_8) == S.INTEGRATION_TITLE
