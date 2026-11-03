from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.categories import analytical_categories
from bookystats.domain.matching import select_metadata_candidate
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate, Source


def _has_primary_description(book: BookRecord) -> bool:
    if book.source != Source.GOODREADS:
        return C.FALSE
    try:
        url = urlsplit(book.url)
        port = url.port
    except ValueError:
        return C.FALSE
    identity = C.BROWSER_BOOK_URL.fullmatch(url.path)
    if (
        url.scheme != S.HTTPS
        or url.hostname not in (S.WWW_GOODREADS_COM, S.GOODREADS_COM)
        or url.username
        or url.password
        or port not in (C.NONE, C.MODELS_ACCOUNT_VALID_PROFILE)
        or url.query
        or url.fragment
        or identity is C.NONE
        or identity[C.ONE] != book.source_id
    ):
        return C.FALSE
    return any(
        item.field == S.DESCRIPTION
        and item.scope == S.WORK
        and item.state == FieldState.PRESENT
        and isinstance(item.value, str)
        and bool(item.value.strip())
        for item in book.observations
    )


def missing_fallback_fields(
    book: BookRecord,
    candidates: Iterable[MetadataCandidate],
    *,
    work_candidates: Iterable[MetadataCandidate] = (),
) -> tuple[str, ...]:
    known: set[str] = set()
    if _has_primary_description(book):
        known.add(S.DESCRIPTION)
    validated = tuple(
        candidate
        for candidate in candidates
        if select_metadata_candidate(book, (candidate,)) is not C.NONE
    )
    validated += tuple(
        candidate for candidate in work_candidates if candidate.provider == Source.OPEN_LIBRARY
    )
    for candidate in validated:
        if candidate.provider not in C.RAW_METADATA_SOURCES:
            continue
        work = candidate.provider == Source.OPEN_LIBRARY
        expected = (
            S.OPEN_LIBRARY_WORK_URL_TEMPLATE if work else S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE
        ).format(v0=candidate.provider_id)
        if candidate.url != expected:
            continue
        origins = {expected}
        if work:
            origins.add(S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=candidate.provider_id))
        for observation in candidate.observations:
            if (
                observation.state != FieldState.PRESENT
                or observation.scope != (S.WORK if work else S.EDITION)
                or observation.source_url not in origins
            ):
                continue
            if (
                observation.field == S.DESCRIPTION
                and isinstance(observation.value, str)
                and observation.value.strip()
            ):
                known.add(S.DESCRIPTION)
            elif (
                observation.field == S.GENRES
                and isinstance(observation.value, list)
                and analytical_categories(
                    value for value in observation.value if isinstance(value, str)
                )
            ):
                known.add(S.GENRES)
    return tuple(field for field in C.ENR_FALLBACK_FIELDS if field not in known)
