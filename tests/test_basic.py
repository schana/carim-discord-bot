import shlex

import pytest

from carim_discord_bot import config


@pytest.mark.skip
def test_import_modules():
    from carim_discord_bot import main
    print(main.format_help(include_admin=True))


@pytest.mark.skip
@pytest.mark.asyncio
async def test_arg_parsing(monkeypatch):
    from carim_discord_bot import main
    args = shlex.split('--safe_shutdown 3000')
    parsed_args, _ = main.message_parser.parse_known_args(args)
    print(parsed_args)

    def message(): return None

    message.channel = lambda: None
    message.channel.id = 123

    async def mock_send(*args, **kwargs):
        pass

    message.channel.send = mock_send
    config.set(config.Config.build_from_dict({
        'token': '',
        'rcon_ip': '127.0.0.1',
        'rcon_port': 42302,
        'rcon_password': 'password',
        'steam_port': 42016,
        'rcon_admin_channels': [message.channel.id]
    }))

    assert config.get().admin_channels == [message.channel.id]

    calls = []

    async def mock_process(delay=0):
        calls.append(delay)

    monkeypatch.setattr(main, 'process_safe_shutdown', mock_process)

    await main.process_message_args(parsed_args, message)

    assert len(calls) == 1
    assert calls[0] == 3000
