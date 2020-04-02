import asyncio
import logging
import re
import struct
import zlib

# https://www.battleye.com/downloads/BERConProtocol.txt
FORMAT_PREFIX = '='
HEADER_FORMAT = 'BBIB'
PACKET_TYPE_FORMAT = 'B'
SEQUENCE_NUMBER_FORMAT = 'B'
HEADER_SIZE = struct.calcsize(FORMAT_PREFIX + HEADER_FORMAT)

sequence_number = 0
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Packet:
    LOGIN = 0x00
    COMMAND = 0x01
    MESSAGE = 0x02


def get_packet_type_name(packet_type):
    if packet_type == Packet.LOGIN:
        return 'login'
    if packet_type == Packet.COMMAND:
        return 'command'
    if packet_type == Packet.MESSAGE:
        return 'message'
    return 'invalid'


def generate_packet(payload):
    data = struct.pack(FORMAT_PREFIX + HEADER_FORMAT, 0x42, 0x45, compute_checksum(payload), 0xff) + payload
    return data


def process_packet(data):
    if len(data) > HEADER_SIZE:
        b, e, checksum, f = struct.unpack_from(FORMAT_PREFIX + HEADER_FORMAT, data)
        payload = data[HEADER_SIZE:]
        if b == 0x42 and e == 0x45 and f == 0xff and checksum == compute_checksum(payload):
            return payload
    log.warning(f'invalid {data}')
    return None


def process_payload(payload, event_queue: asyncio.Queue):
    packet_type = struct.unpack_from(FORMAT_PREFIX + PACKET_TYPE_FORMAT, payload)[0]
    log.debug(f'processing {get_packet_type_name(packet_type)}')
    if packet_type == Packet.LOGIN:
        pass
    elif packet_type == Packet.COMMAND:
        pass
    elif packet_type == Packet.MESSAGE:
        struct_format = FORMAT_PREFIX + PACKET_TYPE_FORMAT + SEQUENCE_NUMBER_FORMAT
        _, received_sequence_number = struct.unpack_from(struct_format, payload)
        message = payload[struct.calcsize(struct_format):]
        message = str(message, encoding='utf-8')
        log.debug(f'message: {message}')
        connect = re.compile(r'Player .*connected')
        if connect.match(message):
            parts = message.split()
            log.info(parts)
            status = parts[-1]
            if status == 'disconnected':
                name = ' '.join(parts[2:-1])
            else:
                name = ' '.join(parts[2:-2])
            asyncio.get_event_loop().create_task(put_in_queue(event_queue, f'{name} {status}'))
        return generate_ack(received_sequence_number)
    return None


async def put_in_queue(queue, item):
    await queue.put(item)


def compute_checksum(payload):
    checksum = zlib.crc32(bytes([0xff]) + payload)
    return checksum


def generate_login(password):
    return generate_packet(
        struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT, Packet.LOGIN) + bytes(password, encoding='ascii'))


def generate_ack(received_sequence_number):
    payload = struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT + SEQUENCE_NUMBER_FORMAT, Packet.MESSAGE,
                          received_sequence_number)
    return generate_packet(payload)


def generate_keep_alive():
    payload = struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT + SEQUENCE_NUMBER_FORMAT, Packet.COMMAND, sequence_number)
    return generate_packet(payload)


def generate_players_query():
    payload = struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT + SEQUENCE_NUMBER_FORMAT, Packet.COMMAND,
                          sequence_number) + bytes('players', encoding='ascii')
    return generate_packet(payload)


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
        payload = process_packet(data)
        if payload is not None:
            log.debug(f'payload {payload}')
            response = process_payload(payload, self.event_queue)
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


async def keep_alive(protocol: RConProtocol, event_queue):
    while True:
        await asyncio.sleep(30)
        protocol.send_keep_alive()
        # await event_queue.put('keep alive')


async def start(future_queue, event_queue, ip, port, password):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: RConProtocol(future_queue, event_queue, password), remote_addr=(ip, port))
    loop.create_task(keep_alive(protocol, event_queue))
    try:
        while True:
            future, command = await future_queue.get()
            log.info(command)
            if command == 'players':
                protocol.send_players_query()
                future.set_result(42)
    finally:
        transport.close()
