import asyncio
import re
import struct

QUERY_HEADER_FORMAT = '=IB'
QUERY = struct.pack(QUERY_HEADER_FORMAT, 0xffffffff, 0x54) + b'Source Engine Query' + struct.pack('=B', 0x00)
RESPONSE_HEADER_FORMAT = '=IBB'
RESPONSE_DATA_FORMAT = '=HBBBBBBB'


class SteamProtocol(asyncio.DatagramProtocol):
    def __init__(self, future: asyncio.Future):
        self.future = future
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        transport.sendto(QUERY)

    def datagram_received(self, data, addr):
        try:
            self.future.set_result(unpack_steam_response(data))
        except:
            self.future.cancel()
        finally:
            self.transport.close()


def unpack_steam_response(data):
    response = SteamData()
    data = data[struct.calcsize(RESPONSE_HEADER_FORMAT):]
    response.name, data = get_next_string(data)
    response.map_name, data = get_next_string(data)
    response.folder, data = get_next_string(data)
    response.game, data = get_next_string(data)
    (
        response.steam_id,
        response.players,
        response.max_players,
        response.bots,
        response.server_type,
        response.env,
        response.vis,
        response.vac
    ), data = unpack_from_format(RESPONSE_DATA_FORMAT, data)
    response.version, data = get_next_string(data)
    (edf,), data = unpack_from_format('=B', data)
    if edf & 0x80:
        (response.port,), data = unpack_from_format('=H', data)
    if edf & 0x10:
        (response.extra_steam_id,), data = unpack_from_format('=Q', data)
    if edf & 0x40:
        (response.source_tv_port,), data = unpack_from_format('=H', data)
        response.source_tv_name, data = get_next_string(data)
    if edf & 0x20:
        temp_keywords, data = get_next_string(data)
        response.keywords = temp_keywords.split(',')
    if edf & 0x01:
        (response.game_id,), data = unpack_from_format('=Q', data)
    return response


def get_next_string(data):
    result, _, data = data.partition(b'\x00')
    result = result.decode()
    return result, data


def unpack_from_format(data_format, data):
    result = struct.unpack_from(data_format, data)
    data = data[struct.calcsize(data_format):]
    return result, data


class SteamData:
    def __init__(self):
        self.name = None
        self.map_name = None
        self.folder = None
        self.game = None
        self.steam_id = None
        self.players = None
        self.max_players = None
        self.bots = None
        self.server_type = None
        self.env = None
        self.vis = None
        self.vac = None
        self.version = None
        self.port = None
        self.extra_steam_id = None
        self.keywords = list()
        self.game_id = None

    def get_queue(self):
        for kw in self.keywords:
            if kw.startswith('lqs'):
                return kw[3:]
        return None

    def get_time(self):
        time_pattern = re.compile(r'[0-9]{2}:[0-9]{2}')
        for kw in self.keywords:
            if time_pattern.match(kw):
                return kw
        return None


async def query(ip, port, future):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(lambda: SteamProtocol(future), remote_addr=(ip, port))
    await asyncio.sleep(2)
    transport.close()
