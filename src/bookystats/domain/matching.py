from __future__ import annotations

import unicodedata
from collections.abc import Callable

from bookystats import constants as C
from bookystats import strings as S
from bookystats.constants import MatchKind as MatchKind
from bookystats.domain.identifiers import normalized_isbns, normalized_text
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate, Source

type Matchable = BookRecord | MetadataCandidate


@C.frozen_dataclass
class MatchResult:
    kind: MatchKind
    reason: str
    identifiers: tuple[str, ...] = ()


def title_author_key(book: Matchable) -> str:
    title = normalized_text(book.title)
    authors = sorted({normalized_text(author) for author in book.authors if author.strip()})
    if not title or not authors or any(not author for author in authors):
        return S.EMPTY
    return (
        title + S.MATCHING_TITLE_AUTHOR_KEY_TEXT + S.MATCHING_TITLE_AUTHOR_KEY_TEXT_2.join(authors)
    )


def _title_key(title: str) -> str:
    normalized = normalized_text(title.replace(S.MATCH_REPAIR_AMPERSAND, S.MATCH_REPAIR_AND))
    return C.MATCH_REPAIR_VOLUME.sub(
        lambda match: S.MATCH_REPAIR_VOLUME_PREFIX + C.MATCH_REPAIR_VOLUME_NUMBERS[match[C.ONE]],
        normalized,
    )


def _title_parts(title: str, *, collections: bool = C.FALSE) -> tuple[str, dict[str, str]]:
    annotation = C.MATCH_REPAIR_SERIES_SUFFIX.search(title)
    series: dict[str, str] = {}
    if annotation:
        for item in annotation[S.MATCH_UPGRADE_SERIES_GROUP].split(S.RAW_SEMICOLON):
            pattern = C.MATCH_REPAIR_COLLECTION_ITEM if collections else C.MATCH_REPAIR_SERIES_ITEM
            match = pattern.fullmatch(item.strip())
            if not match:
                break
            name = _title_key(match[S.MATCH_UPGRADE_SERIES_GROUP].rstrip(S.COMMA))
            number = S.EMPTY.join(match[S.MATCH_UPGRADE_NUMBER_GROUP].split())
            if name in series and series[name] != number:
                break
            series[name] = number
        else:
            title = title[: annotation.start()]
            return _article_title(title), series
        series.clear()
    return _article_title(title), series


def _article_title(title: str) -> str:
    if article := C.MATCH_UPGRADE_ARTICLE_PATTERN.fullmatch(title.strip()):
        title = (
            article[S.MATCH_UPGRADE_ARTICLE_GROUP] + S.SPACE + article[S.MATCH_UPGRADE_TITLE_GROUP]
        )
    return title.strip()


def _series_conflict(left: dict[str, str], right: dict[str, str]) -> bool:
    shared = left.keys() & right.keys()
    return bool(left and right and (not shared or any(left[key] != right[key] for key in shared)))


def _latin_fold(value: str) -> str:
    decomposed = unicodedata.normalize(S.MATCH_UPGRADE_UNICODE_FORM, value)
    folded: list[str] = []
    latin_base = C.FALSE
    for char in decomposed:
        combining = unicodedata.category(char) == S.MATCH_UPGRADE_COMBINING_CATEGORY
        if combining and latin_base:
            continue
        folded.append(char)
        if not combining:
            latin_base = unicodedata.name(char, S.EMPTY).startswith(S.MATCH_UPGRADE_LATIN_PREFIX)
    return unicodedata.normalize(S.NFKC, S.EMPTY.join(folded))


def _author_key(author: str) -> str:
    tokens = normalized_text(_latin_fold(author)).split()
    result: list[str] = []
    initials: list[str] = []
    for token in tokens:
        if len(token) == C.ONE:
            initials.append(token)
        else:
            if initials:
                result.append(S.EMPTY.join(initials))
                initials.clear()
            result.append(token)
    if initials:
        result.append(S.EMPTY.join(initials))
    return S.SPACE.join(result)


def _authors(book: Matchable) -> set[str]:
    return {_author_key(author) for author in book.authors if author.strip()}


def candidate_title_author_key(book: Matchable) -> str:
    title, _ = _title_parts(book.title)
    title = _title_key(title.split(S.COLON, C.ONE)[C.ZERO])
    authors = sorted(_authors(book))
    if not title or not authors or any(not author for author in authors):
        return S.EMPTY
    return (
        title + S.MATCHING_TITLE_AUTHOR_KEY_TEXT + S.MATCHING_TITLE_AUTHOR_KEY_TEXT_2.join(authors)
    )


def work_bibliography_compatible(left: Matchable, right: Matchable) -> bool:
    left_title, left_series = _title_parts(left.title)
    right_title, right_series = _title_parts(right.title)
    title = _title_key(left_title)
    authors = _authors(left)
    return (
        bool(title)
        and title == _title_key(right_title)
        and bool(authors)
        and S.EMPTY not in authors
        and authors == _authors(right)
        and not _series_conflict(left_series, right_series)
    )


def work_bibliography_key(book: Matchable) -> str:
    title, _ = _title_parts(book.title)
    authors = sorted(_authors(book))
    title = _title_key(title)
    if not title or not authors or any(not author for author in authors):
        return S.EMPTY
    return (
        title + S.MATCHING_TITLE_AUTHOR_KEY_TEXT + S.MATCHING_TITLE_AUTHOR_KEY_TEXT_2.join(authors)
    )


def _work_title_key(title: str) -> str:
    return _title_key(
        _latin_fold(title).replace(S.MATCH_REPAIR_MULTIPLICATION, S.MATCH_REPAIR_LETTER_X)
    )


def _numbered_title(title: str) -> tuple[str, str, bool] | None:
    match = C.MATCH_REPAIR_NUMBERED_TITLE.fullmatch(_work_title_key(title))
    if not match:
        return C.NONE
    number = match[S.MATCH_UPGRADE_NUMBER_GROUP]
    explicit = bool(match[S.MATCH_REPAIR_VOLUME_MARKER])
    if not explicit and not number.isdecimal():
        return C.NONE
    number = C.MATCH_REPAIR_ROMAN_NUMBERS.get(number, number)
    return match[S.MATCH_UPGRADE_TITLE_GROUP], number, explicit


def work_candidate_keys(book: Matchable) -> tuple[str, ...]:
    title, _ = _title_parts(book.title, collections=C.TRUE)
    authors = sorted(_authors(book))
    author_key = S.MATCHING_TITLE_AUTHOR_KEY_TEXT_2.join(authors)
    keys = [S.MATCH_REPAIR_ISBN_KEY_PREFIX + isbn for isbn in normalized_isbns(book.isbns)]
    if authors and S.EMPTY not in authors and _work_title_key(title):
        keys.append(
            S.MATCH_REPAIR_ALTERNATE_PREFIX
            + _work_title_key(title)
            + S.MATCHING_TITLE_AUTHOR_KEY_TEXT
            + author_key
        )
        if numbered := _numbered_title(title):
            keys.append(
                S.MATCH_REPAIR_VOLUME_KEY_PREFIX
                + S.MATCHING_TITLE_AUTHOR_KEY_TEXT.join(
                    (numbered[C.ZERO], numbered[C.ONE], author_key)
                )
            )
    if key := work_bibliography_key(book):
        keys.append(key)
    return tuple(keys)


def compare_work_identity(left: Matchable, right: Matchable) -> MatchResult:
    if work_bibliography_compatible(left, right):
        return MatchResult(MatchKind.CONFIRMED, S.MATCH_REPAIR_WORK_REASON)
    left_title, left_series = _title_parts(left.title, collections=C.TRUE)
    right_title, right_series = _title_parts(right.title, collections=C.TRUE)
    left_authors, right_authors = _authors(left), _authors(right)
    authors_compatible = (
        bool(left_authors)
        and bool(right_authors)
        and S.EMPTY not in left_authors | right_authors
        and (left_authors <= right_authors or right_authors <= left_authors)
    )
    shared = tuple(sorted(set(normalized_isbns(left.isbns)) & set(normalized_isbns(right.isbns))))
    if not authors_compatible or _series_conflict(left_series, right_series):
        return MatchResult(
            MatchKind.UNRELATED, S.MATCHING_COMPARE_BOOKS_NO_CORROBORATED_IDENTITY_EVIDENCE
        )
    if (
        shared
        and _work_title_key(left_title)
        and _work_title_key(left_title) == _work_title_key(right_title)
    ):
        return MatchResult(MatchKind.CONFIRMED, S.MATCH_REPAIR_CORROBORATED_REASON, shared)
    left_numbered, right_numbered = _numbered_title(left_title), _numbered_title(right_title)
    if (
        left_authors == right_authors
        and normalized_isbns(left.isbns)
        and normalized_isbns(right.isbns)
        and left_numbered is not C.NONE
        and right_numbered is not C.NONE
        and left_numbered[: C.TWO] == right_numbered[: C.TWO]
        and (left_numbered[C.TWO] or right_numbered[C.TWO])
    ):
        return MatchResult(MatchKind.CONFIRMED, S.MATCH_REPAIR_VOLUME_REASON, shared)
    return MatchResult(
        MatchKind.UNRELATED, S.MATCHING_COMPARE_BOOKS_NO_CORROBORATED_IDENTITY_EVIDENCE
    )


def _compatible_subtitle(left: str, right: str) -> bool:
    left_parts, right_parts = left.split(S.COLON, C.ONE), right.split(S.COLON, C.ONE)
    return len(left_parts) != len(right_parts) and _title_key(left_parts[C.ZERO]) == _title_key(
        right_parts[C.ZERO]
    )


def edition_identity_facts(book: Matchable) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for field in C.MQ_EDITION_IDENTITY_FIELDS:
        facts = {
            normalized_text(item.value)
            for item in book.observations
            if item.field == field
            and item.scope == S.EDITION
            and item.state == FieldState.PRESENT
            and isinstance(item.value, str)
            and item.value.strip()
        }
        if isinstance(book, BookRecord) and (value := getattr(book, field)):
            facts.add(normalized_text(value))
        result[field] = facts
    return result


def _edition_conflict(left: Matchable, right: Matchable) -> bool:
    left_facts, right_facts = edition_identity_facts(left), edition_identity_facts(right)
    for field in C.MQ_EDITION_IDENTITY_FIELDS:
        values = (left_facts[field], right_facts[field])
        if any(len(facts) > C.ONE for facts in values):
            return C.TRUE
        if values[C.ZERO] and values[C.ONE] and (values[C.ZERO] != values[C.ONE]):
            return C.TRUE
    return C.FALSE


def compare_books(left: Matchable, right: Matchable) -> MatchResult:
    shared = tuple(sorted(set(normalized_isbns(left.isbns)) & set(normalized_isbns(right.isbns))))
    left_full, left_series = _title_parts(left.title)
    right_full, right_series = _title_parts(right.title)
    left_title, right_title = _title_key(left_full), _title_key(right_full)
    left_authors, right_authors = _authors(left), _authors(right)
    authors_agree = (
        bool(left_authors) and left_authors == right_authors and S.EMPTY not in left_authors
    )
    series_conflict = _series_conflict(left_series, right_series)
    subtitle_candidate = bool(
        left_title and right_title and _compatible_subtitle(left_full, right_full)
    )
    if shared:
        if series_conflict:
            return MatchResult(MatchKind.CONFLICTING, S.MATCH_UPGRADE_SERIES_CONFLICT, shared)
        if _edition_conflict(left, right):
            return MatchResult(
                MatchKind.CONFLICTING,
                S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_EDITION_LANGUAGE_OR_FORMAT,
                shared,
            )
        if left_title and right_title and (left_title != right_title):
            if subtitle_candidate and authors_agree:
                return MatchResult(MatchKind.LIKELY, S.MATCH_UPGRADE_SUBTITLE_CANDIDATE, shared)
            return MatchResult(
                MatchKind.CONFLICTING,
                S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_FULL_TITLES_DIFFER,
                shared,
            )
        if left_authors and right_authors and (left_authors != right_authors):
            if left_authors < right_authors or right_authors < left_authors:
                return MatchResult(MatchKind.LIKELY, S.MATCH_UPGRADE_AUTHOR_CANDIDATE, shared)
            return MatchResult(
                MatchKind.CONFLICTING,
                S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_AUTHOR_SETS_DIFFER,
                shared,
            )
        if left_title and left_title == right_title and authors_agree:
            return MatchResult(
                MatchKind.CONFIRMED,
                (
                    S.MATCHING_COMPARE_BOOKS_VALIDATED_ISBN_FULL_TITLE_AND_AUTHORS_AGREE
                    if title_author_key(left) == title_author_key(right)
                    else S.MATCH_UPGRADE_NORMALIZED_ISBN
                ),
                shared,
            )
        return MatchResult(
            MatchKind.LIKELY,
            S.MATCHING_COMPARE_BOOKS_SHARED_ISBN_LACKS_SUFFICIENT_TITLE_AND_AUTHOR,
            shared,
        )
    if not series_conflict and authors_agree and subtitle_candidate:
        return MatchResult(MatchKind.LIKELY, S.MATCH_UPGRADE_SUBTITLE_CANDIDATE)
    if not series_conflict and left_title and left_title == right_title and authors_agree:
        return MatchResult(
            MatchKind.LIKELY, S.MATCHING_COMPARE_BOOKS_EXACT_TITLE_AND_AUTHORS_WITHOUT_A_SHARED
        )
    return MatchResult(
        MatchKind.UNRELATED, S.MATCHING_COMPARE_BOOKS_NO_CORROBORATED_IDENTITY_EVIDENCE
    )


def _open_library_work(candidate: MetadataCandidate) -> bool:
    return (
        candidate.provider == Source.OPEN_LIBRARY
        and candidate.work_id == candidate.provider_id
        and candidate.edition_id is C.NONE
        and all(item.scope == S.WORK for item in candidate.observations)
    )


def _article_free(key: str) -> str:
    article, _, rest = key.partition(S.SPACE)
    return rest if article in C.L1_ID_LEADING_ARTICLES and rest else key


def _article_variant(left: str, right: str) -> bool:
    return left != right and (left == _article_free(right) or right == _article_free(left))


def _names_series(series: dict[str, str], title: str) -> bool:
    return any(_article_free(name) == _article_free(title) for name in series)


def work_query_title(title: str) -> str:
    stripped, _ = _title_parts(title)
    return normalized_text(stripped)


def relaxed_metadata_identity(book: BookRecord, candidate: MetadataCandidate) -> MatchResult | None:
    if not _open_library_work(candidate):
        return C.NONE
    book_title, book_series = _title_parts(book.title)
    candidate_title, candidate_series = _title_parts(candidate.title)
    left, right = _title_key(book_title), _title_key(candidate_title)
    authors, candidate_authors = _authors(book), _authors(candidate)
    if (
        not left
        or not right
        or not authors
        or S.EMPTY in authors | candidate_authors
        or _series_conflict(book_series, candidate_series)
        or _edition_conflict(book, candidate)
        or _names_series(book_series, right)
        or _names_series(candidate_series, left)
    ):
        return C.NONE
    shared = tuple(
        sorted(set(normalized_isbns(book.isbns)) & set(normalized_isbns(candidate.isbns)))
    )
    if authors == candidate_authors and _article_variant(left, right):
        return MatchResult(MatchKind.CONFIRMED, S.L1_ID_ARTICLE_REASON, shared)
    if shared and left == right and authors <= candidate_authors:
        return MatchResult(MatchKind.CONFIRMED, S.L1_ID_CONTRIBUTOR_REASON, shared)
    return C.NONE


def _strict_metadata_identity(book: BookRecord, candidate: MetadataCandidate) -> MatchResult:
    comparison = compare_books(book, candidate)
    if (
        comparison.kind != MatchKind.CONFLICTING
        and _open_library_work(candidate)
        and work_bibliography_compatible(book, candidate)
    ):
        return MatchResult(MatchKind.CONFIRMED, S.MATCH_REPAIR_WORK_REASON)
    return comparison


def compare_metadata_identity(book: BookRecord, candidate: MetadataCandidate) -> MatchResult:
    strict = _strict_metadata_identity(book, candidate)
    if strict.kind != MatchKind.CONFIRMED:
        relaxed = relaxed_metadata_identity(book, candidate)
        if relaxed is not C.NONE:
            return relaxed
    return strict


def _unique_confirmed(
    book: BookRecord,
    candidates: tuple[MetadataCandidate, ...],
    compare: Callable[[BookRecord, MetadataCandidate], MatchResult],
) -> MetadataCandidate | None:
    plausible: list[tuple[MetadataCandidate, MatchResult]] = []
    seen: set[str] = set()
    for candidate in candidates:
        serialized = candidate.model_dump_json()
        if serialized in seen:
            continue
        seen.add(serialized)
        comparison = compare(book, candidate)
        if comparison.kind != MatchKind.UNRELATED:
            plausible.append((candidate, comparison))
    if len(plausible) == C.ONE and plausible[C.ZERO][C.ONE].kind == MatchKind.CONFIRMED:
        return plausible[C.ZERO][C.ZERO]
    return C.NONE


def select_metadata_candidate(
    book: BookRecord, candidates: tuple[MetadataCandidate, ...]
) -> MetadataCandidate | None:
    selected = _unique_confirmed(book, candidates, _strict_metadata_identity)
    if selected is not C.NONE:
        return selected
    return _unique_confirmed(book, candidates, compare_metadata_identity)
