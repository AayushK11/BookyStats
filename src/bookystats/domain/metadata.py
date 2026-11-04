from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.categories import analytical_categories
from bookystats.domain.matching import select_metadata_candidate
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate, Observation, Source


def substantive_description(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not value.rstrip().endswith(C.METADATA_PREVIEW_ENDINGS)
    )


def public_work_descriptor(source: str, source_id: str, observation: Observation) -> bool:
    # These public descriptors may follow a confirmed work link without relabeling the observation.
    if observation.field not in C.ENR_FALLBACK_FIELDS:
        return C.FALSE
    if source == Source.OPEN_LIBRARY.value:
        return observation.scope == S.WORK and observation.source_url in (
            S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=source_id),
            S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=source_id),
        )
    if source == Source.GOOGLE_BOOKS.value:
        return observation.scope in (
            S.WORK,
            S.EDITION,
        ) and observation.source_url == S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=source_id)
    if source == Source.WIKIDATA.value:
        return (
            observation.field == S.GENRES
            and observation.scope == S.WORK
            and C.WIKIDATA_ENTITY_ID.fullmatch(source_id) is not C.NONE
            and observation.source_url == S.WIKIDATA_WORK_URL.format(v0=source_id)
        )
    return C.FALSE


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
        and substantive_description(item.value)
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
        expected = (
            S.OPEN_LIBRARY_WORK_URL_TEMPLATE
            if candidate.provider == Source.OPEN_LIBRARY
            else S.WIKIDATA_WORK_URL
            if candidate.provider == Source.WIKIDATA
            else S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE
        ).format(v0=candidate.provider_id)
        if candidate.url != expected:
            continue
        for observation in candidate.observations:
            if observation.state != FieldState.PRESENT or not public_work_descriptor(
                candidate.provider.value, candidate.provider_id, observation
            ):
                continue
            if observation.field == S.DESCRIPTION and substantive_description(observation.value):
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
