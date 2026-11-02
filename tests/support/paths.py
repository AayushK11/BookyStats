from __future__ import annotations

from pathlib import Path

from bookystats import constants as C
from bookystats import strings as S


def fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[C.ONE].joinpath(S.FIXTURES, *parts)
