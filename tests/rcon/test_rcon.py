import asyncio
import logging
import struct
from typing import Union, Text, Tuple

import pytest

from carim_discord_bot import config
from carim_discord_bot.rcon import service, protocol, registrar
from carim_discord_bot.rcon.protocol import FORMAT_PREFIX, PACKET_TYPE_FORMAT, SEQUENCE_NUMBER_FORMAT

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s - %(message)s')


class MockServerProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.login_success = True
        self.transport = None

    def connection_made(self, transport: asyncio.transports.BaseTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: Union[bytes, Text], addr: Tuple[str, int]) -> None:
        packet = protocol.Packet.parse(data)
        if isinstance(packet.payload, protocol.Login):
            packet.payload = \
                CustomPayload(protocol.LOGIN, struct.pack(FORMAT_PREFIX + SEQUENCE_NUMBER_FORMAT,
                                                          protocol.SUCCESS if self.login_success else 0x00))
            self.transport.sendto(packet.generate(), addr)
        elif isinstance(packet.payload, protocol.Command):
            packet.payload = protocol.Command(packet.payload.sequence_number, command='random command data')
            if self.login_success:
                self.transport.sendto(packet.generate(), addr)


class CustomPayload(protocol.Payload):
    def __init__(self, packet_type, data):
        self.packet_type = packet_type
        self.data = data

    def generate(self):
        return struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT, self.packet_type) + self.data

    def __str__(self):
        raise NotImplementedError


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_login_success_before_other_commands(event_loop: asyncio.BaseEventLoop):
    config.set(config.Config.build_from_dict({
        'token': '',
        'rcon_ip': '127.0.0.1',
        'rcon_port': 42302,
        'rcon_password': 'password',
        'steam_port': 42016,
        'rcon_keep_alive_interval': .2,
    }))
    future_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    chat_queue = asyncio.Queue()
    registrar.default_timeout = 1
    mock_protocol = MockServerProtocol()
    server_t, server_p = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: mock_protocol, local_addr=(config.get().ip, config.get().port))

    future = event_loop.create_future()
    await future_queue.put((future, 'players'))
    await service.start(future_queue, event_queue, chat_queue)
    result = await future
    assert result == 'random command data'

    future = event_loop.create_future()
    await future_queue.put((future, 'players'))
    result = await future
    assert result == 'random command data'

    event = await event_queue.get()
    assert event == 'keep alive'


def test_non_ascii_incoming_message():
    raw_packet = b'BEy\\N\xcf\xff\x02<(Global) Survivor: \xd0\xba\xd1\x82\xd0\xbe \xd0\xbd\xd0\xb0 \xd0\xba\xd1\x83\xd0\xbc\xd1\x8b\xd1\x80\xd0\xbd\xd0\xb5 \xd1\x81\xd0\xb5\xd0\xb9\xd1\x87\xd0\xb0\xd1\x81?'
    p = protocol.Packet.parse(raw_packet)
    assert isinstance(p.payload, protocol.Message)
    expected = '(Global) Survivor: кто на кумырне сейчас?'
    assert p.payload.message == expected


def test_non_ascii_outgoing_message():
    command = 'say -1 кто на кумырне сейчас?'
    p = protocol.Command(4, command=command)
    expected = b'\x01\x04say -1 \xd0\xba\xd1\x82\xd0\xbe \xd0\xbd\xd0\xb0 \xd0\xba\xd1\x83\xd0\xbc\xd1\x8b\xd1\x80\xd0\xbd\xd0\xb5 \xd1\x81\xd0\xb5\xd0\xb9\xd1\x87\xd0\xb0\xd1\x81?'
    assert expected == p.generate()
