from __future__ import annotations

import csv
import hashlib
import io

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.exports.csv_import import ExportConnector
from bookystats.domain.models import (
    Account,
    BookRecord,
    CollectionSnapshot,
    Observation,
    Source,
)
from bookystats.persistence.raw import RawDocument


def account(source: Source = Source.GOODREADS) -> Account:
    account_id, profile = C.TEST_IMPORT_ACCOUNT_VALUES[source]
    return Account(source=source, account_id=account_id, profile_url=profile)


def document(body: bytes, source: Source = Source.GOODREADS) -> RawDocument:
    return RawDocument(
        id=S.TEST_IMPORT_DOCUMENT_ID,
        source=source,
        account_id=account(source).account_id,
        body=body,
        media_type=S.TEST_IMPORT_CSV_MEDIA,
        origin=S.TEST_IMPORT_ORIGIN,
        captured_at=S.TEST_IMPORT_CAPTURED_AT,
        sha256=hashlib.sha256(body).hexdigest(),
    )


def csv_body(source: Source, rows: list[dict[str, str]], *, bom: bool = C.FALSE) -> bytes:
    output = io.StringIO(newline=S.EMPTY)
    headers = tuple(
        dict.fromkeys(
            [
                *C.TEST_IMPORT_DEFAULT_HEADERS[source],
                *(header for row in rows for header in row),
            ]
        )
    )
    writer = csv.writer(output, lineterminator=S.NEWLINE)
    writer.writerow(headers)
    writer.writerows([row.get(header, S.EMPTY) for header in headers] for row in rows)
    return output.getvalue().encode(S.UTF_8_SIG if bom else S.UTF_8)


def collect(source: Source, rows: list[dict[str, str]]) -> CollectionSnapshot:
    return ExportConnector(document(csv_body(source, rows), source)).collect(account(source))


def observation(book: BookRecord, field: str) -> Observation:
    return next(value for value in book.observations if value.field == field)
