from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisComponent, AnalyticsReport
from bookystats.domain.errors import BookyError


class AnalyticsStoreError(BookyError):
    pass


def _encode(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=C.TRUE,
            ensure_ascii=C.TRUE,
            separators=(S.COMMA, S.COLON),
            allow_nan=C.FALSE,
        )
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode(S.UTF_8)).hexdigest()


def _key(key: object) -> str:
    if not isinstance(key, str) or C.AN_STORE_KEY_PATTERN.fullmatch(key) is C.NONE:
        raise AnalyticsStoreError(S.AN_STORE_ERROR)
    return key


def _decode(payload: object, digest: object) -> dict[str, JsonValue]:
    if not isinstance(payload, str) or not hmac.compare_digest(_hash(payload), _key(digest)):
        raise AnalyticsStoreError(S.AN_STORE_ERROR)
    try:
        value: JsonValue = json.loads(payload)
        if not isinstance(value, dict) or _encode(value) != payload:
            raise AnalyticsStoreError(S.AN_STORE_ERROR)
        return value
    except (ValueError, TypeError, RecursionError):
        raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE


def _unbound(component: AnalysisComponent) -> AnalysisComponent:
    return component.model_copy(
        update={
            S.AN_STORE_FINDINGS: tuple(
                finding.model_copy(update={S.AN_STORE_SNAPSHOT_IDS: ()})
                for finding in component.findings
            )
        }
    )


def _binding(component: AnalysisComponent) -> dict[str, JsonValue]:
    return {
        S.AN_STORE_COMPONENT_KEY: component.key,
        S.AN_STORE_SNAPSHOT_IDS: [
            list(finding.source_snapshot_ids) for finding in component.findings
        ],
    }


def _bind(component: AnalysisComponent, binding: JsonValue) -> AnalysisComponent:
    if (
        not isinstance(binding, dict)
        or binding.keys() != C.AN_STORE_BINDING_FIELDS
        or binding.get(S.AN_STORE_COMPONENT_KEY) != component.key
    ):
        raise AnalyticsStoreError(S.AN_STORE_ERROR)
    provenance = binding[S.AN_STORE_SNAPSHOT_IDS]
    if not isinstance(provenance, list) or len(provenance) != len(component.findings):
        raise AnalyticsStoreError(S.AN_STORE_ERROR)
    data = component.model_dump(mode=S.JSON, warnings=S.ERROR)
    for finding, snapshot_ids in zip(data[S.AN_STORE_FINDINGS], provenance, strict=C.TRUE):
        if not isinstance(snapshot_ids, list):
            raise AnalyticsStoreError(S.AN_STORE_ERROR)
        finding[S.AN_STORE_SNAPSHOT_IDS] = snapshot_ids
    try:
        bound = AnalysisComponent.model_validate(data)
        if _encode(_binding(bound)) != _encode(binding):
            raise AnalyticsStoreError(S.AN_STORE_ERROR)
        return bound
    except (ValueError, TypeError, RecursionError):
        raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE


class AnalyticsStore:
    def __init__(self, path: Path, *, require_existing: bool = C.FALSE) -> None:
        self._connection: sqlite3.Connection | None = C.NONE
        try:
            if require_existing:
                self._connection = sqlite3.connect(
                    path.resolve().as_uri() + S.LAYOUT_SQLITE_EXISTING_QUERY,
                    timeout=C.FIVE,
                    uri=C.TRUE,
                )
            else:
                path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
                self._connection = sqlite3.connect(path, timeout=C.FIVE)
            connection = self._db()
            connection.execute(S.AN_STORE_FOREIGN_KEYS)
            if connection.execute(S.AN_STORE_FOREIGN_KEYS_CHECK).fetchall() != [(C.ONE,)]:
                raise AnalyticsStoreError(S.AN_STORE_ERROR)
            with self._transaction():
                objects = connection.execute(S.AN_STORE_SCHEMA).fetchall()
                app_id = connection.execute(S.AN_STORE_APP_ID).fetchone()[C.ZERO]
                version = connection.execute(S.AN_STORE_VERSION).fetchone()[C.ZERO]
                if (
                    not objects
                    and app_id == C.ZERO
                    and version == C.ZERO
                    and connection.execute(S.AN_STORE_HAS_SCHEMA).fetchone() is C.NONE
                ):
                    connection.execute(S.AN_STORE_CREATE_COMPONENTS)
                    connection.execute(S.AN_STORE_CREATE_REPORTS)
                    connection.execute(S.AN_STORE_SET_APP_ID)
                    connection.execute(S.REC_CREATE_CACHE)
                    connection.execute(S.REC_CREATE_REPORTS)
                    connection.execute(S.REC_SET_VERSION)
                elif version == C.AN_STORE_SCHEMA_VERSION:
                    self._validate(legacy=C.TRUE)
                    self._validate_payloads()
                    connection.execute(S.REC_CREATE_CACHE)
                    connection.execute(S.REC_CREATE_REPORTS)
                    connection.execute(S.REC_SET_VERSION)
                self._validate()
                self._validate_payloads()
        except (OSError, sqlite3.Error, AnalyticsStoreError, ValueError, UnicodeError):
            self.close()
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def _db(self) -> sqlite3.Connection:
        if self._connection is C.NONE:
            raise AnalyticsStoreError(S.AN_STORE_CLOSED)
        return self._connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._db()
        try:
            with connection:
                connection.execute(S.AN_STORE_BEGIN)
                yield connection
        except sqlite3.Error:
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def _validate(self, *, legacy: bool = C.FALSE) -> None:
        connection = self._db()
        if (
            connection.execute(S.AN_STORE_APP_ID).fetchone()[C.ZERO] != C.AN_STORE_APPLICATION_ID
            or connection.execute(S.AN_STORE_VERSION).fetchone()[C.ZERO]
            != (C.AN_STORE_SCHEMA_VERSION if legacy else C.REC_SCHEMA_VERSION)
            or tuple(connection.execute(S.AN_STORE_SCHEMA).fetchall())
            != (C.AN_STORE_SCHEMA if legacy else C.REC_SCHEMA)
            or connection.execute(S.AN_STORE_INTEGRITY).fetchall() != [(S.OK,)]
            or connection.execute(S.AN_STORE_FK_CHECK).fetchall()
        ):
            raise AnalyticsStoreError(S.AN_STORE_ERROR)

    def _validate_payloads(self) -> None:
        for row in self._db().execute(S.AN_STORE_ALL_COMPONENTS):
            self._component(row)
        for row in self._db().execute(S.AN_STORE_ALL_REPORTS):
            self._report(row)

    @staticmethod
    def _component(row: tuple[object, ...]) -> AnalysisComponent:
        key, kind, payload, digest = row
        data = _decode(payload, digest)
        try:
            component = AnalysisComponent.model_validate(data)
            if (
                component.key != _key(key)
                or component.kind != kind
                or any(finding.source_snapshot_ids for finding in component.findings)
                or _encode(component.model_dump(mode=S.JSON, warnings=S.ERROR)) != payload
            ):
                raise AnalyticsStoreError(S.AN_STORE_ERROR)
            return component
        except (ValueError, TypeError, RecursionError):
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def get_component(self, key: str) -> AnalysisComponent | None:
        try:
            row = self._db().execute(S.AN_STORE_GET_COMPONENT, (_key(key),)).fetchone()
            return C.NONE if row is C.NONE else self._component(row)
        except (sqlite3.Error, UnicodeError):
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    @staticmethod
    def _prepare(component: AnalysisComponent) -> tuple[str, str, str, str]:
        try:
            component = _unbound(component)
            payload = _encode(component.model_dump(mode=S.JSON, warnings=S.ERROR))
            values = (_key(component.key), component.kind.value, payload, _hash(payload))
            AnalyticsStore._component(values)
            return values
        except (ValueError, TypeError, AttributeError, RecursionError):
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def _save(self, values: tuple[str, str, str, str]) -> None:
        existing = self._db().execute(S.AN_STORE_GET_COMPONENT, (values[C.ZERO],)).fetchone()
        if existing is C.NONE:
            self._db().execute(S.AN_STORE_INSERT_COMPONENT, values)
        elif existing != values:
            raise AnalyticsStoreError(S.AN_STORE_COLLISION)

    def save_component(self, component: AnalysisComponent) -> None:
        self._db()
        values = self._prepare(component)
        with self._transaction():
            self._save(values)

    @staticmethod
    def _compatible(report: AnalyticsReport) -> None:
        if (
            report.taste.kind != C.AnalyticsComponentKind.TASTE
            or report.watchlist.kind != C.AnalyticsComponentKind.WATCHLIST
            or report.taste.key == report.watchlist.key
            or any(
                finding.calculation_version != report.manifest.calculation_version
                for component in (report.taste, report.watchlist)
                for finding in component.findings
            )
        ):
            raise AnalyticsStoreError(S.AN_STORE_ERROR)

    def publish(self, report: AnalyticsReport) -> AnalyticsReport:
        self._db()
        try:
            # Revalidation also protects against mutations of nested model containers.
            report = AnalyticsReport.model_validate_json(report.model_dump_json(warnings=S.ERROR))
            self._compatible(report)
            taste = self._prepare(report.taste)
            watchlist = self._prepare(report.watchlist)
            data = report.model_dump(
                mode=S.JSON, exclude=C.AN_STORE_REPORT_EXCLUDED, warnings=S.ERROR
            )
            data[S.AN_STORE_TASTE] = _binding(report.taste)
            data[S.AN_STORE_WATCHLIST] = _binding(report.watchlist)
            payload = _encode(data)
            digest = _hash(payload)
            with self._transaction() as connection:
                self._save(taste)
                self._save(watchlist)
                cursor = connection.execute(
                    S.AN_STORE_INSERT_REPORT,
                    (report.taste.key, report.watchlist.key, payload, digest),
                )
                report_id = cursor.lastrowid
                if report_id is C.NONE:
                    raise AnalyticsStoreError(S.AN_STORE_ERROR)
            return report.model_copy(update={S.AN_STORE_REPORT_ID: report_id})
        except (ValueError, TypeError, AttributeError, RecursionError):
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def _report(self, row: tuple[object, ...]) -> AnalyticsReport:
        report_id, taste_key, watchlist_key, payload, digest = row
        data = _decode(payload, digest)
        if type(report_id) is not int or report_id < C.ONE or S.AN_STORE_REPORT_ID in data:
            raise AnalyticsStoreError(S.AN_STORE_ERROR)
        taste = self.get_component(_key(taste_key))
        watchlist = self.get_component(_key(watchlist_key))
        if taste is C.NONE or watchlist is C.NONE:
            raise AnalyticsStoreError(S.AN_STORE_ERROR)
        taste = _bind(taste, data.get(S.AN_STORE_TASTE))
        watchlist = _bind(watchlist, data.get(S.AN_STORE_WATCHLIST))
        data[S.AN_STORE_REPORT_ID] = report_id
        data[S.AN_STORE_TASTE] = taste.model_dump(mode=S.JSON, warnings=S.ERROR)
        data[S.AN_STORE_WATCHLIST] = watchlist.model_dump(mode=S.JSON, warnings=S.ERROR)
        try:
            report = AnalyticsReport.model_validate(data)
            self._compatible(report)
            normalized = report.model_dump(
                mode=S.JSON, exclude=C.AN_STORE_REPORT_EXCLUDED, warnings=S.ERROR
            )
            normalized[S.AN_STORE_TASTE] = _binding(taste)
            normalized[S.AN_STORE_WATCHLIST] = _binding(watchlist)
            if _encode(normalized) != payload:
                raise AnalyticsStoreError(S.AN_STORE_ERROR)
            return report
        except (ValueError, TypeError, RecursionError):
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def latest(self) -> AnalyticsReport | None:
        try:
            row = self._db().execute(S.AN_STORE_LATEST).fetchone()
            return C.NONE if row is C.NONE else self._report(row)
        except (sqlite3.Error, UnicodeError):
            raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def close(self) -> None:
        if self._connection is not C.NONE:
            connection, self._connection = self._connection, C.NONE
            try:
                connection.close()
            except sqlite3.Error:
                raise AnalyticsStoreError(S.AN_STORE_ERROR) from C.NONE

    def __enter__(self) -> Self:
        self._db()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
