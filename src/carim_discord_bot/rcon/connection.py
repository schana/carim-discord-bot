import asyncio
import logging
import re
from typing import Optional

from carim_discord_bot import config
from carim_discord_bot.discord_client import discord_service
from carim_discord_bot.rcon import protocol

log = logging.getLogger(__name__)


class ProtocolFactory:
    def __init__(self, server_name, rcon_registrar):
        self.server_name = server_name
        self.rcon_registrar = rcon_registrar

    def get(self):
        return RConProtocol(self.server_name, self.rcon_registrar)


class RConProtocol(asyncio.DatagramProtocol):
    def __init__(self, server_name, rcon_registrar):
        self.transport = None
        self.server_name = server_name
        self.rcon_registrar = rcon_registrar
        self.logged_in = False
        self.logged_in_event = asyncio.Event()
        super().__init__()

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        data = protocol.Packet(protocol.Login(password=config.get_server(self.server_name).rcon_password)).generate()
        log.info(f'{self.server_name} sending login')
        self.send_rcon_datagram(data)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.logged_in = False
        self.transport.close()
        log.warning(f'{self.server_name} connection lost {exc}')

    def error_received(self, exc: Exception) -> None:
        self.logged_in = False
        self.transport.close()
        log.warning(f'{self.server_name} error received {exc}')

    def datagram_received(self, data, addr):
        log.debug(f'{self.server_name} received {data}')
        packet = protocol.Packet.parse(data)
        if packet is not None:
            if isinstance(packet.payload, protocol.Login):
                log.info(f'{self.server_name} login was {"" if packet.payload.success else "not "}successful')
                self.logged_in = packet.payload.success
                self.logged_in_event.set()
            else:
                response = self.process_packet(packet)
                if response is not None:
                    log.debug(f'{self.server_name} responding {response}')
                    self.send_rcon_datagram(response)

    def send_rcon_datagram(self, data):
        log.debug(f'{self.server_name} sending {data}')
        self.transport.sendto(data)

    def process_packet(self, packet):
        if isinstance(packet.payload, protocol.Command) or isinstance(packet.payload, protocol.SplitCommand):
            asyncio.create_task(self.rcon_registrar.incoming(packet.payload.sequence_number, packet))
        elif isinstance(packet.payload, protocol.Message):
            message = packet.payload.message
            log.debug(f'{self.server_name} message: {message}')
            disconnect = re.compile(r'Player .* disconnected')
            if disconnect.match(message):
                parts = message.split()
                disconnect_message = ' '.join(parts[2:])
                log.info(f'{self.server_name} login event {disconnect_message}')
                if config.get_server(self.server_name).chat_show_connect_disconnect_notices:
                    asyncio.create_task(discord_service.get_service_manager().send_message(
                        discord_service.Chat(self.server_name, disconnect_message)
                    ))
            connect = re.compile(r'Verified GUID .* of player .*')
            if connect.match(message):
                parts = message.split()
                name = ' '.join(parts[6:])
                login_message = f'{name} connected'
                log.info(f'{self.server_name} login event {login_message}')
                if config.get_server(self.server_name).chat_show_connect_disconnect_notices:
                    asyncio.create_task(discord_service.get_service_manager().send_message(
                        discord_service.Chat(self.server_name, login_message)
                    ))
            chat = re.compile(r'^\((Global|Side)\).*:.*')
            if chat.match(message):
                _, _, content = message.partition(' ')
                asyncio.create_task(discord_service.get_service_manager().send_message(
                    discord_service.Chat(self.server_name, content)
                ))
            if len(message) > 0:
                asyncio.create_task(discord_service.get_service_manager().send_message(
                    discord_service.Log(self.server_name, message)
                ))
            return protocol.Packet(protocol.Message(packet.payload.sequence_number)).generate()
        return None
