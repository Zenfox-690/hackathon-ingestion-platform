import asyncio
from unittest.mock import AsyncMock

import pytest

import bot.notifier as notifier


@pytest.fixture
def notifier_env(monkeypatch):
    """Setup isolated user and notification state for testing notifier."""
    users = ["123456"]
    notified_state = set()
    filters_map = {"123456": ["ai"]}

    monkeypatch.setattr(notifier, "get_users", lambda: users)
    monkeypatch.setattr(notifier, "get_filters", lambda uid: filters_map.get(uid, []))
    monkeypatch.setattr(notifier, "already_notified", lambda uid, fp: fp in notified_state)

    def mock_mark_notified(uid, fp):
        notified_state.add(fp)

    monkeypatch.setattr(notifier, "mark_notified", mock_mark_notified)

    return notified_state


def test_successful_delivery_marks_notified(notifier_env):
    async def _test():
        notified_state = notifier_env
        mock_bot = AsyncMock()
        mock_bot.send_message.return_value = True

        hackathon = {
            "name": "AI Super Challenge",
            "deadline": "2026-07-01T00:00:00",
            "source": "Devpost",
            "link": "https://ai-challenge.devpost.com",
        }

        res = await notifier.async_send_message(hackathon, bot_instance=mock_bot)
        assert res is True
        assert mock_bot.send_message.called

        # Verification: Success must mark the record as notified
        fp = notifier.generate_fingerprint(hackathon)
        assert fp in notified_state

    asyncio.run(_test())


def test_failed_delivery_does_not_mark_notified(notifier_env):
    async def _test():
        notified_state = notifier_env
        mock_bot = AsyncMock()
        # Simulate a network failure or Telegram API error
        mock_bot.send_message.side_effect = Exception("Telegram connection timed out")

        hackathon = {
            "name": "AI Super Challenge 2",
            "deadline": "2026-07-01T00:00:00",
            "source": "Devpost",
            "link": "https://ai-challenge-2.devpost.com",
        }

        # Execute notification
        await notifier.async_send_message(hackathon, bot_instance=mock_bot)

        # Invariant: Failed delivery MUST NOT be marked as notified in the database
        fp = notifier.generate_fingerprint(hackathon)
        assert fp not in notified_state

    asyncio.run(_test())


def test_synchronous_wrapper_runs_without_coroutine_warning(notifier_env):
    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = True

    hackathon = {
        "name": "AI Synchronous Test",
        "deadline": "2026-07-01T00:00:00",
        "source": "Devpost",
        "link": "https://ai-sync.devpost.com",
    }

    # Call synchronous send_message entrypoint
    notifier.send_message(hackathon, bot_instance=mock_bot)

    assert mock_bot.send_message.called
