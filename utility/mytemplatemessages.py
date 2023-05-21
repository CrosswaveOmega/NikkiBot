
from discord import Embed, Color, Guild, Message
from discord.ext import commands
from database import ServerArchiveProfile
import datetime
from .globalfunctions import get_server_icon_color
from .manual_load import load_manual
from assets import AssetLookup

embedicon=None
upper_ignore_limit=50
class MessageTemplates:
    '''Class full of static methods that serve as templates for formatted embeds.'''
    @staticmethod
    def get_server_profile_embed(guild:Guild, description: str, extend_field_list=[],color=0xffffff):
        '''create a embed to display a simple overview on any server.'''
        '''utilizes the extend_field_list'''
        embed=Embed(title=guild.name, description=description, color=Color(color))
        for i in extend_field_list:
            embed.add_field(**i)
        embed.set_thumbnail(url=guild.icon)
        embed.set_author(name=f"{AssetLookup.get_asset('name')}'s Server Profile",icon_url=AssetLookup.get_asset('embed_icon'))
        embed.set_footer(text=f"Server ID: {guild.id}")
        return embed

    @staticmethod
    def get_bot_manual_embed(dictionary:dict,color=0x127a09):
        '''create a embed to display a simple overview on any server.'''
        '''utilizes the extend_field_list'''
        if 'color' in dictionary: dictionary.pop('color')
        if not 'title' in dictionary: dictionary['title']="No title"
        if not 'description' in dictionary: dictionary['description']="N/A"
        embed=Embed(title=dictionary['title'], description=dictionary["description"], color=Color(color))
        for i in dictionary['fields']:
            if 'inline' not in i:
                embed.add_field(**i, inline=False)
            else:
                embed.add_field(**i)
        embed.set_footer(text=f"{AssetLookup.get_asset('name')}'s Manual",icon_url=AssetLookup.get_asset('embed_icon'))
        return embed

    @staticmethod
    def get_server_archive_embed(guild:Guild, description: str, color=0xffffff):
        '''create a server archive embed.'''
        profile=ServerArchiveProfile.get_or_new(guild.id)
        aid,mentions="NOT SET","No ignored channels"
        hist_channel=profile.history_channel_id
        last_date="Never compiled"
        if profile.last_archive_time:
            timestamped=profile.last_archive_time.timestamp()
            last_date=f"<t:{int(timestamped)}:f>"
        if hist_channel: aid=f"<#{hist_channel}>"
        clist=profile.list_channels()
        if clist: mentions=",".join( [f"<#{ment}>" for ment in clist[:upper_ignore_limit]])
        if len(clist) > upper_ignore_limit: mentions += f' and {len(clist)-upper_ignore_limit} more!'
        embed=Embed(title=guild.name, description=f'ignored channels:{mentions}', color=Color(color))
        embed.add_field(name="Archive Channel",value=aid)
        embed.add_field(name="Last Archive Date",
                        value=last_date)
        embed.add_field(name="Result",value=description, inline=False)

        embed.set_thumbnail(url=guild.icon)
        embed.set_author(name="Server RP Archive System",icon_url=embedicon)
        embed.set_footer(text=f"Server ID: {guild.id}")
        return embed

    @staticmethod
    def get_error_embed(title: str, description: str):
        embed=Embed(title=title, description=description, color=Color(0xff0000))
        embed.set_author(name="Error Message",icon_url=embedicon)
        return embed
    @staticmethod
    async def get_manual_list(ctx:commands.Context, file:str, **kwargs):
        '''
        Return a list of manual pages.
        '''
        manual=load_manual(file,ctx)
        embed_list = [MessageTemplates.get_bot_manual_embed(e) for e in manual['embeds']]
        return embed_list



        

    @staticmethod
    async def server_archive_message(ctx:commands.Context, description: str, **kwargs):
        hex=await get_server_icon_color(ctx.guild)
        embed=MessageTemplates.get_server_archive_embed(ctx.guild, description, color=hex)
        await ctx.send(embed=embed,**kwargs)

    @staticmethod
    async def server_profile_message(ctx:commands.Context, description: str, ephemeral=True, **kwargs):
        '''
        Return a simple overview of a server & basic data provided by the cogs.
        '''
        hex=await get_server_icon_color(ctx.guild)
        # Get a list of all cogs loaded by the bot
        extended_fields=ctx.bot.get_field_list(ctx.guild)
        embed=MessageTemplates.get_server_profile_embed(
            ctx.guild, 
            description,
            extend_field_list=extended_fields,
            color=hex)
        if ctx.interaction and ephemeral:
            message:Message=await ctx.send(embed=embed, ephemeral=True,**kwargs)
            return message
        message:Message=await ctx.send(embed=embed, **kwargs)
        return message


