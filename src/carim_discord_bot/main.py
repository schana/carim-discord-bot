import argparse
import asyncio
import datetime
import json
import logging
import os
import pathlib
import re
import shlex
import sys

import discord
from pkg_resources import resource_filename

import carim_discord_bot
from carim_discord_bot import config, message_builder, setup_instructions
from carim_discord_bot.rcon import service, registrar, protocol, connection
from carim_discord_bot.steam import query


class BotArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError()


client = discord.Client()
log = logging.getLogger(__name__)
message_parser = BotArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things',
                                   formatter_class=argparse.RawTextHelpFormatter)
command_group = message_parser.add_argument_group('commands')
command_group.add_argument('--help', action='store_true', help='displays this usage information')
command_group.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
command_group.add_argument('--about', action='store_true', help='display some information about the bot')
command_group.add_argument('--version', action='store_true', help='display the current version of the bot')

admin_group = message_parser.add_argument_group('admin commands')
admin_group.add_argument('--command', nargs='?', type=str, default=argparse.SUPPRESS, metavar='command',
                         help='send command to the server, or list the available commands')
admin_group.add_argument('--safe_shutdown', nargs='?', type=int, default=argparse.SUPPRESS, metavar='seconds',
                         help='shutdown the server in a safe manner with an optional delay')
admin_group.add_argument('--schedule_status', action='store_true', help='show current scheduled item status')
admin_group.add_argument('--schedule_skip', type=int, default=argparse.SUPPRESS, metavar='index',
                         help='skip next run of scheduled command')
admin_group.add_argument('--kill', action='store_true', help='make the bot terminate')

future_queue = asyncio.Queue()
event_queue = asyncio.Queue()
chat_queue = asyncio.Queue()
restart_lock = asyncio.Lock()
current_count = None
scheduled_commands = list()


@client.event
async def on_ready():
    log.info(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id == config.get().chat_channel_id:
        await process_chat(message)
    elif message.channel.id in config.get().admin_channels and message.content.startswith('--'):
        args = shlex.split(message.content, comments=True)
        try:
            parsed_args, _ = message_parser.parse_known_args(args)
        except (ValueError, argparse.ArgumentError):
            log.info(f'invalid command {message.content}')
            return
        await process_message_args(parsed_args, message)


async def process_chat(message):
    chat_message = f'Discord> {message.author.display_name}: {message.content}'
    if len(chat_message) > 128:
        await message.channel.send(f'Message too long: {chat_message}')
        return
    chat_future = await send_command(f'say -1 {chat_message}')
    try:
        await chat_future
    except asyncio.CancelledError:
        await message.channel.send(f'Failed to send: {chat_message}')


async def process_message_args(parsed_args, message):
    if parsed_args.help:
        embed = message_builder.build_embed('Help', format_help(include_admin=True))
        await message.channel.send(embed=embed)
    if parsed_args.secret:
        await message.channel.send(f'Thank you, cnofafva, for giving me life!')
    if parsed_args.about:
        await message.channel.send(embed=message_builder.build_embed(
            'This bot is open source and can be built for any DayZ server\n'
            'For more information, visit https://github.com/schana/carim-discord-bot'))
    await process_admin_args(parsed_args, message)


async def process_admin_args(parsed_args, message):
    if 'command' in parsed_args:
        if parsed_args.command is None:
            command = 'commands'
        else:
            command = parsed_args.command
        future = await send_command(command)
        try:
            result = await future
            await message.channel.send(
                embed=message_builder.build_embed(command, f'{str(result) if result else "success"}'))
        except asyncio.CancelledError:
            await message.channel.send(embed=message_builder.build_embed(command, f'query timed out'))
    if 'safe_shutdown' in parsed_args:
        if restart_lock.locked():
            await message.channel.send(embed=message_builder.build_embed('Shutdown already scheduled'))
        else:
            if parsed_args.safe_shutdown is not None:
                await message.channel.send(embed=message_builder.build_embed('Shutdown scheduled'))
                await process_safe_shutdown(parsed_args.safe_shutdown)
            else:
                await message.channel.send(embed=message_builder.build_embed('Shutting down now'))
                await process_safe_shutdown()
    if parsed_args.schedule_status:
        commands_info = list()
        for i, sc in enumerate(scheduled_commands):
            next_run = sc['next']
            if not isinstance(next_run, str):
                next_run = datetime.timedelta(seconds=next_run)
                next_run -= datetime.timedelta(microseconds=next_run.microseconds)
                next_run = str(next_run)
            c_info = dict(index=i,
                          command=sc['command']['command'],
                          alive=not sc['task'].done(),
                          interval=sc['command']['interval'],
                          next_run=next_run)
            if sc.get('skip', False):
                c_info['skip_next'] = True
            commands_info.append(c_info)
        await message.channel.send(embed=message_builder.build_embed(
            'Scheduled Commands',
            f'```{json.dumps(commands_info, indent=1)}```'))
    if 'schedule_skip' in parsed_args:
        i = parsed_args.schedule_skip
        if not 0 <= i < len(scheduled_commands):
            await message.channel.send(embed=message_builder.build_embed('Invalid index'))
        else:
            scheduled_commands[i]['skip'] = True
    if parsed_args.kill:
        sys.exit(0)
    if parsed_args.version:
        await message.channel.send(embed=message_builder.build_embed(carim_discord_bot.VERSION))


def format_help(include_admin=False):
    formatter = message_parser._get_formatter()

    formatter.add_text(message_parser.description)

    if include_admin:
        action_groups = [command_group, admin_group]
    else:
        action_groups = [command_group]

    for action_group in action_groups:
        formatter.start_section(action_group.title)
        formatter.add_text(action_group.description)
        formatter.add_arguments(action_group._group_actions)
        formatter.end_section()

    formatter.add_text(message_parser.epilog)

    return formatter.format_help()


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


async def process_rcon_events():
    while True:
        event = await event_queue.get()
        log.info(f'got from event_queue {event}')
        if config.get().log_rcon_messages:
            if isinstance(event, tuple):
                title, description = event
                embed_args = dict(title=title, message=description)
            else:
                embed_args = dict(title=event)
            embed = message_builder.build_embed(**embed_args)
            await client.wait_until_ready()
            channel = client.get_channel(config.get().publish_channel_id)
            await channel.send(embed=embed)


async def process_rcon_chats():
    ignore_re = re.compile(config.get().chat_ignore_regex)
    while True:
        chat = await chat_queue.get()
        if not ignore_re.match(chat):
            log.info(f'got from chat_queue and sending {chat}')
            embed_args = dict(description=chat)
            channel = client.get_channel(config.get().chat_channel_id)
            await client.wait_until_ready()
            await channel.send(embed=discord.Embed(**embed_args))
        else:
            log.info(f'got from chat_queue and ignoring {chat}')


async def update_player_count_manager():
    while True:
        await asyncio.sleep(config.get().update_player_count_interval)
        await update_player_count()


async def update_player_count():
    global current_count
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    await query.query(config.get().ip, config.get().steam_port, future)
    try:
        result = await asyncio.wait_for(future, 10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        log.warning('update player count query timed out')
        return

    result: query.SteamData = result
    count_players = result.players
    if count_players != current_count:
        await client.wait_until_ready()
        channel: discord.TextChannel = client.get_channel(config.get().count_channel_id)
        player_count_string = f'{count_players}/{result.max_players} players online'
        await channel.edit(name=player_count_string)
        if config.get().log_player_count_updates:
            await event_queue.put(f'Update player count: {player_count_string}')
        current_count = count_players
    return result


async def schedule_command_manager(index, command):
    if not command.get('with_clock', False):
        await asyncio.sleep(command.get('offset', 0))
    while True:
        await schedule_command(index, command)


async def schedule_command(index, command):
    interval = command.get('interval')
    if command.get('with_clock', False):
        offset = command.get('offset', 0)
        await wait_for_aligned_time(index, interval, offset)
    else:
        time_left = interval
        while time_left > 0:
            scheduled_commands[index]['next'] = time_left
            await asyncio.sleep(2)
            time_left -= 2
    scheduled_commands[index]['next'] = 'now'
    if scheduled_commands[index].get('skip', False):
        await event_queue.put(f'Skipping scheduled command: {command.get("command")}')
        del scheduled_commands[index]['skip']
    else:
        if command.get('command') == 'safe_shutdown':
            await process_safe_shutdown(delay=command.get('delay', 0))
        else:
            await send_command(command.get('command'))


async def wait_for_aligned_time(index, interval, offset):
    while True:
        if is_time_aligned(interval, offset):
            if scheduled_commands[index]['next'] == 'now':
                await asyncio.sleep(2)
            else:
                break
        else:
            scheduled_commands[index]['next'] = get_time_to_next_command(interval, offset)
            await asyncio.sleep(2)


def is_time_aligned(interval, offset):
    if get_time_to_next_command(interval, offset) < 5:
        return True
    else:
        return False


def get_time_to_next_command(interval, offset):
    now = get_datetime_now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_elapsed = (now - midnight).total_seconds() - offset
    return interval - day_elapsed % interval


def get_datetime_now():
    return datetime.datetime.now()


async def log_queue(name, queue: asyncio.Queue):
    while True:
        item = await queue.get()
        log.info(f'{name} {item}')


def loop_exception_handler(loop, context):
    loop.default_exception_handler(context)
    loop.stop()


def main():
    parser = argparse.ArgumentParser(description='carim discord bot')
    parser.add_argument('-c', dest='config', help='path to config file', default=argparse.SUPPRESS)
    parser.add_argument('-v', dest='verbosity', help='verbosity of the output', action='count', default=0)
    parser.add_argument('--setup', nargs='?', type=str, default=argparse.SUPPRESS,
                        help='print out instructions for setting up the bot')
    args = parser.parse_args()

    if 'setup' in args:
        if args.setup is None:
            setup_instructions.print_setup_instructions()
        elif args.setup == 'bot':
            setup_instructions.print_setup_instructions_bot()
        elif args.setup == 'configuration':
            setup_instructions.print_setup_instructions_config()
        elif args.setup == 'service':
            setup_instructions.print_setup_instructions_service()
        return

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    log_level = logging.INFO

    if 'config' not in args:
        args.config = resource_filename(__name__, 'data/config.json')
        if os.name == 'posix':
            p = pathlib.Path('/etc/carim/config.json')
            if p.is_file():
                args.config = p
    settings = config.Config.build_from(args.config)
    config.set(settings)

    if config.get().debug:
        args.verbosity = max(args.verbosity, 1)

    if args.verbosity > 0:
        log_level = logging.DEBUG
    global log
    log = logging.getLogger(__name__)
    log.setLevel(log_level)
    connection.log.setLevel(log_level)
    registrar.log.setLevel(log_level)
    protocol.log.setLevel(log_level)
    service.log.setLevel(log_level)
    config.log.setLevel(log_level)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(loop_exception_handler)

    loop.run_until_complete(client.login(config.get().token))
    loop.create_task(client.connect())
    loop.run_until_complete(client.wait_until_ready())

    if config.get().presence is not None and len(config.get().presence) > 0:
        if config.get().presence_type == 'watching':
            activity_type = discord.ActivityType.watching
        elif config.get().presence_type == 'listening':
            activity_type = discord.ActivityType.listening
        else:
            activity_type = discord.ActivityType.playing
        activity = discord.Activity(type=activity_type, name=config.get().presence)
    else:
        activity = None
    loop.run_until_complete(client.change_presence(activity=activity))

    loop.run_until_complete(service.start(future_queue, event_queue, chat_queue))

    if settings.publish_channel_id is not None:
        loop.create_task(process_rcon_events())
    else:
        loop.create_task(log_queue('rcon admin', event_queue))

    if settings.chat_channel_id is not None:
        loop.create_task(process_rcon_chats())
    else:
        loop.create_task(log_queue('chat', chat_queue))

    if settings.count_channel_id is not None:
        loop.create_task(update_player_count_manager())

    for command in config.get().scheduled_commands:
        task = loop.create_task(schedule_command_manager(len(scheduled_commands), command))
        scheduled_commands.append(dict(task=task, command=command, next=-1))

    loop.run_forever()


if __name__ == '__main__':
    main()
