from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
from collections.abc import Callable, Iterable
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from itertools import islice
from numbers import Real
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

import httpx

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import BookyError
from bookystats.persistence.embeddings import (
    EmbeddingCacheError,
    EmbeddingVectorCache,
    file_hash,
    publish_immutable,
)


class EmbeddingError(BookyError):
    pass


class _EmbeddingModel(Protocol):
    def embed(
        self,
        documents: Iterable[str],
        batch_size: int,
        parallel: int | None,
    ) -> Iterable[Iterable[float]]:
        pass


class _ProviderProbe(Protocol):
    def get_available_providers(self) -> list[str]:
        pass


class _Session(Protocol):
    def get_providers(self) -> list[str]:
        pass


class _SessionHolder(Protocol):
    model: _Session | None


class _LoadedModel(Protocol):
    model: _SessionHolder


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return C.NONE
    except (OSError, ValueError):
        raise EmbeddingError(S.EM3_PROFILE_MISSING) from C.NONE


def _runtime_profile() -> str:
    installed = {package: _package_version(package) for package in C.EM3_PROFILE_PACKAGES}
    cpu_fastembed = installed[S.EM3_FASTEMBED_PACKAGE]
    gpu_fastembed = installed[S.EM3_FASTEMBED_GPU_PACKAGE]
    cpu_onnx = installed[S.EM3_ONNX_PACKAGE]
    gpu_onnx = installed[S.EM3_ONNX_GPU_PACKAGE]
    if (
        (cpu_fastembed is not C.NONE and gpu_fastembed is not C.NONE)
        or (cpu_onnx is not C.NONE and gpu_onnx is not C.NONE)
        or installed[S.EM3_ONNX_DIRECTML_PACKAGE] is not C.NONE
    ):
        raise EmbeddingError(S.EM3_PROFILE_CONFLICT)
    if (cpu_fastembed is C.NONE and gpu_fastembed is C.NONE) or (
        cpu_onnx is C.NONE and gpu_onnx is C.NONE
    ):
        raise EmbeddingError(S.EM3_PROFILE_MISSING)
    if cpu_fastembed is not C.NONE and cpu_onnx is not C.NONE:
        profile = S.EM3_CPU
        fastembed_version = cpu_fastembed
    elif gpu_fastembed is not C.NONE and gpu_onnx is not C.NONE:
        profile = S.EM3_CUDA
        fastembed_version = gpu_fastembed
    else:
        raise EmbeddingError(S.EM3_PROFILE_MISMATCH)
    if fastembed_version != S.EM3_FASTEMBED_VERSION:
        raise EmbeddingError(S.EM3_VERSION_ERROR)
    return profile


def _fingerprint(acceleration: S.EmbeddingAcceleration = S.EM3_AUTO) -> str:
    profile = _runtime_profile()
    if profile == S.EM3_CPU and acceleration == S.EM3_CUDA:
        raise EmbeddingError(S.EM3_CUDA_PROFILE_REQUIRED)
    packages = C.EM3_RUNTIME_PACKAGES if profile == S.EM3_CPU else C.EM3_CUDA_RUNTIME_PACKAGES
    runtime = []
    for package in packages:
        runtime.append((package, _package_version(package) or S.EM3_PACKAGE_MISSING))
    execution: str | tuple[str, S.EmbeddingAcceleration] = (
        S.EM3_CPU_PROVIDER if profile == S.EM3_CPU else (S.EM3_ADAPTIVE_POLICY, acceleration)
    )
    policy = (
        S.EM3_MODEL,
        S.EM3_REPOSITORY,
        S.EM3_REVISION,
        S.EM3_FASTEMBED_VERSION,
        execution,
        S.EM3_POLICY,
        C.EM3_DIMENSION,
        C.EM3_ASSETS,
        runtime,
    )
    digest = hashlib.sha256(json.dumps(policy).encode(S.UTF_8)).hexdigest()
    template = S.EM3_FINGERPRINT if profile == S.EM3_CPU else S.EM3_ADAPTIVE_FINGERPRINT
    return template.format(digest=digest)


def _available_providers() -> tuple[str, ...]:
    runtime = cast(_ProviderProbe, import_module(S.EM3_ONNX_PACKAGE))
    return tuple(runtime.get_available_providers())


def _session_providers(model: _EmbeddingModel) -> tuple[str, ...]:
    session = cast(_LoadedModel, model).model.model
    if session is C.NONE:
        raise EmbeddingError(S.EM3_RUNTIME_ERROR)
    return tuple(session.get_providers())


def _cuda_initialization_incompatible(error: Exception) -> bool:
    message = str(error).casefold()
    return any(marker in message for marker in C.EM3_CUDA_COMPATIBILITY_ERRORS) or any(
        all(marker in message for marker in markers) for markers in C.EM3_CUDA_LOAD_ERROR_MARKERS
    )


def _normalize(raw: Iterable[float]) -> tuple[float, ...]:
    try:
        values = tuple(islice(raw, C.EM3_DIMENSION + C.ONE))
        if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
            raise EmbeddingError(S.EM3_VECTOR_ERROR)
        vector = tuple(float(value) for value in values)
        if len(vector) != C.EM3_DIMENSION or not all(math.isfinite(value) for value in vector):
            raise EmbeddingError(S.EM3_VECTOR_ERROR)
        norm = math.hypot(*vector)
        if not math.isfinite(norm) or norm <= C.ZERO:
            raise EmbeddingError(S.EM3_VECTOR_ERROR)
        return tuple(value / norm for value in vector)
    except (TypeError, ValueError, OverflowError):
        raise EmbeddingError(S.EM3_VECTOR_ERROR) from C.NONE


class LocalDescriptionEncoder:
    def __init__(
        self,
        directory: Path,
        *,
        allow_download: bool = C.TRUE,
        threads: int = C.EM3_THREADS,
        batch_size: int = C.EM3_BATCH_SIZE,
        acceleration: S.EmbeddingAcceleration = S.EM3_AUTO,
        on_event: Callable[[str], None] | None = C.NONE,
    ) -> None:
        if (
            type(threads) is not int
            or not C.ONE <= threads <= C.EM3_MAX_THREADS
            or type(batch_size) is not int
            or not C.ONE <= batch_size <= C.EM3_MAX_BATCH_SIZE
            or type(allow_download) is not bool
            or acceleration not in C.EM3_ACCELERATION_MODES
        ):
            raise EmbeddingError(S.EM3_OPTIONS_ERROR)
        self.directory = directory
        self.allow_download = allow_download
        self.threads = threads
        self.batch_size = batch_size
        self.acceleration = acceleration
        self.on_event = on_event
        self._model: _EmbeddingModel | None = C.NONE
        self._effective_provider: str | None = C.NONE

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.acceleration)

    def _emit(self, message: str) -> None:
        if self.on_event is not C.NONE:
            self.on_event(message)

    def _download_asset(self, destination: Path, name: str, digest: str, size: int) -> None:
        staged = destination.parent / (uuid4().hex + S.EM3_PART_SUFFIX)
        url = S.EM3_PUBLIC_ASSET_URL.format(
            repo=S.EM3_REPOSITORY, revision=S.EM3_REVISION, name=name
        )
        deadline = time.monotonic() + C.EM3_DOWNLOAD_DEADLINE_SECONDS
        received = C.ZERO
        checksum = hashlib.sha256()
        try:
            with (
                httpx.Client(
                    timeout=C.EM3_DOWNLOAD_TIMEOUT_SECONDS,
                    follow_redirects=C.TRUE,
                    trust_env=C.FALSE,
                ) as client,
                client.stream(S.EM3_GET, url) as response,
            ):
                response.raise_for_status()
                with staged.open(S.EM3_WRITE_BINARY) as stream:
                    for chunk in response.iter_bytes(C.EM3_DOWNLOAD_CHUNK_BYTES):
                        received += len(chunk)
                        if received > size or time.monotonic() > deadline:
                            raise EmbeddingError(S.EM3_DOWNLOAD_ERROR)
                        checksum.update(chunk)
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            if received != size or not hmac.compare_digest(checksum.hexdigest(), digest):
                raise EmbeddingError(S.EM3_ASSET_ERROR)
            publish_immutable(staged, destination)
        except (httpx.HTTPError, OSError, EmbeddingCacheError):
            raise EmbeddingError(S.EM3_DOWNLOAD_ERROR) from C.NONE
        finally:
            staged.unlink(missing_ok=C.TRUE)

    def _ensure_assets(self) -> Path:
        directory = self.directory / S.EM3_MODELS_FOLDER / S.EM3_REVISION
        try:
            for name, digest, size in C.EM3_ASSETS:
                path = directory / name
                if path.exists():
                    if path.stat().st_size != size or not hmac.compare_digest(
                        file_hash(path), digest
                    ):
                        raise EmbeddingError(S.EM3_ASSET_ERROR)
                else:
                    if not self.allow_download:
                        raise EmbeddingError(S.EM3_OFFLINE_ERROR)
                    directory.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
                    self._download_asset(path, name, digest, size)
            return directory
        except OSError:
            raise EmbeddingError(S.EM3_ASSET_ERROR) from C.NONE

    def _construct_model(self, model_directory: Path, provider: str) -> _EmbeddingModel:
        from fastembed import TextEmbedding

        providers = (
            C.EM3_CUDA_PROVIDER_OPTIONS if provider == S.EM3_CUDA_PROVIDER else C.EM3_PROVIDERS
        )
        return TextEmbedding(
            model_name=S.EM3_MODEL,
            cache_dir=str(self.directory / S.EM3_FASTEMBED_FOLDER),
            threads=self.threads,
            providers=providers,
            cuda=C.FALSE,
            local_files_only=C.TRUE,
            specific_model_path=str(model_directory),
            lazy_load=C.FALSE,
            enable_cpu_mem_arena=C.FALSE,
        )

    def _cpu_model(self, model_directory: Path) -> _EmbeddingModel:
        model = self._construct_model(model_directory, S.EM3_CPU_PROVIDER)
        if _session_providers(model) != C.EM3_PROVIDERS:
            raise EmbeddingError(S.EM3_RUNTIME_ERROR)
        self._effective_provider = S.EM3_CPU_PROVIDER
        return model

    def _load_model(self) -> _EmbeddingModel:
        profile = _runtime_profile()
        if profile == S.EM3_CPU and self.acceleration == S.EM3_CUDA:
            raise EmbeddingError(S.EM3_CUDA_PROFILE_REQUIRED)
        self._emit(S.EM3_PROGRESS_ASSETS)
        model_directory = self._ensure_assets()
        self._emit(S.EM3_PROGRESS_INITIALIZING)
        try:
            if profile == S.EM3_CPU or self.acceleration == S.EM3_CPU:
                return self._cpu_model(model_directory)
            if S.EM3_CUDA_PROVIDER not in _available_providers():
                if self.acceleration == S.EM3_CUDA:
                    raise EmbeddingError(S.EM3_CUDA_REQUIRED)
                self._emit(S.EM3_PROGRESS_CUDA_UNAVAILABLE)
                return self._cpu_model(model_directory)
            try:
                model = self._construct_model(model_directory, S.EM3_CUDA_PROVIDER)
            except Exception as error:
                if not _cuda_initialization_incompatible(error):
                    raise EmbeddingError(S.EM3_RUNTIME_ERROR) from C.NONE
                if self.acceleration == S.EM3_CUDA:
                    raise EmbeddingError(S.EM3_CUDA_REQUIRED) from C.NONE
                self._emit(S.EM3_PROGRESS_CUDA_INCOMPATIBLE)
                return self._cpu_model(model_directory)
            effective = _session_providers(model)
            if effective == C.EM3_CUDA_PROVIDERS:
                self._effective_provider = S.EM3_CUDA_PROVIDER
                return model
            if effective != C.EM3_PROVIDERS:
                raise EmbeddingError(S.EM3_RUNTIME_ERROR)
            if self.acceleration == S.EM3_CUDA:
                raise EmbeddingError(S.EM3_CUDA_REQUIRED)
            self._emit(S.EM3_PROGRESS_CUDA_INCOMPATIBLE)
            self._effective_provider = S.EM3_CPU_PROVIDER
            return model
        except EmbeddingError:
            raise
        except Exception:
            # Third-party errors can contain input text, paths or signed download URLs.
            raise EmbeddingError(S.EM3_RUNTIME_ERROR) from C.NONE

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not isinstance(texts, tuple) or any(
            not isinstance(text, str) or not text.strip() or len(text) > C.EM3_MAX_TEXT_CHARACTERS
            for text in texts
        ):
            raise EmbeddingError(S.EM3_OPTIONS_ERROR)
        cache = EmbeddingVectorCache(self.directory, self.fingerprint)
        vectors: dict[str, tuple[float, ...]] = {}
        missing: dict[str, str] = {}
        try:
            keys = tuple(cache.key(text) for text in texts)
            for key, text in zip(keys, texts, strict=C.TRUE):
                if key in vectors or key in missing:
                    continue
                cached = cache.get(key)
                if cached is C.NONE:
                    missing[key] = text
                else:
                    vectors[key] = cached
            total = len(vectors) + len(missing)
            cached_count = len(vectors)
            if total:
                template = S.EM3_PROGRESS_CACHE if missing else S.EM3_PROGRESS_CACHE_ONLY
                self._emit(template.format(cached=cached_count, total=total, pending=len(missing)))
            if missing:
                if self._model is C.NONE:
                    self._model = self._load_model()
                if self._effective_provider is not C.NONE:
                    self._emit(
                        S.EM3_PROGRESS_CUDA
                        if self._effective_provider == S.EM3_CUDA_PROVIDER
                        else S.EM3_PROGRESS_CPU
                    )
                pending = tuple(missing)
                progress_stride = max(
                    C.EM3_PROGRESS_MIN_DESCRIPTIONS,
                    math.ceil(len(pending) / C.EM3_PROGRESS_MAX_EVENTS),
                )
                next_progress = progress_stride
                encoded = C.ZERO
                for start in range(C.ZERO, len(pending), self.batch_size):
                    batch = pending[start : start + self.batch_size]
                    try:
                        output = iter(
                            self._model.embed(
                                tuple(missing[key] for key in batch),
                                batch_size=self.batch_size,
                                parallel=C.NONE,
                            )
                        )
                        normalized_list = []
                        for _ in batch:
                            normalized_list.append(_normalize(next(output)))
                        normalized = tuple(normalized_list)
                        if next(output, C.EM3_END_OF_OUTPUT) is not C.EM3_END_OF_OUTPUT:
                            raise EmbeddingError(S.EM3_VECTOR_ERROR)
                    except StopIteration:
                        raise EmbeddingError(S.EM3_VECTOR_ERROR) from C.NONE
                    except EmbeddingError:
                        raise
                    except Exception:
                        raise EmbeddingError(S.EM3_RUNTIME_ERROR) from C.NONE
                    for key, vector in zip(batch, normalized, strict=C.TRUE):
                        cache.put(key, vector)
                        vectors[key] = vector
                    encoded += len(batch)
                    if encoded >= next_progress or encoded == len(pending):
                        self._emit(
                            S.EM3_PROGRESS_BATCH.format(
                                encoded=encoded,
                                pending=len(pending),
                                cached=cached_count,
                                total=total,
                            )
                        )
                        next_progress = encoded + progress_stride
            return tuple(vectors[key] for key in keys)
        except EmbeddingCacheError:
            raise EmbeddingError(S.EM3_CACHE_ERROR) from C.NONE
        except (OSError, UnicodeError):
            raise EmbeddingError(S.EM3_CACHE_ERROR) from C.NONE
