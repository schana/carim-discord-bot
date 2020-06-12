from carim_discord_bot import managed_service
from carim_discord_bot.managed_service import Message


class RconService(managed_service.ManagedService):

    async def service(self):
        pass

    async def handle_message(self, message: Message):
        pass


service = None


def get_service_manager():
    global service
    if service is None:
        service = RconService()
    return service
