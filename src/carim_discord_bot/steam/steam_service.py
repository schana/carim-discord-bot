import asyncio
import logging

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import discord_service
from carim_discord_bot.steam import query

log = logging.getLogger(__name__)


class Query(managed_service.Message):
    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port


class SteamService(managed_service.ManagedService):
    def __init__(self):
        super().__init__()
        self.current_count = -1

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Query):
            await query.query(message.ip, message.port, message.result)

    async def service(self):
        while True:
            await asyncio.sleep(config.get().update_player_count_interval)
            await self.update_player_count()

    async def update_player_count(self):
        message = Query(config.get().ip, config.get().steam_port)
        await self.send_message(message)
        try:
            result = await asyncio.wait_for(message.result, 10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            log.warning('update player count query timed out')
            return

        result: query.SteamData = result
        count_players = result.players
        if count_players != self.current_count:
            message = discord_service.PlayerCount(count_players, result.max_players)
            message = discord_service.Log(f'Update player count: {count_players}/{result.max_players}')
            await discord_service.get_service_manager().send_message(message)
            self.current_count = count_players


service = None


def get_service_manager():
    global service
    if service is None:
        service = SteamService()
    return service
