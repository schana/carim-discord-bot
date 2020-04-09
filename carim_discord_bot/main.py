import argparse
import asyncio
import json
import logging
import os
import random
import shlex
import sys

import discord
from pkg_resources import resource_filename

import carim_discord_bot
from carim_discord_bot import config, message_builder
from carim_discord_bot.rcon import service, registrar, protocol

client = discord.Client()
log = None
message_parser = argparse.ArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things',
                                         formatter_class=argparse.RawTextHelpFormatter)
command_group = message_parser.add_argument_group('commands')
command_group.add_argument('--help', action='store_true', help='displays this usage information')
command_group.add_argument('--hello', action='store_true', help='says hello to the beloved user')
command_group.add_argument('--random', nargs='?', type=int, default=argparse.SUPPRESS, metavar='num',
                           help='generate a random number between 0 and 100 or num if specified')
command_group.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
command_group.add_argument('--about', action='store_true', help='display some information about the bot')

admin_group = message_parser.add_argument_group('admin commands')
admin_group.add_argument('--command', nargs='?', type=str, default=argparse.SUPPRESS, metavar='command',
                         help='send command to the server, or list the available commands')
admin_group.add_argument('--kill', action='store_true', help='make the bot terminate')
admin_group.add_argument('--version', action='store_true', help='display the current version of the bot')

future_queue = asyncio.Queue()
event_queue = asyncio.Queue()
chat_queue = asyncio.Queue()


@client.event
async def on_ready():
    log.info(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id == config.get().chat_channel_id:
        chat_message = f'Discord> {message.author.display_name}: {message.content}'
        future = asyncio.get_running_loop().create_future()
        await future_queue.put((future, f'say -1 {chat_message}'))
        return

    if message.content.startswith('--'):
        args = shlex.split(message.content, comments=True)
        parsed_args, _ = message_parser.parse_known_args(args)
        await process_message_args(parsed_args, message)


async def process_message_args(parsed_args, message):
    if parsed_args.help:
        include_admin = message.channel.id in config.get().admin_channels
        embed = message_builder.build_embed(f'{"Admin " if include_admin else ""}Help',
                                            format_help(include_admin=include_admin))
        await message.channel.send(embed=embed)
    if parsed_args.hello:
        word = random.choice(('Hello', 'Howdy', 'Greetings', 'Hiya', 'Hey'))
        await message.channel.send(f'{word}, {message.author.display_name}!')
    if parsed_args.secret:
        await message.channel.send(f'Thank you, cnofafva, for giving me life!')
    if 'random' in parsed_args:
        if parsed_args.random is None:
            parsed_args.random = 100
        await message.channel.send(
            embed=message_builder.build_embed(f'Random number: {random.randint(0, parsed_args.random)}'))
    if parsed_args.about:
        await message.channel.send(embed=message_builder.build_embed(
            'This bot is open source and can be built for any DayZ server\n'
            'For more information, visit https://github.com/schana/carim-discord-bot'))
    if message.channel.id in config.get().admin_channels:
        await process_admin_args(parsed_args, message)


async def process_admin_args(parsed_args, message):
    if 'command' in parsed_args:
        if parsed_args.command is None:
            command = 'commands'
        else:
            command = parsed_args.command
        future = asyncio.get_running_loop().create_future()
        await future_queue.put((future, command))
        try:
            result = await future
            await message.channel.send(embed=message_builder.build_embed(command, f'{str(result)}'))
        except asyncio.CancelledError:
            await message.channel.send(embed=message_builder.build_embed(command, f'query timed out'))
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
    while True:
        chat = await chat_queue.get()
        embed_args = dict(description=chat)
        log.info(f'got from chat_queue {chat}')
        await client.wait_until_ready()
        channel = client.get_channel(config.get().chat_channel_id)
        await channel.send(embed=discord.Embed(**embed_args))


async def update_player_count():
    current_count = None
    while True:
        await asyncio.sleep(config.get().update_player_count_interval)
        future = asyncio.get_running_loop().create_future()
        await future_queue.put((future, 'players'))
        try:
            result = await asyncio.wait_for(future, 10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            log.warning('update player count query timed out')
            continue
        last_line: str = result.split('\n')[-1]
        count_players = last_line.strip('()').split()[0]
        try:
            count_players = int(count_players)
            if count_players != current_count:
                await client.wait_until_ready()
                channel: discord.TextChannel = client.get_channel(config.get().count_channel_id)
                player_count_string = f'{count_players} player{"s" if count_players != 1 else ""} online'
                await channel.edit(name=player_count_string)
                if config.get().log_player_count_updates:
                    await event_queue.put(f'Update player count: {player_count_string}')
                current_count = count_players
        except ValueError:
            log.warning('invalid data from player count')


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
            print_setup_instructions()
        elif args.setup == 'bot':
            print_setup_instructions_bot()
        elif args.setup == 'configuration':
            print_setup_instructions_config()
        elif args.setup == 'service':
            print_setup_instructions_service()
        return

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    log_level = logging.INFO

    if 'config' not in args:
        args.config = resource_filename(__name__, 'data/config.json')
    settings = config.Config.build_from(args.config)
    config.set(settings)

    if config.get().debug:
        args.verbosity = max(args.verbosity, 1)

    if args.verbosity > 0:
        log_level = logging.DEBUG
    global log
    log = logging.getLogger(__name__)
    log.setLevel(log_level)
    registrar.log.setLevel(log_level)
    protocol.log.setLevel(log_level)
    service.log.setLevel(log_level)
    config.log.setLevel(log_level)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(loop_exception_handler)

    loop.run_until_complete(client.login(config.get().token))
    loop.create_task(client.connect())

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
        loop.create_task(update_player_count())

    loop.run_forever()


def print_setup_instructions():
    header = 'Setup instructions for the Carim Discord Bot'
    print_header(header)
    print('For additional help, visit the Carim Discord at https://discord.gg/kdPnVu4')
    print()
    print_setup_instructions_bot()
    print_setup_instructions_config()
    print_setup_instructions_service()


def print_setup_instructions_bot():
    permissions = ('Manage Channels', 'View Channels', 'Send Messages')
    required_permissions = ', '.join(f'"{p}"' for p in permissions[:-1])
    required_permissions += f', and "{permissions[-1]}"'
    print_header('Create bot account')
    print('Follow the guide at https://discordpy.readthedocs.io/en/v1.3.3/discord.html')
    print('Save the token for later')
    print()
    print('In step 6 under "Creating a Bot Account", make sure "Public Bot" is unticked')
    print()
    print('Under "Inviting Your Bot", step 6 has you setup the permissions for the bot')
    print(f'Currently, the bot needs {required_permissions}')
    print()


def print_setup_instructions_config():
    print_header('Update configuration')
    config_template_path = resource_filename(__name__, 'data/config.json')
    config_descriptions_path = resource_filename(__name__, 'data/config_descriptions.json')
    print('The configuration file is located at:')
    print(config_template_path)
    print()
    print('Edit this file with your values following the descriptions below:')
    with open(config_descriptions_path) as f:
        descriptions = json.load(f)
    for entry_type in ('required', 'optional', 'log_events_in_discord'):
        print(entry_type.upper())
        for entry, description in descriptions.get(entry_type, dict()).items():
            print(' ', f'"{entry}"', ':', description)
    print()
    print('To get Discord Channel IDs, you need to enable developer mode in the app:')
    print('  Settings -> Appearance -> Advanced -> Developer Mode')
    print('Then, you will be able to right click on a Channel and select "Copy ID"')
    print()


def print_setup_instructions_service():
    print_header('Run the bot as a service')
    if os.name == 'nt':
        print('Setting up a service in Windows using sc')
        print()
        print('STEPS')
        steps = (
            'Ensure your bot runs with your configuration by calling "carim-bot" from command prompt',
            '  Use Ctrl+C to quit the running process, or use --kill from the admin channel in discord',
            'Create the service with the following command',
            '  sc create CarimBot start= delayed-auto binpath= carim-bot'
        )
        for step in steps:
            print(' ', step)
        print()
    elif os.name == 'posix':
        print('Setting up a systemd service in Linux')
        print()
        service_template_path = resource_filename(__name__, 'data/carim.service')
        print(f'Service file: {service_template_path}')
        print('STEPS')
        steps = (
            'Ensure your bot runs with your configuration by calling "carim-bot" from the terminal',
            '  Use Ctrl+C to quit the running process, or use --kill from the admin channel in discord',
            'Copy the service file to /etc/systemd/system/carim.service',
            'Enable and start the service with the following commands:',
            '  sudo systemctl enable carim.service',
            '  sudo systemctl start carim.service'
        )
        for step in steps:
            print(' ', step)
        print()
    else:
        print('no instructions available for your platform')
    print()


def print_header(header):
    box = '+' + '-' * (len(header) + 2) + '+'
    print(box)
    print('| ' + header + ' |')
    print(box)


if __name__ == '__main__':
    main()
