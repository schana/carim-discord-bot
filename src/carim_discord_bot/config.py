import json
import logging

log = logging.getLogger(__name__)


class Config:
    def __init__(self, token, ip, port, password, steam_port, presence, presence_type, publish_channel_id,
                 admin_channels, chat_channel_id, chat_ignore_regex, count_channel_id, update_player_count_interval,
                 rcon_keep_alive_interval, log_connect_disconnect_notices, log_player_count_updates, log_rcon_messages,
                 log_rcon_keep_alive, include_timestamp, debug, scheduled_commands):
        self.token = token
        self.ip = ip
        self.port = port
        self.password = password
        self.steam_port = steam_port
        self.presence = presence
        self.presence_type = presence_type
        self.publish_channel_id = publish_channel_id
        self.admin_channels = admin_channels
        self.chat_channel_id = chat_channel_id
        self.chat_ignore_regex = chat_ignore_regex
        self.count_channel_id = count_channel_id
        self.update_player_count_interval = update_player_count_interval
        self.rcon_keep_alive_interval = rcon_keep_alive_interval
        self.log_connect_disconnect_notices = log_connect_disconnect_notices
        self.log_player_count_updates = log_player_count_updates
        self.log_rcon_messages = log_rcon_messages
        self.log_rcon_keep_alive = log_rcon_keep_alive
        self.include_timestamp = include_timestamp
        self.debug = debug
        self.scheduled_commands = scheduled_commands

    @staticmethod
    def build_from_dict(config):
        token = config['token']
        ip = config['rcon_ip']
        port = config['rcon_port']
        password = config['rcon_password']
        steam_port = config['steam_port']

        presence = config.get('bot_presence')
        presence_type = config.get('bot_presence_type', 'playing')
        if presence_type not in ('playing', 'listening', 'watching'):
            log.error(f'config.json unknown presence type ({presence_type}), using default instead')
            presence_type = 'playing'

        publish_channel_id = config.get('rcon_admin_log_channel')
        if publish_channel_id is None:
            publish_channel_id = config.get('rcon_publish_channel')
            if publish_channel_id is not None:
                log.warning('config.json rcon_publish_channel is deprecated, use rcon_admin_log_channel instead')
        publish_channel_id = Config.check_channel_default(channel=publish_channel_id)

        admin_channels = config.get('rcon_admin_channels', list())
        if isinstance(admin_channels, int):
            log.warning('config.json rcon_admin_channels should be a list, but only an int was found')
            admin_channels = [admin_channels]
        admin_channels = Config.check_channel_default(channels=admin_channels)

        chat_channel_id = Config.check_channel_default(channel=config.get('rcon_chat_channel'))
        chat_ignore_regex = config.get('rcon_chat_ignore_regex', r'^$')
        count_channel_id = Config.check_channel_default(channel=config.get('rcon_count_channel'))

        update_player_count_interval = config.get('update_player_count_interval', 300)
        rcon_keep_alive_interval = config.get('rcon_keep_alive_interval', 30)

        discord_logging_verbosity = config.get('log_events_in_discord', dict())

        log_connect_disconnect_notices = discord_logging_verbosity.get('connect_disconnect_notices', True)
        log_player_count_updates = discord_logging_verbosity.get('player_count_updates', True)
        log_rcon_messages = discord_logging_verbosity.get('rcon_messages', True)
        log_rcon_keep_alive = discord_logging_verbosity.get('rcon_keep_alive', True)
        include_timestamp = discord_logging_verbosity.get('include_timestamp', True)

        debug = config.get('debug', False)

        scheduled_commands = config.get('scheduled_commands', list())
        if not isinstance(scheduled_commands, list):
            message = 'config.json scheduled_commands needs to be a list if present'
            log.error(message)
            raise ValueError(message)

        return Config(token, ip, port, password, steam_port, presence, presence_type, publish_channel_id,
                      admin_channels, chat_channel_id, chat_ignore_regex, count_channel_id,
                      update_player_count_interval, rcon_keep_alive_interval, log_connect_disconnect_notices,
                      log_player_count_updates, log_rcon_messages, log_rcon_keep_alive, include_timestamp, debug,
                      scheduled_commands)

    @staticmethod
    def check_channel_default(channel=None, channels: list = None):
        if channel is not None:
            return None if channel == 0 else channel
        if channels is not None:
            if 0 in channels:
                channels.remove(0)
            return channels

    @staticmethod
    def build_from(file_path):
        with open(file_path) as f:
            config = json.load(f)
        return Config.build_from_dict(config)


_config: Config = None


def get() -> Config:
    return _config


def set(config):
    global _config
    _config = config
