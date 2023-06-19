from typing import List, Literal
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
from bot import TC_Cog_Mixin, TCBot
from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import serverAdmin, serverOwner, load_manual, MessageTemplates
from utility.embed_paginator import pages_of_embeds

from assets import AssetLookup
from discord.app_commands import AppCommand
from database import Users_DoNotTrack
''''''



    
class Setup(commands.Cog, TC_Cog_Mixin):
    """The component where you enable/disable other components."""
    def __init__(self, bot):
        self.helptext="This section is for enabling and disabling specific bot features for your server."
        self.bot:TCBot=bot
        self.bot.add_act("WatchExample"," This space for rent.",discord.ActivityType.watching)
        self.bot.add_act("WatchExample2"," My prefix is '>'.",discord.ActivityType.watching)
        self.bot.add_act("listen"," webcore music.",discord.ActivityType.listening)

    nikkisetup = app_commands.Group(name="nikkisetup", description="Some general commands for helping with setting up your server.")
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        bot=self.bot

        await bot.tree.sync(guild=guild)
        if guild.system_channel!=None:
            await guild.system_channel.send("Hi, thanks for inviting me to your server!  I hope to be of use!\n"+ \
                "Please understand that some of my features may require additional permissions.  \n"+
                "I'll try to let you know which ones are needed and when.")

    @nikkisetup.command(name="app_permmission_info", description="learn how to set up my app commands!")
    async def info(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        pages=await MessageTemplates.get_manual_list(ctx,"nikki_setup_manual.json")
        await pages_of_embeds(ctx,pages,ephemeral=True)

    @app_commands.command(name="add_ticker", description="Owner Only, add a command to the ticker.", extras={"homeonly":True})
    @app_commands.describe(name='the name of the ticker entry')
    @app_commands.describe(text='the text of the ticker entry')
    #@app_commands.guilds(discord.Object(id=AssetLookup.get_asset('homeguild')))
    async def add_ticker(self, interaction: discord.Interaction, name:str, text:str) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        bot=ctx.bot
        bot.add_act(name,text,discord.ActivityType.playing)
        await ctx.send("done",ephemeral=True)


    @nikkisetup.command(name="permissions", description="get links for re-authenticating my permissions")
    async def perms(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        
        pages=await MessageTemplates.get_manual_list(ctx,"nikki_permissions_manual.json")
        await pages_of_embeds(ctx,pages,ephemeral=True)
    
    @nikkisetup.command(name="get_tree_json", description="return a JSON representation of my command tree for this server")
    async def mytree(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        if not ctx.guild:
            await ctx.send("you can only use this in a guild.")
            return
        await ctx.send("Getting tree...")
        treedict=await ctx.bot.get_tree_dict(ctx.guild)
        await ctx.send("Tree retrieved.")
        file_object = io.StringIO()
        json.dump(treedict, file_object, indent=4, sort_keys=True,default=str)
        file_object.seek(0)
        await ctx.send(file=discord.File(file_object, filename="yourtree.json"))


    @app_commands.command(name='usersettings_ignore_me',
                           description="WORK IN PROGRESS: USE THIS COMMAND IF YOU WANT ME TO IGNORE YOU.",
                           extras={"nocheck":True})
    @app_commands.describe(condition="set this to on if you want me to listen to you, ignore if you want me to ignore you, .")
    async def ignoreme(self, interaction: discord.Interaction, condition:Literal['on','off']='on') -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        user=interaction.user
        if condition=='on':
            if Users_DoNotTrack.check_entry(user.id):
                result=Users_DoNotTrack.delete_entry(user.id,'self')
                if result:
                    await ctx.send("Okay!  I'll stop ignoring you.",ephemeral=True)
                else:
                    await ctx.send("I'm sorry, but it appears I can't respond due to an administrative override.",ephemeral=True)
            else:
                await ctx.send("But I'm not ignoring you!",ephemeral=True)
        else:
            if Users_DoNotTrack.check_entry(user.id):
                await ctx.send("I'm already ignoring you.",ephemeral=True)
            else:
                Users_DoNotTrack.add_entry(user.id,'self')
                await ctx.send("Understood.  I will start ignoring you.",ephemeral=True)
        
        

    @commands.command()
    @commands.is_owner()
    async def syncall(self,ctx):
        await ctx.send("Syncing...")
        await ctx.bot.all_guild_startup(True)
        await ctx.send("DONE.")

    @commands.hybrid_command(name='getapps',description="get all my app commands for this server, and check if you set any specific overrides.")
    async def get_apps(self,ctx):
        if not ctx.guild:
            await ctx.send("This command is a guild only command.")
        my_tree:discord.app_commands.CommandTree=ctx.bot.tree
        mycommsfor=await my_tree.fetch_commands(guild=discord.Object(ctx.guild.id))
        embed_list=[]
        for appcommand in mycommsfor:
            embed=discord.Embed(title=appcommand.name,description=appcommand.description)
            try:
                guild_perms=await appcommand.fetch_permissions(guild=discord.Object(ctx.guild.id))
                for perm in guild_perms.permissions:
                    type=perm.type #AppCommandPermissionType
                    if type==discord.AppCommandPermissionType.channel:
                        if perm.id==(ctx.guild.id-1):
                            embed.add_field(
                                name="ALL CHANNELS:",value=str(perm.permission))
                        else:
                            embed.add_field(
                                name=f"Channel perm",
                                value=f"<#{perm.id}>, {perm.permission}"
                            )
                    if type==discord.AppCommandPermissionType.role:
                        embed.add_field(
                                name=f"Role perm",
                                value=f"<@&{perm.id}>, {perm.permission}"
                            )
                    if type==discord.AppCommandPermissionType.user:
                        embed.add_field(
                                name=f"User perm",
                                value=f"<@{perm.id}>, {perm.permission}"
                            )
            except Exception as e:
                embed.add_field(
                    name=f"NO PERMS SET",
                    value=f"No permissions where set."
                )
            embed_list.append(embed)
        if ctx.interaction:
            await pages_of_embeds(ctx,embed_list, ephemeral=True)
        else:
            await pages_of_embeds(ctx,embed_list)
                #gui.gprint(type.name)

            



        


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
            channels= [c for c in channels_part1 \
                if c.type == discord.ChannelType.category or c.category_id not in categories]

            channel_mentions = [channel.mention for channel in channels[:max_channels]]
            if len(channels) > max_channels:
                channel_mentions.append(f"and {len(channels) - max_channels} more...")
            formattedstring= ", ".join(channel_mentions)
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
