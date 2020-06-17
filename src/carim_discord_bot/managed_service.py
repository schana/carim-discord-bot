import asyncio
import logging

log = logging.getLogger(__name__)


class Message:
    def __init__(self, server_name):
        self.result = asyncio.get_event_loop().create_future()
        self.server_name = server_name


class Stop(Message):
    pass


class Restart(Message):
    pass


class ManagedService:
    def __init__(self):
        log.debug(f'{self._get_server_name_if_present()}initializing service {type(self).__name__}')
        self.message_queue = asyncio.Queue()
        self.tasks = []

    def _get_server_name_if_present(self):
        if hasattr(self, 'server_name'):
            return self.server_name + ' '
        return ''

    async def start(self):
        log.info(f'{self._get_server_name_if_present()}starting service {type(self).__name__}')
        self.tasks.append(asyncio.create_task(self._message_processor()))
        self.tasks.append(asyncio.create_task(self.service()))
        self.tasks.append(asyncio.create_task(self._status_checker()))

    async def stop(self):
        log.debug(f'{self._get_server_name_if_present()}stopping service {type(self).__name__}')
        for task in self.tasks:
            task.cancel()
        self.tasks = []

    async def restart(self):
        log.debug(f'{self._get_server_name_if_present()}restarting service {type(self).__name__}')
        await self.stop()
        await self.start()

    async def send_message(self, message: Message):
        log.debug(
            f'{self._get_server_name_if_present()}sending message to {type(self).__name__} of type {type(message).__name__}')
        await self.message_queue.put(message)

    async def _status_checker(self):
        await asyncio.sleep(1)
        while True:
            for task in self.tasks:
                task: asyncio.Task = task
                if task.done():
                    log.error(f'{self._get_server_name_if_present()}something crashed {type(self).__name__}',
                              exc_info=task.exception())
                    await self.send_message(Restart(None))
            await asyncio.sleep(1)

    async def _message_processor(self):
        while True:
            message = await self.message_queue.get()
            await self._handle_message(message)

    async def _handle_message(self, message: Message):
        log.debug(f'{message.server_name} received message in {type(self).__name__} of type {type(message).__name__}')
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
