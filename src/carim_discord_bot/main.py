import asyncio
import logging
import re

import discord

from carim_discord_bot import config, message_builder
from carim_discord_bot.rcon import service

log = logging.getLogger(__name__)


future_queue = asyncio.Queue()
event_queue = asyncio.Queue()
chat_queue = asyncio.Queue()
restart_lock = asyncio.Lock()
current_count = None
scheduled_commands = list()


async def process_safe_shutdown(delay=0):
    async with restart_lock:
        notifications_at_minutes = (60, 30, 20, 10, 5, 4, 3, 2, 1)
        notification_index = 0
        for notification in notifications_at_minutes:
            if delay / 60 < notification:
                notification_index += 1
        log.info(f'shutdown scheduled with notifications at {notifications_at_minutes[notification_index:]} minutes')
        proceed_at_minute_intervals = False
        while delay > 0:
            if delay / 60 < notifications_at_minutes[notification_index]:
                message = f'Restarting the server in {notifications_at_minutes[notification_index]} minutes'
                notification_index += 1
                await send_command(f'say -1 {message}')
                await event_queue.put(message)
                proceed_at_minute_intervals = True
            if proceed_at_minute_intervals:
                await asyncio.sleep(60)
                delay -= 60
            else:
                await asyncio.sleep(1)
                delay -= 1

        await event_queue.put('shutdown -> kicking')
        await kick_everybody('Server is restarting')

        await event_queue.put('shutdown -> locking')
        await event_queue.put('shutdown -> wait for a minute')
        # Lock RCon command doesn't seem to work, so instead we loop
        # kicking players. It could be more complex and only kick if people
        # join, but this seems like the simpler solution
        # await send_command('#lock')
        time_left = 60
        while time_left > 0:
            await kick_everybody(f'Server locked, restarting in {time_left} seconds')
            await asyncio.sleep(2)
            time_left -= 2

        await event_queue.put('shutdown -> shutting down')
        await send_command('#shutdown')


async def kick_everybody(message):
    await update_player_count()
    future = await send_command('players')
    try:
        raw_players = await asyncio.wait_for(future, 10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        log.warning('player query timed out')
        return
    count_players = 0 if current_count is None else current_count
    player_ids = range(count_players)
    if raw_players is not None:
        player_lines = raw_players.split('\n')[3:-1]
        player_ids = [line.split()[0] for line in player_lines]
    for i in player_ids:
        command = f'kick {i} {message}'
        await send_command(command)
        log.info(command)


async def send_command(command):
    future = asyncio.get_running_loop().create_future()
    await future_queue.put((future, command))
    return future


def main():
    loop.run_until_complete(service.start(future_queue, event_queue, chat_queue))

    if settings.publish_channel_id is not None:
        loop.create_task(process_rcon_events())
    else:
        loop.create_task(log_queue('rcon admin', event_queue))

    if settings.chat_channel_id is not None:
        loop.create_task(process_rcon_chats())
    else:
        loop.create_task(log_queue('chat', chat_queue))

    for command in config.get().scheduled_commands:
        task = loop.create_task(schedule_command_manager(len(scheduled_commands), command))
        scheduled_commands.append(dict(task=task, command=command, next=-1))

    loop.run_forever()
