import asyncio
import logging

from carim_discord_bot.rcon import protocol

log = logging.getLogger(__name__)
tasks = dict()
splits = dict()
_sequence_number = 0
lock = asyncio.Lock()
default_timeout = 10


async def get_next_sequence_number():
    global _sequence_number
    async with lock:
        seq_number = _sequence_number
        _sequence_number += 1
        _sequence_number &= 0xff
    return seq_number


async def reset():
    global _sequence_number
    async with lock:
        log.debug('reset')
        keys = list(tasks.keys())
        for key in keys:
            log.debug(f'cancelling {key}')
            future = tasks.pop(key, None)
            if future is not None:
                future.cancel()
        _sequence_number = 0


async def register(key, future: asyncio.Future, timeout=default_timeout):
    log.debug(f'register key {key}')
    tasks[key] = future
    asyncio.get_running_loop().create_task(wait_for_timeout(key, future, timeout))


async def incoming(key, packet):
    log.debug(f'incoming key {key} and type {type(packet.payload)}')

    if not packet.payload.is_split():
        future = tasks.pop(key)
        future.set_result(packet)
    else:
        split = splits.get(key, [''] * packet.payload.count)
        split[packet.payload.index] = packet.payload.data

        if all(split):
            data = ''.join(split)
            new_packet = protocol.Packet(protocol.Command(key, data=data))
            future = tasks.pop(key)
            future.set_result(new_packet)
            splits.pop(key)
        else:
            splits[key] = split


async def wait_for_timeout(key, future, timeout):
    log.debug(f'waiting for key {key}')
    try:
        await asyncio.wait_for(future, timeout)
    except asyncio.TimeoutError:
        log.debug(f'timeout waiting for key {key}')
        await reset()
