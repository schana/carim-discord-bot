import argparse
import asyncio
import datetime
import json
import sys

import carim_discord_bot
from carim_discord_bot import message_builder, config
from carim_discord_bot.rcon import rcon_service
from carim_discord_bot.services import scheduled_command


class BotArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError()


message_parser = BotArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things',
                                   formatter_class=argparse.RawTextHelpFormatter)
command_group = message_parser.add_argument_group('commands')
command_group.add_argument('--help', action='store_true', help='displays this usage information')
command_group.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
command_group.add_argument('--about', action='store_true', help='display some information about the bot')
command_group.add_argument('--version', action='store_true', help='display the current version of the bot')

admin_group = message_parser.add_argument_group('admin commands')
admin_group.add_argument('--command', nargs='?', type=str, default=argparse.SUPPRESS, metavar='command',
                         help='send command to the server, or list the available commands')
admin_group.add_argument('--safe_shutdown', nargs='?', type=int, default=argparse.SUPPRESS, metavar='seconds',
                         help='shutdown the server in a safe manner with an optional delay')
admin_group.add_argument('--schedule_status', action='store_true', help='show current scheduled item status')
admin_group.add_argument('--schedule_skip', type=int, default=argparse.SUPPRESS, metavar='index',
                         help='skip next run of scheduled command')
admin_group.add_argument('--kill', action='store_true', help='make the bot terminate')


def format_help():
    formatter = message_parser._get_formatter()

    formatter.add_text(message_parser.description)

    action_groups = [command_group, admin_group]

    for action_group in action_groups:
        formatter.start_section(action_group.title)
        formatter.add_text(action_group.description)
        formatter.add_arguments(action_group._group_actions)
        formatter.end_section()

    formatter.add_text(message_parser.epilog)

    return formatter.format_help()


async def process_chat(server_name, message):
    chat_message = f'Discord> {message.author.display_name}: {message.content}'
    if len(chat_message) > 128:
        await message.channel.send(f'Message too long: {chat_message}')
        return
    rcon_message = rcon_service.Command(server_name, f'say -1 {chat_message}')
    await rcon_service.get_service_manager(server_name).send_message(rcon_message)
    try:
        await rcon_message.result
    except asyncio.CancelledError:
        await message.channel.send(f'Failed to send: {chat_message}')


async def process_message_args(server_name, parsed_args, message):
    if parsed_args.help:
        embed = message_builder.build_embed('Help', format_help())
        await message.channel.send(embed=embed)
    if parsed_args.secret:
        await message.channel.send(f'Thank you, cnofafva, for giving me life!')
    if parsed_args.about:
        await message.channel.send(embed=message_builder.build_embed(
            'This bot is open source and can be built for any DayZ server\n'
            'For more information, visit https://github.com/schana/carim-discord-bot'))
    await process_admin_args(server_name, parsed_args, message)


async def process_admin_args(server_name, parsed_args, message):
    if 'command' in parsed_args:
        if parsed_args.command is None:
            command = 'commands'
        else:
            command = parsed_args.command
        service_message = rcon_service.Command(server_name, command)
        await rcon_service.get_service_manager(server_name).send_message(service_message)
        try:
            result = await service_message.result
            await message.channel.send(
                embed=message_builder.build_embed(command, f'{str(result) if result else "success"}'))
        except asyncio.CancelledError:
            await message.channel.send(embed=message_builder.build_embed(command, f'query timed out'))
    if 'safe_shutdown' in parsed_args:
        if restart_lock.locked():
            await message.channel.send(embed=message_builder.build_embed('Shutdown already scheduled'))
        else:
            if parsed_args.safe_shutdown is not None:
                await message.channel.send(embed=message_builder.build_embed('Shutdown scheduled'))
                await process_safe_shutdown(parsed_args.safe_shutdown)
            else:
                await message.channel.send(embed=message_builder.build_embed('Shutting down now'))
                await process_safe_shutdown()
    if parsed_args.schedule_status:
        commands_info = list()
        commands_config = config.get_server(server_name).scheduled_commands
        for i, command_config in enumerate(commands_config):
            sc = scheduled_command.get_service_manager(server_name, i)
            next_run = sc.command['next']
            if not isinstance(next_run, str):
                next_run = datetime.timedelta(seconds=next_run)
                next_run -= datetime.timedelta(microseconds=next_run.microseconds)
                next_run = str(next_run)
            c_info = dict(index=i,
                          command=sc.command['command'],
                          interval=sc.command['interval'],
                          next_run=next_run)
            if sc.command.get('skip', False):
                c_info['skip_next'] = True
            commands_info.append(c_info)
        await message.channel.send(embed=message_builder.build_embed(
            'Scheduled Commands',
            f'```{json.dumps(commands_info, indent=1)}```'))
    if 'schedule_skip' in parsed_args:
        i = parsed_args.schedule_skip
        if not 0 <= i < len(scheduled_commands):
            await message.channel.send(embed=message_builder.build_embed('Invalid index'))
        else:
            scheduled_commands[i]['skip'] = True
    if parsed_args.kill:
        sys.exit(0)
    if parsed_args.version:
        await message.channel.send(embed=message_builder.build_embed(carim_discord_bot.VERSION))