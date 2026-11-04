from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.metadata.wikidata import WikidataProvider
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.interfaces import HttpResponse
from bookystats.domain.matching import select_metadata_candidate
from bookystats.domain.models import BookRecord, FieldState, MetadataCandidate, Source, SyncState
from bookystats.persistence.cache import MetadataCache
from tests.support.paths import fixture_path


class FakeHttp:
    def __init__(self, *payloads: object, status: int = C.HTTP_OK) -> None:
        self.payloads = list(payloads)
        self.status = status
        self.calls: list[dict[str, str]] = []

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        assert url == S.WD_ENDPOINT
        self.calls.append(dict(params or {}))
        assert self.payloads
        payload = self.payloads.pop(C.ZERO)
        if isinstance(payload, ConnectorError):
            raise payload
        return HttpResponse(
            url=url,
            status_code=self.status,
            headers={},
            body=json.dumps(payload).encode(),
        )


@pytest.fixture
def payload() -> dict[str, Any]:
    return json.loads(
        fixture_path(S.WD_TEST_FIXTURE, S.WD_TEST_WORK_FILE).read_text(encoding=S.UTF_8)
    )


@pytest.fixture
def book() -> BookRecord:
    return BookRecord(
        source=Source.GOODREADS,
        source_id=S.WD_TEST_PRIVATE_MARKER,
        title=S.MATILDA,
        authors=(S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
        url=S.TEST_OPEN_LIBRARY_BOOK_URL_HTTPS_WWW_GOODREADS_COM_BOOK_SHOW,
    )


def _http(payload: dict[str, Any]) -> FakeHttp:
    return FakeHttp(
        {S.WD_SEARCH: payload[S.WD_SEARCH]},
        {S.WD_ENTITIES: payload[S.WD_ENTITIES]},
        payload[S.WD_TEST_RELATED],
    )


def _entity(payload: dict[str, Any]) -> dict[str, Any]:
    return payload[S.WD_ENTITIES][S.WD_TEST_WORK_ID]


def _claim(payload: dict[str, Any], prop: str) -> dict[str, Any]:
    return _entity(payload)[S.WD_CLAIMS][prop][C.ZERO]


def _value(payload: dict[str, Any], prop: str) -> Any:
    return _claim(payload, prop)[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE]


def test_work_identity_and_correctly_paired_series(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = _http(payload)
    result = WikidataProvider(http).lookup(book)
    assert result.state == SyncState.COMPLETE
    candidate = result.candidates[C.ZERO]
    assert candidate.provider == Source.WIKIDATA
    assert candidate.provider_id == candidate.work_id == S.WD_TEST_WORK_ID
    assert candidate.edition_id is C.NONE and not candidate.isbns
    assert all(
        item.scope == S.WORK and item.source_url == candidate.url for item in candidate.observations
    )
    facts = {item.field: item for item in candidate.observations}
    assert facts[S.WD_SERIES_MEMBERSHIPS].value == [
        {
            S.WD_SERIES_ID: S.WD_NOVEL_SERIES,
            S.WD_NAME: S.WD_TEST_SECOND_SERIES,
            S.WD_POSITION: S.WD_TEST_OTHER_POSITION,
        },
        {
            S.WD_SERIES_ID: S.WD_BOOK_SERIES,
            S.WD_NAME: S.WD_TEST_FIRST_SERIES,
            S.WD_POSITION: S.WD_TEST_POSITION,
        },
    ]
    assert facts[S.FIRST_PUBLICATION_YEAR].value == S.WD_TEST_DATE
    assert S.LANGUAGE not in facts
    assert S.DESCRIPTION not in facts
    assert facts[S.WD_ORIGINAL_LANGUAGE].state == FieldState.PRESENT
    assert S.WD_TEST_PRIVATE_MARKER not in json.dumps(http.calls)
    assert S.WD_GOODREADS_WORK not in json.dumps(http.calls)


@pytest.mark.parametrize(S.TYPE, C.WD_TEST_REJECT_TYPES)
def test_rejects_edition_and_series_items(
    payload: dict[str, Any], book: BookRecord, type: str
) -> None:
    _value(payload, S.WD_INSTANCE)[S.ID] = type
    assert not WikidataProvider(_http(payload)).lookup(book).candidates


def test_rejects_edition_of_even_with_novel_type(payload: dict[str, Any], book: BookRecord) -> None:
    _entity(payload)[S.WD_CLAIMS][S.WD_EDITION_OF] = copy.deepcopy(
        _entity(payload)[S.WD_CLAIMS][S.WD_INSTANCE]
    )
    assert not WikidataProvider(_http(payload)).lookup(book).candidates


def test_wrong_title_or_author_cannot_use_goodreads_work_id(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = _http(payload)
    wrong = book.model_copy(update={S.TITLE: S.WD_TEST_PRIVATE_MARKER})
    assert not WikidataProvider(http).lookup(wrong).candidates
    author = payload[S.WD_TEST_RELATED][S.WD_ENTITIES][S.WD_TEST_AUTHOR_ID]
    author[S.WD_LABELS][S.WD_EN][S.VALUE] = S.WD_TEST_PRIVATE_MARKER
    assert not WikidataProvider(_http(payload)).lookup(book).candidates


def test_full_author_initials_and_public_aliases_are_supported(
    payload: dict[str, Any], book: BookRecord
) -> None:
    author = payload[S.WD_TEST_RELATED][S.WD_ENTITIES][S.WD_TEST_AUTHOR_ID]
    author[S.WD_LABELS][S.WD_EN][S.VALUE] = S.WD_TEST_SPACED_INITIALS
    altered = book.model_copy(update={S.AUTHORS: (S.WD_TEST_INITIALS,)})
    assert WikidataProvider(_http(payload)).lookup(altered).candidates
    author[S.WD_LABELS][S.WD_EN][S.VALUE] = S.WD_TEST_PRIVATE_MARKER
    author[S.WD_ALIASES][S.WD_EN] = [{S.VALUE: S.WD_TEST_INITIALS}]
    assert WikidataProvider(_http(payload)).lookup(altered).candidates


def test_unknown_extra_coauthor_rejected(payload: dict[str, Any], book: BookRecord) -> None:
    claim = copy.deepcopy(_claim(payload, S.WD_AUTHOR))
    claim[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE][S.ID] = S.WD_TEST_COAUTHOR_ID
    _entity(payload)[S.WD_CLAIMS][S.WD_AUTHOR].append(claim)
    payload[S.WD_TEST_RELATED][S.WD_ENTITIES][S.WD_TEST_COAUTHOR_ID] = {
        S.ID: S.WD_TEST_COAUTHOR_ID,
        S.WD_LABELS: {S.WD_EN: {S.VALUE: S.WD_TEST_PRIVATE_MARKER}},
    }
    assert not WikidataProvider(_http(payload)).lookup(book).candidates


def test_multiple_plausible_works_abstain(payload: dict[str, Any], book: BookRecord) -> None:
    _entity(payload)[S.ID] = S.WD_TEST_OTHER_ID
    payload[S.WD_ENTITIES][S.WD_TEST_OTHER_ID] = copy.deepcopy(_entity(payload))
    _entity(payload)[S.ID] = S.WD_TEST_WORK_ID
    payload[S.WD_SEARCH].append({S.ID: S.WD_TEST_OTHER_ID})
    result = WikidataProvider(_http(payload)).lookup(book)
    assert not result.candidates and result.issues[C.ZERO].code == S.WD_AMBIGUOUS


def test_selected_open_library_work_is_conflict_veto(
    payload: dict[str, Any], book: BookRecord
) -> None:
    selected = MetadataCandidate(
        provider=Source.OPEN_LIBRARY,
        provider_id=S.WD_TEST_OTHER_OL,
        work_id=S.WD_TEST_OTHER_OL,
        title=book.title,
        authors=book.authors,
        url=book.url,
    )
    provider = WikidataProvider(_http(payload), candidates_for_book=lambda _: (selected,))
    assert not provider.lookup(book).candidates
    selected = selected.model_copy(update={S.WORK_ID: S.WD_TEST_OL_ID})
    provider = WikidataProvider(_http(payload), candidates_for_book=lambda _: (selected,))
    assert provider.lookup(book).candidates


def test_missing_facts_remain_unavailable(payload: dict[str, Any], book: BookRecord) -> None:
    for prop in C.WD_TEST_FACT_PROPERTIES:
        del _entity(payload)[S.WD_CLAIMS][prop]
    result = WikidataProvider(_http(payload)).lookup(book)
    facts = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert all(
        facts[field].state == FieldState.UNAVAILABLE and facts[field].value is C.NONE
        for field in C.WD_FACT_FIELDS
    )


@pytest.mark.parametrize(S.WD_TEST_PARAMETER_PRECISION, C.WD_TEST_DATE_CASES)
def test_publication_precision_retained(
    payload: dict[str, Any], book: BookRecord, precision: int, expected: str
) -> None:
    _value(payload, S.WD_PUBLICATION)[S.WD_PRECISION] = precision
    result = WikidataProvider(_http(payload)).lookup(book)
    assert (
        next(
            item.value
            for item in result.candidates[C.ZERO].observations
            if item.field == S.FIRST_PUBLICATION_YEAR
        )
        == expected
    )


def test_deprecated_dates_ignored_and_preferred_rank_wins(
    payload: dict[str, Any], book: BookRecord
) -> None:
    other = copy.deepcopy(_claim(payload, S.WD_PUBLICATION))
    other[S.WD_RANK] = S.WD_DEPRECATED
    other[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE][S.WD_TIME] = S.WD_TEST_OTHER_TIME
    _entity(payload)[S.WD_CLAIMS][S.WD_PUBLICATION].append(other)
    assert WikidataProvider(_http(payload)).lookup(book).state == SyncState.COMPLETE
    other[S.WD_RANK] = S.WD_NORMAL
    _claim(payload, S.WD_PUBLICATION)[S.WD_RANK] = S.WD_PREFERRED
    assert WikidataProvider(_http(payload)).lookup(book).state == SyncState.COMPLETE


def test_conflicting_dates_fail_without_choosing_earliest(
    payload: dict[str, Any], book: BookRecord
) -> None:
    other = copy.deepcopy(_claim(payload, S.WD_PUBLICATION))
    other[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE][S.WD_TIME] = S.WD_TEST_OTHER_TIME
    _entity(payload)[S.WD_CLAIMS][S.WD_PUBLICATION].append(other)
    result = WikidataProvider(_http(payload)).lookup(book)
    fact = next(
        item
        for item in result.candidates[C.ZERO].observations
        if item.field == S.FIRST_PUBLICATION_YEAR
    )
    assert result.issues and fact.state == FieldState.FAILED and fact.value is C.NONE


def test_invalid_date_fails_and_julian_date_is_not_converted(
    payload: dict[str, Any], book: BookRecord
) -> None:
    _value(payload, S.WD_PUBLICATION)[S.WD_TIME] = S.WD_TEST_INVALID_TIME
    result = WikidataProvider(_http(payload)).lookup(book)
    assert result.state == SyncState.PARTIAL
    _value(payload, S.WD_PUBLICATION)[S.WD_CALENDAR] = S.WD_TEST_JULIAN
    result = WikidataProvider(_http(payload)).lookup(book)
    fact = next(
        item
        for item in result.candidates[C.ZERO].observations
        if item.field == S.FIRST_PUBLICATION_YEAR
    )
    assert fact.state == FieldState.UNAVAILABLE


def test_conflicting_series_position_stays_unknown(
    payload: dict[str, Any], book: BookRecord
) -> None:
    claim = _claim(payload, S.WD_SERIES)
    duplicate = copy.deepcopy(claim)
    duplicate[S.WD_QUALIFIERS][S.WD_ORDINAL][C.ZERO][S.WD_DATAVALUE][S.VALUE] = (
        S.WD_TEST_OTHER_POSITION
    )
    _entity(payload)[S.WD_CLAIMS][S.WD_SERIES].append(duplicate)
    result = WikidataProvider(_http(payload)).lookup(book)
    memberships = next(
        item.value
        for item in result.candidates[C.ZERO].observations
        if item.field == S.WD_SERIES_MEMBERSHIPS
    )
    assert result.issues
    assert (
        next(item for item in memberships if item[S.WD_SERIES_ID] == S.WD_BOOK_SERIES)[
            S.WD_POSITION
        ]
        is C.NONE
    )


def test_settled_response_cache_is_zero_wire_across_process_instances(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    path = tmp_path / S.WD_TEST_CACHE_FILE
    cache = MetadataCache(path)
    http = _http(payload)
    first = WikidataProvider(http, cache=cache).lookup(book)
    cache.close()
    cache = MetadataCache(path)
    no_wire = FakeHttp()
    repeated = WikidataProvider(no_wire, cache=cache).lookup(book)
    assert repeated.cache_hit and not first.cache_hit
    assert repeated.candidates[C.ZERO].provider_id == first.candidates[C.ZERO].provider_id
    assert not no_wire.calls
    cache.close()


def test_budget_propagates_deferred_and_halts_without_fake_results(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = _http(payload)
    provider = WikidataProvider(http, max_requests=C.ONE)
    with pytest.raises(ProviderDeferredError) as caught:
        provider.lookup(book)
    assert caught.value.code == S.REQUEST_BUDGET_EXHAUSTED
    with pytest.raises(ProviderDeferredError):
        provider.lookup(book)
    assert len(http.calls) == C.ONE


def test_truncated_search_abstains_without_entity_requests(book: BookRecord) -> None:
    http = FakeHttp({S.WD_SEARCH: [{S.ID: S.WD_TEST_WORK_ID}], S.WD_SEARCH_CONTINUE: C.ONE})
    result = WikidataProvider(http).lookup(book)
    assert result.issues[C.ZERO].code == S.WD_INCOMPLETE
    assert not result.candidates and len(http.calls) == C.ONE


@pytest.mark.parametrize(S.WD_TEST_PARAMETER_ERROR, C.WD_TEST_ERRORS)
def test_api_errors_never_turn_into_success_or_cached_missing(
    book: BookRecord, code: str, retryable: bool
) -> None:
    http = FakeHttp({S.ERROR: {S.CODE: code}})
    provider = WikidataProvider(http)
    with pytest.raises(ConnectorError) as caught:
        provider.lookup(book)
    assert caught.value.retryable == retryable
    assert isinstance(caught.value, ProviderDeferredError) == retryable
    if retryable:
        assert caught.value.state == SyncState.BLOCKED
        assert caught.value.code == S.PROVIDER_COOLDOWN
        assert str(caught.value) == C.WD_API_PAUSE_MESSAGES[code]
        assert str(caught.value) != S.WD_ERROR_MESSAGE


@pytest.mark.parametrize(S.STATUS, C.WD_TEST_BLOCKED_HTTP)
def test_http_blocks_and_transient_failures_are_explicit(book: BookRecord, status: int) -> None:
    http = FakeHttp({}, status=status)
    with pytest.raises(ConnectorError) as caught:
        WikidataProvider(http).lookup(book)
    assert caught.value.retryable


@pytest.mark.parametrize(S.TYPE, C.WD_UNKNOWN_SNAKS)
def test_unknown_date_snak_does_not_invent_date(
    payload: dict[str, Any], book: BookRecord, type: str
) -> None:
    _claim(payload, S.WD_PUBLICATION)[S.WD_MAIN_SNAK] = {S.WD_SNAK_TYPE: type}
    result = WikidataProvider(_http(payload)).lookup(book)
    fact = next(
        item
        for item in result.candidates[C.ZERO].observations
        if item.field == S.FIRST_PUBLICATION_YEAR
    )
    assert fact.state == FieldState.UNAVAILABLE and fact.value is C.NONE


def test_compatible_date_precisions_refine_without_choosing_earliest(
    payload: dict[str, Any], book: BookRecord
) -> None:
    year = copy.deepcopy(_claim(payload, S.WD_PUBLICATION))
    year[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE][S.WD_PRECISION] = C.WD_YEAR_PRECISION
    _entity(payload)[S.WD_CLAIMS][S.WD_PUBLICATION].append(year)
    result = WikidataProvider(_http(payload)).lookup(book)
    fact = next(
        item
        for item in result.candidates[C.ZERO].observations
        if item.field == S.FIRST_PUBLICATION_YEAR
    )
    assert fact.value == S.WD_TEST_DATE and not result.issues


def test_malformed_facts_fail_their_field_without_discarding_identity(
    payload: dict[str, Any], book: BookRecord
) -> None:
    _claim(payload, S.WD_PUBLICATION)[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE] = {}
    _claim(payload, S.WD_GENRE)[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE] = {}
    result = WikidataProvider(_http(payload)).lookup(book)
    facts = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert facts[S.FIRST_PUBLICATION_YEAR].state == FieldState.FAILED
    assert facts[S.GENRES].state == FieldState.FAILED
    assert facts[S.SERIES].state == FieldState.PRESENT
    assert result.state == SyncState.PARTIAL


def test_malformed_position_does_not_borrow_other_series_position(
    payload: dict[str, Any], book: BookRecord
) -> None:
    _claim(payload, S.WD_SERIES)[S.WD_QUALIFIERS][S.WD_ORDINAL][C.ZERO][S.WD_DATAVALUE][S.VALUE] = (
        S.WD_TEST_BAD_POSITION
    )
    result = WikidataProvider(_http(payload)).lookup(book)
    memberships = next(
        item.value
        for item in result.candidates[C.ZERO].observations
        if item.field == S.WD_SERIES_MEMBERSHIPS
    )
    assert (
        next(item for item in memberships if item[S.WD_SERIES_ID] == S.WD_BOOK_SERIES)[
            S.WD_POSITION
        ]
        is C.NONE
    )
    assert (
        next(item for item in memberships if item[S.WD_SERIES_ID] == S.WD_NOVEL_SERIES)[
            S.WD_POSITION
        ]
        == S.WD_TEST_OTHER_POSITION
    )


def test_missing_search_is_cached_without_source_or_capture_time_invalidation(
    book: BookRecord, tmp_path: Path
) -> None:
    cache = MetadataCache(tmp_path / S.WD_TEST_CACHE_FILE)
    first = WikidataProvider(FakeHttp({S.WD_SEARCH: []}), cache=cache).lookup(book)
    no_wire = FakeHttp()
    changed = book.model_copy(update={S.SOURCE_ID: S.WD_TEST_OTHER_ID, S.URL: S.WD_ENDPOINT})
    repeated = WikidataProvider(no_wire, cache=cache).lookup(changed)
    assert not first.candidates and not repeated.candidates
    assert repeated.cache_hit and not no_wire.calls
    cache.close()


def test_entity_responses_reused_across_different_title_queries(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = _http(payload)
    provider = WikidataProvider(http)
    assert provider.lookup(book).candidates
    changed = book.model_copy(update={S.TITLE: S.WD_TEST_PRIVATE_MARKER})
    http.payloads.append({S.WD_SEARCH: payload[S.WD_SEARCH]})
    before = len(http.calls)
    assert not provider.lookup(changed).candidates
    assert len(http.calls) == before + C.ONE


def test_conflicting_confirmed_catalog_links_abstain_without_requests(
    book: BookRecord,
) -> None:
    selected = MetadataCandidate(
        provider=Source.OPEN_LIBRARY,
        provider_id=S.WD_TEST_OL_ID,
        work_id=S.WD_TEST_OL_ID,
        title=book.title,
        authors=book.authors,
        url=book.url,
    )
    other = selected.model_copy(update={S.WORK_ID: S.WD_TEST_OTHER_OL})
    http = FakeHttp()
    result = WikidataProvider(http, candidates_for_book=lambda _: (selected, other)).lookup(book)
    assert not result.candidates and not http.calls


def test_raw_json_syntax_and_shapes_must_be_valid(book: BookRecord) -> None:
    class MalformedHttp(FakeHttp):
        def fetch(
            self,
            url: str,
            *,
            params: Mapping[str, str] | None = C.NONE,
            headers: Mapping[str, str] | None = C.NONE,
        ) -> HttpResponse:
            return HttpResponse(
                url=url, status_code=C.HTTP_OK, headers={}, body=S.WD_TEST_HTTP_BODY
            )

    with pytest.raises(ConnectorError) as caught:
        WikidataProvider(MalformedHttp()).lookup(book)
    assert not caught.value.retryable
    with pytest.raises(ConnectorError):
        WikidataProvider(FakeHttp([])).lookup(book)


def test_underlying_wire_budget_also_halts_provider_run(book: BookRecord) -> None:
    http = FakeHttp(
        ConnectorError(S.WD_BUDGET_MESSAGE, code=S.REQUEST_BUDGET_EXHAUSTED, retryable=C.TRUE)
    )
    with pytest.raises(ProviderDeferredError) as caught:
        WikidataProvider(http).lookup(book)
    assert caught.value.code == S.REQUEST_BUDGET_EXHAUSTED


@pytest.mark.parametrize(S.WD_TEST_PARAMETER_OPTIONAL, C.WD_TEST_OPTIONAL_CASES)
def test_optional_work_fact_defect_preserves_strict_identity(
    payload: dict[str, Any], book: BookRecord, prop: str, field: str
) -> None:
    _claim(payload, prop)[S.WD_MAIN_SNAK][S.WD_DATAVALUE][S.VALUE] = {}
    result = WikidataProvider(_http(payload)).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert all(issue.code in C.META_COVERAGE_OPTIONAL_ISSUES for issue in result.issues)
    selected = select_metadata_candidate(book, result.candidates)
    assert selected is not C.NONE
    assert (
        next(item for item in selected.observations if item.field == field).state
        == FieldState.FAILED
    )


def test_maxlag_explained_without_echoing_server_details_or_caching_missing(
    book: BookRecord, tmp_path: Path
) -> None:
    cache = MetadataCache(tmp_path / S.WD_TEST_CACHE_FILE)
    http = FakeHttp(
        {
            S.ERROR: {
                S.CODE: S.WD_API_MAXLAG,
                S.WD_ERROR_INFO: S.WD_TEST_PRIVATE_MARKER,
            }
        },
        {S.WD_SEARCH: []},
    )
    provider = WikidataProvider(http, cache=cache)
    with pytest.raises(ProviderDeferredError) as caught:
        provider.lookup(book)
    assert str(caught.value) == S.WD_MAXLAG_MESSAGE
    assert S.WD_TEST_PRIVATE_MARKER not in str(caught.value)
    recovered = provider.lookup(book)
    assert recovered.issues[C.ZERO].code == S.WD_NO_MATCH
    assert not recovered.cache_hit and len(http.calls) == C.TWO
    cache.close()


@pytest.mark.parametrize(S.WD_TEST_PARAMETER_QUERY, C.WD_TEST_QUERY_CASES)
def test_search_uses_recognized_display_suffix_policy_only(
    book: BookRecord, title: str, expected: str
) -> None:
    http = FakeHttp({S.WD_SEARCH: []})
    original = book.model_copy(update={S.TITLE: title})
    WikidataProvider(http).lookup(original)
    assert http.calls[C.ZERO][S.WD_SEARCH] == expected
    assert original.title == title


def test_display_suffix_retrieval_preserves_original_identity_validation(
    payload: dict[str, Any], book: BookRecord
) -> None:
    original = book.model_copy(update={S.TITLE: S.WD_TEST_MATILDA_DISPLAY})
    http = _http(payload)
    result = WikidataProvider(http).lookup(original)
    assert http.calls[C.ZERO][S.WD_SEARCH] == S.WD_TEST_MATILDA_QUERY
    assert select_metadata_candidate(original, result.candidates) is not C.NONE
    _entity(payload)[S.WD_LABELS][S.WD_EN][S.VALUE] = S.WD_TEST_MATILDA_CONFLICT
    result = WikidataProvider(_http(payload)).lookup(original)
    assert not result.candidates


@pytest.mark.parametrize(S.TITLE, C.WD_TEST_TITLE_COLLISIONS)
def test_retrieval_does_not_remove_volume_omnibus_or_subtitle_identity_guards(
    payload: dict[str, Any], book: BookRecord, title: str
) -> None:
    original = book.model_copy(update={S.TITLE: title})
    assert not WikidataProvider(_http(payload)).lookup(original).candidates


def test_display_suffix_query_still_abstains_when_search_is_truncated(book: BookRecord) -> None:
    http = FakeHttp({S.WD_SEARCH: [{S.ID: S.WD_TEST_WORK_ID}], S.WD_SEARCH_CONTINUE: C.ONE})
    original = book.model_copy(update={S.TITLE: S.WD_TEST_MATILDA_DISPLAY})
    result = WikidataProvider(http).lookup(original)
    assert http.calls[C.ZERO][S.WD_SEARCH] == S.WD_TEST_MATILDA_QUERY
    assert result.issues[C.ZERO].code == S.WD_INCOMPLETE
    assert not result.candidates and len(http.calls) == C.ONE
