from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import PureWindowsPath

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import SourceReceipt, SyncReceipt
from bookystats.domain.models import Issue, Verification


def _issue_lines(issues: Sequence[Issue], limit: int | None) -> list[str]:
    groups = list(Counter((issue.code, issue.message) for issue in issues).items())
    shown = groups if limit is C.NONE else groups[: max(C.ZERO, limit)]
    lines = [
        (S.REPORT_REPEATED_ISSUE_LINE if count > C.ONE else S.REPORT_ISSUE_LINE).format(
            code=code, message=message, count=count
        )
        for (code, message), count in shown
    ]
    remaining = len(issues) - sum(count for _, count in shown)
    if remaining:
        lines.append(S.REPORT_MORE_ISSUES_LINE.format(count=remaining))
    return lines


def source_lines(source: SourceReceipt, *, issue_limit: int | None) -> list[str]:
    lines = [
        S.REPORT_SOURCE_LINE.format(
            source=source.source.value,
            collection=source.collection,
            state=source.state.value,
            records=source.records,
            pages=source.pages,
        )
    ]
    if source.publication is not C.NONE:
        counts = source.publication
        lines.append(
            S.REPORT_PUBLICATION_LINE.format(
                added=counts.added,
                updated=counts.updated,
                unchanged=counts.unchanged,
                removed=counts.removed,
            )
        )
    lines.extend(_issue_lines(source.issues, issue_limit))
    return lines


def receipt_lines(receipt: SyncReceipt, *, issue_limit: int | None) -> list[str]:
    lines = [S.REPORT_RUN_HEADING.format(run_id=receipt.run_id, state=receipt.state.value)]
    for source in receipt.sources:
        lines.extend(source_lines(source, issue_limit=issue_limit))
    for metadata in receipt.metadata:
        lines.append(
            S.REPORT_METADATA_LINE.format(
                provider=metadata.provider.value,
                state=metadata.state.value,
                processed=metadata.processed,
                deferred=metadata.deferred,
            )
        )
        lines.extend(_issue_lines(metadata.issues, issue_limit))
    if receipt.analytics is not C.NONE:
        analysis = receipt.analytics
        lines.append(
            S.AN_RECEIPT_LINE.format(
                state=analysis.state.value,
                report_id=analysis.report_id,
                findings=analysis.findings,
                rated=analysis.rated_read,
                read=analysis.read_works,
            )
        )
        lines.append(
            S.AN_REUSE_LINE.format(taste=analysis.taste_reused, watchlist=analysis.watchlist_reused)
        )
        lines.append(S.AN_EXECUTION_LINE.format(mode=analysis.execution_mode))
        lines.extend(_issue_lines(analysis.issues, issue_limit))
    if any(source.input_kind == S.INPUT_FILE for source in receipt.sources):
        lines.append(S.CLI_FILE_SCOPE)
    elif not receipt.account_sync_complete:
        lines.append(S.CLI_PRINT_RECEIPT_LAST_GOOD_SOURCE_SNAPSHOTS_REMAIN_AVAILABLE_THIS)
    return lines


def verification_lines(verification: Verification) -> list[str]:
    lines = [S.REPORT_CHECKS_HEADING]
    lines.extend(
        S.REPORT_CHECK_LINE.format(
            marker=C.VERIFICATION_MARKERS[check.result],
            source=check.source.value,
            name=check.name.value.replace(S.UNDERSCORE, S.SPACE),
            detail=check.detail,
        )
        for check in verification.checks
    )
    lines.append(S.REPORT_RESULT_LINE.format(result=verification.result.value.upper()))
    lines.append(C.VERIFICATION_EXPLANATIONS[verification.result])
    return lines


def run_lines(receipt: SyncReceipt, *, issue_limit: int | None) -> list[str]:
    lines = receipt_lines(receipt, issue_limit=issue_limit)
    if receipt.verification is not C.NONE:
        lines.extend([S.EMPTY, *verification_lines(receipt.verification)])
    return lines


def _mapping(value: JsonValue) -> Mapping[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _sequence(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _text(value: JsonValue, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _number(value: JsonValue) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else C.ZERO


def _location(path: JsonValue, size: JsonValue) -> str:
    if not isinstance(path, str):
        return S.STATUS_NOT_CREATED
    if isinstance(size, int) and not isinstance(size, bool):
        megabytes = S.STATUS_SIZE.format(megabytes=size / C.BYTES_PER_MEGABYTE)
        return S.STATUS_LOCATION_WITH_SIZE.format(path=PureWindowsPath(path).name, size=megabytes)
    return PureWindowsPath(path).name


def _last_run(value: JsonValue) -> str:
    run = _mapping(value)
    if not run:
        return S.STATUS_NONE_YET
    return S.STATUS_LAST_RUN_VALUE.format(
        run_id=_number(run.get(S.RUN_ID)),
        state=_text(run.get(S.STATE), S.STATUS_UNKNOWN),
    )


def status_lines(report: Mapping[str, JsonValue]) -> list[str]:
    lines = [
        S.CLI_PRINT_STATUS_BOOKYSTATS_STATUS_LOCAL_DATA_NO_SOURCE_REQUESTS,
        S.STATUS_LAST_RUN_LINE.format(value=_last_run(report.get(S.LAST_RUN))),
    ]
    analysis = _mapping(report.get(S.AN_ANALYTICS))
    if analysis:
        lines.append(
            S.AN_STATUS_LINE.format(
                report_id=_number(analysis.get(S.AN_REPORT_ID)),
                created_at=_text(analysis.get(S.AN_CREATED_AT), S.STATUS_UNKNOWN),
            )
        )
    inputs = _sequence(report.get(S.CSV_INPUTS))
    if inputs:
        lines.extend(
            [
                S.EMPTY,
                S.STATUS_CSV_HEADING,
                S.STATUS_CSV_CONFIGURATION.format(
                    path=_text(report.get(S.CSV_CONFIGURATION_PATH), S.CONFIG_JSON)
                ),
            ]
        )
        for item in inputs:
            entry = _mapping(item)
            path = entry.get(S.CSV_INPUT_PATH)
            lines.append(
                S.STATUS_CSV_LINE.format(
                    source=_text(entry.get(S.SOURCE), S.STATUS_UNKNOWN),
                    collection=_text(entry.get(S.COLLECTION), S.LIBRARY),
                    filename=PureWindowsPath(path).name
                    if isinstance(path, str)
                    else S.STATUS_CSV_NOT_CONFIGURED,
                    state=S.STATUS_CSV_READY
                    if entry.get(S.CSV_INPUT_EXISTS) is C.TRUE
                    else S.STATUS_CSV_MISSING,
                )
            )
    library = _mapping(report.get(S.LIBRARY))
    if library:
        lines.append(
            S.STATUS_LIBRARY_COUNTS_LINE.format(
                entries=_number(library.get(S.SOURCE_RECORDS)),
                works=_number(library.get(S.WORKS)),
                events=_number(library.get(S.READING_EVENTS)),
            )
        )
    lines.extend([S.EMPTY, S.STATUS_SOURCES_HEADING])
    sources = [_mapping(entry) for entry in _sequence(report.get(S.SOURCES))]
    if not sources:
        lines.append(S.STATUS_NONE_LINE)
    else:
        lines.append(S.STATUS_SOURCE_HEADER)
    lines.extend(
        S.STATUS_SOURCE_LINE.format(
            source=_text(entry.get(S.SOURCE), S.STATUS_UNKNOWN),
            collection=_text(entry.get(S.COLLECTION), S.STATUS_UNKNOWN),
            state=_text(entry.get(S.STATE), S.STATUS_UNKNOWN),
            count=_number(entry.get(S.ACTIVE_COUNT)),
        )
        for entry in sources
    )
    if any(entry.get(S.STATE) != S.COMPLETE for entry in sources):
        lines.extend([S.EMPTY, S.STATUS_RETAINED_SNAPSHOTS])
    providers = _mapping(report.get(S.METADATA))
    if providers:
        lines.extend([S.EMPTY, S.STATUS_METADATA_HEADING, S.STATUS_METADATA_HEADER])
        for provider, value in providers.items():
            entry = _mapping(value)
            lines.append(
                S.STATUS_METADATA_LINE.format(
                    provider=provider,
                    matched=_number(entry.get(S.SELECTED)),
                    unmatched=_number(entry.get(S.UNRESOLVED)),
                    success=_text(entry.get(S.LAST_SUCCESS_AT), S.STATUS_NEVER),
                )
            )
    schedule = _mapping(report.get(S.SCHEDULE))
    lines.extend(
        [
            S.EMPTY,
            S.STATUS_SCHEDULE_LINE.format(
                state=_text(schedule.get(S.STATE), S.STATUS_UNKNOWN).replace(S.UNDERSCORE, S.SPACE)
            ),
        ]
    )
    lines.append(
        S.STATUS_GOOGLE_KEY_LINE.format(
            state=S.STATUS_KEY_SET
            if report.get(S.GOOGLE_BOOKS_KEY_CONFIGURED) is C.TRUE
            else S.STATUS_OAUTH_SAVED
            if report.get(S.GOOGLE_BOOKS_OAUTH_SAVED) is C.TRUE
            else S.STATUS_KEY_NOT_SET
        )
    )
    lines.extend(
        [
            S.EMPTY,
            S.STATUS_DATA_FOLDER_LINE.format(path=_text(report.get(S.DATA_DIRECTORY), S.EMPTY)),
            S.STATUS_RAW_ARCHIVE_LINE.format(
                location=_location(report.get(S.CLI_RAW_ARCHIVE), report.get(S.RAW_ARCHIVE_BYTES))
            ),
            S.STATUS_LIBRARY_DATABASE_LINE.format(
                location=_location(report.get(S.LIBRARY_DATABASE), report.get(S.LIBRARY_BYTES))
            ),
            S.STATUS_LATEST_LOG_LINE.format(
                location=PureWindowsPath(_text(report.get(S.LATEST_LOG), S.STATUS_NONE_YET)).name
            ),
        ]
    )
    return lines
