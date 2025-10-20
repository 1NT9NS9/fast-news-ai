#!/usr/bin/env python3
"""Manual validation helper for the outbound rate limiter.

The script simulates bursts of outbound messages across multiple chats, letting
you verify global limits, per-chat cooldowns, backlog metrics, and admin-alert
behavior without hitting the live Telegram API.

Examples:
    # Simulate 3 chats sending 15 messages each, 50ms bot latency
    python scripts/validate_rate_limiter.py --chats 3 --messages 15 --send-latency 0.05

    # Stress the queue with heavier load and verbose logging
    python scripts/validate_rate_limiter.py --chats 5 --messages 40 --send-latency 0.1 --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.services.rate_limiter import RateLimiter  # noqa: E402


class DummyBot:
    """Minimal bot stub that records send timestamps."""

    def __init__(self, send_latency: float) -> None:
        self.send_latency = max(0.0, float(send_latency))
        self.sent: List[Tuple[float, int, str]] = []
        self.typing: List[Tuple[float, int]] = []

    async def send_message(self, chat_id: int | str, text: str, **_: Any) -> Dict[str, Any]:
        await asyncio.sleep(self.send_latency)
        timestamp = asyncio.get_running_loop().time()
        self.sent.append((timestamp, chat_id, text))
        return {"chat_id": chat_id, "text": text}

    async def send_chat_action(self, chat_id: int | str, action: str) -> None:
        timestamp = asyncio.get_running_loop().time()
        self.typing.append((timestamp, chat_id))


async def _dispatch_burst(limiter: RateLimiter, bot: DummyBot, chats: int, messages_per_chat: int) -> None:
    futures: List[asyncio.Future[Any]] = []
    loop = asyncio.get_running_loop()
    for offset, chat_index in enumerate(range(chats)):
        chat_id = chat_index + 1
        for message_index in range(messages_per_chat):
            text = f"chat{chat_id}-msg{message_index+1}"
            future = await limiter.enqueue_send(
                bot.send_message,
                chat_id=chat_id,
                args=(chat_id, text),
                kwargs={},
                context={"enqueued_by": "validate_rate_limiter", "offset": offset},
            )
            if isinstance(future, asyncio.Future):
                futures.append(future)
            else:  # pragma: no cover - enqueue_send currently always returns Future
                futures.append(loop.create_future())
                futures[-1].set_result(future)
    await asyncio.gather(*futures)


def _format_seconds(value: float) -> str:
    return f"{value:.3f}s"


def _summarize(bot: DummyBot) -> Dict[str, Any]:
    per_chat_times: Dict[int | str, List[float]] = defaultdict(list)
    if not bot.sent:
        return {"total_messages": 0, "per_chat": {}, "global": {}}

    sorted_events = sorted(bot.sent, key=lambda item: item[0])
    first_ts = sorted_events[0][0]
    last_ts = sorted_events[-1][0]
    per_chat_counts: Dict[int | str, int] = defaultdict(int)

    for timestamp, chat_id, _ in sorted_events:
        per_chat_counts[chat_id] += 1
        per_chat_times[chat_id].append(timestamp)

    per_chat_stats: Dict[int | str, Dict[str, Any]] = {}
    for chat_id, timestamps in per_chat_times.items():
        deltas = [
            current - previous
            for previous, current in zip(timestamps, timestamps[1:])
        ]
        per_chat_stats[chat_id] = {
            "count": len(timestamps),
            "first_at": timestamps[0] - first_ts,
            "last_at": timestamps[-1] - first_ts,
            "min_delta": min(deltas) if deltas else None,
            "max_delta": max(deltas) if deltas else None,
            "avg_delta": statistics.mean(deltas) if deltas else None,
        }

    global_deltas = [
        current[0] - previous[0]
        for previous, current in zip(sorted_events, sorted_events[1:])
    ]

    return {
        "total_messages": len(sorted_events),
        "duration": last_ts - first_ts,
        "per_chat": per_chat_stats,
        "global": {
            "min_delta": min(global_deltas) if global_deltas else None,
            "max_delta": max(global_deltas) if global_deltas else None,
            "avg_delta": statistics.mean(global_deltas) if global_deltas else None,
        },
        "typing_events": len(bot.typing),
    }


def _print_summary(summary: Dict[str, Any], queue_metrics: Dict[str, Any]) -> None:
    print("\n=== Dispatch Summary ===")
    print(f"Total messages sent: {summary['total_messages']}")
    duration = summary.get("duration")
    if duration is not None:
        print(f"Elapsed wall time: {_format_seconds(duration)}")
    print(f"Typing indicators triggered: {summary['typing_events']}")

    print("\nPer-chat breakdown:")
    if not summary["per_chat"]:
        print("  (no messages sent)")
    else:
        for chat_id, stats in sorted(summary["per_chat"].items(), key=lambda item: item[0]):
            print(f"  Chat {chat_id}: {stats['count']} messages")
            print(f"    First at +{_format_seconds(stats['first_at'])}")
            print(f"    Last at +{_format_seconds(stats['last_at'])}")
            if stats["min_delta"] is not None:
                print(f"    delta_min={_format_seconds(stats['min_delta'])}, delta_avg={_format_seconds(stats['avg_delta'])}, delta_max={_format_seconds(stats['max_delta'])}")
            else:
                print("    only one message, no spacing metrics")

    print("\nGlobal pacing:")
    global_stats = summary["global"]
    if global_stats["min_delta"] is None:
        print("  Insufficient data to compute global deltas.")
    else:
        print(f"  delta_min={_format_seconds(global_stats['min_delta'])}, delta_avg={_format_seconds(global_stats['avg_delta'])}, delta_max={_format_seconds(global_stats['max_delta'])}")

    print("\nQueue metrics at completion:")
    print(f"  Queue depth: {queue_metrics['queue_depth']}")
    print(f"  Max delay: {_format_seconds(queue_metrics['max_delay_sec'])}")
    print(f"  Avg delay: {_format_seconds(queue_metrics['avg_delay_sec'])}")
    worst_chat = queue_metrics.get("max_delay_chat_id")
    if worst_chat is None:
        print("  No per-chat delays recorded.")
    else:
        print(f"  Worst chat {worst_chat} delay: {_format_seconds(queue_metrics['max_delay_chat_sec'])}")


async def main_async(args: argparse.Namespace) -> None:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    bot = DummyBot(send_latency=args.send_latency)
    limiter = RateLimiter(
        bot=bot,
        global_rate_per_sec=args.global_rate,
        per_chat_cooldown_sec=args.per_chat_cooldown,
    )

    await limiter.start()
    try:
        start_time = asyncio.get_running_loop().time()
        await _dispatch_burst(limiter, bot, args.chats, args.messages)
        end_time = asyncio.get_running_loop().time()
        summary = _summarize(bot)
        summary["duration"] = end_time - start_time
        queue_metrics = await limiter.queue_metrics()
    finally:
        await limiter.stop()

    _print_summary(summary, queue_metrics)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate outbound sends through the rate limiter.")
    parser.add_argument("--chats", type=int, default=3, help="Number of simulated chats.")
    parser.add_argument("--messages", type=int, default=20, help="Messages per chat.")
    parser.add_argument("--global-rate", type=int, default=30, help="Global messages per second.")
    parser.add_argument("--per-chat-cooldown", type=float, default=1.0, help="Minimum seconds between sends per chat.")
    parser.add_argument("--send-latency", type=float, default=0.05, help="Artificial latency per send (seconds).")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging for the limiter.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
