import asyncio
import logging

things = dict()
log = logging.getLogger(__name__)


def get_next_sequence_number():
    if len(things) > 0:
        number = max(*things.keys()) + 1
    else:
        number = 0
    return number


def register(key, future: asyncio.Future, timeout=10):
    log.debug(f'register {key}')
    things[key] = future
    log.debug(f'keys {sorted(things.keys())}')
    loop = asyncio.get_event_loop()
    loop.create_task(wait_for_timeout(key, future, timeout))


def incoming(key, packet):
    log.debug(f'incoming {key} {packet}')
    future = things.pop(key, None)
    if future is not None:
        future.set_result(packet)
    log.debug(f'keys {sorted(things.keys())}')


async def wait_for_timeout(key, future, timeout):
    log.debug(f'waiting for {key}')
    await asyncio.sleep(timeout)
    log.debug(f'done waiting for {key}')
    if not future.done():
        log.debug(f'timeout {key}')
        things.pop(key, None)
        future.cancel()
