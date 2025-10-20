import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from bot.handlers import log as log_handler


def _build_stats():
    return {
        "unique_users": {1, 2, 3},
        "actions": {
            "/start": 5,
            "added channel": 2,
            "clicked button": 4,
        },
        "date_range": (datetime(2025, 10, 13), datetime(2025, 10, 20)),
    }


def _build_metrics():
    return {
        "queue_depth": 7,
        "max_delay_sec": 4.25,
        "avg_delay_sec": 1.75,
        "max_delay_chat_id": 101,
        "max_delay_chat_sec": 3.5,
    }


def test_format_statistics_includes_queue_metrics():
    stats = _build_stats()
    metrics = _build_metrics()

    message = log_handler._format_statistics(stats, metrics)

    assert "<b>Queue Delay Metrics</b>" in message
    assert "- Queue depth: 7" in message
    assert "- Max delay: 4.25s" in message
    assert "- Average delay: 1.75s" in message
    assert "- Highest per-chat delay: 3.50s (chat 101)" in message


@pytest.mark.asyncio
async def test_gather_queue_metrics_handles_unconfigured_messenger(monkeypatch):
    monkeypatch.setattr(log_handler.messenger_service, "is_configured", lambda: False)

    metrics = await log_handler._gather_queue_metrics()

    assert metrics is None
