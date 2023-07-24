

import discord
import logging
from discord import app_commands, Embed, Colour
from discord.app_commands import Choice
from discord.ext import commands, tasks

from utility import MessageTemplates

from assets import AssetLookup

class MessageTemplatesMusic(MessageTemplates):

    @staticmethod
    def get_music_embed(title: str, description: str, merge_with:dict={},use_author=True):
        myname=AssetLookup.get_asset("name")
        myicon=AssetLookup.get_asset("embed_icon")
        embed=Embed(title="", description=description,color=Colour(0x68ff72))
        if use_author:
            embed.set_author(
            name=f"{myname}'s music player.",icon_url=myicon)
        if merge_with:
            title=merge_with["title"]
            duration=merge_with["duration"]
            remaining=merge_with["remaining"]
            embed.add_field(name="Song Data",value=f"{title} \n duration:{duration} \ Requested by: "+merge_with["requested_by"]+"")
            embed.set_footer(text=f"{myname}_music")
        return embed
    @staticmethod
    async def music_msg(ctx, title: str, description: str, merge_with={},view=None, use_author=True, delete_after=True):
        message:discord.Message=await ctx.send(embed=MessageTemplatesMusic.get_music_embed(title, description, merge_with,use_author))
        if delete_after:
            await message.add_reaction("📋")
            ctx.bot.schedule_for_deletion(message,60)
