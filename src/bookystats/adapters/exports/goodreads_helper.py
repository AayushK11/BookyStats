from __future__ import annotations

import json
import re
from importlib.resources import files

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConfigurationError
from bookystats.domain.models import Account, Source


def render_goodreads_helper(account: Account) -> str:
    if account.source != Source.GOODREADS or not re.fullmatch(
        S.FETCH_ACCOUNT_PATTERN, account.account_id
    ):
        raise ConfigurationError(S.FETCH_ACCOUNT_REQUIRED)
    template = (
        files(S.FETCH_RESOURCE_PACKAGE).joinpath(S.FETCH_RESOURCE_FILE).read_text(encoding=S.UTF_8)
    )
    if template.count(S.FETCH_ACCOUNT_PLACEHOLDER) != C.ONE:
        raise ConfigurationError(S.FETCH_TEMPLATE_INVALID)
    return template.replace(
        S.FETCH_ACCOUNT_PLACEHOLDER, json.dumps(account.account_id, ensure_ascii=C.TRUE)
    )
