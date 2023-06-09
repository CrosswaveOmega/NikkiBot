
from discord import Embed, Color, Guild
from discord.ext import commands

from utility import MessageTemplates, get_server_icon_color
from bot import TCGuildTask
from assets import AssetLookup
upper_ignore_limit=50
from database import ServerArchiveProfile
'''
This template will only ever be used inside ArchiveSub
'''
class ArchiveMessageTemplate(MessageTemplates):
    @staticmethod
    def get_server_archive_embed(guild:Guild, description: str, color:int=0xffffff):
        '''Create an embed that sums up the server archive information for this server.'''
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
        #Ignored channels go into mentions becuase there will be *alot* of them.
        embed=Embed(title=guild.name, description=f'ignored channels:{mentions}', color=Color(color))
        embed.add_field(name="Archive Channel",value=aid)
        embed.add_field(name="Last Archive Date",
                        value=last_date)

        embed.add_field(name="Result",value=description, inline=False)
        
        embed.add_field(name="Archive Details",value=profile.get_details(), inline=True)
        autoval=""
        tasks=["COMPILE","LAZYARCHIVE"]
        for t in tasks:
            autoentry=TCGuildTask.get(guild.id,t)
            if autoentry:
                res=autoentry.get_status_desc()
                if res: 
                    autoval+=t+":"+res+'\n'
        if autoval:
            embed.add_field(name="Automatic Task Data",value=autoval)
        embed.set_thumbnail(url=guild.icon)
        embed.set_author(name="Server RP Archive System",icon_url=AssetLookup.get_asset('embed_icon'))
        embed.set_footer(text=f"Server ID: {guild.id}")
        return embed

    @staticmethod
    async def server_archive_message(ctx:commands.Context, description: str, **kwargs):
        '''Create an embed'''
        hex=await get_server_icon_color(ctx.guild)
        embed=ArchiveMessageTemplate.get_server_archive_embed(ctx.guild, description, color=hex)
        await ctx.send(embed=embed,**kwargs)
