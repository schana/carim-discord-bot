import asyncio
import logging

from carim_discord_bot import managed_service, config
from carim_discord_bot.steam import query

log = logging.getLogger(__name__)


class Query(managed_service.Message):
    pass


class SteamService(managed_service.ManagedService):
    def __init__(self, server_name):
        super().__init__()
        self.server_name = server_name

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Query):
            await query.query(config.get_server(self.server_name).ip,
                              config.get_server(self.server_name).steam_port,
                              message.result)

    async def service(self):
        while True:
            await asyncio.sleep(1)


services = dict()


def get_service_manager(server_name):
    if server_name not in services:
        services[server_name] = SteamService(server_name)
    return services[server_name]
