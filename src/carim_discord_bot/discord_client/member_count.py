import asyncio
import logging

import discord

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import discord_service

log = logging.getLogger(__name__)


class MemberCountService(managed_service.ManagedService):
    async def handle_message(self, message: managed_service.Message):
        pass

    async def service(self):
        while True:
            await asyncio.sleep(10 * 60)
            await self.update_member_count()

    async def update_member_count(self):
        if config.get().discord_member_count_channel_id:
            client: discord.Client = discord_service.get_service_manager().client
            if not client or not client.is_ready():
                log.warning('client not ready')
                return
            channel: discord.VoiceChannel = client.get_channel(
                config.get().discord_member_count_channel_id)
            count = channel.guild.member_count
            discord_member_count_string = config.get().discord_member_count_format.format(count=count)
            await channel.edit(name=discord_member_count_string)
            log.info(f'Update member count: {discord_member_count_string}')


service = None


def get_service_manager():
    global service
    if not service:
        service = MemberCountService()
    return service
