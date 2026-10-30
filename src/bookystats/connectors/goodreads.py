from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from xml.etree.ElementTree import Element, ParseError

from bs4 import BeautifulSoup, Tag
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.dates import parse_date
from bookystats.errors import ConnectorError
from bookystats.identifiers import normalize_isbn
from bookystats.interfaces import BrowserFetcher, HttpFetcher, ProgressCallback
from bookystats.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    FieldState,
    Issue,
    Observation,
    PartialDate,
    ReadingStatus,
    Source,
    SyncState,
    utc_now,
)

_Scope = S.ObservationScope


class _FeedUnavailable(ConnectorError):
    pass


@dataclass
class _Run:
    started_at: str = field(default_factory=utc_now)
    records: dict[str, BookRecord] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    pages_seen: int = C.ZERO
    expected_count: int | None = C.NONE
    identity_verified: bool = C.FALSE
    termination_verified: bool = C.FALSE
    incomplete: bool = C.FALSE


@dataclass
class _Page:
    records: tuple[BookRecord, ...]
    item_count: int
    issues: list[Issue]
    expected_count: int | None = C.NONE
    has_next: bool = C.FALSE
    error: ConnectorError | None = C.NONE


def _failure(code: str, message: str, *, state: SyncState = SyncState.FAILED) -> ConnectorError:
    return ConnectorError(message, state=state, code=code)


def _issue(error: ConnectorError, source_id: str | None = C.NONE) -> Issue:
    return Issue(
        code=error.code, message=str(error), source_id=source_id, retryable=error.retryable
    )


def _text(value: str | None) -> str:
    if value is C.NONE:
        return S.EMPTY
    value = unescape(value)
    if re.search(S.GOODREADS_TEXT_A_ZA_Z_W_S, value):
        soup = BeautifulSoup(value, S.HTML_PARSER)
        for node in soup.select(S.GOODREADS_TEXT_SCRIPT_STYLE):
            node.decompose()
        value = soup.get_text(S.SPACE, strip=C.TRUE)
    return S.SPACE.join(value.split())


def _xml_text(node: Element, path: str) -> str | None:
    child = node.find(path)
    return C.NONE if child is C.NONE else _text(S.EMPTY.join(child.itertext()))


def _safe_url(
    value: str, *, base: str = S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM, allow_http: bool = C.FALSE
) -> str:
    value = unescape(value).strip()
    if not value or re.search(S.BROWSERCLIENT_CHECKED_URL_VALID_X00_X20, value):
        raise _failure(
            S.UNSAFE_LINK, S.GOODREADS_SAFE_URL_GOODREADS_SUPPLIED_AN_INVALID_SOURCE_LINK
        )
    try:
        parsed = urlsplit(urljoin(base, value))
        valid = (
            parsed.scheme in ({S.HTTPS, S.HTTP} if allow_http else {S.HTTPS})
            and parsed.hostname in C.GOODREADS_HOSTS
            and (not parsed.username)
            and (not parsed.password)
            and (
                parsed.port
                in (
                    C.NONE,
                    C.GOODREADS_SAFE_URL_VALID
                    if parsed.scheme == S.HTTPS
                    else C.GOODREADS_SAFE_URL_VALID_2,
                )
            )
        )
    except ValueError:
        valid = C.FALSE
    if not valid:
        raise _failure(
            S.UNSAFE_LINK, S.GOODREADS_SAFE_URL_A_GOODREADS_LINK_LEFT_THE_PERMITTED_SOURCE
        )
    return (
        S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM
        + parsed.path
        + (S.GOODREADS_SAFE_URL_TEXT + parsed.query if parsed.query else S.EMPTY)
    )


def _query(url: str) -> dict[str, list[str]]:
    try:
        return parse_qs(
            urlsplit(url).query,
            keep_blank_values=C.TRUE,
            max_num_fields=C.GOODREADS_QUERY_MAX_NUM_FIELDS,
        )
    except ValueError as exc:
        raise _failure(
            S.UNSAFE_LINK, S.GOODREADS_QUERY_GOODREADS_SUPPLIED_AN_INVALID_QUERY_STRING
        ) from exc


def _reader(url: str) -> str | None:
    match = C.GOODREADS_READER_PATH.fullmatch(urlsplit(url).path)
    return C.NONE if match is C.NONE else match[C.ONE]


def _shelf_query(url: str, *, required: bool = C.FALSE) -> None:
    shelves = _query(url).get(S.SHELF)
    if (required and shelves is C.NONE) or (shelves is not C.NONE and shelves != [S.TO_READ]):
        raise _failure(
            S.WRONG_COLLECTION, S.GOODREADS_SHELF_QUERY_GOODREADS_DID_NOT_RETURN_THE_REQUESTED_TO
        )


def _collection_url(reader_id: str, page: int, *, rss: bool) -> str:
    route = S.LIST_RSS if rss else S.LIST
    query = urlencode({S.SHELF: S.TO_READ, S.PAGE: page, S.PER_PAGE: C.GOODREADS_PER_PAGE})
    return S.GOODREADS_COLLECTION_URL_TEMPLATE.format(
        v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM, v1=route, v2=reader_id, v3=query
    )


def _check_document_url(url: str, account: Account, *, rss: bool) -> str:
    safe = _safe_url(url)
    path = urlsplit(safe).path
    reader = _reader(safe)
    if reader is not C.NONE and reader != account.account_id:
        raise _failure(
            S.ACCOUNT_MISMATCH,
            S.GOODREADS_CHECK_DOCUMENT_URL_GOODREADS_A_DIFFERENT_READER_S_PAGE,
            state=SyncState.NEEDS_AUTH,
        )
    if path.startswith(C.GOODREADS_LOGIN_PATHS):
        return safe
    route = (
        S.GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST_RSS
        if rss
        else S.GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST
    )
    if reader != account.account_id or not path.startswith(route):
        raise _failure(
            S.UNEXPECTED_PAGE, S.GOODREADS_CHECK_DOCUMENT_URL_GOODREADS_RETURNED_AN_UNEXPECTED_PAGE
        )
    _shelf_query(safe, required=not rss)
    return safe


def _check_access(status: int | None, text: str, url: str, *, rss: bool) -> None:
    is_html = bool(
        re.match(
            S.GOODREADS_CHECK_ACCESS_IS_HTML_S_XML_S_DOCTYPE_S_HTML_HTML,
            text[: C.GOODREADS_CHECK_ACCESS_IS_HTML],
            re.I,
        )
    )
    soup = BeautifulSoup(text, S.HTML_PARSER) if is_html else C.NONE
    visible = soup.get_text(S.SPACE, strip=C.TRUE).casefold() if soup is not C.NONE else S.EMPTY
    challenge = any(
        phrase in visible
        for phrase in (
            S.BROWSER_PAGE_ACCESS_PROBLEM_VERIFY_YOU_ARE_HUMAN,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_VERIFY_THAT_YOU_ARE_HUMAN,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_UNUSUAL_TRAFFIC,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_ACCESS_DENIED,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_CHECKING_YOUR_BROWSER,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_ENABLE_AND_COOKIES_TO_CONTINUE,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_SECURITY_CHALLENGE,
            S.GOODREADS_CHECK_ACCESS_CHALLENGE_REQUEST_BLOCKED,
        )
    )
    if soup is not C.NONE and soup.select_one(
        S.GOODREADS_CHECK_ACCESS_IFRAME_SRC_CAPTCHA_G_RECAPTCHA_H_CAPTCHA
    ):
        challenge = C.TRUE
    if status in {C.GOODREADS_CHECK_ACCESS, C.GOODREADS_CHECK_ACCESS_2} or challenge:
        raise ConnectorError(
            S.GOODREADS_CHECK_ACCESS_GOODREADS_BLOCKED_NO_ALTERNATIVE_ROUTE_WAS,
            state=SyncState.BLOCKED,
            code=S.ACCESS_BLOCKED,
            retryable=status == C.GOODREADS_CHECK_ACCESS_RETRYABLE,
        )
    private = any(
        phrase in visible
        for phrase in (
            S.GOODREADS_CHECK_ACCESS_PRIVATE_THIS_PROFILE_IS_PRIVATE,
            S.GOODREADS_CHECK_ACCESS_PRIVATE_THIS_USER_S_PROFILE_IS_PRIVATE,
            S.GOODREADS_CHECK_ACCESS_PRIVATE_THIS_MEMBER_S_PROFILE_IS_PRIVATE,
            S.GOODREADS_CHECK_ACCESS_PRIVATE_ONLY_VISIBLE_TO_FRIENDS,
            S.GOODREADS_CHECK_ACCESS_PRIVATE_SIGN_IN_TO_VIEW_THIS,
            S.GOODREADS_CHECK_ACCESS_PRIVATE_LOG_IN_TO_VIEW_THIS,
        )
    )
    login_form = (
        soup is not C.NONE
        and soup.select_one(S.GOODREADS_CHECK_ACCESS_LOGIN_FORM_INPUT_TYPE_PASSWORD) is not C.NONE
    )
    login = (
        status == C.GOODREADS_CHECK_ACCESS_LOGIN
        or urlsplit(url).path.startswith(C.GOODREADS_LOGIN_PATHS)
        or private
        or login_form
    )
    if login or (rss and status in {C.GOODREADS_CHECK_ACCESS_3, C.GOODREADS_CHECK_ACCESS_4}):
        error = _FeedUnavailable if rss else ConnectorError
        raise error(
            S.GOODREADS_CHECK_ACCESS_GOODREADS_CONFIGURED_READER_S_ORDINARY
            if login
            else S.GOODREADS_CHECK_ACCESS_GOODREADS_RSS_UNAVAILABLE_AN_ORDINARY_SIGNED,
            state=SyncState.NEEDS_AUTH,
            code=S.NEEDS_AUTH if login else S.RSS_UNAVAILABLE,
        )
    if status is not C.NONE and (
        not C.GOODREADS_CHECK_ACCESS_5 <= status < C.GOODREADS_CHECK_ACCESS_6
    ):
        raise ConnectorError(
            S.GOODREADS_CHECK_ACCESS_GOODREADS_COULD_NOT_SERVE_THE_REQUESTED_PAGE,
            code=S.SOURCE_HTTP_ERROR,
            retryable=status >= C.GOODREADS_CHECK_ACCESS_RETRYABLE_2,
        )


def _rss_identity(channel: Element, account: Account) -> None:
    links = [
        *[node.text or S.EMPTY for node in channel.findall(S.LINK)],
        *[
            node.get(S.HREF, S.EMPTY)
            for node in channel.findall(
                S.GOODREADS_RSS_IDENTITY_LINKS_TEMPLATE.format(
                    v0=S.GOODREADS_ATOM_HTTP_WWW_W3_ORG_ATOM
                )
            )
            if node.get(S.REL) == S.SELF
        ],
    ]
    verified = C.FALSE
    shelf_verified = C.FALSE
    for link in links:
        safe = _safe_url(link, allow_http=C.TRUE)
        reader = _reader(safe)
        if reader is not C.NONE and reader != account.account_id:
            raise _failure(
                S.ACCOUNT_MISMATCH,
                S.GOODREADS_RSS_IDENTITY_THE_RSS_CHANNEL_IDENTIFIES_A_DIFFERENT_READER,
            )
        if reader == account.account_id:
            verified = C.TRUE
            _shelf_query(safe)
            shelf_verified |= _query(safe).get(S.SHELF) == [S.TO_READ]
    title = _xml_text(channel, S.TITLE) or S.EMPTY
    shelf_verified |= bool(re.search(S.GOODREADS_RSS_IDENTITY_BOOKSHELF_S_TO_READ_S, title, re.I))
    if not verified:
        raise _failure(
            S.IDENTITY_UNVERIFIED, S.GOODREADS_RSS_IDENTITY_THE_RSS_CHANNEL_DOES_NOT_IDENTIFY_THE
        )
    if not shelf_verified:
        raise _failure(
            S.WRONG_COLLECTION, S.GOODREADS_RSS_IDENTITY_THE_RSS_CHANNEL_DOES_NOT_IDENTIFY_THE_2
        )


def _rss_count(channel: Element) -> int | None:
    counts: set[int] = set()
    for namespace in (
        S.GOODREADS_RSS_COUNT_HTTP_A9_COM_SPEC_OPENSEARCH,
        S.GOODREADS_RSS_COUNT_HTTP_A9_COM_SPEC_OPENSEARCH_2,
    ):
        for node in channel.findall(S.GOODREADS_RSS_COUNT_TEMPLATE.format(v0=namespace)):
            raw = (node.text or S.EMPTY).strip()
            if not re.fullmatch(S.GOODREADS_RSS_COUNT_TEXT, raw):
                raise _failure(
                    S.INVALID_COUNT, S.GOODREADS_RSS_COUNT_THE_RSS_SHELF_COUNT_IS_INVALID
                )
            counts.add(int(raw))
    if len(counts) > C.ONE:
        raise _failure(
            S.CONFLICTING_COUNT, S.GOODREADS_RSS_COUNT_GOODREADS_REPORTED_CONFLICTING_SHELF_COUNTS
        )
    return next(iter(counts), C.NONE)


@dataclass
class _Fields:
    source_id: str
    url: str
    issues: list[Issue] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)

    def observe(self, name: str, value: JsonValue, state: FieldState, scope: _Scope) -> None:
        self.observations.append(
            Observation(field=name, value=value, state=state, scope=scope, source_url=self.url)
        )

    def bad(self, name: str, code: str, scope: _Scope) -> None:
        self.issues.append(
            Issue(
                code=code,
                message=S.FIELDS_BAD_MESSAGE_TEMPLATE.format(v0=name),
                source_id=self.source_id,
            )
        )
        self.observe(name, C.NONE, FieldState.FAILED, scope)

    def absent(self, name: str, raw: str | None, scope: _Scope) -> bool:
        if raw is not C.NONE and raw.strip():
            return C.FALSE
        self.observe(
            name, C.NONE, FieldState.UNAVAILABLE if raw is C.NONE else FieldState.EMPTY, scope
        )
        return C.TRUE

    def date(self, name: str, raw: str | None, scope: _Scope) -> PartialDate | None:
        if self.absent(name, raw, scope):
            return C.NONE
        try:
            value = parse_date(raw)
        except (ValueError, OverflowError):
            self.bad(name, S.INVALID_DATE, scope)
            return C.NONE
        if value is not C.NONE:
            self.observe(name, value.value, FieldState.PRESENT, scope)
        return value

    def number(
        self,
        name: str,
        raw: str | None,
        scope: _Scope,
        *,
        decimal: bool = C.FALSE,
        maximum: int | None = C.NONE,
        zero_empty: bool = C.FALSE,
    ) -> int | float | None:
        if self.absent(name, raw, scope):
            return C.NONE
        assert raw is not C.NONE
        pattern = S.FIELDS_NUMBER_PATTERN_TEXT if decimal else S.FIELDS_NUMBER_PATTERN_TEXT_2
        if len(raw) > C.GOODREADS_FIELDS_NUMBER or not re.fullmatch(pattern, raw.strip()):
            self.bad(name, S.INVALID_NUMBER, scope)
            return C.NONE
        value = float(raw) if decimal else int(raw.replace(S.COMMA, S.EMPTY))
        if maximum is not C.NONE and value > maximum:
            self.bad(name, S.INVALID_NUMBER, scope)
            return C.NONE
        if value == C.ZERO and zero_empty:
            self.observe(name, C.NONE, FieldState.EMPTY, scope)
            return C.NONE
        self.observe(name, value, FieldState.PRESENT, scope)
        return value

    def isbns(self, *raw_values: str | None) -> tuple[str, ...]:
        values: set[str] = set()
        invalid = C.FALSE
        for raw in raw_values:
            if raw:
                isbn = normalize_isbn(raw)
                if isbn is C.NONE:
                    invalid = C.TRUE
                    self.issues.append(
                        Issue(
                            code=S.INVALID_ISBN,
                            message=S.FIELDS_ISBNS_MESSAGE_GOODREADS_SUPPLIED_AN_INVALID_ISBN,
                            source_id=self.source_id,
                        )
                    )
                else:
                    values.add(isbn)
        if invalid:
            self.observe(S.ISBNS, C.NONE, FieldState.FAILED, S.EDITION)
        elif values:
            identifiers: list[JsonValue] = [isbn for isbn in sorted(values)]
            self.observe(S.ISBNS, identifiers, FieldState.PRESENT, S.EDITION)
        else:
            self.observe(
                S.ISBNS,
                C.NONE,
                FieldState.UNAVAILABLE
                if all(v is C.NONE for v in raw_values)
                else FieldState.EMPTY,
                S.EDITION,
            )
        return tuple(sorted(values))


def _shelves(values: list[str]) -> tuple[str, ...]:
    shelves = tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
    if S.TO_READ not in shelves and {S.READ, S.CURRENTLY_READING}.intersection(shelves):
        raise _failure(
            S.MEMBERSHIP_CONFLICT,
            S.GOODREADS_SHELVES_A_GOODREADS_ROW_CONTRADICTS_TO_READ_MEMBERSHIP,
        )
    return tuple(dict.fromkeys((S.TO_READ, *shelves)))


def _rss_record(item: Element) -> tuple[BookRecord, list[Issue]]:
    source_id = _xml_text(item, S.BOOK_ID) or S.EMPTY
    title = _xml_text(item, S.TITLE) or S.EMPTY
    if not re.fullmatch(S.GOODREADS_RSS_RECORD_TEXT, source_id) or not title:
        raise _failure(S.INVALID_RECORD, S.GOODREADS_RSS_RECORD_A_GOODREADS_RSS_ITEM_HAS_NO_VALID)
    nested = item.find(S.BOOK)
    if nested is not C.NONE and nested.get(S.ID) not in (C.NONE, source_id):
        raise _failure(S.BOOK_ID_MISMATCH, S.GOODREADS_RSS_RECORD_A_GOODREADS_RSS_ITEM_S_BOOK_IDS)
    for node in [*item.findall(S.LINK), *item.findall(S.GUID)]:
        if node.tag == S.GUID and node.get(S.ISPERMALINK) == S.FALSE_2:
            continue
        safe = _safe_url(node.text or S.EMPTY, allow_http=C.TRUE)
        path = urlsplit(safe).path
        book = C.GOODREADS_BOOK_PATH.fullmatch(path)
        if (book is C.NONE and C.GOODREADS_REVIEW_PATH.fullmatch(path) is C.NONE) or (
            book is not C.NONE and book[C.ONE] != source_id
        ):
            raise _failure(
                S.BOOK_ID_MISMATCH, S.GOODREADS_RSS_RECORD_A_GOODREADS_RSS_ITEM_LINKS_TO_A
            )
    url = S.GOODREADS_RSS_RECORD_URL_TEMPLATE.format(
        v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM, v1=source_id
    )
    fields = _Fields(source_id, url)
    isbns = fields.isbns(_xml_text(item, S.ISBN), _xml_text(item, S.ISBN13))
    added = fields.date(S.ADDED_AT, _xml_text(item, S.USER_DATE_ADDED), S.READER)
    fields.date(S.PUBLICATION_DATE, _xml_text(item, S.BOOK_PUBLISHED), S.EDITION)
    fields.number(
        S.PAGE_COUNT,
        _xml_text(item, S.GOODREADS_RSS_RECORD_BOOK_NUM_PAGES),
        S.EDITION,
        zero_empty=C.TRUE,
    )
    fields.number(
        S.COMMUNITY_RATING,
        _xml_text(item, S.AVERAGE_RATING),
        S.WORK,
        decimal=C.TRUE,
        maximum=C.FIVE,
    )
    fields.number(
        S.GOODREADS_PERSONAL_RATING,
        _xml_text(item, S.USER_RATING),
        S.READER,
        maximum=C.FIVE,
        zero_empty=C.TRUE,
    )
    shelves = _shelves((_xml_text(item, S.USER_SHELVES) or S.EMPTY).split(S.COMMA))
    authors = tuple(
        dict.fromkeys(
            author
            for node in item.findall(S.AUTHOR_NAME)
            if (author := _text(S.EMPTY.join(node.itertext())))
        )
    )
    return (
        BookRecord(
            source=Source.GOODREADS,
            source_id=source_id,
            title=title,
            authors=authors,
            url=url,
            status=ReadingStatus.TO_READ,
            raw_status=S.TO_READ,
            isbns=isbns,
            collections=(S.TO_READ,),
            shelves=shelves,
            added_at=added,
            observations=tuple(fields.observations),
        ),
        fields.issues,
    )


def _cell(row: Tag, name: str) -> Tag | None:
    return row.select_one(S.GOODREADS_CELL_TEMPLATE.format(v0=name))


def _cell_text(row: Tag, name: str) -> str | None:
    cell = _cell(row, name)
    return C.NONE if cell is C.NONE else cell.get_text(S.SPACE, strip=C.TRUE)


def _attribute(tag: Tag, name: str) -> str:
    value = tag.get(name)
    return value if isinstance(value, str) else S.EMPTY


def _browser_identity(soup: BeautifulSoup, account: Account) -> None:
    own_ids: set[str] = set()
    has_logout = any(
        _attribute(a, S.HREF).split(S.GOODREADS_SAFE_URL_TEXT, C.ONE)[C.ZERO]
        in {
            S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_USER_SIGN_OUT,
            S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_GOODREADS_COM_USER_SIGN_OUT,
            S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_GOODREADS_COM_USER_SIGN_OUT_2,
        }
        for a in soup.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF)
    )
    for anchor in soup.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF):
        if anchor.find_parent(S.TR, class_=S.BOOKALIKE) is not C.NONE:
            continue
        labels = {
            anchor.get_text(S.SPACE, strip=C.TRUE).casefold(),
            _attribute(anchor, S.TITLE).casefold(),
            _attribute(anchor, S.ARIA_LABEL).casefold(),
        }
        own = bool(
            labels.intersection(
                {
                    S.GOODREADS_BROWSER_IDENTITY_OWN_MY_BOOKS,
                    S.GOODREADS_BROWSER_IDENTITY_OWN_MY_PROFILE,
                }
            )
        ) or (
            has_logout
            and bool(
                labels.intersection({S.PROFILE, S.GOODREADS_BROWSER_IDENTITY_OWN_VIEW_PROFILE})
            )
        )
        if own:
            reader = _reader(_safe_url(_attribute(anchor, S.HREF)))
            if reader is not C.NONE:
                own_ids.add(reader)
    if own_ids and own_ids != {account.account_id}:
        raise _failure(
            S.ACCOUNT_MISMATCH,
            S.GOODREADS_BROWSER_IDENTITY_THE_BROWSER_IS_SIGNED_IN_TO_A,
            state=SyncState.NEEDS_AUTH,
        )
    if not own_ids:
        raise _failure(
            S.AUTH_IDENTITY_UNVERIFIED,
            S.GOODREADS_BROWSER_IDENTITY_THE_BROWSER_PAGE_DOES_NOT_VERIFY_THE,
            state=SyncState.NEEDS_AUTH,
        )
    for heading in soup.select(S.GOODREADS_BROWSER_IDENTITY_H1_H2):
        for anchor in heading.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF):
            safe = _safe_url(_attribute(anchor, S.HREF))
            reader = _reader(safe)
            if reader is not C.NONE and reader != account.account_id:
                raise _failure(
                    S.ACCOUNT_MISMATCH,
                    S.GOODREADS_BROWSER_IDENTITY_THE_HEADING_IDENTIFIES_ANOTHER_READER,
                )


def _browser_count(soup: BeautifulSoup, account: Account) -> int | None:
    counts: set[int] = set()
    for anchor in soup.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF):
        if anchor.find_parent(S.TR, class_=S.BOOKALIKE) is not C.NONE:
            continue
        text = (
            anchor.get_text(S.SPACE, strip=C.TRUE)
            .replace(S.GOODREADS_BROWSER_COUNT_TEXT_TEXT, S.EMPTY)
            .replace(S.GOODREADS_BROWSER_COUNT_TEXT_TEXT_2, S.EMPTY)
        )
        match = re.fullmatch(
            S.GOODREADS_BROWSER_COUNT_MATCH_TO_READ_TO_READ_WANT_TO_READ, text, re.I
        )
        if match is C.NONE:
            continue
        safe = _safe_url(_attribute(anchor, S.HREF))
        if _reader(safe) != account.account_id:
            raise _failure(
                S.ACCOUNT_MISMATCH,
                S.GOODREADS_BROWSER_COUNT_THE_IDENTIFIES_ANOTHER_GOODREADS_READER,
            )
        _shelf_query(safe, required=C.TRUE)
        if len(match[C.ONE]) > C.GOODREADS_BROWSER_COUNT or not re.fullmatch(
            S.FIELDS_NUMBER_PATTERN_TEXT_2, match[C.ONE]
        ):
            raise _failure(
                S.INVALID_COUNT,
                S.GOODREADS_BROWSER_COUNT_GOODREADS_SUPPLIED_INVALID_SHELF_BOOK_COUNT,
            )
        counts.add(int(match[C.ONE].replace(S.COMMA, S.EMPTY)))
    if len(counts) > C.ONE:
        raise _failure(
            S.CONFLICTING_COUNT, S.GOODREADS_RSS_COUNT_GOODREADS_REPORTED_CONFLICTING_SHELF_COUNTS
        )
    return next(iter(counts), C.NONE)


def _next_link(href: str, account: Account, page: int, *, rss: bool, base: str) -> None:
    safe = _safe_url(href, base=base)
    route = (
        S.GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST_RSS
        if rss
        else S.GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST
    )
    if _reader(safe) != account.account_id or not urlsplit(safe).path.startswith(route):
        raise _failure(
            S.UNSAFE_PAGINATION, S.GOODREADS_NEXT_LINK_GOODREADS_PAGINATION_THE_CONFIGURED_READER_S
        )
    _shelf_query(safe, required=C.TRUE)
    query = _query(safe)
    if query.get(S.PAGE) != [str(page + C.ONE)]:
        raise _failure(
            S.PAGINATION_NO_PROGRESS,
            S.GOODREADS_NEXT_LINK_GOODREADS_PAGINATION_DID_NOT_ADVANCE_BY_ONE,
        )
    size = query.get(S.PER_PAGE, [str(C.GOODREADS_PER_PAGE)])
    if (
        len(size) != C.ONE
        or not re.fullmatch(S.GOODREADS_NEXT_LINK_TEXT, size[C.ZERO])
        or (not C.ONE <= int(size[C.ZERO]) <= C.GOODREADS_PER_PAGE)
    ):
        raise _failure(
            S.UNSAFE_PAGINATION,
            S.GOODREADS_NEXT_LINK_GOODREADS_PAGINATION_EXCEEDED_THE_PER_PAGE_LIMIT,
        )


def _browser_next(soup: BeautifulSoup, account: Account, page: int, base: str) -> bool:
    has_next = C.FALSE
    for anchor in soup.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF):
        if anchor.find_parent(S.TR, class_=S.BOOKALIKE) is not C.NONE:
            continue
        label = anchor.get_text(S.SPACE, strip=C.TRUE).casefold()
        rel = anchor.get(S.REL, [])
        explicitly_next = S.NEXT in rel or bool(
            re.fullmatch(S.GOODREADS_BROWSER_NEXT_EXPLICITLY_NEXT_NEXT_S_U203A, label)
        )
        if not explicitly_next and label != str(page + C.ONE):
            continue
        href = _attribute(anchor, S.HREF)
        if not explicitly_next and (
            S.GOODREADS_BROWSER_NEXT_PAGE not in href
            or (
                S.GOODREADS_CHECK_DOCUMENT_URL_ROUTE_REVIEW_LIST not in href
                and (not href.startswith(S.GOODREADS_SAFE_URL_TEXT))
            )
        ):
            continue
        _next_link(href, account, page, rss=C.FALSE, base=base)
        has_next = C.TRUE
    return has_next


def _browser_rating(row: Tag) -> str | None:
    cell = _cell(row, S.RATING)
    if cell is C.NONE:
        return C.NONE
    stars = cell.select(S.GOODREADS_BROWSER_RATING_STARS_STATICSTARS_STATICSTAR)
    if len(stars) == C.FIVE and all(
        S.P10 in star.get(S.CLASS, []) or S.P0 in star.get(S.CLASS, []) for star in stars
    ):
        return str(sum(S.P10 in star.get(S.CLASS, []) for star in stars))
    text = cell.get_text(S.SPACE, strip=C.TRUE)
    return text if not text or re.fullmatch(S.GOODREADS_BROWSER_RATING_TEXT, text) else C.NONE


def _browser_record(row: Tag, account: Account) -> tuple[BookRecord, list[Issue]]:
    title_cell = _cell(row, S.TITLE)
    anchor = (
        C.NONE
        if title_cell is C.NONE
        else title_cell.select_one(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF)
    )
    if anchor is C.NONE:
        raise _failure(
            S.INVALID_RECORD, S.GOODREADS_BROWSER_RECORD_A_GOODREADS_SHELF_ROW_HAS_NO_BOOK
        )
    safe = _safe_url(_attribute(anchor, S.HREF))
    book = C.GOODREADS_BOOK_PATH.fullmatch(urlsplit(safe).path)
    title = _attribute(anchor, S.TITLE).strip() or anchor.get_text(S.SPACE, strip=C.TRUE)
    if book is C.NONE or not title:
        raise _failure(
            S.INVALID_RECORD, S.GOODREADS_BROWSER_RECORD_A_GOODREADS_SHELF_ROW_HAS_NO_VALID
        )
    source_id = book[C.ONE]
    url = S.GOODREADS_RSS_RECORD_URL_TEMPLATE.format(
        v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM, v1=source_id
    )
    authors: list[str] = []
    author_cell = _cell(row, S.AUTHOR)
    if author_cell is not C.NONE:
        for author in author_cell.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF):
            author_url = _safe_url(_attribute(author, S.HREF))
            if C.GOODREADS_AUTHOR_PATH.fullmatch(urlsplit(author_url).path):
                name = author.get_text(S.SPACE, strip=C.TRUE)
                if name:
                    authors.append(name)
        if not authors and (not author_cell.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF)):
            name = author_cell.get_text(S.SPACE, strip=C.TRUE)
            if name:
                authors.append(name)
    fields = _Fields(source_id, url)
    isbns = fields.isbns(_cell_text(row, S.ISBN), _cell_text(row, S.ISBN13))
    added_cell = _cell(row, S.DATE_ADDED)
    added_span = (
        C.NONE
        if added_cell is C.NONE
        else added_cell.select_one(S.GOODREADS_BROWSER_RECORD_ADDED_SPAN_SPAN_TITLE)
    )
    added_raw = (
        _attribute(added_span, S.TITLE)
        if added_span is not C.NONE
        else _cell_text(row, S.DATE_ADDED)
    )
    added = fields.date(S.ADDED_AT, added_raw, S.READER)
    original = _cell_text(row, S.DATE_PUB)
    if not fields.absent(S.FIRST_PUBLICATION_YEAR, original, S.WORK):
        try:
            published = parse_date(original)
        except (ValueError, OverflowError):
            fields.bad(S.FIRST_PUBLICATION_YEAR, S.INVALID_DATE, S.WORK)
        else:
            if published is not C.NONE:
                fields.observe(
                    S.FIRST_PUBLICATION_YEAR,
                    int(published.value[: C.FOUR]),
                    FieldState.PRESENT,
                    S.WORK,
                )
    fields.date(S.PUBLICATION_DATE, _cell_text(row, S.DATE_PUB_EDITION), S.EDITION)
    pages = _cell_text(row, S.NUM_PAGES)
    if pages is not C.NONE:
        pages = re.sub(S.GOODREADS_BROWSER_RECORD_PAGES_S_PP_PAGES_S, S.EMPTY, pages, flags=re.I)
    fields.number(S.PAGE_COUNT, pages, S.EDITION, zero_empty=C.TRUE)
    fields.number(
        S.COMMUNITY_RATING, _cell_text(row, S.AVG_RATING), S.WORK, decimal=C.TRUE, maximum=C.FIVE
    )
    fields.number(S.COMMUNITY_RATINGS_COUNT, _cell_text(row, S.NUM_RATINGS), S.WORK)
    fields.number(
        S.GOODREADS_PERSONAL_RATING,
        _browser_rating(row),
        S.READER,
        maximum=C.FIVE,
        zero_empty=C.TRUE,
    )
    position = fields.number(S.SHELF_POSITION, _cell_text(row, S.POSITION), S.READER)
    shelves: list[str] = []
    shelf_cell = _cell(row, S.SHELVES)
    if shelf_cell is not C.NONE:
        for link in shelf_cell.select(S.GOODREADS_BROWSER_IDENTITY_HAS_LOGOUT_A_HREF):
            href = _attribute(link, S.HREF)
            if S.GOODREADS_BROWSER_RECORD_SHELF not in href:
                continue
            safe = _safe_url(href)
            if _reader(safe) != account.account_id:
                raise _failure(
                    S.ACCOUNT_MISMATCH,
                    S.GOODREADS_BROWSER_RECORD_A_SHELF_ROW_IDENTIFIES_A_DIFFERENT_READER,
                )
            values = _query(safe).get(S.SHELF, [])
            if len(values) != C.ONE or not values[C.ZERO]:
                raise _failure(
                    S.INVALID_RECORD,
                    S.GOODREADS_BROWSER_RECORD_A_GOODREADS_ROW_HAS_AN_INVALID_SHELF,
                )
            shelves.append(values[C.ZERO])
    return (
        BookRecord(
            source=Source.GOODREADS,
            source_id=source_id,
            title=title,
            authors=tuple(dict.fromkeys(authors)),
            url=url,
            status=ReadingStatus.TO_READ,
            raw_status=S.TO_READ,
            collections=(S.TO_READ,),
            shelves=_shelves(shelves),
            isbns=isbns,
            added_at=added,
            shelf_position=int(position) if position is not C.NONE else C.NONE,
            edition_format=_cell_text(row, S.FORMAT) or C.NONE,
            observations=tuple(fields.observations),
        ),
        fields.issues,
    )


class GoodreadsConnector:
    def __init__(
        self,
        http: HttpFetcher,
        browser: BrowserFetcher | None = C.NONE,
        *,
        max_pages: int = C.GOODREADSCONNECTOR_INIT_MAX_PAGES,
    ) -> None:
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < C.ONE:
            raise ValueError(S.GOODREADS_GOODREADSCONNECTOR_INIT_MAX_PAGES_BE_A_POSITIVE_INTEGER)
        self._http = http
        self._browser = browser
        self._max_pages = max_pages

    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        if account.source != Source.GOODREADS:
            raise ValueError(S.GOODREADS_GOODREADSCONNECTOR_COLLECT_GOODREADS_READER_ACCOUNT)
        run = _Run()
        failure: ConnectorError | None = C.NONE
        try:
            try:
                self._walk(account, run, rss=C.TRUE, on_progress=on_progress)
            except _FeedUnavailable as exc:
                if self._browser is C.NONE or run.records or run.identity_verified:
                    raise
                run.issues.append(_issue(exc))
                self._walk(account, run, rss=C.FALSE, on_progress=on_progress)
        except ConnectorError as exc:
            failure = exc
            run.issues.append(_issue(exc))
        if run.expected_count is not C.NONE and len(run.records) != run.expected_count:
            run.incomplete = C.TRUE
            run.issues.append(
                Issue(
                    code=S.COUNT_MISMATCH,
                    message=S.GOODREADSCONNECTOR_COLLECT_MESSAGE_THE_COUNT_DOES_NOT_MATCH,
                    retryable=C.TRUE,
                )
            )
        if failure is not C.NONE:
            state = failure.state
            if state == SyncState.FAILED and (run.records or run.identity_verified):
                state = SyncState.PARTIAL
        else:
            state = (
                SyncState.COMPLETE
                if run.identity_verified and run.termination_verified and (not run.incomplete)
                else SyncState.PARTIAL
            )
        watchlist = FieldState.UNAVAILABLE
        if run.identity_verified and run.records:
            watchlist = FieldState.PRESENT
        elif run.identity_verified and run.termination_verified and (not run.incomplete):
            watchlist = FieldState.EMPTY
        capabilities = {
            S.WATCHLIST: watchlist,
            S.REVIEWS: FieldState.UNSUPPORTED,
            S.ORIGINAL_SHELF_TRANSITION_DATE: FieldState.UNAVAILABLE,
        }
        for record in run.records.values():
            for observation in record.observations:
                previous = capabilities.get(observation.field)
                if previous is C.NONE or observation.state == FieldState.PRESENT:
                    capabilities[observation.field] = observation.state
        return CollectionSnapshot(
            source=Source.GOODREADS,
            account_id=account.account_id,
            collection=S.TO_READ,
            state=state,
            records=tuple(run.records.values()),
            started_at=run.started_at,
            pages_seen=run.pages_seen,
            expected_count=run.expected_count,
            identity_verified=run.identity_verified,
            termination_verified=run.termination_verified,
            capabilities=capabilities,
            issues=tuple(run.issues),
        )

    def _walk(
        self, account: Account, run: _Run, *, rss: bool, on_progress: ProgressCallback | None
    ) -> None:
        for number in range(C.ONE, self._max_pages + C.ONE):
            cursor = _collection_url(account.account_id, number, rss=rss)
            run.pages_seen += C.ONE
            fresh: list[BookRecord] = []
            try:
                try:
                    page = (
                        self._rss_page(account, number)
                        if rss
                        else self._browser_page(account, number)
                    )
                except (OSError, UnicodeError) as exc:
                    raise ConnectorError(
                        S.GOODREADS_GOODREADSCONNECTOR_WALK_GOODREADS_A_TRANSPORT_OR_ENCODING,
                        code=S.TRANSPORT_ERROR,
                        retryable=C.TRUE,
                    ) from exc
                run.identity_verified = C.TRUE
                run.issues.extend(page.issues)
                run.incomplete |= bool(page.issues)
                if page.expected_count is not C.NONE:
                    if run.expected_count is C.NONE:
                        run.expected_count = page.expected_count
                    elif run.expected_count != page.expected_count:
                        run.incomplete = C.TRUE
                        run.issues.append(
                            Issue(
                                code=S.SHELF_CHANGED,
                                message=S.GOODREADSCONNECTOR_WALK_MESSAGE_THE_COUNT_CHANGED_DURING_PAGING,
                                retryable=C.TRUE,
                            )
                        )
                for record in page.records:
                    if record.source_id not in run.records:
                        run.records[record.source_id] = record
                        fresh.append(record)
                    else:
                        run.incomplete = C.TRUE
                        run.issues.append(
                            Issue(
                                code=S.DUPLICATE_RECORD,
                                message=S.GOODREADSCONNECTOR_WALK_MESSAGE_A_GOODREADS_OCCURRED_MORE_THAN_ONCE,
                                source_id=record.source_id,
                                retryable=C.TRUE,
                            )
                        )
                if page.error is not C.NONE:
                    raise page.error
                if page.item_count == C.ZERO:
                    if page.has_next:
                        raise _failure(
                            S.EMPTY_PAGE_GAP,
                            S.GOODREADS_GOODREADSCONNECTOR_WALK_AN_EMPTY_PAGE_STILL_LINKS_ONWARD,
                        )
                    if not rss and number == C.ONE and (page.expected_count != C.ZERO):
                        raise _failure(
                            S.EMPTY_SHELF_UNVERIFIED,
                            S.GOODREADS_GOODREADSCONNECTOR_WALK_AN_INITIAL_BROWSER_TABLE_HAS_NO,
                        )
                    run.termination_verified = C.TRUE
                    return
                if not fresh:
                    run.incomplete = C.TRUE
                    run.issues.append(
                        Issue(
                            code=S.PAGINATION_NO_PROGRESS,
                            message=S.GOODREADSCONNECTOR_WALK_MESSAGE_GOODREADS_PAGE_OR_SUPPLIED_NO,
                            retryable=C.TRUE,
                        )
                    )
                    return
                if (
                    not rss
                    and run.expected_count is not C.NONE
                    and (len(run.records) == run.expected_count)
                    and (not page.has_next)
                ):
                    run.termination_verified = C.TRUE
                    return
            finally:
                if on_progress is not C.NONE:
                    on_progress(
                        CollectionProgress(
                            source=Source.GOODREADS,
                            collection=S.TO_READ,
                            pages_seen=run.pages_seen,
                            records=tuple(fresh),
                            cursor=cursor,
                            message=S.GOODREADSCONNECTOR_WALK_MESSAGE_TEMPLATE.format(
                                v0=S.RSS if rss else S.BROWSER, v1=number
                            ),
                        )
                    )
        run.incomplete = C.TRUE
        run.issues.append(
            Issue(
                code=S.PAGE_LIMIT,
                message=S.GOODREADSCONNECTOR_WALK_MESSAGE_GOODREADS_THE_CONFIGURED_PAGE_LIMIT,
                retryable=C.TRUE,
            )
        )

    def _rss_page(self, account: Account, page: int) -> _Page:
        url = S.GOODREADSCONNECTOR_RSS_PAGE_URL_TEMPLATE.format(
            v0=S.GOODREADS_BASE_HTTPS_WWW_GOODREADS_COM, v1=account.account_id
        )
        response = self._http.fetch(
            url,
            params={S.SHELF: S.TO_READ, S.PAGE: str(page), S.PER_PAGE: str(C.GOODREADS_PER_PAGE)},
            headers={S.ACCEPT: S.RSS_PAGE_RESPONSE_HEADERS_APPLICATION_RSS_XML_APPLICATION_XML_Q},
        )
        safe = _safe_url(response.url)
        if len(response.body) > C.GOODREADS_MAX_BODY_BYTES:
            raise _failure(
                S.PAGE_TOO_LARGE, S.GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_THE_RESPONSE_SIZE_LIMIT
            )
        _check_access(
            response.status_code,
            response.body.decode(S.UTF_8_SIG, errors=S.REPLACE),
            safe,
            rss=C.TRUE,
        )
        _check_document_url(safe, account, rss=C.TRUE)
        try:
            root = ElementTree.fromstring(
                response.body, forbid_dtd=C.TRUE, forbid_entities=C.TRUE, forbid_external=C.TRUE
            )
        except DefusedXmlException as exc:
            raise _failure(
                S.UNSAFE_XML,
                S.GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_A_FORBIDDEN_XML_DECLARATION,
                state=SyncState.BLOCKED,
            ) from exc
        except (ParseError, ValueError) as exc:
            raise _failure(
                S.MALFORMED_XML,
                S.GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_GOODREADS_NOT_WELL_FORMED_XML,
            ) from exc
        channel = root.find(S.CHANNEL) if root.tag == S.RSS_2 else C.NONE
        if channel is C.NONE or len(root.findall(S.CHANNEL)) != C.ONE:
            raise _failure(
                S.UNSUPPORTED_FEED, S.GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_RETURN_A_RECOGNIZED_RSS
            )
        _rss_identity(channel, account)
        items = channel.findall(S.ITEM)
        if len(items) > C.GOODREADS_PER_PAGE:
            raise _failure(
                S.PAGE_TOO_LARGE,
                S.GOODREADS_GOODREADSCONNECTOR_RSS_PAGE_GOODREADS_THE_BOOK_PAGE_LIMIT,
            )
        records: list[BookRecord] = []
        issues: list[Issue] = []
        for item in items:
            try:
                record, item_issues = _rss_record(item)
                records.append(record)
                issues.extend(item_issues)
            except ConnectorError as exc:
                source_id = _xml_text(item, S.BOOK_ID)
                issues.append(
                    _issue(
                        exc,
                        source_id
                        if source_id and re.fullmatch(S.GOODREADS_RSS_RECORD_TEXT, source_id)
                        else C.NONE,
                    )
                )
        parsed = _Page(tuple(records), len(items), issues)
        try:
            parsed.expected_count = _rss_count(channel)
            for link in channel.findall(
                S.GOODREADS_RSS_IDENTITY_LINKS_TEMPLATE.format(
                    v0=S.GOODREADS_ATOM_HTTP_WWW_W3_ORG_ATOM
                )
            ):
                if link.get(S.REL) == S.NEXT:
                    _next_link(
                        link.get(S.HREF, S.EMPTY),
                        account,
                        page,
                        rss=C.TRUE,
                        base=_collection_url(account.account_id, page, rss=C.TRUE),
                    )
                    parsed.has_next = C.TRUE
        except ConnectorError as exc:
            parsed.error = exc
        return parsed

    def _browser_page(self, account: Account, page: int) -> _Page:
        assert self._browser is not C.NONE
        url = _collection_url(account.account_id, page, rss=C.FALSE)
        document = self._browser.fetch(url)
        safe = _safe_url(document.url)
        if len(document.html.encode(S.UTF_8)) > C.GOODREADS_MAX_BODY_BYTES:
            raise _failure(
                S.PAGE_TOO_LARGE,
                S.GOODREADS_GOODREADSCONNECTOR_BROWSER_PAGE_THE_RESPONSE_SIZE_LIMIT,
            )
        _check_access(document.status_code, document.html, safe, rss=C.FALSE)
        _check_document_url(safe, account, rss=C.FALSE)
        soup = BeautifulSoup(document.html, S.HTML_PARSER)
        _browser_identity(soup, account)
        table = soup.select_one(S.GOODREADSCONNECTOR_BROWSER_PAGE_TABLE_TABLE_BOOKS)
        rows = (table if table is not C.NONE else soup).select(S.TR_BOOKALIKE)
        body = soup.select_one(S.GOODREADSCONNECTOR_BROWSER_PAGE_BODY_TABLE_BOOKS_TBODY_BOOKSBODY)
        if not rows and (body is C.NONE or body.select_one(S.TR) is not C.NONE):
            raise _failure(
                S.UNKNOWN_MARKUP,
                S.GOODREADS_GOODREADSCONNECTOR_BROWSER_PAGE_TABLE_WAS_NOT_RECOGNIZED,
            )
        if len(rows) > C.GOODREADS_PER_PAGE:
            raise _failure(
                S.PAGE_TOO_LARGE, S.GOODREADS_GOODREADSCONNECTOR_BROWSER_PAGE_THE_BOOK_PAGE_LIMIT
            )
        records: list[BookRecord] = []
        issues: list[Issue] = []
        for row in rows:
            try:
                record, row_issues = _browser_record(row, account)
                records.append(record)
                issues.extend(row_issues)
            except ConnectorError as exc:
                issues.append(_issue(exc))
        parsed = _Page(tuple(records), len(rows), issues)
        try:
            parsed.expected_count = _browser_count(soup, account)
            parsed.has_next = _browser_next(soup, account, page, safe)
        except ConnectorError as exc:
            parsed.error = exc
        return parsed
