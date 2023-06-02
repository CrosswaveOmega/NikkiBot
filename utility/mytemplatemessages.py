
from typing import List, Union
from discord import Embed, Color, Guild, Message
from discord.ext import commands
from .globalfunctions import get_server_icon_color
from .manual_load import load_manual
from assets import AssetLookup

embedicon=None

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
        if 'fields' in dictionary:
            for i in dictionary['fields']:
                if 'inline' not in i:
                    embed.add_field(**i, inline=False)
                else:
                    embed.add_field(**i)
        if 'image' in dictionary:
            embed.set_image(url=dictionary['image']['url'])
        embed.set_footer(text=f"{AssetLookup.get_asset('name')}'s Manual",icon_url=AssetLookup.get_asset('embed_icon'))
        return embed

    @staticmethod
    def get_error_embed(title: str, description: str):
        embed=Embed(title=title, description=description, color=Color(0xff0000))
        embed.set_author(name="Error Message",icon_url=embedicon)
        return embed
    
    @staticmethod
    def get_paged_error_embed(title: str, description: Union[str,List[str]]):
        pageme=commands.Paginator(prefix="",suffix="",max_size=4096)
        for p in description.split('\n'):pageme.add_line(p)
        embeds=[]
        for page in pageme.pages:
            embed=Embed(title=title, description=page, color=Color(0xff0000))
            embed.set_author(name="Error Message",icon_url=embedicon)
            embeds.append(embed)
        return embeds
    @staticmethod
    async def get_manual_list(ctx:commands.Context, file:str, **kwargs):
        '''
        Return a list of manual pages.
        '''
        manual=load_manual(file,ctx)
        embed_list = [MessageTemplates.get_bot_manual_embed(e) for e in manual['embeds']]
        return embed_list

    @staticmethod
    async def server_profile_embed_list(ctx:commands.Context, description: List[str], ephemeral=True, **kwargs):
        '''
        Return a simple overview of a server & basic data provided by the cogs.
        '''
        hex=await get_server_icon_color(ctx.guild)
        # Get a list of all cogs loaded by the bot
        extended_fields=ctx.bot.get_field_list(ctx.guild)
        embeds=[]
        for d in description:
            embed=MessageTemplates.get_server_profile_embed(
                ctx.guild, 
                d,
                extend_field_list=extended_fields,
                color=hex)
            embeds.append(embed)
        return embeds



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


