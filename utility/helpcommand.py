
import asyncio
import itertools
from opcode import hasconst
from random import randint
import gui
import discord
from discord.ext import commands
from discord.ext.commands import Paginator
from discord.ext.commands.help import HelpCommand
from discord import Webhook, ui

from discord import app_commands
from discord.app_commands import Choice


'''
Custom Help Functions
'''

class HelpSelect(discord.ui.Select):
    def __init__(self,myhelp):
        self.myhelp=myhelp
        ctx = self.myhelp.context
        bot = ctx.bot
        self.cogs = bot.cogs
        options=[]
        for i, v in self.cogs.items():
            options.append(discord.SelectOption(label=v.qualified_name,description="This is cog {}".format(v.qualified_name)))
           
            gui.gprint(i)

        super().__init__(placeholder="Select an option",max_values=1,min_values=1,options=options)
    async def callback(self, interaction: discord.Interaction):
        value=self.values[0]
        for option in self.options:
            option.default=False
            if option.value==value:
                option.default=True
        
        for i, v in self.cogs.items():
            if value==v.qualified_name:
                myembed=await self.myhelp.get_cog_help_embed(v)
                await interaction.response.edit_message(content="showing cog help",embed=myembed,view=self.view)

class SelectView(discord.ui.View):
    def __init__(self, *, timeout = 180, myhelp=None):
        super().__init__(timeout=timeout)
        
        cogchunk=discord.utils.as_chunks(myhelp.context.bot.cogs.values(),25)
        for c in cogchunk:
            options=[]
            for v in c:
                options.append(discord.SelectOption(label=v.qualified_name,description="This is cog {}".format(v.qualified_name)))
            self.add_item(HelpSelect(myhelp))

        


class Chelp(HelpCommand):

    def __init__(self, **options):
        super().__init__(**options)

    async def prepare_help_command(self, ctx, command):
        gui.gprint("Help command prepared.")
        await super().prepare_help_command(ctx, command)

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot
        channel = ctx.channel
        gui.gprint("SEND")
        gui.gprint(mapping)
        cogs = bot.cogs
        guild=ctx.message.channel.guild

        
        embed=discord.Embed(title="Help",
        colour=discord.Colour(0x7289da),
        description="All commands.  use ;help [GroupName] for more details. ")
        comcount={}
        for i, v in cogs.items():
            comcount[i]=0
            for comm in v.get_commands():
                if comm.hidden!= True:
                    comcount[i]+=1
        comcount=dict(sorted(comcount.items(), key=lambda item: item[1]))

        for i, ve in comcount.items():
            v=cogs[i]
            gui.gprint(i)
            helpdesc="NO DESCRIPTION!"
            if hasattr(v,"helptext"):
                helpdesc=v.helptext
            elif hasattr(v,"description"):
                helpdesc=v.description
            commands=""
            nameval=v.qualified_name
            commcount=0
            for comm in v.get_commands():
                if comm.hidden!= True:
                    commands=commands + " `{}`".format(comm.name)
                    commcount+=1
            if commands:
                embed.add_field(name="{}-{}".format(nameval,commcount), value=helpdesc, inline=False)
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed,ephemeral=True)
        else:
            mess = await ctx.send(embed=embed,view=SelectView(myhelp=self))

        #await super().send_bot_help(mapping)
    async def send_command_help(self, command):
        ctx = self.context
        gui.gprint(ctx.channel.name)
        bot = ctx.bot
        channel = ctx.channel
        gui.gprint("Fired.")
        embed=discord.Embed(title="Help: {}".format(command.name),
        colour=discord.Colour(0x7289da),
        description="All commands")
        embed.description=command.help
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed,ephemeral=True)
        else:
            mess = await ctx.send(embed=embed)
        await super().send_command_help(command)

    async def send_group_help(self, group):
        gui.gprint("Fired.")
        ctx = self.context
        bot = ctx.bot
        channel = ctx.channel
        embed=discord.Embed(title="Help: {}".format(group.name),
        colour=discord.Colour(0x7289da),
        description="All commands")
        help_val=group.help
        
        embed.add_field(name="Subcommands",value="subcommands below",inline=False)
        for ccomm in group.commands:
            helpname=f"{group.name} {ccomm.name}"
            helpdesc=f"{ccomm.help}\n"
            embed.add_field(name=helpname,value=helpdesc,inline=False)
        embed.description=help_val
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed,ephemeral=True)
        else:
            mess = await ctx.send(embed=embed)
        await super().send_group_help(group)
    async def get_cog_help_embed(self, cog):
        ctx = self.context
        bot = ctx.bot
        channel = ctx.channel
        embed=discord.Embed(title="Help",
        colour=discord.Colour(0x7289da),
        description="Cog_Help")
        gui.gprint(cog)
        commandSTR=""
        embed.title=cog.qualified_name
        addcommands=True
        if hasattr(cog,"helptext"):
             embed.description=str(cog.helptext)
        if hasattr(cog,"helpdesc"):
            embed.description=str(cog.helpdesc)
            addcommands=False
        if addcommands:
            for comm in cog.get_commands():
                if comm.hidden!= True:
                    name_val, help_val=comm.name,comm.help
                    if isinstance(comm, commands.Group): 
                        help_val=comm.help+ "\n"
                        for ccomm in comm.walk_commands():
                            help_val+=f"**{ccomm.full_parent_name} {ccomm.name}** : {ccomm.brief}\n"
                    embed.add_field(name=name_val, value=help_val, inline=False)
                    commandSTR=commandSTR + " `{}`:{}".format(comm.name,comm.help)
        return embed

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot
        embed=await self.get_cog_help_embed(cog)
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed,ephemeral=True)
        else:
            mess = await ctx.send(embed=embed)
        await super().send_cog_help(cog)
