from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.persistence.inspection import (
    StoreChangedDuringRead,
    StoreStateError,
    inspect_store,
)
from bookystats.runtime.layout import database_path

if TYPE_CHECKING:
    from bookystats.domain.analytics import AnalyticsReport


def library_status(path: Path) -> dict[str, JsonValue] | None:
    # Status never migrates, journals or creates sidecars; an unreadable store reports as None.
    from bookystats.persistence.library import Database

    for _attempt in range(C.DBSAFE_READ_ATTEMPTS):
        store = Database(path)
        try:
            store.initialize(require_existing=C.TRUE, read_only=C.TRUE)
            return store.status()
        except StoreChangedDuringRead:
            continue
        except StoreStateError:
            return C.NONE
        finally:
            store.close()
    return C.NONE


def latest_analytics(path: Path) -> AnalyticsReport | None:
    from bookystats.persistence.analytics import AnalyticsStore

    for _attempt in range(C.DBSAFE_READ_ATTEMPTS):
        try:
            with AnalyticsStore(path, require_existing=C.TRUE, read_only=C.TRUE) as store:
                return store.latest()
        except StoreChangedDuringRead:
            continue
        except StoreStateError:
            return C.NONE
    return C.NONE


def storage_report(directory: Path) -> dict[str, JsonValue]:
    stores: dict[str, JsonValue] = {
        kind.value: inspect_store(
            database_path(directory, C.DBSAFE_CONTRACTS[kind].filename), kind
        ).report()
        for kind in C.StoreKind
    }
    return {S.DBSAFE_ACCESS: S.DBSAFE_ACCESS_READ_ONLY, S.DBSAFE_STORES: stores}


def attention_lines(report: Mapping[str, JsonValue]) -> list[str]:
    storage = report.get(S.DBSAFE_STORAGE)
    stores = storage.get(S.DBSAFE_STORES) if isinstance(storage, dict) else C.NONE
    if not isinstance(stores, dict):
        return []
    return [
        S.DBSAFE_ATTENTION_LINE.format(store=name, detail=entry.get(S.DETAIL))
        for name, entry in stores.items()
        if isinstance(entry, dict) and entry.get(S.STATE) not in C.DBSAFE_QUIET_STATES
    ]
