import asyncio
import logging
from math import inf
from typing import Sequence

from PySide6.QtCore import QThread
from PySide6.QtCore import QObject
from qt_extensions.core import TypedSignal

from core.translation.translation import Translator
from ..typing import IndexLikeSequence

__all__ = ["TranslationWorker"]

logger = logging.getLogger(__name__)

class TranslationWorker(QThread):
    """
    Runs batch translation concurrently using asyncio in a background thread.
    
    Uses a semaphore + delay to limit the number of concurrent requests and avoid rate limiting.
    """
    work_finished = TypedSignal(IndexLikeSequence, list)     # (idxs: list, translations: list[str|None])
    translated    = TypedSignal(int, str|None)  # (idx: int, translation: str)
    progress      = TypedSignal(int, int)       # (progress_count: int, total_count: int)
    error         = TypedSignal(str)

    def __init__(
        self,
        translator: Translator,
        idxs: IndexLikeSequence,
        texts: list[str],
        delay: float = 0.0,
        max_concurrency: int = 5,
        parent: QObject | None = None,
        as_batch: bool = False,
    ):
        """
        Arguments:
            translator (Translator): the Translator wrapper to use for each call.
            idxs (IndexLikeSequence):             parallel list of row keys/indexes (returned unchanged in ``finished``).
            texts (list[str]):       the source strings to translate, in the same order as ``idxs``.
            delay (float):           minimum seconds between initiating requests (rate-limit guard).
            max_concurrency (int):   maximum concurrent requests. Defaults per provider (1 for Google, 4-5 for others).
        """
        super().__init__(parent=parent)
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if delay < 0:
            raise ValueError("delay must be >= 0")
        self.translator = translator
        self.idxs = idxs
        self.texts = texts
        self.delay = delay
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self._cancelled = False
        self.progress_count = 0
        self.last_request_time = -inf
        self.as_batch = as_batch
        self.translated.connect(self.on_translated)
    
    def cancel(self) -> None:
        """Request graceful cancellation.

        Any in-flight calls will complete, while unstarted or queued tasks
        will return None without sending requests.
        """
        self._cancelled = True
        
    def on_translated(self, idx: int, translation: str|None) -> None:
        """Emit the translated signal for a single item."""
        logger.debug("Translated idx %d: %s", idx, translation)
        self.progress_count += 1
        self.progress.emit(self.progress_count, len(self.texts))
        
    async def _translate(self, text: str, idx: int) -> str | None:
        """Translate a single text item asynchronously."""
        if self._cancelled:
            return None
        async with self.semaphore:
            if self._cancelled:
                return None
            try:
                # Delay between requests to avoid rate limiting
                wait_time = self.delay - (asyncio.get_running_loop().time() - self.last_request_time)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self.last_request_time = asyncio.get_running_loop().time()
                res = await asyncio.to_thread(self.translator.translate, text)
                self.translated.emit(idx, res)
                return res
            except Exception as e:
                logger.error("Error translating text: %s", e)

    def run(self) -> None:
        try:
            if self.as_batch:
                results: Sequence[str | None] | None = (
                    self.translator.line_batch_translate(self.texts)
                )
                if results is None:
                    self.error.emit("line_batch_translate returned None")
                    self.work_finished.emit(self.idxs, [None] * len(self.texts))
                else:
                    for idx, translation in zip(self.idxs, results):
                        self.translated.emit(idx, translation)
                    self.work_finished.emit(self.idxs, list(results))
            else:
                self.semaphore = asyncio.Semaphore(self.max_concurrency)

                async def _run_all() -> list[str | None]:
                    tasks = [self._translate(text, idx) for text, idx in zip(self.texts, self.idxs)]
                    return await asyncio.gather(*tasks)

                results = asyncio.run(_run_all())
                self.work_finished.emit(self.idxs, results)
        except Exception as e:
            logger.error("%s encountered an error: %s", type(self).__name__, e)
            self.error.emit(str(e))
