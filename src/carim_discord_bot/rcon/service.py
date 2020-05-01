import asyncio
import logging

from carim_discord_bot import config
from carim_discord_bot.rcon import protocol, registrar, connection

log = logging.getLogger(__name__)
VALID_COMMANDS = ('players', 'admins', 'kick', 'bans', 'ban', 'removeBan', 'say', 'addBan', '#shutdown')


async def start(future_queue, event_queue, chat_queue):
    factory = connection.ProtocolFactory(future_queue, event_queue, chat_queue)
    asyncio.create_task(service_manager(factory))


async def service_manager(factory):
    while True:
        log.debug('starting rcon service')
        await run_service(factory)


async def run_service(factory):
    await registrar.reset()
    transport, rcon_protocol = await create_datagram_endpoint(factory)
    try:
        await asyncio.wait_for(rcon_protocol.logged_in_event.wait(), timeout=5)
    except asyncio.TimeoutError:
        log.info('login timed out')
        transport.close()
        return
    log.debug('starting futures processor')
    process_futures_task = asyncio.create_task(process_futures(factory.future_queue, rcon_protocol))
    rcon_protocol: connection.RConProtocol = rcon_protocol
    log.debug('starting keep alive manager')
    keep_alive_task = asyncio.create_task(keep_alive_manager(rcon_protocol, factory.event_queue))
    while True:
        if process_futures_task.done():
            process_futures_task = asyncio.create_task(process_futures(factory.future_queue, rcon_protocol))
        if keep_alive_task.done():
            break
        await asyncio.sleep(.2)
    log.warning('keep alive manager died')
    rcon_protocol.logged_in = False
    rcon_protocol.logged_in_event.clear()
    process_futures_task.cancel()
    transport.close()


async def create_datagram_endpoint(factory):
    transport, rcon_protocol = await asyncio.get_running_loop().create_datagram_endpoint(
        factory.get, remote_addr=(config.get().ip, config.get().port))
    return transport, rcon_protocol


async def process_futures(future_queue, rcon_protocol):
    while True:
        future, command = await future_queue.get()
        log.info(f'command received: {command}')
        if command == 'commands':
            future.set_result(VALID_COMMANDS)
        elif not rcon_protocol.logged_in:
            log.warning(f'not logged in, cancelling command: {command}')
            future.cancel()
            break
        elif command.split()[0] in VALID_COMMANDS:
            seq_number = await registrar.get_next_sequence_number()
            packet = protocol.Packet(protocol.Command(seq_number, command=command))
            command_future = asyncio.get_running_loop().create_future()
            await registrar.register(packet.payload.sequence_number, command_future)
            rcon_protocol.send_rcon_datagram(packet.generate())
            try:
                await command_future
                future.set_result(command_future.result().payload.data)
            except asyncio.CancelledError:
                log.warning(f'command cancelled: {command}')
                future.cancel()
        else:
            future.set_result('invalid command')


async def keep_alive_manager(rcon_protocol, event_queue):
    while True:
        await asyncio.sleep(config.get().rcon_keep_alive_interval)
        try:
            log.debug('sending keep alive')
            await keep_alive(rcon_protocol, event_queue)
        except asyncio.CancelledError:
            log.warning('keep alive timed out')
            await event_queue.put('keep alive timed out')
            break


async def keep_alive(rcon_protocol, event_queue):
    seq_number = await registrar.get_next_sequence_number()
    packet = protocol.Packet(protocol.Command(seq_number))
    future = asyncio.get_running_loop().create_future()
    await registrar.register(packet.payload.sequence_number, future)
    rcon_protocol.send_rcon_datagram(packet.generate())
    await future
    if config.get().log_rcon_keep_alive:
        await event_queue.put('keep alive')
