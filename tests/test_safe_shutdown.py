import pytest

from carim_discord_bot import main


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
        last_line: str = response.split('\n')[-1]
        count_players = last_line.strip('()').split()[0]
        count_players = int(count_players)
        main.current_count = count_players
        return response

    monkeypatch.setattr(main, 'update_player_count', mock_update)

    sent_commands = list()

    async def mock_send(command):
        sent_commands.append(command)

    monkeypatch.setattr(main, 'send_command', mock_send)

    result = await main.update_player_count()
    assert response == result

    await main.kick_everybody('')
    assert len(sent_commands) == 2
    assert 'kick 2' in sent_commands[0]
    assert 'kick 4' in sent_commands[1]
