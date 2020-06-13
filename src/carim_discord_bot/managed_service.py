import asyncio
import logging

log = logging.getLogger(__name__)


class Message:
    def __init__(self):
        self.result = asyncio.get_event_loop().create_future()


class Stop(Message):
    pass


class Restart(Message):
    pass


class ManagedService:
    def __init__(self):
        log.info(f'initializing service {type(self).__name__}')
        self.message_queue = asyncio.Queue()
        self.tasks = []

    async def start(self):
        log.info(f'starting service {type(self).__name__}')
        self.tasks.append(asyncio.create_task(self._message_processor()))
        self.tasks.append(asyncio.create_task(self.service()))

    async def stop(self):
        log.info(f'stopping service {type(self).__name__}')
        for task in self.tasks:
            task.cancel()
        self.tasks = []

    async def restart(self):
        log.info(f'restarting service {type(self).__name__}')
        await self.stop()
        await self.start()

    async def send_message(self, message: Message):
        await self.message_queue.put(message)

    async def _message_processor(self):
        while True:
            message = await self.message_queue.get()
            await self._handle_message(message)

    async def _handle_message(self, message: Message):
        log.info(f'received message in {type(self).__name__} of type {type(message).__name__}')
        if isinstance(message, Stop):
            await self.stop()
        elif isinstance(message, Restart):
            await self.restart()
        else:
            await self.handle_message(message)

    async def service(self):
        raise NotImplementedError

    async def handle_message(self, message: Message):
        raise NotImplementedError
