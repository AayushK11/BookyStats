from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.identifiers import normalize_isbn
from bookystats.domain.matching import (
    MatchKind,
    candidate_title_author_key,
    compare_books,
    compare_work_identity,
    select_metadata_candidate,
)
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate, Observation, Source


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


def test_wikidata_confirms_only_canonical_work_identity_not_an_edition() -> None:
    reference = S.WIKIDATA_WORK_URL.format(v0=S.WIKIDATA_TEST_ID)
    work = candidate(
        provider=Source.WIKIDATA,
        provider_id=S.WIKIDATA_TEST_ID,
        work_id=S.WIKIDATA_TEST_ID,
        edition_id=C.NONE,
        isbns=(),
        url=reference,
        observations=(
            Observation(
                field=S.GENRES,
                value=[S.ANALYTIC_CATEGORY_FANTASY],
                state=FieldState.PRESENT,
                scope=S.WORK,
                source_url=reference,
            ),
        ),
    )
    assert select_metadata_candidate(book(isbns=()), (work,)) == work
    assert compare_books(book(isbns=()), work).kind == MatchKind.LIKELY
    edition = work.model_copy(update={S.EDITION_ID: S.VOLUME_ONE})
    assert select_metadata_candidate(book(isbns=()), (edition,)) is C.NONE
    other_author = work.model_copy(
        update={S.AUTHORS: (S.TEST_MATCHING_METADATA_REQUIRES_CANDIDATE_AUTHORS_DIFFERENT_AUTHOR,)}
    )
    assert select_metadata_candidate(book(isbns=()), (other_author,)) is C.NONE
    noncanonical = work.model_copy(update={S.URL: S.TEST_RAW_FILE})
    assert select_metadata_candidate(book(isbns=()), (noncanonical,)) is C.NONE


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


@pytest.mark.parametrize(
    S.MATCH_UPGRADE_TEST_NORMALIZED_PARAMETERS, C.MATCH_UPGRADE_TEST_NORMALIZATIONS
)
def test_real_structural_title_and_author_variants_require_a_shared_isbn(
    left_title: str, right_title: str, left_author: str, right_author: str
) -> None:
    left = book(title=left_title, authors=(left_author,))
    right = book(title=right_title, authors=(right_author,))
    assert compare_books(left, right).kind == MatchKind.CONFIRMED
    assert compare_books(left, right.model_copy(update={S.ISBNS: ()})).kind == MatchKind.LIKELY
    assert candidate_title_author_key(left) == candidate_title_author_key(right)


@pytest.mark.parametrize(S.MATCH_UPGRADE_TEST_TITLE_PARAMETERS, C.MATCH_UPGRADE_TEST_TITLE_HAZARDS)
def test_series_numbers_parts_and_subtitles_are_not_discarded_as_identity_proof(
    title: str, kind: MatchKind
) -> None:
    left = book(title=S.MATCH_UPGRADE_TEST_SERIES_TITLE)
    assert compare_books(left, book(title=title)).kind == kind


def test_incompatible_subtitles_and_author_homonyms_never_confirm() -> None:
    left = book(title=S.MATCH_UPGRADE_TEST_SUBTITLE)
    other = book(title=S.MATCH_UPGRADE_TEST_OTHER_SUBTITLE)
    assert candidate_title_author_key(left) == candidate_title_author_key(other)
    assert compare_books(left, other).kind == MatchKind.CONFLICTING
    assert compare_books(left.model_copy(update={S.ISBNS: ()}), other).kind == MatchKind.UNRELATED
    assert (
        compare_books(
            left,
            other.model_copy(
                update={
                    S.TITLE: left.title,
                    S.AUTHORS: (S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,),
                }
            ),
        ).kind
        == MatchKind.CONFLICTING
    )


def test_missing_coauthor_is_a_candidate_not_an_automatic_edition_link() -> None:
    left = book(
        authors=(
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
        )
    )
    assert compare_books(left, book()).kind == MatchKind.LIKELY
    assert compare_books(left, book()).reason == S.MATCH_UPGRADE_AUTHOR_CANDIDATE


def test_author_normalization_does_not_remove_non_latin_identity_marks() -> None:
    left = book(authors=(S.MATCH_UPGRADE_TEST_VOICED_AUTHOR,))
    right = book(authors=(S.MATCH_UPGRADE_TEST_UNVOICED_AUTHOR,))
    assert compare_books(left, right).kind == MatchKind.CONFLICTING


def test_contradictory_provider_work_ids_remain_ambiguous_after_normalization() -> None:
    first = candidate(
        title=S.MATCH_UPGRADE_TEST_SERIES_TITLE,
        authors=(S.MATCH_UPGRADE_TEST_SPACED_AUTHOR,),
        work_id=S.FIRST,
    )
    contradictory = first.model_copy(update={S.WORK_ID: S.SECOND})
    source = book(title=S.MATCH_UPGRADE_TEST_TITLE, authors=(S.MATCH_UPGRADE_TEST_AUTHOR,))
    assert select_metadata_candidate(source, (first,)) == first
    assert select_metadata_candidate(source, (first, contradictory)) is C.NONE


def test_structural_title_normalization_does_not_override_edition_conflicts() -> None:
    left = book(title=S.MATCH_UPGRADE_TEST_TITLE, language=S.EN)
    right = book(title=S.MATCH_UPGRADE_TEST_SERIES_TITLE, language=S.FR)
    assert compare_books(left, right).kind == MatchKind.CONFLICTING
    assert (
        compare_books(
            left,
            right.model_copy(
                update={
                    S.LANGUAGE: S.EN,
                    S.ISBNS: (S.MATCH_UPGRADE_TEST_ALTERNATE_ISBN,),
                }
            ),
        ).kind
        == MatchKind.LIKELY
    )


@pytest.mark.parametrize(S.MATCH_UPGRADE_TEST_ISBN_PARAMETERS, C.MATCH_UPGRADE_TEST_ISBN_LABELS)
def test_isbn_labels_are_anchored_and_still_require_valid_checksums(
    value: str, expected: str | None
) -> None:
    assert normalize_isbn(value) == expected


def test_contradictory_observed_edition_fact_blocks_an_otherwise_confirmed_isbn() -> None:
    source = book(language=S.EN)
    contradictory = source.model_copy(
        update={
            S.OBSERVATIONS: (
                Observation(
                    field=S.LANGUAGE,
                    value=S.FR,
                    state=FieldState.PRESENT,
                    scope=S.EDITION,
                    source_url=source.url,
                ),
            )
        }
    )
    assert compare_books(source, contradictory).kind == MatchKind.CONFLICTING


@pytest.mark.parametrize(S.MATCH_REPAIR_TEST_PARAMETERS, C.MATCH_REPAIR_TEST_COMPATIBLE_TITLES)
def test_catalog_series_and_volume_spelling_require_identifier_corroboration(
    left_title: str, right_title: str
) -> None:
    left, right = book(title=left_title), book(title=right_title)
    assert compare_books(left, right).kind == MatchKind.CONFIRMED
    assert compare_books(left.model_copy(update={S.ISBNS: ()}), right).kind == MatchKind.LIKELY


@pytest.mark.parametrize(S.TITLE, C.MATCH_REPAIR_TEST_TITLE_HAZARDS)
def test_series_normalization_preserves_ranges_malformed_annotations_and_conflicts(
    title: str,
) -> None:
    assert (
        compare_books(book(title=S.MATCH_REPAIR_TEST_SERIES), book(title=title)).kind
        == MatchKind.CONFLICTING
    )


def test_volume_spelling_does_not_discard_discriminating_numbers() -> None:
    assert (
        compare_books(
            book(title=S.MATCH_REPAIR_TEST_VOLUME_WORD),
            book(title=S.MATCH_REPAIR_TEST_VOLUME_OTHER),
        ).kind
        == MatchKind.CONFLICTING
    )


def test_structurally_normalized_metadata_remains_ambiguous_with_multiple_work_ids() -> None:
    source = book(title=S.MATCH_REPAIR_TEST_SERIES)
    first = candidate(title=S.MATCH_REPAIR_TEST_PLAIN, work_id=S.FIRST)
    second = first.model_copy(update={S.WORK_ID: S.SECOND})
    assert select_metadata_candidate(source, (first,)) == first
    assert select_metadata_candidate(source, (first, second)) is C.NONE


def test_shared_isbn_corroborates_work_with_omitted_coauthor_but_not_edition() -> None:
    left = book(
        authors=(
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
        )
    )
    right = book()
    assert compare_work_identity(left, right).kind == MatchKind.CONFIRMED
    assert compare_books(left, right).kind == MatchKind.LIKELY
    assert (
        compare_work_identity(left, right.model_copy(update={S.ISBNS: ()})).kind
        == MatchKind.UNRELATED
    )
    assert (
        compare_work_identity(
            left,
            right.model_copy(
                update={
                    S.AUTHORS: (S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,)
                }
            ),
        ).kind
        == MatchKind.UNRELATED
    )


def test_collection_annotations_require_shared_isbn_and_preserve_range_conflicts() -> None:
    collection = book(title=S.MATCH_REPAIR_TEST_COLLECTION)
    assert compare_work_identity(collection, book()).kind == MatchKind.CONFIRMED
    assert compare_books(collection, book()).kind == MatchKind.CONFLICTING
    assert compare_work_identity(collection, book(isbns=())).kind == MatchKind.UNRELATED
    assert (
        compare_work_identity(collection, book(title=S.MATCH_REPAIR_TEST_OTHER_COLLECTION)).kind
        == MatchKind.UNRELATED
    )
    assert (
        compare_work_identity(book(title=S.MATCH_REPAIR_TEST_MULTI_VOLUME), book()).kind
        == MatchKind.CONFIRMED
    )


def test_explicit_unicode_numbered_volume_preserves_number_and_edition_uncertainty() -> None:
    left = book(title=S.MATCH_REPAIR_TEST_UNICODE_VOLUME)
    right = book(
        title=S.MATCH_REPAIR_TEST_NUMBERED_VOLUME,
        isbns=(S.MATCH_UPGRADE_TEST_ALTERNATE_ISBN,),
    )
    assert compare_work_identity(left, right).kind == MatchKind.CONFIRMED
    assert compare_books(left, right).kind != MatchKind.CONFIRMED
    assert (
        compare_work_identity(
            left, right.model_copy(update={S.TITLE: S.MATCH_REPAIR_TEST_OTHER_VOLUME})
        ).kind
        == MatchKind.UNRELATED
    )
    assert (
        compare_work_identity(left, right.model_copy(update={S.ISBNS: ()})).kind
        == MatchKind.UNRELATED
    )
    assert (
        compare_work_identity(
            book(title=S.MATCH_REPAIR_TEST_MULTIPLICATION_VOLUME),
            book(title=S.MATCH_REPAIR_TEST_LETTER_VOLUME),
        ).kind
        == MatchKind.CONFIRMED
    )


def test_latin_title_accent_variant_requires_shared_validated_isbn() -> None:
    left, right = book(title=S.MATCH_REPAIR_TEST_ACCENT_TITLE), book()
    assert compare_work_identity(left, right).kind == MatchKind.CONFIRMED
    assert (
        compare_work_identity(left, right.model_copy(update={S.ISBNS: ()})).kind
        == MatchKind.UNRELATED
    )
