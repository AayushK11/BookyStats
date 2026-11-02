from __future__ import annotations

from collections import Counter
from html import unescape
from re import Pattern
from urllib.parse import urlsplit, urlunsplit

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisEvidence,
    AnalysisInput,
    AnalyticsSettings,
    Capability,
    Finding,
)
from bookystats.domain.models import FieldState, ReadingStatus


@C.frozen_dataclass
class _Description:
    book: AnalysisBook
    text: str
    evidence: AnalysisEvidence
    public_url: str


def _description(book: AnalysisBook) -> _Description | None:
    if (
        book.field_states.get(S.DESCRIPTION) not in (C.NONE, FieldState.PRESENT)
        or not book.description
        or not book.description.strip()
    ):
        return C.NONE
    for source in C.CONTENT_ANALYSIS_PUBLIC_SOURCES:
        for item in book.evidence:
            observation = item.observation
            if (
                item.source != source
                or observation.field != S.DESCRIPTION
                or observation.state != FieldState.PRESENT
                or observation.scope != S.WORK
                or observation.value != book.description
            ):
                continue
            reference = observation.source_url
            if not C.CONTENT_ANALYSIS_PUBLIC_URL.match(reference):
                if source != S.GOODREADS or not item.public_url:
                    continue
                reference = item.public_url
                if not C.CONTENT_ANALYSIS_PUBLIC_URL.match(reference):
                    continue
            try:
                url = urlsplit(reference)
            except ValueError:
                continue
            if url.username or url.password:
                continue
            public_url = urlunsplit((url.scheme, url.netloc, url.path, S.EMPTY, S.EMPTY))
            text = C.CONTENT_ANALYSIS_SPACE.sub(
                S.SPACE,
                unescape(
                    C.CONTENT_ANALYSIS_HTML.sub(
                        S.SPACE, book.description[: C.CONTENT_ANALYSIS_MAX_DESCRIPTION]
                    )
                ),
            ).strip()
            if text:
                return _Description(book, text, item, public_url)
    return C.NONE


def _proof(description: _Description, pattern: Pattern[str]) -> dict[str, JsonValue] | None:
    for match in pattern.finditer(description.text):
        prefix = description.text[
            max(C.ZERO, match.start() - C.CONTENT_ANALYSIS_NEGATION_CONTEXT) : match.start()
        ]
        clause = C.CONTENT_ANALYSIS_CLAUSE.split(prefix)[-C.ONE]
        if C.CONTENT_ANALYSIS_NEGATION.search(clause):
            continue
        return {
            S.CONTENT_ANALYSIS_WORK: description.book.book_id,
            S.CONTENT_ANALYSIS_SOURCE: description.evidence.source,
            S.CONTENT_ANALYSIS_FIELD: S.DESCRIPTION,
            S.CONTENT_ANALYSIS_SCOPE: description.evidence.observation.scope,
            S.CONTENT_ANALYSIS_URL: description.public_url,
            S.CONTENT_ANALYSIS_MATCH: match.group(),
            S.CONTENT_ANALYSIS_QUOTE: description.text[
                max(C.ZERO, match.start() - C.CONTENT_ANALYSIS_EXCERPT_CONTEXT) : match.end()
                + C.CONTENT_ANALYSIS_EXCERPT_CONTEXT
            ],
        }
    return C.NONE


def description_provenance(book: AnalysisBook) -> dict[str, JsonValue] | None:
    description = _description(book)
    if description is C.NONE:
        return C.NONE
    return {
        S.CONTENT_ANALYSIS_SOURCE: description.evidence.source,
        S.SOURCE_ID: description.evidence.source_id,
        S.CONTENT_ANALYSIS_URL: description.public_url,
    }


def _in_collection(book: AnalysisBook, collection: str) -> bool:
    status = ReadingStatus.READ if collection == S.READ else ReadingStatus.TO_READ
    return collection in book.collections or book.status == status


def _missing_description_state(book: AnalysisBook) -> str:
    state = book.field_states.get(S.DESCRIPTION)
    if state is not C.NONE and state != FieldState.PRESENT:
        return state.value
    if book.description is C.NONE:
        return FieldState.UNAVAILABLE.value
    if not book.description.strip():
        return FieldState.EMPTY.value
    return S.CONTENT_ANALYSIS_UNVERIFIED


def _finding(
    data: AnalysisInput,
    metric: str,
    population: str,
    value: dict[str, JsonValue],
    known: tuple[_Description, ...],
    missing: int,
    limitations: tuple[str, ...],
    supporting: tuple[str, ...],
) -> Finding:
    return Finding(
        metric_id=metric,
        population=population,
        value=value,
        unit=S.CONTENT_ANALYSIS_UNIT,
        sample_size=len(known),
        missing_count=missing,
        period=data.as_of,
        reliability=S.CONTENT_ANALYSIS_RELIABILITY,
        uncertainty={
            S.CONTENT_ANALYSIS_RULE_VERSION: S.CONTENT_ANALYSIS_VERSION,
            S.CONTENT_ANALYSIS_AS_OF: data.as_of,
        },
        supporting_books=supporting,
        limitations=limitations,
        calculation_version=data.manifest.calculation_version,
        source_snapshot_ids=tuple(sorted({item.snapshot_id for item in data.manifest.snapshots})),
    )


def _capability(
    metric: str, available: int, total: int, has_support: bool, settings: AnalyticsSettings
) -> Capability:
    if available < settings.min_group_size:
        state = C.AnalyticsCapability.NEEDS_ENRICHMENT
        reason = S.CONTENT_ANALYSIS_UNKNOWN
    elif not has_support:
        state = C.AnalyticsCapability.NEEDS_OBSERVATIONS
        reason = S.CONTENT_ANALYSIS_THIN
    else:
        state = (
            C.AnalyticsCapability.SUPPORTED if available == total else C.AnalyticsCapability.SUBSET
        )
        reason = S.CONTENT_ANALYSIS_SUPPORTED
    return Capability(
        metric_id=metric, state=state, available=available, population=total, reason=reason
    )


def _collection_analysis(
    data: AnalysisInput,
    settings: AnalyticsSettings,
    collection: str,
    books: tuple[AnalysisBook, ...],
    descriptions: dict[int, _Description],
    rules: tuple[tuple[str, Pattern[str]], ...],
    metric_template: str,
) -> tuple[Finding, Capability]:
    known = tuple(descriptions[book.work_id] for book in books if book.work_id in descriptions)
    missing_states = Counter(
        _missing_description_state(book) for book in books if book.work_id not in descriptions
    )
    groups: dict[str, JsonValue] = {}
    matched: set[str] = set()
    supporting: set[str] = set()
    suppressed = C.ZERO
    for family, pattern in rules:
        proofs = [
            proof for description in known if (proof := _proof(description, pattern)) is not C.NONE
        ]
        works = {str(proof[S.CONTENT_ANALYSIS_WORK]) for proof in proofs}
        matched.update(works)
        if len(works) < settings.min_group_size:
            suppressed += C.ONE
            continue
        supporting.update(works)
        groups[family] = {
            S.CONTENT_ANALYSIS_COUNT: len(works),
            S.CONTENT_ANALYSIS_SHARE: len(works) / len(known),
            S.CONTENT_ANALYSIS_WORKS: [work for work in sorted(works)],
            S.CONTENT_ANALYSIS_RULE_PATTERN: pattern.pattern,
            S.CONTENT_ANALYSIS_PROOF: list(proofs[: C.CONTENT_ANALYSIS_MAX_PROOFS]),
        }
    metric = metric_template.format(collection=collection)
    limitations: tuple[str, ...] = C.CONTENT_ANALYSIS_LIMITATIONS
    if metric_template == S.CONTENT_ANALYSIS_HUNGERS:
        limitations += (S.CONTENT_ANALYSIS_HUNGER_LIMIT,)
    finding = _finding(
        data,
        metric,
        collection,
        {
            S.CONTENT_ANALYSIS_KNOWN: len(known),
            S.CONTENT_ANALYSIS_MISSING: dict(sorted(missing_states.items())),
            S.CONTENT_ANALYSIS_GROUPS: groups,
            S.CONTENT_ANALYSIS_UNMATCHED: len(known) - len(matched),
            S.CONTENT_ANALYSIS_THRESHOLD: settings.min_group_size,
            S.CONTENT_ANALYSIS_SUPPRESSED: suppressed,
        },
        known,
        len(books) - len(known),
        limitations,
        tuple(sorted(supporting)),
    )
    return finding, _capability(metric, len(known), len(books), bool(groups), settings)


def build_content_analysis(
    data: AnalysisInput, settings: AnalyticsSettings
) -> tuple[tuple[Finding, ...], tuple[Capability, ...]]:
    unique = {book.work_id: book for book in reversed(data.books) if _in_collection(book, S.READ)}
    books = tuple(unique[work_id] for work_id in sorted(unique))
    descriptions = {
        book.work_id: description
        for book in books
        if (description := _description(book)) is not C.NONE
    }
    findings: list[Finding] = []
    capabilities: list[Capability] = []
    for collection in C.CONTENT_ANALYSIS_COLLECTIONS:
        population = tuple(book for book in books if _in_collection(book, collection))
        for rules, metric in (
            (C.CONTENT_ANALYSIS_THEME_RULES, S.CONTENT_ANALYSIS_THEMES),
            (C.CONTENT_ANALYSIS_HUNGER_RULES, S.CONTENT_ANALYSIS_HUNGERS),
        ):
            finding, capability = _collection_analysis(
                data, settings, collection, population, descriptions, rules, metric
            )
            findings.append(finding)
            capabilities.append(capability)
    return tuple(findings), tuple(capabilities)
