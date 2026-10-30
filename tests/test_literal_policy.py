from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S


def _annotation_constants(tree: ast.Module) -> set[int]:
    annotations: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AnnAssign, ast.arg)) and node.annotation is not C.NONE:
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not C.NONE:
                annotations.append(node.returns)
        elif isinstance(node, ast.TypeAlias) or (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Subscript)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id in C.TYPE_ALIAS_CONSTRUCTORS
        ):
            annotations.append(node.value)
    return {
        id(node)
        for annotation in annotations
        for node in ast.walk(annotation)
        if isinstance(node, ast.Constant) and (node.value is C.NONE or node.value is C.ELLIPSIS)
    }


def _literal_violations(root: Path) -> list[str]:
    paths = sorted(
        [
            *root.joinpath(S.SOURCE_FOLDER).rglob(S.PYTHON_PATTERN),
            *root.joinpath(S.TESTS).rglob(S.PYTHON_PATTERN),
        ]
    )
    violations: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding=S.UTF_8))
        annotations = _annotation_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or id(node) in annotations:
                continue
            text = isinstance(node.value, (str, bytes))
            destination = S.STRINGS_MODULE_FILE if text else S.CONSTANTS_MODULE_FILE
            if path != root / S.SOURCE_FOLDER / S.BOOKYSTATS_2 / destination:
                violations.append(
                    S.LITERAL_POLICY_LOCATION.format(
                        path=path.relative_to(root), line=node.lineno, value=node.value
                    )
                )
    return violations


def test_all_code_and_test_literals_are_centralized() -> None:
    violations = _literal_violations(Path(__file__).resolve().parents[C.ONE])
    assert not violations, S.NEWLINE.join(violations)


@pytest.mark.parametrize(
    S.LITERAL_CASE_FIELDS,
    (
        (S.STRINGS_MODULE_FILE, S.MISPLACED_TEXT_SOURCE),
        (S.CONSTANTS_MODULE_FILE, S.MISPLACED_NUMBER_SOURCE),
    ),
)
def test_duplicate_named_modules_do_not_bypass_the_literal_rule(
    tmp_path: Path, name: str, source: str
) -> None:
    misplaced = tmp_path / S.SOURCE_FOLDER / S.LITERAL_TEST_MODULE / name
    misplaced.parent.mkdir(parents=C.TRUE)
    misplaced.write_text(source, encoding=S.UTF_8)
    assert _literal_violations(tmp_path)
