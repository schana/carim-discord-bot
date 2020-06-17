import asyncio

import pytest

# from carim_discord_bot import main


@pytest.mark.skip
@pytest.mark.asyncio
async def test_kick_everybody(monkeypatch):
    response = '''\
Players on server:
[#] [IP Address]:[Port] [Ping] [GUID] [Name]
--------------------------------------------------
2 127.0.0.1:2304 0 1234(OK) Survivor2
4 127.0.0.2:2304 32 5678(OK) Survivor4
(2 players in total)'''

    async def mock_update():
        pass

    monkeypatch.setattr(main, 'update_player_count', mock_update)

    sent_commands = list()

    async def mock_send(command):
        sent_commands.append(command)
        if command == 'players':
            future = asyncio.get_running_loop().create_future()
            future.set_result(response)
            return future

    monkeypatch.setattr(main, 'send_command', mock_send)

    await main.kick_everybody('')
    assert len(sent_commands) == 3
    assert 'kick 2' in sent_commands[1]
    assert 'kick 4' in sent_commands[2]
