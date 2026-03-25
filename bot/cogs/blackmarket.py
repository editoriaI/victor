from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot import embeds
from bot.config import Config
from bot.utils.permissions import has_any_role


class BlackmarketCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _has_any_role(self, member: discord.Member, role_names: list) -> bool:
        return has_any_role(member.roles, role_names)

    def _is_owner(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self.cfg.roles.get("owner", []))

    def _is_admin(self, member: discord.Member) -> bool:
        if self._is_owner(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("admin", []))

    def _can_blackmarket(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("blackmarket", []))

    def _blacklist_record(self, discord_id: str) -> Optional[dict]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.is_blacklisted(conn, discord_id)
        finally:
            conn.close()

    async def _send_interaction_embed(
        self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = True
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    @commands.group(name="blackmarket", invoke_without_command=True)
    async def blackmarket(self, ctx: commands.Context) -> None:
        embed = embeds.invalid_usage_embed("!blackmarket list | add | remove")
        await ctx.send(embed=embed)

    @blackmarket.command(name="list")
    async def list_listings(self, ctx: commands.Context, *, query: str = "") -> None:
        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listings = db.list_listings(conn, item_query=query if query else None)
        finally:
            conn.close()

        embed = embeds.listings_embed(listings)
        await ctx.send(embed=embed)

    @blackmarket.command(name="add")
    async def add_listing(self, ctx: commands.Context, item_name: str, price: int) -> None:
        if not self._can_blackmarket(ctx.author):
            embed = embeds.permission_denied_embed("Blackmarket")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        if price <= 0:
            embed = embeds.invalid_usage_embed("!blackmarket add \"item\" 25000")
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listing_id = db.create_listing(conn, str(ctx.author.id), item_name, int(price))
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="LISTING_ADD",
                target_id=str(listing_id),
                details=f"item={item_name}|price={price}",
            )
            conn.commit()
        finally:
            conn.close()

        embed = embeds.listing_created_embed(listing_id, item_name, price)
        await ctx.send(embed=embed)

    @blackmarket.command(name="remove")
    async def remove_listing(self, ctx: commands.Context, listing_id: int) -> None:
        if not self._can_blackmarket(ctx.author):
            embed = embeds.permission_denied_embed("Blackmarket")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listing = db.fetch_listing(conn, int(listing_id))
            if not listing:
                embed = embeds.not_found_embed(str(listing_id))
                await ctx.send(embed=embed)
                return

            if not self._is_admin(ctx.author) and listing["seller_id"] != str(ctx.author.id):
                embed = embeds.permission_denied_embed("Blackmarket")
                await ctx.send(embed=embed)
                return

            db.close_listing(conn, int(listing_id))
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="LISTING_REMOVE",
                target_id=str(listing_id),
                details="removed",
            )
            conn.commit()
        finally:
            conn.close()

        embed = embeds.listing_removed_embed(int(listing_id))
        await ctx.send(embed=embed)

    @app_commands.command(name="marketlist", description="Show open blackmarket listings.")
    @app_commands.describe(query="Optional item name filter")
    @app_commands.guild_only()
    async def market_list_slash(
        self, interaction: discord.Interaction, query: Optional[str] = None
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listings = db.list_listings(conn, item_query=query if query else None)
        finally:
            conn.close()

        await self._send_interaction_embed(interaction, embeds.listings_embed(listings))

    @app_commands.command(name="marketadd", description="Create a blackmarket listing.")
    @app_commands.describe(item_name="Item to list", price="Listing price")
    @app_commands.guild_only()
    async def market_add_slash(
        self, interaction: discord.Interaction, item_name: str, price: int
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        if price <= 0:
            await self._send_interaction_embed(
                interaction, embeds.invalid_usage_embed("/marketadd item_name price")
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listing_id = db.create_listing(conn, str(author.id), item_name, int(price))
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="LISTING_ADD",
                target_id=str(listing_id),
                details=f"item={item_name}|price={price}",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(
            interaction, embeds.listing_created_embed(listing_id, item_name, price)
        )

    @app_commands.command(name="marketremove", description="Remove one of your blackmarket listings.")
    @app_commands.describe(listing_id="Listing ID to remove")
    @app_commands.guild_only()
    async def market_remove_slash(self, interaction: discord.Interaction, listing_id: int) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listing = db.fetch_listing(conn, int(listing_id))
            if not listing:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(listing_id)))
                return

            if not self._is_admin(author) and listing["seller_id"] != str(author.id):
                await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"))
                return

            db.close_listing(conn, int(listing_id))
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="LISTING_REMOVE",
                target_id=str(listing_id),
                details="removed",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(interaction, embeds.listing_removed_embed(int(listing_id)))


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(BlackmarketCog(bot, cfg))
