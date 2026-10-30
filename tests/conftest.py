from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S


@pytest.fixture(autouse=C.TRUE)
def isolated_data_directory(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The default data folder is the tracked <checkout>\data; tests must never write there.
    monkeypatch.setenv(
        S.BOOKYSTATS_DATA_DIR, str(tmp_path_factory.mktemp(S.TEST_ISOLATED_DATA_FOLDER))
    )
