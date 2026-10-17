import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot.commands as commands


def test_upcoming_command_unpacks_4_tuple_cleanly(monkeypatch):
    async def _test():
        # Simulate get_upcoming returning 4-tuples: (name, deadline, source, link)
        fake_hackathons = [
            ("FIND EVIL!", "2026-06-15T00:00:00", "Devpost", "https://findevil.devpost.com"),
            ("NetElixir AIgnition", "2026-06-10T00:00:00", "Unstop", "https://unstop.com/hackathons/netelixir"),
        ]
        monkeypatch.setattr(commands, "get_upcoming", lambda: fake_hackathons)

        mock_update = MagicMock()
        mock_update.effective_chat.id = 999
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        # Must execute without raising ValueError: too many values to unpack (expected 3)
        await commands.upcoming_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]

        assert "FIND EVIL!" in reply_text
        assert "https://findevil.devpost.com" in reply_text
        assert "NetElixir AIgnition" in reply_text

    asyncio.run(_test())


def test_upcoming_command_handles_empty(monkeypatch):
    async def _test():
        monkeypatch.setattr(commands, "get_upcoming", lambda: [])

        mock_update = MagicMock()
        mock_update.effective_chat.id = 999
        mock_update.message.reply_text = AsyncMock()

        await commands.upcoming_command(mock_update, MagicMock())

        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "No hackathons found" in reply_text

    asyncio.run(_test())
