from __future__ import annotations

from bot.telegram.filters.mention import IsBotMentioned


class MockMessage:
    def __init__(self, text: str = "", entities=None, reply_to_message=None):
        self.text = text
        self.entities = entities
        self.reply_to_message = reply_to_message


class MockUser:
    def __init__(self, user_id: int):
        self.id = user_id


class MockDetector:
    def __init__(self, should_match: bool):
        self.should_match = should_match

    def is_addressed(self, text, entities=None, reply_to_user_id=None):
        return self.should_match


async def test_is_bot_mentioned_filter():
    filter_instance = IsBotMentioned()

    detector_true = MockDetector(True)
    detector_false = MockDetector(False)

    msg = MockMessage(text="Hello Ista")

    assert await filter_instance(msg, mention_detector=detector_true, bot=None) is True
    assert await filter_instance(msg, mention_detector=detector_false, bot=None) is False
