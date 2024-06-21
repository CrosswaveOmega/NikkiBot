import discord
import logging
from discord import app_commands, Embed, Color
from discord.app_commands import Choice
from discord.ext import commands, tasks

from utility import MessageTemplates

from assetloader import AssetLookup


class PollMessageTemplates(MessageTemplates):
    @staticmethod
    def get_poll_embed(title: str, description: str, color=0xFFFFFF):
        """create a server archive embed."""
        embed = Embed(title=title, description="", color=Color(color))

        embed.add_field(name="Result", value=description, inline=False)

        embed.set_author(
            name="Polling System", icon_url=AssetLookup.get_asset("embed_icon")
        )
        return embed

    @staticmethod
    async def poll_message(
        ctx, description: str, title: str = "Polling", ephemeral: bool = False, **kwargs
    ):
        embed = PollMessageTemplates.get_poll_embed(title, description)
        if ctx.interaction and ephemeral:
            message: discord.Message = await ctx.send(
                embed=embed, ephemeral=True, **kwargs
            )
            return message
        message: discord.Message = await ctx.send(embed=embed, **kwargs)
        return message
