from __future__ import annotations

from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.statistics import build_watchlist
from bookystats.domain.analytics import AnalyticsReport, AnalyticsSettings
from bookystats.domain.models import SyncState
from bookystats.domain.products import ProductReceipt
from bookystats.persistence import products as products_module
from bookystats.persistence.products import ReportBundleError, ReportBundleStore
from tests.application.test_statistics import _book, _data, _taste


def _report(report_id: int = C.ONE) -> AnalyticsReport:
    data = _data(_book(C.ONE, C.FOUR))
    taste = _taste(data)
    return AnalyticsReport(
        report_id=report_id,
        as_of=data.as_of,
        manifest=data.manifest,
        taste=taste,
        watchlist=build_watchlist(data, AnalyticsSettings(), taste, key=S.TEST),
    )


def _publish(store: ReportBundleStore, report: AnalyticsReport) -> ProductReceipt:
    return store.publish(
        report,
        recommendations=S.PROD_TEST_JSON,
        metadata_quality=S.PROD_TEST_JSON,
        summary=ProductReceipt(state=SyncState.COMPLETE, analytics_report_id=report.report_id),
        render_pdf=lambda path: path.write_bytes(S.PROD_TEST_PDF),
    )


def test_complete_bundle_is_verified_and_immutable(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    receipt = _publish(store, report)
    assert store.latest() == receipt
    assert store.for_report(report) == receipt
    assert receipt.pdf_file is not C.NONE
    assert Path(receipt.pdf_file).read_bytes() == S.PROD_TEST_PDF
    with pytest.raises(ReportBundleError, match=S.PROD_INVALID_BUNDLE):
        _publish(store, report)
    assert store.latest() == receipt


@pytest.mark.parametrize(S.PROD_TEST_FILENAME, C.PROD_BUNDLE_FILES)
def test_status_rejects_modified_bundle_files(tmp_path: Path, filename: str) -> None:
    store = ReportBundleStore(tmp_path)
    receipt = _publish(store, _report())
    assert receipt.output_directory is not C.NONE
    (Path(receipt.output_directory) / filename).write_bytes(S.PROD_TEST_CORRUPT)
    with pytest.raises(ReportBundleError, match=S.PROD_INVALID_BUNDLE):
        store.latest()


def test_pdf_failure_keeps_previous_bundle_and_removes_only_staging(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    first = _publish(store, _report())
    pointer = store.root / S.PROD_LATEST_FILE
    saved_pointer = pointer.read_bytes()

    def fail(path: Path) -> None:
        path.write_bytes(S.PROD_TEST_CORRUPT)
        raise OSError(S.PROD_TEST_FAILURE)

    report = _report(C.TWO)
    with pytest.raises(OSError, match=S.PROD_TEST_FAILURE):
        store.publish(
            report,
            recommendations=S.PROD_TEST_JSON,
            metadata_quality=S.PROD_TEST_JSON,
            summary=ProductReceipt(state=SyncState.COMPLETE, analytics_report_id=report.report_id),
            render_pdf=fail,
        )
    assert pointer.read_bytes() == saved_pointer
    assert store.latest() == first
    assert len(tuple(store.root.iterdir())) == C.TWO


def test_interrupted_pointer_publication_recovers_verified_finished_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ReportBundleStore(tmp_path)
    first = _publish(store, _report())
    write = products_module.atomic_write
    report = _report(C.TWO)

    def fail_pointer(path: Path, content: str) -> None:
        if path.name == S.PROD_LATEST_FILE:
            raise OSError(S.PROD_TEST_FAILURE)
        write(path, content)

    monkeypatch.setattr(products_module, S.PROD_TEST_ATOMIC_WRITE, fail_pointer)
    with pytest.raises(OSError, match=S.PROD_TEST_FAILURE):
        _publish(store, report)
    assert store.latest() == first
    monkeypatch.setattr(products_module, S.PROD_TEST_ATOMIC_WRITE, write)
    recovered = store.for_report(report)
    assert recovered is not C.NONE
    assert recovered.analytics_report_id == C.TWO
    assert store.latest() == recovered


def test_manifest_or_generation_mismatch_is_not_reused(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    receipt = _publish(store, report)
    changed = report.model_copy(
        update={
            S.AN_CALC_TEST_MANIFEST_FIELD: report.manifest.model_copy(
                update={S.AN_ACCOUNT_FINGERPRINT: S.DIFFERENT_BOOK}
            )
        }
    )
    with pytest.raises(ReportBundleError, match=S.PROD_INPUT_MISMATCH):
        store.for_report(changed)
    assert store.latest() == receipt
    assert receipt.manifest_file is not C.NONE
    path = Path(receipt.manifest_file)
    path.write_bytes(path.read_bytes() + S.NEWLINE.encode(S.UTF_8))
    with pytest.raises(ReportBundleError, match=S.PROD_INVALID_BUNDLE):
        store.latest()
