

import discord
import logging
from discord import app_commands, Embed, Color
from discord.app_commands import Choice
from discord.ext import commands, tasks

from utility import MessageTemplates

from assets import AssetLookup

class PollMessageTemplates(MessageTemplates):


    @staticmethod
    def get_poll_embed(title:str, description: str, color=0xffffff):
        '''create a server archive embed.'''
        embed=Embed(title=title, description='', color=Color(color))

        embed.add_field(name="Result",value=description, inline=False)

        embed.set_author(name="Polling System",icon_url=AssetLookup.get_asset('embed_icon'))
        return embed

    @staticmethod
    async def poll_message(ctx, title: str, description: str, **kwargs):
        message:discord.Message=await ctx.send(embed=PollMessageTemplates.get_poll_embed(title, description), **kwargs)
        return message
