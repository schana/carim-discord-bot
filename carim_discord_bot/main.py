import argparse
import logging
import random
import shlex

import discord

client = discord.Client()
log = None
message_parser = argparse.ArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things')
message_parser.add_argument('--help', action='store_true', help='displays this usage information')
message_parser.add_argument('--hello', action='store_true', help='says hello to the beloved user')
message_parser.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
message_parser.add_argument('--random', nargs='?', type=int, default=argparse.SUPPRESS,
                            help='generate a random number between 0 and RANDOM (default: 100)')


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
            await message.channel.send(message_parser.format_help())
        if parsed_args.hello:
            word = random.choice(('Hello', 'Howdy', 'Greetings', 'Hiya', 'Hey'))
            await message.channel.send(f'{word}, {message.author.display_name}!')
        if parsed_args.secret:
            await message.channel.send(f'Thank you, cnofafva, for giving me life!')
        if 'random' in parsed_args:
            if parsed_args.random is None:
                parsed_args.random = 100
            await message.channel.send(f'Your random number is: {random.randint(0, parsed_args.random)}')


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
