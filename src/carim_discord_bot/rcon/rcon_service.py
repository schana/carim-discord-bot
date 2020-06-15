from carim_discord_bot import managed_service
from carim_discord_bot.managed_service import Message


class RconService(managed_service.ManagedService):
    def __init__(self, server_name):
        super().__init__()
        self.server_name = server_name

    async def service(self):
        pass

    async def handle_message(self, message: Message):
        pass


services = dict()


def get_service_manager(server_name):
    if server_name not in services:
        services[server_name] = RconService(server_name)
    return services[server_name]
