"""Regression coverage for memory-safe PaddleOCR lifecycle and inference input."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import sys
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from app.schemas.ocr import OcrLine
from app.services import ocr_engine


@pytest.fixture(autouse=True)
def reset_ocr_singleton():
    previous = ocr_engine._ocr_model
    ocr_engine._ocr_model = None
    yield
    ocr_engine._ocr_model = previous


class RecordingOcr:
    def __init__(self):
        self.received = None

    def ocr(self, image):
        self.received = image
        height, width = image.shape[:2]
        image[0, 0] = 255
        return [{
            "rec_texts": ["DEMO"],
            "rec_scores": [0.99],
            "dt_polys": [np.array([
                [0, 0],
                [width, 0],
                [width, height],
                [0, height],
            ])],
        }]


def test_large_image_uses_downscaled_ocr_copy_without_mutating_original(monkeypatch):
    provider = RecordingOcr()
    monkeypatch.setattr(ocr_engine, "get_ocr_model", lambda: provider)
    original = np.zeros((4080, 3060, 3), dtype=np.uint8)
    original_shape = original.shape
    original_digest = hashlib.sha256(original).digest()

    lines = ocr_engine.analyze_image(original)

    assert provider.received.shape[:2] == (1800, 1350)
    assert max(provider.received.shape[:2]) <= 1800
    assert original.shape == original_shape
    assert hashlib.sha256(original).digest() == original_digest
    assert lines[0].polygon == [
        [0.0, 0.0],
        [3060.0, 0.0],
        [3060.0, 4080.0],
        [0.0, 4080.0],
    ]


def test_small_image_uses_copy_without_enlargement(monkeypatch):
    provider = RecordingOcr()
    monkeypatch.setattr(ocr_engine, "get_ocr_model", lambda: provider)
    original = np.zeros((480, 640, 3), dtype=np.uint8)

    lines = ocr_engine.analyze_image(original)

    assert provider.received.shape == original.shape
    assert provider.received is not original
    assert not np.shares_memory(provider.received, original)
    assert np.count_nonzero(original) == 0
    assert lines == [
        OcrLine(
            text="DEMO",
            confidence=0.99,
            polygon=[[0.0, 0.0], [640.0, 0.0], [640.0, 480.0], [0.0, 480.0]],
        )
    ]


def test_concurrent_first_use_constructs_and_reuses_one_provider(monkeypatch):
    constructed = []
    constructed_lock = threading.Lock()
    callers_ready = threading.Barrier(8)

    def paddle_factory(**_kwargs):
        with constructed_lock:
            instance = object()
            constructed.append(instance)
        time.sleep(0.05)
        return instance

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=paddle_factory))

    def load_provider():
        callers_ready.wait()
        return ocr_engine.get_ocr_model()

    with ThreadPoolExecutor(max_workers=8) as pool:
        providers = list(pool.map(lambda _index: load_provider(), range(8)))

    assert len(constructed) == 1
    assert all(provider is providers[0] for provider in providers)


def test_import_does_not_construct_paddle_provider(monkeypatch):
    constructed = []

    def paddle_factory(**kwargs):
        constructed.append(kwargs)
        return object()

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCR=paddle_factory),
    )

    reloaded = importlib.reload(ocr_engine)

    assert constructed == []
    assert reloaded._ocr_model is None
