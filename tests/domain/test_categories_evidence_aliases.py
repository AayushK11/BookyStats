from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.categories import analytical_categories


@pytest.mark.parametrize(S.L1_GEN_TEST_PARAMETERS, C.L1_GEN_ALIAS_CASES)
def test_evidence_listed_paths_map_to_their_named_family(
    label: str, expected: tuple[str, ...]
) -> None:
    assert analytical_categories((label,)) == expected


def test_non_genre_and_broad_labels_stay_unmapped() -> None:
    assert [label for label in C.L1_GEN_UNMAPPED_LABELS if analytical_categories((label,))] == []


def test_mixed_labels_keep_only_exactly_aliased_families() -> None:
    assert analytical_categories(C.L1_GEN_MIXED_LABELS) == C.L1_GEN_MIXED_EXPECTED


def test_new_aliases_are_specific_known_families_without_overrides() -> None:
    families = {family for family, _ in C.ANALYTIC_CATEGORY_FAMILIES}
    base_keys = {alias for family, aliases in C.ANALYTIC_CATEGORY_FAMILIES for alias in aliases}
    targets = set(C.L1_GEN_EXACT_ALIASES.values())

    assert targets <= families
    assert S.ANALYTIC_CATEGORY_FICTION not in targets
    assert not set(C.L1_GEN_EXACT_ALIASES) & (base_keys | families)
    assert all(
        C.ANALYTIC_CATEGORY_ALIASES[key] == family for key, family in C.L1_GEN_EXACT_ALIASES.items()
    )
