import logging

import discord
from discord.ext import commands

from bot import embeds
from bot.config import Config
from bot.utils.command_logging import log_command_event


class MonitorCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg
        self.logger = logging.getLogger("victor.monitor")

    async def _report_failure(
        self, surface: str, user_id: int, command_name: str, error: Exception, location: str, details: str
    ) -> None:
        self.logger.exception("%s command failed: %s", surface, command_name, exc_info=error)
        await log_command_event(
            self.bot,
            self.cfg,
            "fail",
            surface,
            user_id,
            command_name,
            location,
            details=details,
            level=logging.ERROR,
        )

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        await log_command_event(
            self.bot,
            self.cfg,
            "success",
            "prefix",
            ctx.author.id,
            ctx.command.qualified_name if ctx.command else "unknown",
            str(ctx.guild.id) if ctx.guild else "dm",
            details=ctx.message.content,
            publish_to_channel=False,
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if getattr(ctx.command, "on_error", None):
            return
        if ctx.cog and ctx.cog is not self:
            overridden = ctx.cog._get_overridden_method(getattr(ctx.cog, "cog_command_error", None))
            if overridden is not None:
                return

        original = getattr(error, "original", error)
        command_name = ctx.command.qualified_name if ctx.command else "unknown"
        location = str(ctx.guild.id) if ctx.guild else "dm"

        if isinstance(error, commands.CommandNotFound):
            await log_command_event(
                self.bot,
                self.cfg,
                "fail",
                "prefix",
                ctx.author.id,
                "unknown",
                location,
                details=ctx.message.content,
                level=logging.WARNING,
                publish_to_channel=False,
            )
            embed = embeds.invalid_usage_embed(f"Unknown command: {ctx.message.content}")
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await log_command_event(
                self.bot,
                self.cfg,
                "fail",
                "prefix",
                ctx.author.id,
                command_name,
                location,
                details="missing required argument",
                level=logging.WARNING,
                publish_to_channel=False,
            )
            usage = f"{self.bot.command_prefix}{ctx.command.qualified_name}" if ctx.command else "command"
            embed = embeds.invalid_usage_embed(usage)
            await ctx.send(embed=embed)
            return

        if isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound)):
            await log_command_event(
                self.bot,
                self.cfg,
                "fail",
                "prefix",
                ctx.author.id,
                command_name,
                location,
                details=str(error),
                level=logging.WARNING,
                publish_to_channel=False,
            )
            embed = embeds.invalid_usage_embed(ctx.message.content)
            await ctx.send(embed=embed)
            return

        await self._report_failure(
            "prefix",
            ctx.author.id,
            command_name,
            original,
            location,
            str(error),
        )
        await ctx.send(embed=embeds.system_error_embed())

async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(MonitorCog(bot, cfg))
