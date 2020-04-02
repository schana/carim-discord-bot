import struct
import asyncio
import zlib
import logging

# https://www.battleye.com/downloads/BERConProtocol.txt
FORMAT_PREFIX = '='
HEADER_FORMAT = 'BBIB'
PACKET_TYPE_FORMAT = 'B'
SEQUENCE_NUMBER_FORMAT = 'B'
HEADER_SIZE = struct.calcsize(FORMAT_PREFIX + HEADER_FORMAT)

sequence_number = 0
log = logging.getLogger(__name__)


class Packet:
    LOGIN = 0x00
    COMMAND = 0x01
    MESSAGE = 0x02


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


def process_payload(payload):
    packet_type = struct.unpack_from(FORMAT_PREFIX + PACKET_TYPE_FORMAT, payload)[0]
    log.info(f'processing {packet_type}')
    if packet_type == Packet.LOGIN:
        pass
    elif packet_type == Packet.COMMAND:
        pass
    elif packet_type == Packet.MESSAGE:
        _, received_sequence_number = struct.unpack_from(FORMAT_PREFIX + PACKET_TYPE_FORMAT + SEQUENCE_NUMBER_FORMAT, payload)
        return generate_ack(received_sequence_number)
    return None


def compute_checksum(payload):
    checksum = zlib.crc32(bytes([0xff]) + payload)
    return checksum


def generate_login(password):
    return generate_packet(struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT, Packet.LOGIN) + bytes(password, encoding='ascii'))


def generate_ack(received_sequence_number):
    payload = struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT + SEQUENCE_NUMBER_FORMAT, 0x02, received_sequence_number)
    return generate_packet(payload)


class RConProtocol(asyncio.DatagramProtocol):
    def __init__(self, future_queue, password):
        self.transport = None
        self.password = password
        self.future_queue = future_queue
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
            response = process_payload(payload)
            if response is not None:
                log.debug(f'responding {response}')
                self.transport.sendto(response)


async def start(future_queue, ip, port, password):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: RConProtocol(future_queue, password), remote_addr=(ip, port))
    try:
        while True:
            future, command = await future_queue.get()
            log.info(command)
            future.set_result(42)
    finally:
        transport.close()
