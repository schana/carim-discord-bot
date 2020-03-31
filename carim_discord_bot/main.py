import argparse
import logging
import shlex

import discord

client = discord.Client()
log = None
message_parser = argparse.ArgumentParser()
message_parser.add_argument('--hello', dest='hello', action='store_true')


@client.event
async def on_ready():
    log.info(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('--'):
        args = shlex.split(message.content, comments=True)
        parsed_args = message_parser.parse_args(args)
        if parsed_args.hello:
            await message.channel.send(f'Hello, {message.author.display_name}!')


def main():
    parser = argparse.ArgumentParser(description='carim discord bot')
    parser.add_argument('-t', dest='token_path', required=True, help='path to file containing token')
    parser.add_argument('-v', dest='verbosity', help='verbosity of the output', action='count', default=0)
    args = parser.parse_args()

    log_level = logging.INFO
    if args.verbosity > 0:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
    global log
    log = logging.getLogger(__name__)

    with open(args.token_path) as f:
        token = f.read().strip()

    client.run(token)


if __name__ == '__main__':
    main()
