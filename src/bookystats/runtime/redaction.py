from __future__ import annotations

import re
from collections.abc import Iterable

from bookystats import strings as S


def redact(message: str, secrets: Iterable[str] = ()) -> str:
    result = message
    for secret in secrets:
        if secret:
            result = result.replace(secret, S.REDACTION_REDACT_RESULT_REDACTED)
    result = re.sub(
        S.REDACTION_REDACT_RESULT_I_KEY_API_KEY_ACCESS_TOKEN_TOKEN,
        S.REDACTION_REDACT_RESULT_REDACTED_2,
        result,
    )
    return re.sub(
        S.REDACTION_REDACT_I_BBEARER_S_A_ZA_Z0, S.REDACTION_REDACT_BEARER_REDACTED, result
    )
