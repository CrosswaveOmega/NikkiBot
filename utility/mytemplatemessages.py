from typing import List, Union
from discord import Embed, Color, Guild, Message
from discord.ext import commands
from .manual_load import load_manual
from .views import ConfirmView
from assetloader import AssetLookup
from database.database_ai import ServerAIConfig
import re

embedicon = None


class MessageTemplates:
    """Class full of static methods that serve as templates for formatted embeds."""

    @staticmethod
    def get_ai_config_embed(guild, description: str, color=0xFFFFFF):
        """Create an embed based on a ServerAIConfig entry."""
        upper_channel_limit = 25
        profile = ServerAIConfig.get_or_new(guild.id)

        aid, mentions = "NOT SET", "No added channels"
        clist = profile.list_channels()
        if clist:
            mentions = ",".join([f"<#{ment}>" for ment in clist[:upper_channel_limit]])
        if len(clist) > upper_channel_limit:
            mentions += f" and {len(clist) - upper_channel_limit} more!"
        embed = Embed(
            title="Server AI Config", description=mentions, color=Color(color)
        )
        embed.set_author(
            name=f"{AssetLookup.get_asset('name')}'s Server AI Profile",
            icon_url=AssetLookup.get_asset("embed_icon"),
        )
        embed.add_field(name="Result", value=description, inline=False)

        embed.set_footer(text="AI Config Details")

        return embed

    @staticmethod
    async def server_ai_message(ctx, description="", **kwargs):
        embed = MessageTemplates.get_ai_config_embed(ctx.guild, description)
        return await ctx.send(embed=embed, **kwargs)

    @staticmethod
    def get_server_profile_embed(
        guild: Guild, description: str, extend_field_list=[], color=0xFFFFFF
    ):
        """create a embed to display a simple overview on any server."""
        """utilizes the extend_field_list"""
        embed = Embed(title=guild.name, description=description, color=Color(color))
        for i in extend_field_list:
            embed.add_field(**i)
        embed.set_thumbnail(url=guild.icon)
        embed.set_author(
            name=f"{AssetLookup.get_asset('name')}'s Server Profile",
            icon_url=AssetLookup.get_asset("embed_icon"),
        )

        embed.set_footer(text=f"Server ID: {guild.id}")
        return embed

    @staticmethod
    def get_tag_edit_embed(title: str, description: str, tag=None, color=0x127A09):
        """This is for the tag system."""
        tagres = ""
        if tag != None:
            if "text" in tag:
                to_send = tag["text"]
            else:
                to_send = "???"
            if len(to_send) > 2000:
                to_send = to_send[:1950] + "...tag size limit."
            tagres = f"{tag['tagname']}\n```{to_send}```\n Guild only:{tag.get('guild_only', '???')}"
        embed = Embed(title=title, description=tagres, color=Color(color))
        if tag != None:
            if "topic" in tag:
                if tag["topic"]:
                    embed.add_field(name="Category", value=tag["topic"], inline=False)

            if "filename" in tag:
                if tag["filename"]:
                    embed.add_field(
                        name="Has file", value=tag["filename"], inline=False
                    )
        embed.add_field(name="Result", value=description, inline=False)
        embed.set_thumbnail(url=AssetLookup.get_asset("embed_icon"))
        embed.set_author(
            name=f"{AssetLookup.get_asset('name')}'s Tag system",
            icon_url=AssetLookup.get_asset("embed_icon"),
        )

        return embed

    @staticmethod
    def get_bot_manual_embed(dictionary: dict, color=0x127A09):
        """create a embed to display a simple overview on any server."""
        """utilizes the extend_field_list"""
        if "color" in dictionary:
            dictionary.pop("color")
        if "title" not in dictionary:
            dictionary["title"] = "No title"
        if "description" not in dictionary:
            dictionary["description"] = "N/A"
        embed = Embed(
            title=dictionary["title"],
            description=dictionary["description"],
            color=Color(color),
        )
        if "fields" in dictionary:
            for i in dictionary["fields"]:
                if "inline" not in i:
                    embed.add_field(**i, inline=False)
                else:
                    embed.add_field(**i)
        if "image" in dictionary:
            embed.set_image(url=dictionary["image"]["url"])
        embed.set_footer(
            text=f"{AssetLookup.get_asset('name')}'s Manual",
            icon_url=AssetLookup.get_asset("embed_icon"),
        )
        return embed

    @staticmethod
    def get_error_embed(title: str, description: str):
        embed = Embed(title=title, description=description, color=Color(0xFF0000))
        embed.set_author(name="Error Message", icon_url=embedicon)
        return embed

    @staticmethod
    def get_checkfail_embed(title: str, description: str):
        embed = Embed(title=title, description=description, color=Color(0xFF0000))
        embed.set_author(name="Check Failure", icon_url=embedicon)
        return embed

    @staticmethod
    def split_lines(text: str, max_size):
        lines = []
        words = text.split(",")
        current_line = ""

        for word in words:
            if len(current_line + "," + word) <= max_size:
                current_line += "," + word

            else:
                lines.append(current_line.strip()[:3000])
                current_line = word

        if current_line:
            lines.append(current_line.strip()[:3000])

        return lines

    @staticmethod
    def get_paged_error_embed(title: str, description: Union[str, List[str]]):
        pageme = commands.Paginator(prefix="", suffix="", max_size=4096)

        description = re.sub(r"\\+n", r"\n", description)
        for p in description.split("\n"):
            if len(p) > 4000:
                sub = MessageTemplates.split_lines(p, 2000)
                for pe in sub:
                    pageme.add_line(pe)
            else:
                pageme.add_line(p)
        embeds = []
        for page in pageme.pages:
            embed = MessageTemplates.get_error_embed(title, page)
            embeds.append(embed)
        return embeds

    @staticmethod
    async def get_manual_list(ctx: commands.Context, file: str, **kwargs):
        """
        Return a list of manual pages.
        """
        manual = load_manual(file, ctx)
        embed_list = [
            MessageTemplates.get_bot_manual_embed(e) for e in manual["embeds"]
        ]
        return embed_list

    @staticmethod
    async def server_profile_embed_list(
        ctx: commands.Context, description: List[str], ephemeral=True, **kwargs
    ):
        """
        Return a simple overview of a server & basic data provided by the cogs.
        """
        hex = 0
        # Get a list of all cogs loaded by the bot
        extended_fields = ctx.bot.get_field_list(ctx.guild)
        embeds = []
        for d in description:
            embed = MessageTemplates.get_server_profile_embed(
                ctx.guild, d, extend_field_list=extended_fields, color=hex
            )
            embeds.append(embed)
        return embeds

    @staticmethod
    async def confirm(
        ctx: commands.Context, description: str, ephemeral=False, **kwargs
    ):
        """
        Send a quick yes/no message
        """
        confirm = ConfirmView(user=ctx.author)
        mes = await ctx.send(description, view=confirm, ephemeral=ephemeral)
        await confirm.wait()
        confirm.clear_items()
        await mes.edit(view=confirm)
        return confirm.value, mes

    @staticmethod
    async def tag_message(
        ctx: commands.Context,
        description: str,
        tag: dict = None,
        title="Tags",
        ephemeral=True,
        **kwargs,
    ):
        """
        Return a simple overview of a server & basic data provided by the cogs.
        """
        embed = MessageTemplates.get_tag_edit_embed(title, description, tag=tag)
        if ctx.interaction and ephemeral:
            message: Message = await ctx.send(embed=embed, ephemeral=True, **kwargs)
            return message
        message: Message = await ctx.send(embed=embed, **kwargs)
        return message

    @staticmethod
    async def server_profile_message(
        ctx: commands.Context, description: str, ephemeral=True, **kwargs
    ):
        """
        Return a simple overview of a server & basic data provided by the cogs.
        """
        # hex = await get_server_icon_color(ctx.guild)
        # Get a list of all cogs loaded by the bot
        extended_fields = ctx.bot.get_field_list(ctx.guild)
        embed = MessageTemplates.get_server_profile_embed(
            ctx.guild, description, extend_field_list=extended_fields, color=0
        )
        if ctx.interaction and ephemeral:
            message: Message = await ctx.send(embed=embed, ephemeral=True, **kwargs)
            return message
        message: Message = await ctx.send(embed=embed, **kwargs)
        return message
