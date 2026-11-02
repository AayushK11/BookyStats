from __future__ import annotations

import unicodedata

from bookystats import constants as C
from bookystats import strings as S
from bookystats.constants import MatchKind as MatchKind
from bookystats.domain.identifiers import normalized_isbns, normalized_text
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate

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


def _title_parts(title: str) -> tuple[str, str]:
    annotation = C.MATCH_UPGRADE_SERIES_PATTERN.search(title)
    series = S.EMPTY
    if annotation:
        series = (
            normalized_text(annotation[S.MATCH_UPGRADE_SERIES_GROUP])
            + S.MATCHING_TITLE_AUTHOR_KEY_TEXT
            + annotation[S.MATCH_UPGRADE_NUMBER_GROUP]
        )
        title = title[: annotation.start()]
    if article := C.MATCH_UPGRADE_ARTICLE_PATTERN.fullmatch(title.strip()):
        title = (
            article[S.MATCH_UPGRADE_ARTICLE_GROUP] + S.SPACE + article[S.MATCH_UPGRADE_TITLE_GROUP]
        )
    return title.strip(), series


def _author_key(author: str) -> str:
    decomposed = unicodedata.normalize(S.MATCH_UPGRADE_UNICODE_FORM, author)
    folded: list[str] = []
    latin_base = C.FALSE
    for char in decomposed:
        combining = unicodedata.category(char) == S.MATCH_UPGRADE_COMBINING_CATEGORY
        if combining and latin_base:
            continue
        folded.append(char)
        if not combining:
            latin_base = unicodedata.name(char, S.EMPTY).startswith(S.MATCH_UPGRADE_LATIN_PREFIX)
    tokens = normalized_text(unicodedata.normalize(S.NFKC, S.EMPTY.join(folded))).split()
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
    title = normalized_text(title.split(S.COLON, C.ONE)[C.ZERO])
    authors = sorted(_authors(book))
    if not title or not authors or any(not author for author in authors):
        return S.EMPTY
    return (
        title + S.MATCHING_TITLE_AUTHOR_KEY_TEXT + S.MATCHING_TITLE_AUTHOR_KEY_TEXT_2.join(authors)
    )


def work_bibliography_compatible(left: Matchable, right: Matchable) -> bool:
    left_title, left_series = _title_parts(left.title)
    right_title, right_series = _title_parts(right.title)
    title = normalized_text(left_title)
    authors = _authors(left)
    return (
        bool(title)
        and title == normalized_text(right_title)
        and bool(authors)
        and S.EMPTY not in authors
        and authors == _authors(right)
        and not (left_series and right_series and left_series != right_series)
    )


def _compatible_subtitle(left: str, right: str) -> bool:
    left_parts, right_parts = left.split(S.COLON, C.ONE), right.split(S.COLON, C.ONE)
    return len(left_parts) != len(right_parts) and normalized_text(
        left_parts[C.ZERO]
    ) == normalized_text(right_parts[C.ZERO])


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
    left_title, right_title = normalized_text(left_full), normalized_text(right_full)
    left_authors, right_authors = _authors(left), _authors(right)
    authors_agree = (
        bool(left_authors) and left_authors == right_authors and S.EMPTY not in left_authors
    )
    series_conflict = bool(left_series and right_series and left_series != right_series)
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


def select_metadata_candidate(
    book: BookRecord, candidates: tuple[MetadataCandidate, ...]
) -> MetadataCandidate | None:
    plausible: list[tuple[MetadataCandidate, MatchResult]] = []
    seen: set[str] = set()
    for candidate in candidates:
        serialized = candidate.model_dump_json()
        if serialized in seen:
            continue
        seen.add(serialized)
        comparison = compare_books(book, candidate)
        if comparison.kind != MatchKind.UNRELATED:
            plausible.append((candidate, comparison))
    if len(plausible) == C.ONE and plausible[C.ZERO][C.ONE].kind == MatchKind.CONFIRMED:
        return plausible[C.ZERO][C.ZERO]
    return C.NONE
