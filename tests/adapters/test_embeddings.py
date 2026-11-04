from __future__ import annotations

import hashlib
import json
import math
import os
import socket
import subprocess
import sys
from collections.abc import Callable, Iterable
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters import embeddings
from bookystats.adapters.embeddings import EmbeddingError, LocalDescriptionEncoder
from bookystats.persistence.embeddings import EmbeddingVectorCache


class _Session:
    def __init__(self, providers: tuple[str, ...]) -> None:
        self.providers = providers

    def get_providers(self) -> list[str]:
        return list(self.providers)


class _Model:
    def __init__(self, providers: tuple[str, ...] = C.EM3_PROVIDERS) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.model = SimpleNamespace(model=_Session(providers))

    def embed(
        self, documents: Iterable[str], batch_size: int, parallel: int | None
    ) -> Iterable[Iterable[float]]:
        assert C.ONE <= batch_size <= C.EM3_MAX_BATCH_SIZE
        assert parallel is C.NONE
        texts = tuple(documents)
        self.calls.append(texts)
        for text in texts:
            vector = [float(C.ZERO)] * C.EM3_DIMENSION
            vector[C.ZERO if text == S.EM3_TEST_TEXT else C.ONE] = float(C.TWO)
            yield vector


def _encoder(
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    batch_size: int = C.EM3_BATCH_SIZE,
    on_event: Callable[[str], None] | None = C.NONE,
) -> tuple[LocalDescriptionEncoder, _Model]:
    model = _Model()
    monkeypatch.setattr(LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(return_value=model))
    return LocalDescriptionEncoder(directory, batch_size=batch_size, on_event=on_event), model


def _versions(monkeypatch: pytest.MonkeyPatch, *, cuda: bool = C.FALSE) -> dict[str, str]:
    versions = dict(C.EM3_TEST_CUDA_VERSIONS if cuda else C.EM3_TEST_CPU_VERSIONS)

    def installed(package: str) -> str:
        if package not in versions:
            raise PackageNotFoundError(package)
        return versions[package]

    monkeypatch.setattr(embeddings, S.EM3_TEST_VERSION, installed)
    return versions


def _runtime(directory: Path, monkeypatch: pytest.MonkeyPatch, *, cuda: bool = C.TRUE) -> Mock:
    _versions(monkeypatch, cuda=cuda)

    def construct(**options: object) -> _Model:
        provider_options = options[S.EM3_TEST_PROVIDERS_KEY]
        effective = (
            C.EM3_CUDA_PROVIDERS
            if provider_options == C.EM3_CUDA_PROVIDER_OPTIONS
            else C.EM3_PROVIDERS
        )
        return _Model(effective)

    factory = Mock(side_effect=construct)
    module = ModuleType(S.EM3_FASTEMBED_PACKAGE)
    monkeypatch.setattr(module, S.EM3_TEST_FACTORY, factory, raising=C.FALSE)
    monkeypatch.setitem(sys.modules, S.EM3_FASTEMBED_PACKAGE, module)
    monkeypatch.setattr(
        LocalDescriptionEncoder, S.EM3_TEST_ENSURE_ASSETS, Mock(return_value=directory)
    )
    monkeypatch.setattr(
        embeddings, S.EM3_TEST_PROVIDER_PROBE, Mock(return_value=C.EM3_CUDA_PROVIDERS)
    )
    return factory


def test_order_dedup_normalization_and_bounded_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    encoder, model = _encoder(tmp_path, monkeypatch, batch_size=C.ONE)
    vectors = encoder.encode((S.EM3_TEST_OTHER_TEXT, S.EM3_TEST_TEXT, S.EM3_TEST_OTHER_TEXT))
    assert vectors[C.ZERO] == vectors[C.TWO]
    assert vectors[C.ZERO] != vectors[C.ONE]
    assert all(math.isclose(math.hypot(*vector), C.ONE) for vector in vectors)
    assert model.calls == [(S.EM3_TEST_OTHER_TEXT,), (S.EM3_TEST_TEXT,)]


def test_cache_restart_never_loads_model_or_assets_and_keeps_exact_text_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / S.EM3_TEST_DIRECTORY
    encoder, model = _encoder(directory, monkeypatch)
    assert not directory.exists()
    fingerprint = encoder.fingerprint
    assert not directory.exists()
    first = encoder.encode((S.EM3_TEST_TEXT, S.EM3_TEST_OTHER_TEXT))
    with monkeypatch.context() as context:
        context.setattr(
            LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(side_effect=AssertionError)
        )
        context.setattr(
            LocalDescriptionEncoder, S.EM3_TEST_ENSURE_ASSETS, Mock(side_effect=AssertionError)
        )
        context.setattr(httpx, S.EM3_TEST_CLIENT, Mock(side_effect=AssertionError))
        offline = LocalDescriptionEncoder(directory, allow_download=C.FALSE)
        assert offline.fingerprint == fingerprint
        assert offline.encode((S.EM3_TEST_OTHER_TEXT, S.EM3_TEST_TEXT)) == tuple(reversed(first))
    encoder.encode((S.EM3_TEST_CHANGED_TEXT,))
    assert len(model.calls) == C.TWO
    cache = EmbeddingVectorCache(directory, fingerprint)
    assert cache.key(S.EM3_TEST_TEXT) != cache.key(S.EM3_TEST_TEXT + S.SPACE)
    assert S.EM3_TEST_TEXT not in S.EMPTY.join(
        path.read_text(encoding=S.UTF_8) for path in directory.rglob(S.EM3_JSON_PATTERN)
    )


def test_fresh_process_cache_reuse_blocks_model_imports_and_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    encoder, _ = _encoder(tmp_path, monkeypatch)
    texts = (S.EM3_TEST_TEXT, S.EM3_TEST_OTHER_TEXT)
    first = encoder.encode(texts)
    restarted = subprocess.run(
        (
            sys.executable,
            S.EM3_TEST_PYTHON_COMMAND,
            S.EM3_TEST_OFFLINE_CACHE_PROCESS,
            str(tmp_path.resolve()),
            json.dumps(tuple(reversed(texts))),
        ),
        check=C.TRUE,
        capture_output=C.TRUE,
        text=C.TRUE,
        timeout=C.EM3_TEST_CHILD_TIMEOUT_SECONDS,
    )
    assert tuple(tuple(vector) for vector in json.loads(restarted.stdout)) == tuple(reversed(first))


def test_runtime_fingerprint_change_misses_prior_vectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    encoder, model = _encoder(tmp_path, monkeypatch)
    encoder.encode((S.EM3_TEST_TEXT,))
    monkeypatch.setattr(
        embeddings, S.EM3_TEST_MODULE_FINGERPRINT, Mock(return_value=S.EM3_TEST_FINGERPRINT)
    )
    LocalDescriptionEncoder(tmp_path).encode((S.EM3_TEST_TEXT,))
    assert len(model.calls) == C.TWO


@pytest.mark.parametrize(
    S.EM3_TEST_BAD_CASES,
    C.EM3_TEST_BAD_CASES,
)
def test_malformed_inference_is_rejected_without_cache_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    vector: list[object] = [float(C.ONE)] * C.EM3_DIMENSION
    output: list[object] = [vector]
    if case == S.EM3_TEST_SHORT_VECTOR:
        vector.pop()
    elif case == S.EM3_TEST_ZERO_VECTOR:
        vector[:] = [float(C.ZERO)] * C.EM3_DIMENSION
    elif case == S.EM3_TEST_NAN_VECTOR:
        vector[C.ZERO] = C.EM3_TEST_NAN
    elif case == S.EM3_TEST_INF_VECTOR:
        vector[C.ZERO] = C.EM3_TEST_INF
    elif case == S.EM3_TEST_EXTRA_VECTOR:
        output.append(vector)
    elif case == S.EM3_TEST_EXTRA_NONE_VECTOR:
        output.append(C.NONE)
    elif case == S.EM3_TEST_MISSING_VECTOR:
        output.clear()
    elif case == S.EM3_TEST_TEXT_VECTOR:
        vector[C.ZERO] = S.EM3_TEST_TEXT
    else:
        vector[C.ZERO] = C.TRUE
    model = Mock()
    model.embed.return_value = iter(output)
    monkeypatch.setattr(LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(return_value=model))
    with pytest.raises(EmbeddingError, match=S.EM3_VECTOR_ERROR):
        LocalDescriptionEncoder(tmp_path).encode((S.EM3_TEST_TEXT,))
    assert not tuple(tmp_path.rglob(S.EM3_JSON_PATTERN))


def test_failure_diagnostics_do_not_expose_private_causes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = Mock()
    model.embed.side_effect = ValueError(S.EM3_TEST_RUNTIME_FAILURE)
    monkeypatch.setattr(LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(return_value=model))
    with pytest.raises(EmbeddingError) as error:
        LocalDescriptionEncoder(tmp_path).encode((S.EM3_TEST_TEXT,))
    assert str(error.value) == S.EM3_RUNTIME_ERROR
    assert error.value.__suppress_context__
    assert error.value.__cause__ is C.NONE


def test_corrupt_cache_is_not_hidden_by_reencoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    encoder, _ = _encoder(tmp_path, monkeypatch)
    encoder.encode((S.EM3_TEST_TEXT,))
    cache = EmbeddingVectorCache(tmp_path, encoder.fingerprint)
    path = cache.directory / (cache.key(S.EM3_TEST_TEXT) + S.EM3_CACHE_SUFFIX)
    path.write_bytes(S.EM3_TEST_CORRUPT_BYTES)
    monkeypatch.setattr(
        LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(side_effect=AssertionError)
    )
    with pytest.raises(EmbeddingError, match=S.EM3_CACHE_ERROR):
        LocalDescriptionEncoder(tmp_path).encode((S.EM3_TEST_TEXT,))
    assert path.read_bytes() == S.EM3_TEST_CORRUPT_BYTES


@pytest.mark.parametrize(
    S.EM3_TEST_LIMIT_FIELDS,
    C.EM3_TEST_INVALID_LIMITS,
)
def test_cpu_and_memory_limits_reject_invalid_configuration(
    tmp_path: Path, threads: int, batch_size: int
) -> None:
    with pytest.raises(EmbeddingError, match=S.EM3_OPTIONS_ERROR):
        LocalDescriptionEncoder(tmp_path, threads=threads, batch_size=batch_size)
    assert not tuple(tmp_path.iterdir())


def test_offline_missing_model_is_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _versions(monkeypatch)
    monkeypatch.setattr(httpx, S.EM3_TEST_CLIENT, Mock(side_effect=AssertionError))
    with pytest.raises(EmbeddingError, match=S.EM3_OFFLINE_ERROR):
        LocalDescriptionEncoder(tmp_path, allow_download=C.FALSE).encode((S.EM3_TEST_TEXT,))
    assert not tmp_path.joinpath(S.EM3_MODELS_FOLDER).exists()


def test_cpu_only_explicit_local_model_path_and_bounded_runtime_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / S.EM3_TEST_DIRECTORY
    events: list[str] = []

    def construct(**options: object) -> _Model:
        assert events[-C.ONE] == S.EM3_PROGRESS_INITIALIZING
        return _Model()

    factory = Mock(side_effect=construct)
    module = ModuleType(S.EM3_FASTEMBED_PACKAGE)
    monkeypatch.setattr(module, S.EM3_TEST_FACTORY, factory, raising=C.FALSE)
    monkeypatch.setitem(sys.modules, S.EM3_FASTEMBED_PACKAGE, module)
    _versions(monkeypatch)
    probe = Mock(side_effect=AssertionError)
    monkeypatch.setattr(embeddings, S.EM3_TEST_PROVIDER_PROBE, probe)
    monkeypatch.setattr(
        LocalDescriptionEncoder, S.EM3_TEST_ENSURE_ASSETS, Mock(return_value=directory)
    )
    encoder = LocalDescriptionEncoder(directory, threads=C.ONE, on_event=events.append)
    assert not events
    assert encoder.fingerprint
    assert not events
    encoder.encode((S.EM3_TEST_TEXT,))
    assert events[C.ONE] == S.EM3_PROGRESS_ASSETS
    options = factory.call_args.kwargs
    assert options[S.EM3_TEST_PROVIDERS_KEY] == C.EM3_PROVIDERS
    assert options[S.EM3_TEST_LOCAL_KEY] is C.TRUE
    assert options[S.EM3_TEST_PATH_KEY] == str(directory)
    assert options[S.EM3_TEST_THREADS_KEY] == C.ONE
    assert options[S.EM3_TEST_ARENA_KEY] is C.FALSE
    assert options[S.EM3_TEST_CUDA_KEY] is C.FALSE
    assert options[S.EM3_TEST_MODEL_NAME_KEY] == S.EM3_MODEL
    probe.assert_not_called()
    assert S.EM3_PROGRESS_CPU in events


def test_cpu_auto_and_explicit_cpu_preserve_exact_existing_fingerprint_lazily(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _versions(monkeypatch)
    monkeypatch.setattr(embeddings, S.EM3_TEST_IMPORT_MODULE, Mock(side_effect=AssertionError))
    directory = tmp_path / S.EM3_TEST_DIRECTORY
    automatic = LocalDescriptionEncoder(directory)
    cpu = LocalDescriptionEncoder(directory, acceleration=S.EM3_CPU)
    assert automatic.fingerprint == cpu.fingerprint == S.EM3_TEST_CPU_FINGERPRINT
    assert not directory.exists()


def test_cuda_fingerprints_bind_actual_distributions_and_execution_policy_without_probing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = _versions(monkeypatch, cuda=C.TRUE)
    monkeypatch.setattr(embeddings, S.EM3_TEST_IMPORT_MODULE, Mock(side_effect=AssertionError))
    fingerprints = {
        LocalDescriptionEncoder(tmp_path, acceleration=mode).fingerprint
        for mode in C.EM3_ACCELERATION_MODES
    }
    assert len(fingerprints) == len(C.EM3_ACCELERATION_MODES)
    assert S.EM3_TEST_CPU_FINGERPRINT not in fingerprints
    previous = LocalDescriptionEncoder(tmp_path).fingerprint
    versions[S.EM3_ONNX_GPU_PACKAGE] = S.EM3_TEST_ONNX_VERSION
    assert LocalDescriptionEncoder(tmp_path).fingerprint != previous
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize(S.EM3_TEST_PACKAGE_FIELDS, C.EM3_TEST_CONFLICT_PACKAGES)
def test_conflicting_native_variants_fail_before_import_or_asset_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: str
) -> None:
    versions = _versions(monkeypatch)
    versions[extra] = S.EM3_FASTEMBED_VERSION
    monkeypatch.setattr(embeddings, S.EM3_TEST_IMPORT_MODULE, Mock(side_effect=AssertionError))
    with pytest.raises(EmbeddingError, match=S.EM3_PROFILE_CONFLICT):
        LocalDescriptionEncoder(tmp_path).encode((S.EM3_TEST_TEXT,))
    assert not tuple(tmp_path.iterdir())


def test_missing_or_mismatched_runtime_pairs_are_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = _versions(monkeypatch)
    versions.pop(S.EM3_ONNX_PACKAGE)
    with pytest.raises(EmbeddingError) as missing:
        _ = LocalDescriptionEncoder(tmp_path).fingerprint
    assert str(missing.value) == S.EM3_PROFILE_MISSING
    versions[S.EM3_ONNX_GPU_PACKAGE] = S.EM3_TEST_GPU_ONNX_VERSION
    with pytest.raises(EmbeddingError) as mismatched:
        _ = LocalDescriptionEncoder(tmp_path).fingerprint
    assert str(mismatched.value) == S.EM3_PROFILE_MISMATCH


def test_cpu_profile_cannot_satisfy_explicit_cuda_even_when_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _versions(monkeypatch)
    encoder, _ = _encoder(tmp_path, monkeypatch)
    encoder.encode((S.EM3_TEST_TEXT,))
    with pytest.raises(EmbeddingError, match=S.EM3_CUDA_PROFILE_REQUIRED):
        LocalDescriptionEncoder(tmp_path, acceleration=S.EM3_CUDA).encode((S.EM3_TEST_TEXT,))


def test_available_cuda_is_selected_and_cached_vectors_do_not_probe_current_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    events: list[str] = []
    encoder = LocalDescriptionEncoder(tmp_path, on_event=events.append)
    first = encoder.encode((S.EM3_TEST_OTHER_TEXT, S.EM3_TEST_TEXT))
    assert factory.call_args.kwargs[S.EM3_TEST_PROVIDERS_KEY] == C.EM3_CUDA_PROVIDER_OPTIONS
    assert first[C.ZERO][C.ONE] == C.ONE
    assert first[C.ONE][C.ZERO] == C.ONE
    assert S.EM3_PROGRESS_CUDA in events
    assert S.EM3_PROGRESS_CPU not in events
    events.clear()
    monkeypatch.setattr(embeddings, S.EM3_TEST_PROVIDER_PROBE, Mock(side_effect=AssertionError))
    monkeypatch.setattr(embeddings, S.EM3_TEST_IMPORT_MODULE, Mock(side_effect=AssertionError))
    factory.side_effect = AssertionError
    assert LocalDescriptionEncoder(tmp_path, allow_download=C.FALSE, on_event=events.append).encode(
        (S.EM3_TEST_TEXT, S.EM3_TEST_OTHER_TEXT)
    ) == tuple(reversed(first))
    assert events == [S.EM3_PROGRESS_CACHE_ONLY.format(cached=C.TWO, total=C.TWO)]


def test_cuda_profile_without_cuda_ignores_other_providers_and_visibly_uses_cpu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        embeddings, S.EM3_TEST_PROVIDER_PROBE, Mock(return_value=C.EM3_TEST_CPU_OTHER_PROVIDERS)
    )
    events: list[str] = []
    LocalDescriptionEncoder(tmp_path, on_event=events.append).encode((S.EM3_TEST_TEXT,))
    assert factory.call_args.kwargs[S.EM3_TEST_PROVIDERS_KEY] == C.EM3_PROVIDERS
    assert S.EM3_PROGRESS_CUDA_UNAVAILABLE in events
    assert S.EM3_PROGRESS_CPU in events
    assert S.EM3_PROGRESS_CUDA not in events


def test_explicit_cpu_in_cuda_profile_does_not_probe_or_attempt_cuda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(embeddings, S.EM3_TEST_PROVIDER_PROBE, Mock(side_effect=AssertionError))
    events: list[str] = []
    LocalDescriptionEncoder(tmp_path, acceleration=S.EM3_CPU, on_event=events.append).encode(
        (S.EM3_TEST_TEXT,)
    )
    assert factory.call_args.kwargs[S.EM3_TEST_PROVIDERS_KEY] == C.EM3_PROVIDERS
    assert S.EM3_PROGRESS_CPU in events
    assert S.EM3_PROGRESS_CUDA_UNAVAILABLE not in events


@pytest.mark.parametrize(S.EM3_TEST_CPU_FALLBACK_FIELDS, C.EM3_TEST_FALLBACK_CASES)
def test_advertised_but_unusable_cuda_has_visible_bounded_cpu_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, implicit: bool
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    if implicit:
        factory.side_effect = C.NONE
        factory.return_value = _Model()
    else:
        factory.side_effect = [
            RuntimeError(S.EM3_TEST_CUDA_LOAD_FAILURE),
            _Model(),
        ]
    events: list[str] = []
    LocalDescriptionEncoder(tmp_path, on_event=events.append).encode((S.EM3_TEST_TEXT,))
    assert factory.call_args_list[C.ZERO].kwargs[S.EM3_TEST_PROVIDERS_KEY] == (
        C.EM3_CUDA_PROVIDER_OPTIONS
    )
    assert factory.call_count == (C.ONE if implicit else C.TWO)
    assert events.count(S.EM3_PROGRESS_CUDA_INCOMPATIBLE) == C.ONE
    assert S.EM3_PROGRESS_CPU in events
    assert S.EM3_PROGRESS_CUDA not in events


@pytest.mark.parametrize(S.EM3_TEST_CUDA_FAILURE_FIELDS, C.EM3_TEST_CUDA_FAILURE_CASES)
def test_explicit_cuda_never_returns_or_publishes_cpu_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    if failure == S.EM3_TEST_CUDA_MISSING:
        monkeypatch.setattr(
            embeddings, S.EM3_TEST_PROVIDER_PROBE, Mock(return_value=C.EM3_PROVIDERS)
        )
    elif failure == S.EM3_TEST_CUDA_DRIVER:
        factory.side_effect = RuntimeError(S.EM3_TEST_CUDA_LOAD_FAILURE)
    else:
        factory.side_effect = C.NONE
        factory.return_value = _Model()
    events: list[str] = []
    with pytest.raises(EmbeddingError, match=S.EM3_CUDA_REQUIRED):
        LocalDescriptionEncoder(tmp_path, acceleration=S.EM3_CUDA, on_event=events.append).encode(
            (S.EM3_TEST_TEXT,)
        )
    assert S.EM3_PROGRESS_CPU not in events
    assert S.EM3_PROGRESS_CUDA not in events
    assert not tuple(tmp_path.rglob(S.EM3_JSON_PATTERN))
    assert factory.call_count <= C.ONE


def test_model_integrity_failure_never_attempts_cuda_or_cpu_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        LocalDescriptionEncoder,
        S.EM3_TEST_ENSURE_ASSETS,
        Mock(side_effect=EmbeddingError(S.EM3_ASSET_ERROR)),
    )
    monkeypatch.setattr(embeddings, S.EM3_TEST_PROVIDER_PROBE, Mock(side_effect=AssertionError))
    events: list[str] = []
    with pytest.raises(EmbeddingError, match=S.EM3_ASSET_ERROR):
        LocalDescriptionEncoder(tmp_path, on_event=events.append).encode((S.EM3_TEST_TEXT,))
    factory.assert_not_called()
    assert S.EM3_PROGRESS_CPU not in events


def test_unknown_construction_or_inference_errors_never_trigger_cpu_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _runtime(tmp_path, monkeypatch)
    factory.side_effect = ValueError(S.EM3_TEST_RUNTIME_FAILURE)
    events: list[str] = []
    with pytest.raises(EmbeddingError, match=S.EM3_RUNTIME_ERROR):
        LocalDescriptionEncoder(tmp_path, on_event=events.append).encode((S.EM3_TEST_TEXT,))
    assert factory.call_count == C.ONE
    factory.reset_mock()
    model = _Model(C.EM3_CUDA_PROVIDERS)
    monkeypatch.setattr(
        model, S.EM3_TEST_EMBED, Mock(side_effect=RuntimeError(S.EM3_TEST_CUDA_LOAD_FAILURE))
    )
    factory.side_effect = C.NONE
    factory.return_value = model
    with pytest.raises(EmbeddingError, match=S.EM3_RUNTIME_ERROR):
        LocalDescriptionEncoder(tmp_path, on_event=events.append).encode((S.EM3_TEST_TEXT,))
    assert factory.call_count == C.ONE
    assert S.EM3_PROGRESS_CPU not in events
    assert S.EM3_PROGRESS_CUDA_INCOMPATIBLE not in events
    assert not tuple(tmp_path.rglob(S.EM3_JSON_PATTERN))


def test_progress_distinguishes_cached_and_new_unique_descriptions_without_runtime_on_hits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    encoder, _ = _encoder(tmp_path, monkeypatch)
    encoder.encode((S.EM3_TEST_TEXT,))
    events: list[str] = []
    encoder, _ = _encoder(tmp_path, monkeypatch, batch_size=C.ONE, on_event=events.append)
    texts = (
        S.EM3_TEST_TEXT,
        S.EM3_TEST_OTHER_TEXT,
        S.EM3_TEST_CHANGED_TEXT,
        S.EM3_TEST_OTHER_TEXT,
    )
    encoder.encode(texts)
    assert events == [
        S.EM3_PROGRESS_CACHE.format(cached=C.ONE, total=C.THREE, pending=C.TWO),
        S.EM3_PROGRESS_BATCH.format(encoded=C.TWO, pending=C.TWO, cached=C.ONE, total=C.THREE),
    ]
    events.clear()
    monkeypatch.setattr(
        LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(side_effect=AssertionError)
    )
    LocalDescriptionEncoder(tmp_path, allow_download=C.FALSE, on_event=events.append).encode(texts)
    assert events == [S.EM3_PROGRESS_CACHE_ONLY.format(cached=C.THREE, total=C.THREE)]
    assert all(text not in message for text in texts for message in events)


def test_single_item_batches_emit_bounded_progress_not_per_vector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    encoder, _ = _encoder(tmp_path, monkeypatch, batch_size=C.ONE, on_event=events.append)
    texts = tuple(
        S.EM3_TEST_LIVE_TEXT.format(text=S.EM3_TEST_TEXT, nonce=index)
        for index in range(C.EM3_MAX_BATCH_SIZE)
    )
    encoder.encode(texts)
    assert len(events) < len(texts)
    assert len(events) <= C.EM3_PROGRESS_MAX_EVENTS + C.ONE
    assert events[-C.ONE] == S.EM3_PROGRESS_BATCH.format(
        encoded=len(texts), pending=len(texts), cached=C.ZERO, total=len(texts)
    )


def _synthetic_assets(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, int]:
    asset = (
        S.EM3_MODEL_FILE,
        hashlib.sha256(S.EM3_TEST_FIXTURE_BYTES).hexdigest(),
        len(S.EM3_TEST_FIXTURE_BYTES),
    )
    monkeypatch.setattr(C, S.EM3_TEST_ASSETS, (asset,))
    return asset


def test_public_asset_download_is_pinned_anonymous_verified_and_atomically_reusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name, digest, size = _synthetic_assets(monkeypatch)
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(C.HTTP_OK, content=S.EM3_TEST_FIXTURE_BYTES)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    factory = Mock(return_value=client)
    monkeypatch.setattr(httpx, S.EM3_TEST_CLIENT, factory)
    encoder = LocalDescriptionEncoder(tmp_path)
    directory = encoder._ensure_assets()
    assert (directory / name).read_bytes() == S.EM3_TEST_FIXTURE_BYTES
    assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    assert (directory / name).stat().st_size == size
    assert len(requests) == C.ONE
    assert S.EM3_REVISION in str(requests[C.ZERO].url)
    assert S.EM3_TEST_AUTHORIZATION not in requests[C.ZERO].headers
    assert not requests[C.ZERO].url.userinfo
    assert factory.call_args.kwargs[S.EM3_TEST_TRUST_ENV] is C.FALSE
    assert LocalDescriptionEncoder(tmp_path, allow_download=C.FALSE)._ensure_assets() == directory
    assert not tuple(tmp_path.rglob(S.EM3_PART_PATTERN))


def test_wrong_download_and_existing_model_corruption_fail_without_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name, _, _ = _synthetic_assets(monkeypatch)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(C.HTTP_OK, content=S.EM3_TEST_FIXTURE_BYTES[:: -C.ONE])
        )
    )
    monkeypatch.setattr(httpx, S.EM3_TEST_CLIENT, Mock(return_value=client))
    encoder = LocalDescriptionEncoder(tmp_path)
    with pytest.raises(EmbeddingError, match=S.EM3_ASSET_ERROR):
        encoder._ensure_assets()
    directory = tmp_path / S.EM3_MODELS_FOLDER / S.EM3_REVISION
    assert not (directory / name).exists()
    assert not tuple(tmp_path.rglob(S.EM3_PART_PATTERN))
    corrupted = S.EM3_TEST_FIXTURE_BYTES[:: -C.ONE]
    (directory / name).write_bytes(corrupted)
    monkeypatch.setattr(
        LocalDescriptionEncoder, S.EM3_TEST_DOWNLOAD, Mock(side_effect=AssertionError)
    )
    with pytest.raises(EmbeddingError, match=S.EM3_ASSET_ERROR):
        encoder._ensure_assets()
    assert (directory / name).read_bytes() == corrupted


def test_network_failure_is_redacted_and_cleans_only_own_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_assets(monkeypatch)

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(S.EM3_TEST_RUNTIME_FAILURE, request=request)

    client = httpx.Client(transport=httpx.MockTransport(fail))
    monkeypatch.setattr(httpx, S.EM3_TEST_CLIENT, Mock(return_value=client))
    with pytest.raises(EmbeddingError) as error:
        LocalDescriptionEncoder(tmp_path)._ensure_assets()
    assert str(error.value) == S.EM3_DOWNLOAD_ERROR
    assert error.value.__cause__ is C.NONE
    assert error.value.__suppress_context__
    assert not tuple(tmp_path.rglob(S.EM3_PART_PATTERN))


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get(S.EM3_TEST_MODEL_ENV) != S.EM3_TEST_MODEL_ENABLED,
    reason=S.EM3_TEST_LIVE_SKIP,
)
def test_live_public_cpu_model_and_fresh_offline_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = Path(os.environ.get(S.EM3_TEST_CACHE_FOLDER_ENV, str(tmp_path)))
    nonce = uuid4().hex
    texts = tuple(
        S.EM3_TEST_LIVE_TEXT.format(text=text, nonce=nonce)
        for text in (S.EM3_TEST_TEXT, S.EM3_TEST_OTHER_TEXT)
    )
    encoder = LocalDescriptionEncoder(directory)
    first = encoder.encode(texts)
    assert len(first) == C.TWO
    assert all(len(vector) == C.EM3_DIMENSION for vector in first)
    assert all(math.isclose(math.hypot(*vector), C.ONE) for vector in first)
    assert first[C.ZERO] != first[C.ONE]
    loaded = getattr(encoder._model, S.EM3_TEST_MODEL_ATTRIBUTE)
    session = getattr(loaded, S.EM3_TEST_MODEL_ATTRIBUTE)
    assert tuple(session.get_providers()) == C.EM3_PROVIDERS
    monkeypatch.setattr(socket.socket, S.EM3_TEST_SOCKET_CONNECT, Mock(side_effect=AssertionError))
    monkeypatch.setattr(httpx, S.EM3_TEST_CLIENT, Mock(side_effect=AssertionError))
    offline_inference = LocalDescriptionEncoder(directory, allow_download=C.FALSE).encode(
        (S.EM3_TEST_LIVE_TEXT.format(text=S.EM3_TEST_CHANGED_TEXT, nonce=nonce),)
    )
    assert len(offline_inference[C.ZERO]) == C.EM3_DIMENSION
    monkeypatch.setattr(
        LocalDescriptionEncoder, S.EM3_TEST_LOAD_MODEL, Mock(side_effect=AssertionError)
    )
    assert LocalDescriptionEncoder(directory, allow_download=C.FALSE).encode(texts) == first


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get(S.EM3_TEST_CUDA_FALLBACK_ENV) != S.EM3_TEST_MODEL_ENABLED,
    reason=S.EM3_TEST_CUDA_FALLBACK_SKIP,
)
def test_live_cuda_profile_cpu_fallback_strict_cuda_and_offline_process_reuse(
    tmp_path: Path,
) -> None:
    assert embeddings._runtime_profile() == S.EM3_CUDA
    directory = Path(os.environ.get(S.EM3_TEST_CACHE_FOLDER_ENV, str(tmp_path)))
    nonce = uuid4().hex
    texts = tuple(
        S.EM3_TEST_LIVE_TEXT.format(text=text, nonce=nonce)
        for text in (S.EM3_TEST_TEXT, S.EM3_TEST_OTHER_TEXT)
    )
    events: list[str] = []
    encoder = LocalDescriptionEncoder(directory, on_event=events.append)
    first = encoder.encode(texts)
    assert encoder._effective_provider == S.EM3_CPU_PROVIDER
    assert S.EM3_PROGRESS_CPU in events
    assert S.EM3_PROGRESS_CUDA_UNAVAILABLE in events or S.EM3_PROGRESS_CUDA_INCOMPATIBLE in events
    assert S.EM3_PROGRESS_CUDA not in events
    assert all(len(vector) == C.EM3_DIMENSION for vector in first)
    assert all(math.isclose(math.hypot(*vector), C.ONE) for vector in first)
    assert first[C.ZERO] != first[C.ONE]
    strict_events: list[str] = []
    with pytest.raises(EmbeddingError, match=S.EM3_CUDA_REQUIRED):
        LocalDescriptionEncoder(
            directory,
            acceleration=S.EM3_CUDA,
            allow_download=C.FALSE,
            on_event=strict_events.append,
        ).encode(texts)
    assert S.EM3_PROGRESS_CPU not in strict_events
    assert S.EM3_PROGRESS_CUDA not in strict_events
    restarted = subprocess.run(
        (
            sys.executable,
            S.EM3_TEST_PYTHON_COMMAND,
            S.EM3_TEST_OFFLINE_CACHE_PROCESS,
            str(directory.resolve()),
            json.dumps(tuple(reversed(texts))),
        ),
        check=C.TRUE,
        capture_output=C.TRUE,
        text=C.TRUE,
        timeout=C.EM3_TEST_CHILD_TIMEOUT_SECONDS,
    )
    assert tuple(tuple(vector) for vector in json.loads(restarted.stdout)) == tuple(reversed(first))
