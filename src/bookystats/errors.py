from __future__ import annotations

from bookystats import constants as C
from bookystats import strings as S
from bookystats.models import SyncState


class BookyError(Exception):
    pass


class ConfigurationError(BookyError):
    pass


class AlreadyRunning(BookyError):
    pass


class SnapshotRejectedError(BookyError, ValueError):
    pass


class AccountMismatchError(SnapshotRejectedError):
    pass


class ConnectorError(BookyError):
    def __init__(
        self,
        message: str,
        *,
        state: SyncState = SyncState.FAILED,
        code: str = S.COLLECTION_FAILED,
        retryable: bool = C.FALSE,
    ) -> None:
        super().__init__(message)
        self.state = state
        self.code = code
        self.retryable = retryable


class ProviderDeferredError(ConnectorError):
    pass
