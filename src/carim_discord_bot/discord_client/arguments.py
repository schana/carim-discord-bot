import argparse
import asyncio
import datetime
import json
import logging
import sys
from typing import Sequence, Text

import carim_discord_bot
from carim_discord_bot import config
from carim_discord_bot.cftools import omega_service, cf_cloud_service
from carim_discord_bot.discord_client import discord_service
from carim_discord_bot.rcon import rcon_service
from carim_discord_bot.services import scheduled_command

log = logging.getLogger(__name__)


class BotArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError()


class OptionalIndexAction(argparse.Action):
    def __init__(self, option_strings: Sequence[Text], dest: Text, **kwargs):
        super().__init__(option_strings, dest, nargs='+', **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 2:
            raise argparse.ArgumentError(self, 'too many arguments')
        if len(values) == 1:
            values += [0]
        values[1] = int(values[1])
        setattr(namespace, self.dest, values)


message_parser = BotArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things',
                                   formatter_class=argparse.RawTextHelpFormatter)
command_group = message_parser.add_argument_group('commands')
command_group.add_argument('--help', action='store_true', help='displays this usage information')
command_group.add_argument('--secret', action='store_true', help=argparse.SUPPRESS)
command_group.add_argument('--about', action='store_true', help='display some information about the bot')
command_group.add_argument('--version', action='store_true', help='display the current version of the bot')

admin_group = message_parser.add_argument_group('admin commands')
admin_group.add_argument('--list_priority', action='store_true', help='list queue priority entries')
admin_group.add_argument('--create_priority', nargs=3, type=str, default=argparse.SUPPRESS,
                         metavar=('cftools_id', 'comment', 'days'),
                         help='create a queue priority entry for {days} length, -1 is permanent')
admin_group.add_argument('--revoke_priority', type=str, default=argparse.SUPPRESS, metavar='cftools_id',
                         help='revoke a queue priority entry')
admin_group.add_argument('--command', nargs='?', type=str, default=argparse.SUPPRESS, metavar='command',
                         help='send command to the server, or list the available commands')
admin_group.add_argument('--shutdown', nargs='?', type=int, default=argparse.SUPPRESS, metavar='seconds',
                         help='shutdown the server in a safe manner with an optional delay')
admin_group.add_argument('--status', action='store_true', help='show current scheduled item status')
admin_group.add_argument('--skip', type=int, default=argparse.SUPPRESS, metavar='index',
                         help='skip next run of scheduled command')
admin_group.add_argument('--kill', action='store_true', help='make the bot terminate')

user_message_parser = BotArgumentParser(prog='', add_help=False, description='A helpful bot that can do a few things',
                                        formatter_class=argparse.RawTextHelpFormatter)
user_group = user_message_parser.add_argument_group('user commands')
user_group.add_argument('--leaderboard', action=OptionalIndexAction, metavar=('stat', 'index'),
                        default=argparse.SUPPRESS, help='show leaderboard')
user_group.add_argument('--stats', action=OptionalIndexAction, type=int, metavar=('steam64', 'index'),
                        default=argparse.SUPPRESS, help='query stats')


def format_help(parser=message_parser):
    formatter = parser._get_formatter()

    formatter.add_text(parser.description)

    action_groups = [command_group, admin_group]

    for action_group in action_groups:
        formatter.start_section(action_group.title)
        formatter.add_text(action_group.description)
        formatter.add_arguments(action_group._group_actions)
        formatter.end_section()

    formatter.add_text(parser.epilog)

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
        asyncio.create_task(discord_service.get_service_manager().send_message(
            discord_service.Response(server_name, format_help())
        ))
    if parsed_args.secret:
        asyncio.create_task(discord_service.get_service_manager().send_message(
            discord_service.Response(server_name, 'Thank you, cnofafva, for giving me life!')
        ))
    if parsed_args.about:
        asyncio.create_task(discord_service.get_service_manager().send_message(
            discord_service.Response(server_name, (
                'This bot is open source and can be built for any DayZ server\n'
                'For more information, visit https://github.com/schana/carim-discord-bot'
            ))
        ))
    await process_admin_args(server_name, parsed_args, message)


async def process_admin_args(server_name, parsed_args, message):
    if parsed_args.list_priority:
        cf_message = omega_service.QueuePriorityList(server_name)
        await omega_service.get_service_manager().send_message(cf_message)
        try:
            result = await cf_message.result
            result = json.dumps(result, indent=1)
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**Queue Priority**\n```{result}```')
            ))
        except asyncio.CancelledError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**Queue Priority**\nquery timed out')
            ))
    if 'create_priority' in parsed_args:
        cftools_id, comment, days = parsed_args.create_priority
        try:
            days = int(days)
            if days != -1:
                expires_at = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=days)
                expires_at = expires_at.timestamp()
            else:
                expires_at = -1
        except ValueError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'Invalid days: {days}')
            ))
            return
        cf_message = omega_service.QueuePriorityCreate(server_name, cftools_id, comment, expires_at)
        await omega_service.get_service_manager().send_message(cf_message)
        try:
            result = await cf_message.result
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**Create Priority**\n{result}')
            ))
        except asyncio.CancelledError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**Create Priority**\nquery timed out')
            ))
    if 'revoke_priority' in parsed_args:
        cftools_id = parsed_args.revoke_priority
        cf_message = omega_service.QueuePriorityRevoke(server_name, cftools_id)
        await omega_service.get_service_manager().send_message(cf_message)
        try:
            result = await cf_message.result
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**Revoke Priority**\n{result}')
            ))
        except asyncio.CancelledError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**Revoke Priority**\nquery timed out')
            ))
    if 'command' in parsed_args:
        if parsed_args.command is None:
            command = 'commands'
        else:
            command = parsed_args.command
        service_message = rcon_service.Command(server_name, command)
        await rcon_service.get_service_manager(server_name).send_message(service_message)
        try:
            result = await service_message.result
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**{command}**\n{str(result) if result else "success"}')
            ))
        except asyncio.CancelledError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, f'**{command}**\nquery timed out')
            ))
    if 'shutdown' in parsed_args:
        if parsed_args.shutdown is not None:
            delay = parsed_args.shutdown
        else:
            delay = 0
        service_message = rcon_service.SafeShutdown(server_name, delay)
        await rcon_service.get_service_manager(server_name).send_message(service_message)
    if parsed_args.status:
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
        asyncio.create_task(discord_service.get_service_manager().send_message(
            discord_service.Response(server_name, f'```{json.dumps(commands_info, indent=1)}```')
        ))
    if 'skip' in parsed_args:
        i = parsed_args.skip
        if not 0 <= i < len(scheduled_command.services.get(server_name, list())):
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.Response(server_name, 'Invalid index')
            ))
        else:
            await scheduled_command.get_service_manager(server_name, i).send_message(
                scheduled_command.Skip(server_name)
            )
    if parsed_args.kill:
        sys.exit(0)
    if parsed_args.version:
        asyncio.create_task(discord_service.get_service_manager().send_message(
            discord_service.Response(server_name, f'{carim_discord_bot.VERSION}')
        ))


async def process_user_message_args(channel_id, parsed_args):
    if 'leaderboard' in parsed_args:
        query_stat = parsed_args.leaderboard[0]
        server_index = parsed_args.leaderboard[1]
        try:
            server_name = config.get().server_names[server_index]
        except IndexError:
            index_names = json.dumps({k: v for k, v in enumerate(config.get().server_names)})
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Leaderboard', f'Invalid index. Valid options:\n{index_names}')
            ))
            return
        if config.get().cf_cloud_application_id is not None:
            stat_options = (
                'deaths',
                'kills',
                'playtime',
                'longest_kill',
                'longest_shot',
                'suicides',
                'kdratio'
            )
        else:
            stat_options = (
                'deaths',
                'kills',
                'playtime',
                'damage_dealt',
                'damage_taken',
                'hits',
                'hitted',
                'longest_kill_distance',
                'kdratio'
            )
        if query_stat not in stat_options:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Leaderboard',
                                             f'Invalid leaderboard stat. Valid options:\n{stat_options}')
            ))
            return

        if config.get().cf_cloud_application_id is not None:
            message = cf_cloud_service.Leaderboard(server_name, query_stat)
            await cf_cloud_service.get_service_manager().send_message(message)
        else:
            message = omega_service.Leaderboard(server_name, query_stat)
            await omega_service.get_service_manager().send_message(message)

        try:
            result = await message.result
            result_data = []
            stats = None
            for r in result.get('leaderboard' if config.get().cf_cloud_application_id is not None else 'users', list()):
                if stats is None:
                    stats = tuple(k for k in r.keys() if k not in ('cftools_id', 'rank', 'latest_name'))
                    result_data.append([stat for stat in ('#',) + ('name',) + stats])
                line_items = [r['rank']]
                line_items += [r['latest_name']]
                for stat in stats:
                    if isinstance(r[stat], float):
                        line_items += [f'{r[stat]:.2f}']
                    elif stat == 'playtime':
                        line_items += [str(datetime.timedelta(seconds=r[stat]))]
                    else:
                        line_items += [r[stat]]
                result_data.append(line_items)
            s = [[str(e) for e in row] for row in result_data]
            lens = [max(map(len, col)) for col in zip(*s)]
            fmt = ' '.join('{{:{}}}'.format(x) for x in lens)
            table = [fmt.format(*row) for row in s]
            formatted_result = '```\n' + '\n'.join(table) + '\n```'
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Leaderboard', formatted_result)
            ))
        except asyncio.CancelledError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Leaderboard', 'query timed out')
            ))
    if 'stats' in parsed_args:
        steam64 = parsed_args.stats[0]
        server_index = parsed_args.stats[1]
        try:
            server_name = config.get().server_names[server_index]
        except IndexError:
            index_names = json.dumps({k: v for k, v in enumerate(config.get().server_names)})
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Stats', f'Invalid index. Valid options:\n{index_names}')
            ))
            return

        if config.get().cf_cloud_application_id is not None:
            message = cf_cloud_service.Stats(server_name, steam64)
            await cf_cloud_service.get_service_manager().send_message(message)
        else:
            message = omega_service.Stats(server_name, steam64)
            await omega_service.get_service_manager().send_message(message)

        try:
            result = await message.result
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Stats', result)
            ))
        except asyncio.CancelledError:
            asyncio.create_task(discord_service.get_service_manager().send_message(
                discord_service.UserResponse(channel_id, 'Stats', 'query timed out')
            ))
