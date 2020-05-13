import asyncio
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
            name, _, data = data[struct.calcsize(RESPONSE_HEADER_FORMAT):].partition(b'\x00')
            map_name, _, data = data.partition(b'\x00')
            folder, _, data = data.partition(b'\x00')
            game, _, data = data.partition(b'\x00')
            steam_id, players, max_players, bots, server_type, env, vis, vac = struct.unpack_from(RESPONSE_DATA_FORMAT,
                                                                                                  data)
            data = SteamData(name.decode(), map_name.decode(), folder.decode(), game.decode(), steam_id, players,
                             max_players, bots, server_type, env, vis, vac)
            self.future.set_result(data)
        except:
            self.future.cancel()
        finally:
            self.transport.close()


class SteamData:
    def __init__(self, name, map_name, folder, game, steam_id, players, max_players, bots, server_type, env, vis, vac):
        self.name = name
        self.map_name = map_name
        self.folder = folder
        self.game = game
        self.steam_id = steam_id
        self.players = players
        self.max_players = max_players
        self.bots = bots
        self.server_type = server_type
        self.env = env
        self.vis = vis
        self.vac = vac


async def query(ip, port, future):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(lambda: SteamProtocol(future), remote_addr=(ip, port))
    await asyncio.sleep(2)
    transport.close()
