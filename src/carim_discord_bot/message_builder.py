import datetime

import discord

from carim_discord_bot import config


class Response:
    def __init__(self, configuration):
        self.enabled = configuration.get('enabled', True)
        self.channels = configuration.get('channels', list())
        self.command = configuration['command']

        response = configuration['response']
        self.title = response.get('title', '')
        self.description = response.get('text', '')
        self.url = response.get('url', '')
        self.color = response.get('color', -1)

        self.image = response.get('image', dict())
        self.video = response.get('video', dict())
        self.thumbnail = response.get('thumbnail', dict())

        self.author = response.get('author', dict())
        self.footer = response.get('footer', dict())

    def generate(self):
        embed = discord.Embed()
        if self.title:
            embed.title = self.title
        if self.description:
            embed.description = self.description
        if self.url:
            embed.url = self.url
        if self.color > -1:
            embed.colour = self.color

        for content, proxy in ((self.image, embed.image), (self.video, embed.video), (self.thumbnail, embed.thumbnail)):
            if content:
                proxy.url = content['url']
                proxy.width = content.get('width', discord.Embed.Empty)
                proxy.height = content.get('height', discord.Embed.Empty)

        if self.author:
            proxy = embed.author
            proxy.name = self.author.get('name', discord.Embed.Empty)
            proxy.url = self.author.get('url', discord.Embed.Empty)
            proxy.icon_url = self.author.get('icon_url', discord.Embed.Empty)
        if self.footer:
            proxy = embed.footer
            proxy.text = self.footer.get('text', discord.Embed.Empty)
            proxy.icon_url = self.footer.get('icon_url', discord.Embed.Empty)

        return embed


def build_embed(title=None, message=None):
    if message is None:
        message = title
        title = None
    embed_args = dict(title=title, description=message)
    embed = discord.Embed(**embed_args)
    if config.get().include_timestamp:
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        embed.set_footer(text=timestamp)
    return embed
