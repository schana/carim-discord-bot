import asyncio
import datetime
import logging

from carim_discord_bot import managed_service, config

log = logging.getLogger(__name__)


class ScheduledCommand(managed_service.ManagedService):
    def __init__(self, server_name, index):
        super().__init__()
        self.server_name = server_name
        self.index = index
        self.command = None

    def set_command(self, command):
        self.command = command

    async def handle_message(self, message: managed_service.Message):
        pass

    async def service(self):
        if not self.command.get('with_clock', False):
            await asyncio.sleep(self.command.get('offset', 0))
        while True:
            await self.schedule_command()
            await asyncio.sleep(config.get().update_player_count_interval)

    async def schedule_command(self):
        interval = self.command.get('interval')
        if self.command.get('with_clock', False):
            offset = self.command.get('offset', 0)
            await self.wait_for_aligned_time(index, interval, offset)
        else:
            time_left = interval
            while time_left > 0:
                scheduled_commands[index]['next'] = time_left
                await asyncio.sleep(2)
                time_left -= 2
        scheduled_commands[index]['next'] = 'now'
        if scheduled_commands[index].get('skip', False):
            await event_queue.put(f'Skipping scheduled command: {self.command.get("command")}')
            del scheduled_commands[index]['skip']
        else:
            if self.command.get('command') == 'safe_shutdown':
                await process_safe_shutdown(delay=self.command.get('delay', 0))
            else:
                await send_command(self.command.get('command'))

    async def wait_for_aligned_time(self, index, interval, offset):
        while True:
            if self.is_time_aligned(interval, offset):
                if scheduled_commands[index]['next'] == 'now':
                    await asyncio.sleep(2)
                else:
                    break
            else:
                scheduled_commands[index]['next'] = get_time_to_next_command(interval, offset)
                await asyncio.sleep(2)

    def is_time_aligned(self, interval, offset):
        if self.get_time_to_next_command(interval, offset) < 5:
            return True
        else:
            return False

    def get_time_to_next_command(self, interval, offset):
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
