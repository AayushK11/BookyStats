from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.identifiers import normalize_isbn
from bookystats.domain.matching import (
    MatchKind,
    compare_books,
    compare_metadata_identity,
    relaxed_metadata_identity,
    select_metadata_candidate,
    work_query_title,
)
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate, Observation, Source


def book(**changes: object) -> BookRecord:
    return BookRecord.model_validate(
        {
            S.SOURCE: Source.GOODREADS,
            S.SOURCE_ID: S.L1_ID_TEST_SOURCE_ID,
            S.TITLE: S.L1_ID_TEST_BARE_TITLE,
            S.AUTHORS: (S.L1_ID_TEST_AUTHOR,),
            S.URL: S.L1_ID_TEST_BOOK_URL,
            S.ISBNS: (S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
        }
        | changes
    )


def candidate(**changes: object) -> MetadataCandidate:
    return MetadataCandidate.model_validate(
        {
            S.PROVIDER: Source.OPEN_LIBRARY,
            S.PROVIDER_ID: S.L1_ID_TEST_WORK_ID,
            S.WORK_ID: S.L1_ID_TEST_WORK_ID,
            S.TITLE: S.L1_ID_TEST_ARTICLE_TITLE,
            S.AUTHORS: (S.L1_ID_TEST_AUTHOR,),
            S.ISBNS: (S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
            S.URL: S.L1_ID_TEST_WORK_URL,
        }
        | changes
    )


@pytest.mark.parametrize(S.L1_ID_ARTICLE_PARAMETERS, C.L1_ID_ARTICLE_CASES)
def test_article_only_variants_with_identical_authors_are_confirmed(
    book_title: str, candidate_title: str, shared_isbn: bool
) -> None:
    isbns = (S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,) if shared_isbn else (S.L1_ID_TEST_OTHER_ISBN,)
    source, found = book(title=book_title), candidate(title=candidate_title, isbns=isbns)
    assert compare_books(source, found).kind != MatchKind.CONFIRMED
    relaxed = relaxed_metadata_identity(source, found)
    assert relaxed is not C.NONE
    assert relaxed.kind == MatchKind.CONFIRMED and relaxed.reason == S.L1_ID_ARTICLE_REASON
    assert compare_metadata_identity(source, found) == relaxed
    assert select_metadata_candidate(source, (found,)) == found


def test_contributor_superset_with_a_shared_isbn_is_confirmed() -> None:
    source, found = book(), candidate(**C.L1_ID_CONTRIBUTOR_CANDIDATE)
    assert compare_books(source, found).kind == MatchKind.LIKELY
    relaxed = relaxed_metadata_identity(source, found)
    assert relaxed is not C.NONE
    assert relaxed.reason == S.L1_ID_CONTRIBUTOR_REASON
    assert relaxed.identifiers == (normalize_isbn(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT),)
    assert select_metadata_candidate(source, (found,)) == found


@pytest.mark.parametrize(S.L1_ID_VETO_PARAMETERS, C.L1_ID_VETO_CASES)
def test_relaxation_vetoes_keep_the_strict_outcome(
    book_changes: dict[str, object], candidate_changes: dict[str, object]
) -> None:
    source, found = book(**book_changes), candidate(**candidate_changes)
    assert relaxed_metadata_identity(source, found) is C.NONE
    assert compare_metadata_identity(source, found).kind != MatchKind.CONFIRMED
    assert select_metadata_candidate(source, (found,)) is C.NONE


def test_relaxations_apply_only_to_open_library_work_records() -> None:
    edition_fact = Observation(
        field=S.LANGUAGE,
        value=S.EN,
        state=FieldState.PRESENT,
        scope=S.EDITION,
        source_url=S.L1_ID_TEST_WORK_URL,
    )
    assert relaxed_metadata_identity(book(), candidate()) is not C.NONE
    for variant in (
        candidate(provider=Source.GOOGLE_BOOKS),
        candidate(edition_id=S.L1_ID_TEST_WORK_ID),
        candidate(work_id=S.L1_ID_TEST_OTHER_WORK_ID),
        candidate(observations=(edition_fact,)),
    ):
        assert relaxed_metadata_identity(book(), variant) is C.NONE


def test_two_relaxed_candidates_remain_ambiguous() -> None:
    other = candidate(
        provider_id=S.L1_ID_TEST_OTHER_WORK_ID,
        work_id=S.L1_ID_TEST_OTHER_WORK_ID,
        title=S.L1_ID_TEST_INDEFINITE_TITLE,
    )
    assert select_metadata_candidate(book(), (candidate(), other)) is C.NONE


def test_exact_candidate_and_shared_isbn_article_variant_remain_ambiguous() -> None:
    exact = candidate(title=S.L1_ID_TEST_BARE_TITLE)
    variant = candidate(provider_id=S.L1_ID_TEST_OTHER_WORK_ID, work_id=S.L1_ID_TEST_OTHER_WORK_ID)
    assert select_metadata_candidate(book(), (exact, variant)) is C.NONE


def test_existing_strict_selection_is_unchanged_by_an_unanchored_article_variant() -> None:
    exact = candidate(title=S.L1_ID_TEST_BARE_TITLE)
    variant = candidate(
        provider_id=S.L1_ID_TEST_OTHER_WORK_ID,
        work_id=S.L1_ID_TEST_OTHER_WORK_ID,
        isbns=(S.L1_ID_TEST_OTHER_ISBN,),
    )
    assert select_metadata_candidate(book(), (exact, variant)) == exact


def test_unique_relaxed_candidate_ignores_unrelated_candidates() -> None:
    unrelated = candidate(
        provider_id=S.L1_ID_TEST_OTHER_WORK_ID,
        work_id=S.L1_ID_TEST_OTHER_WORK_ID,
        title=S.L1_ID_TEST_UNRELATED_TITLE,
        authors=(S.L1_ID_TEST_OTHER_AUTHOR,),
        isbns=(),
    )
    assert select_metadata_candidate(book(), (unrelated, candidate())) == candidate()


@pytest.mark.parametrize(S.L1_ID_QUERY_PARAMETERS, C.L1_ID_QUERY_CASES)
def test_work_query_title_drops_only_a_parsed_series_suffix(title: str, expected: str) -> None:
    assert work_query_title(title) == expected
