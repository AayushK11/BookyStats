from __future__ import annotations

import re
import unicodedata

from bookystats import constants as C
from bookystats import strings as S


def normalize_isbn(value: str) -> str | None:
    candidate = value.strip()
    if candidate.startswith(S.IDENTIFIERS_NORMALIZE_ISBN_TEXT) and candidate.endswith(
        S.IDENTIFIERS_NORMALIZE_ISBN_TEXT_2
    ):
        candidate = candidate[C.TWO : -C.ONE]
    candidate = re.sub(S.IDENTIFIERS_NORMALIZE_ISBN_CANDIDATE_S, S.EMPTY, candidate).upper()
    if re.fullmatch(S.IDENTIFIERS_NORMALIZE_ISBN_D_DX, candidate):
        total = sum(
            (
                (C.TEN - index) * (C.TEN if char == S.X else int(char))
                for index, char in enumerate(candidate)
            )
        )
        if total % C.IDENTIFIERS_NORMALIZE_ISBN:
            return C.NONE
        prefix = S.IDENTIFIERS_NORMALIZE_ISBN_PREFIX_TEXT + candidate[: C.NINE]
        check = (
            -sum(
                (
                    int(char) * (C.ONE if index % C.TWO == C.ZERO else C.THREE)
                    for index, char in enumerate(prefix)
                )
            )
            % C.TEN
        )
        return prefix + str(check)
    if re.fullmatch(S.IDENTIFIERS_NORMALIZE_ISBN_D, candidate) and (
        sum(
            (
                int(char) * (C.ONE if index % C.TWO == C.ZERO else C.THREE)
                for index, char in enumerate(candidate)
            )
        )
        % C.TEN
        == C.ZERO
    ):
        return candidate
    return C.NONE


def normalized_text(value: str) -> str:
    normalized = unicodedata.normalize(S.NFKC, value).casefold()
    return S.SPACE.join(
        re.sub(S.IDENTIFIERS_NORMALIZED_TEXT_W_S, S.SPACE, normalized, flags=re.UNICODE).split()
    )


def normalized_isbns(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        sorted({isbn for value in values if (isbn := normalize_isbn(value)) is not C.NONE})
    )
