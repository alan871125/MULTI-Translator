import time
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QCoreApplication

from app.workers import TranslationWorker


@pytest.fixture(scope="session")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def test_translation_worker_concurrent(qapp):
    mock_translator = MagicMock()
    mock_translator.settings.api_provider = "custom"
    mock_translator.translate.side_effect = lambda t: f"trans_{t}"

    worker = TranslationWorker(
        translator=mock_translator,
        idxs=[10, 20, 30],
        texts=["hello", "world", "test"],
        delay=0.0,
        max_concurrency=3,
    )

    results = []
    progress_updates = []
    worker.work_finished.connect(lambda idxs, trans: results.extend(trans))
    worker.progress.connect(lambda done, total: progress_updates.append((done, total)))

    worker.start()
    worker.wait()
    qapp.processEvents()

    assert results == ["trans_hello", "trans_world", "trans_test"]
    assert progress_updates == [(1, 3), (2, 3), (3, 3)]


def test_translation_worker_cancellation(qapp):
    mock_translator = MagicMock()
    mock_translator.settings.api_provider = "custom"

    def slow_translate(t):
        time.sleep(0.08)
        return f"trans_{t}"

    mock_translator.translate.side_effect = slow_translate

    worker = TranslationWorker(
        translator=mock_translator,
        idxs=[1, 2, 3, 4],
        texts=["a", "b", "c", "d"],
        delay=0.0,
        max_concurrency=1,
    )

    results = []
    worker.work_finished.connect(lambda idxs, trans: results.extend(trans))

    worker.start()
    time.sleep(0.04)
    worker.cancel()
    worker.wait()
    qapp.processEvents()

    assert len(results) == 4
    # At least some items should be None due to early cancellation
    assert None in results


def test_line_batch_translation_worker(qapp):
    mock_translator = MagicMock()
    mock_translator.line_batch_translate.return_value = ["line1_tr", "line2_tr"]

    worker = TranslationWorker(
        translator=mock_translator,
        idxs=[100, 200],
        texts=["line1", "line2"],
        as_batch=True,
    )

    results = []
    worker.work_finished.connect(lambda idxs, trans: results.extend(trans))

    worker.start()
    worker.wait()
    qapp.processEvents()

    assert results == ["line1_tr", "line2_tr"]
