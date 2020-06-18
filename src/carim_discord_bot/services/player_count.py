import asyncio
import logging

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import discord_service
from carim_discord_bot.steam import query
from carim_discord_bot.steam import steam_service

log = logging.getLogger(__name__)


class PlayerCountService(managed_service.ManagedService):
    def __init__(self, server_name):
        super().__init__()
        self.server_name = server_name

    async def handle_message(self, message: managed_service.Message):
        pass

    async def service(self):
        while True:
            await asyncio.sleep(config.get_server(self.server_name).player_count_update_interval)
            await self.update_player_count()

    async def update_player_count(self):
        message = steam_service.Query(self.server_name)
        await steam_service.get_service_manager(self.server_name).send_message(message)
        try:
            result = await asyncio.wait_for(message.result, 10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            log.warning('update player count query timed out')
            return

        result: query.SteamData = result
        message = discord_service.PlayerCount(
            self.server_name,
            result.players,
            result.max_players,
            result.get_queue(),
            result.get_time()
        )
        await discord_service.get_service_manager().send_message(message)


services = dict()


def get_service_manager(server_name):
    if server_name not in services:
        services[server_name] = PlayerCountService(server_name)
    return services[server_name]
