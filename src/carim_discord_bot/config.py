import json
import logging

from carim_discord_bot import message_builder

log = logging.getLogger(__name__)
_global_config = None
_server_configs = dict()


class GlobalConfig:
    def __init__(self):
        self.token = None
        self.presence = None
        self.presence_type = None
        self.discord_member_count_channel_id = None
        self.discord_member_count_format = '{count} members'
        self.user_channel_ids = list()
        self.debug = False
        self.log_player_count_updates = True

        self.cftools_application_id = None
        self.cftools_client_id = None
        self.cftools_secret = None

        self.cf_cloud_application_id = None
        self.cf_cloud_secret = None

        self.server_names = list()

        self.custom_commands = list()


class ServerConfig:
    def __init__(self):
        self.name = None
        self.ip = None
        self.rcon_port = None
        self.rcon_password = None
        self.steam_port = None
        self.admin_channel_id = None

        self.chat_channel_id = None
        self.chat_ignore_regex = r'^$'
        self.chat_show_connect_disconnect_notices = True

        self.player_count_channel_id = None
        self.player_count_format = '{players}/{slots} players online'
        self.player_count_queue_format = ''
        self.player_count_update_interval = 30

        self.log_rcon_messages = True
        self.log_rcon_keep_alive = False

        self.cftools_service_id = None

        self.cf_cloud_server_api_id = None

        self.scheduled_commands = list()


def _build_from_dict(raw, config_type):
    config = config_type()
    for key in config.__dict__:
        if key in raw:
            config.__setattr__(key, raw[key])
    return config


def initialize(file_path):
    global _global_config
    with open(file_path) as f:
        config = json.load(f)

    _global_config = _build_from_dict(config, GlobalConfig)

    for server_config in config.get('servers', list()):
        _server_configs[server_config['name']] = _build_from_dict(server_config, ServerConfig)
        _global_config.server_names.append(server_config['name'])

    _validate_config()


def _validate_config():
    if get().presence_type not in ('playing', 'listening', 'watching', None):
        raise ValueError(f'unknown presence type: {get().presence_type}')

    for server_name in _server_configs:
        scheduled_commands = get_server(server_name).scheduled_commands
        if not isinstance(scheduled_commands, list):
            raise ValueError(f'scheduled_commands not a list in config for: {server_name}')

    parsed_custom_commands = list()
    for raw_command in get().custom_commands:
        parsed_custom_commands.append(message_builder.Response(raw_command))
    get().custom_commands = parsed_custom_commands


def get() -> GlobalConfig:
    return _global_config


def get_server(name) -> ServerConfig:
    return _server_configs[name]


def get_server_names():
    return _server_configs.keys()
