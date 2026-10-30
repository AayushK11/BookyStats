from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.connectors.goodreads import GoodreadsConnector
from bookystats.errors import ConnectorError
from bookystats.interfaces import HttpResponse, PageDocument
from bookystats.models import (
    Account,
    BookRecord,
    CollectionProgress,
    FieldState,
    Observation,
    ReadingStatus,
    Source,
    SyncState,
)
from bookystats.net import HttpClient

_FIXTURES = Path(__file__).parent / S.FIXTURES / S.GOODREADS


def sample(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding=S.UTF_8)


def feed(items: str = S.EMPTY, *, identity: str | None = C.NONE, shelf: str = S.TO_READ) -> str:
    identity = identity or S.TEST_GOODREADS_FEED_IDENTITY_TEMPLATE.format(
        v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM, v1=shelf
    )
    return S.TEST_GOODREADS_FEED_TEMPLATE.format(v0=shelf, v1=identity, v2=items)


def item(
    extra: str = S.EMPTY,
    *,
    book_id: str = S.TEST_GOODREADS_ITEM_BOOK_ID_TEXT,
    title: str = S.TEST_GOODREADS_ITEM_TITLE_TOILES,
) -> str:
    return S.TEST_GOODREADS_ITEM_TEMPLATE.format(v0=book_id, v1=title, v2=extra)


def with_count(xml: str, count: int) -> str:
    return xml.replace(
        S.TEST_GOODREADS_WITH_COUNT_CHANNEL, S.TEST_GOODREADS_WITH_COUNT_TEMPLATE.format(v0=count)
    )


@dataclass(frozen=C.TRUE)
class Reply:
    body: str | bytes
    status: int = C.TEST_GOODREADS_REPLY_STATUS
    url: str | None = C.NONE


class FakeHttp:
    def __init__(self, *replies: Reply | ConnectorError | OSError) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        assert self.replies, S.TEST_GOODREADS_FAKEHTTP_FETCH_UNEXPECTED_HTTP_FETCH
        reply = self.replies.pop(C.ZERO)
        if isinstance(reply, Exception):
            raise reply
        body = reply.body.encode(S.UTF_8) if isinstance(reply.body, str) else reply.body
        return HttpResponse(
            reply.url or url,
            reply.status,
            {S.CONTENT_TYPE_2: S.TEST_GOODREADS_FAKEHTTP_FETCH_APPLICATION_RSS_XML},
            body,
        )


class FakeBrowser:
    def __init__(self, *replies: Reply | ConnectorError) -> None:
        self.replies = list(replies)
        self.calls: list[str] = []

    def fetch(self, url: str, *, wait_for: str | None = C.NONE) -> PageDocument:
        self.calls.append(url)
        assert wait_for is C.NONE
        assert self.replies, S.TEST_GOODREADS_FAKEBROWSER_FETCH_UNEXPECTED_BROWSER_FETCH
        reply = self.replies.pop(C.ZERO)
        if isinstance(reply, ConnectorError):
            raise reply
        assert isinstance(reply.body, str)
        return PageDocument(reply.url or url, reply.body, reply.status)


@pytest.fixture
def account() -> Account:
    return Account(
        source=Source.GOODREADS,
        account_id=S.TEST_GOODREADS_ACCOUNT_ACCOUNT_ID_TEXT,
        profile_url=S.TEST_GOODREADS_ACCOUNT_PROFILE_URL_TEMPLATE.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        ),
    )


def observation(book: BookRecord, name: str) -> Observation:
    return next(value for value in book.observations if value.field == name)


def browser_connector(
    *pages: Reply | ConnectorError, max_pages: int = C.TEST_GOODREADS_BROWSER_CONNECTOR_MAX_PAGES
) -> tuple[GoodreadsConnector, FakeHttp, FakeBrowser]:
    http = FakeHttp(Reply(S.EMPTY, status=C.BROWSER_CONNECTOR_HTTP_STATUS))
    browser = FakeBrowser(*pages)
    return (GoodreadsConnector(http, browser, max_pages=max_pages), http, browser)


def test_construction_performs_no_io(account: Account) -> None:
    http = FakeHttp()
    browser = FakeBrowser()
    GoodreadsConnector(http, browser)
    assert http.calls == browser.calls == []


@pytest.mark.parametrize(
    S.LIMIT, [C.ZERO, -C.ONE, C.TRUE, C.TEST_GOODREADS_INVALID_PAGE_LIMIT_IS_REJECTED_WITHOUT_FETCH]
)
def test_invalid_page_limit_is_rejected_without_fetch(limit: int) -> None:
    http = FakeHttp()
    with pytest.raises(
        ValueError, match=S.TEST_GOODREADS_INVALID_PAGE_LIMIT_FETCH_MATCH_POSITIVE_INTEGER
    ):
        GoodreadsConnector(http, max_pages=limit)
    assert not http.calls


def test_rejects_an_account_for_a_different_source() -> None:
    http = FakeHttp()
    account = Account(
        source=Source.STORYGRAPH,
        account_id=S.READER,
        profile_url=S.TEST_REJECTS_AN_ACCOUNT_FOR_A_APP_THESTORYGRAPH_COM_PROFILE_READER,
    )
    with pytest.raises(
        ValueError, match=S.TEST_GOODREADS_REJECTS_AN_ACCOUNT_SOURCE_MATCH_GOODREADS_READER
    ):
        GoodreadsConnector(http).collect(account)
    assert not http.calls


def test_rss_walks_short_pages_to_a_verified_empty_tail(account: Account) -> None:
    http = FakeHttp(
        Reply(sample(S.RSS_FIRST_XML)),
        Reply(sample(S.RSS_SECOND_XML)),
        Reply(sample(S.RSS_EMPTY_XML)),
    )
    browser = FakeBrowser()
    progress: list[CollectionProgress] = []
    result = GoodreadsConnector(http, browser).collect(account, on_progress=progress.append)
    assert result.state == SyncState.COMPLETE
    assert result.identity_verified and result.termination_verified
    assert result.source == Source.GOODREADS
    assert result.collection == S.TO_READ
    assert result.pages_seen == C.THREE
    assert result.expected_count is C.NONE
    assert not result.issues
    assert [book.source_id for book in result.records] == [
        S.TEST_GOODREADS_ITEM_BOOK_ID_TEXT,
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT,
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_2,
    ]
    assert [event.pages_seen for event in progress] == [C.ONE, C.TWO, C.THREE]
    assert [len(event.records) for event in progress] == [C.TWO, C.ONE, C.ZERO]
    assert [call[C.ONE] for call in http.calls] == [
        {
            S.SHELF: S.TO_READ,
            S.PAGE: str(page),
            S.PER_PAGE: S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_3,
        }
        for page in [C.ONE, C.TWO, C.THREE]
    ]
    assert all(
        call[C.ZERO]
        == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_TEMPLATE.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        )
        for call in http.calls
    )
    assert not browser.calls
    first, second, third = result.records
    assert first.title == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_RBITA_CAF
    assert first.authors == (S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_EMPTY_TAIL_MAR_A_S_ENZ,)
    assert first.isbns == (S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,)
    assert first.shelves == (
        S.TO_READ,
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_FICCI_N,
        S.OWNED,
    )
    assert all(book.status == ReadingStatus.TO_READ for book in result.records)
    assert all(book.collections == (S.TO_READ,) for book in result.records)
    assert all(book.reading_events == () for book in result.records)
    assert (
        first.added_at is not C.NONE
        and first.added_at.value
        == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_5
    )
    assert (
        first.added_at.raw == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_A_VERIFIED_EMPTY_TAIL_MON_JUL
    )
    assert second.added_at is not C.NONE and second.added_at.precision == S.MONTH
    assert third.added_at is not C.NONE and third.added_at.precision == S.YEAR
    assert third.title == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_EMPTY_TAIL_THE_QUIET_MAP
    assert (
        observation(first, S.PAGE_COUNT).value
        == C.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL
    )
    assert (
        observation(first, S.COMMUNITY_RATING).value
        == C.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_2
    )
    assert (
        observation(first, S.PUBLICATION_DATE).value
        == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_6
    )
    assert observation(first, S.GOODREADS_PERSONAL_RATING).state == FieldState.EMPTY
    assert observation(second, S.GOODREADS_PERSONAL_RATING).value == C.FIVE
    assert observation(second, S.PAGE_COUNT).state == FieldState.UNAVAILABLE
    assert observation(second, S.PAGE_COUNT).value is C.NONE
    assert all(value.field not in {S.RATING, S.REVIEW} for value in first.observations)
    assert result.capabilities[S.WATCHLIST] == FieldState.PRESENT
    assert all(
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_KEY not in book.url
        for book in result.records
    )
    assert all(
        S.GOODREADS_SAFE_URL_TEXT not in value.source_url
        for book in result.records
        for value in book.observations
    )
    assert all(
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TOKEN
        not in (event.cursor or S.EMPTY)
        for event in progress
    )


def test_common_http_client_contract_without_real_network(account: Account) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == S.WWW_GOODREADS_COM
        assert (
            request.url.path == S.TEST_GOODREADS_COMMON_HTTP_CLIENT_NETWORK_RESPOND_REVIEW_LIST_RSS
        )
        assert (
            request.url.params[S.PER_PAGE]
            == S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_3
        )
        assert request.url.params[S.SHELF] == S.TO_READ
        xml = (
            sample(S.RSS_FIRST_XML)
            if request.url.params[S.PAGE] == S.SCHEDULING_TASK_XML_TEXT
            else sample(S.RSS_EMPTY_XML)
        )
        return httpx.Response(
            C.TEST_GOODREADS_COMMON_HTTP_CLIENT_WITHOUT_REAL_NETWORK_RESPOND,
            content=xml.encode(S.UTF_8),
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = HttpClient(
            allowed_hosts=(S.WWW_GOODREADS_COM, S.GOODREADS_COM), min_interval=C.ZERO, client=client
        )
        result = GoodreadsConnector(http).collect(account)
    assert result.state == SyncState.COMPLETE
    assert len(result.records) == C.TWO
    assert len(requests) == C.TWO


def test_empty_rss_is_complete_only_with_reader_channel_identity(account: Account) -> None:
    result = GoodreadsConnector(FakeHttp(Reply(sample(S.RSS_EMPTY_XML)))).collect(account)
    assert result.state == SyncState.COMPLETE
    assert result.records == ()
    assert result.pages_seen == C.ONE
    assert result.identity_verified and result.termination_verified
    assert result.capabilities[S.WATCHLIST] == FieldState.EMPTY


@pytest.mark.parametrize(
    S.IDENTITY,
    [
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_BOOKS_OR_AUTHOR_ID_TEMPLATE.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        ),
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_BOOKS_OR_AUTHOR_ID_TEMPLATE_2.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        ),
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_WWW_GOODREADS_COM_EVIL_INVA,
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_WWW_GOODREADS_COM_EVIL_INVA_2,
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_OR_AUTHOR_ID_JAVASCRIPT_ALERT,
    ],
)
def test_channel_identity_is_not_inferred_from_books_or_author_id(
    account: Account, identity: str
) -> None:
    browser = FakeBrowser()
    http = FakeHttp(Reply(feed(item(), identity=identity)))
    result = GoodreadsConnector(http, browser).collect(account)
    assert result.state != SyncState.COMPLETE
    assert not result.identity_verified
    assert not result.records
    assert len(http.calls) == C.ONE and (not browser.calls)


def test_missing_channel_reader_link_does_not_verify_identity(account: Account) -> None:
    xml = (
        S.TEST_GOODREADS_MISSING_CHANNEL_READER_CHANNEL_TITLE_READER_S_BOOKSH
        + item()
        + S.TEST_GOODREADS_MISSING_CHANNEL_READER_IDENTITY_XML_CHANNEL_RSS
    )
    result = GoodreadsConnector(FakeHttp(Reply(xml))).collect(account)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.IDENTITY_UNVERIFIED


def test_conflicting_atom_self_identity_is_rejected(account: Account) -> None:
    xml = sample(S.RSS_EMPTY_XML).replace(
        S.TEST_GOODREADS_CONFLICTING_ATOM_SELF_IS_REJECTED_XML_LIST_RSS,
        S.TEST_GOODREADS_CONFLICTING_ATOM_SELF_IS_REJECTED_XML_LIST_RSS_2,
    )
    result = GoodreadsConnector(FakeHttp(Reply(xml))).collect(account)
    assert result.state == SyncState.FAILED
    assert not result.identity_verified


def test_wrong_shelf_is_not_a_watchlist(account: Account) -> None:
    result = GoodreadsConnector(FakeHttp(Reply(feed(item(), shelf=S.READ)))).collect(account)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.WRONG_COLLECTION


@pytest.mark.parametrize(S.COUNT, [C.ZERO, C.TWO, C.FOUR])
def test_rss_expected_count_is_reconciled_without_discarding_records(
    account: Account, count: int
) -> None:
    result = GoodreadsConnector(
        FakeHttp(Reply(with_count(sample(S.RSS_FIRST_XML), count)), Reply(sample(S.RSS_EMPTY_XML)))
    ).collect(account)
    assert result.expected_count == count
    assert len(result.records) == C.TWO
    assert result.termination_verified
    assert result.state == (SyncState.COMPLETE if count == C.TWO else SyncState.PARTIAL)
    assert (S.COUNT_MISMATCH in {issue.code for issue in result.issues}) == (count != C.TWO)


def test_book_page_count_is_never_used_as_shelf_book_count(account: Account) -> None:
    xml = feed(item(S.TEST_GOODREADS_BOOK_PAGE_COUNT_IS_NEVER_ID_NUM_PAGES_NUM_PAGES_BOOK))
    result = GoodreadsConnector(FakeHttp(Reply(xml), Reply(feed()))).collect(account)
    assert result.state == SyncState.COMPLETE
    assert result.expected_count is C.NONE
    assert (
        observation(result.records[C.ZERO], S.PAGE_COUNT).value
        == C.TEST_GOODREADS_BOOK_PAGE_COUNT_IS_NEVER_USED_AS_SHELF_BOOK_COUNT
    )


@pytest.mark.parametrize(
    S.STATUS,
    [
        C.TEST_GOODREADS_ACCESS_BLOCK_IS_NOT_PERMISSION_FOR_BROWSER_FALLBACK,
        C.TEST_GOODREADS_ACCESS_BLOCK_IS_NOT_PERMISSION_FOR_BROWSER_FALLBACK_2,
    ],
)
def test_access_block_is_not_permission_for_browser_fallback(account: Account, status: int) -> None:
    http = FakeHttp(
        Reply(S.TEST_GOODREADS_ACCESS_BLOCK_IS_NOT_HTML_BODY_ACCESS_DENIED_BODY_HTML, status=status)
    )
    browser = FakeBrowser(Reply(sample(S.BROWSER_EMPTY_HTML)))
    result = GoodreadsConnector(http, browser).collect(account, interactive=C.TRUE)
    assert result.state == SyncState.BLOCKED
    assert result.issues[C.ZERO].code == S.ACCESS_BLOCKED
    assert len(http.calls) == C.ONE
    assert not browser.calls


@pytest.mark.parametrize(
    S.CHALLENGE,
    [
        S.TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_VERIFY_YOU_ARE_HUMAN_BO,
        S.TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_BODY_FORM_ID_CHALLENGE_FORM,
        S.TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_DIV_CLASS_H_CAPTCHA_DIV,
    ],
)
def test_success_status_challenge_cannot_trigger_browser_fallback(
    account: Account, challenge: str
) -> None:
    browser = FakeBrowser()
    result = GoodreadsConnector(FakeHttp(Reply(challenge)), browser).collect(account)
    assert result.state == SyncState.BLOCKED
    assert not browser.calls


def test_a_book_title_is_not_an_access_block(account: Account) -> None:
    xml = feed(
        item(
            S.TEST_GOODREADS_A_BOOK_TITLE_IS_HTML_ACCESS_DENIED_HTML_DESCRIPT,
            title=S.TEST_A_BOOK_TITLE_IS_NOT_AN_ACCESS_BLOCK_XML_TITLE_ACCESS_DENIED,
        )
    )
    result = GoodreadsConnector(FakeHttp(Reply(xml), Reply(feed()))).collect(account)
    assert result.state == SyncState.COMPLETE
    assert (
        result.records[C.ZERO].title
        == S.TEST_A_BOOK_TITLE_IS_NOT_AN_ACCESS_BLOCK_XML_TITLE_ACCESS_DENIED
    )


@pytest.mark.parametrize(
    (S.STATUS, S.BODY, S.URL),
    [
        (C.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_REQUIRES_ORDINARY_AUTH, S.EMPTY, C.NONE),
        (C.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_REQUIRES_ORDINARY_AUTH_2, S.EMPTY, C.NONE),
        (C.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_REQUIRES_ORDINARY_AUTH_3, S.EMPTY, C.NONE),
        (
            C.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_REQUIRES_ORDINARY_AUTH_4,
            S.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_THIS_PROFILE_IS_PRIVATE_BODY,
            C.NONE,
        ),
        (
            C.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_REQUIRES_ORDINARY_AUTH_4,
            S.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_INPUT_TYPE_PASSWORD_FORM_HTML,
            C.NONE,
        ),
        (
            C.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_REQUIRES_ORDINARY_AUTH_4,
            S.TEST_GOODREADS_PRIVATE_OR_UNAVAILABLE_FEED_BODY_SIGN_IN_BODY_HTML,
            S.TEST_GOODREADS_PRIVATE_OR_REQUIRES_ORDINARY_AUTH_TEMPLATE.format(
                v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
            ),
        ),
    ],
)
def test_private_or_unavailable_feed_requires_ordinary_auth(
    account: Account, status: int, body: str, url: str | None
) -> None:
    http = FakeHttp(Reply(body, status, url))
    result = GoodreadsConnector(http).collect(account)
    assert result.state == SyncState.NEEDS_AUTH
    assert not result.records
    assert not result.termination_verified


@pytest.mark.parametrize(
    S.BODY,
    [
        S.TEST_GOODREADS_ARBITRARY_HTML_OR_HTML_BODY_SOMETHING_CHANGED,
        S.TEST_GOODREADS_ARBITRARY_HTML_OR_IS_NOT_GENUINE_UNAVAILABILITY_RSS,
        S.EMPTY,
    ],
)
def test_arbitrary_html_or_malformed_rss_is_not_genuine_unavailability(
    account: Account, body: str
) -> None:
    browser = FakeBrowser()
    result = GoodreadsConnector(FakeHttp(Reply(body)), browser).collect(account)
    assert result.state == SyncState.FAILED
    assert not browser.calls


@pytest.mark.parametrize(
    S.DECLARATION,
    [
        S.TEST_GOODREADS_DTD_AND_ENTITIES_WITHOUT_EXPANSION_DOCTYPE_RSS,
        S.TEST_GOODREADS_DTD_AND_ENTITIES_ARE_RSS_ENTITY_XXE_SYSTEM_FILE_C,
        S.TEST_GOODREADS_DTD_AND_ENTITIES_ARE_RSS_ENTITY_ONE_ABC_ENTITY_TWO,
    ],
)
def test_dtd_and_entities_are_rejected_without_expansion(
    account: Account, declaration: str
) -> None:
    browser = FakeBrowser()
    result = GoodreadsConnector(FakeHttp(Reply(declaration + feed(item()))), browser).collect(
        account
    )
    assert result.state == SyncState.BLOCKED
    assert result.issues[C.ZERO].code == S.UNSAFE_XML
    assert not result.records and (not browser.calls)


def test_invalid_xml_encoding_is_reported_without_exposing_payload(account: Account) -> None:
    result = GoodreadsConnector(
        FakeHttp(Reply(S.TEST_GOODREADS_INVALID_XML_ENCODING_EXPOSING_PAYLOAD_RESULT_BYTES))
    ).collect(account)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.MALFORMED_XML


def test_xml_encoding_declaration_is_respected(account: Account) -> None:
    xml = S.TEST_GOODREADS_XML_ENCODING_DECLARATION_XML_XML_VERSION_ENCODING_ISO + feed(item())
    result = GoodreadsConnector(FakeHttp(Reply(xml.encode(S.ISO_8859_1)), Reply(feed()))).collect(
        account
    )
    assert result.state == SyncState.COMPLETE
    assert result.records[C.ZERO].title == S.TEST_GOODREADS_ITEM_TITLE_TOILES


def test_block_status_survives_invalid_encoding_and_challenge_redirect(account: Account) -> None:
    browser = FakeBrowser()
    result = GoodreadsConnector(
        FakeHttp(
            Reply(
                S.TEST_GOODREADS_BLOCK_STATUS_SURVIVES_CHALLENGE_REDIRECT_RESULT_BYTES,
                status=C.TEST_BLOCK_STATUS_SURVIVES_INVALID_CHALLENGE_REDIRECT_RESULT_STATUS,
                url=S.TEST_BLOCK_STATUS_SURVIVES_INVALID_REDIRECT_RESULT_URL_TEMPLATE.format(
                    v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
                ),
            )
        ),
        browser,
    ).collect(account)
    assert result.state == SyncState.BLOCKED
    assert not browser.calls


def test_browser_redirect_to_challenge_is_blocked_not_unknown_markup(account: Account) -> None:
    connector, _, _ = browser_connector(
        Reply(
            S.TEST_GOODREADS_SUCCESS_STATUS_CHALLENGE_VERIFY_YOU_ARE_HUMAN_BO,
            url=S.TEST_BROWSER_REDIRECT_TO_CHALLENGE_NOT_UNKNOWN_MARKUP_URL_TEMPLATE.format(
                v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
            ),
        )
    )
    result = connector.collect(account)
    assert result.state == SyncState.BLOCKED
    assert not result.records


@pytest.mark.parametrize(
    S.DESTINATION,
    [
        S.TEST_GOODREADS_UNEXPECTED_FINAL_URL_IS_EVIL_INVALID_REVIEW_LIST_RSS,
        S.TEST_GOODREADS_UNEXPECTED_FINAL_URL_IS_GOODREADS_COM_REVIEW_LIST_RSS,
        S.TEST_GOODREADS_UNEXPECTED_FINAL_URL_REJECTED_BEFORE_RECORDS_TEMPLATE.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        ),
        S.TEST_GOODREADS_UNEXPECTED_FINAL_URL_REJECTED_BEFORE_RECORDS_TEMPLATE_2.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        ),
    ],
)
def test_unexpected_final_url_is_rejected_before_records(
    account: Account, destination: str
) -> None:
    result = GoodreadsConnector(FakeHttp(Reply(sample(S.RSS_FIRST_XML), url=destination))).collect(
        account
    )
    assert result.state != SyncState.COMPLETE
    assert not result.records


@pytest.mark.parametrize(
    S.LINK,
    [
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_OR_AUTHOR_ID_JAVASCRIPT_ALERT,
        S.TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_HTTPS_EVIL_INVALID_BOOK_SHOW,
        S.TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_HTTPS_WWW_GOODREADS_COM_EVIL,
        S.TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_DISCARD_OTHER_ROWS_TEMPLATE.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        ),
    ],
)
def test_malicious_or_mismatched_book_links_do_not_discard_other_rows(
    account: Account, link: str
) -> None:
    xml = feed(
        item(S.TEST_GOODREADS_MALICIOUS_OR_MISMATCHED_OTHER_ROWS_XML_TEMPLATE.format(v0=link))
        + item(book_id=S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT)
    )
    result = GoodreadsConnector(FakeHttp(Reply(xml), Reply(feed()))).collect(account)
    assert result.state == SyncState.PARTIAL
    assert [book.source_id for book in result.records] == [
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT
    ]
    assert result.issues
    assert all(S.EVIL_INVALID not in issue.message for issue in result.issues)


def test_feed_failure_keeps_prior_pages_and_emits_failed_page_progress(account: Account) -> None:
    http = FakeHttp(
        Reply(sample(S.RSS_FIRST_XML)),
        ConnectorError(
            S.TEST_GOODREADS_FEED_FAILURE_KEEPS_HTTP_GOODREADS_REQUEST_TIMED,
            code=S.TIMEOUT,
            retryable=C.TRUE,
        ),
    )
    progress: list[CollectionProgress] = []
    result = GoodreadsConnector(http).collect(account, on_progress=progress.append)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO
    assert result.pages_seen == C.TWO
    assert result.identity_verified and (not result.termination_verified)
    assert result.issues[C.ZERO].code == S.TIMEOUT
    assert [len(event.records) for event in progress] == [C.TWO, C.ZERO]


def test_progress_persistence_errors_are_not_mistaken_for_source_errors(account: Account) -> None:

    def failing_callback(progress: CollectionProgress) -> None:
        raise OSError(S.TEST_GOODREADS_PROGRESS_PERSISTENCE_FAILING_CALLBACK_THE_LOCAL)

    http = FakeHttp(Reply(sample(S.RSS_FIRST_XML)))
    with pytest.raises(
        OSError, match=S.TEST_GOODREADS_PROGRESS_PERSISTENCE_MATCH_LOCAL_PROGRESS_STORE
    ):
        GoodreadsConnector(http).collect(account, on_progress=failing_callback)
    assert len(http.calls) == C.ONE


@pytest.mark.parametrize(
    (S.STATUS, S.STATE),
    [
        (C.TEST_GOODREADS_MID_FEED_ACCESS_FAILURE_DOES_NOT_RESTART_OR_BYPASS, SyncState.NEEDS_AUTH),
        (
            C.TEST_GOODREADS_MID_FEED_ACCESS_FAILURE_DOES_NOT_RESTART_OR_BYPASS_2,
            SyncState.NEEDS_AUTH,
        ),
        (C.TEST_GOODREADS_MID_FEED_ACCESS_FAILURE_DOES_NOT_RESTART_OR_BYPASS_3, SyncState.BLOCKED),
    ],
)
def test_mid_feed_access_failure_does_not_restart_or_bypass(
    account: Account, status: int, state: SyncState
) -> None:
    browser = FakeBrowser()
    http = FakeHttp(Reply(sample(S.RSS_FIRST_XML)), Reply(S.EMPTY, status=status))
    result = GoodreadsConnector(http, browser).collect(account)
    assert result.state == state
    assert len(result.records) == C.TWO
    assert not result.termination_verified
    assert not browser.calls


def test_repeated_rss_page_is_partial_not_success(account: Account) -> None:
    http = FakeHttp(Reply(sample(S.RSS_FIRST_XML)), Reply(sample(S.RSS_FIRST_XML)))
    result = GoodreadsConnector(http).collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO and result.pages_seen == C.TWO
    assert not result.termination_verified
    assert S.PAGINATION_NO_PROGRESS in {issue.code for issue in result.issues}


def test_page_cap_does_not_treat_a_short_page_as_end(account: Account) -> None:
    http = FakeHttp(Reply(sample(S.RSS_FIRST_XML)))
    result = GoodreadsConnector(http, max_pages=C.ONE).collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO and result.pages_seen == C.ONE
    assert not result.termination_verified
    assert result.issues[-C.ONE].code == S.PAGE_LIMIT


def test_per_page_limit_is_enforced(account: Account) -> None:
    xml = feed(
        S.EMPTY.join(
            item(book_id=str(index))
            for index in range(C.TEST_GOODREADS_PER_PAGE_LIMIT_IS_ENFORCED_XML)
        )
    )
    result = GoodreadsConnector(FakeHttp(Reply(xml))).collect(account)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.PAGE_TOO_LARGE


def test_duplicate_ids_in_one_page_remain_non_authoritative(account: Account) -> None:
    result = GoodreadsConnector(FakeHttp(Reply(feed(item() + item())), Reply(feed()))).collect(
        account
    )
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.ONE
    assert S.DUPLICATE_RECORD in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    S.ISBN,
    [
        S.TEST_GOODREADS_INVALID_ISBN_IS_NOT_PROMOTED_TO_AN_IDENTIFIER_TEXT,
        S.NOT_AN_ISBN,
        S.TEST_GOODREADS_INVALID_ISBN_IS_NOT_PROMOTED_TO_AN_IDENTIFIER_TEXT_2,
    ],
)
def test_invalid_isbn_is_not_promoted_to_an_identifier(account: Account, isbn: str) -> None:
    result = GoodreadsConnector(
        FakeHttp(
            Reply(
                feed(
                    item(
                        S.TEST_GOODREADS_INVALID_ISBN_IS_NOT_TO_AN_IDENTIFIER_RESULT_TEMPLATE.format(
                            v0=isbn
                        )
                    )
                )
            ),
            Reply(feed()),
        )
    ).collect(account)
    assert result.state == SyncState.PARTIAL
    assert result.records[C.ZERO].isbns == ()
    assert observation(result.records[C.ZERO], S.ISBNS).state == FieldState.FAILED
    assert S.INVALID_ISBN in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    (S.DATE, S.EXPECTED),
    [
        (
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT,
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT,
        ),
        (
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_2,
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_2,
        ),
        (
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_JUNE,
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_2,
        ),
        (
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_JUN,
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_3,
        ),
        (
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_T23,
            S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT_3,
        ),
    ],
)
def test_source_date_precision_is_retained(account: Account, date: str, expected: str) -> None:
    result = GoodreadsConnector(
        FakeHttp(
            Reply(
                feed(
                    item(
                        S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_RESULT_TEMPLATE.format(
                            v0=date
                        )
                    )
                )
            ),
            Reply(feed()),
        )
    ).collect(account)
    assert result.state == SyncState.COMPLETE
    added = result.records[C.ZERO].added_at
    assert added is not C.NONE and added.value == expected
    assert added.raw == date
    observed = observation(result.records[C.ZERO], S.ADDED_AT)
    assert observed.value == expected
    assert observed.observed_at != added.value


@pytest.mark.parametrize(
    S.DATE,
    [
        S.TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_TEXT,
        S.TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_TEXT_2,
        S.TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_BECOMES_OBSERVATION_DATE_MAY,
        S.YESTERDAY,
        S.TEST_GOODREADS_AMBIGUOUS_OR_IMPOSSIBLE_OBSERVATION_DATE_MON_JUL,
    ],
)
def test_ambiguous_or_impossible_date_never_becomes_observation_date(
    account: Account, date: str
) -> None:
    result = GoodreadsConnector(
        FakeHttp(
            Reply(
                feed(
                    item(
                        S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_RESULT_TEMPLATE.format(
                            v0=date
                        )
                    )
                )
            ),
            Reply(feed()),
        )
    ).collect(account)
    assert result.state == SyncState.PARTIAL
    assert result.records[C.ZERO].added_at is C.NONE
    assert observation(result.records[C.ZERO], S.ADDED_AT).state == FieldState.FAILED
    assert S.INVALID_DATE in {issue.code for issue in result.issues}


def test_missing_metadata_is_not_fabricated(account: Account) -> None:
    result = GoodreadsConnector(FakeHttp(Reply(feed(item())), Reply(feed()))).collect(account)
    assert result.state == SyncState.COMPLETE
    book = result.records[C.ZERO]
    assert book.added_at is C.NONE
    assert book.edition_format is C.NONE and book.shelf_position is C.NONE
    assert book.isbns == ()
    for name in [S.PAGE_COUNT, S.PUBLICATION_DATE, S.COMMUNITY_RATING, S.GOODREADS_PERSONAL_RATING]:
        value = observation(book, name)
        assert value.state == FieldState.UNAVAILABLE and value.value is C.NONE


def test_zero_page_count_and_personal_rating_mean_empty_not_zero_values(account: Account) -> None:
    xml = feed(item(S.TEST_GOODREADS_ZERO_PAGE_COUNT_AND_XML_BOOK_NUM_PAGES_NUM_PAGE))
    result = GoodreadsConnector(FakeHttp(Reply(xml), Reply(feed()))).collect(account)
    assert result.state == SyncState.COMPLETE
    for name in [S.PAGE_COUNT, S.GOODREADS_PERSONAL_RATING]:
        value = observation(result.records[C.ZERO], name)
        assert value.state == FieldState.EMPTY and value.value is C.NONE


@pytest.mark.parametrize(
    S.RAW,
    [
        S.NAN_2,
        S.TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_IS_ISSUE_NOT_A_CRASH_TEXT,
        S.INFINITY,
        S.TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_IS_ISSUE_NOT_A_CRASH_TEXT_2
        * C.TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_IS_FIELD_ISSUE_NOT_A_CRASH,
    ],
)
def test_malformed_numeric_metadata_is_a_field_issue_not_a_crash(
    account: Account, raw: str
) -> None:
    xml = feed(
        item(S.TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_NOT_A_CRASH_XML_TEMPLATE.format(v0=raw))
    )
    result = GoodreadsConnector(FakeHttp(Reply(xml), Reply(feed()))).collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.ONE
    assert observation(result.records[C.ZERO], S.PAGE_COUNT).state == FieldState.FAILED


def test_multiple_authors_preserve_the_source_spelling(account: Account) -> None:
    xml = feed(item(S.TEST_GOODREADS_MULTIPLE_AUTHORS_PRESERVE_THE_FRAN_OISE_NO_L_AUTHOR))
    result = GoodreadsConnector(FakeHttp(Reply(xml), Reply(feed()))).collect(account)
    assert result.state == SyncState.COMPLETE
    assert result.records[C.ZERO].authors == (
        S.TEST_GOODREADS_MULTIPLE_AUTHORS_PRESERVE_SOURCE_SPELLING_JOS_LVARES,
        S.TEST_GOODREADS_MULTIPLE_AUTHORS_PRESERVE_THE_SPELLING_FRAN_OISE_NO_L,
    )


def test_browser_fallback_collects_published_table_layouts_and_matches_feed_membership(
    account: Account,
) -> None:
    connector, http, browser = browser_connector(
        Reply(sample(S.BROWSER_TABLE_HTML)), Reply(sample(S.BROWSER_FRAGMENT_HTML))
    )
    progress: list[CollectionProgress] = []
    result = connector.collect(account, interactive=C.TRUE, on_progress=progress.append)
    rss = GoodreadsConnector(
        FakeHttp(
            Reply(sample(S.RSS_FIRST_XML)),
            Reply(sample(S.RSS_SECOND_XML)),
            Reply(sample(S.RSS_EMPTY_XML)),
        )
    ).collect(account)
    assert result.state == SyncState.COMPLETE
    assert result.expected_count == C.THREE
    assert result.identity_verified and result.termination_verified
    assert result.pages_seen == C.THREE
    assert [len(event.records) for event in progress] == [C.ZERO, C.TWO, C.ONE]
    assert len(http.calls) == C.ONE and len(browser.calls) == C.TWO
    assert [
        (book.source_id, book.title, book.status, book.collections, book.shelves)
        for book in result.records
    ] == [
        (book.source_id, book.title, book.status, book.collections, book.shelves)
        for book in rss.records
    ]
    first, second, third = result.records
    assert first.authors == (S.TEST_GOODREADS_BROWSER_FALLBACK_COLLECTS_MEMBERSHIP_S_ENZ_MAR_A,)
    assert first.edition_format == S.HARDCOVER
    assert first.shelf_position == C.ONE
    assert (
        observation(first, S.PAGE_COUNT).value
        == C.TEST_GOODREADS_BROWSER_FALLBACK_COLLECTS_AND_MATCHES_FEED_MEMBERSHIP
    )
    assert (
        observation(first, S.COMMUNITY_RATING).value
        == C.TEST_GOODREADS_BROWSER_FALLBACK_COLLECTS_AND_MATCHES_FEED_MEMBERSHIP_2
    )
    assert (
        observation(first, S.COMMUNITY_RATINGS_COUNT).value
        == C.TEST_GOODREADS_BROWSER_FALLBACK_COLLECTS_AND_MATCHES_FEED_MEMBERSHIP_3
    )
    assert (
        observation(first, S.PUBLICATION_DATE).value
        == S.TEST_GOODREADS_BROWSER_FALLBACK_MATCHES_FEED_MEMBERSHIP_TEXT
    )
    assert (
        observation(first, S.FIRST_PUBLICATION_YEAR).value
        == C.TEST_GOODREADS_BROWSER_FALLBACK_COLLECTS_AND_MATCHES_FEED_MEMBERSHIP_4
    )
    assert observation(first, S.GOODREADS_PERSONAL_RATING).state == FieldState.EMPTY
    assert observation(second, S.GOODREADS_PERSONAL_RATING).value == C.FIVE
    assert observation(third, S.GOODREADS_PERSONAL_RATING).state == FieldState.UNAVAILABLE
    assert all(value.field != S.RATING for book in result.records for value in book.observations)
    assert all(
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TOKEN not in url
        and S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_KEY not in url
        for url in browser.calls
    )
    assert parse_qs(urlsplit(browser.calls[C.ONE]).query) == {
        S.SHELF: [S.TO_READ],
        S.PAGE: [S.TEST_GOODREADS_BROWSER_FALLBACK_MATCHES_FEED_MEMBERSHIP_TEXT_2],
        S.PER_PAGE: [S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_3],
    }


def test_verified_empty_browser_shelf_is_complete(account: Account) -> None:
    connector, _, _ = browser_connector(Reply(sample(S.BROWSER_EMPTY_HTML)))
    result = connector.collect(account)
    assert result.state == SyncState.COMPLETE
    assert result.expected_count == C.ZERO
    assert result.records == ()
    assert result.identity_verified and result.termination_verified
    assert result.capabilities[S.WATCHLIST] == FieldState.EMPTY


def test_browser_with_no_expected_count_walks_to_normal_empty_tail(account: Account) -> None:
    first = sample(S.BROWSER_TABLE_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_FIRST_TO_READ, S.TO_READ
    )
    second = sample(S.BROWSER_FRAGMENT_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_FIRST_TO_READ, S.TO_READ
    )
    empty = sample(S.BROWSER_EMPTY_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_EMPTY_TO_READ, S.TO_READ
    )
    connector, _, browser = browser_connector(Reply(first), Reply(second), Reply(empty))
    result = connector.collect(account)
    assert result.state == SyncState.COMPLETE
    assert result.expected_count is C.NONE
    assert result.termination_verified
    assert len(browser.calls) == C.THREE


def test_initial_empty_browser_shell_needs_an_explicit_zero_count(account: Account) -> None:
    html = sample(S.BROWSER_EMPTY_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_EMPTY_TO_READ, S.TO_READ
    )
    connector, _, _ = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.PARTIAL
    assert not result.termination_verified
    assert S.EMPTY_SHELF_UNVERIFIED in {issue.code for issue in result.issues}


def test_browser_rejects_logged_in_account_mismatch_before_collecting(account: Account) -> None:
    html = sample(S.BROWSER_TABLE_HTML).replace(
        S.TEST_GOODREADS_BROWSER_REJECTS_LOGGED_IN_A_HREF_REVIEW_LIST_MY_BO,
        S.TEST_GOODREADS_BROWSER_REJECTS_LOGGED_IN_A_HREF_REVIEW_LIST_MY_BO_2,
    )
    connector, _, browser = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.NEEDS_AUTH
    assert not result.identity_verified and (not result.records)
    assert S.ACCOUNT_MISMATCH in {issue.code for issue in result.issues}
    assert len(browser.calls) == C.ONE


def test_browser_requires_auth_identity_even_if_viewed_shelf_is_correct(account: Account) -> None:
    html = (
        sample(S.BROWSER_TABLE_HTML)
        .replace(
            S.TEST_GOODREADS_BROWSER_REQUIRES_AUTH_IS_CORRECT_HTML_MY_BOOKS,
            S.TEST_GOODREADS_BROWSER_REQUIRES_AUTH_IS_CORRECT_HTML_PUBLIC_BOOKS,
        )
        .replace(S.PROFILE_2, S.READER_2)
    )
    connector, _, _ = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.NEEDS_AUTH
    assert not result.records
    assert S.AUTH_IDENTITY_UNVERIFIED in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    S.HTML,
    [
        S.TEST_GOODREADS_BROWSER_LOGIN_OR_PRIVATE_FORM_INPUT_TYPE_PASSWORD_FOR,
        S.TEST_GOODREADS_BROWSER_LOGIN_OR_PRIVATE_THIS_MEMBER_S_PROFILE_IS,
    ],
)
def test_browser_login_or_private_page_is_not_an_empty_shelf(account: Account, html: str) -> None:
    connector, _, _ = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.NEEDS_AUTH
    assert not result.records and (not result.termination_verified)


@pytest.mark.parametrize(
    S.REPLACEMENT,
    [
        S.TEST_GOODREADS_UNKNOWN_BROWSER_MARKUP_SHELF_MAIN_NEW_INTERFACE_MAIN,
        S.TEST_GOODREADS_UNKNOWN_BROWSER_MARKUP_IS_BOOKS_TBODY_ID_BOOKSBODY_TR,
    ],
)
def test_unknown_browser_markup_is_not_an_empty_shelf(account: Account, replacement: str) -> None:
    html = sample(S.BROWSER_EMPTY_HTML).replace(
        S.TEST_GOODREADS_UNKNOWN_BROWSER_MARKUP_CLASS_TABLE_STACKED_TBODY, replacement
    )
    connector, _, _ = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.FAILED
    assert not result.termination_verified
    assert S.UNKNOWN_MARKUP in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    S.NEXT_URL,
    [
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_HTTPS_EVIL_INVALID_REVIEW,
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ,
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_READ_AM,
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ_2,
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ_3,
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_REVIEW_LIST_SHELF_TO_READ_4
        + S.TEST_GOODREADS_MALFORMED_NUMERIC_METADATA_IS_ISSUE_NOT_A_CRASH_TEXT_2
        * C.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_SHELF_OR_EXPAND_PAGE_SIZE,
        S.TEST_GOODREADS_CHANNEL_IDENTITY_IS_NOT_OR_AUTHOR_ID_JAVASCRIPT_ALERT,
    ],
)
def test_browser_pagination_cannot_leave_reader_shelf_or_expand_page_size(
    account: Account, next_url: str
) -> None:
    html = sample(S.BROWSER_TABLE_HTML).replace(
        S.TEST_GOODREADS_BROWSER_PAGINATION_CANNOT_HTML_REVIEW_LIST_SHELF_TO, next_url
    )
    connector, _, browser = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO
    assert not result.termination_verified
    assert len(browser.calls) == C.ONE


def test_browser_repeated_page_cannot_be_complete(account: Account) -> None:
    first = sample(S.BROWSER_TABLE_HTML)
    second = first.replace(
        S.TEST_GOODREADS_BROWSER_REPEATED_PAGE_BE_COMPLETE_SECOND_REL_NEXT,
        S.TEST_GOODREADS_BROWSER_REPEATED_PAGE_BE_COMPLETE_SECOND_REL_PREV,
    ).replace(S.TEST_GOODREADS_BROWSER_REPEATED_PAGE_CANNOT_BE_COMPLETE_SECOND_NEXT, S.PREVIOUS)
    connector, _, _ = browser_connector(Reply(first), Reply(second))
    result = connector.collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO
    assert not result.termination_verified
    assert S.PAGINATION_NO_PROGRESS in {issue.code for issue in result.issues}


def test_number_named_custom_shelf_is_not_mistaken_for_a_pagination_link(account: Account) -> None:
    html = sample(S.BROWSER_FRAGMENT_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_FIRST_TO_READ,
        S.TEST_GOODREADS_NUMBER_NAMED_CUSTOM_PAGINATION_LINK_HTML_TO_READ,
    )
    html = html.replace(
        S.TEST_GOODREADS_NUMBER_NAMED_CUSTOM_A_PAGINATION_LINK_HTML_ASIDE,
        S.TEST_GOODREADS_NUMBER_NAMED_CUSTOM_SHELF_HTML_A_HREF_REVIEW_LIST_SH,
    )
    connector, _, _ = browser_connector(Reply(html))
    result = connector.collect(account)
    assert result.state == SyncState.COMPLETE
    assert [book.source_id for book in result.records] == [
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_2
    ]


def test_browser_page_cap_remains_partial(account: Account) -> None:
    connector, _, _ = browser_connector(Reply(sample(S.BROWSER_TABLE_HTML)), max_pages=C.ONE)
    result = connector.collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO
    assert not result.termination_verified
    assert S.PAGE_LIMIT in {issue.code for issue in result.issues}


def test_browser_count_mismatch_preserves_records_and_verified_termination(
    account: Account,
) -> None:
    empty = sample(S.BROWSER_EMPTY_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_EMPTY_TO_READ,
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_FIRST_TO_READ,
    )
    connector, _, _ = browser_connector(Reply(sample(S.BROWSER_TABLE_HTML)), Reply(empty))
    result = connector.collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.TWO
    assert result.expected_count == C.THREE
    assert result.termination_verified
    assert S.COUNT_MISMATCH in {issue.code for issue in result.issues}


def test_browser_changing_shelf_count_is_not_authoritative(account: Account) -> None:
    changed = sample(S.BROWSER_FRAGMENT_HTML).replace(
        S.TEST_GOODREADS_BROWSER_WITH_NO_EXPECTED_EMPTY_TAIL_FIRST_TO_READ,
        S.TEST_GOODREADS_BROWSER_CHANGING_SHELF_AUTHORITATIVE_CHANGED_TO_READ,
    )
    connector, _, _ = browser_connector(Reply(sample(S.BROWSER_TABLE_HTML)), Reply(changed))
    result = connector.collect(account)
    assert result.state == SyncState.PARTIAL
    assert len(result.records) == C.THREE
    assert S.SHELF_CHANGED in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    S.ERROR,
    [
        ConnectorError(
            S.TEST_GOODREADS_BROWSER_FETCHER_COMPLETED_PAGES_SESSION_EXPIRED,
            state=SyncState.NEEDS_AUTH,
            code=S.NEEDS_AUTH,
        ),
        ConnectorError(
            S.TEST_GOODREADS_BROWSER_FETCHER_COMPLETED_PAGES_ACCESS_BLOCKED,
            state=SyncState.BLOCKED,
            code=S.ACCESS_BLOCKED,
        ),
        ConnectorError(
            S.TEST_GOODREADS_BROWSER_FETCHER_COMPLETED_PAGES_BROWSER_TIMEOUT,
            code=S.BROWSER_TIMEOUT,
            retryable=C.TRUE,
        ),
    ],
)
def test_browser_fetcher_failures_preserve_completed_pages(
    account: Account, error: ConnectorError
) -> None:
    connector, _, _ = browser_connector(Reply(sample(S.BROWSER_TABLE_HTML)), error)
    result = connector.collect(account)
    assert result.state == (SyncState.PARTIAL if error.state == SyncState.FAILED else error.state)
    assert len(result.records) == C.TWO
    assert not result.termination_verified
    assert error.code in {issue.code for issue in result.issues}
