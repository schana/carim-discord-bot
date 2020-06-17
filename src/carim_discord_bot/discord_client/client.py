import argparse
import logging
import re
import shlex

import discord

from carim_discord_bot import config, message_builder
from carim_discord_bot.discord_client import arguments

log = logging.getLogger(__name__)


class CarimClient(discord.Client):
    async def on_ready(self):
        log.info(f'Logged in as {self.user}')

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        for server_name in config.get_server_names():
            if message.channel.id == config.get_server(server_name).chat_channel_id:
                await arguments.process_chat(server_name, message)
            elif message.channel.id == config.get_server(server_name).admin_channel_id \
                    and message.content.startswith('--'):
                args = shlex.split(message.content, comments=True)
                try:
                    parsed_args, _ = arguments.message_parser.parse_known_args(args)
                except (ValueError, argparse.ArgumentError):
                    log.info(f'invalid command {message.content}')
                    return
                await arguments.process_message_args(server_name, parsed_args, message)

        for custom_command in config.get().custom_commands:
            custom_command: message_builder.Response = custom_command
            if custom_command.enabled:
                if message.channel.id in custom_command.channels or len(custom_command.channels) == 0:
                    if re.match(custom_command.command, message.content):
                        embed = custom_command.generate()
                        if len(embed) <= 6000:
                            await message.channel.send(embed=embed)
                        else:
                            await message.channel.send(f'Message longer than 6000 character limit: {len(embed)}')
