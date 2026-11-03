from __future__ import annotations

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.metadata import missing_fallback_fields
from bookystats.domain.models import (
    BookRecord,
    FieldState,
    MetadataCandidate,
    Observation,
    Source,
)


def _evidence() -> tuple[BookRecord, MetadataCandidate]:
    book = BookRecord(
        source=Source.GOODREADS,
        source_id=S.ORIGINAL_WATCHLIST_BOOK,
        title=S.MATILDA,
        authors=(S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
        isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
        url=S.TEST_OPEN_LIBRARY_BOOK_URL_HTTPS_WWW_GOODREADS_COM_BOOK_SHOW,
    )
    url = S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=S.OL45883W)
    candidate = MetadataCandidate(
        provider=Source.OPEN_LIBRARY,
        provider_id=S.OL45883W,
        work_id=S.OL45883W,
        title=book.title,
        authors=book.authors,
        isbns=book.isbns,
        url=url,
        observations=(
            Observation(
                field=S.DESCRIPTION,
                value=S.META_COVERAGE_TEST_DETAILS_TEXT,
                state=FieldState.PRESENT,
                scope=S.WORK,
                source_url=S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=S.OL45883W),
            ),
            Observation(
                field=S.GENRES,
                value=[S.ANALYTIC_CATEGORY_FANTASY],
                state=FieldState.PRESENT,
                scope=S.WORK,
                source_url=url,
            ),
        ),
    )
    return book, candidate


def test_fallback_requires_confirmed_public_evidence_and_recognized_genres() -> None:
    book, candidate = _evidence()
    assert missing_fallback_fields(book, (candidate,)) == ()
    conflicting = candidate.model_copy(update={S.TITLE: S.DIFFERENT_BOOK})
    assert missing_fallback_fields(book, (conflicting,)) == C.ENR_FALLBACK_FIELDS
    unknown_genre = candidate.observations[C.ONE].model_copy(
        update={S.VALUE: [S.ANALYTIC_CATEGORY_TEST_CATALOG_TAG]}
    )
    unrecognized = candidate.model_copy(
        update={S.OBSERVATIONS: (candidate.observations[C.ZERO], unknown_genre)}
    )
    assert missing_fallback_fields(book, (unrecognized,)) == (S.GENRES,)
    reader_scoped = candidate.model_copy(
        update={
            S.OBSERVATIONS: tuple(
                observation.model_copy(update={S.ENR_OBSERVATION_SCOPE: S.READER})
                for observation in candidate.observations
            )
        }
    )
    assert missing_fallback_fields(book, (reader_scoped,)) == C.ENR_FALLBACK_FIELDS
    empty_description = candidate.observations[C.ZERO].model_copy(
        update={S.VALUE: C.NONE, S.STATE: FieldState.EMPTY}
    )
    empty = candidate.model_copy(
        update={S.OBSERVATIONS: (empty_description, candidate.observations[C.ONE])}
    )
    assert missing_fallback_fields(book, (empty,)) == (S.DESCRIPTION,)


def test_existing_google_evidence_can_fill_open_library_description_gap() -> None:
    book, work = _evidence()
    work = work.model_copy(update={S.OBSERVATIONS: (work.observations[C.ONE],)})
    url = S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=S.TESTVOLUME_1)
    edition = MetadataCandidate(
        provider=Source.GOOGLE_BOOKS,
        provider_id=S.TESTVOLUME_1,
        edition_id=S.TESTVOLUME_1,
        title=book.title,
        authors=book.authors,
        isbns=book.isbns,
        url=url,
        observations=(
            Observation(
                field=S.DESCRIPTION,
                value=S.META_COVERAGE_TEST_DETAILS_TEXT,
                state=FieldState.PRESENT,
                scope=S.EDITION,
                source_url=url,
            ),
        ),
    )
    assert missing_fallback_fields(book, (work,)) == (S.DESCRIPTION,)
    assert missing_fallback_fields(book, (work, edition)) == ()
    unsafe = edition.model_copy(
        update={
            S.OBSERVATIONS: (
                edition.observations[C.ZERO].model_copy(
                    update={S.META_COVERAGE_SOURCE_URL: S.SOURCE_INVALID}
                ),
            )
        }
    )
    assert missing_fallback_fields(book, (work, unsafe)) == (S.DESCRIPTION,)


def test_primary_public_description_avoids_redundant_google_fallback() -> None:
    book, work = _evidence()
    work = work.model_copy(update={S.OBSERVATIONS: (work.observations[C.ONE],)})
    book = book.model_copy(
        update={
            S.SOURCE_ID: S.MQ_REPORT_TEST_GOODREADS_ID,
            S.URL: S.MQ_REPORT_TEST_GOODREADS_URL,
            S.OBSERVATIONS: (
                Observation(
                    field=S.DESCRIPTION,
                    value=S.META_COVERAGE_TEST_DETAILS_TEXT,
                    state=FieldState.PRESENT,
                    scope=S.WORK,
                    source_url=S.MQ_REPORT_TEST_CSV_ORIGIN,
                ),
                Observation(
                    field=S.GENRES,
                    value=[S.ANALYTIC_CATEGORY_FANTASY],
                    state=FieldState.PRESENT,
                    scope=S.WORK,
                    source_url=S.MQ_REPORT_TEST_CSV_ORIGIN,
                ),
            ),
        }
    )
    assert missing_fallback_fields(book, (work,)) == ()
    assert missing_fallback_fields(book, ()) == (S.GENRES,)
    assert missing_fallback_fields(
        book.model_copy(update={S.SOURCE_ID: S.SECOND_ORIGINAL_ID}), (work,)
    ) == (S.DESCRIPTION,)
    assert missing_fallback_fields(
        book.model_copy(update={S.SOURCE: Source.STORYGRAPH}), (work,)
    ) == (S.DESCRIPTION,)
    edition = book.observations[C.ZERO].model_copy(update={S.ENR_OBSERVATION_SCOPE: S.EDITION})
    assert missing_fallback_fields(
        book.model_copy(update={S.OBSERVATIONS: (edition,)}), (work,)
    ) == (S.DESCRIPTION,)
