import datetime

import discord

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import client
from carim_discord_bot.managed_service import Message


class PlayerCount(managed_service.Message):
    def __init__(self, count, slots):
        super().__init__()
        self.count = count
        self.slots = slots


class Log(managed_service.Message):
    def __init__(self, text):
        super().__init__()
        self.text = text


class DiscordService(managed_service.ManagedService):
    def __init__(self):
        super().__init__()
        self.client = None
        self.log_rollup = []
        self.last_log_time = datetime.datetime.now()

    async def stop(self):
        await self.client.close()
        await super().stop()

    async def service(self):
        self.client = client.CarimClient()
        await self.client.login(config.get().token)
        await self.client.connect()

    async def handle_message(self, message: Message):
        await self.client.wait_until_ready()
        if isinstance(message, PlayerCount):
            channel: discord.TextChannel = self.client.get_channel(config.get().count_channel_id)
            player_count_string = config.get().player_count_format.format(players=message.count,
                                                                          slots=message.slots)
            await channel.edit(name=player_count_string)
        elif isinstance(message, Log):
            self.log_rollup.append(message.text)
            if datetime.timedelta(seconds=10) < datetime.datetime.now() - self.last_log_time:
                channel: discord.TextChannel = self.client.get_channel(config.get().rcon_admin_log_channel_id)
                rolled_up_log = '\n'.join(self.log_rollup)
                await channel.send(f'```{rolled_up_log}```')
                self.last_log_time = datetime.datetime.now()
                self.log_rollup = list()


service = None


def get_service_manager():
    global service
    if service is None:
        service = DiscordService()
    return service
