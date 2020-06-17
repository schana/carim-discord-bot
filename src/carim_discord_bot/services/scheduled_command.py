import asyncio
import datetime
import logging

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import discord_service
from carim_discord_bot.rcon import rcon_service

log = logging.getLogger(__name__)


class Skip(managed_service.Message):
    pass


class ScheduledCommand(managed_service.ManagedService):
    def __init__(self, server_name, index):
        super().__init__()
        self.server_name = server_name
        self.index = index
        self.command = config.get_server(self.server_name).scheduled_commands[self.index]
        self.command['next'] = 'unknown'

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Skip):
            self.command['skip'] = True

    async def service(self):
        if not self.command.get('with_clock', False):
            await asyncio.sleep(self.command.get('offset', 0))
        while True:
            await self.schedule_command()
            await asyncio.sleep(5)

    async def schedule_command(self):
        interval = self.command['interval']
        if self.command.get('with_clock', False):
            await self.wait_for_aligned_time()
        else:
            time_left = interval
            while time_left > 0:
                self.command['next'] = time_left
                await asyncio.sleep(2)
                time_left -= 2
        self.command['next'] = 'now'
        if self.command.get('skip', False):
            await discord_service.get_service_manager().send_message(
                discord_service.Log(self.server_name, f'Skipping scheduled command: {self.command.get("command")}')
            )
            del self.command['skip']
        else:
            if self.command.get('command') == 'safe_shutdown':
                await rcon_service.get_service_manager(self.server_name).send_message(
                    rcon_service.SafeShutdown(self.server_name, self.command.get('delay', 0))
                )
            else:
                await rcon_service.get_service_manager(self.server_name).send_message(
                    rcon_service.Command(self.server_name, self.command['command'])
                )

    async def wait_for_aligned_time(self):
        while True:
            if self.is_time_aligned():
                if self.command['next'] == 'now':
                    await asyncio.sleep(2)
                else:
                    break
            else:
                self.command['next'] = self.get_time_to_next_command()
                await asyncio.sleep(2)

    def is_time_aligned(self):
        if self.get_time_to_next_command() < 5:
            return True
        else:
            return False

    def get_time_to_next_command(self):
        interval = self.command['interval']
        offset = self.command.get('offset', 0)
        now = datetime.datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_elapsed = (now - midnight).total_seconds() - offset
        return interval - day_elapsed % interval


services = dict()


def get_service_manager(server_name, index):
    if server_name not in services:
        services[server_name] = dict()
    if index not in services[server_name]:
        services[server_name][index] = ScheduledCommand(server_name, index)
    return services[server_name][index]
