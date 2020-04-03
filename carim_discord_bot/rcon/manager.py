import asyncio
import logging

log = logging.getLogger(__name__)
tasks = asyncio.Queue(1)


def get_next_sequence_number():
    return 0


async def register(key, future: asyncio.Future, timeout=10):
    log.debug(f'register key {key}')
    await tasks.put(future)
    loop = asyncio.get_event_loop()
    loop.create_task(wait_for_timeout(key, future, timeout))


async def incoming(key, packet):
    log.debug(f'incoming {packet}, key {key}')
    if tasks.full():
        future = await tasks.get()
        future.set_result(packet)


async def wait_for_timeout(key, future, timeout):
    log.debug(f'waiting for key {key}')
    try:
        await asyncio.wait_for(future, timeout)
    except asyncio.TimeoutError:
        log.debug(f'timeout waiting for key {key}')
        if tasks.full():
            await tasks.get()
