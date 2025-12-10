# Rate Limiter & Messaging Queue

## Overview

The bot can deliver outbound Telegram messages either directly or through an asynchronous queue. The queue enforces Telegram-friendly pacing and provides richer telemetry around delivery delays. By default the queue is enabled.

## Core Behavior

- **Global throttle**: Up to 30 messages per second (configurable via `GLOBAL_RATE_MESSAGES_PER_SEC`).
- **Per-chat cooldown**: At least 1 second between consecutive messages per chat (`PER_CHAT_COOLDOWN_SEC`).
- **Retry policy**: Network/timeout/429 errors back off exponentially up to three attempts.
- **Heavy-load typing indicator**: When a send is expected to wait >3 seconds, the bot immediately sends `typing` to the chat.
- **Logging & metrics**: Enqueue/dispatch events are logged; `/log` reports queue depth, average & max delay, highest per-chat delay.

## Feature Flag

Set `ENABLE_RATE_LIMITED_QUEUE` to switch between queued and direct-send modes:

```bash
ENABLE_RATE_LIMITED_QUEUE=true   # queue + pacing + metrics (default)
ENABLE_RATE_LIMITED_QUEUE=false  # bypass queue, send immediately
```

When disabled, messenger helpers call Telegram APIs directly and queue metrics report zero delay. Re-enable to restore throttling and `/log` telemetry.

## Manual Validation

Use `python scripts/validate_rate_limiter.py` to simulate bursts of messages without hitting Telegram. Key options:

| Option | Description |
| --- | --- |
| `--chats` | Number of simulated chats. |
| `--messages` | Messages per chat. |
| `--send-latency` | Artificial delay per send (seconds). |
| `--verbose` | Enable debug logging for enqueue/dispatch events. |

The script prints per-chat pacing, global spacing, typing indicator counts, and current queue metrics for quick sanity checks before production rollout.

## Automated Coverage

`tests/test_api_17.py`–`tests/test_api_20.py` verify the queue metrics formatting, backlog alert behavior, feature flag fallback, and validation script tooling.
