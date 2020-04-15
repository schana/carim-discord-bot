import asyncio
import datetime

import pytest

from carim_discord_bot import main


@pytest.mark.asyncio
async def test_with_clock_should_send_one_command_per_interval(event_loop: asyncio.BaseEventLoop):
    sent_commands = []
    main.scheduled_commands.append(dict(task=None, command='', next=-1))

    async def mock_send_command(c):
        sent_commands.append(c)

    main.send_command = mock_send_command

    now = datetime.datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_elapsed = (now - midnight).total_seconds()

    index = 0
    command = {
        'command': 'test command',
        'interval': day_elapsed - .1,
        'with_clock': True
    }

    task = event_loop.create_task(main.schedule_command_manager(index, command))
    await asyncio.sleep(.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert len(sent_commands) == 1
