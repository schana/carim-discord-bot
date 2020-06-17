import asyncio
import datetime
import hashlib
import logging

import discord

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import client
from carim_discord_bot.managed_service import Message

log = logging.getLogger(__name__)


class PlayerCount(managed_service.Message):
    def __init__(self, server_name, count, slots):
        super().__init__(server_name)
        self.count = count
        self.slots = slots


class Chat(managed_service.Message):
    def __init__(self, server_name, content):
        super().__init__(server_name)
        self.content = content


class Log(managed_service.Message):
    def __init__(self, server_name, text):
        super().__init__(server_name)
        self.text = text


class DiscordService(managed_service.ManagedService):
    def __init__(self):
        super().__init__()
        self.client = None
        self.log_rollup = {name: list() for name in config.get_server_names()}
        start_date = datetime.datetime.now().replace(year=1984)
        self.last_log_time = {name: start_date for name in config.get_server_names()}
        self.last_player_count_update = {name: start_date for name in config.get_server_names()}

    async def stop(self):
        await self.client.close()
        await super().stop()

    async def service(self):
        self.client = client.CarimClient()
        await self.client.login(config.get().token)
        asyncio.create_task(self.client.connect())
        await self.set_presence()
        while True:
            await asyncio.sleep(1)
            await self.flush_log()

    async def set_presence(self):
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
        await self.client.wait_until_ready()
        await self.client.change_presence(activity=activity)

    async def handle_message(self, message: Message):
        await self.client.wait_until_ready()
        if isinstance(message, PlayerCount):
            await self.handle_player_count_message(message)
        elif isinstance(message, Log):
            log.info(f'log {message.server_name}: {message.text}')
            self.log_rollup[message.server_name].append(f'{message.text}')
        elif isinstance(message, Chat):
            log.info(f'chat {message.server_name}: {message.content}')
            channel_id = config.get_server(message.server_name).chat_channel_id
            if channel_id:
                channel: discord.TextChannel = self.client.get_channel(channel_id)
                await channel.send(embed=discord.Embed(description=message.content))

    async def handle_player_count_message(self, message: PlayerCount):
        channel: discord.TextChannel = self.client.get_channel(
            config.get_server(message.server_name).player_count_channel_id)
        player_count_string = config.get_server(message.server_name).player_count_format.format(
            players=message.count, slots=message.slots)
        if datetime.timedelta(minutes=5) < \
                datetime.datetime.now() - self.last_player_count_update[message.server_name]:
            # Rate limit is triggered when updating a channel name too often, so we need to
            # put a hard limit on how often the player count channel gets updated
            await channel.edit(name=player_count_string)
            self.last_player_count_update[message.server_name] = datetime.datetime.now()

    async def flush_log(self):
        color_options = [
            0x9c27b0,
            0x3f51b5,
            0x2196f3,
            0x03a9f4,
            0x00bcd4,
            0x009688,
            0x4caf50,
            0x8bc34a,
            0xcddc39,
            0xffeb3b,
            0xffc107,
            0xff9800,
            0x795548,
            0x607d8b
        ]
        await self.client.wait_until_ready()
        for server_name in config.get_server_names():
            server_color = color_options[
                int.from_bytes(hashlib.sha256(bytes(server_name, encoding='utf-8')).digest()[-4:], 'big') % len(color_options)]
            if self.log_rollup[server_name] and datetime.timedelta(seconds=10) < \
                    datetime.datetime.now() - self.last_log_time[server_name]:
                channel: discord.TextChannel = self.client.get_channel(
                    config.get_server(server_name).admin_channel_id)
                rolled_up_log = '\n'.join([f'**{server_name}**'] + self.log_rollup[server_name])
                await channel.send(embed=discord.Embed(description=f'{rolled_up_log}',
                                                       color=server_color))
                self.last_log_time[server_name] = datetime.datetime.now()
                self.log_rollup[server_name] = list()


service = None


def get_service_manager():
    global service
    if service is None:
        service = DiscordService()
    return service
