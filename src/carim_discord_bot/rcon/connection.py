import asyncio
import logging
import re

from carim_discord_bot import config
from carim_discord_bot.rcon import protocol, registrar

log = logging.getLogger(__name__)


class ProtocolFactory:
    def __init__(self, future_queue, event_queue, chat_queue):
        self.future_queue = future_queue
        self.event_queue = event_queue
        self.chat_queue = chat_queue

    def get(self):
        return RConProtocol(self.future_queue, self.event_queue, self.chat_queue)


class RConProtocol(asyncio.DatagramProtocol):
    def __init__(self, future_queue, event_queue, chat_queue):
        self.transport = None
        self.future_queue = future_queue
        self.event_queue = event_queue
        self.chat_queue = chat_queue
        self.logged_in = False
        self.logged_in_event = asyncio.Event()
        super().__init__()

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        data = protocol.Packet(protocol.Login(password=config.get().password)).generate()
        log.info('sending login')
        self.send_rcon_datagram(data)

    def datagram_received(self, data, addr):
        log.debug(f'received {data}')
        packet = protocol.Packet.parse(data)
        if packet is not None:
            if isinstance(packet.payload, protocol.Login):
                log.info(f'login was {"" if packet.payload.success else "not "}successful')
                self.logged_in = packet.payload.success
                self.logged_in_event.set()
            else:
                response = process_packet(packet, self.event_queue, self.chat_queue)
                if response is not None:
                    log.debug(f'responding {response}')
                    self.send_rcon_datagram(response)

    def send_rcon_datagram(self, data):
        log.debug(f'sending {data}')
        self.transport.sendto(data)


def process_packet(packet, event_queue: asyncio.Queue, chat_queue: asyncio.Queue):
    if isinstance(packet.payload, protocol.Command):
        asyncio.create_task(registrar.incoming(packet.payload.sequence_number, packet))
    elif isinstance(packet.payload, protocol.Message):
        message = packet.payload.message
        log.debug(f'message: {message}')
        disconnect = re.compile(r'Player .* disconnected')
        if disconnect.match(message):
            parts = message.split()
            disconnect_message = ' '.join(parts[2:])
            log.info(f'login event {disconnect_message}')
            if config.get().log_connect_disconnect_notices:
                chat_queue.put_nowait(disconnect_message)
        connect = re.compile(r'Verified GUID .* of player .*')
        if connect.match(message):
            parts = message.split()
            name = ' '.join(parts[6:])
            login_message = f'{name} connected'
            log.info(f'login event {login_message}')
            if config.get().log_connect_disconnect_notices:
                chat_queue.put_nowait(login_message)
        chat = re.compile(r'^\((Global|Side)\).*:.*')
        if chat.match(message):
            _, _, content = message.partition(' ')
            chat_queue.put_nowait(content)
        if len(message) > 0:
            event_queue.put_nowait(message)
        return protocol.Packet(protocol.Message(packet.payload.sequence_number)).generate()
    return None
