from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.browser import page_access_problem
from bookystats.dates import parse_date
from bookystats.errors import ConnectorError
from bookystats.identifiers import normalize_isbn
from bookystats.interfaces import BrowserFetcher, PageDocument, ProgressCallback
from bookystats.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    FieldState,
    Issue,
    Observation,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
    utc_now,
)


@C.frozen_dataclass
class _Surface:
    status: ReadingStatus
    url: str


def _attr(tag: Tag, name: str) -> str:
    value = tag.get(name)
    if isinstance(value, list):
        return S.SPACE.join(str(item) for item in value)
    return str(value) if value is not C.NONE else S.EMPTY


def _visible(tag: Tag) -> bool:
    current: Tag | None = tag
    while current is not C.NONE:
        if (
            current.has_attr(S.HIDDEN)
            or _attr(current, S.ARIA_HIDDEN).casefold() == S.TRUE_2
            or S.HIDDEN in _attr(current, S.CLASS).split()
            or re.search(
                S.STORYGRAPH_VISIBLE_DISPLAY_S_S_NONE_VISIBILITY_S_S, _attr(current, S.STYLE)
            )
        ):
            return C.FALSE
        current = current.parent if isinstance(current.parent, Tag) else C.NONE
    return C.TRUE


def _text(tag: Tag, *, separator: str = S.SPACE) -> str:
    return separator.join(
        str(node).strip()
        for node in tag.find_all(string=C.TRUE)
        if isinstance(node.parent, Tag)
        and node.parent.name not in {S.SCRIPT, S.STYLE, S.TEMPLATE}
        and _visible(node.parent)
        and str(node).strip()
    )


def _label(text: str) -> str:
    return re.sub(S.STORYGRAPH_LABEL_S, S.SPACE, text.casefold().replace(S.HYPHEN, S.SPACE)).strip(
        S.STORYGRAPH_LABEL_TEXT
    )


def _field_label(text: str, *, personal_only: bool = C.FALSE) -> str | None:
    label = _label(text)
    personal = label.startswith(
        (S.STORYGRAPH_FIELD_LABEL_PERSONAL_YOUR, S.STORYGRAPH_FIELD_LABEL_PERSONAL_MY)
    )
    if personal_only and (not personal):
        return C.NONE
    if personal:
        label = label.split(S.SPACE, C.ONE)[C.ONE]
    return C.STORYGRAPH_LABELS.get(label)


def _safe_url(url: str, base: str = S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM) -> str:
    try:
        absolute = urljoin(base, url)
        parsed = urlsplit(absolute)
        valid = (
            parsed.scheme == S.HTTPS
            and parsed.hostname == S.APP_THESTORYGRAPH_COM
            and (parsed.port in (C.NONE, C.STORYGRAPH_SAFE_URL_VALID))
            and (parsed.username is C.NONE)
            and (parsed.password is C.NONE)
            and (not re.search(S.BROWSERCLIENT_CHECKED_URL_VALID_X00_X20, absolute))
        )
    except ValueError:
        valid = C.FALSE
    if not valid:
        raise ConnectorError(
            S.STORYGRAPH_SAFE_URL_A_STORYGRAPH_LINK_LEFT_THE_APPROVED_HTTPS,
            state=SyncState.BLOCKED,
            code=S.UNSAFE_SOURCE_LINK,
        )
    if re.search(
        S.STORYGRAPH_SAFE_URL_EXPORTS_DOWNLOADS, unquote(unquote(parsed.path)), re.I
    ) or any((key.casefold() in {S.EXPORT, S.DOWNLOAD} for key, _ in parse_qsl(parsed.query))):
        raise ConnectorError(
            S.STORYGRAPH_SAFE_URL_STORYGRAPH_EXPORT_DOWNLOAD_LINKS_ARE_DISABLED,
            state=SyncState.BLOCKED,
            code=S.EXPORT_DISABLED,
        )
    return urlunsplit((S.HTTPS, S.APP_THESTORYGRAPH_COM, parsed.path, parsed.query, S.EMPTY))


def _receipt_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, S.EMPTY, S.EMPTY))


def _url_key(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip(S.SLASH),
            urlencode(sorted(parse_qsl(parsed.query))),
            S.EMPTY,
        )
    )


def _profile_owner(href: str) -> str | None:
    try:
        parsed = urlsplit(urljoin(S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM, href))
    except ValueError:
        return C.NONE
    if parsed.scheme != S.HTTPS or parsed.hostname != S.APP_THESTORYGRAPH_COM:
        return C.NONE
    match = C.STORYGRAPH_PROFILE_PATH.fullmatch(unquote(parsed.path))
    return match[C.ONE] if match else C.NONE


def _identity(soup: BeautifulSoup, account_id: str, *, required: bool) -> bool:
    owners: set[str] = set()
    has_logout = any(
        _visible(tag)
        and (
            _label(_text(tag))
            in {
                S.STORYGRAPH_IDENTITY_HAS_LOGOUT_LOG_OUT,
                S.LOGOUT,
                S.STORYGRAPH_IDENTITY_HAS_LOGOUT_SIGN_OUT,
            }
            or urlsplit(
                urljoin(S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM, _attr(tag, S.ACTION))
            ).path
            == S.STORYGRAPH_IDENTITY_HAS_LOGOUT_USERS_SIGN_OUT
        )
        for tag in soup.find_all([S.A, S.FORM])
        if isinstance(tag, Tag)
    )
    for link in soup.find_all(S.A, href=C.TRUE):
        if not isinstance(link, Tag) or not _visible(link):
            continue
        owner = _profile_owner(_attr(link, S.HREF))
        if owner is C.NONE:
            continue
        label = _label(_attr(link, S.ARIA_LABEL) or _text(link))
        navigation = link.find_parent([S.NAV, S.HEADER]) is not C.NONE or any(
            isinstance(parent, Tag) and _attr(parent, S.ROLE) == S.NAVIGATION
            for parent in link.parents
        )
        if navigation and (
            label
            in {S.STORYGRAPH_IDENTITY_YOUR_PROFILE, S.GOODREADS_BROWSER_IDENTITY_OWN_MY_PROFILE}
            or (has_logout and label in {S.PROFILE, owner.casefold()})
        ):
            owners.add(owner)
    if owners and owners != {account_id}:
        raise ConnectorError(
            S.STORYGRAPH_IDENTITY_THE_AUTHENTICATED_OWNER_DOES_NOT_MATCH, code=S.WRONG_ACCOUNT
        )
    if owners == {account_id}:
        return C.TRUE
    if required:
        raise ConnectorError(
            S.STORYGRAPH_IDENTITY_THE_AUTHENTICATED_STORYGRAPH_OWNER_COULD_NOT_BE,
            state=SyncState.NEEDS_AUTH,
            code=S.OWNER_IDENTITY_UNAVAILABLE,
        )
    return C.FALSE


def _owned_list_url(url: str, account_id: str) -> bool:
    parsed = urlsplit(_safe_url(url))
    parts = unquote(parsed.path).strip(S.SLASH).split(S.SLASH)
    if len(parts) != C.TWO or parts[C.ONE] != account_id:
        return C.FALSE
    for key, value in parse_qsl(parsed.query):
        if (
            key.casefold() in {S.USER, S.USERNAME, S.USER_ID, S.ACCOUNT, S.OWNER}
            and value != account_id
        ):
            return C.FALSE
    return parts[C.ZERO] not in {S.PROFILE, S.BOOKS, S.REVIEWS, S.AUTHORS, S.USERS}


def _discover_surfaces(
    soup: BeautifulSoup, account: Account, base: str
) -> tuple[list[_Surface], set[ReadingStatus]]:
    surfaces: list[_Surface] = []
    empty: set[ReadingStatus] = set()
    for link in soup.find_all(S.A, href=C.TRUE):
        if not isinstance(link, Tag) or not _visible(link):
            continue
        if _attr(link, S.ID) == S.NEXT_LINK or S.NEXT in _attr(link, S.REL).split():
            continue
        if any(
            _attr(link, key).casefold() not in {S.EMPTY, S.GET_2}
            for key in (S.DATA_METHOD, S.DATA_TURBO_METHOD)
        ):
            continue
        href = _attr(link, S.HREF)
        parsed = urlsplit(urljoin(base, href))
        parts = unquote(parsed.path).strip(S.SLASH).split(S.SLASH)
        label = re.sub(
            S.STORYGRAPH_DISCOVER_SURFACES_LABEL_S_D_S, S.EMPTY, _label(_text(link))
        ).strip()
        status = C.STORYGRAPH_KNOWN_SURFACES.get(parts[C.ZERO]) if len(parts) == C.TWO else C.NONE
        if status is C.NONE:
            status = C.STORYGRAPH_STATUS_NAMES.get(label)
        if status is C.NONE:
            continue
        url = _safe_url(href, base)
        if not _owned_list_url(url, account.account_id):
            continue
        surfaces.append(_Surface(status, url))
    for status, pattern in (
        (
            ReadingStatus.PAUSED,
            S.STORYGRAPH_DISCOVER_SURFACES_NO_PAUSED_BOOKS_PAUSED_BOOKS_YOU_HAVE,
        ),
        (ReadingStatus.DNF, S.STORYGRAPH_DISCOVER_SURFACES_NO_DID_NOT_FINISH_BOOKS_DID_NOT),
    ):
        if any(
            isinstance(tag, Tag)
            and _visible(tag)
            and _is_reader_field(tag, account.account_id)
            and re.fullmatch(pattern, _label(_text(tag)))
            for tag in soup.find_all([S.P, S.H1, S.H2, S.H3])
        ):
            empty.add(status)
    return (surfaces, empty)


def _is_reader_field(tag: Tag, account_id: str) -> bool:
    for parent in (tag, *tag.parents):
        if not isinstance(parent, Tag):
            continue
        if {S.TRIX_CONTENT, S.AVERAGE_STAR_RATING}.intersection(
            _attr(parent, S.CLASS).split()
        ) or _attr(parent, S.ITEMPROP) in {S.REVIEWBODY, S.COMMENTTEXT}:
            return C.FALSE
        if parent.name in {S.ARTICLE, S.SECTION}:
            heading = parent.find([S.H1, S.H2, S.H3, S.H4], recursive=C.FALSE)
            if isinstance(heading, Tag) and S.COMMUNITY in _label(_text(heading)):
                return C.FALSE
            owners = {
                owner
                for link in parent.find_all(S.A, href=C.TRUE)
                if isinstance(link, Tag)
                and (owner := _profile_owner(_attr(link, S.HREF))) is not C.NONE
            }
            if owners and owners != {account_id}:
                return C.FALSE
    return C.TRUE


def _pairs(
    root: Tag, *, personal_only: bool = C.FALSE, account_id: str | None = C.NONE
) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for term in root.find_all(S.DT):
        if not isinstance(term, Tag) or not _visible(term):
            continue
        if account_id is not C.NONE and (not _is_reader_field(term, account_id)):
            continue
        field = _field_label(_text(term), personal_only=personal_only)
        value = term.find_next_sibling(S.DD)
        if field and isinstance(value, Tag) and _visible(value):
            time = value.find(S.TIME, datetime=C.TRUE)
            pairs[field] = (
                _attr(time, S.DATETIME)
                if isinstance(time, Tag) and field in {S.STARTED, S.FINISHED}
                else _text(value)
            )
    for tag in root.find_all([S.P, S.LI, S.SPAN, S.OUTPUT]):
        if not isinstance(tag, Tag) or not _visible(tag):
            continue
        if account_id is not C.NONE and (not _is_reader_field(tag, account_id)):
            continue
        text = _text(tag)
        match = re.fullmatch(S.STORYGRAPH_PAIRS_MATCH_N_S, text)
        if match:
            field = _field_label(match[C.ONE], personal_only=personal_only)
            if field and field not in pairs:
                pairs[field] = match[C.TWO].strip()
    return pairs


def _observation(
    field: str, value: JsonValue, state: FieldState, url: str, *, reader: bool = C.TRUE
) -> Observation:
    return Observation(
        field=field,
        value=value,
        state=state,
        scope=S.READER if reader else S.WORK,
        source_url=_receipt_url(url),
    )


def _rating(value: str, *, quarter_stars: bool = C.TRUE) -> tuple[FieldState, float | None]:
    normalized = _label(value)
    if normalized in {
        S.EMPTY,
        S.UNRATED,
        S.STORYGRAPH_RATING_NOT_RATED,
        S.STORYGRAPH_RATING_NO_RATING,
        S.NONE_2,
    }:
        return (FieldState.EMPTY, C.NONE)
    match = re.fullmatch(S.STORYGRAPH_RATING_MATCH_YOUR_MY_STAR_RATING_S_D_D, normalized)
    if not match:
        return (FieldState.FAILED, C.NONE)
    try:
        number = Decimal(match[C.ONE])
    except InvalidOperation:
        return (FieldState.FAILED, C.NONE)
    if not C.ZERO <= number <= C.FIVE or (
        quarter_stars and number * C.FOUR != (number * C.FOUR).to_integral_value()
    ):
        return (FieldState.FAILED, C.NONE)
    return (FieldState.PRESENT, float(number))


def _owner_regions(root: Tag, account_id: str) -> list[Tag]:
    result: list[Tag] = []
    candidates = root.find_all([S.SECTION, S.ARTICLE, S.DIV])
    if root.name in {S.SECTION, S.ARTICLE, S.DIV}:
        candidates.insert(C.ZERO, root)
    for region in candidates:
        if not isinstance(region, Tag) or not _visible(region):
            continue
        if not _is_reader_field(region, account_id):
            continue
        heading = region.find([S.H1, S.H2, S.H3, S.H4, S.H5, S.H6], recursive=C.FALSE)
        label = _label(_attr(region, S.ARIA_LABEL))
        if isinstance(heading, Tag):
            label = _label(_text(heading))
        explicit = bool(
            re.fullmatch(S.STORYGRAPH_OWNER_REGIONS_EXPLICIT_RATING_READING_HISTORY_READING, label)
        )
        owners = {
            owner
            for link in region.find_all(S.A, href=C.TRUE)
            if isinstance(link, Tag)
            and (owner := _profile_owner(_attr(link, S.HREF))) is not C.NONE
            and _visible(link)
        }
        authored = (
            owners == {account_id}
            and region.name in {S.ARTICLE, S.SECTION}
            and (
                S.REVIEW in _attr(region, S.ITEMPROP).split()
                or region.select_one(S.STORYGRAPH_OWNER_REGIONS_AUTHORED_ITEMPROP_REVIEWBODY)
                is not C.NONE
                or S.REVIEW in label
                or (S.STORYGRAPH_OWNER_REGIONS_AUTHORED_READING_HISTORY in label)
            )
        )
        if explicit and owners and (owners != {account_id}):
            raise ConnectorError(
                S.STORYGRAPH_OWNER_REGIONS_A_PERSONAL_SECTION_BELONGS_TO_ANOTHER,
                code=S.REVIEW_OWNER_MISMATCH,
            )
        if (explicit or authored) and (not any(parent in result for parent in region.parents)):
            result.append(region)
    return result


def _history_rows(region: Tag) -> list[tuple[str | None, dict[str, str]]]:
    rows: list[tuple[str | None, dict[str, str]]] = []
    for table in region.find_all(S.TABLE):
        if not isinstance(table, Tag) or not _visible(table):
            continue
        headers = [
            _field_label(_text(header))
            for header in table.find_all(S.TH)
            if isinstance(header, Tag)
        ]
        if not {S.STARTED, S.FINISHED}.intersection(headers):
            continue
        for row in table.find_all(S.TR):
            if not isinstance(row, Tag) or not _visible(row):
                continue
            cells = [
                cell for cell in row.find_all(S.TD, recursive=C.FALSE) if isinstance(cell, Tag)
            ]
            if not cells:
                continue
            values: dict[str, str] = {}
            for field, cell in zip(headers, cells, strict=C.FALSE):
                if field:
                    time = cell.find(S.TIME, datetime=C.TRUE)
                    values[field] = (
                        _attr(time, S.DATETIME)
                        if isinstance(time, Tag) and field in {S.STARTED, S.FINISHED}
                        else _text(cell)
                    )
            rows.append((_attr(row, S.ID) or C.NONE, values))
    for definition in region.find_all(S.DL):
        if not isinstance(definition, Tag) or not _visible(definition):
            continue
        values = _pairs(definition)
        if {S.STARTED, S.FINISHED}.intersection(values):
            rows.append((_attr(definition, S.ID) or C.NONE, values))
    return rows


def _events(
    regions: list[Tag], status: ReadingStatus, source_id: str, url: str
) -> tuple[list[ReadingEvent], Observation, list[Issue]]:
    events: list[ReadingEvent] = []
    issues: list[Issue] = []
    state = FieldState.UNAVAILABLE
    for region in regions:
        text = _label(_text(region))
        rows = _history_rows(region)
        if not rows:
            if re.search(S.STORYGRAPH_EVENTS_B_NO_READING_HISTORY_NO_READS_YET, text):
                state = FieldState.EMPTY
            continue
        state = FieldState.PRESENT
        for event_id, values in rows:
            try:
                started = parse_date(values.get(S.STARTED))
                finished = parse_date(values.get(S.FINISHED))
                event_status = C.STORYGRAPH_STATUS_NAMES.get(
                    _label(values.get(S.STATUS, S.EMPTY)),
                    ReadingStatus.READ if finished else status,
                )
                if (
                    values.get(S.STATUS)
                    and _label(values[S.STATUS]) not in C.STORYGRAPH_STATUS_NAMES
                ):
                    issues.append(
                        Issue(
                            code=S.UNKNOWN_READING_STATUS,
                            message=S.STORYGRAPH_EVENTS_MESSAGE_A_READING_STATUS_WAS_NOT_RECOGNIZED,
                            source_id=source_id,
                        )
                    )
                    event_status = ReadingStatus.UNKNOWN
                events.append(
                    ReadingEvent(
                        source_event_id=event_id,
                        started=started,
                        finished=finished,
                        status=event_status,
                    )
                )
            except ValueError:
                issues.append(
                    Issue(
                        code=S.INVALID_READING_DATE,
                        message=S.STORYGRAPH_EVENTS_MESSAGE_A_READING_EVENT_HAS_AN_INVALID_AMBIGUOUS,
                        source_id=source_id,
                    )
                )
    if issues:
        state = FieldState.FAILED
    value: JsonValue = (
        [event.model_dump(mode=S.JSON) for event in events]
        if state == FieldState.PRESENT
        else C.NONE
    )
    return (events, _observation(S.READING_EVENTS, value, state, url), issues)


def _personal(
    root: Tag, account_id: str, source_id: str, status: ReadingStatus, url: str
) -> tuple[list[Observation], list[ReadingEvent], list[Issue]]:
    regions = _owner_regions(root, account_id)
    values = _pairs(root, personal_only=C.TRUE, account_id=account_id)
    for region in regions:
        values.update(_pairs(region, account_id=account_id))
        if S.RATING not in values:
            for rating in region.select(S.STORYGRAPH_PERSONAL_ITEMPROP_RATINGVALUE_ARIA_LABEL):
                if not isinstance(rating, Tag) or not _visible(rating):
                    continue
                if not _is_reader_field(rating, account_id):
                    continue
                accessible = _attr(rating, S.ARIA_LABEL) or _text(rating)
                if _attr(rating, S.ITEMPROP) == S.RATINGVALUE or re.fullmatch(
                    S.STORYGRAPH_PERSONAL_D_D_OUT_OF_STARS, accessible, re.I
                ):
                    values[S.RATING] = accessible
                    break
        if S.REVIEW not in values:
            heading = region.find([S.H1, S.H2, S.H3, S.H4, S.H5, S.H6], recursive=C.FALSE)
            is_review = (
                isinstance(heading, Tag) and S.REVIEW in _label(_text(heading))
            ) or S.REVIEW in _attr(region, S.ITEMPROP).split()
            body = region.select_one(S.STORYGRAPH_OWNER_REGIONS_AUTHORED_ITEMPROP_REVIEWBODY)
            if body is C.NONE and is_review:
                body = region.select_one(S.STORYGRAPH_PERSONAL_BODY_TRIX_CONTENT)
            if isinstance(body, Tag) and _visible(body):
                values[S.REVIEW] = _text(body, separator=S.NEWLINE)
            elif re.search(
                S.STORYGRAPH_PERSONAL_B_NO_WRITTEN_REVIEW_YOU_HAVEN_T, _text(region), re.I
            ):
                values[S.REVIEW] = S.EMPTY
        if S.READ_COUNT not in values:
            count = re.search(S.STORYGRAPH_PERSONAL_COUNT_BREAD_D_TIMES_B, _text(region), re.I)
            if count:
                values[S.READ_COUNT] = count[C.ONE]
    observations: list[Observation] = []
    issues: list[Issue] = []
    for field in C.STORYGRAPH_PERSONAL_FIELDS:
        if field == S.READING_EVENTS:
            continue
        if field not in values:
            observations.append(_observation(field, C.NONE, FieldState.UNAVAILABLE, url))
            continue
        raw = values[field]
        if field == S.RATING:
            state, number = _rating(raw)
            observations.append(_observation(field, number, state, url))
            if state == FieldState.FAILED:
                issues.append(
                    Issue(
                        code=S.INVALID_PERSONAL_RATING,
                        message=S.STORYGRAPH_PERSONAL_MESSAGE_THE_VISIBLE_PERSONAL_RATING_COULD_NOT_BE,
                        source_id=source_id,
                    )
                )
        elif field == S.READ_COUNT:
            if re.fullmatch(S.STORYGRAPH_PERSONAL_D, raw):
                observations.append(_observation(field, int(raw), FieldState.PRESENT, url))
            else:
                observations.append(_observation(field, C.NONE, FieldState.FAILED, url))
                issues.append(
                    Issue(
                        code=S.INVALID_READ_COUNT,
                        message=S.STORYGRAPH_PERSONAL_MESSAGE_THE_VISIBLE_READ_COUNT_COULD_NOT,
                        source_id=source_id,
                    )
                )
        elif field in {S.MOODS, S.TAGS, S.CONTENT_WARNINGS}:
            empty = _label(raw) in {
                S.EMPTY,
                S.NONE_2,
                S.STORYGRAPH_PERSONAL_EMPTY_NO_TAGS,
                S.STORYGRAPH_PERSONAL_EMPTY_NO_CONTENT_WARNINGS,
                S.STORYGRAPH_PERSONAL_EMPTY_NO_MOODS,
            }
            entries = [
                part.strip()
                for part in re.split(S.STORYGRAPH_PERSONAL_ENTRIES_N, raw)
                if part.strip()
            ]
            observations.append(
                _observation(
                    field,
                    C.NONE if empty else entries,
                    FieldState.EMPTY if empty else FieldState.PRESENT,
                    url,
                )
            )
        else:
            observations.append(
                _observation(
                    field,
                    raw if raw else C.NONE,
                    FieldState.PRESENT if raw else FieldState.EMPTY,
                    url,
                )
            )
    events, event_observation, event_issues = _events(regions, status, source_id, url)
    observations.append(event_observation)
    issues.extend(event_issues)
    return (observations, events, issues)


def _merge_events(
    old: tuple[ReadingEvent, ...], new: tuple[ReadingEvent, ...]
) -> tuple[ReadingEvent, ...]:
    result = list(old)
    used: set[int] = set()
    event_ids = {
        event.source_event_id: index for index, event in enumerate(result) if event.source_event_id
    }

    def semantic_key(event: ReadingEvent) -> tuple[str | None, str | None, ReadingStatus]:
        return (
            event.started.value if event.started is not C.NONE else C.NONE,
            event.finished.value if event.finished is not C.NONE else C.NONE,
            event.status,
        )

    for event in new:
        if event.source_event_id and event.source_event_id in event_ids:
            index = event_ids[event.source_event_id]
            result[index] = event
            used.add(index)
            continue
        match = next(
            (
                index
                for index, prior in enumerate(old)
                if index not in used
                and semantic_key(prior) == semantic_key(event)
                and (event.source_event_id is C.NONE or prior.source_event_id is C.NONE)
            ),
            C.NONE,
        )
        if match is not C.NONE:
            used.add(match)
            if event.source_event_id:
                result[match] = event
                event_ids[event.source_event_id] = match
            continue
        result.append(event)
        if event.source_event_id:
            event_ids[event.source_event_id] = len(result) - C.ONE
    return tuple(result)


def _merge(old: BookRecord, new: BookRecord) -> BookRecord:
    observations = {(item.field, item.scope): item for item in old.observations}
    for item in new.observations:
        key = (item.field, item.scope)
        prior = observations.get(key)
        if prior is C.NONE or item.state in {
            FieldState.PRESENT,
            FieldState.EMPTY,
            FieldState.FAILED,
        }:
            observations[key] = item
    collections = tuple(dict.fromkeys((*old.collections, *new.collections)))
    statuses = {ReadingStatus(value) for value in collections}
    active = statuses.intersection({ReadingStatus.CURRENTLY_READING, ReadingStatus.PAUSED})
    if len(active) == C.ONE:
        status = next(iter(active))
    elif len(statuses) == C.ONE:
        status = next(iter(statuses))
    else:
        status = ReadingStatus.UNKNOWN
    events = _merge_events(old.reading_events, new.reading_events)
    observations[S.STATUSES, S.READER] = _observation(
        S.STATUSES, list(collections), FieldState.PRESENT, new.url
    )
    observations[S.STATUS, S.READER] = _observation(
        S.STATUS,
        status.value if status != ReadingStatus.UNKNOWN else C.NONE,
        FieldState.PRESENT if status != ReadingStatus.UNKNOWN else FieldState.UNAVAILABLE,
        new.url,
    )
    prior_events = observations.get((S.READING_EVENTS, S.READER))
    if events and prior_events is not C.NONE and (prior_events.state != FieldState.FAILED):
        observations[S.READING_EVENTS, S.READER] = _observation(
            S.READING_EVENTS,
            [event.model_dump(mode=S.JSON) for event in events],
            FieldState.PRESENT,
            prior_events.source_url,
        )
    return old.model_copy(
        update={
            S.AUTHORS: new.authors or old.authors,
            S.ISBNS: tuple(dict.fromkeys((*old.isbns, *new.isbns))),
            S.EDITION_FORMAT: new.edition_format or old.edition_format,
            S.LANGUAGE: new.language or old.language,
            S.COLLECTIONS: collections,
            S.STATUS: status,
            S.RAW_STATUS: S.STORYGRAPH_MERGE_UPDATE_TEXT.join(collections),
            S.OBSERVATIONS: tuple(observations.values()),
            S.READING_EVENTS: events,
            S.DETAIL_CHECKED_AT: new.detail_checked_at or old.detail_checked_at,
        }
    )


def _book_card(title: Tag, container: Tag) -> Tag:
    parent = title.parent
    if not isinstance(parent, Tag) or parent is container:
        return title
    for ancestor in title.parents:
        if not isinstance(ancestor, Tag) or ancestor is container:
            break
        if len(ancestor.select(S.STORYGRAPH_BOOK_CARD_BOOK_TITLE_AUTHOR_AND_SERIES)) > C.ONE:
            break
        parent = ancestor
    return parent


def _personal_links(root: Tag, base: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for link in root.find_all(S.A, href=C.TRUE):
        if not isinstance(link, Tag) or not _visible(link):
            continue
        label = _label(_attr(link, S.ARIA_LABEL) or _text(link))
        if label in {
            S.STORYGRAPH_PERSONAL_LINKS_YOUR_REVIEW,
            S.STORYGRAPH_PERSONAL_LINKS_MY_REVIEW,
            S.STORYGRAPH_PERSONAL_LINKS_VIEW_YOUR_REVIEW,
            S.STORYGRAPH_PERSONAL_LINKS_READ_YOUR_REVIEW,
        }:
            kind = S.REVIEW
        elif label in {
            S.STORYGRAPH_PERSONAL_LINKS_YOUR_READING_HISTORY,
            S.STORYGRAPH_PERSONAL_LINKS_MY_READING_HISTORY,
            S.STORYGRAPH_OWNER_REGIONS_AUTHORED_READING_HISTORY,
            S.STORYGRAPH_PERSONAL_LINKS_YOUR_READING_JOURNAL,
            S.STORYGRAPH_PERSONAL_LINKS_YOUR_READING_ACTIVITY,
        }:
            kind = S.HISTORY
        elif label in {
            S.STORYGRAPH_PERSONAL_LINKS_YOUR_BOOK_DETAILS,
            S.STORYGRAPH_PERSONAL_LINKS_MY_BOOK_DETAILS,
        }:
            kind = S.DETAILS
        else:
            continue
        if any(
            _attr(link, key).casefold() not in {S.EMPTY, S.GET_2}
            for key in (S.DATA_METHOD, S.DATA_TURBO_METHOD)
        ):
            continue
        url = _safe_url(_attr(link, S.HREF), base)
        if any(
            part in unquote(urlsplit(url).path).split(S.SLASH) for part in (S.EDIT, S.NEW, S.DELETE)
        ):
            continue
        links.append((kind, url))
    return links


class StoryGraphConnector:
    def __init__(
        self, browser: BrowserFetcher, *, max_pages: int = C.STORYGRAPHCONNECTOR_INIT_MAX_PAGES
    ) -> None:
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < C.ONE:
            raise ValueError(S.GOODREADS_GOODREADSCONNECTOR_INIT_MAX_PAGES_BE_A_POSITIVE_INTEGER)
        self.browser = browser
        self.max_pages = max_pages

    def _fetch(
        self, url: str, account: Account, *, owner_required: bool = C.FALSE
    ) -> tuple[PageDocument, BeautifulSoup]:
        document = self.browser.fetch(_safe_url(url))
        _safe_url(document.url)
        problem = page_access_problem(document)
        if problem is not C.NONE:
            raise problem
        soup = BeautifulSoup(document.html, S.HTML_PARSER)
        _identity(soup, account.account_id, required=owner_required)
        return (document, soup)

    def _list_page(
        self, soup: BeautifulSoup, surface: _Surface, account: Account, url: str
    ) -> tuple[list[BookRecord], dict[str, list[tuple[str, str]]], str, list[Issue]]:
        selector = {
            ReadingStatus.READ: S.STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_READ_BOOKS,
            ReadingStatus.CURRENTLY_READING: S.STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_READ_BOOKS,
            ReadingStatus.TO_READ: S.STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_TO_READ_BOOKS,
            ReadingStatus.PAUSED: S.STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_PAUSED_BOOKS_READ_BOOKS,
            ReadingStatus.DNF: S.STORYGRAPHCONNECTOR_LIST_PAGE_SELECTOR_READ_BOOKS,
        }[surface.status]
        containers = [
            tag for tag in soup.select(selector) if isinstance(tag, Tag) and _visible(tag)
        ]
        if not containers:
            containers = [
                tag
                for tag in soup.find_all([S.SECTION, S.MAIN])
                if isinstance(tag, Tag)
                and _visible(tag)
                and (
                    C.STORYGRAPH_STATUS_NAMES.get(_label(_attr(tag, S.ARIA_LABEL)))
                    == surface.status
                )
            ]
        if len(containers) != C.ONE:
            raise ConnectorError(
                S.STORYGRAPH_STORYGRAPHCONNECTOR_LIST_PAGE_CONTAINER_WAS_MISSING,
                code=S.COLLECTION_LAYOUT_UNAVAILABLE,
            )
        container = containers[C.ZERO]
        titles = [
            tag
            for tag in container.select(S.STORYGRAPH_BOOK_CARD_BOOK_TITLE_AUTHOR_AND_SERIES)
            if isinstance(tag, Tag) and _visible(tag)
        ]
        records: list[BookRecord] = []
        links: dict[str, list[tuple[str, str]]] = {}
        issues: list[Issue] = []
        for title in titles:
            title_links = [
                link
                for link in title.find_all(S.A, href=C.TRUE)
                if isinstance(link, Tag)
                and C.STORYGRAPH_BOOK_PATH.fullmatch(
                    urlsplit(urljoin(url, _attr(link, S.HREF))).path
                )
                and _visible(link)
            ]
            if not title_links or not _text(title_links[C.ZERO]):
                issues.append(
                    Issue(
                        code=S.BOOK_IDENTITY_MISSING,
                        message=S.STORYGRAPHCONNECTOR_LIST_PAGE_MESSAGE_A_ENTRY_LACKED_A_BOOK_IDENTITY,
                    )
                )
                continue
            book_url = _safe_url(_attr(title_links[C.ZERO], S.HREF), url)
            match = C.STORYGRAPH_BOOK_PATH.fullmatch(urlsplit(book_url).path)
            assert match is not C.NONE
            source_id = match[C.ONE]
            authors = tuple(
                _text(link)
                for link in title.find_all(S.A, href=C.TRUE)
                if isinstance(link, Tag)
                and urlsplit(urljoin(url, _attr(link, S.HREF))).path.startswith(
                    S.STORYGRAPHCONNECTOR_LIST_PAGE_AUTHORS_AUTHORS
                )
                and _visible(link)
                and _text(link)
            )
            card = _book_card(title, container)
            try:
                observations, events, problems = _personal(
                    card, account.account_id, source_id, surface.status, url
                )
            except ConnectorError as exc:
                observations = [
                    _observation(field, C.NONE, FieldState.FAILED, url)
                    for field in C.STORYGRAPH_PERSONAL_FIELDS
                ]
                events = []
                problems = [Issue(code=exc.code, message=str(exc), source_id=source_id)]
            observations.extend(
                (
                    _observation(
                        S.TITLE, _text(title_links[C.ZERO]), FieldState.PRESENT, url, reader=C.FALSE
                    ),
                    _observation(
                        S.AUTHORS,
                        list(authors) if authors else C.NONE,
                        FieldState.PRESENT if authors else FieldState.UNAVAILABLE,
                        url,
                        reader=C.FALSE,
                    ),
                    _observation(S.ISBNS, C.NONE, FieldState.UNAVAILABLE, url, reader=C.FALSE),
                    _observation(S.STATUSES, [surface.status.value], FieldState.PRESENT, url),
                    _observation(S.STATUS, surface.status.value, FieldState.PRESENT, url),
                )
            )
            record = BookRecord(
                source=Source.STORYGRAPH,
                source_id=source_id,
                title=_text(title_links[C.ZERO]),
                authors=authors,
                url=_receipt_url(book_url),
                status=surface.status,
                raw_status=surface.status.value,
                collections=(surface.status.value,),
                observations=tuple(observations),
                reading_events=tuple(events),
            )
            records.append(record)
            try:
                links[source_id] = _personal_links(card, url)
            except ConnectorError as exc:
                issues.append(Issue(code=exc.code, message=str(exc), source_id=source_id))
            issues.extend(problems)
        if not titles and (
            not re.search(
                S.STORYGRAPH_STORYGRAPHCONNECTOR_LIST_PAGE_B_BOOKS_BOOKS_NO_READS_YET,
                _text(container),
                re.I,
            )
        ):
            raise ConnectorError(
                S.STORYGRAPH_STORYGRAPHCONNECTOR_LIST_PAGE_CONTAINER_DID_NOT_PROVIDE,
                code=S.EMPTY_COLLECTION_UNVERIFIED,
            )
        fingerprint = hashlib.sha256(
            (
                _text(container)
                + repr(
                    [
                        _attr(link, S.HREF)
                        for link in container.find_all(S.A, href=C.TRUE)
                        if isinstance(link, Tag)
                        and _attr(link, S.ID) != S.NEXT_LINK
                        and _visible(link)
                    ]
                )
            ).encode()
        ).hexdigest()
        return (records, links, fingerprint, issues)

    def _next(self, soup: BeautifulSoup, url: str, account: Account) -> str | None:
        candidates = [
            tag
            for tag in soup.select(
                S.STORYGRAPHCONNECTOR_NEXT_CANDIDATES_A_NEXT_LINK_HREF_A_REL_NEXT
            )
            if isinstance(tag, Tag) and _visible(tag) and (_attr(tag, S.ARIA_DISABLED) != S.TRUE_2)
        ]
        urls = {_safe_url(_attr(tag, S.HREF), url) for tag in candidates}
        if len(urls) > C.ONE:
            raise ConnectorError(
                S.STORYGRAPH_STORYGRAPHCONNECTOR_NEXT_STORYGRAPH_LINKS_WERE_AMBIGUOUS,
                code=S.PAGINATION_AMBIGUOUS,
            )
        if not urls:
            return C.NONE
        next_url = next(iter(urls))
        if not _owned_list_url(next_url, account.account_id) or urlsplit(next_url).path.rstrip(
            S.SLASH
        ) != urlsplit(url).path.rstrip(S.SLASH):
            raise ConnectorError(
                S.STORYGRAPH_STORYGRAPHCONNECTOR_NEXT_A_CHANGED_COLLECTION_OR_ACCOUNT,
                code=S.PAGINATION_OWNER_MISMATCH,
            )
        return next_url

    def _detail(
        self,
        record: BookRecord,
        account: Account,
        links: list[tuple[str, str]],
        on_record: Callable[[BookRecord], None],
    ) -> tuple[BookRecord, list[Issue], ConnectorError | None]:
        queue = [(S.BOOK, record.url), *links]
        seen: set[str] = set()
        history_fingerprints: set[str] = set()
        history_pages = C.ZERO
        other_pages = C.ZERO
        issues: list[Issue] = []
        current = record
        for kind, requested in queue:
            if _url_key(requested) in seen:
                continue
            if kind == S.HISTORY:
                if history_pages >= self.max_pages:
                    issues.append(
                        Issue(
                            code=S.HISTORY_PAGINATION_LIMIT,
                            message=S.STORYGRAPHCONNECTOR_DETAIL_MESSAGE_THE_PAGE_LIMIT_WAS_REACHED,
                            source_id=record.source_id,
                        )
                    )
                    current = current.model_copy(
                        update={
                            S.OBSERVATIONS: tuple(
                                item.model_copy(
                                    update={S.STATE: FieldState.FAILED, S.VALUE: C.NONE}
                                )
                                if item.field == S.READING_EVENTS
                                else item
                                for item in current.observations
                            )
                        }
                    )
                    on_record(current)
                    break
                history_pages += C.ONE
            else:
                if other_pages >= C.FOUR:
                    issues.append(
                        Issue(
                            code=S.DETAIL_LINK_LIMIT,
                            message=S.STORYGRAPHCONNECTOR_DETAIL_MESSAGE_LINKS_REMAIN_UNVERIFIED,
                            source_id=record.source_id,
                        )
                    )
                    continue
                other_pages += C.ONE
            seen.add(_url_key(requested))
            try:
                for key, value in parse_qsl(urlsplit(requested).query):
                    if (
                        key in {S.USER, S.USERNAME, S.OWNER, S.ACCOUNT}
                        and value != account.account_id
                    ):
                        raise ConnectorError(
                            S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_A_LINK_CHANGED_READER_IDENTITY,
                            code=S.REVIEW_OWNER_MISMATCH,
                        )
                document, soup = self._fetch(requested, account, owner_required=C.TRUE)
                regions = _owner_regions(soup, account.account_id)
                if kind == S.BOOK:
                    match = C.STORYGRAPH_BOOK_PATH.fullmatch(urlsplit(document.url).path)
                    if match is C.NONE or match[C.ONE] != record.source_id:
                        raise ConnectorError(
                            S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_A_CHANGED_BOOK_IDENTITY,
                            code=S.BOOK_IDENTITY_MISMATCH,
                        )
                else:
                    associated_ids = {
                        match[C.ONE]
                        for region in regions
                        for link in region.find_all(S.A, href=C.TRUE)
                        if isinstance(link, Tag)
                        and (
                            match := C.STORYGRAPH_BOOK_PATH.fullmatch(
                                urlsplit(urljoin(document.url, _attr(link, S.HREF))).path
                            )
                        )
                    }
                    if not associated_ids:
                        associated_ids = {
                            match[C.ONE]
                            for link in soup.select(
                                S.STORYGRAPHCONNECTOR_DETAIL_ASSOCIATED_IDS_BOOK_AND_SERIES_A_HREF
                            )
                            if isinstance(link, Tag)
                            and (
                                match := C.STORYGRAPH_BOOK_PATH.fullmatch(
                                    urlsplit(urljoin(document.url, _attr(link, S.HREF))).path
                                )
                            )
                        }
                    if not regions or associated_ids != {record.source_id}:
                        raise ConnectorError(
                            S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_THE_DID_NOT_VERIFY_BOTH,
                            code=S.PERSONAL_PAGE_IDENTITY_UNAVAILABLE,
                        )
                if kind == S.HISTORY:
                    fingerprint = hashlib.sha256(
                        S.NEWLINE.join(_text(region) for region in regions).encode()
                    ).hexdigest()
                    if fingerprint in history_fingerprints:
                        raise ConnectorError(
                            S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_A_HISTORY_PAGE_REPEATED,
                            code=S.HISTORY_REPEATED_PAGE,
                        )
                    history_fingerprints.add(fingerprint)
                observations, events, problems = _personal(
                    soup, account.account_id, record.source_id, current.status, document.url
                )
                issues.extend(problems)
                values = _pairs(soup) if kind == S.BOOK else {}
                isbns: tuple[str, ...] = ()
                if S.ISBNS in values:
                    isbn = normalize_isbn(values[S.ISBNS])
                    if isbn:
                        isbns = (isbn,)
                        observations.append(
                            _observation(
                                S.ISBNS, [isbn], FieldState.PRESENT, document.url, reader=C.FALSE
                            )
                        )
                    else:
                        observations.append(
                            _observation(
                                S.ISBNS, C.NONE, FieldState.FAILED, document.url, reader=C.FALSE
                            )
                        )
                        issues.append(
                            Issue(
                                code=S.INVALID_ISBN,
                                message=S.STORYGRAPHCONNECTOR_DETAIL_MESSAGE_A_VISIBLE_ISBN_FAILED_VALIDATION,
                                source_id=record.source_id,
                            )
                        )
                tags = [
                    _text(tag)
                    for tag in soup.select(
                        S.STORYGRAPHCONNECTOR_DETAIL_TAGS_BOOK_PAGE_TAG_SECTION_SPAN
                    )
                    if isinstance(tag, Tag) and _visible(tag) and _text(tag)
                ]
                if tags:
                    observations.append(
                        _observation(
                            S.BOOK_TAGS,
                            list(dict.fromkeys(tags)),
                            FieldState.PRESENT,
                            document.url,
                            reader=C.FALSE,
                        )
                    )
                community = soup.select_one(
                    S.STORYGRAPHCONNECTOR_DETAIL_COMMUNITY_AVERAGE_STAR_RATING
                )
                if isinstance(community, Tag) and _visible(community):
                    community_state, number = _rating(_text(community), quarter_stars=C.FALSE)
                    observations.append(
                        _observation(
                            S.COMMUNITY_RATING,
                            number,
                            community_state,
                            document.url,
                            reader=C.FALSE,
                        )
                    )
                new = current.model_copy(
                    update={
                        S.OBSERVATIONS: tuple(observations),
                        S.READING_EVENTS: tuple(events),
                        S.ISBNS: isbns,
                        S.EDITION_FORMAT: values.get(S.EDITION_FORMAT),
                        S.LANGUAGE: values.get(S.LANGUAGE),
                        S.DETAIL_CHECKED_AT: utc_now(),
                    }
                )
                current = _merge(current, new)
                on_record(current)
                if kind == S.BOOK:
                    queue.extend(_personal_links(soup, document.url))
                elif kind == S.HISTORY:
                    next_links = soup.select(
                        S.STORYGRAPHCONNECTOR_NEXT_CANDIDATES_A_NEXT_LINK_HREF_A_REL_NEXT
                    )
                    next_urls = {
                        _safe_url(_attr(link, S.HREF), document.url)
                        for link in next_links
                        if isinstance(link, Tag)
                        and _visible(link)
                        and (_attr(link, S.ARIA_DISABLED) != S.TRUE_2)
                    }
                    if len(next_urls) > C.ONE:
                        raise ConnectorError(
                            S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_PAGINATION_WAS_AMBIGUOUS,
                            code=S.HISTORY_PAGINATION_AMBIGUOUS,
                        )
                    if next_urls:
                        next_url = next(iter(next_urls))
                        if urlsplit(next_url).path != urlsplit(document.url).path:
                            raise ConnectorError(
                                S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_READING_CHANGED_ITS_SURFACE,
                                code=S.HISTORY_PAGINATION_IDENTITY,
                            )
                        if _url_key(next_url) in seen:
                            raise ConnectorError(
                                S.STORYGRAPH_STORYGRAPHCONNECTOR_DETAIL_READING_REPEATED_A_CURSOR,
                                code=S.HISTORY_REPEATED_CURSOR,
                            )
                        queue.append((S.HISTORY, next_url))
            except ConnectorError as exc:
                issues.append(
                    Issue(
                        code=exc.code,
                        message=str(exc),
                        source_id=record.source_id,
                        retryable=exc.retryable,
                    )
                )
                if (
                    exc.state in {SyncState.NEEDS_AUTH, SyncState.BLOCKED}
                    or exc.code == S.WRONG_ACCOUNT
                ):
                    return (current, issues, exc)
                failed_fields = (
                    {S.READING_EVENTS} if kind == S.HISTORY else set(C.STORYGRAPH_REQUIRED_FIELDS)
                )
                failed = tuple(
                    observation.model_copy(update={S.STATE: FieldState.FAILED, S.VALUE: C.NONE})
                    if observation.field in failed_fields
                    and (kind == S.HISTORY or observation.state == FieldState.UNAVAILABLE)
                    else observation
                    for observation in current.observations
                )
                current = current.model_copy(update={S.OBSERVATIONS: failed})
                on_record(current)
        return (current, issues, C.NONE)

    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        started = utc_now()
        records: dict[str, BookRecord] = {}
        issues: list[Issue] = []
        surfaces: dict[ReadingStatus, FieldState] = {}
        pages = C.ZERO
        identity = C.FALSE
        terminated = C.TRUE
        terminal_state: SyncState | None = C.NONE
        queue: list[_Surface] = []
        detailed: set[str] = set()

        def progress(cursor: str | None = C.NONE) -> None:
            if on_progress is not C.NONE:
                on_progress(
                    CollectionProgress(
                        source=Source.STORYGRAPH,
                        collection=S.LIBRARY,
                        pages_seen=pages,
                        records=tuple(records.values()),
                        cursor=cursor,
                        message=S.COLLECT_PROGRESS_MESSAGE_TEMPLATE.format(
                            v0=len(records), v1=pages
                        ),
                    )
                )

        def keep_detail(record: BookRecord) -> None:
            records[record.source_id] = record
            progress()

        if account.source != Source.STORYGRAPH:
            raise ConnectorError(
                S.STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_A_STORYGRAPH_ACCOUNT, code=S.WRONG_SOURCE
            )
        try:
            profile, soup = self._fetch(account.profile_url, account, owner_required=C.TRUE)
            identity = C.TRUE
            if _receipt_url(profile.url).rstrip(S.SLASH) != account.profile_url.rstrip(S.SLASH):
                raise ConnectorError(
                    S.STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_THE_CHANGED_ACCOUNT_IDENTITY,
                    code=S.WRONG_ACCOUNT,
                )
            found, empty = _discover_surfaces(soup, account, profile.url)
            queue.extend(found)
            for status in empty:
                surfaces[status] = FieldState.EMPTY
            for path, status in C.STORYGRAPH_KNOWN_SURFACES.items():
                if status in {ReadingStatus.READ, ReadingStatus.CURRENTLY_READING} and (
                    not any(surface.status == status for surface in queue)
                ):
                    queue.append(
                        _Surface(
                            status,
                            S.STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_TEMPLATE.format(
                                v0=S.STORYGRAPH_ORIGIN_HTTPS_APP_THESTORYGRAPH_COM,
                                v1=path,
                                v2=quote(account.account_id, safe=S.EMPTY),
                            ),
                        )
                    )
            seen_surfaces: set[ReadingStatus] = set()
            for surface in queue:
                if surface.status in seen_surfaces:
                    continue
                seen_surfaces.add(surface.status)
                surfaces[surface.status] = FieldState.UNAVAILABLE
                seen_urls: set[str] = set()
                fingerprints: set[str] = set()
                url: str | None = surface.url
                surface_count = C.ZERO
                while url is not C.NONE:
                    if pages >= self.max_pages:
                        terminated = C.FALSE
                        issues.append(
                            Issue(
                                code=S.PAGINATION_LIMIT,
                                message=S.STORYGRAPHCONNECTOR_COLLECT_MESSAGE_THE_PAGE_LIMIT_WAS_REACHED,
                                retryable=C.TRUE,
                            )
                        )
                        break
                    key = _url_key(url)
                    if key in seen_urls:
                        terminated = C.FALSE
                        issues.append(
                            Issue(
                                code=S.PAGINATION_REPEATED_CURSOR,
                                message=S.STORYGRAPHCONNECTOR_COLLECT_MESSAGE_A_PAGINATION_CURSOR_REPEATED,
                            )
                        )
                        break
                    seen_urls.add(key)
                    try:
                        document, page = self._fetch(url, account, owner_required=C.TRUE)
                        if not _owned_list_url(document.url, account.account_id) or urlsplit(
                            document.url
                        ).path.rstrip(S.SLASH) != urlsplit(surface.url).path.rstrip(S.SLASH):
                            raise ConnectorError(
                                S.STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_A_ACCOUNT_OR_COLLECTION,
                                code=S.PAGINATION_OWNER_MISMATCH,
                            )
                        page_records, personal_links, fingerprint, problems = self._list_page(
                            page, surface, account, document.url
                        )
                        pages += C.ONE
                        if fingerprint in fingerprints:
                            raise ConnectorError(
                                S.STORYGRAPH_STORYGRAPHCONNECTOR_COLLECT_COLLECTION_PAGE_CONTENT,
                                code=S.PAGINATION_REPEATED_PAGE,
                            )
                        fingerprints.add(fingerprint)
                        issues.extend(problems)
                        for record in page_records:
                            prior = records.get(record.source_id)
                            records[record.source_id] = _merge(prior, record) if prior else record
                        surface_count += len(page_records)
                        progress()
                        found, empty = _discover_surfaces(page, account, document.url)
                        queue.extend(found)
                        for status in empty:
                            if status not in surfaces:
                                surfaces[status] = FieldState.EMPTY
                        for record in page_records:
                            if record.source_id in detailed:
                                continue
                            detailed.add(record.source_id)
                            enriched, detail_issues, detail_failure = self._detail(
                                records[record.source_id],
                                account,
                                personal_links.get(record.source_id, []),
                                keep_detail,
                            )
                            records[record.source_id] = enriched
                            issues.extend(detail_issues)
                            if detail_failure is not C.NONE:
                                raise detail_failure
                        url = self._next(page, document.url, account)
                        if url is C.NONE:
                            surfaces[surface.status] = (
                                FieldState.PRESENT if surface_count else FieldState.EMPTY
                            )
                    except ConnectorError as exc:
                        terminated = C.FALSE
                        issues.append(
                            Issue(code=exc.code, message=str(exc), retryable=exc.retryable)
                        )
                        if (
                            exc.state in {SyncState.NEEDS_AUTH, SyncState.BLOCKED}
                            or exc.code == S.WRONG_ACCOUNT
                        ):
                            terminal_state = exc.state
                        url = C.NONE
                    cursor = (
                        S.STORYGRAPHCONNECTOR_COLLECT_CURSOR_TEMPLATE.format(
                            v0=surface.status.value,
                            v1=hashlib.sha256(url.encode()).hexdigest()[
                                : C.STORYGRAPHCONNECTOR_COLLECT_CURSOR
                            ],
                        )
                        if url
                        else C.NONE
                    )
                    progress(cursor)
                    if terminal_state is not C.NONE:
                        break
                if terminal_state is not C.NONE or (pages >= self.max_pages and url is not C.NONE):
                    break
        except ConnectorError as exc:
            terminal_state = exc.state
            terminated = C.FALSE
            issues.append(Issue(code=exc.code, message=str(exc), retryable=exc.retryable))
        for status in C.STORYGRAPH_REQUIRED_SURFACES:
            if status not in surfaces:
                surfaces[status] = FieldState.UNSUPPORTED
                issues.append(
                    Issue(
                        code=S.COLLECTION_NOT_EXPOSED,
                        message=S.STORYGRAPHCONNECTOR_COLLECT_MESSAGE_TEMPLATE.format(
                            v0=status.value
                        ),
                    )
                )
        for source_id, record in records.items():
            count = next(
                (
                    item.value
                    for item in record.observations
                    if item.field == S.READ_COUNT and item.state == FieldState.PRESENT
                ),
                C.NONE,
            )
            completed_reads = sum(
                event.status == ReadingStatus.READ for event in record.reading_events
            )
            if (
                isinstance(count, int)
                and (not isinstance(count, bool))
                and (count != completed_reads)
            ):
                issues.append(
                    Issue(
                        code=S.READING_EVENTS_INCOMPLETE,
                        message=S.STORYGRAPHCONNECTOR_COLLECT_MESSAGE_THE_COUNT_DIFFERS_FROM_THE,
                        source_id=source_id,
                    )
                )
                updated = tuple(
                    item.model_copy(update={S.STATE: FieldState.FAILED, S.VALUE: C.NONE})
                    if item.field == S.READING_EVENTS
                    else item
                    for item in record.observations
                )
                records[source_id] = record.model_copy(update={S.OBSERVATIONS: updated})
        capabilities = {
            S.STORYGRAPHCONNECTOR_COLLECT_CAPABILITIES_TEMPLATE.format(v0=status.value): state
            for status, state in surfaces.items()
        }
        capabilities[S.OWNER_IDENTITY] = FieldState.PRESENT if identity else FieldState.UNAVAILABLE
        for field in (*C.STORYGRAPH_PERSONAL_FIELDS, S.STATUS):
            states = {
                item.state
                for record in records.values()
                for item in record.observations
                if item.field == field
            }
            capabilities[field] = next(
                (
                    state
                    for state in (
                        FieldState.FAILED,
                        FieldState.UNAVAILABLE,
                        FieldState.UNSUPPORTED,
                        FieldState.PRESENT,
                        FieldState.EMPTY,
                    )
                    if state in states
                ),
                FieldState.UNSUPPORTED,
            )
        verified_empty = (
            identity
            and terminated
            and (not records)
            and all(
                surfaces[status] == FieldState.EMPTY for status in C.STORYGRAPH_REQUIRED_SURFACES
            )
        )
        if verified_empty:
            for field in (*C.STORYGRAPH_REQUIRED_FIELDS, S.STATUS):
                capabilities[field] = FieldState.EMPTY
        complete = (
            identity
            and terminated
            and all(
                surfaces[status] in {FieldState.PRESENT, FieldState.EMPTY}
                for status in C.STORYGRAPH_REQUIRED_SURFACES
            )
            and all(
                item.state in {FieldState.PRESENT, FieldState.EMPTY}
                for record in records.values()
                for item in record.observations
                if item.field in (*C.STORYGRAPH_REQUIRED_FIELDS, S.STATUS)
            )
            and (not issues)
            and (
                not any(
                    item.state == FieldState.FAILED
                    for record in records.values()
                    for item in record.observations
                )
            )
        )
        if identity and (not complete) and (terminal_state is C.NONE):
            issues.append(
                Issue(
                    code=S.COVERAGE_INCOMPLETE,
                    message=S.STORYGRAPHCONNECTOR_COLLECT_MESSAGE_COLLECTION_COVERAGE_REMAIN,
                )
            )
        return CollectionSnapshot(
            source=Source.STORYGRAPH,
            account_id=account.account_id,
            collection=S.LIBRARY,
            state=terminal_state or (SyncState.COMPLETE if complete else SyncState.PARTIAL),
            records=tuple(records.values()),
            started_at=started,
            pages_seen=pages,
            identity_verified=identity,
            termination_verified=terminated
            and all(
                surfaces[status] in {FieldState.PRESENT, FieldState.EMPTY}
                for status in C.STORYGRAPH_REQUIRED_SURFACES
            ),
            capabilities=capabilities,
            issues=tuple(issues),
        )
