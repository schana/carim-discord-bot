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


class RconService(managed_service.ManagedService):
    def __init__(self, server_name):
        super().__init__()
        self.server_name = server_name
        self.rcon_registrar = registrar.Registrar(self.server_name)
        self.transport = None
        self.rcon_protocol = None

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
                await discord_service.get_service_manager().send_message(
                    discord_service.Log(self.server_name, 'keep alive timed out')
                )
                return

    async def keep_alive(self):
        seq_number = await self.rcon_registrar.get_next_sequence_number()
        packet = protocol.Packet(protocol.Command(seq_number))
        future = asyncio.get_running_loop().create_future()
        await self.rcon_registrar.register(packet.payload.sequence_number, future)
        self.rcon_protocol.send_rcon_datagram(packet.generate())
        await future
        if config.get_server(self.server_name).log_rcon_keep_alive:
            await discord_service.get_service_manager().send_message(
                discord_service.Log(self.server_name, 'keep alive')
            )

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Command):
            await self.handle_command(message)

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


services = dict()


def get_service_manager(server_name) -> RconService:
    if server_name not in services:
        services[server_name] = RconService(server_name)
    return services[server_name]
