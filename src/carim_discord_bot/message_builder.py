import logging

import discord

log = logging.getLogger(__name__)


class Response:
    def __init__(self, configuration):
        self.enabled = configuration.get('enabled', True)
        self.channels = configuration.get('channels', list())
        self.command = configuration['command']
        self.response = configuration['response']

    def generate(self):
        embed = discord.Embed.from_dict(self.response)
        log.info(f'generated embed: {embed.to_dict()}')
        return embed


def build_embed(title=None, message=None):
    if message is None:
        message = title
        title = None
    embed_args = dict(title=title, description=message)
    embed = discord.Embed(**embed_args)
    return embed
