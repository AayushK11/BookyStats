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
from bookystats.runtime.config import atomic_write


class ReportBundleError(BookyError):
    pass


def _digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ReportBundleError(S.PROD_INVALID_BUNDLE)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReportBundleStore:
    def __init__(self, directory: Path) -> None:
        self.root = directory / S.PROD_REPORTS_FOLDER

    def _path(self, report_id: int) -> Path:
        return self.root / S.PROD_BUNDLE_NAME.format(report_id=report_id)

    def _read(self, report_id: int) -> BundleManifest:
        directory = self._path(report_id)
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
            or manifest.summary.analytics_report_id != report_id
            or manifest.summary.state != SyncState.COMPLETE
            or set(manifest.files) != set(C.PROD_BUNDLE_FILES)
        ):
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        if any(_digest(directory / name) != checksum for name, checksum in manifest.files.items()):
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        return manifest

    def _receipt(self, manifest: BundleManifest) -> ProductReceipt:
        directory = self._path(manifest.analytics_report_id)
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
        directory = self._path(pointer.analytics_report_id)
        if _digest(directory / S.PROD_MANIFEST_FILE) != pointer.manifest_sha256:
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        manifest = self._read(pointer.analytics_report_id)
        if current is not C.NONE and (
            current.manifest.account_fingerprint != manifest.analysis_manifest.account_fingerprint
            or (
                current.report_id == manifest.analytics_report_id
                and current.manifest != manifest.analysis_manifest
            )
        ):
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        return self._receipt(manifest)

    def for_report(self, report: AnalyticsReport) -> ProductReceipt | None:
        if report.report_id is C.NONE:
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        directory = self._path(report.report_id)
        if not directory.exists() and not directory.is_symlink():
            return C.NONE
        manifest = self._read(report.report_id)
        if manifest.analysis_manifest != report.manifest:
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        self._activate(manifest)
        return self._receipt(manifest)

    def _activate(self, manifest: BundleManifest) -> None:
        pointer = BundlePointer(
            analytics_report_id=manifest.analytics_report_id,
            manifest_sha256=_digest(
                self._path(manifest.analytics_report_id) / S.PROD_MANIFEST_FILE
            ),
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
    ) -> ProductReceipt:
        if (
            report.report_id is C.NONE
            or summary.analytics_report_id != report.report_id
            or summary.state != SyncState.COMPLETE
        ):
            raise ReportBundleError(S.PROD_INPUT_MISMATCH)
        self.root.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        destination = self._path(report.report_id)
        if destination.exists() or destination.is_symlink():
            raise ReportBundleError(S.PROD_INVALID_BUNDLE)
        with tempfile.TemporaryDirectory(prefix=S.PROD_PENDING_PREFIX, dir=self.root) as temporary:
            staging = Path(temporary)
            for name, content in (
                (S.PROD_ANALYTICS_FILE, report.model_dump_json(indent=C.TWO)),
                (S.PROD_RECOMMENDATIONS_FILE, recommendations),
                (S.PROD_QUALITY_FILE, metadata_quality),
            ):
                atomic_write(staging / name, content + S.NEWLINE)
            render_pdf(staging / S.PROD_PDF_FILE)
            manifest = BundleManifest(
                analytics_report_id=report.report_id,
                analysis_manifest=report.manifest,
                files={name: _digest(staging / name) for name in C.PROD_BUNDLE_FILES},
                summary=summary,
            )
            atomic_write(
                staging / S.PROD_MANIFEST_FILE,
                manifest.model_dump_json(indent=C.TWO) + S.NEWLINE,
            )
            os.replace(staging, destination)
        self._activate(manifest)
        return self._receipt(manifest)
