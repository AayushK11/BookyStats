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
                        S.SPACE.join(label.split()).casefold()
                    )
                )
                is not C.NONE
            }
        )
    )
