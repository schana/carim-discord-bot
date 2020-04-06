import datetime

import discord

from carim_discord_bot import config


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
