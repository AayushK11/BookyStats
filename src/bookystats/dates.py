from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from bookystats import constants as C
from bookystats import strings as S
from bookystats.models import PartialDate


def parse_date(value: str | None) -> PartialDate | None:
    if value is C.NONE or not value.strip():
        return C.NONE
    raw = value.strip()
    if re.fullmatch(S.DATES_PARSE_DATE_D_D_D, raw):
        return PartialDate(value=raw, raw=raw)
    if re.fullmatch(S.DATES_PARSE_DATE_D_D_D_2, raw):
        return PartialDate(value=raw.replace(S.SLASH, S.HYPHEN), raw=raw)
    if re.match(S.DATES_PARSE_DATE_D_D_D_T, raw):
        parsed = datetime.fromisoformat(raw.replace(S.Z, S.DATES_PARSE_DATE_PARSED_TEXT))
        return PartialDate(value=parsed.date().isoformat(), raw=raw)
    for pattern in (
        S.DATES_PARSE_DATE_B_D_Y,
        S.DATES_PARSE_DATE_B_D_Y_2,
        S.DATES_PARSE_DATE_D_B_Y,
        S.DATES_PARSE_DATE_D_B_Y_2,
    ):
        try:
            parsed = datetime.strptime(raw, pattern)
        except ValueError:
            continue
        return PartialDate(value=parsed.date().isoformat(), raw=raw)
    for pattern in (S.DATES_PARSE_DATE_B_Y, S.DATES_PARSE_DATE_B_Y_2):
        try:
            parsed = datetime.strptime(raw, pattern)
        except ValueError:
            continue
        return PartialDate(value=parsed.strftime(S.DATES_PARSE_DATE_Y_M), raw=raw)
    if re.match(S.DATES_PARSE_DATE_MON_TUE_WED_THU_FRI_SAT_SUN, raw):
        try:
            parsed = parsedate_to_datetime(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(S.DATES_PARSE_DATE_UNSUPPORTED_SOURCE_DATE) from exc
        return PartialDate(value=parsed.date().isoformat(), raw=raw)
    raise ValueError(S.DATES_PARSE_DATE_AMBIGUOUS_OR_UNSUPPORTED_SOURCE_DATE)
