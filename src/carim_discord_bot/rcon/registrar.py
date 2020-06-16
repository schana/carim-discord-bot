import asyncio
import logging

from carim_discord_bot.rcon import protocol

log = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10


class Registrar:
    def __init__(self, server_name):
        self.server_name = server_name
        self.tasks = dict()
        self.splits = dict()
        self.sequence_number = 0
        self.lock = asyncio.Lock()

    async def get_next_sequence_number(self):
        async with self.lock:
            seq_number = self.sequence_number
            self.sequence_number += 1
            self.sequence_number &= 0xff
        return seq_number

    async def reset(self):
        async with self.lock:
            log.debug(f'{self.server_name} reset')
            keys = list(self.tasks.keys())
            for key in keys:
                log.debug(f'{self.server_name} cancelling {key}')
                future = self.tasks.pop(key, None)
                if future is not None:
                    future.cancel()
            self.sequence_number = 0

    async def register(self, key, future: asyncio.Future, timeout=DEFAULT_TIMEOUT):
        log.debug(f'{self.server_name} register key {key}')
        self.tasks[key] = future
        asyncio.get_running_loop().create_task(self.wait_for_timeout(key, future, timeout))

    async def incoming(self, key, packet):
        log.debug(f'{self.server_name} incoming key {key} and type {type(packet.payload)}')

        if not packet.payload.is_split():
            future = self.tasks.pop(key)
            future.set_result(packet)
        else:
            split = self.splits.get(key, [''] * packet.payload.count)
            split[packet.payload.index] = packet.payload.data

            if all(split):
                data = ''.join(split)
                new_packet = protocol.Packet(protocol.Command(key, data=data))
                future = self.tasks.pop(key)
                future.set_result(new_packet)
                self.splits.pop(key)
            else:
                self.splits[key] = split

    async def wait_for_timeout(self, key, future, timeout):
        log.debug(f'{self.server_name} waiting for key {key}')
        try:
            await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            log.debug(f'{self.server_name} timeout waiting for key {key}')
            await self.reset()
