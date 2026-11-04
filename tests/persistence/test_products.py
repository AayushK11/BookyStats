from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.statistics import build_watchlist
from bookystats.domain.analytics import AnalyticsReport, AnalyticsSettings
from bookystats.domain.models import SyncState
from bookystats.domain.products import ProductReceipt
from bookystats.domain.reader_report import (
    Chapter,
    Cover,
    ProseBlock,
    ReaderReport,
    manifest_digest,
)
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


def _write_pdf(path: Path) -> object:
    return path.write_bytes(S.PROD_TEST_PDF)


def _publish(store: ReportBundleStore, report: AnalyticsReport) -> ProductReceipt:
    return store.publish(
        report,
        recommendations=S.PROD_TEST_JSON,
        metadata_quality=S.PROD_TEST_JSON,
        summary=ProductReceipt(state=SyncState.COMPLETE, analytics_report_id=report.report_id),
        render_pdf=lambda path: path.write_bytes(S.PROD_TEST_PDF),
    )


def _typed(report: AnalyticsReport) -> ReaderReport:
    return ReaderReport(
        model_version=C.RPT_MODEL_VERSION,
        analysis_report_id=report.report_id,
        as_of=report.as_of,
        manifest_digest=manifest_digest(report.manifest),
        calculation_version=report.manifest.calculation_version,
        cover=Cover(eyebrow=S.TEST, title=S.TEST, subtitle=S.TEST, as_of=report.as_of, heroes=()),
        chapters=(Chapter(key=S.TEST, title=S.TEST, blocks=(ProseBlock(paragraphs=(S.TEST,)),)),),
    )


def _publish_layout(
    store: ReportBundleStore,
    report: AnalyticsReport,
    *,
    changes: dict[str, object] | None = C.NONE,
    layout: int = C.RPT_LAYOUT_VERSION,
    render: Callable[[Path], object] = _write_pdf,
    text: str | None = C.NONE,
) -> ProductReceipt:
    typed = _typed(report).model_copy(update=changes or {})
    return store.publish(
        report,
        recommendations=S.PROD_TEST_JSON,
        metadata_quality=S.PROD_TEST_JSON,
        summary=ProductReceipt(state=SyncState.COMPLETE, analytics_report_id=report.report_id),
        render_pdf=render,
        reader_report=typed.model_dump_json(indent=C.TWO) if text is C.NONE else text,
        layout_version=layout,
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


def test_each_layout_version_has_its_own_verified_bundle(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    legacy = _publish(store, report)
    current = _publish_layout(store, report)
    newer_layout = C.RPT_LAYOUT_VERSION + C.ONE
    newer = _publish_layout(store, report, layout=newer_layout)
    directories = {receipt.output_directory for receipt in (legacy, current, newer)}
    assert len(directories) == C.THREE
    assert store.latest() == newer
    for receipt, layout in ((current, C.RPT_LAYOUT_VERSION), (newer, newer_layout)):
        assert receipt.output_directory is not C.NONE
        typed = ReaderReport.model_validate_json(
            (Path(receipt.output_directory) / S.RPT_BUNDLE_FILE).read_bytes()
        )
        assert typed.manifest_digest == manifest_digest(report.manifest)
        assert store.for_report(report, layout_version=layout) == receipt
        assert store.latest() == receipt
    assert store.for_report(report) == legacy
    assert store.latest() == legacy
    assert store.for_report(_report(C.TWO), layout_version=C.RPT_LAYOUT_VERSION) is C.NONE


def test_new_report_directory_does_not_expose_rendering_versions(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    layout = C.PROD_READER_DIRECTORY_VERSION
    receipt = _publish_layout(store, report, layout=layout)
    assert receipt.output_directory is not C.NONE
    assert Path(receipt.output_directory).name == S.PROD_BUNDLE_NAME.format(
        report_id=report.report_id
    )
    assert store.latest() == receipt
    assert store.for_report(report, layout_version=layout) == receipt
    assert store.for_report(report) is C.NONE
    newer = _publish_layout(store, report, layout=layout + C.ONE)
    assert newer.output_directory != receipt.output_directory
    assert store.latest() == newer
    assert store.for_report(report, layout_version=layout) == receipt


def test_existing_layout_directories_remain_readable_beside_new_report(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    historical = _publish_layout(store, report, layout=C.THREE)
    assert historical.output_directory is not C.NONE
    directory = Path(historical.output_directory)
    original = {path.name: path.read_bytes() for path in directory.iterdir()}
    current = _publish_layout(store, report, layout=C.PROD_READER_DIRECTORY_VERSION)
    assert store.latest() == current
    assert store.for_report(report, layout_version=C.THREE) == historical
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == original


@pytest.mark.parametrize(S.PROD_TEST_FILENAME, C.PROD_BUNDLE_FILES_V2)
def test_status_rejects_modified_layout_bundle_files(tmp_path: Path, filename: str) -> None:
    store = ReportBundleStore(tmp_path)
    receipt = _publish_layout(store, _report())
    assert receipt.output_directory is not C.NONE
    (Path(receipt.output_directory) / filename).write_bytes(S.PROD_TEST_CORRUPT)
    with pytest.raises(ReportBundleError, match=S.PROD_INVALID_BUNDLE):
        store.latest()


@pytest.mark.parametrize(S.RPT_TEST_CHANGE_ARGS, C.RPT_TEST_PROVENANCE_CHANGES)
def test_reader_report_with_other_provenance_is_refused_before_writing(
    tmp_path: Path, field: str, value: object
) -> None:
    store = ReportBundleStore(tmp_path)
    with pytest.raises(ReportBundleError, match=S.PROD_INPUT_MISMATCH):
        _publish_layout(store, _report(), changes={field: value})
    assert not store.root.exists()


def test_unreadable_reader_report_is_refused_before_writing(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    with pytest.raises(ReportBundleError, match=S.PROD_INPUT_MISMATCH):
        _publish_layout(store, _report(), text=S.PROD_TEST_JSON)
    assert not store.root.exists()


@pytest.mark.parametrize(S.RPT_TEST_MISUSE_ARGS, C.RPT_TEST_LAYOUT_MISUSE)
def test_reader_report_is_required_exactly_for_layouts_that_render_it(
    tmp_path: Path, layout: int, included: bool
) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    with pytest.raises(ReportBundleError, match=S.PROD_INPUT_MISMATCH):
        store.publish(
            report,
            recommendations=S.PROD_TEST_JSON,
            metadata_quality=S.PROD_TEST_JSON,
            summary=ProductReceipt(state=SyncState.COMPLETE, analytics_report_id=report.report_id),
            render_pdf=_write_pdf,
            reader_report=_typed(report).model_dump_json() if included else C.NONE,
            layout_version=layout,
        )
    assert not store.root.exists()


def test_failed_layout_render_keeps_the_legacy_bundle_active(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    legacy = _publish(store, report)
    pointer = store.root / S.PROD_LATEST_FILE
    saved_pointer = pointer.read_bytes()

    def fail(path: Path) -> None:
        path.write_bytes(S.PROD_TEST_CORRUPT)
        raise OSError(S.PROD_TEST_FAILURE)

    with pytest.raises(OSError, match=S.PROD_TEST_FAILURE):
        _publish_layout(store, report, render=fail)
    assert pointer.read_bytes() == saved_pointer
    assert store.latest() == legacy
    assert store.for_report(report, layout_version=C.RPT_LAYOUT_VERSION) is C.NONE
    assert len(tuple(store.root.iterdir())) == C.TWO


def test_layout_bundle_for_other_manifest_inputs_is_not_reused(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    receipt = _publish_layout(store, report)
    changed = report.model_copy(
        update={
            S.AN_CALC_TEST_MANIFEST_FIELD: report.manifest.model_copy(
                update={S.AN_ACCOUNT_FINGERPRINT: S.DIFFERENT_BOOK}
            )
        }
    )
    with pytest.raises(ReportBundleError, match=S.PROD_INPUT_MISMATCH):
        store.for_report(changed, layout_version=C.RPT_LAYOUT_VERSION)
    assert store.latest() == receipt


def test_baseline_format_bundle_without_layout_fields_still_reads(tmp_path: Path) -> None:
    store = ReportBundleStore(tmp_path)
    report = _report()
    receipt = _publish(store, report)
    assert receipt.manifest_file is not C.NONE
    manifest_path = Path(receipt.manifest_file)
    manifest = json.loads(manifest_path.read_bytes())
    del manifest[S.RPT_TEST_LAYOUT_FIELD]
    manifest_path.write_bytes(json.dumps(manifest, indent=C.TWO).encode(S.UTF_8))
    pointer_path = store.root / S.PROD_LATEST_FILE
    pointer = json.loads(pointer_path.read_bytes())
    del pointer[S.RPT_TEST_LAYOUT_FIELD]
    pointer[S.RPT_TEST_POINTER_HASH_FIELD] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    pointer_path.write_bytes(json.dumps(pointer, indent=C.TWO).encode(S.UTF_8))
    assert store.latest() == receipt
    assert store.for_report(report) == receipt
