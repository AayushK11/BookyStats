from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.matching import MatchKind, compare_books, select_metadata_candidate
from bookystats.models import BookRecord, FieldState, MetadataCandidate, Observation, Source


def book(**changes: object) -> BookRecord:
    return BookRecord.model_validate(
        {
            S.SOURCE: Source.STORYGRAPH,
            S.SOURCE_ID: S.STORYGRAPH_RECORD,
            S.TITLE: S.MATILDA,
            S.AUTHORS: (S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
            S.URL: S.TEST_MATCHING_BOOK_HTTPS_APP_COM_BOOKS_STORYGRAPH_RECORD,
            S.ISBNS: (S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,),
        }
        | changes
    )


def candidate(**changes: object) -> MetadataCandidate:
    return MetadataCandidate.model_validate(
        {
            S.PROVIDER: Source.GOOGLE_BOOKS,
            S.PROVIDER_ID: S.VOLUME_ONE,
            S.EDITION_ID: S.VOLUME_ONE,
            S.TITLE: S.MATILDA,
            S.AUTHORS: (S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
            S.ISBNS: (S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
            S.URL: S.TEST_MATCHING_CANDIDATE_HTTPS_BOOKS_GOOGLE_COM_BOOKS_ID_VOLUME,
        }
        | changes
    )


def test_isbn10_and_isbn13_corroborate_without_using_source_ids() -> None:
    match = compare_books(
        book(),
        book(
            source_id=S.ANOTHER_ID,
            isbns=(S.TEST_ISBN10_AND_ISBN13_CORROBORATE_SOURCE_IDS_MATCH_ISBNS_TEXT,),
        ),
    )
    assert match.kind == MatchKind.CONFIRMED
    assert match.identifiers == (
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,
    )


@pytest.mark.parametrize(
    S.CHANGES,
    [
        {S.AUTHORS: (S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,)},
        {S.TITLE: S.TEST_MATCHING_SHARED_ISBN_WITH_MATILDA_AND_OTHER_STORIES_OMNIBU},
        {S.TITLE: S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_MATILDA_PART_TWO},
        {S.LANGUAGE: S.FR},
        {S.EDITION_FORMAT: S.AUDIOBOOK},
    ],
)
def test_shared_isbn_with_conflicting_bibliography_does_not_confirm(
    changes: dict[str, object],
) -> None:
    left = book(language=S.EN, edition_format=S.PAPERBACK)
    right = book(**{S.LANGUAGE: S.EN, S.EDITION_FORMAT: S.PAPERBACK} | changes)
    assert compare_books(left, right).kind == MatchKind.CONFLICTING


@pytest.mark.parametrize(
    S.ISBNS,
    [
        (),
        (S.TEST_MATCHING_TITLE_AUTHOR_ONLY_AND_ARE_LIKELY_NOT_CONFIRMED_TEXT,),
        (S.STORYGRAPH_UUID,),
        (S.TEST_GOODREADS_INVALID_ISBN_IS_NOT_PROMOTED_TO_AN_IDENTIFIER_TEXT_2,),
    ],
)
def test_title_author_only_and_invalid_identifiers_are_likely_not_confirmed(
    isbns: tuple[str, ...],
) -> None:
    left = book(
        source_id=S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,
        isbns=isbns,
    )
    right = book(
        source=Source.GOODREADS,
        source_id=S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,
        isbns=isbns,
    )
    assert compare_books(left, right).kind == MatchKind.LIKELY


def test_absent_authors_cannot_corroborate_a_valid_isbn() -> None:
    assert compare_books(book(), book(authors=())).kind == MatchKind.LIKELY


def test_full_title_is_not_stripped_to_merge_parts() -> None:
    assert (
        compare_books(
            book(
                isbns=(), title=S.TEST_MATCHING_FULL_TITLE_IS_NOT_MERGE_PARTS_TITLE_MATILDA_PART_ONE
            ),
            book(
                isbns=(), title=S.TEST_MATCHING_FULL_TITLE_IS_NOT_MERGE_PARTS_TITLE_MATILDA_PART_TWO
            ),
        ).kind
        == MatchKind.UNRELATED
    )


def test_normalized_full_titles_and_author_order_can_corroborate() -> None:
    left = book(
        title=S.MATILDA_2,
        authors=(
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
        ),
    )
    right = book(
        title=S.TEST_NORMALIZED_FULL_TITLES_AND_CAN_CORROBORATE_RIGHT_TITLE_MATILDA,
        authors=(
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
        ),
    )
    assert compare_books(left, right).kind == MatchKind.CONFIRMED


def test_metadata_requires_one_unambiguous_confirmed_candidate() -> None:
    first = candidate()
    second = candidate(provider_id=S.OTHER_EDITION, edition_id=S.OTHER_EDITION)
    assert select_metadata_candidate(book(), (first,)) == first
    assert select_metadata_candidate(book(), (first, first)) == first
    assert select_metadata_candidate(book(), (first, second)) is C.NONE
    assert select_metadata_candidate(book(isbns=()), (first,)) is C.NONE
    assert (
        select_metadata_candidate(
            book(),
            (
                first,
                candidate(
                    authors=(S.TEST_MATCHING_METADATA_REQUIRES_CANDIDATE_AUTHORS_DIFFERENT_AUTHOR,)
                ),
            ),
        )
        is C.NONE
    )


def test_unrelated_search_hits_do_not_defeat_exact_identifier_evidence() -> None:
    first = candidate()
    unrelated = candidate(
        title=S.TEST_UNRELATED_SEARCH_HITS_DO_NOT_UNRELATED_TITLE_AN_UNRELATED_WORK,
        isbns=(S.TEST_UNRELATED_SEARCH_HITS_DO_EVIDENCE_UNRELATED_ISBNS_TEXT,),
    )
    assert select_metadata_candidate(book(), (unrelated, first)) == first


def test_provider_edition_language_must_not_conflict_with_known_source_edition() -> None:
    translated = candidate(
        observations=(
            Observation(
                field=S.LANGUAGE,
                value=S.FR,
                state=FieldState.PRESENT,
                scope=S.EDITION,
                source_url=S.TEST_MATCHING_CANDIDATE_HTTPS_BOOKS_GOOGLE_COM_BOOKS_ID_VOLUME,
            ),
        )
    )
    assert compare_books(book(language=S.EN), translated).kind == MatchKind.CONFLICTING
    assert select_metadata_candidate(book(language=S.EN), (translated,)) is C.NONE
