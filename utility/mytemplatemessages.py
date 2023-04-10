
from discord import Embed, Color, Guild
from discord.ext import commands
from database import ServerArchiveProfile

from .globalfunctions import get_server_icon_color


embedicon=None
class MessageTemplates:
    '''Class full of static methods that serve as templates for formatted embeds.'''
    @staticmethod
    def get_server_archive_embed(guild:Guild, description: str):
        '''create a server archive embed.'''
        profile=ServerArchiveProfile.get_or_new(guild.id)
        aid,mentions="NOT SET","No ignored channels"
        ment=profile.history_channel_id
        if ment: aid=f"<#{ment}>"
        clist=profile.list_channels()
        if clist: mentions=",".join( [f"<#{ment}>" for ment in clist])
        hex=get_server_icon_color(guild)
        embed=Embed(title=guild.name, description=mentions, color=Color(int(hex,16)))
        embed.add_field(name="Archive Channel",value=aid)
        embed.add_field(name="Result",value=description, inline=False)
        embed.set_thumbnail(url=guild.icon)
        embed.set_author(name="Server RP Archive System",icon_url=embedicon)
        embed.set_footer(text=f"Server ID: {guild.id}")
        return embed

    @staticmethod
    def get_error_embed(title: str, description: str):
        embed=Embed(title=title, description=description, color=Color(0xff6868))
        embed.set_author(name="Error Message",icon_url=embedicon)
        return embed

    @staticmethod
    async def server_archive_message(ctx:commands.Context, description: str):
        await ctx.send(embed=MessageTemplates.get_server_archive_embed(ctx.guild, description))

