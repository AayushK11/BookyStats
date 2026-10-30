from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.models import Issue, Verification
from bookystats.sync import SyncReceipt


def _issue_lines(issues: Sequence[Issue], limit: int | None) -> list[str]:
    shown = issues if limit is C.NONE else issues[:limit]
    lines = [S.REPORT_ISSUE_LINE.format(code=issue.code, message=issue.message) for issue in shown]
    if len(shown) < len(issues):
        lines.append(S.REPORT_MORE_ISSUES_LINE.format(count=len(issues) - len(shown)))
    return lines


def receipt_lines(receipt: SyncReceipt, *, issue_limit: int | None) -> list[str]:
    lines = [S.REPORT_RUN_HEADING.format(run_id=receipt.run_id, state=receipt.state.value)]
    for source in receipt.sources:
        lines.append(
            S.REPORT_SOURCE_LINE.format(
                source=source.source.value,
                state=source.state.value,
                records=source.records,
                pages=source.pages,
            )
        )
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
        return S.STATUS_LOCATION_WITH_SIZE.format(path=path, size=megabytes)
    return path


def _last_run(value: JsonValue) -> str:
    run = _mapping(value)
    if not run:
        return S.STATUS_NONE_YET
    return S.STATUS_LAST_RUN_VALUE.format(
        run_id=_number(run.get(S.RUN_ID)),
        state=_text(run.get(S.STATE), S.STATUS_UNKNOWN),
        finished=_text(run.get(S.FINISHED_AT), S.STATUS_UNKNOWN),
    )


def status_lines(report: Mapping[str, JsonValue]) -> list[str]:
    lines = [
        S.CLI_PRINT_STATUS_BOOKYSTATS_STATUS_LOCAL_DATA_NO_SOURCE_REQUESTS,
        S.STATUS_DATA_FOLDER_LINE.format(path=_text(report.get(S.DATA_DIRECTORY), S.EMPTY)),
        S.STATUS_RAW_ARCHIVE_LINE.format(
            location=_location(report.get(S.CLI_RAW_ARCHIVE), report.get(S.RAW_ARCHIVE_BYTES))
        ),
        S.STATUS_LIBRARY_DATABASE_LINE.format(
            location=_location(report.get(S.LIBRARY_DATABASE), report.get(S.LIBRARY_BYTES))
        ),
        S.STATUS_LATEST_LOG_LINE.format(
            location=_text(report.get(S.LATEST_LOG), S.STATUS_NONE_YET)
        ),
        S.STATUS_LAST_RUN_LINE.format(value=_last_run(report.get(S.LAST_RUN))),
        S.STATUS_SOURCES_HEADING,
    ]
    sources = [_mapping(entry) for entry in _sequence(report.get(S.SOURCES))]
    if not sources:
        lines.append(S.STATUS_NONE_LINE)
    lines.extend(
        S.STATUS_SOURCE_LINE.format(
            source=_text(entry.get(S.SOURCE), S.STATUS_UNKNOWN),
            state=_text(entry.get(S.STATE), S.STATUS_UNKNOWN),
            count=_number(entry.get(S.ACTIVE_COUNT)),
            success=_text(entry.get(S.LAST_SUCCESS_AT), S.STATUS_NEVER),
        )
        for entry in sources
    )
    library = _mapping(report.get(S.LIBRARY))
    if library:
        lines.append(
            S.STATUS_LIBRARY_COUNTS_LINE.format(
                entries=_number(library.get(S.SOURCE_RECORDS)),
                works=_number(library.get(S.WORKS)),
                editions=_number(library.get(S.EDITIONS)),
                events=_number(library.get(S.READING_EVENTS)),
            )
        )
    providers = _mapping(report.get(S.METADATA))
    if providers:
        lines.append(S.STATUS_METADATA_HEADING)
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
    lines.append(
        S.STATUS_SCHEDULE_LINE.format(
            state=_text(schedule.get(S.STATE), S.STATUS_UNKNOWN).replace(S.UNDERSCORE, S.SPACE)
        )
    )
    lines.append(
        S.STATUS_GOOGLE_KEY_LINE.format(
            state=S.STATUS_KEY_SET
            if report.get(S.GOOGLE_BOOKS_KEY_CONFIGURED) is C.TRUE
            else S.STATUS_KEY_NOT_SET
        )
    )
    return lines
