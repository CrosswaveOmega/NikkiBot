from discord import Embed, Color, Guild, ChannelType
from discord.ext import commands

from utility import MessageTemplates, get_server_icon_color
from bot import TCGuildTask
from assets import AssetLookup

upper_ignore_limit = 50
upper_cat_limit = 10
from database import ServerArchiveProfile

"""
This template will only ever be used inside ArchiveSub
"""


class ArchiveMessageTemplate(MessageTemplates):
    @staticmethod
    def get_server_archive_embed(guild: Guild, description: str, color: int = 0xFFFFFF):
        """Create an embed that sums up the server archive information for this server."""
        profile = ServerArchiveProfile.get_or_new(guild.id)
        mentionlist, catlist = [], []
        aid, mentions, cattext = "NOT SET", "No ignored channels", ""
        hist_channel = profile.history_channel_id
        last_date = "Never compiled"
        if profile.last_archive_time:
            timestamped = profile.last_archive_time.timestamp()
            last_date = f"<t:{int(timestamped)}:f>"
        if hist_channel:
            aid = f"<#{hist_channel}>"
        clist = profile.list_channels()
        rc = 0
        if clist:
            filtered = [
                guild.get_channel(ment)
                for ment in clist
                if guild.get_channel(ment) != None
            ]
            rc = len(
                [
                    guild.get_channel(ment)
                    for ment in clist
                    if guild.get_channel(ment) == None
                ]
            )
            mentionlist = [
                f"<#{ment.id}>"
                for ment in filtered
                if ment.type != ChannelType.category
            ]
            catlist = [
                f"<#{ment.id}>"
                for ment in filtered
                if ment.type == ChannelType.category
            ]
            mentions = ",".join(mentionlist[:upper_ignore_limit])
            cattext = ",".join(catlist[:upper_cat_limit])
        if len(mentionlist) > upper_ignore_limit:
            mentions += f" and {len(mentionlist)-upper_ignore_limit} more!"
        if len(catlist) > upper_cat_limit:
            cattext += f" and {len(catlist)-upper_ignore_limit} more!"
        # Ignored channels go into mentions becuase there will be *alot* of them.
        ments = f"Ignoring {len(mentionlist)} Channels:{mentions}\n"[:3000]
        cats = f"Ignoring {len(catlist)} Categories:{cattext}\n"[:1000]
        if len(catlist) <= 0:
            cats = ""
        if len(mentionlist) <= 0:
            ments = "No ignored channels."
        removeif = f""
        if rc > 0:
            removeif = f"# {rc} CHANNEL/CATEGORIES IN IGNORE LIST WHERE DELETED.\n"
        embed = Embed(
            title=guild.name, description=f"{removeif}{ments}{cats}", color=Color(color)
        )
        embed.add_field(name="Archive Channel", value=aid)
        embed.add_field(name="Last Archive Date", value=last_date)

        embed.add_field(name="Result", value=description, inline=False)

        embed.add_field(
            name="Archive Details", value=profile.get_details(), inline=True
        )
        autoval = ""
        tasks = ["COMPILE", "LAZYARCHIVE"]
        for t in tasks:
            autoentry = TCGuildTask.get(guild.id, t)
            if autoentry:
                res = autoentry.get_status_desc()
                if res:
                    autoval += t + ":" + res + "\n"
        if autoval:
            embed.add_field(name="Automatic Task Data", value=autoval)
        embed.set_thumbnail(url=guild.icon)
        embed.set_author(
            name="Server RP Archive System",
            icon_url=AssetLookup.get_asset("embed_icon"),
        )
        embed.set_footer(text=f"Server ID: {guild.id}")
        return embed

    @staticmethod
    async def server_archive_message(ctx: commands.Context, description: str, **kwargs):
        """Create an embed"""
        hex = await get_server_icon_color(ctx.guild)
        embed = ArchiveMessageTemplate.get_server_archive_embed(
            ctx.guild, description, color=hex
        )
        await ctx.send(embed=embed, **kwargs)
