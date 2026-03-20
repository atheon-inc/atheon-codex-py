import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class _FlushSentinel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    done_event: threading.Event


class _EventQueue:
    def __init__(
        self,
        send_fn: Callable,
        upload_size: int = 10,
        upload_interval: float = 1.0,
        max_queue_size: int = 10_000,
    ) -> None:
        self._send_fn = send_fn

        self.upload_size = upload_size
        self.upload_interval = upload_interval

        self._queue: queue.Queue[dict[str, Any] | _FlushSentinel] = queue.Queue(
            maxsize=max_queue_size
        )

        self._stop_event = threading.Event()
        self._is_shutting_down = False

        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="atheon-queue"
        )
        self._thread.start()

    def enqueue(self, payload: dict[str, Any]) -> None:
        if self._is_shutting_down:
            logger.warning("Event dropped because queue is shutting down.")
            return

        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.warning(
                "Event queue is full, dropping event. Consider calling flush() more frequently."
            )

    def flush(self, timeout: float | None = 5.0) -> bool:
        done = threading.Event()

        try:
            self._queue.put(_FlushSentinel(done_event=done), timeout=timeout)
        except queue.Full:
            logger.warning("Cannot flush: queue is completely full and unresponsive.")
            return False

        success = done.wait(timeout=timeout)
        if not success:
            logger.warning("Flush operation timed out.")

        return success

    def shutdown(self, timeout: float = 5.0) -> None:
        self._is_shutting_down = True
        self.flush(timeout=timeout)
        self._stop_event.set()
        self._thread.join(timeout=timeout)

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            batch: list[dict] = []
            sentinels: list[threading.Event] = []

            try:
                item = self._queue.get(timeout=self.upload_interval)
            except queue.Empty:
                continue

            if isinstance(item, _FlushSentinel):
                sentinels.append(item.done_event)
            else:
                batch.append(item)

            while len(batch) < self.upload_size:
                try:
                    next_item = self._queue.get_nowait()
                    if isinstance(next_item, _FlushSentinel):
                        sentinels.append(next_item.done_event)
                    else:
                        batch.append(next_item)
                except queue.Empty:
                    break

            self._send_batch(batch)

            for event in sentinels:
                event.set()

    def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return

        try:
            self._send_fn(batch)
        except Exception:
            logger.exception("Failed to send event batch.")
