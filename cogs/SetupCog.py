from typing import Literal
import discord
import io
import json

# import datetime


from discord.ext import commands
from bot import TC_Cog_Mixin, TCBot, GuildCogToggle
from discord import app_commands
from database.database_singleton import DatabaseSingleton
from utility import (
    MessageTemplates,
    urltomessage,
)
from utility.embed_paginator import pages_of_embeds

from database import Users_DoNotTrack
import gui

""""""


class Setup(commands.Cog, TC_Cog_Mixin):
    """This Cog is for bot help and configuration"""

    def __init__(self, bot):
        self.helptext = "This section is for enabling and disabling specific bot features for your server."
        self.bot: TCBot = bot
        self.bot.add_act(
            "WatchExample",
            " /nikkifeedback if you have a suggestion.",
            discord.ActivityType.watching,
        )
        self.bot.add_act("WatchExample2", "Prefix:'>'.", discord.ActivityType.watching)

    def server_profile_field_ext(self, guild: discord.Guild):
        features = guild.features
        if features:
            value = ""
            for f in features:
                value += f"- {f}\n"
            field = {"name": "Feature Map", "value": value, "inline": False}
            return field
        return None

    nikkisetup = app_commands.Group(
        name="nikkisetup",
        description="Some general commands for helping with setting up your server.",
        default_permissions=discord.Permissions(
            manage_channels=True, manage_messages=True, manage_roles=True
        ),
    )

    ticker = app_commands.Group(
        name="ticker", description="Commands for the ticker.", extras={"homeonly": True}
    )

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        bot = self.bot
        await bot.tree.sync(guild=guild)
        if guild.system_channel != None:
            try:
                await guild.system_channel.send(
                    "Hi, thanks for inviting me to your server!  I hope to be of use!\n"
                    + "Please understand that some of my features may require additional permissions.  \n"
                    + "I'll try to let you know which ones are needed and when.\n"
                    + "Starting application command sync..."
                )
            except Exception as e:
                gui.gprint(e)
        await self.bot.sync_one_guild(guild=guild, force=True)
        if guild.system_channel != None:
            try:
                await guild.system_channel.send("Sync complete!")
            except Exception as e:
                gui.gprint(e)

    @nikkisetup.command(
        name="app_permission_info",
        description="learn how to restrict access to my commands.",
    )
    async def info(self, interaction: discord.Interaction) -> None:
        """Display a manual about changing the permission overrides for the bot's app commands."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        pages = await MessageTemplates.get_manual_list(
            ctx, "nikki_ac_perm_overrides.json"
        )
        await pages_of_embeds(ctx, pages, ephemeral=True)

    @nikkisetup.command(
        name="permissions", description="get links for re-authenticating my permissions"
    )
    async def perms(self, interaction: discord.Interaction) -> None:
        """Return a manual that has a few oath2 links for server owners to quickly change Nikki's permissons with."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        pages = await MessageTemplates.get_manual_list(
            ctx, "nikki_permission_links.json"
        )
        await pages_of_embeds(ctx, pages, ephemeral=True)

    @nikkisetup.command(
        name="toggle_cog", description="Enable/disable any of my features."
    )
    @app_commands.describe(cogname="the name of the cog to toggle on or off")
    async def cogtoggle(self, interaction: discord.Interaction, cogname: str) -> None:
        """Open a view where you can configure Nikki's features."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        # profile = AppGuildTreeSync.get(server_id=ctx.guild.id)
        # list = AppGuildTreeSync.load_list(server_id=ctx.guild.id)
        # onlist = AppGuildTreeSync.load_onlist(server_id=ctx.guild.id)
        if cogname.lower() == "setup":
            await ctx.send("you can't disable setup, sorry", ephemeral=True)
            return
        if ctx.bot.get_cog(cogname) is not None:
            cog = ctx.bot.get_cog(cogname)
            entry = GuildCogToggle.get_or_add(ctx.guild.id, cog)
            manual = private = False
            if hasattr(cog, "globalonly"):
                if cog.globalonly:
                    await ctx.send(
                        "This is a global cog, you will need to disable these commands in my integration menu!",
                        ephemeral=True,
                    )
                    return
            if hasattr(cog, "manual_enable"):
                manual = cog.manual_enable
            if manual:
                if hasattr(cog, "private"):
                    private = cog.private

                if entry.enabled:
                    entry.enabled = False
                    GuildCogToggle.edit(ctx.guild.id, cog, False)
                    await ctx.send(
                        f"I will not sync cog {cogname} here.", ephemeral=True
                    )
                else:
                    if private:
                        if ctx.author.id != ctx.bot.application.owner.id:
                            await ctx.send(f"{cogname} is owner only.", ephemeral=True)
                            return
                    entry.enabled = True
                    GuildCogToggle.edit(ctx.guild.id, cog, True)
                    await ctx.send(f"I will sync cog {cogname} here.", ephemeral=True)
                # profile.save_onlist(onlist)
                self.bot.database.commit()
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.all_guild_startup()
            else:
                gui.gprint(entry, entry.enabled)
                if not entry.enabled:
                    # entry.enabled = True
                    GuildCogToggle.edit(ctx.guild.id, cog, True)
                    await ctx.send(
                        f"I will once again sync cog {cogname} here.", ephemeral=True
                    )
                else:
                    # entry.enabled = False
                    GuildCogToggle.edit(ctx.guild.id, cog, False)
                    await ctx.send(
                        f"I will no longer sync cog {cogname} here.", ephemeral=True
                    )
                    DatabaseSingleton.get_session().commit()
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.all_guild_startup()
        else:
            await ctx.send("That cog does not exist!", ephemeral=True)

    @ticker.command(
        name="add",
        description="Owner Only, add a string to the ticker.",
        extras={"homeonly": True},
    )
    @app_commands.describe(name="the name of the ticker entry")
    @app_commands.describe(text="the text of the ticker entry")
    async def add_ticker(
        self, interaction: discord.Interaction, name: str, text: str
    ) -> None:
        """add a new rotating status to Nikki's 'news ticker.'"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        bot = ctx.bot
        bot.add_act(name, text, discord.ActivityType.playing)
        await ctx.send("Ticker added.", ephemeral=True)

    @ticker.command(
        name="view", description="view all tickers", extras={"homeonly": True}
    )
    async def view_ticker(self, interaction: discord.Interaction) -> None:
        """Debug, display all rotating statuses on the news ticker."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        bot = ctx.bot
        lines = []

        for i, v in bot.status_map.items():
            st = f"{i}:{v.name}"
            lines.append(st)
        joined_list = []
        for i in range(0, len(lines), 10):
            joined_list.append("\n".join(lines[i : i + 10]))
        for l in joined_list:
            await ctx.send(l)

    @nikkisetup.command(
        name="get_tree_json",
        description="return a JSON representation of my command tree for this server",
    )
    async def mytree(self, interaction: discord.Interaction) -> None:
        """This is for debugging, it returns a json representation of a server's app command tree."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        if not ctx.guild:
            await ctx.send("you can only use this in a guild.")
            return
        await ctx.send("Getting tree...")
        treedict = await ctx.bot.get_tree_dict(ctx.guild)
        await ctx.send("Tree retrieved.")
        file_object = io.StringIO()
        json.dump(treedict, file_object, indent=4, sort_keys=True, default=str)
        file_object.seek(0)
        await ctx.send(file=discord.File(file_object, filename="yourtree.json"))

    @app_commands.command(
        name="usersettings_ignore_me",
        description="WORK IN PROGRESS: USE THIS COMMAND IF YOU WANT ME TO IGNORE YOU.",
        extras={"nocheck": True},
    )
    @app_commands.describe(
        condition="set this to on if you want me to listen to you, ignore if you want me to ignore you."
    )
    async def ignoreme(
        self, interaction: discord.Interaction, condition: Literal["on", "off"] = "on"
    ) -> None:
        """Using this command makes it so the bot will never respond to a user for any reason, if they wish to be ignored."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        user = interaction.user
        if condition == "on":
            if Users_DoNotTrack.check_entry(user.id):
                result = Users_DoNotTrack.delete_entry(user.id, "self")
                if result:
                    await ctx.send("Okay!  I'll stop ignoring you.", ephemeral=True)
                else:
                    await ctx.send(
                        "I'm sorry, but it appears I can't respond due to an administrative override.",
                        ephemeral=True,
                    )
            else:
                await ctx.send("But I'm not ignoring you!", ephemeral=True)
        else:
            if Users_DoNotTrack.check_entry(user.id):
                await ctx.send("I'm already ignoring you.", ephemeral=True)
            else:
                Users_DoNotTrack.add_entry(user.id, "self")
                await ctx.send(
                    "Understood.  I will start ignoring you.", ephemeral=True
                )

    @commands.command()
    @commands.is_owner()
    async def syncall(self, ctx):
        """Sync my app commands.  Owner only."""
        await ctx.send("Syncing...")
        await ctx.bot.all_guild_startup(True)
        await ctx.send("DONE.")

    @commands.command()
    @commands.is_owner()
    async def purge_messages(
        self, ctx: commands.Context, afterurl: str, beforeurl: str
    ):
        m1 = await urltomessage(afterurl, ctx.bot)
        m2 = await urltomessage(beforeurl, ctx.bot)

        if not m1:
            await ctx.send("Invalid after message link.")
            return
        if not m2:
            await ctx.send("Invalid before message link.")
            return

        if m1.channel != m2.channel:
            await ctx.send("Messages must be in the same channel")
            return

        # Ensure messages are no older than 2 weeks
        if (discord.utils.utcnow() - m1.created_at).days > 14 or (
            discord.utils.utcnow() - m2.created_at
        ).days > 14:
            await ctx.send("Messages must be sent within the last 2 weeks")
            return

        channel = m1.channel
        if not channel.permissions_for(ctx.guild.me).manage_messages:
            await ctx.send("I do not have manage_messages permission in this channel.")
            return

        cont, mess = await MessageTemplates.confirm(
            ctx,
            "Initiate purge\nAfter message timestamp: {m1.created_at}\nBefore message timestamp: {m2.created_at}\nAre you sure you want to continue?",
            False,
        )

        await mess.delete()
        if not cont:
            await ctx.send("Purge Operation aborted.")
            return

        deleted = await channel.purge(
            before=discord.Object(m2.id),
            after=discord.Object(m1.id),
            oldest_first=False,
            limit=1000,
        )
        await ctx.channel.send(f"Purged {len(deleted)} message(s)")

    @commands.hybrid_command(
        name="getapps",
        description="get all my app commands for this server, and check if you set any specific overrides.",
    )
    @commands.guild_only()
    async def get_apps(self, ctx):
        """List all App Commands synced in a server."""
        if not ctx.guild:
            await ctx.send("This command is a guild only command.")
        my_tree: discord.app_commands.CommandTree = ctx.bot.tree
        mycommsfor = await my_tree.fetch_commands(guild=discord.Object(ctx.guild.id))
        embed_list = []
        for appcommand in mycommsfor:
            embed = discord.Embed(
                title=appcommand.name, description=appcommand.description
            )
            try:
                guild_perms = await appcommand.fetch_permissions(
                    guild=discord.Object(ctx.guild.id)
                )
                for perm in guild_perms.permissions:
                    type = perm.type  # AppCommandPermissionType
                    if type == discord.AppCommandPermissionType.channel:
                        if perm.id == (ctx.guild.id - 1):
                            embed.add_field(
                                name="ALL CHANNELS:", value=str(perm.permission)
                            )
                        else:
                            embed.add_field(
                                name="Channel perm",
                                value=f"<#{perm.id}>, {perm.permission}",
                            )
                    if type == discord.AppCommandPermissionType.role:
                        embed.add_field(
                            name="Role perm", value=f"<@&{perm.id}>, {perm.permission}"
                        )
                    if type == discord.AppCommandPermissionType.user:
                        embed.add_field(
                            name="User perm", value=f"<@{perm.id}>, {perm.permission}"
                        )
            except Exception:
                embed.add_field(name="NO PERMS SET", value="No permissions where set.")
            embed_list.append(embed)
        if ctx.interaction:
            await pages_of_embeds(ctx, embed_list, ephemeral=True)
        else:
            await pages_of_embeds(ctx, embed_list)
            # gui.gprint(type.name)

    @commands.hybrid_command(
        name="perm_check",
        description="check the bot permissions for this server or another.",
    )
    async def permission_check(self, ctx, guild_id: int = 0):
        "DEBUG: check the bot permissions for this server."
        # Get the bot member object for this guild or the passed in guild_id
        if guild_id == 0:
            guild_id = ctx.guild.id
        else:
            if ctx.author.id != ctx.bot.application.owner.id:
                await ctx.send(
                    "This is for my owner only, to help when something is wrong."
                )
                return
        guild = ctx.bot.get_guild(guild_id)
        bot_member = await guild.fetch_member(ctx.bot.user.id)

        # Print the permissions for the bot in this guild
        permissions = bot_member.guild_permissions
        permissions = str(permissions)
        await ctx.send(
            f"Permissions for {ctx.bot.user.name} in {guild.name}:\n{permissions}\n"
        )
        # Print the names of all permissions for the bot in this guild
        allowed_perms = []
        denied_perms = []
        for perm, value in bot_member.guild_permissions:
            if value:
                allowed_perms.append(perm)
            else:
                denied_perms.append(perm)
        await ctx.send("Allowed Permissions: ")
        perms = "\n".join([f"- {perm}" for perm in allowed_perms])
        await ctx.send(perms)
        await ctx.send("Denied Permissions: ")
        perms = "\n".join([f"- {perm}" for perm in denied_perms])
        await ctx.send(perms)

    def compare_tuples(self, list1, list2):
        """Compare two lists of tuples and return two lists: one with tuples that appear in both lists and one with tuples that appear only in one list."""
        common_tuples = []
        unique_tuples = []
        for tuple1 in list1:
            if tuple1 in list2:
                common_tuples.append(tuple1)
            else:
                unique_tuples.append(tuple1)
        for tuple2 in list2:
            if tuple2 not in common_tuples:
                unique_tuples.append(tuple2)
        return common_tuples, unique_tuples

    def format_resolved_permissions(self, resolved_permissions):
        """format resolved permissions for a particular channel group."""
        groups = {}
        for num, perm, overtype, name, case in resolved_permissions:
            key = (num, name)
            if key not in groups:
                groups[key] = []
            groups[key].append((perm, case))
        stringval = ""
        for group_key in sorted(groups.keys()):
            num, name = group_key
            stringval += f"\n{num} ({name}):\n"
            allow = ",".join(
                [f"`{i}`" for i, e in sorted(groups[group_key]) if e == "allow"]
            )
            deny = ",".join(
                [f"`{i}`" for i, e in sorted(groups[group_key]) if e == "deny"]
            )
            if allow:
                stringval += f"**allowed:**{allow}\n"
            if deny:
                stringval += f"**denied:**{deny}\n"
        if len(stringval) > 4025:
            stringval = (
                stringval[:4020]
                + "...\n There are too many overwrites here for me to list!"
            )
        return stringval

    @commands.hybrid_command(
        name="permission_sleuth",
        description="Investigate permission resolution for user.",
    )
    @app_commands.describe(user="The user to evaluate permissions for.")
    async def permissionsleuth(self, ctx, user: discord.User):
        """Sometimes, people go overboard with discord permissions and
          turn their servers into something crazy.
          This command figures out if there's a problem.
        Args:
            user (discord.User): user to investigate permissions for.

        """
        guild = ctx.guild

        member = await guild.fetch_member(user.id)
        global_perms = member.guild_permissions
        resolved_global_permission_list = [(i, v) for i, v in global_perms]
        resolved_global_permissions = {}
        for i, v in global_perms:
            resolved_global_permissions[i] = v
        role_permissions = {}

        for role in member.roles:
            role_name = role.name
            permissions = role.permissions
            for perm, val in permissions:
                if val:
                    if perm not in role_permissions:
                        role_permissions[perm] = []
                    role_permissions[perm].append(role_name)

        def are_equal(list1, list2):
            # Just check if there are unique tuples in the two lists.
            common, unique = self.compare_tuples(list1, list2)
            if len(unique) > 0:
                return False
            return True

        def format_channel_mentions(channels_part1, max_channels=10):
            # Format channel mentions, simplify by removing categories.
            categories = [
                c.id for c in channels_part1 if c.type == discord.ChannelType.category
            ]
            channels = [
                c
                for c in channels_part1
                if c.type == discord.ChannelType.category
                or c.category_id not in categories
            ]

            channel_mentions = [channel.mention for channel in channels[:max_channels]]
            if len(channels) > max_channels:
                channel_mentions.append(f"and {len(channels) - max_channels} more...")
            formattedstring = ", ".join(channel_mentions)
            return formattedstring

        channel_groups = {}
        for channel in guild.channels:
            channel_overrides = await self.check_overwrites(
                guild, user, member, channel
            )
            channel_permissions = channel.permissions_for(member)
            resolved_permissions = [(i, v) for i, v in channel_permissions]
            # To simplify output, grouping is preformed.
            found_group = False
            for group_id, group_channels in channel_groups.items():
                if are_equal(channel_overrides, group_channels[0][1]):
                    group_channels.append(
                        (channel, channel_overrides, resolved_permissions)
                    )
                    found_group = True
                    break
            if not found_group:
                group_id = len(channel_groups) + 1
                channel_groups[group_id] = [
                    (channel, channel_overrides, resolved_permissions)
                ]
        allow = ",".join([f"`{i}({len(e)})`" for i, e in role_permissions.items()])
        deny = ",".join([i for i, e in resolved_global_permission_list if e == False])
        embeds = []

        globals = f"Global Permissions:\n **Granted:**\n{allow}\n**Deny:**\n{deny}"
        globals = f"Global Permissions:\n **Granted:**\n{allow}\n**Deny:**\n{deny}"
        embed = discord.Embed(
            title=f"Sleuth results: {len(channel_groups.keys())} Pages",
            description=globals,
            color=0x00FF00,
        )
        embeds.append(embed)
        for group_id, group_channels in channel_groups.items():
            resolved_overrides = group_channels[0][1]
            channel_list = []
            for m in group_channels:
                c, cover, res = m
                channel_list.append(c)
            channelgrouplisting = format_channel_mentions(channel_list)
            output = self.format_resolved_permissions(resolved_overrides)
            allow = ",".join(
                [
                    i
                    for i, e in resolved_permissions
                    if e == True and (resolved_global_permissions[i] != e)
                ]
            )
            deny = ",".join(
                [
                    i
                    for i, e in resolved_permissions
                    if e == False and (resolved_global_permissions[i] != e)
                ]
            )

            embed = discord.Embed(
                title=f"Group: {group_id}", description=output, color=0x00FF00
            )
            embed.add_field(
                name="Channels", value=f"{channelgrouplisting}"[:1020], inline=False
            )
            if allow:
                embed.add_field(name="Allowed Now", value=allow)
            if deny:
                embed.add_field(name="Denied Now", value=deny)
            embeds.append(embed)
        if ctx.interaction:
            await pages_of_embeds(ctx, embeds, ephemeral=True)
        else:
            await pages_of_embeds(ctx, embeds)

    async def check_overwrites(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: discord.Member,
        channel: discord.abc.GuildChannel,
    ):
        overwrite_reasons = []

        def get_sub_overwrite_list(overwrite, num, typev, name):
            value_list = []
            allow, deny = overwrite.pair()
            for perm, value in allow:
                if value:
                    value_list.append((num, perm, typev, name, "allow"))
            for perm, value in deny:
                if value:
                    value_list.append((num, perm, typev, name, "deny"))
            return value_list

        everyone_overwrite = channel.overwrites_for(guild.default_role)
        if not everyone_overwrite.is_empty():
            overwrite_reasons += get_sub_overwrite_list(
                everyone_overwrite, 1, "at_everyone", "everyone"
            )

        for role in member.roles:
            if role.name != "@everyone":
                role_overwrite = channel.overwrites_for(role)
                if role_overwrite.is_empty():
                    continue
                overwrite_reasons += get_sub_overwrite_list(
                    role_overwrite, 2, "role", (role.name).replace("@", "")
                )

        user_overwrite = channel.overwrites_for(user)
        if not user_overwrite.is_empty():
            overwrite_reasons += get_sub_overwrite_list(
                user_overwrite, 3, "user", user.name
            )

        return overwrite_reasons


async def setup(bot):
    await bot.add_cog(Setup(bot))
