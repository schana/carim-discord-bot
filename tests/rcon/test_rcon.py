import asyncio
import logging
import struct
from typing import Union, Text, Tuple

import pytest

from carim_discord_bot.rcon import service, protocol
from carim_discord_bot import config
from carim_discord_bot.rcon.protocol import FORMAT_PREFIX, PACKET_TYPE_FORMAT, SEQUENCE_NUMBER_FORMAT

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s - %(message)s')


class MockServerProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None

    def connection_made(self, transport: asyncio.transports.BaseTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: Union[bytes, Text], addr: Tuple[str, int]) -> None:
        packet = protocol.Packet.parse(data)
        if isinstance(packet.payload, protocol.Login):
            packet.payload =\
                CustomPayload(protocol.LOGIN, struct.pack(FORMAT_PREFIX + SEQUENCE_NUMBER_FORMAT, protocol.SUCCESS))
        elif isinstance(packet.payload, protocol.Command):
            packet.payload = protocol.Command(packet.payload.sequence_number, command='random command data')
        self.transport.sendto(packet.generate(), addr)


class CustomPayload(protocol.Payload):
    def __init__(self, packet_type, data):
        self.packet_type = packet_type
        self.data = data

    def generate(self):
        return struct.pack(FORMAT_PREFIX + PACKET_TYPE_FORMAT, self.packet_type) + self.data

    def __str__(self):
        raise NotImplementedError


def loop_exception_handler(loop, context):
    return
    loop.default_exception_handler(context)


@pytest.mark.asyncio
async def test_login_success_before_other_commands(event_loop: asyncio.BaseEventLoop):
    event_loop.set_exception_handler(loop_exception_handler)
    config.set(config.Config.build_from_dict({
        'token': '',
        'rcon_ip': '127.0.0.1',
        'rcon_port': 2302,
        'rcon_password': 'password',
        'rcon_keep_alive_interval': .2,
    }))
    future_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    chat_queue = asyncio.Queue()
    server_t, server_p = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: MockServerProtocol(), local_addr=(config.get().ip, config.get().port))

    future = event_loop.create_future()
    await future_queue.put((future, 'players'))
    await service.start(future_queue, event_queue, chat_queue)

    with pytest.raises(asyncio.CancelledError):
        result = await future

    async with service.process_command:
        pass

    future = event_loop.create_future()
    await future_queue.put((future, 'players'))
    result = await future
    assert result == 'random command data'

    event = await event_queue.get()
    assert event == 'keep alive'
