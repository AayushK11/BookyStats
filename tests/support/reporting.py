from __future__ import annotations

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import MetadataReceipt, SourceReceipt, SyncReceipt
from bookystats.domain.models import (
    Issue,
    SyncState,
    Verification,
)


def run_receipt(
    *,
    sources: tuple[SourceReceipt, ...] = (),
    metadata: tuple[MetadataReceipt, ...] = (),
    verification: Verification | None = C.NONE,
    run_id: int = C.ONE,
) -> SyncReceipt:
    return SyncReceipt(
        run_id=run_id,
        state=SyncState.COMPLETE,
        started_at=S.TEST_REPORTING_FIRST_TIME,
        finished_at=S.TEST_REPORTING_SECOND_TIME,
        account_sync_complete=C.FALSE,
        sources=sources,
        metadata=metadata,
        verification=verification,
    )


def reporting_issues() -> tuple[Issue, ...]:
    return tuple(
        Issue(code=code, message=message) for code, message in C.TEST_REPORTING_ISSUE_VALUES
    )
