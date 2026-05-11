import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import db, embeds
from bot.config import Config
from bot.utils.permissions import has_any_role


def _slugify(value: str, *, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().casefold()).strip("-")
    return text or fallback


class ProjectUpdateModal(discord.ui.Modal):
    def __init__(self, project_cog: "ProjectsCog", update_type: str) -> None:
        super().__init__(title=f"Victor // {update_type.title()} Update")
        self.project_cog = project_cog
        self.update_type = update_type
        self.project_name = discord.ui.TextInput(
            label="Project",
            placeholder="victor-bot, highrise-bot, old-client, etc.",
            max_length=80,
            required=True,
        )
        self.fold_name = discord.ui.TextInput(
            label="Fold",
            placeholder="banking, menu-flow, auth, archive, polish, etc.",
            max_length=60,
            required=True,
        )
        self.title_text = discord.ui.TextInput(
            label="Short title",
            placeholder="What changed or needs to change?",
            max_length=100,
            required=True,
        )
        self.details = discord.ui.TextInput(
            label="Details",
            style=discord.TextStyle.long,
            placeholder="Keep the intricate part here. Victor will file it under the project and fold.",
            max_length=2000,
            required=True,
        )
        self.add_item(self.project_name)
        self.add_item(self.fold_name)
        self.add_item(self.title_text)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.project_cog.handle_project_update_modal(
            interaction,
            update_type=self.update_type,
            project_name=str(self.project_name),
            fold_name=str(self.fold_name),
            title=str(self.title_text),
            details=str(self.details),
        )


class ProjectHotView(discord.ui.View):
    def __init__(self, project_cog: "ProjectsCog") -> None:
        super().__init__(timeout=300)
        self.project_cog = project_cog

    async def _open_modal(self, interaction: discord.Interaction, update_type: str) -> None:
        if not self.project_cog._can_use_project_desk(interaction.user):
            await self.project_cog._send_interaction_embed(
                interaction,
                embeds.permission_denied_embed("Victor Admin"),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ProjectUpdateModal(self.project_cog, update_type))

    @discord.ui.button(label="Feature", style=discord.ButtonStyle.primary)
    async def feature_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._open_modal(interaction, "feature")

    @discord.ui.button(label="Fix", style=discord.ButtonStyle.secondary)
    async def fix_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._open_modal(interaction, "fix")

    @discord.ui.button(label="Research", style=discord.ButtonStyle.secondary)
    async def research_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._open_modal(interaction, "research")

    @discord.ui.button(label="Archive", style=discord.ButtonStyle.secondary)
    async def archive_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._open_modal(interaction, "archive")


class ProjectsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _has_any_role(self, member: discord.Member, role_names: list[str]) -> bool:
        return has_any_role(member, role_names)

    def _can_use_project_desk(self, user: discord.abc.User) -> bool:
        if isinstance(user, discord.Member):
            if self._has_any_role(user, self.cfg.roles.get("owner", [])):
                return True
            if self._has_any_role(user, self.cfg.roles.get("admin", [])):
                return True
        return False

    async def _send_interaction_embed(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        *,
        ephemeral: bool = True,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        kwargs = {"embed": embed, "ephemeral": ephemeral}
        if view is not None:
            kwargs["view"] = view
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
            return
        await interaction.response.send_message(**kwargs)

    def _hot_view(self) -> ProjectHotView:
        return ProjectHotView(self)

    async def handle_project_update_modal(
        self,
        interaction: discord.Interaction,
        *,
        update_type: str,
        project_name: str,
        fold_name: str,
        title: str,
        details: str,
    ) -> None:
        actor = interaction.user
        if not self._can_use_project_desk(actor):
            await self._send_interaction_embed(
                interaction,
                embeds.permission_denied_embed("Victor Admin"),
                ephemeral=True,
            )
            return

        cleaned_project = project_name.strip()
        cleaned_fold = fold_name.strip()
        cleaned_title = title.strip()
        cleaned_details = details.strip()
        if not cleaned_project or not cleaned_fold or not cleaned_title or not cleaned_details:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("project + fold + title + details"),
                ephemeral=True,
            )
            return

        project_key = _slugify(cleaned_project, fallback="project")
        fold_key = _slugify(cleaned_fold, fallback="general")
        status = "ARCHIVED" if update_type == "archive" else "ACTIVE"

        conn = db.get_connection(self.cfg.db_path)
        try:
            project_id = db.upsert_project(
                conn,
                project_key=project_key,
                project_name=cleaned_project,
                created_by=str(actor.id),
                status=status,
            )
            update_id = db.create_project_update(
                conn,
                project_id=project_id,
                fold_key=fold_key,
                update_type=update_type,
                title=cleaned_title,
                details=cleaned_details,
                created_by=str(actor.id),
            )
            db.log_audit(
                conn,
                actor_id=str(actor.id),
                action="PROJECT_UPDATE_ADD",
                target_id=str(update_id),
                details=f"project={project_key}|fold={fold_key}|type={update_type}|title={cleaned_title}",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(
            interaction,
            embeds.project_update_created_embed(
                cleaned_project,
                fold_key,
                update_type,
                cleaned_title,
                update_id,
            ),
            ephemeral=True,
        )

    async def _send_hotdesk(self, destination) -> None:
        await destination.send(embed=embeds.project_hot_embed(), view=self._hot_view())

    @commands.command(name="hot", aliases=["hotmenu"])
    async def hot_command(self, ctx: commands.Context) -> None:
        if not self._can_use_project_desk(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Victor Admin"))
            return
        await self._send_hotdesk(ctx)

    @app_commands.command(name="hot", description="Open the reusable project update desk.")
    @app_commands.guild_only()
    async def hot_slash(self, interaction: discord.Interaction) -> None:
        if not self._can_use_project_desk(interaction.user):
            await self._send_interaction_embed(
                interaction,
                embeds.permission_denied_embed("Victor Admin"),
                ephemeral=True,
            )
            return
        await self._send_interaction_embed(
            interaction,
            embeds.project_hot_embed(),
            ephemeral=True,
            view=self._hot_view(),
        )


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    cog = ProjectsCog(bot, cfg)
    await bot.add_cog(cog)
