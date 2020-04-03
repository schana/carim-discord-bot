import argparse
import asyncio
import json
import logging
import random
import shlex

import discord

from carim_discord_bot.rcon import service

client = discord.Client()
log = None
message_parser = argparse.ArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things')
message_parser.add_argument('--help', action='store_true', help='displays this usage information')
message_parser.add_argument('--hello', action='store_true', help='says hello to the beloved user')
message_parser.add_argument('--random', nargs='?', type=int, default=argparse.SUPPRESS,
                            help='generate a random number between 0 and RANDOM (default: 100)')
message_parser.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
message_parser.add_argument('--command', nargs='?', type=str, help=argparse.SUPPRESS, default=argparse.SUPPRESS)
future_queue = asyncio.Queue()
event_queue = asyncio.Queue()
admin_channels = []


@client.event
async def on_ready():
    log.info(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('--'):
        args = shlex.split(message.content, comments=True)
        parsed_args, _ = message_parser.parse_known_args(args)
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


def build_embed(title, message):
    embed = discord.Embed(title=title, description=message)
    return embed


async def process_rcon_events(queue, publish_channel_id):
    while True:
        event = await queue.get()
        log.info(f'got from event_queue {event}')
        channel = client.get_channel(publish_channel_id)
        await channel.send(embed=discord.Embed(title=event))


async def update_player_count(channel_id):
    await asyncio.sleep(4)
    while True:
        future = asyncio.get_running_loop().create_future()
        await future_queue.put((future, 'players'))
        try:
            result = await future
            last_line: str = result.split('\n')[-1]
            count_players = last_line.strip('()').split()[0]
            try:
                count_players = int(count_players)
                channel: discord.TextChannel = client.get_channel(channel_id)
                await channel.edit(name=f'{count_players} player{"s" if count_players != 1 else ""} online')
            except ValueError:
                log.warning('invalid data from player count')
        except asyncio.CancelledError:
            log.warning('update player count query timed out')
        await asyncio.sleep(60 * 5)


def main():
    parser = argparse.ArgumentParser(description='carim discord bot')
    parser.add_argument('-c', dest='config', required=True, help='path to config file')
    parser.add_argument('-v', dest='verbosity', help='verbosity of the output', action='count', default=0)
    args = parser.parse_args()

    log_level = logging.INFO
    if args.verbosity > 0:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    global log
    log = logging.getLogger(__name__)

    with open(args.config) as f:
        config = json.load(f)

    token = config.get('token')
    ip = config.get('rcon_ip')
    port = config.get('rcon_port')
    password = config.get('rcon_password')
    publish_channel_id = config.get('rcon_publish_channel')
    global admin_channels
    admin_channels = config.get('rcon_admin_channels')
    count_channel_id = config.get('rcon_count_channel')

    loop = asyncio.get_event_loop()
    loop.create_task(client.start(token))
    loop.create_task(process_rcon_events(event_queue, publish_channel_id))
    loop.create_task(service.start(future_queue, event_queue, ip, port, password))
    loop.create_task(update_player_count(count_channel_id))
    loop.run_forever()


if __name__ == '__main__':
    main()