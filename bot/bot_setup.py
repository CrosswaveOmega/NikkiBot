import datetime
from typing import Any
import discord
import traceback
from urllib.request import Request, urlopen
import asyncio
import configparser
import os
from pathlib import Path

import logging
import logging.handlers

import sys, random


from queue import Queue
from utility import serverOwner, serverAdmin,MessageTemplates, relativedelta_sp

from discord.ext import commands, tasks

from discord import Webhook
from subprocess import Popen


from collections import defaultdict
from dateutil.rrule import rrule,rrulestr, WEEKLY, SU
from .TauCetiBot import TCBot
from .Tasks.TCTasks import TCTask, TCTaskManager
from .TcGuildTaskDB import TCGuildTask
"""
Initalizes TCBot, and defines some checks

"""

from database import ServerData
from assets import AssetLookup


bot = TCBot()


taskflags=defaultdict(bool)

async def opening():
    print("OK.")


@bot.check
async def is_cog_enabled(ctx):
    return True

@bot.check
async def guildcheck(ctx):
    if ctx.guild!=None:
        serverdata=ServerData.get_or_new(ctx.guild.id)
        serverdata.update_last_time()
        if ctx.command.extras:
            if 'guildtask' in ctx.command.extras and ctx.guild!=None:
                if taskflags[str(ctx.guild.id)]: 
                    return False
    return True

@bot.on_error
def on_error(event_method: str, /, *args: Any, **kwargs: Any):
    print("Error?")
    log=logging.getLogger('discord')
    log.exception('Ignoring exception AS in %s', event_method)
    try:
        just_the_string=''.join(traceback.format_exc())
        er=MessageTemplates.get_error_embed(title=f"Error with {event_method}",description=f"{just_the_string}")
        asyncio.create_task(bot.send_error_embed(er))
    except:
        print("The error had an error.")



@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError):
    
    logger=logging.getLogger('discord')
    logger.error('Ignoring exception in app command %s', interaction.command.name, exc_info=error)
    ctx=await bot.get_context(interaction)
    if 'guildtask' in ctx.command.extras and ctx.guild!=None:
        taskflags[str(ctx.guild.id)]=False
    await bot.send_error(error,f"App Command {interaction.command.name}")
    await ctx.send(f"This app command failed due to {str(error)}")
    print("ERROR")

@bot.before_invoke
async def add_log(ctx):
    print(f"{ctx.invoked_with},{str(ctx.invoked_parents)}")
    if ctx.command.extras:
         if 'guildtask' in ctx.command.extras and ctx.guild!=None:
             taskflags[str(ctx.guild.id)]=True

    print(f"Firing {ctx.command.name}")

    

@bot.after_invoke
async def free_command(ctx):
    if 'guildtask' in ctx.command.extras and ctx.guild!=None:
        taskflags[str(ctx.guild.id)]=False

    if ctx.command_failed:


        await ctx.send(f"ERROR, {ctx.message.content} failed!  ")
@bot.event
async def on_connect():
    print("Bot connected.")
@bot.event
async def on_disconnect():
    print("Bot disconnected.")

@bot.event
async def on_ready():

    print("Connection ready.")
    await opening()
    print("BOT ACTIVE")
    try:
        if bot.error_channel==-726:
            #Time to make a new guild.
            from .guild_maker import new_guild
            await new_guild(bot)
    except Exception as e:
        print(e)
        await bot.close()

    #audit old guild data.
    await bot.audit_guilds()


    for x in bot.tree.walk_commands():
        print(x.name)
    await bot.after_startup()
    print("Setup done.")

'''
@TCTask(name="my_stask", time_interval=relativedelta_sp(weekday=[TU,WE], hour=9, minute=0))
async def my_coroutines():
    print("Task running at", datetime.now())
    await asyncio.sleep(5)

    print("Task done at", datetime.now())
@TCTask(name="my_task1", time_interval=relativedelta_sp(months='var', day=23, hour=12, minute=5))
async def my_coroutine():
    print("Task running at", datetime.now())
    await asyncio.sleep(5)

    print("Task done at", datetime.now())
'''


class Main(commands.Cog):
    """ debug class, only my owner can use these.
    """
    async def cog_check(self, ctx):
        if ctx.author.id==ctx.bot.application.owner.id:
            return True
        return False
        
    @commands.command(hidden=True)
    async def shutdown(self, ctx):  
        '''
        debug command, shuts the bot down.
        '''
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        
        bot.post_queue_message.cancel()
        bot.delete_queue_message.cancel()
        bot.check_tc_tasks.cancel()

        await ctx.channel.send("Shutting Down")
        
        await ctx.bot.close()
        
    
    @commands.command()
    async def task_view(self, ctx):
        """debugging only."""
        bot=ctx.bot
        guild=ctx.guild
        list=TCTaskManager.task_check()
        chunks = ["\n".join(list[i:i + 10]) for i in range(0, len(list), 10)]
        formatted_strings = ['\n'.join(chunk) for chunk in chunks]
        for i in formatted_strings:
            await ctx.send(i)
            
            
        


    @commands.command()
    async def task_add(self, ctx):
        """debugging only."""
        bot=ctx.bot
        guild=ctx.guild
        message=await ctx.send("Target Message.")
        myurl=message.jump_url
        robj= rrule(
                freq=WEEKLY,
                byweekday=SU,
                dtstart= datetime(2023, 1, 1, 15, 0)
            )
        new=TCGuildTask.add_guild_task(guild.id, "COMPILE",message,robj)
        new.to_task(bot)

    @commands.command()
    async def task_remove(self, ctx):
        """debugging only."""
        return
        bot=ctx.bot
        guild=ctx.guild
        message=await ctx.send("Target Message.")
        myurl=message.jump_url
        robj=relativedelta_sp(minutes=2)
        new=TCGuildTask.remove_guild_task(guild.id, "COMPILE")
        



    @commands.command()
    async def reload(self, ctx):
        """debugging only."""
        bot=ctx.bot
        bot.update_ext_list()
        await bot.reload_all()
        for x in bot.tree.walk_commands():
            print(x.name)
        #await bot.tree.sync()
        print("BOT SYNCED!")
        for x in bot.tree.walk_commands():
            print(x.name)
        embed=discord.Embed(title="Loaded Extensions")
        for i, v in bot.loaded_extensions.items():
            ex,val=v
            embed.add_field(name=i,value=ex,inline=True)
            if val:
                exepemb=discord.Embed(title=f"Error={i}", description=f"{ex}\n{val}")
                await ctx.send(embed=exepemb)
        await ctx.send(embed=embed)
    @commands.command()
    async def view_extend_status(self, ctx):
        """debugging only."""

        bot=ctx.bot
        embed=discord.Embed(title="Loaded Extensions")
        for i, v in bot.loaded_extensions.items():
            ex,val=v
            embed.add_field(name=i,value=ex,inline=True)
            if val:
                print(f"{ex}\n{val}")
                #exepemb=discord.Embed(title=f"Error={i}", description=f"{ex}\n{val}")
                #await ctx.send(embed=exepemb)
        await ctx.send(embed=embed)
    @commands.command()
    async def reload_extend(self, ctx, extname:str):
        """debugging only."""

        bot=ctx.bot

        result=await bot.extension_loader(extname)
        if result=="NOTFOUND":
            await ctx.send("I don't have an extension by that name.")
        elif result=="LOADOK":
            await ctx.send("I reloaded the extension without problems.")
        else:
            embed=discord.Embed(title="Embed Error Extensions")
            v=bot.loaded_extensions[extname]
            ex,val=v
            if val:
                exepemb=discord.Embed(title=f"Error={extname}", description=f"{ex}\n{val}")
                await ctx.send(embed=exepemb)
            else: 
                await ctx.send("...what?")


def setup(args):
    'get or create the config.ini file.'
    arglength=len(args)
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        print("No config.ini file detected.")
        token,error_channel_id='',''
        if arglength >1: token=args[1]
        if arglength >2: error_channel_id=args[2]
        if not token:       
            token = input("Please enter your bot token: ")
        if not error_channel_id: 
            error_channel_id = input("Please enter the ID of the channel to send error messages to, or 'NEWGUILD': ")

        print("No config.ini file detected.")

        config["vital"] = {'cipher': token}
        config["optional"] = {'error_channel_id': error_channel_id}
        print("MAKE SURE TO ADD YOUR ERROR CHANNEL ID!")
        config.write(open('config.ini', 'w'))
        try:
            print("making savedata")
            Path("/saveData").mkdir(parents=True, exist_ok=True) #saveData
        except FileExistsError:
            print("saveData exists already.")
        try:
            print("making logs")
            Path("/logs").mkdir(parents=True, exist_ok=True) #logs
        except FileExistsError:
            print("logs exists already.")
        AssetLookup()
        print("you can restart the bot now.")

        return None

    else:
        # Read File
        config.read('config.ini')
        AssetLookup()
        return config


async def main(args):
    '''setup and start the bot.'''
    config=setup(args)
    if config==None: 
        return
    async with bot:

        intent=discord.Intents.default();
        intent.presences=True
        intent.message_content=True
        intent.guilds=True
        intent.members=True
        bot.database_on()
        outcome=bot.set_error_channel(config.get("optional", 'error_channel_id'))
        if not outcome:
            bot.error_channel=-726
        await bot.add_cog(Main())
        bot.set_ext_directory('./cogs')
        bot.update_ext_list()
        await bot.reload_all()
        if (config!=None):
            await bot.start(config.get("vital", 'cipher'))
             


