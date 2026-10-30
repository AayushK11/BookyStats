from __future__ import annotations

from bookystats import constants as C
from bookystats import strings as S
from bookystats.constants import MatchKind as MatchKind
from bookystats.identifiers import normalized_isbns, normalized_text
from bookystats.models import BookRecord, FieldState, MetadataCandidate

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


def _edition_conflict(left: Matchable, right: Matchable) -> bool:
    for field in (S.LANGUAGE, S.EDITION_FORMAT):
        values: list[set[str]] = []
        for book in (left, right):
            facts = {
                normalized_text(item.value)
                for item in book.observations
                if item.field == field
                and item.scope == S.EDITION
                and (item.state == FieldState.PRESENT)
                and isinstance(item.value, str)
                and item.value.strip()
            }
            if isinstance(book, BookRecord) and (value := getattr(book, field)):
                facts.add(normalized_text(value))
            values.append(facts)
        if any(len(facts) > C.ONE for facts in values):
            return C.TRUE
        if values[C.ZERO] and values[C.ONE] and (values[C.ZERO] != values[C.ONE]):
            return C.TRUE
    return C.FALSE


def compare_books(left: Matchable, right: Matchable) -> MatchResult:
    shared = tuple(sorted(set(normalized_isbns(left.isbns)) & set(normalized_isbns(right.isbns))))
    left_title, right_title = (normalized_text(left.title), normalized_text(right.title))
    left_key, right_key = (title_author_key(left), title_author_key(right))
    if shared:
        if left_title and right_title and (left_title != right_title):
            return MatchResult(
                MatchKind.CONFLICTING,
                S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_FULL_TITLES_DIFFER,
                shared,
            )
        left_authors = {normalized_text(author) for author in left.authors if author.strip()}
        right_authors = {normalized_text(author) for author in right.authors if author.strip()}
        if left_authors and right_authors and (left_authors != right_authors):
            return MatchResult(
                MatchKind.CONFLICTING,
                S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_AUTHOR_SETS_DIFFER,
                shared,
            )
        if _edition_conflict(left, right):
            return MatchResult(
                MatchKind.CONFLICTING,
                S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_EDITION_LANGUAGE_OR_FORMAT,
                shared,
            )
        if left_key and left_key == right_key:
            return MatchResult(
                MatchKind.CONFIRMED,
                S.MATCHING_COMPARE_BOOKS_VALIDATED_ISBN_FULL_TITLE_AND_AUTHORS_AGREE,
                shared,
            )
        return MatchResult(
            MatchKind.LIKELY,
            S.MATCHING_COMPARE_BOOKS_SHARED_ISBN_LACKS_SUFFICIENT_TITLE_AND_AUTHOR,
            shared,
        )
    if left_key and left_key == right_key:
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
