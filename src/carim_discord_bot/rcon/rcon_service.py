import asyncio
import logging

from carim_discord_bot import managed_service, config
from carim_discord_bot.discord_client import discord_service
from carim_discord_bot.rcon import registrar, protocol, connection

VALID_COMMANDS = ('players', 'admins', 'kick', 'bans', 'ban', 'removeBan', 'say', 'addBan', '#shutdown')
log = logging.getLogger(__name__)


class Command(managed_service.Message):
    def __init__(self, server_name, command):
        super().__init__(server_name)
        self.command = command


class SafeShutdown(managed_service.Message):
    def __init__(self, server_name, delay):
        super().__init__(server_name)
        self.delay = delay


class RconService(managed_service.ManagedService):
    def __init__(self, server_name):
        super().__init__()
        self.server_name = server_name
        self.rcon_registrar = registrar.Registrar(self.server_name)
        self.transport = None
        self.rcon_protocol = None
        self.restart_lock = asyncio.Lock()

    async def start(self):
        await self.rcon_registrar.reset()
        try:
            await asyncio.wait_for(self.create_datagram_endpoint(), timeout=5)
            await asyncio.wait_for(self.rcon_protocol.logged_in_event.wait(), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            log.info(f'{self.server_name} login timed out')
            await asyncio.sleep(5)
            await self.restart()
            return
        self.tasks.append(asyncio.create_task(self.keep_alive_manager()))
        await super().start()

    async def stop(self):
        await super().stop()
        if self.rcon_protocol is not None:
            self.rcon_protocol.logged_in = False
            self.rcon_protocol.logged_in_event.clear()
        if self.transport is not None:
            self.transport.close()

    async def service(self):
        while True:
            await asyncio.sleep(1)

    async def create_datagram_endpoint(self):
        self.transport, self.rcon_protocol = await asyncio.get_running_loop().create_datagram_endpoint(
            connection.ProtocolFactory(self.server_name, self.rcon_registrar).get,
            remote_addr=(config.get_server(self.server_name).ip,
                         config.get_server(self.server_name).rcon_port))

    async def keep_alive_manager(self):
        RCON_KEEP_ALIVE_INTERVAL = 30
        while True:
            await asyncio.sleep(RCON_KEEP_ALIVE_INTERVAL)
            try:
                log.debug(f'{self.server_name} sending keep alive')
                await self.keep_alive()
            except asyncio.CancelledError:
                log.warning(f'{self.server_name} keep alive timed out')
                await self.discord_log('keep alive timed out')
                return

    async def keep_alive(self):
        seq_number = await self.rcon_registrar.get_next_sequence_number()
        packet = protocol.Packet(protocol.Command(seq_number))
        future = asyncio.get_running_loop().create_future()
        await self.rcon_registrar.register(packet.payload.sequence_number, future)
        self.rcon_protocol.send_rcon_datagram(packet.generate())
        await future
        if config.get_server(self.server_name).log_rcon_keep_alive:
            await self.discord_log('keep alive')

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Command):
            await self.handle_command(message)
        elif isinstance(message, SafeShutdown):
            asyncio.create_task(self.safe_shutdown(message.delay))

    async def handle_command(self, command_message: Command):
        command = command_message.command
        future = command_message.result
        log.info(f'{self.server_name} command received: {command}')
        if command == 'commands':
            future.set_result(VALID_COMMANDS)
        elif not self.rcon_protocol.logged_in:
            log.warning(f'{self.server_name} not logged in, cancelling command: {command}')
            future.cancel()
        elif command.split()[0] in VALID_COMMANDS:
            seq_number = await self.rcon_registrar.get_next_sequence_number()
            packet = protocol.Packet(protocol.Command(seq_number, command=command))
            command_future = asyncio.get_running_loop().create_future()
            await self.rcon_registrar.register(packet.payload.sequence_number, command_future)
            self.rcon_protocol.send_rcon_datagram(packet.generate())
            try:
                await command_future
                future.set_result(command_future.result().payload.data)
            except asyncio.CancelledError:
                log.warning(f'{self.server_name} command cancelled: {command}')
                future.cancel()
        else:
            future.set_result('invalid command')

    async def safe_shutdown(self, delay):
        log.info(f'{self.server_name} safe_shutdown called with delay {delay}')
        if self.restart_lock.locked():
            await self.discord_log('Shutdown already scheduled')
        else:
            await self.discord_log('Shutdown scheduled')
            await self.process_safe_shutdown(delay)

    async def process_safe_shutdown(self, delay):
        async with self.restart_lock:
            notifications_at_minutes = (60, 30, 20, 10, 5, 4, 3, 2, 1)
            notification_index = 0
            for notification in notifications_at_minutes:
                if delay / 60 < notification:
                    notification_index += 1
            log.info(
                f'shutdown scheduled with notifications at {notifications_at_minutes[notification_index:]} minutes')
            proceed_at_minute_intervals = False
            while delay > 0:
                if delay / 60 < notifications_at_minutes[notification_index]:
                    message = (f'Restarting the server in {notifications_at_minutes[notification_index]} '
                               f'minute{"s" if notifications_at_minutes[notification_index] != 1 else ""}')
                    notification_index += 1
                    await self.handle_command(Command(self.server_name, f'say -1 {message}'))
                    proceed_at_minute_intervals = True
                if proceed_at_minute_intervals:
                    await asyncio.sleep(60)
                    delay -= 60
                else:
                    await asyncio.sleep(1)
                    delay -= 1

            await self.discord_log('shutdown -> kicking')
            await self.kick_everybody('Server is restarting')

            await self.discord_log('shutdown -> locking')
            await self.discord_log('shutdown -> wait for a minute')
            # Lock RCon command doesn't seem to work, so instead we loop
            # kicking players. It could be more complex and only kick if people
            # join, but this seems like the simpler solution
            time_left = 60
            while time_left > 0:
                await self.kick_everybody(f'Server locked, restarting in {time_left} seconds')
                await asyncio.sleep(2)
                time_left -= 2

            await self.discord_log('shutdown -> shutting down')
            await self.handle_command(Command(self.server_name, '#shutdown'))

    async def kick_everybody(self, message):
        players_query = Command(self.server_name, 'players')
        await self.handle_command(players_query)
        try:
            raw_players = await asyncio.wait_for(players_query.result, 10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            log.warning('player query timed out')
            return
        if raw_players is None:
            log.warning('player query response empty')
            return
        player_lines = raw_players.split('\n')[3:-1]
        player_ids = [line.split()[0] for line in player_lines]
        for i in player_ids:
            command = f'kick {i} {message}'
            await self.handle_command(Command(self.server_name, command))
            log.info(command)

    async def discord_log(self, message):
        await discord_service.get_service_manager().send_message(
            discord_service.Log(self.server_name, message)
        )


services = dict()


def get_service_manager(server_name) -> RconService:
    if server_name not in services:
        services[server_name] = RconService(server_name)
    return services[server_name]
