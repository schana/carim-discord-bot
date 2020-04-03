import asyncio
import logging
import re

from carim_discord_bot.rcon import protocol

sequence_number = 0
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def process_packet(packet, event_queue: asyncio.Queue):
    if isinstance(packet.payload, protocol.Login):
        log.info(f'login was {"" if packet.payload.success else "not "}successful')
    elif isinstance(packet.payload, protocol.Command):
        pass
    elif isinstance(packet.payload, protocol.Message):
        message = packet.payload.message
        log.debug(f'message: {message}')
        connect = re.compile(r'Player .*connected')
        if connect.match(message):
            parts = message.split()
            status = parts[-1]
            if status == 'disconnected':
                name = ' '.join(parts[2:-1])
            else:
                name = ' '.join(parts[2:-2])
            login_message = f'{name} {status}'
            log.info(login_message)
            asyncio.get_event_loop().create_task(put_in_queue(event_queue, login_message))
        return generate_ack(packet.payload.sequence_number)
    return None


async def put_in_queue(queue, item):
    await queue.put(item)


def generate_login(password):
    return protocol.Packet(protocol.Login(password=password)).generate()


def generate_ack(received_sequence_number):
    return protocol.Packet(protocol.Message(received_sequence_number)).generate()


def generate_keep_alive():
    return protocol.Packet(protocol.Command(sequence_number)).generate()


def generate_players_query():
    return protocol.Packet(protocol.Command(sequence_number, command='players')).generate()


class RConProtocol(asyncio.DatagramProtocol):
    def __init__(self, future_queue, event_queue, password):
        self.transport = None
        self.password = password
        self.future_queue = future_queue
        self.event_queue = event_queue
        super().__init__()

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        data = generate_login(self.password)
        log.debug(f'sending {data}')
        self.transport.sendto(data)

    def datagram_received(self, data, addr):
        log.debug(f'received {data}')
        packet = protocol.Packet.parse(data)
        if packet is not None:
            response = process_packet(packet, self.event_queue)
            if response is not None:
                log.debug(f'responding {response}')
                self.transport.sendto(response)

    def send_keep_alive(self):
        log.info('sending keep alive')
        data = generate_keep_alive()
        self.transport.sendto(data)

    def send_players_query(self):
        log.info('sending players query')
        data = generate_players_query()
        self.transport.sendto(data)


async def keep_alive(rcon_protocol: RConProtocol, event_queue):
    while True:
        await asyncio.sleep(30)
        rcon_protocol.send_keep_alive()
        # await event_queue.put('keep alive')


async def start(future_queue, event_queue, ip, port, password):
    loop = asyncio.get_running_loop()
    transport, rcon_protocol = await loop.create_datagram_endpoint(
        lambda: RConProtocol(future_queue, event_queue, password), remote_addr=(ip, port))
    loop.create_task(keep_alive(rcon_protocol, event_queue))
    try:
        while True:
            future, command = await future_queue.get()
            log.info(command)
            if command == 'players':
                rcon_protocol.send_players_query()
                future.set_result(42)
    finally:
        transport.close()
