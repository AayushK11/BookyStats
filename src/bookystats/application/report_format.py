from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable, Iterable
from datetime import datetime
from html import unescape
from urllib.parse import parse_qs, urlsplit

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.reader_report import Link


def clean(text: str) -> str:
    folded = unicodedata.normalize(S.RPT_NFC, text)
    return C.CONTENT_ANALYSIS_SPACE.sub(S.SPACE, C.PDF_CONTROL_PATTERN.sub(S.SPACE, folded)).strip()


def count(value: int) -> str:
    return S.RPT_COUNT.format(value=value)


def noun(value: int, one: str, many: str) -> str:
    return S.RPT_NOUN.format(value=count(value), noun=one if value == C.ONE else many)


def books(value: int) -> str:
    return noun(value, S.RPT_BOOK, S.RPT_BOOKS)


def pages(value: float) -> str:
    return noun(int(value + C.RPT_HALF), S.RPT_PAGE, S.RPT_PAGES)


def trimmed(value: float, places: int = C.TWO) -> str:
    text = S.RPT_FIXED.format(value=value, places=places)
    if S.RPT_DOT in text:
        text = text.rstrip(S.RPT_ZERO).rstrip(S.RPT_DOT)
    return S.RPT_ZERO if text in C.RPT_NEGATIVE_ZEROS else text


def stars(value: float | None) -> str:
    return S.RPT_UNKNOWN if value is C.NONE else trimmed(value)


def signed(value: float, places: int = C.TWO) -> str:
    text = trimmed(abs(value), places)
    if text == S.RPT_ZERO:
        return text
    return (S.RPT_PLUS if value > C.ZERO else S.RPT_MINUS) + text


def star_noun(value: float) -> str:
    return S.RPT_STAR if round(abs(value), C.TWO) == C.ONE else S.RPT_STARS


def star_count(value: float) -> str:
    return S.RPT_NOUN.format(value=trimmed(value), noun=star_noun(value))


def signed_stars(value: float) -> str:
    return S.RPT_NOUN.format(value=signed(value), noun=star_noun(value))


def percent(part: int, whole: int) -> str:
    if whole <= C.ZERO:
        return S.RPT_UNKNOWN
    if part <= C.ZERO:
        return S.RPT_PERCENT.format(value=C.ZERO)
    share = part * C.RPT_PERCENT_SCALE / whole
    if share < C.ONE:
        return S.RPT_PERCENT_UNDER_ONE
    rounded = int(share + C.RPT_HALF)
    if rounded >= C.RPT_PERCENT_SCALE and part < whole:
        rounded = C.RPT_PERCENT_SCALE - C.ONE
    return S.RPT_PERCENT.format(value=rounded)


def share_text(part: int, whole: int) -> str:
    return S.RPT_OF_SHARE.format(part=count(part), whole=count(whole), share=percent(part, whole))


def fraction(value: float) -> str:
    return percent(int(value * C.RPT_FRACTION_SCALE + C.RPT_HALF), C.RPT_FRACTION_SCALE)


def span(days: float) -> str:
    if days < C.RPT_DAYS_PER_MONTH * C.TWO:
        return noun(int(days + C.RPT_HALF), S.RPT_DAY, S.RPT_DAYS)
    if days < C.RPT_DAYS_PER_YEAR:
        return noun(int(days / C.RPT_DAYS_PER_MONTH + C.RPT_HALF), S.RPT_MONTH, S.RPT_MONTHS)
    years = trimmed(days / C.RPT_DAYS_PER_YEAR, C.ONE)
    return S.RPT_NOUN.format(value=years, noun=S.RPT_YEAR if years == S.RPT_ONE else S.RPT_YEARS)


def join_names(names: Iterable[str]) -> str:
    items = [name for name in names if name]
    if not items:
        return S.EMPTY
    if len(items) == C.ONE:
        return items[C.ZERO]
    return S.RPT_AND.format(head=S.COMMA_SPACE.join(items[: -C.ONE]), tail=items[-C.ONE])


def month_year(value: str) -> str:
    parts = value.split(S.HYPHEN)
    year = int(parts[C.ZERO])
    if len(parts) == C.ONE:
        return str(year)
    month = C.RPT_MONTHS[int(parts[C.ONE]) - C.ONE]
    if len(parts) == C.TWO:
        return S.RPT_MONTH_YEAR.format(month=month, year=year)
    return S.RPT_DAY_MONTH_YEAR.format(day=int(parts[C.TWO]), month=month, year=year)


def as_of_parts(as_of: str | None) -> datetime | None:
    if not as_of:
        return C.NONE
    try:
        return datetime.fromisoformat(as_of)
    except ValueError:
        return C.NONE


def as_of_text(as_of: str | None) -> str:
    moment = as_of_parts(as_of)
    if moment is C.NONE:
        return S.RPT_UNKNOWN_DATE
    return S.RPT_DAY_MONTH_YEAR.format(
        day=moment.day, month=C.RPT_MONTHS[moment.month - C.ONE], year=moment.year
    )


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit + C.ONE]
    index = max(cut.rfind(S.SPACE), cut.rfind(S.HYPHEN))
    if index <= C.RPT_MIN_SHORTEN:
        return text
    return text[:index].rstrip(C.RPT_TRIM_CHARACTERS) + S.RPT_ELLIPSIS


def display_title(title: str) -> str:
    text = clean(C.RPT_SERIES_SUFFIX.sub(S.EMPTY, clean(title)))
    return shorten(text or clean(title), C.RPT_TITLE_LIMIT)


def byline(authors: Iterable[str]) -> str:
    names = tuple(dict.fromkeys(clean(name) for name in authors if clean(name)))
    return join_names(names) if names else S.RPT_UNKNOWN_AUTHOR


def stable_pick[T](items: Iterable[T], key: Callable[[T], str], limit: int, salt: str) -> list[T]:
    def rank(item: T) -> str:
        token = S.RPT_HASH_JOIN.format(salt=salt, key=key(item)).encode(S.UTF_8)
        return hashlib.sha256(token).hexdigest()

    return sorted(items, key=rank)[:limit]


def plain_description(text: str | None) -> str:
    if not text:
        return S.EMPTY
    stripped = C.CONTENT_ANALYSIS_HTML.sub(S.SPACE, text[: C.CONTENT_ANALYSIS_MAX_DESCRIPTION])
    return C.CONTENT_ANALYSIS_SPACE.sub(S.SPACE, unescape(stripped)).strip()


def sentence(label: str) -> str:
    text = clean(label)
    return text[: C.ONE].upper() + text[C.ONE :] if text.islower() else text


def _inside_word(source: str, left: int, right: int) -> bool:
    if left < C.ZERO or right >= len(source):
        return C.FALSE
    before, after = source[left], source[right]
    if before.isalnum() and after.isalnum():
        return C.TRUE
    if before.isalnum() and after in C.RPT_WORD_JOINERS:
        return right + C.ONE < len(source) and source[right + C.ONE].isalnum()
    if before in C.RPT_WORD_JOINERS and after.isalnum():
        return left > C.ZERO and source[left - C.ONE].isalnum()
    return C.FALSE


def _cue_present(text: str, cue: str) -> bool:
    pattern = S.RPT_WORD_EDGE.format(cue=re.escape(cue))
    return re.search(pattern, text, re.IGNORECASE) is not C.NONE


def word_safe_excerpt(excerpt: str, cue: str, description: str | None) -> str | None:
    text = clean(excerpt)
    cue = clean(cue)
    if not text or not cue:
        return C.NONE
    source = plain_description(description)
    index = source.find(text) if source else -C.ONE
    left_partial = right_partial = left_more = right_more = C.TRUE
    if index >= C.ZERO:
        end = index + len(text)
        left_partial = _inside_word(source, index - C.ONE, index)
        right_partial = _inside_word(source, end - C.ONE, end)
        left_more = index > C.ZERO and not source[:index].rstrip().endswith(C.RPT_SENTENCE_END)
        right_more = end < len(source) and not text.endswith(C.RPT_SENTENCE_END)
    elif text.endswith(C.RPT_SENTENCE_END):
        right_partial = right_more = C.FALSE
    if left_partial:
        head, _, rest = text.partition(S.SPACE)
        if not rest or not head:
            return C.NONE
        text = rest
        left_more = C.TRUE
    if right_partial:
        rest, _, tail = text.rpartition(S.SPACE)
        if not rest or not tail:
            return C.NONE
        text = rest
        right_more = C.TRUE
    text = text.strip()
    if not _cue_present(text, cue):
        return C.NONE
    prefix = S.RPT_ELLIPSIS if left_more else S.EMPTY
    suffix = S.RPT_ELLIPSIS if right_more else S.EMPTY
    return prefix + text + suffix


def human_link(url: str | None) -> Link | None:
    if not url:
        return C.NONE
    try:
        parts = urlsplit(url)
    except ValueError:
        return C.NONE
    host = (parts.hostname or S.EMPTY).lower().removeprefix(S.RPT_WWW)
    path = parts.path.rstrip(S.RPT_SLASH)
    if parts.scheme != S.RPT_HTTPS or parts.username or parts.password:
        return C.NONE
    if host == S.RPT_GOODREADS_HOST and C.RPT_GOODREADS_PATH.fullmatch(path):
        return _link(host, S.RPT_WWW + host, path)
    if host == S.RPT_OPEN_LIBRARY_HOST and C.RPT_OPEN_LIBRARY_PATH.fullmatch(path):
        return _link(host, host, path.removesuffix(S.RPT_JSON_SUFFIX))
    if host == S.RPT_GOOGLE_API_HOST:
        match = C.RPT_GOOGLE_API_PATH.fullmatch(path)
        if match is not C.NONE:
            return _link(
                S.RPT_GOOGLE_BOOKS_HOST,
                S.RPT_GOOGLE_BOOKS_HOST,
                S.RPT_GOOGLE_BOOKS_PATH,
                match.group(C.ONE),
            )
    if host == S.RPT_GOOGLE_BOOKS_HOST and path == S.RPT_GOOGLE_BOOKS_PATH:
        identifiers = parse_qs(parts.query).get(S.RPT_GOOGLE_ID_KEY, [])
        if len(identifiers) == C.ONE and C.RPT_GOOGLE_ID.fullmatch(identifiers[C.ZERO]):
            return _link(host, host, path, identifiers[C.ZERO])
    return C.NONE


def _link(label_host: str, url_host: str, path: str, volume: str | None = C.NONE) -> Link:
    if volume is C.NONE:
        return Link(
            label=S.RPT_LINK_LABEL.format(host=label_host, path=path),
            url=S.RPT_URL.format(host=url_host, path=path),
        )
    return Link(
        label=S.RPT_LINK_LABEL_QUERY.format(host=label_host, path=path, volume=volume),
        url=S.RPT_URL_QUERY.format(host=url_host, path=path, volume=volume),
    )
