import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv
#import datetime
from datetime import datetime, timedelta

from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook,ui
from bot import TCMixin, TCBot
from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import serverAdmin, serverOwner
from utility.embed_paginator import pages_of_embeds
''''''



class HelpSelect(discord.ui.Select):
    def __init__(self,myhelp):
        self.myhelp=myhelp
        ctx = self.myhelp.context
        bot = ctx.bot
        self.cogs = bot.cogs
        options=[]
        for i, v in self.cogs.items():
            options.append(discord.SelectOption(label=v.qualified_name,description="This is cog {}".format(v.qualified_name)))
           
            print(i)

        super().__init__(placeholder="Select a cog",max_values=1,min_values=1,options=options)
    async def callback(self, interaction: discord.Interaction):
        value=self.values[0]
        
        for i, v in self.cogs.items():
            if value==v.qualified_name:
                myembed=await self.myhelp.get_cog_help_embed(v)
                await interaction.response.edit_message(content="showing cog help",embed=myembed)

class SelectView(discord.ui.View):
    def __init__(self, *, timeout = 180, myhelp=None):
        super().__init__(timeout=timeout)
        self.add_item(HelpSelect(myhelp))



class SetupCommands(app_commands.Group):
    pass
class Setup(commands.Cog, TCMixin):
    """The component where you enable/disable other components."""
    def __init__(self, bot):
        self.helptext="This section is for enabling and disabling specific bot features for your server."
        self.bot:TCBot=bot
        self.bot.add_act("WatchExample"," This space for rent.",discord.ActivityType.watching)
        self.bot.add_act("WatchExample2"," My prefix is '>'.",discord.ActivityType.watching)


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        bot=self.bot

        await bot.tree.sync(guild=guild)
        if guild.system_channel!=None:
            await guild.system_channel.send("Hi, thanks for inviting me to your server!  I hope to be of use!\n"+ \
                "Please understand that some of my features may require additional permissions. I'll try to let you know which ones are needed and when.")

    @commands.command()
    async def syncall(self,ctx):
        await ctx.send("Syncing...")
        await ctx.bot.all_guild_startup(True)
        await ctx.send("DONE.")
    
    @commands.hybrid_command(name='perm_check',description="check the bot permissions for this server or another.")
    async def permission_check(self,ctx, guild_id:int=0):
        # Get the bot member object for this guild or the passed in guild_id
        if guild_id==0:
            guild_id=ctx.guild.id
        guild=ctx.bot.get_guild(guild_id)
        bot_member = await guild.fetch_member(ctx.bot.user.id)

        # Print the permissions for the bot in this guild
        permissions = bot_member.guild_permissions
        permissions=str(permissions)
        await ctx.send(f"Permissions for {ctx.bot.user.name} in {guild.name}:\n{permissions}\n")
                # Print the names of all permissions for the bot in this guild
        allowed_perms = []
        denied_perms = []
        for perm, value in bot_member.guild_permissions:
            if value:
                allowed_perms.append(perm)
            else:
                denied_perms.append(perm)
        await ctx.send("Allowed Permissions: ")
        perms="\n".join([f'- {perm}' for perm in allowed_perms])
        await ctx.send(perms)
        await ctx.send("Denied Permissions: ")
        perms="\n".join([f'- {perm}' for perm in denied_perms])
        await ctx.send(perms)
    def compare_tuples(self,list1, list2):
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
        stringval=""
        for group_key in sorted(groups.keys()):
            num, name = group_key
            stringval+=f"\n{num} ({name}):\n"
            allow=",".join([f"`{i}`" for i, e in sorted(groups[group_key]) if e=='allow'])
            deny=",".join([f"`{i}`" for i, e in sorted(groups[group_key]) if e=='deny'])
            if allow:  stringval+=f"**allowed:**{allow}\n"
            if deny:   stringval+=f"**denied:**{deny}\n"
        if len(stringval)>4025:
            stringval=stringval[:4020]+"...\n There are too many overwrites here for me to list!"
        return stringval

    @commands.hybrid_command(name='permission_sleuth',description="Investigate permissions for user.")
    @app_commands.describe(user="The user to evaluate permissions for.")
    async def permissionsleuth(self,ctx, user:discord.User):
        """Sometimes, people go overboard with discord permissions and turn their servers into something crazy.
          This command figures out if they have.
        Args:
            user (discord.User): user to investigate permissions for.

        """        
        guild = ctx.guild

        member = await guild.fetch_member(user.id)
        global_perms = member.guild_permissions
        resolved_global_permission_list=[(i,v) for i, v in global_perms]
        resolved_global_permissions={}
        for i, v in global_perms:
            resolved_global_permissions[i]=v
        role_permissions = {}

        for role in member.roles:
            role_name = role.name
            permissions = role.permissions
            for perm, val in permissions:
                if val:
                    if not perm in role_permissions:
                        role_permissions[perm]=[]
                    role_permissions[perm].append(role_name)

        def are_equal(list1,list2):
            #Just check if there are unique tuples in the two lists.
            common,unique=self.compare_tuples(list1,list2)
            if len(unique)>0:
                return False
            return True

        def format_channel_mentions(channels_part1, max_channels=10):
            #Format channel mentions, simplify by removing categories.
            categories = [c.id for c in channels_part1 if c.type == discord.ChannelType.category]
            print(categories)
            channels= [c for c in channels_part1 \
                if c.type == discord.ChannelType.category or c.category_id not in categories]

            channel_mentions = [channel.mention for channel in channels[:max_channels]]
            if len(channels) > max_channels:
                channel_mentions.append(f"and {len(channels) - max_channels} more...")
            formattedstring= ", ".join(channel_mentions)
            print(formattedstring)
            return formattedstring


        channel_groups = {}
        for channel in guild.channels:
            channel_overrides = await self.check_overwrites(guild, user, member, channel)
            channel_permissions = channel.permissions_for(member)
            resolved_permissions=[(i,v) for i, v in channel_permissions]
            #To simplify output, grouping is preformed.
            found_group = False
            for group_id, group_channels in channel_groups.items():
                if are_equal(channel_overrides, group_channels[0][1]):
                    group_channels.append((channel, channel_overrides, resolved_permissions))
                    found_group = True
                    break
            if not found_group:
                group_id = len(channel_groups) + 1
                channel_groups[group_id] = [(channel, channel_overrides, resolved_permissions)]
        allow=",".join([f"`{i}({len(e)})`" for i, e in role_permissions.items()])
        deny=",".join([i for i, e in resolved_global_permission_list if e==False])
        embeds = []
        
        globals=f"Global Permissions:\n **Granted:**\n{allow}\n**Deny:**\n{deny}"
        globals=f"Global Permissions:\n **Granted:**\n{allow}\n**Deny:**\n{deny}"
        embed = discord.Embed(
            title=f"Sleuth results: {len(channel_groups.keys())} Pages", 
            description=globals, color=0x00ff00)
        embeds.append(embed)
        for group_id, group_channels in channel_groups.items():
            resolved_overrides = group_channels[0][1]
            channel_list=[]
            for m in group_channels:
                c,cover,res=m
                channel_list.append(c)
            channelgrouplisting=format_channel_mentions(channel_list)
            output=self.format_resolved_permissions(resolved_overrides)
            allow=",".join([i for i, e in resolved_permissions if e==True and (resolved_global_permissions[i]!=e)])
            deny=",".join([i for i, e in resolved_permissions if e==False and (resolved_global_permissions[i]!=e)])

            embed = discord.Embed(title=f"Group: {group_id}", description=output, color=0x00ff00)
            embed.add_field(name="Channels", value=f"{channelgrouplisting}"[:1020],inline=False)
            if allow:
                embed.add_field(name="Allowed Now", value=allow)
            if deny:
                embed.add_field(name="Denied Now", value=deny)
            embeds.append(embed)
        if ctx.interaction:
            await pages_of_embeds(ctx,embeds, ephemeral=True)
        else:
            await pages_of_embeds(ctx,embeds)


    async def check_overwrites(self,guild: discord.Guild, user: discord.User, member: discord.Member, channel: discord.abc.GuildChannel):
        overwrite_reasons = []

        def get_sub_overwrite_list(overwrite, num, typev, name):
            value_list = []
            allow, deny = overwrite.pair()
            for perm, value in allow:
                if value:
                    value_list.append((num, perm, typev, name, 'allow'))
            for perm, value in deny:
                if value:
                    value_list.append((num, perm, typev, name, 'deny'))
            return value_list

        everyone_overwrite = channel.overwrites_for(guild.default_role)
        if not everyone_overwrite.is_empty():
            overwrite_reasons += get_sub_overwrite_list(everyone_overwrite, 1, 'at_everyone', 'everyone')

        for role in member.roles:
            if role.name!="@everyone":
                role_overwrite = channel.overwrites_for(role)
                if role_overwrite.is_empty():
                    continue
                overwrite_reasons += get_sub_overwrite_list(role_overwrite, 2, 'role', (role.name).replace("@",""))

        user_overwrite = channel.overwrites_for(user)
        if not user_overwrite.is_empty():
            overwrite_reasons += get_sub_overwrite_list(user_overwrite, 3, 'user', user.name)

        return overwrite_reasons






async def setup(bot):
    await bot.add_cog(Setup(bot))
