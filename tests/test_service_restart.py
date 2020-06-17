import asyncio
import logging

import pytest

from carim_discord_bot.rcon import connection, registrar

protocol_counter = 0


class MockProtocol:
    def __init__(self, future_queue, event_queue, chat_queue):
        self.future_queue = future_queue
        self.event_queue = event_queue
        self.chat_queue = chat_queue
        self.logged_in = True
        self.logged_in_event = asyncio.Event()
        self.logged_in_event.set()

    def send_rcon_datagram(self, data):
        print(f'sending {data}')


class MockTransport:
    def close(self):
        pass


@pytest.mark.skip
@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_process_futures_dies(event_loop: asyncio.BaseEventLoop, monkeypatch):
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s - %(message)s')

    async def mock_create_endpoint(factory):
        return MockTransport(), MockProtocol(factory.future_queue, factory.event_queue, factory.chat_queue)

    async def mock_register(key, future, timeout=10):
        registrar.tasks[key] = future

    keep_alive_event = asyncio.Event()

    async def mock_keep_aliver(protocol, e_queue):
        await keep_alive_event.wait()

    monkeypatch.setattr(service, 'create_datagram_endpoint', mock_create_endpoint)
    monkeypatch.setattr(service, 'keep_alive_manager', mock_keep_aliver)
    monkeypatch.setattr(registrar, 'register', mock_register)

    future_queue = asyncio.Queue()
    event_queue = asyncio.Queue()
    chat_queue = asyncio.Queue()

    future1 = event_loop.create_future()
    await future_queue.put((future1, 'commands'))

    factory = connection.ProtocolFactory(future_queue, event_queue, chat_queue)
    task = event_loop.create_task(service.run_service(factory))

    await future1
    assert future1.result() == service.VALID_COMMANDS

    assert not task.done()
    keep_alive_event.set()
    await task
    assert task.done()
    keep_alive_event.clear()

    future2 = event_loop.create_future()
    await future_queue.put((future2, 'commands'))
    task = event_loop.create_task(service.run_service(factory))

    await future2
    assert future2.result() == service.VALID_COMMANDS
