from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import client
from carim_discord_bot.managed_service import Message


class DiscordService(managed_service.ManagedService):
    def __init__(self):
        super().__init__()
        self.client = None

    async def stop(self):
        await self.client.close()
        await super().stop()

    async def service(self):
        self.client = client.CarimClient()
        await self.client.login(config.get().token)
        await self.client.connect()

    async def handle_message(self, message: Message):
        await self.client.wait_until_ready()


service = None


def get_service_manager():
    global service
    if service is None:
        service = DiscordService()
    return service
