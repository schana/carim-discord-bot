import shlex
from contextlib import nullcontext

import pytest

from carim_discord_bot.discord_client import arguments


@pytest.mark.parametrize('raw_arg,expected_key,expected_value,expectation', [
    ('--leaderboard kills', 'leaderboard', ['kills', 0], nullcontext()),
    ('--leaderboard kills 0', 'leaderboard', ['kills', 0], nullcontext()),
    ('--stats 12345', 'stats', [12345, 0], nullcontext()),
    ('--stats 12345 0', 'stats', [12345, 0], nullcontext()),
    ('--stats 12345 0 1', 'stats', [], pytest.raises(ValueError)),
    ('--leaderboard kills nonnumber', 'leaderboard', [], pytest.raises(ValueError))
])
def test_arg_parsing(raw_arg, expected_key, expected_value, expectation):
    with expectation:
        args = shlex.split(raw_arg)
        parsed_args, _ = arguments.user_message_parser.parse_known_args(args)
        assert expected_key in parsed_args
        assert getattr(parsed_args, expected_key) == expected_value


@pytest.mark.skip
def test_help():
    assert '' == arguments.format_help()
