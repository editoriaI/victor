import logging

import discord
from discord.ext import commands

from bot.config import Config

logger = logging.getLogger("victor.sync")


async def sync_application_commands(bot: commands.Bot, cfg: Config) -> int:
    synced_count = 0

    if cfg.command_guild_ids:
        for guild_id in cfg.command_guild_ids:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)

        bot.tree.clear_commands(guild=None)
        cleared = await bot.tree.sync()
        logger.info("Cleared %s global application commands before guild sync", len(cleared))

        for guild_id in cfg.command_guild_ids:
            guild = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild)
            synced_count = max(synced_count, len(synced))
            logger.info("Synced %s application commands to guild %s", len(synced), guild_id)
    else:
        synced = await bot.tree.sync()
        synced_count = len(synced)
        logger.info("Synced %s application commands", len(synced))

    bot.victor_synced_count = synced_count
    return synced_count
