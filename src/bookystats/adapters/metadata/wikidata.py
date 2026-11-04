from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import cast

from pydantic import JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.interfaces import HttpFetcher
from bookystats.domain.matching import work_bibliography_compatible, work_query_title
from bookystats.domain.models import (
    BookRecord,
    EnrichmentResult,
    FieldState,
    Issue,
    MetadataCandidate,
    Observation,
    PartialDate,
    Source,
    SyncState,
    canonical_json,
    utc_now,
)
from bookystats.persistence.cache import MetadataCache


def _invalid(*, retryable: bool = C.FALSE) -> ConnectorError:
    return ConnectorError(S.WD_ERROR_MESSAGE, code=S.INVALID_RESPONSE, retryable=retryable)


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise _invalid()
    return value


def _qid(value: JsonValue) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(S.WD_QID_PATTERN, value) else C.NONE


def _claims(entity: dict[str, JsonValue], prop: str) -> list[dict[str, JsonValue]]:
    raw = _object(entity.get(S.WD_CLAIMS, {})).get(prop, [])
    if not isinstance(raw, list):
        raise _invalid()
    claims = [_object(item) for item in raw]
    if any(item.get(S.WD_RANK) not in C.WD_RANKS for item in claims):
        raise _invalid()
    usable = [item for item in claims if item[S.WD_RANK] != S.WD_DEPRECATED]
    preferred = [item for item in usable if item[S.WD_RANK] == S.WD_PREFERRED]
    return preferred or usable


def _snak(snak: JsonValue) -> JsonValue:
    data = _object(snak)
    if data.get(S.WD_SNAK_TYPE) in C.WD_UNKNOWN_SNAKS:
        return C.NONE
    if data.get(S.WD_SNAK_TYPE) != S.WD_VALUE:
        raise _invalid()
    return _object(data.get(S.WD_DATAVALUE)).get(S.VALUE)


def _values(entity: dict[str, JsonValue], prop: str) -> list[JsonValue]:
    return [
        value
        for claim in _claims(entity, prop)
        if (value := _snak(claim.get(S.WD_MAIN_SNAK))) is not C.NONE
    ]


def _references(entity: dict[str, JsonValue], prop: str) -> tuple[str, ...]:
    result: set[str] = set()
    for value in _values(entity, prop):
        qid = _qid(_object(value).get(S.ID))
        if qid is C.NONE:
            raise _invalid()
        result.add(qid)
    return tuple(sorted(result))


def _names(entity: dict[str, JsonValue]) -> tuple[str, ...]:
    label = _object(entity.get(S.WD_LABELS, {})).get(S.WD_EN)
    aliases = _object(entity.get(S.WD_ALIASES, {})).get(S.WD_EN, [])
    if not isinstance(aliases, list):
        raise _invalid()
    entries = ([label] if label is not C.NONE else []) + aliases
    names: list[str] = []
    for entry in entries:
        value = _object(entry).get(S.VALUE)
        if not isinstance(value, str) or not value.strip():
            raise _invalid()
        if value.strip() not in names:
            names.append(value.strip())
    return tuple(names)


def _titles(entity: dict[str, JsonValue]) -> tuple[str, ...]:
    titles = list(_names(entity))
    for item in _values(entity, S.WD_TITLE):
        value = _object(item).get(S.WD_TEXT)
        if isinstance(value, str) and value.strip():
            titles.append(value.strip())
    return tuple(dict.fromkeys(titles))


def _ol_ids(candidates: tuple[MetadataCandidate, ...]) -> set[str]:
    result: set[str] = set()
    for item in candidates:
        if item.provider != Source.OPEN_LIBRARY or not item.work_id:
            continue
        match = re.fullmatch(S.WD_OL_PATTERN, item.work_id)
        if match:
            result.add(match[C.ONE])
    return result


def _compatible(
    book: BookRecord,
    entity: dict[str, JsonValue],
    related: dict[str, dict[str, JsonValue]],
    ol_ids: set[str],
) -> tuple[str, tuple[str, ...]] | None:
    kinds = set(_references(entity, S.WD_INSTANCE))
    if (
        not kinds.intersection(C.WD_WORK_TYPES)
        or kinds.intersection(C.WD_REJECT_TYPES)
        or _claims(entity, S.WD_EDITION_OF)
    ):
        return C.NONE
    catalog = _values(entity, S.WD_OL_ID)
    if any(
        not isinstance(value, str) or not re.fullmatch(S.WD_OL_PATTERN, value) for value in catalog
    ):
        return C.NONE
    if ol_ids and catalog and not set(cast(list[str], catalog)).issubset(ol_ids):
        return C.NONE
    authors: list[str] = []
    author_ids = _references(entity, S.WD_AUTHOR)
    if not author_ids or not book.authors:
        return C.NONE
    for author_id in author_ids:
        matches = [
            name
            for name in _names(related.get(author_id, {}))
            if any(
                work_bibliography_compatible(
                    book.model_copy(update={S.AUTHORS: (author,)}),
                    book.model_copy(update={S.AUTHORS: (name,)}),
                )
                for author in book.authors
            )
        ]
        if not matches:
            return C.NONE
        authors.append(matches[C.ZERO])
    for title in _titles(entity):
        probe = book.model_copy(update={S.TITLE: title, S.AUTHORS: tuple(authors)})
        if work_bibliography_compatible(book, probe):
            return title, tuple(authors)
    return C.NONE


class _Facts:
    def __init__(self, qid: str) -> None:
        self.url = S.WD_ENTITY_URL.format(qid=qid)
        self.observed_at = utc_now()
        self.observations: list[Observation] = []
        self.issues: list[Issue] = []

    def add(
        self, field: str, value: JsonValue = C.NONE, state: FieldState = FieldState.PRESENT
    ) -> None:
        self.observations.append(
            Observation(
                field=field,
                value=value,
                state=state,
                scope=S.WORK,
                source_url=self.url,
                observed_at=self.observed_at,
            )
        )

    def invalid(self, field: str) -> None:
        self.issues.append(
            Issue(code=S.INVALID_METADATA_FIELD, message=S.WD_FIELD_MESSAGE.format(field=field))
        )

    def publication(self, entity: dict[str, JsonValue]) -> None:
        dates: set[str] = set()
        try:
            values = _values(entity, S.WD_PUBLICATION)
            for raw in values:
                data = _object(raw)
                precision, time = data.get(S.WD_PRECISION), data.get(S.WD_TIME)
                if type(precision) is not int or not isinstance(time, str):
                    raise ValueError
                if precision not in C.WD_DATE_LENGTHS or data.get(S.WD_CALENDAR) != S.WD_GREGORIAN:
                    continue
                match = re.fullmatch(S.WD_TIME_PATTERN, time)
                if not match or any(data.get(key, C.ZERO) != C.ZERO for key in C.WD_DATE_AUXILIARY):
                    raise ValueError
                length = C.WD_DATE_LENGTHS[precision]
                date = time[C.ONE : length + C.ONE]
                PartialDate(value=date)
                dates.add(date)
            longest = max(dates, key=len) if dates else C.NONE
            if longest and any(not longest.startswith(date) for date in dates):
                raise ValueError
        except (ValueError, ValidationError, ConnectorError):
            self.invalid(S.FIRST_PUBLICATION_YEAR)
            self.add(S.FIRST_PUBLICATION_YEAR, state=FieldState.FAILED)
            return
        self.add(
            S.FIRST_PUBLICATION_YEAR,
            longest,
            FieldState.PRESENT if longest else FieldState.UNAVAILABLE,
        )

    def memberships(
        self, entity: dict[str, JsonValue], related: dict[str, dict[str, JsonValue]]
    ) -> None:
        memberships: dict[str, set[str]] = {}
        invalid: set[str] = set()
        for claim in _claims(entity, S.WD_SERIES):
            value = _snak(claim.get(S.WD_MAIN_SNAK))
            if value is C.NONE:
                continue
            qid = _qid(_object(value).get(S.ID))
            if qid is C.NONE:
                raise _invalid()
            positions = memberships.setdefault(qid, set())
            qualifiers = _object(claim.get(S.WD_QUALIFIERS, {})).get(S.WD_ORDINAL, [])
            if not isinstance(qualifiers, list):
                raise _invalid()
            for qualifier in qualifiers:
                position = _snak(qualifier)
                if position is C.NONE:
                    continue
                if not isinstance(position, str) or not re.fullmatch(
                    S.WD_POSITION_PATTERN, position
                ):
                    invalid.add(qid)
                else:
                    positions.add(position)
        pairs: list[JsonValue] = []
        names: list[JsonValue] = []
        positions_output: list[JsonValue] = []
        for qid, positions in sorted(memberships.items()):
            labels = _names(related.get(qid, {}))
            name = labels[C.ZERO] if labels else C.NONE
            position = (
                next(iter(positions)) if len(positions) == C.ONE and qid not in invalid else C.NONE
            )
            if len(positions) > C.ONE or qid in invalid:
                self.invalid(S.WD_SERIES_MEMBERSHIPS)
            pairs.append({S.WD_SERIES_ID: qid, S.WD_NAME: name, S.WD_POSITION: position})
            if name:
                names.append(name)
            if position:
                positions_output.append(position)
        for field, value in (
            (S.WD_SERIES_MEMBERSHIPS, pairs),
            (S.SERIES, names),
            (S.META_COVERAGE_SERIES_POSITIONS, positions_output),
        ):
            self.add(
                field,
                value if value else C.NONE,
                FieldState.PRESENT if value else FieldState.UNAVAILABLE,
            )

    def labels(
        self,
        entity: dict[str, JsonValue],
        related: dict[str, dict[str, JsonValue]],
        prop: str,
        field: str,
    ) -> None:
        values: list[JsonValue] = []
        for qid in _references(entity, prop):
            labels = _names(related.get(qid, {}))
            if labels:
                values.append(labels[C.ZERO])
        self.add(
            field,
            values if values else C.NONE,
            FieldState.PRESENT if values else FieldState.UNAVAILABLE,
        )

    def collect(
        self, entity: dict[str, JsonValue], related: dict[str, dict[str, JsonValue]]
    ) -> None:
        self.publication(entity)
        try:
            self.memberships(entity, related)
        except ConnectorError:
            for field in C.WD_SERIES_FIELDS:
                self.invalid(field)
                self.add(field, state=FieldState.FAILED)
        for prop, field in C.WD_LABEL_FIELDS:
            try:
                self.labels(entity, related, prop, field)
            except ConnectorError:
                self.invalid(field)
                self.add(field, state=FieldState.FAILED)


class WikidataProvider:
    def __init__(
        self,
        fetcher: HttpFetcher,
        *,
        cache: MetadataCache | None = C.NONE,
        candidates_for_book: Callable[[BookRecord], tuple[MetadataCandidate, ...]] | None = C.NONE,
        max_requests: int = C.WD_MAX_REQUESTS,
    ) -> None:
        if type(max_requests) is not int or max_requests < C.ZERO:
            raise ValueError(S.WD_BUDGET_MESSAGE)
        self._fetcher = fetcher
        self._cache = cache
        self._candidates_for_book = candidates_for_book
        self._max_requests = max_requests
        self._requests = C.ZERO
        self._memory: dict[str, dict[str, JsonValue]] = {}
        self._wire_at_start = C.ZERO

    def _request(
        self, params: dict[str, str], identity: tuple[str, ...] = ()
    ) -> dict[str, JsonValue]:
        params = {
            **params,
            S.WD_FORMAT: S.JSON,
            S.WD_MAXLAG: str(C.WD_MAXLAG_SECONDS),
        }
        key = canonical_json((S.WD_CACHE_TAG, C.WD_ADAPTER_VERSION, params, identity))
        if key in self._memory:
            return self._memory[key]
        if self._cache is not C.NONE:
            cached = self._cache.get(Source.WIKIDATA, key, allow_expired=C.TRUE)
            if cached is not C.NONE:
                self._memory[key] = cached
                return cached
        if self._requests >= self._max_requests:
            raise ProviderDeferredError(
                S.WD_BUDGET_MESSAGE,
                state=SyncState.PARTIAL,
                code=S.REQUEST_BUDGET_EXHAUSTED,
                retryable=C.TRUE,
            )
        self._requests += C.ONE
        try:
            response = self._fetcher.fetch(
                S.WD_ENDPOINT,
                params=params,
                headers={S.ACCEPT: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
            )
        except ConnectorError as error:
            if error.code == S.REQUEST_BUDGET_EXHAUSTED:
                raise ProviderDeferredError(
                    str(error), state=error.state, code=error.code, retryable=C.TRUE
                ) from error
            raise
        if response.status_code in C.WD_BLOCKED_HTTP:
            raise ProviderDeferredError(
                S.WD_ERROR_MESSAGE,
                state=SyncState.BLOCKED,
                code=S.RATE_LIMITED
                if response.status_code == C.HTTP_TOO_MANY_REQUESTS
                else S.WD_ACCESS_DENIED,
                retryable=C.TRUE,
            )
        if response.status_code != C.HTTP_OK:
            raise _invalid(retryable=response.status_code >= C.WD_SERVER_ERROR)
        content_type = next(
            (value for key, value in response.headers.items() if key.lower() == S.CONTENT_TYPE),
            S.EMPTY,
        )
        if (
            content_type
            and content_type.split(S.RAW_SEMICOLON, C.ONE)[C.ZERO].strip().lower()
            != S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON
        ):
            raise _invalid()
        if len(response.body) > C.WD_MAX_BYTES:
            raise _invalid()
        try:
            payload = _object(cast(JsonValue, json.loads(response.text)))
            canonical_json(payload)
        except (ValueError, UnicodeError, RecursionError):
            raise _invalid() from C.NONE
        if S.ERROR in payload:
            code = _object(payload[S.ERROR]).get(S.CODE)
            transient = isinstance(code, str) and (
                code in C.WD_TRANSIENT_API_CODES or code.startswith(S.WD_API_INTERNAL)
            )
            error_type = ProviderDeferredError if transient else ConnectorError
            raise error_type(
                C.WD_API_PAUSE_MESSAGES.get(code, S.WD_INTERNAL_MESSAGE)
                if transient and isinstance(code, str)
                else S.WD_ERROR_MESSAGE,
                state=SyncState.BLOCKED if transient else SyncState.FAILED,
                code=S.PROVIDER_COOLDOWN if transient else S.API_ERROR,
                retryable=transient,
            )
        self._memory[key] = payload
        if self._cache is not C.NONE:
            self._cache.put(Source.WIKIDATA, key, payload, ttl_seconds=C.WD_CACHE_TTL)
        return payload

    def _entities(
        self, qids: tuple[str, ...], *, labels_only: bool = C.FALSE
    ) -> dict[str, dict[str, JsonValue]]:
        result: dict[str, dict[str, JsonValue]] = {}
        for qid in qids:
            key = canonical_json((S.WD_ENTITIES, C.WD_ADAPTER_VERSION, qid, labels_only))
            if key in self._memory:
                result[qid] = self._memory[key]
            elif self._cache is not C.NONE:
                cached = self._cache.get(Source.WIKIDATA, key, allow_expired=C.TRUE)
                if cached is not C.NONE:
                    self._memory[key] = cached
                    result[qid] = cached
        missing = tuple(qid for qid in qids if qid not in result)
        if not missing:
            return result
        if len(missing) > C.WD_ENTITY_LIMIT:
            raise _invalid()
        payload = self._request(
            {
                S.WD_ACTION: S.WD_ENTITIES_ACTION,
                S.WD_IDS: S.WD_PIPE.join(missing),
                S.WD_PROPS: S.WD_LABEL_PROPS if labels_only else S.WD_ENTITY_PROPS,
                S.WD_LANGUAGES: S.WD_EN,
            }
        )
        entities = _object(payload.get(S.WD_ENTITIES))
        for qid in missing:
            entity = _object(entities.get(qid))
            if entity.get(S.ID) != qid:
                raise _invalid()
            result[qid] = entity
            key = canonical_json((S.WD_ENTITIES, C.WD_ADAPTER_VERSION, qid, labels_only))
            self._memory[key] = entity
            if self._cache is not C.NONE:
                self._cache.put(Source.WIKIDATA, key, entity, ttl_seconds=C.WD_CACHE_TTL)
        return result

    def lookup(self, book: BookRecord) -> EnrichmentResult:
        self._wire_at_start = self._requests
        query = work_query_title(book.title)
        if not query or not book.authors or len(query) > C.WD_MAX_TITLE:
            return self._abstain(book, S.WD_NO_MATCH, S.WD_NO_MATCH_MESSAGE)
        candidates = self._candidates_for_book(book) if self._candidates_for_book else ()
        selected_ids = _ol_ids(candidates)
        if len(selected_ids) > C.ONE:
            return self._abstain(book, S.WD_AMBIGUOUS, S.WD_AMBIGUOUS_MESSAGE)
        search = self._request(
            {
                S.WD_ACTION: S.WD_SEARCH_ACTION,
                S.WD_SEARCH: query,
                S.WD_LANGUAGE: S.WD_EN,
                S.WD_LIMIT: str(C.WD_SEARCH_LIMIT),
                S.TYPE: S.WD_ITEM,
            },
            tuple(sorted(selected_ids)),
        )
        raw = search.get(S.WD_SEARCH)
        if not isinstance(raw, list):
            raise _invalid()
        if S.WD_SEARCH_CONTINUE in search or len(raw) >= C.WD_SEARCH_LIMIT:
            return self._abstain(book, S.WD_INCOMPLETE, S.WD_INCOMPLETE_MESSAGE)
        qids: set[str] = set()
        for item in raw:
            qid = _qid(_object(item).get(S.ID))
            if qid is C.NONE:
                raise _invalid()
            qids.add(qid)
        entities = self._entities(tuple(sorted(qids))) if qids else {}
        related_ids: set[str] = set()
        for entity in entities.values():
            for prop in C.WD_RELATED_PROPERTIES:
                try:
                    related_ids.update(_references(entity, prop))
                except ConnectorError:
                    if prop == S.WD_AUTHOR:
                        raise
        if len(related_ids) > C.WD_ENTITY_LIMIT:
            return self._abstain(book, S.WD_INCOMPLETE, S.WD_INCOMPLETE_MESSAGE)
        related = (
            self._entities(tuple(sorted(related_ids)), labels_only=C.TRUE) if related_ids else {}
        )
        matches = [
            (qid, entity, match)
            for qid, entity in entities.items()
            if (match := _compatible(book, entity, related, selected_ids)) is not C.NONE
        ]
        if len(matches) != C.ONE:
            return self._abstain(
                book,
                S.WD_AMBIGUOUS if matches else S.WD_NO_MATCH,
                S.WD_AMBIGUOUS_MESSAGE if matches else S.WD_NO_MATCH_MESSAGE,
            )
        qid, entity, (title, authors) = matches[C.ZERO]
        facts = _Facts(qid)
        facts.add(S.PROVIDER_ID, qid)
        facts.add(S.TITLE, title)
        facts.add(S.AUTHORS, list(authors))
        facts.collect(entity, related)
        candidate = MetadataCandidate(
            provider=Source.WIKIDATA,
            provider_id=qid,
            work_id=qid,
            title=title,
            authors=authors,
            url=facts.url,
            observations=tuple(facts.observations),
        )
        return EnrichmentResult(
            source_id=book.source_id,
            state=SyncState.PARTIAL if facts.issues else SyncState.COMPLETE,
            candidates=(candidate,),
            issues=tuple(facts.issues),
            cache_hit=self._wire_at_start == self._requests,
        )

    def _abstain(self, book: BookRecord, code: str, message: str) -> EnrichmentResult:
        return EnrichmentResult(
            source_id=book.source_id,
            state=SyncState.PARTIAL,
            issues=(Issue(code=code, message=message),),
            cache_hit=self._wire_at_start == self._requests,
        )
