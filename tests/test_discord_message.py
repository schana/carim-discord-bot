import json

import pytest

from carim_discord_bot.discord_client import discord_service


@pytest.mark.parametrize('fields,expected_messages,expected_fields', [
    (['a' * 2000], 1, 2),
    (['a' * 1000] * 8, 2, 8)
])
def test_build_fields(fields, expected_messages, expected_fields):
    messages = discord_service.build_fields('test', fields)
    print(json.dumps(messages, indent=2))
    assert expected_messages == len(messages)
    assert expected_fields == sum(len(m) for m in messages)
