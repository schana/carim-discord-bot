import logging

import discord

log = logging.getLogger(__name__)


class CarimClient(discord.Client):
    async def on_ready(self):
        log.info(f'Logged in as {self.user}')
