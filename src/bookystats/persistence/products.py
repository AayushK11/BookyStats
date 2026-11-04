from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalyticsReport
from bookystats.domain.errors import BookyError
from bookystats.domain.models import SyncState
from bookystats.domain.products import BundleManifest, BundlePointer, ProductReceipt
from bookystats.domain.reader_report import ReaderReport, manifest_digest
from bookystats.runtime.config import atomic_write


class ReportBundleError(BookyError):
    pass


def _digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ReportBundleError(S.PROD_INVALID_BUNDLE)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy(layout_version: int) -> bool:
    return layout_version == C.RPT_LEGACY_LAYOUT_VERSION


def _schema(layout_version: int) -> int:
    return C.ONE if _legacy(layout_version) else C.TWO


def _files(layout_version: int) -> tuple[str, ...]:
    return C.PROD_BUNDLE_FILES if _legacy(layout_version) else C.PROD_BUNDLE_FILES_V2


class ReportBundleStore:
    def __init__(self, directory: Path) -> None:
        self.root = directory / S.PROD_REPORTS_FOLDER

    def _path(self, report_id: int, layout_version: int = C.RPT_LEGACY_LAYOUT_VERSION) -> Path:
        if _legacy(layout_version):
            return self.root / S.PROD_BUNDLE_NAME.format(report_id=report_id)
        if layout_version >= C.PROD_READER_DIRECTORY_VERSION:
            primary = self.root / S.PROD_BUNDLE_NAME.format(report_id=report_id)
            revision = self.root / S.PROD_BUNDLE_REVISION_NAME.format(
                report_id=report_id, revision=layout_version
            )
            if primary.is_symlink():
                raise ReportBundleError(S.PROD_INVALID_BUNDLE)
            if not primary.exists():
                return revision if revision.exists() or revision.is_symlink() else primary
            try:
                manifest = BundleManifest.model_validate_json(
                    (primary / S.PROD_MANIFEST_FILE).read_bytes()
                )
            except (ValidationError, FileNotFoundError) as exc:
                raise ReportBundleError(S.PROD_INVALID_BUNDLE) from exc
            if manifest.analytics_report_id != report_id:
                raise ReportBundleError(S.PROD_INVALID_BUNDLE)
            return primary if manifest.layout_version == layout_version else revision
        return self.root / S.RPT_BUNDLE_LAYOUT_NAME.format(
            report_id=report_id, layout=layout_version
        )

    def _read(self, report_id: int, layout_version: int) -> BundleManifest:
        directory = self._path(report_id, layout_version)
        if directory.is_symlink():
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        try:
            manifest = BundleManifest.model_validate_json(
                (directory / S.PROD_MANIFEST_FILE).read_bytes()
            )
        except (ValidationError, FileNotFoundError) as exc:
            raise ReportBundleError(S.PROD_INVALID_BUNDLE) from exc
        if (
            manifest.analytics_report_id != report_id
            or manifest.layout_version != layout_version
            or manifest.schema_version != _schema(layout_version)
            or manifest.summary.analytics_report_id != report_id
            or manifest.summary.state != SyncState.COMPLETE
            or set(manifest.files) != set(_files(layout_version))
        ):
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        if any(_digest(directory / name) != checksum for name, checksum in manifest.files.items()):
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        if not _legacy(layout_version):
            self._check_reader_report(directory, manifest)
        return manifest

    def _check_reader_report(self, directory: Path, manifest: BundleManifest) -> None:
        try:
            typed = ReaderReport.model_validate_json((directory / S.RPT_BUNDLE_FILE).read_bytes())
        except (ValidationError, FileNotFoundError) as exc:
            raise ReportBundleError(S.PROD_INVALID_BUNDLE) from exc
        if (
            typed.analysis_report_id != manifest.analytics_report_id
            or typed.manifest_digest != manifest_digest(manifest.analysis_manifest)
        ):
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)

    def _receipt(self, manifest: BundleManifest) -> ProductReceipt:
        directory = self._path(manifest.analytics_report_id, manifest.layout_version)
        return manifest.summary.model_copy(
            update={
                S.PROD_OUTPUT_DIRECTORY: str(directory),
                S.PROD_PDF_PATH: str(directory / S.PROD_PDF_FILE),
                S.PROD_QUALITY_PATH: str(directory / S.PROD_QUALITY_FILE),
                S.PROD_RECOMMENDATIONS_PATH: str(directory / S.PROD_RECOMMENDATIONS_FILE),
                S.PROD_MANIFEST_PATH: str(directory / S.PROD_MANIFEST_FILE),
            }
        )

    def latest(self, *, current: AnalyticsReport | None = C.NONE) -> ProductReceipt | None:
        pointer_path = self.root / S.PROD_LATEST_FILE
        if not pointer_path.exists() and not pointer_path.is_symlink():
            return C.NONE
        if pointer_path.is_symlink():
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        try:
            pointer = BundlePointer.model_validate_json(pointer_path.read_bytes())
        except ValidationError as exc:
            raise ReportBundleError(S.PROD_INVALID_BUNDLE) from exc
        directory = self._path(pointer.analytics_report_id, pointer.layout_version)
        if (
            pointer.schema_version != _schema(pointer.layout_version)
            or _digest(directory / S.PROD_MANIFEST_FILE) != pointer.manifest_sha256
        ):
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        manifest = self._read(pointer.analytics_report_id, pointer.layout_version)
        if current is not C.NONE and (
            current.manifest.account_fingerprint != manifest.analysis_manifest.account_fingerprint
            or (
                current.report_id == manifest.analytics_report_id
                and current.manifest != manifest.analysis_manifest
            )
        ):
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        return self._receipt(manifest)

    def for_report(
        self, report: AnalyticsReport, layout_version: int = C.RPT_LEGACY_LAYOUT_VERSION
    ) -> ProductReceipt | None:
        if report.report_id is C.NONE or layout_version < C.ONE:
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        directory = self._path(report.report_id, layout_version)
        if not directory.exists() and not directory.is_symlink():
            return C.NONE
        if directory.is_symlink():
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        if _legacy(layout_version):
            try:
                stored = BundleManifest.model_validate_json(
                    (directory / S.PROD_MANIFEST_FILE).read_bytes()
                )
            except (ValidationError, FileNotFoundError) as exc:
                raise ReportBundleError(S.PROD_INVALID_BUNDLE) from exc
            if (
                stored.analytics_report_id == report.report_id
                and stored.layout_version >= C.PROD_READER_DIRECTORY_VERSION
            ):
                return C.NONE
        manifest = self._read(report.report_id, layout_version)
        if manifest.analysis_manifest != report.manifest:
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        self._activate(manifest)
        return self._receipt(manifest)

    def _activate(self, manifest: BundleManifest) -> None:
        directory = self._path(manifest.analytics_report_id, manifest.layout_version)
        pointer = BundlePointer(
            schema_version=manifest.schema_version,
            layout_version=manifest.layout_version,
            analytics_report_id=manifest.analytics_report_id,
            manifest_sha256=_digest(directory / S.PROD_MANIFEST_FILE),
        )
        atomic_write(
            self.root / S.PROD_LATEST_FILE,
            pointer.model_dump_json(indent=C.TWO) + S.NEWLINE,
        )

    def publish(
        self,
        report: AnalyticsReport,
        *,
        recommendations: str,
        metadata_quality: str,
        summary: ProductReceipt,
        render_pdf: Callable[[Path], object],
        reader_report: str | None = C.NONE,
        layout_version: int = C.RPT_LEGACY_LAYOUT_VERSION,
    ) -> ProductReceipt:
        if (
            report.report_id is C.NONE
            or layout_version < C.ONE
            or summary.analytics_report_id != report.report_id
            or summary.state != SyncState.COMPLETE
            or (reader_report is C.NONE) != _legacy(layout_version)
        ):
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        if reader_report is not C.NONE:
            self._check_publishable(report, reader_report)
        self.root.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        destination = self._path(report.report_id, layout_version)
        if destination.exists() or destination.is_symlink():
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        with tempfile.TemporaryDirectory(prefix=S.PROD_PENDING_PREFIX, dir=self.root) as temporary:
            staging = Path(temporary)
            contents = [
                (S.PROD_ANALYTICS_FILE, report.model_dump_json(indent=C.TWO)),
                (S.PROD_RECOMMENDATIONS_FILE, recommendations),
                (S.PROD_QUALITY_FILE, metadata_quality),
            ]
            if reader_report is not C.NONE:
                contents.append((S.RPT_BUNDLE_FILE, reader_report))
            for name, content in contents:
                atomic_write(staging / name, content + S.NEWLINE)
            render_pdf(staging / S.PROD_PDF_FILE)
            manifest = BundleManifest(
                schema_version=_schema(layout_version),
                layout_version=layout_version,
                analytics_report_id=report.report_id,
                analysis_manifest=report.manifest,
                files={name: _digest(staging / name) for name in _files(layout_version)},
                summary=summary,
            )
            atomic_write(
                staging / S.PROD_MANIFEST_FILE,
                manifest.model_dump_json(indent=C.TWO) + S.NEWLINE,
            )
            os.replace(staging, destination)
        self._activate(manifest)
        return self._receipt(manifest)

    def _check_publishable(self, report: AnalyticsReport, text: str) -> None:
        try:
            typed = ReaderReport.model_validate_json(text)
        except ValidationError as exc:
            raise ReportBundleError(S.PROD_INPUT_MISMATCH) from exc
        if (
            typed.analysis_report_id != report.report_id
            or typed.as_of != report.as_of
            or typed.manifest_digest != manifest_digest(report.manifest)
        ):
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
