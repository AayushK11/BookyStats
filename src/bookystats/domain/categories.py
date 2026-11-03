from __future__ import annotations

from collections.abc import Iterable

from bookystats import constants as C
from bookystats import strings as S


def analytical_categories(labels: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                category
                for label in labels
                if (
                    category := C.ANALYTIC_CATEGORY_ALIASES.get(
                        S.ENR_CATEGORY_PATH_SEPARATOR.join(
                            S.SPACE.join(part.split()).casefold()
                            for part in label.replace(S.COMMA, S.SLASH).split(S.SLASH)
                        )
                    )
                )
                is not C.NONE
            }
        )
    )
