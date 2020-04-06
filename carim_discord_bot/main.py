import argparse
import asyncio
import datetime
import json
import logging
import random
import shlex
import sys

import discord

from carim_discord_bot.rcon import service, registrar, protocol

client = discord.Client()
log = None
message_parser = argparse.ArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things')
message_parser.add_argument('--help', action='store_true', help='displays this usage information')
message_parser.add_argument('--hello', action='store_true', help='says hello to the beloved user')
message_parser.add_argument('--random', nargs='?', type=int, default=argparse.SUPPRESS,
                            help='generate a random number between 0 and RANDOM (default: 100)')
message_parser.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
message_parser.add_argument('--command', nargs='?', type=str, help=argparse.SUPPRESS, default=argparse.SUPPRESS)
message_parser.add_argument('--kill', action='store_true', help=argparse.SUPPRESS)
future_queue = asyncio.Queue()
event_queue = asyncio.Queue()
chat_queue = asyncio.Queue()
admin_channels = []
chat_channel_id = 0


@client.event
async def on_ready():
    log.info(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id == chat_channel_id:
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
        await message.channel.send(embed=build_embed('Help', message_parser.format_help()))
    if parsed_args.hello:
        word = random.choice(('Hello', 'Howdy', 'Greetings', 'Hiya', 'Hey'))
        await message.channel.send(f'{word}, {message.author.display_name}!')
    if parsed_args.secret:
        await message.channel.send(f'Thank you, cnofafva, for giving me life!')
    if 'random' in parsed_args:
        if parsed_args.random is None:
            parsed_args.random = 100
        await message.channel.send(embed=build_embed('Random number', f'{random.randint(0, parsed_args.random)}'))
    if message.channel.id in admin_channels:
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
            await message.channel.send(embed=build_embed(command, f'{str(result)}'))
        except asyncio.CancelledError:
            await message.channel.send(embed=build_embed(command, f'query timed out'))
    if parsed_args.kill:
        sys.exit(0)


def build_embed(title, message):
    embed = discord.Embed(title=title, description=message)
    return embed


async def process_rcon_events(publish_channel_id):
    while True:
        event = await event_queue.get()
        if isinstance(event, tuple):
            title, description = event
            embed_args = dict(title=title, description=description)
        else:
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            embed_args = dict(title=event, description=timestamp)
        log.info(f'got from event_queue {event}')
        await client.wait_until_ready()
        channel = client.get_channel(publish_channel_id)
        await channel.send(embed=discord.Embed(**embed_args))


async def process_rcon_chats():
    while True:
        chat = await chat_queue.get()
        embed_args = dict(description=chat)
        log.info(f'got from chat_queue {chat}')
        await client.wait_until_ready()
        channel = client.get_channel(chat_channel_id)
        await channel.send(embed=discord.Embed(**embed_args))


async def update_player_count(channel_id):
    while True:
        sleep_for = 60 * 5
        await asyncio.sleep(sleep_for)
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
            await client.wait_until_ready()
            channel: discord.TextChannel = client.get_channel(channel_id)
            player_count_string = f'{count_players} player{"s" if count_players != 1 else ""} online'
            await channel.edit(name=player_count_string)
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            await event_queue.put(('Update player count', f'{player_count_string}\n{timestamp}'))
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
    parser.add_argument('-c', dest='config', required=True, help='path to config file')
    parser.add_argument('-v', dest='verbosity', help='verbosity of the output', action='count', default=0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    log_level = logging.INFO
    if args.verbosity > 0:
        log_level = logging.DEBUG
    global log
    log = logging.getLogger(__name__)
    log.setLevel(log_level)
    registrar.log.setLevel(log_level)
    protocol.log.setLevel(log_level)
    service.log.setLevel(log_level)

    with open(args.config) as f:
        config = json.load(f)

    token = config['token']
    ip = config['rcon_ip']
    port = config['rcon_port']
    password = config['rcon_password']
    publish_channel_id = config.get('rcon_admin_log_channel')
    if publish_channel_id is None:
        publish_channel_id = config.get('rcon_publish_channel')
        if publish_channel_id is not None:
            log.warning('carim.json rcon_publish_channel is deprecated, use rcon_admin_log_channel instead')

    global admin_channels, chat_channel_id
    admin_channels = config.get('rcon_admin_channels', list())
    chat_channel_id = config.get('rcon_chat_channel')
    count_channel_id = config.get('rcon_count_channel')

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(loop_exception_handler)

    loop.run_until_complete(client.login(token))
    loop.create_task(client.connect())

    loop.run_until_complete(service.start(future_queue, event_queue, chat_queue, ip, port, password))

    if publish_channel_id is not None:
        loop.create_task(process_rcon_events(publish_channel_id))
    else:
        loop.create_task(log_queue('rcon admin', event_queue))

    if chat_channel_id is not None:
        loop.create_task(process_rcon_chats())
    else:
        loop.create_task(log_queue('chat', chat_queue))

    if count_channel_id is not None:
        loop.create_task(update_player_count(count_channel_id))

    loop.run_forever()


if __name__ == '__main__':
    main()
