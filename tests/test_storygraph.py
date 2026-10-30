from __future__ import annotations

from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.connectors.storygraph import StoryGraphConnector
from bookystats.errors import ConnectorError
from bookystats.interfaces import PageDocument
from bookystats.models import (
    Account,
    BookRecord,
    CollectionProgress,
    FieldState,
    ReadingStatus,
    Source,
    SyncState,
)

FIXTURES = Path(__file__).parent / S.FIXTURES / S.STORYGRAPH
ACCOUNT = Account(
    source=Source.STORYGRAPH, account_id=S.ALICE, profile_url=C.TEST_STORYGRAPH_PROFILE
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding=S.UTF_8)


def owned(body: str, owner: str = S.ALICE) -> str:
    return S.TEST_STORYGRAPH_OWNED_TEMPLATE.format(v0=owner, v1=body)


def empty(container: str = S.READ_BOOKS) -> str:
    return owned(S.TEST_STORYGRAPH_EMPTY_TEMPLATE.format(v0=container))


class FakeBrowser:
    def __init__(self, pages: dict[str, str | PageDocument | ConnectorError]) -> None:
        self.pages = pages
        self.requests: list[str] = []

    def fetch(self, url: str, *, wait_for: str | None = C.NONE) -> PageDocument:
        self.requests.append(url)
        assert wait_for is C.NONE
        assert url in self.pages, S.TEST_STORYGRAPH_FAKEBROWSER_FETCH_TEMPLATE.format(v0=url)
        value = self.pages[url]
        if isinstance(value, ConnectorError):
            raise value
        return value if isinstance(value, PageDocument) else PageDocument(url, value)


def pages() -> dict[str, str | PageDocument | ConnectorError]:
    return {
        C.TEST_STORYGRAPH_PROFILE: fixture(S.PROFILE_HTML),
        C.TEST_STORYGRAPH_READ: fixture(S.READ_PAGE_HTML),
        C.TEST_STORYGRAPH_CURRENT: empty(),
        C.TEST_STORYGRAPH_PAUSED: empty(S.PAUSED_BOOKS),
        C.TEST_STORYGRAPH_DNF: empty(),
        C.TEST_STORYGRAPH_BOOK: fixture(S.BOOK_HTML),
    }


def observation(book: BookRecord, name: str):
    return next(item for item in book.observations if item.field == name)


def test_source_structures_personal_fields_and_rereads_are_preserved() -> None:
    browser = FakeBrowser(pages())
    progress: list[CollectionProgress] = []
    snapshot = StoryGraphConnector(browser).collect(ACCOUNT, on_progress=progress.append)
    assert snapshot.state == SyncState.COMPLETE
    assert snapshot.identity_verified and snapshot.termination_verified
    assert snapshot.expected_count is C.NONE
    assert len(snapshot.records) == C.ONE
    book = snapshot.records[C.ZERO]
    assert book.source_id == S.BOOK_A_ID
    assert book.title == S.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_PRESERVED_THE_FIRST_BOOK
    assert book.authors == (S.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_ARE_PRESERVED_AUTHOR_ONE,)
    assert book.isbns == (S.TEST_UNRELATED_SEARCH_HITS_DO_EVIDENCE_UNRELATED_ISBNS_TEXT,)
    assert (
        observation(book, S.RATING).value
        == C.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_AND_REREADS_ARE_PRESERVED
    )
    assert (
        observation(book, S.COMMUNITY_RATING).value
        == C.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_AND_REREADS_ARE_PRESERVED_2
    )
    assert (
        S.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_OWNER_S_OWN_REVIEW
        in observation(book, S.REVIEW).value
    )
    assert (
        S.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_PRESERVED_SOMEONE_ELSE_S
        not in observation(book, S.REVIEW).value
    )
    assert observation(book, S.MOODS).value == [S.REFLECTIVE, S.HOPEFUL]
    assert observation(book, S.PACE).value == S.SLOW
    assert observation(book, S.TAGS).value == [S.FAVOURITES]
    assert observation(book, S.CONTENT_WARNINGS).value == [S.GRIEF]
    assert observation(book, S.BOOK_TAGS).scope == S.WORK
    assert observation(book, S.READ_COUNT).value == C.TWO
    assert [event.source_event_id for event in book.reading_events] == [S.READ_ONE, S.READ_TWO]
    assert (
        book.reading_events[C.ONE].finished.value
        == S.TEST_STORYGRAPH_SOURCE_STRUCTURES_REREADS_ARE_PRESERVED_TEXT
    )
    assert snapshot.capabilities[S.STATUS] == FieldState.PRESENT
    assert progress[-C.ONE].records == snapshot.records
    assert all(S.REVIEW not in item.message for item in progress)
    assert not any(S.HIDDEN_BOOK in url for url in browser.requests)


@pytest.mark.parametrize(
    (S.RATING, S.STATE, S.VALUE),
    [
        (
            S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS,
            FieldState.PRESENT,
            C.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_AND_EXPLICIT_BLANK_RATINGS,
        ),
        (
            S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS_2,
            FieldState.PRESENT,
            C.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_AND_EXPLICIT_BLANK_RATINGS_2,
        ),
        (
            S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_TEXT,
            FieldState.PRESENT,
            C.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_AND_EXPLICIT_BLANK_RATINGS_3,
        ),
        (S.EMPTY, FieldState.EMPTY, C.NONE),
        (S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_BLANK_RATINGS_NOT_RATED, FieldState.EMPTY, C.NONE),
        (
            S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS_3,
            FieldState.FAILED,
            C.NONE,
        ),
        (
            S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_BLANK_RATINGS_SIX_STARS,
            FieldState.FAILED,
            C.NONE,
        ),
    ],
)
def test_personal_zero_quarter_and_explicit_blank_ratings(rating, state, value) -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_PERSONAL_ZERO_QUARTER_EXPLICIT_BLANK_RATINGS_STARS_4, rating
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    actual = observation(snapshot.records[C.ZERO], S.RATING)
    assert actual.state == state
    assert actual.value == value
    assert (snapshot.state == SyncState.PARTIAL) == (state == FieldState.FAILED)


def test_community_average_and_other_review_never_become_personal_fields() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_COMMUNITY_AVERAGE_AND_FIELDS_DIV_CLASS_STANDARD
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    for name in (S.RATING, S.REVIEW, S.READING_EVENTS):
        assert observation(snapshot.records[C.ZERO], name).state == FieldState.UNAVAILABLE
        assert observation(snapshot.records[C.ZERO], name).value is C.NONE
    assert (
        observation(snapshot.records[C.ZERO], S.COMMUNITY_RATING).value
        == C.TEST_STORYGRAPH_COMMUNITY_AVERAGE_AND_NEVER_BECOME_PERSONAL_FIELDS
    )


@pytest.mark.parametrize(
    (S.DOCUMENT, S.STATE, S.CODE),
    [
        (
            PageDocument(
                S.TEST_BROWSER_ONLY_DISCOVERED_OWNER_LOGIN_FORM_CAN_SUBMIT_TEMPLATE.format(
                    v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
                ),
                S.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_INPUT_TYPE_PASSWORD_FORM,
            ),
            SyncState.NEEDS_AUTH,
            S.NEEDS_AUTH,
        ),
        (
            PageDocument(
                C.TEST_STORYGRAPH_PROFILE,
                S.TEST_BROWSER_UNATTENDED_AUTH_AND_TITLE_JUST_A_MOMENT_TITLE,
            ),
            SyncState.BLOCKED,
            S.SOURCE_BLOCKED,
        ),
        (
            PageDocument(
                C.TEST_STORYGRAPH_PROFILE,
                S.DENIED,
                C.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_EVIDENCE_ARE_REQUIRED,
            ),
            SyncState.BLOCKED,
            S.SOURCE_BLOCKED,
        ),
        (
            PageDocument(
                C.TEST_STORYGRAPH_PROFILE,
                S.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_ARE_REQUIRED_RATE_LIMITED,
                C.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_EVIDENCE_ARE_REQUIRED_2,
            ),
            SyncState.BLOCKED,
            S.SOURCE_BLOCKED,
        ),
        (
            PageDocument(
                C.TEST_STORYGRAPH_PROFILE,
                owned(S.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_ARE_REQUIRED_H1_ALICE_H1, S.BOB),
            ),
            SyncState.FAILED,
            S.WRONG_ACCOUNT,
        ),
        (
            PageDocument(
                C.TEST_STORYGRAPH_PROFILE,
                S.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_H1_A_HREF_PROFILE_ALICE,
            ),
            SyncState.NEEDS_AUTH,
            S.OWNER_IDENTITY_UNAVAILABLE,
        ),
    ],
)
def test_authentication_and_owner_evidence_are_required(document, state, code) -> None:
    browser = FakeBrowser({C.TEST_STORYGRAPH_PROFILE: document})
    snapshot = StoryGraphConnector(browser).collect(ACCOUNT)
    assert snapshot.state == state
    assert not snapshot.records
    assert code in {issue.code for issue in snapshot.issues}
    assert browser.requests == [C.TEST_STORYGRAPH_PROFILE]


def test_wrong_owner_mid_collection_keeps_only_previously_verified_books() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_CURRENT] = owned(
        S.TEST_STORYGRAPH_WRONG_OWNER_MID_COLLECTION_BOOKS_DIV_CLASS_READ_BOOK, S.BOB
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.FAILED
    assert len(snapshot.records) == C.ONE
    assert (
        observation(snapshot.records[C.ZERO], S.RATING).value
        == C.TEST_STORYGRAPH_WRONG_OWNER_MID_KEEPS_ONLY_PREVIOUSLY_VERIFIED_BOOKS
    )
    assert not snapshot.termination_verified


@pytest.mark.parametrize(
    S.SOURCE_2,
    [
        S.TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_TEXT_2,
        S.TEST_STORYGRAPH_INVALID_AMBIGUOUS_OR_READING_DATES_ARE_FAILED_TEXT,
        S.TEST_STORYGRAPH_INVALID_AMBIGUOUS_OR_READING_DATES_ARE_FAILED_TEXT_2,
    ],
)
def test_invalid_ambiguous_or_reversed_reading_dates_are_failed(source_value) -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_INVALID_AMBIGUOUS_OR_READING_DATES_ARE_FAILED_TEXT_3, source_value
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert observation(snapshot.records[C.ZERO], S.READING_EVENTS).state == FieldState.FAILED
    assert len(snapshot.records[C.ZERO].reading_events) == C.ONE
    assert S.INVALID_READING_DATE in {issue.code for issue in snapshot.issues}


def test_read_count_does_not_invent_events_or_expected_work_count() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_READ_COUNT_DOES_NOT_INVENT_COUNT_DT_READ_COUNT_DT_DD,
        S.TEST_STORYGRAPH_READ_COUNT_DOES_NOT_INVENT_COUNT_DT_READ_COUNT_DT_DD_2,
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert snapshot.expected_count is C.NONE
    assert len(snapshot.records) == C.ONE
    assert len(snapshot.records[C.ZERO].reading_events) == C.TWO
    assert observation(snapshot.records[C.ZERO], S.READ_COUNT).value == C.FIVE
    assert S.READING_EVENTS_INCOMPLETE in {issue.code for issue in snapshot.issues}


def test_unknown_optional_fields_are_not_fabricated_empty() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_UNKNOWN_OPTIONAL_FIELDS_DT_DD_REFLECTIVE_HOPEFUL, S.EMPTY
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.COMPLETE
    assert observation(snapshot.records[C.ZERO], S.MOODS).state == FieldState.UNAVAILABLE
    assert observation(snapshot.records[C.ZERO], S.MOODS).value is C.NONE


def test_duplicate_appearances_merge_statuses_without_duplicate_history() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_CURRENT] = fixture(S.READ_PAGE_HTML)
    data[C.TEST_STORYGRAPH_PAUSED] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_DUPLICATE_APPEARANCES_MERGE_HISTORY_CLASS_READ_BOOKS,
        S.TEST_STORYGRAPH_DUPLICATE_APPEARANCES_HISTORY_CLASS_PAUSED_BOOKS,
    )
    browser = FakeBrowser(data)
    snapshot = StoryGraphConnector(browser).collect(ACCOUNT)
    book = snapshot.records[C.ZERO]
    assert len(snapshot.records) == C.ONE
    assert set(book.collections) == {S.READ, S.CURRENTLY_READING, S.PAUSED}
    assert book.status == ReadingStatus.UNKNOWN
    assert snapshot.state == SyncState.PARTIAL
    assert len(book.reading_events) == C.TWO
    assert browser.requests.count(C.TEST_STORYGRAPH_BOOK) == C.ONE


def test_discovered_dnf_and_paused_books_are_not_classified_as_read() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_READ] = empty()
    data[C.TEST_STORYGRAPH_PAUSED] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_DUPLICATE_APPEARANCES_MERGE_HISTORY_CLASS_READ_BOOKS,
        S.TEST_STORYGRAPH_DUPLICATE_APPEARANCES_HISTORY_CLASS_PAUSED_BOOKS,
    )
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_DISCOVERED_DNF_AND_PAUSED_SECTION_H2_YOUR_REVIEW_H
    )
    data[C.TEST_STORYGRAPH_DNF] = fixture(S.READ_PAGE_HTML).replace(S.BOOK_A_ID, S.BOOK_B_ID)
    data[
        S.TEST_STORYGRAPH_DISCOVERED_DNF_AND_NOT_CLASSIFIED_AS_READ_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        )
    ] = data[C.TEST_STORYGRAPH_BOOK]
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert {book.status for book in snapshot.records} == {ReadingStatus.PAUSED, ReadingStatus.DNF}
    assert all(not book.reading_events for book in snapshot.records)
    assert snapshot.state == SyncState.COMPLETE


def test_missing_status_surfaces_remain_unsupported_not_empty() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_PROFILE] = owned(
        S.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_ARE_REQUIRED_H1_ALICE_H1
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert not snapshot.termination_verified
    assert snapshot.capabilities[S.COLLECTION_PAUSED] == FieldState.UNSUPPORTED
    assert snapshot.capabilities[S.COLLECTION_DID_NOT_FINISH] == FieldState.UNSUPPORTED


def test_empty_list_requires_owner_and_explicit_empty_evidence() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_READ] = owned(
        S.TEST_STORYGRAPH_WRONG_OWNER_MID_COLLECTION_BOOKS_DIV_CLASS_READ_BOOK
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert S.EMPTY_COLLECTION_UNVERIFIED in {issue.code for issue in snapshot.issues}


def test_explicit_empty_owned_library_can_complete_without_fake_field_values() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_READ] = empty()
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.COMPLETE
    assert not snapshot.records
    assert snapshot.identity_verified and snapshot.termination_verified
    assert snapshot.capabilities[S.RATING] == FieldState.EMPTY


def test_actual_next_links_are_followed_and_progress_cursor_is_safe() -> None:
    data = pages()
    next_url = S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_IS_SAFE_NEXT_URL_TEMPLATE.format(
        v0=C.TEST_STORYGRAPH_READ
    )
    data[C.TEST_STORYGRAPH_READ] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_A_ID_NEXT_LINK_DATA_REMO,
    )
    data[next_url] = (
        fixture(S.READ_PAGE_HTML)
        .replace(S.BOOK_A_ID, S.BOOK_B_ID)
        .replace(
            S.TEST_STORYGRAPH_SOURCE_STRUCTURES_PERSONAL_PRESERVED_THE_FIRST_BOOK,
            S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_BOOK_B,
        )
    )
    data[
        S.TEST_STORYGRAPH_DISCOVERED_DNF_AND_NOT_CLASSIFIED_AS_READ_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        )
    ] = fixture(S.BOOK_HTML).replace(S.BOOK_A_ID, S.BOOK_B_ID)
    progress: list[CollectionProgress] = []
    browser = FakeBrowser(data)
    snapshot = StoryGraphConnector(browser).collect(ACCOUNT, on_progress=progress.append)
    assert snapshot.state == SyncState.COMPLETE
    assert len(snapshot.records) == C.TWO
    assert next_url in browser.requests
    assert any(item.cursor for item in progress)
    assert all(
        S.SENSITIVE_TOKEN not in (item.cursor or S.EMPTY) + item.message for item in progress
    )
    assert all(
        S.GOODREADS_SAFE_URL_TEXT not in obs.source_url
        for book in snapshot.records
        for obs in book.observations
    )


@pytest.mark.parametrize(S.REPEAT_CURSOR, [C.FALSE, C.TRUE])
def test_pagination_repetition_is_partial_and_retains_records(repeat_cursor) -> None:
    data = pages()
    target = (
        C.TEST_STORYGRAPH_READ
        if repeat_cursor
        else S.TEST_STORYGRAPH_PAGINATION_REPETITION_RECORDS_TARGET_TEMPLATE.format(
            v0=C.TEST_STORYGRAPH_READ
        )
    )
    data[C.TEST_STORYGRAPH_READ] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_PAGINATION_REPETITION_AND_RETAINS_RECORDS_TEMPLATE.format(v0=target),
    )
    if not repeat_cursor:
        data[target] = fixture(S.READ_PAGE_HTML)
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert len(snapshot.records) == C.ONE
    assert not snapshot.termination_verified
    assert any(issue.code.startswith(S.PAGINATION_REPEATED) for issue in snapshot.issues)


def test_capped_walk_is_partial_without_discarding_first_page() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_READ] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_CAPPED_WALK_IS_PARTIAL_ID_NEXT_LINK_HREF_PAGE_MORE,
    )
    browser = FakeBrowser(data)
    snapshot = StoryGraphConnector(browser, max_pages=C.ONE).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert len(snapshot.records) == C.ONE
    assert snapshot.pages_seen == C.ONE
    assert S.PAGINATION_LIMIT in {issue.code for issue in snapshot.issues}
    assert (
        S.TEST_STORYGRAPH_PAGINATION_REPETITION_RECORDS_TARGET_TEMPLATE.format(
            v0=C.TEST_STORYGRAPH_READ
        )
        not in browser.requests
    )


@pytest.mark.parametrize(
    S.TARGET,
    [
        S.TEST_STORYGRAPH_UNSAFE_OR_CROSS_OWNER_EXAMPLE_BOOKS_READ_ALICE_PA,
        S.TEST_STORYGRAPH_UNSAFE_OR_CROSS_LINK_IS_NEVER_REQUESTED_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        ),
        S.TEST_STORYGRAPH_UNSAFE_OR_CROSS_LINK_IS_NEVER_REQUESTED_TEMPLATE_2.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        ),
        S.TEST_STORYGRAPH_UNSAFE_OR_CROSS_LINK_IS_NEVER_REQUESTED_TEMPLATE_3.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        ),
    ],
)
def test_unsafe_or_cross_owner_next_link_is_never_requested(target) -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_READ] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_PAGINATION_REPETITION_AND_RETAINS_RECORDS_TEMPLATE.format(v0=target),
    )
    browser = FakeBrowser(data)
    snapshot = StoryGraphConnector(browser).collect(ACCOUNT)
    assert snapshot.state in {SyncState.PARTIAL, SyncState.BLOCKED}
    assert target not in browser.requests
    assert len(snapshot.records) == C.ONE


def test_unsafe_final_redirect_is_rejected_with_injected_browser() -> None:
    snapshot = StoryGraphConnector(
        FakeBrowser(
            {
                C.TEST_STORYGRAPH_PROFILE: PageDocument(
                    S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_EVIL_EXAMPLE,
                    owned(S.EMPTY),
                )
            }
        )
    ).collect(ACCOUNT)
    assert snapshot.state == SyncState.BLOCKED
    assert not snapshot.records


def test_detail_failure_keeps_list_membership_and_other_collected_details() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_DETAIL_FAILURE_KEEPS_LIST_DETAILS_A_HREF_REVIEWS_REV,
    )
    data[
        S.TEST_STORYGRAPH_DETAIL_FAILURE_OTHER_COLLECTED_DETAILS_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        )
    ] = ConnectorError(
        S.TEST_STORYGRAPH_DETAIL_FAILURE_KEEPS_DETAILS_SOURCE_TIMED_OUT,
        code=S.BROWSER_TIMEOUT,
        retryable=C.TRUE,
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert len(snapshot.records) == C.ONE
    assert (
        observation(snapshot.records[C.ZERO], S.RATING).value
        == C.TEST_STORYGRAPH_DETAIL_FAILURE_KEEPS_AND_OTHER_COLLECTED_DETAILS
    )
    assert len(snapshot.records[C.ZERO].reading_events) == C.TWO
    assert S.BROWSER_TIMEOUT in {issue.code for issue in snapshot.issues}


def test_missing_auth_mid_detail_keeps_recovered_data_and_explicit_state() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_MISSING_AUTH_MID_DETAIL_STATE_A_HREF_REVIEWS_REVI,
    )
    data[
        S.TEST_STORYGRAPH_DETAIL_FAILURE_OTHER_COLLECTED_DETAILS_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        )
    ] = ConnectorError(
        S.TEST_STORYGRAPH_MISSING_AUTH_MID_EXPLICIT_STATE_NEEDS_OWNER_LOGIN,
        state=SyncState.NEEDS_AUTH,
        code=S.NEEDS_AUTH,
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.NEEDS_AUTH
    assert len(snapshot.records) == C.ONE
    assert (
        observation(snapshot.records[C.ZERO], S.RATING).value
        == C.TEST_STORYGRAPH_MISSING_AUTH_MID_RECOVERED_DATA_AND_EXPLICIT_STATE
    )


def test_discovered_review_cannot_attribute_another_readers_text() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_DISCOVERED_REVIEW_CANNOT_HREF_REVIEWS_REVIEW_B_YOU
    )
    data[
        S.TEST_STORYGRAPH_DISCOVERED_REVIEW_ANOTHER_READERS_TEXT_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        )
    ] = owned(S.TEST_STORYGRAPH_DISCOVERED_REVIEW_CANNOT_ARTICLE_ITEMPROP_REVIEW_A_H)
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert observation(snapshot.records[C.ZERO], S.REVIEW).state == FieldState.FAILED
    assert (
        S.TEST_STORYGRAPH_DISCOVERED_REVIEW_CANNOT_TEXT_BOB_SECRET_REVIEW
        not in snapshot.model_dump_json()
    )


def history_page(event_id: str, date: str, next_link: str = S.EMPTY) -> str:
    return owned(S.TEST_STORYGRAPH_HISTORY_PAGE_TEMPLATE.format(v0=event_id, v1=date) + next_link)


def test_discovered_personal_history_follows_next_and_preserves_distinct_events() -> None:
    data = pages()
    history = S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_DISTINCT_EVENTS_HISTORY_TEMPLATE.format(
        v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
    )
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_DISTINCT_EVENTS_TEMPLATE.format(v0=history)
    )
    data[history] = history_page(
        S.EVENT_1,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_HISTORY_EVENTS_A_REL_NEXT_H,
    )
    data[S.TEST_STORYGRAPH_PAGINATION_REPETITION_RECORDS_TARGET_TEMPLATE.format(v0=history)] = (
        history_page(
            S.EVENT_2, S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT_2
        )
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.COMPLETE
    assert [event.finished.value for event in snapshot.records[C.ZERO].reading_events] == [
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT_2,
    ]


def test_repeated_history_is_partial_and_retains_first_event() -> None:
    data = pages()
    history = S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_DISTINCT_EVENTS_HISTORY_TEMPLATE.format(
        v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
    )
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_REPEATED_HISTORY_IS_AND_RETAINS_FIRST_EVENT_TEMPLATE.format(v0=history)
    )
    body = history_page(
        S.EVENT_1,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_HISTORY_EVENTS_A_REL_NEXT_H,
    )
    data[history] = body
    data[S.TEST_STORYGRAPH_PAGINATION_REPETITION_RECORDS_TARGET_TEMPLATE.format(v0=history)] = body
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert len(snapshot.records[C.ZERO].reading_events) == C.ONE
    assert S.HISTORY_REPEATED_PAGE in {issue.code for issue in snapshot.issues}


def test_export_links_are_ignored_even_when_present_on_owner_profile() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_PROFILE] = fixture(S.PROFILE_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_EXPORT_LINKS_ARE_IGNORED_A_HREF_EXPORT_EXPORT_AL,
    )
    browser = FakeBrowser(data)
    StoryGraphConnector(browser).collect(ACCOUNT)
    assert all(S.EXPORT not in url for url in browser.requests)


def test_progress_failure_is_not_swallowed_as_collection_success() -> None:

    def fail(_progress: CollectionProgress) -> None:
        raise RuntimeError(S.TEST_STORYGRAPH_PROGRESS_FAILURE_IS_SUCCESS_FAIL_STORAGE_UNAVAILABLE)

    with pytest.raises(
        RuntimeError, match=S.TEST_STORYGRAPH_PROGRESS_FAILURE_IS_SUCCESS_FAIL_STORAGE_UNAVAILABLE
    ):
        StoryGraphConnector(FakeBrowser(pages())).collect(ACCOUNT, on_progress=fail)


def test_review_text_cannot_supply_fake_owner_or_empty_collection_evidence() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_PROFILE] = owned(
        S.TEST_STORYGRAPH_AUTHENTICATION_AND_OWNER_ARE_REQUIRED_H1_ALICE_H1
    )
    data[C.TEST_STORYGRAPH_READ] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_EMPTY_COLLECTION_EVIDENCE_ARTICLE,
        S.TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_SUPPLY_EVIDENCE_SECTION_H2_YOUR_R,
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.capabilities[S.COLLECTION_PAUSED] == FieldState.UNSUPPORTED
    assert snapshot.capabilities[S.COLLECTION_DID_NOT_FINISH] == FieldState.UNSUPPORTED
    impostor = PageDocument(
        C.TEST_STORYGRAPH_PROFILE,
        S.TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_EVIDENCE_IMPOSTOR_MAIN_ARTICLE_A,
    )
    assert (
        StoryGraphConnector(FakeBrowser({C.TEST_STORYGRAPH_PROFILE: impostor}))
        .collect(ACCOUNT)
        .state
        == SyncState.NEEDS_AUTH
    )


def test_nested_other_reader_heading_is_not_an_owner_review() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_NESTED_OTHER_READER_HEADING_ITEMPROP_REVIEW_A_HREF_P
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert snapshot.state == SyncState.PARTIAL
    assert observation(snapshot.records[C.ZERO], S.RATING).state == FieldState.UNAVAILABLE
    assert (
        S.TEST_STORYGRAPH_NESTED_OTHER_READER_OWNER_REVIEW_BOB_PRIVATE_TEXT
        not in snapshot.model_dump_json()
    )


@pytest.mark.parametrize(
    S.EVENT_ID, [S.EMPTY, S.TEST_STORYGRAPH_SAME_EVENT_OBSERVED_NOT_DUPLICATED_ID_REAL_EVENT]
)
def test_same_event_observed_with_different_date_text_is_not_duplicated(event_id) -> None:
    data = pages()
    list_history = S.TEST_STORYGRAPH_SAME_EVENT_OBSERVED_WITH_LIST_HISTORY_SECTION_H2_YO
    data[C.TEST_STORYGRAPH_READ] = fixture(S.READ_PAGE_HTML).replace(
        S.TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_EMPTY_COLLECTION_EVIDENCE_ARTICLE,
        list_history + S.TEST_STORYGRAPH_REVIEW_TEXT_CANNOT_EMPTY_COLLECTION_EVIDENCE_ARTICLE,
    )
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_SAME_EVENT_OBSERVED_TEXT_IS_NOT_DUPLICATED_TEMPLATE.format(v0=event_id)
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert len(snapshot.records[C.ZERO].reading_events) == C.ONE
    if event_id:
        assert snapshot.records[C.ZERO].reading_events[C.ZERO].source_event_id == S.REAL_EVENT


def test_two_actual_same_day_events_without_ids_are_not_collapsed() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_TWO_ACTUAL_SAME_DAY_SECTION_H2_YOUR_READING_HI
    )
    snapshot = StoryGraphConnector(FakeBrowser(data)).collect(ACCOUNT)
    assert len(snapshot.records[C.ZERO].reading_events) == C.TWO
    assert all(event.source_event_id is C.NONE for event in snapshot.records[C.ZERO].reading_events)


def test_history_page_cap_preserves_events_and_marks_field_failed() -> None:
    data = pages()
    history = S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_DISTINCT_EVENTS_HISTORY_TEMPLATE.format(
        v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
    )
    data[C.TEST_STORYGRAPH_BOOK] = owned(
        S.TEST_STORYGRAPH_REPEATED_HISTORY_IS_AND_RETAINS_FIRST_EVENT_TEMPLATE.format(v0=history)
    )
    data[history] = history_page(
        S.EVENT_1,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_PRESERVES_DISTINCT_EVENTS_TEXT,
        S.TEST_STORYGRAPH_DISCOVERED_PERSONAL_HISTORY_EVENTS_A_REL_NEXT_H,
    )
    browser = FakeBrowser(data)
    snapshot = StoryGraphConnector(browser, max_pages=C.ONE).collect(ACCOUNT)
    assert len(snapshot.records[C.ZERO].reading_events) == C.ONE
    assert observation(snapshot.records[C.ZERO], S.READING_EVENTS).state == FieldState.FAILED
    assert (
        S.TEST_STORYGRAPH_PAGINATION_REPETITION_RECORDS_TARGET_TEMPLATE.format(v0=history)
        not in browser.requests
    )
    assert S.HISTORY_PAGINATION_LIMIT in {issue.code for issue in snapshot.issues}


def test_mutating_personal_link_is_not_followed() -> None:
    data = pages()
    data[C.TEST_STORYGRAPH_BOOK] = fixture(S.BOOK_HTML).replace(
        S.TEST_STORYGRAPH_ACTUAL_NEXT_LINKS_ARE_PROGRESS_CURSOR_IS_SAFE_MAIN,
        S.TEST_STORYGRAPH_MUTATING_PERSONAL_LINK_REVIEWS_REVIEW_A_DATA_TURBO,
    )
    browser = FakeBrowser(data)
    snapshot = StoryGraphConnector(browser).collect(ACCOUNT)
    assert snapshot.state == SyncState.COMPLETE
    assert (
        S.TEST_STORYGRAPH_DETAIL_FAILURE_OTHER_COLLECTED_DETAILS_TEMPLATE.format(
            v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM
        )
        not in browser.requests
    )
