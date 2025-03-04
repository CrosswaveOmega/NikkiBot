from database import ServerArchiveProfile
from discord import Embed, Color, Guild, ChannelType
from discord.ext import commands

from utility import MessageTemplates, get_server_icon_color
from bot import TCGuildTask
from assetloader import AssetLookup

upper_ignore_limit = 50
upper_cat_limit = 10

"""
This template will only ever be used inside ArchiveSub
"""


class ArchiveMessageTemplate(MessageTemplates):
    @staticmethod
    def get_server_archive_embed(guild: Guild, description: str, color: int = 0xFFFFFF):
        """Create an embed that sums up the server archive information for this server."""
        profile = ServerArchiveProfile.get(
            guild.id
        )  # Retrieve the archive profile using the guild ID
        if not profile:
            embed = Embed(
                title=guild.name,
                description=f"Server RP Archive System is unset in this server.",
                color=Color(color),  # Creating the embed
            )

            embed.add_field(
                name="Result", value=description, inline=False
            )  # Add description of the result

            embed.set_author(
                name="Server RP Archive System",
                icon_url=AssetLookup.get_asset(
                    "embed_icon"
                ),  # Set author with special icon
            )
            return embed
        clist, mentionlist, catlist = (
            [],
            [],
            [],
        )  # Initialize lists for storing channels and categories
        aid, mentions, cattext = (
            "NOT SET",
            "No ignored channels",
            "",
        )  # Initialize default values for display
        hist_channel = (
            profile.history_channel_id
        )  # Get the history channel ID from the profile
        last_date = "Never compiled"  # Default message if no archive has been compiled
        if profile.last_archive_time:  # Check if there is a recorded last archive time
            timestamped = (
                profile.last_archive_time.timestamp()
            )  # Convert last archive time to a timestamp
            last_date = f"<t:{int(timestamped)}:f>"  # Format the last date as a Discord timestamp
        if hist_channel:  # If a history channel ID is provided
            aid = f"<#{hist_channel}>"  # Format history channel ID as a mention
        clist = profile.list_channels()  # List of channels from the profile
        rc = 0  # Variable to count non-existent channels
        if clist:  # If there are channels listed
            filtered = [
                guild.get_channel(ment)
                for ment in clist
                if guild.get_channel(ment)
                != None  # Filter out channels that still exist
            ]
            rc = len(
                [
                    guild.get_channel(ment)
                    for ment in clist
                    if guild.get_channel(ment)
                    == None  # Count channels that do not exist anymore
                ]
            )
            mentionlist = [
                f"<#{ment.id}>"
                for ment in filtered
                if ment.type != ChannelType.category  # Separate non-category channels
            ]
            catlist = [
                f"<#{ment.id}>"
                for ment in filtered
                if ment.type == ChannelType.category  # Separate category channels
            ]
            mentions = ",".join(
                mentionlist[:upper_ignore_limit]
            )  # Combine mentions up to limit
            cattext = ",".join(
                catlist[:upper_cat_limit]
            )  # Combine category mentions up to limit
        if len(mentionlist) > upper_ignore_limit:  # If mention list exceeds limit
            mentions += f" and {len(mentionlist) - upper_ignore_limit} more!"  # Add extra number
        if len(catlist) > upper_cat_limit:  # If category list exceeds limit
            cattext += (
                f" and {len(catlist) - upper_ignore_limit} more!"  # Add extra number
            )
        ments = f"Ignoring {len(mentionlist)} Channels:{mentions}\n"[
            :3000
        ]  # Final mentions message with new limit
        cats = f"Ignoring {len(catlist)} Categories:{cattext}\n"[
            :1000
        ]  # Final category message with new limit
        if len(catlist) <= 0:  # No categories to display
            cats = ""
        if len(mentionlist) <= 0:  # No channels to display
            ments = "No ignored channels."
        removeif = ""
        if rc > 0:  # If there are non-existent channels or categories
            removeif = f"# {rc} CHANNEL/CATEGORIES IN IGNORE LIST WHERE DELETED.\n"  # Note about deletion
        embed = Embed(
            title=guild.name,
            description=f"{removeif}{ments}{cats}",
            color=Color(color),  # Creating the embed
        )
        embed.add_field(
            name="Archive Channel", value=aid
        )  # Add history channel to embed
        embed.add_field(
            name="Last Archive Date", value=last_date
        )  # Add last archive date to embed

        embed.add_field(
            name="Result", value=description, inline=False
        )  # Add description of the result

        embed.add_field(
            name="Archive Details",
            value=profile.get_details(),
            inline=True,  # Add detailed archive results
        )
        autoval = ""
        tasks = ["COMPILE", "LAZYARCHIVE"]  # Set automatic tasks
        for t in tasks:  # For each task in the list
            autoentry = TCGuildTask.get(guild.id, t)  # Get the task entry
            if autoentry:
                res = autoentry.get_status_desc()  # Get task status description
                if res:
                    autoval += t + ":" + res + "\n"  # Combine task info into value
        if autoval:  # If there is automatic task data
            embed.add_field(name="Automatic Task Data", value=autoval)  # Add to embed
        embed.set_thumbnail(url=guild.icon)  # Set guild icon as thumbnail
        embed.set_author(
            name="Server RP Archive System",
            icon_url=AssetLookup.get_asset(
                "embed_icon"
            ),  # Set author with special icon
        )
        embed.set_footer(text=f"Server ID: {guild.id}")  # Add server ID in footer
        return embed  # Return the fully constructed embed

    @staticmethod
    async def server_archive_message(ctx: commands.Context, description: str, **kwargs):
        """Create an embed"""
        # hex = await get_server_icon_color(ctx.guild)
        embed = ArchiveMessageTemplate.get_server_archive_embed(
            ctx.guild,
            description,
        )
        await ctx.send(embed=embed, **kwargs)
