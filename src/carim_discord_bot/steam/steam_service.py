from carim_discord_bot import managed_service
from carim_discord_bot.steam import query


class Query(managed_service.Message):
    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port


class SteamService(managed_service.ManagedService):

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Query):
            await query.query(message.ip, message.port, message.result)

    async def service(self):
        pass


service = None


def get_service_manager():
    global service
    if service is None:
        service = SteamService()
    return service
