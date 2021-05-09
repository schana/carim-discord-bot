import argparse
import asyncio
import logging
import os
import pathlib
import sys

from pkg_resources import resource_filename

import carim_discord_bot
from carim_discord_bot import setup_instructions, config
from carim_discord_bot.cftools import omega_service, cf_cloud_service
from carim_discord_bot.discord_client import discord_service, member_count
from carim_discord_bot.rcon import rcon_service
from carim_discord_bot.services import player_count, scheduled_command
from carim_discord_bot.steam import steam_service

LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s - %(message)s'
log = logging.getLogger(__name__)


def main():
    parse_parameters()
    start_event_loop()
    asyncio.get_event_loop().run_until_complete(start_service_managers())
    asyncio.get_event_loop().create_task(debug_tasks())
    run_bot()


def parse_parameters():
    parser = argparse.ArgumentParser(description='carim discord bot')
    parser.add_argument('-c', dest='config', help='path to config file')
    parser.add_argument('-v', dest='verbosity', help='verbosity of the output', action='count', default=0)
    parser.add_argument('--setup', nargs='?', type=str, default=argparse.SUPPRESS,
                        help='print out instructions for setting up the bot')
    parser.add_argument('--version', action='store_true', help='prints the version and exits')
    args = parser.parse_args()

    if 'setup' in args:
        setup_instructions.print_setup_instructions(setup_part=args.setup)
        sys.exit()

    if args.version:
        print(carim_discord_bot.VERSION)
        sys.exit()

    setup_configuration(args.config)
    set_log_verbosity(args.verbosity)


def setup_configuration(config_argument):
    # We need to initialize logging so errors are reported when trying to load the configuration
    # After configuration is loaded, logging will be re-initialized with the appropriate level
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if config_argument is None:
        config_argument = resource_filename(__name__, 'data/config.json')
        if os.name == 'posix':
            p = pathlib.Path('/etc/carim/config.json')
            if p.is_file():
                config_argument = p
    config.initialize(config_argument)


def set_log_verbosity(verbosity):
    if config.get().debug:
        verbosity = max(verbosity, 1)

    if verbosity > 0:
        logging.getLogger(carim_discord_bot.__name__).setLevel(logging.DEBUG)


def start_event_loop():
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(loop_exception_handler)


def loop_exception_handler(loop, context):
    log.error(context)
    loop.default_exception_handler(context)
    loop.stop()


async def start_service_managers():
    await discord_service.get_service_manager().start()
    await member_count.get_service_manager().start()

    if config.get().cf_cloud_application_id is not None:
        await cf_cloud_service.get_service_manager().start()
    elif config.get().cftools_application_id is not None:
        await omega_service.get_service_manager().start()

    for server_name in config.get_server_names():
        asyncio.create_task(start_server(server_name))


async def start_server(server_name):
    await steam_service.get_service_manager(server_name).start()
    if config.get_server(server_name).rcon_password is not None:
        await rcon_service.get_service_manager(server_name).start()
        for i in range(len(config.get_server(server_name).scheduled_commands)):
            sm = scheduled_command.get_service_manager(server_name, i)
            await sm.start()
    if config.get_server(server_name).player_count_channel_id is not None:
        await player_count.get_service_manager(server_name).start()


async def debug_tasks():
    while False:
        print('\n'.join(str(task) for task in list(asyncio.all_tasks())))
        await asyncio.sleep(28)


def run_bot():
    asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    main()
