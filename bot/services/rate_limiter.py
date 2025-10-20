# -*- coding: utf-8 -*-
"""Async rate limiter and send queue for Telegram bot interactions.

Currently provides scaffolding for future tasks:
- RateLimiter lifecycle hooks (`start`, `stop`, `enqueue_send`)
- Global sliding-window limiter helpers
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import heapq
import logging
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional, Tuple

from telegram import Bot
from telegram.error import NetworkError, RetryAfter, TimedOut

from bot.utils.config import (
    ADMIN_CHAT_ID_LOG_INT,
    GLOBAL_RATE_MESSAGES_PER_SEC,
    HEAVY_LOAD_DELAY_THRESHOLD_SEC,
    PER_CHAT_COOLDOWN_SEC,
)


SendMethod = Callable[..., Awaitable[Any]]


class RateLimiter:
    """Coordinate outbound Telegram sends with global/per-chat rate controls."""

    def __init__(
        self,
        bot: Bot,
        *,
        global_rate_per_sec: int = GLOBAL_RATE_MESSAGES_PER_SEC,
        per_chat_cooldown_sec: float = PER_CHAT_COOLDOWN_SEC,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self._bot = bot
        self._global_rate_per_sec = max(1, int(global_rate_per_sec))
        self._per_chat_cooldown = max(0.0, float(per_chat_cooldown_sec))
        self._loop = loop
        self._log = logging.getLogger(__name__)

        # Sliding window of send timestamps (seconds since epoch).
        self._global_window: Deque[float] = deque()
        # Track last send time per chat for cooldown enforcement.
        self._per_chat_last_sent: Dict[int | str, float] = {}

        # Priority queue for scheduled sends.
        self._queue: List[Tuple[float, int, "_QueueEntry"]] = []
        self._queue_seq: int = 0

        self._queue_event: Optional[asyncio.Event] = None
        self._queue_lock: Optional[asyncio.Lock] = None
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._running: bool = False

        # Queue monitoring and alerts.
        self._admin_chat_id_log = ADMIN_CHAT_ID_LOG_INT
        self._last_delay_alert_at: Optional[float] = None
        self._delay_alert_cooldown: float = 300.0  # seconds between admin alerts
        self._delay_alert_threshold: float = HEAVY_LOAD_DELAY_THRESHOLD_SEC * 2.0

        # Retry configuration.
        self._max_retry_attempts: int = 3
        self._retry_base_delay: float = 0.5  # seconds

    async def start(self) -> None:
        """Initialize background resources."""
        loop = self._ensure_loop()

        if self._queue_event is None:
            self._queue_event = asyncio.Event()
        if self._queue_lock is None:
            self._queue_lock = asyncio.Lock()

        if self._worker_task is None or self._worker_task.done():
            self._running = True
            self._worker_task = loop.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Tear down background resources."""
        self._running = False

        if self._queue_event is not None:
            self._queue_event.set()

        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        if self._queue_lock is not None:
            async with self._queue_lock:
                while self._queue:
                    _, _, entry = heapq.heappop(self._queue)
                    self._reject_entry(entry, RuntimeError("RateLimiter stopped"))

    async def enqueue_send(
        self,
        method: SendMethod,
        *,
        chat_id: int | str,
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
    ) -> Any:
        """Add a Telegram send operation to the outbound queue."""
        if self._queue_event is None or self._queue_lock is None:
            raise RuntimeError("RateLimiter.start() must be awaited before enqueue_send.")

        loop = self._ensure_loop()
        now = loop.time()
        ready_at = self.next_allowed_for_chat(chat_id, now)

        delay = ready_at - now
        if delay > HEAVY_LOAD_DELAY_THRESHOLD_SEC:
            self._log.info(
                "RateLimiter heavy-load typing indicator triggered for chat %s (expected delay %.2fs)",
                chat_id,
                delay,
            )
            await self._send_typing_indicator(chat_id, delay)

        future: asyncio.Future[Any] = loop.create_future()
        entry = _QueueEntry(
            method=method,
            chat_id=chat_id,
            args=args,
            kwargs=kwargs or {},
            context=context,
            future=future,
            enqueued_at=now,
            ready_at=ready_at,
        )

        async with self._queue_lock:
            self._queue_seq += 1
            heapq.heappush(self._queue, (ready_at, self._queue_seq, entry))
            queue_depth = len(self._queue)
            self._queue_event.set()

        self._log.info(
            "RateLimiter enqueued send for chat %s via %s (delay %.2fs, ready_at %.6f, queue_depth %d)",
            chat_id,
            getattr(method, "__name__", repr(method)),
            max(0.0, delay),
            ready_at,
            queue_depth,
        )

        if queue_depth > self._global_rate_per_sec or delay > HEAVY_LOAD_DELAY_THRESHOLD_SEC:
            metrics = await self.queue_metrics()
            await self._maybe_notify_delay(metrics)

        loop = self._ensure_loop()

        def _on_future_done(fut: asyncio.Future[Any]) -> None:  # pragma: no cover - callback
            if fut.cancelled():
                loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self._cancel_entry(entry),
                )

        future.add_done_callback(_on_future_done)
        return future

    def can_send_global(self, now: float) -> bool:
        """Return True if another message can be sent at `now`."""
        self._trim_global_window(now)
        return len(self._global_window) < self._global_rate_per_sec

    def record_global(self, now: float) -> None:
        """Record that a message was sent at `now`."""
        self._trim_global_window(now)
        self._global_window.append(now)

    def next_allowed_for_chat(self, chat_id: int | str, now: float) -> float:
        """Return the earliest timestamp the chat can send again."""
        last_sent = self._per_chat_last_sent.get(chat_id)
        if last_sent is None:
            return now
        return max(now, last_sent + self._per_chat_cooldown)

    def record_chat_send(self, chat_id: int | str, now: float) -> None:
        """Record the latest send timestamp for the chat."""
        self._per_chat_last_sent[chat_id] = max(now, self._per_chat_last_sent.get(chat_id, now))

    def _trim_global_window(self, now: float) -> None:
        """Drop timestamps older than the 1-second sliding window."""
        while self._global_window and (now - self._global_window[0]) >= 1.0:
            self._global_window.popleft()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def _worker_loop(self) -> None:
        assert self._queue_event is not None
        assert self._queue_lock is not None

        try:
            while self._running:
                entry = await self._next_ready_entry()
                if entry is None:
                    continue
                await self._handle_ready_entry(entry)
        except asyncio.CancelledError:
            pass

    async def _next_ready_entry(self) -> Optional["_QueueEntry"]:
        assert self._queue_event is not None
        assert self._queue_lock is not None

        loop = self._ensure_loop()
        while self._running:
            async with self._queue_lock:
                if not self._queue:
                    self._queue_event.clear()
                    wait_timeout = None
                else:
                    ready_at, _, entry = self._queue[0]
                    now = loop.time()
                    delay = ready_at - now
                    if delay <= 0:
                        heapq.heappop(self._queue)
                        return entry
                    self._queue_event.clear()
                    wait_timeout = delay

            try:
                if wait_timeout is None:
                    await self._queue_event.wait()
                else:
                    await asyncio.wait_for(self._queue_event.wait(), timeout=wait_timeout)
            except asyncio.TimeoutError:
                pass

        return None

    async def _handle_ready_entry(self, entry: "_QueueEntry") -> None:
        """Dispatch an entry if allowed; requeue otherwise."""
        loop = self._ensure_loop()
        now = loop.time()

        if not self.can_send_global(now):
            await self._requeue(entry, self._next_global_ready(now))
            return

        chat_ready = self.next_allowed_for_chat(entry.chat_id, now)
        if chat_ready > now:
            await self._requeue(entry, chat_ready)
            return

        await self._dispatch_entry(entry, now)

    async def _dispatch_entry(self, entry: "_QueueEntry", now: float) -> None:
        """Call the underlying Telegram API and record usage."""
        attempt = entry.retries
        loop = self._ensure_loop()

        queue_depth = await self._queue_size()
        waited = max(0.0, now - entry.enqueued_at)
        ready_offset = max(0.0, entry.ready_at - now)
        method_name = getattr(entry.method, "__name__", repr(entry.method))
        self._log.info(
            "RateLimiter dispatch starting for chat %s via %s (waited %.2fs, ready_offset %.2fs, retries %d, queue_depth %d)",
            entry.chat_id,
            method_name,
            waited,
            ready_offset,
            attempt,
            queue_depth,
        )

        while True:
            try:
                result = await entry.method(*entry.args, **entry.kwargs)
            except asyncio.CancelledError as exc:
                self._reject_entry(entry, exc)
                raise
            except RetryAfter as exc:
                attempt += 1
                if attempt > self._max_retry_attempts:
                    self._log.error(
                        "RateLimiter dropping send for chat %s after RetryAfter exhaustion",
                        entry.chat_id,
                        exc_info=exc,
                    )
                    self._reject_entry(entry, exc)
                    return
                entry.retries = attempt
                delay = max(float(exc.retry_after), self._retry_backoff(attempt))
                ready_at = loop.time() + delay
                self._log.warning(
                    "RateLimiter retrying send for chat %s in %.2fs (RetryAfter %.2fs, attempt %d)",
                    entry.chat_id,
                    delay,
                    float(exc.retry_after),
                    attempt,
                )
                await self._requeue(entry, ready_at)
                return
            except (TimedOut, NetworkError) as exc:
                attempt += 1
                if attempt > self._max_retry_attempts:
                    self._log.error(
                        "RateLimiter dropping send for chat %s after network retries",
                        entry.chat_id,
                        exc_info=exc,
                    )
                    self._reject_entry(entry, exc)
                    return
                entry.retries = attempt
                delay = self._retry_backoff(attempt)
                ready_at = loop.time() + delay
                self._log.warning(
                    "RateLimiter network retry for chat %s in %.2fs (attempt %d)",
                    entry.chat_id,
                    delay,
                    attempt,
                )
                await self._requeue(entry, ready_at)
                return
            except Exception as exc:  # pylint: disable=broad-except
                self._log.exception(
                    "RateLimiter encountered unexpected error dispatching chat %s",
                    entry.chat_id,
                    exc_info=exc,
                )
                self._reject_entry(entry, exc)
                return
            else:
                send_time = loop.time()
                self.record_global(send_time)
                self.record_chat_send(entry.chat_id, send_time)
                entry.retries = 0
                self._resolve_entry(entry, result)
                total_wait = max(0.0, send_time - entry.enqueued_at)
                self._log.info(
                    "RateLimiter dispatch completed for chat %s via %s (total_wait %.2fs)",
                    entry.chat_id,
                    method_name,
                    total_wait,
                )
                return

    async def _requeue(self, entry: "_QueueEntry", ready_at: float) -> None:
        assert self._queue_lock is not None
        assert self._queue_event is not None

        async with self._queue_lock:
            self._queue_seq += 1
            entry.ready_at = ready_at
            heapq.heappush(self._queue, (ready_at, self._queue_seq, entry))
            self._queue_event.set()

    def _next_global_ready(self, now: float) -> float:
        if not self._global_window:
            return now
        oldest = self._global_window[0]
        return max(now, oldest + 1.0)

    async def _send_typing_indicator(self, chat_id: int | str, delay: float) -> None:
        try:
            await self._bot.send_chat_action(chat_id=chat_id, action="typing")
            self._log.info(
                "RateLimiter sent typing indicator for chat %s due to expected delay %.2fs",
                chat_id,
                delay,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug(
                "RateLimiter typing indicator failed for chat %s: %s",
                chat_id,
                exc,
            )

    def _retry_backoff(self, attempt: int) -> float:
        # Exponential backoff: base * 2^(attempt-1)
        return self._retry_base_delay * (2 ** max(0, attempt - 1))

    async def _cancel_entry(self, entry: "_QueueEntry") -> None:
        if self._queue_lock is None or self._queue_event is None:
            return
        async with self._queue_lock:
            for index, queued in enumerate(self._queue):
                if queued[2] is entry:
                    self._queue[index] = self._queue[-1]
                    self._queue.pop()
                    if index < len(self._queue):
                        heapq.heapify(self._queue)
                    break
            self._queue_event.set()

    def _resolve_entry(self, entry: "_QueueEntry", result: Any) -> None:
        if entry.future is not None and not entry.future.done():
            entry.future.set_result(result)

    def _reject_entry(self, entry: "_QueueEntry", exc: BaseException) -> None:
        if entry.future is not None and not entry.future.done():
            entry.future.set_exception(exc)

    async def _queue_size(self) -> int:
        if self._queue_lock is None:
            return 0
        async with self._queue_lock:
            return len(self._queue)

    async def queue_metrics(self) -> Dict[str, Any]:
        """Return current queue delay metrics for diagnostics."""
        loop = self._ensure_loop()
        now = loop.time()

        if self._queue_lock is None:
            return {
                "queue_depth": 0,
                "max_delay_sec": 0.0,
                "avg_delay_sec": 0.0,
                "max_delay_chat_id": None,
                "max_delay_chat_sec": 0.0,
                "sampled_at": now,
            }

        async with self._queue_lock:
            queue_depth = len(self._queue)
            if queue_depth == 0:
                return {
                    "queue_depth": 0,
                    "max_delay_sec": 0.0,
                    "avg_delay_sec": 0.0,
                    "max_delay_chat_id": None,
                    "max_delay_chat_sec": 0.0,
                    "sampled_at": now,
                }

            delays: List[float] = []
            per_chat: Dict[int | str, float] = {}
            for ready_at, _, entry in self._queue:
                delay_val = max(0.0, ready_at - now)
                delays.append(delay_val)
                existing = per_chat.get(entry.chat_id)
                if existing is None or delay_val > existing:
                    per_chat[entry.chat_id] = delay_val

        max_delay = max(delays) if delays else 0.0
        avg_delay = sum(delays) / queue_depth if queue_depth else 0.0
        max_delay_chat_id: Optional[int | str] = None
        max_delay_chat_sec = 0.0
        if per_chat:
            max_delay_chat_id, max_delay_chat_sec = max(per_chat.items(), key=lambda item: item[1])

        return {
            "queue_depth": queue_depth,
            "max_delay_sec": max_delay,
            "avg_delay_sec": avg_delay,
            "max_delay_chat_id": max_delay_chat_id,
            "max_delay_chat_sec": max_delay_chat_sec,
            "sampled_at": now,
        }

    async def _maybe_notify_delay(self, metrics: Dict[str, Any]) -> None:
        if self._admin_chat_id_log is None:
            return

        queue_depth = metrics.get("queue_depth", 0)
        max_delay = metrics.get("max_delay_sec", 0.0)

        if queue_depth == 0 or max_delay < self._delay_alert_threshold:
            return

        loop = self._ensure_loop()
        now = loop.time()

        if self._last_delay_alert_at is not None and (now - self._last_delay_alert_at) < self._delay_alert_cooldown:
            return

        self._last_delay_alert_at = now

        avg_delay = metrics.get("avg_delay_sec", 0.0)
        worst_chat = metrics.get("max_delay_chat_id")
        worst_delay = metrics.get("max_delay_chat_sec", 0.0)

        message = (
            "Warning: rate limiter backlog detected.\n"
            f"Queue depth: {queue_depth}\n"
            f"Max delay: {max_delay:.2f}s\n"
            f"Average delay: {avg_delay:.2f}s"
        )
        if worst_chat is not None:
            message += f"\nWorst chat: {worst_chat} ({worst_delay:.2f}s)"

        loop.create_task(self._safe_notify_admin(message))
        self._log.warning(
            "RateLimiter backlog alert (queue_depth=%d, max_delay=%.2fs, avg_delay=%.2fs, worst_chat=%s, worst_delay=%.2fs)",
            queue_depth,
            max_delay,
            avg_delay,
            worst_chat,
            worst_delay,
        )

    async def _safe_notify_admin(self, text: str) -> None:
        try:
            await self._bot.send_message(chat_id=self._admin_chat_id_log, text=text)
        except Exception as exc:  # pylint: disable=broad-except
            self._log.debug("RateLimiter failed to send backlog alert: %s", exc)


@dataclass
class _QueueEntry:
    method: SendMethod
    chat_id: int | str
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    context: Optional[Any]
    future: asyncio.Future[Any]
    retries: int = field(default=0)
    enqueued_at: float = field(default=0.0)
    ready_at: float = field(default=0.0)
