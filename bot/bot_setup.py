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
from utility import serverOwner, serverAdmin,MessageTemplates

from discord.ext import commands, tasks

from discord import Webhook
from subprocess import Popen


from collections import defaultdict


from .TauCetiBot import TCBot
"""
Initalizes TCBot, and defines some checks

"""





bot = TCBot()


taskflags=defaultdict(bool)

async def opening():
    print("OK.")


@bot.check
async def is_cog_enabled(ctx):
    return True

@bot.check
async def guildcheck(ctx):
    if ctx.command.extras:
        if 'guildtask' in ctx.command.extras and ctx.guild!=None:
            if taskflags[str(ctx.guild.id)]: 
                return False
    return True

@bot.on_error
async def on_error(event_method: str, /, *args: Any, **kwargs: Any):
    log=logging.getLogger('discord')
    log.exception('Ignoring exception AS in %s', event_method)
    try:
        just_the_string=''.join(traceback.format_exc())
        er=MessageTemplates.get_error_embed(title=f"Error with {event_method}",description=f"{just_the_string}")
        await bot.send_error_embed(er)
    except:
        print("Minor issue.")



@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError):
    logger=logging.getLogger('discord')
    logger.error('Ignoring exception in app command %s', interaction.command.name, exc_info=error)
    ctx=await bot.get_context(interaction)
    await bot.send_error(error,f"App Command {interaction.command.name}")
    await ctx.send(f"This app command failed due to {str(error)}")
    print("ERROR")

@bot.before_invoke
async def add_log(ctx):
    await ctx.channel.send(f"{ctx.invoked_with},{str(ctx.invoked_parents)}")
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
async def on_ready():
    zehttp=logging.getLogger('discord.http')
    zehttp.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        filename='./logs/discord_http.log',
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[LINE] [{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    zehttp.addHandler(handler)

    handler2 = logging.handlers.RotatingFileHandler(
        filename='./logs/discord.log',
        encoding='utf-8',
        maxBytes=7 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter2 = logging.Formatter('[LINE] [{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler2.setFormatter(formatter2)
    discord.utils.setup_logging(level=logging.INFO,handler=handler2,root=True)
    print("Activating Bot.")
    await opening()
    print("BOT ACTIVE")
    for x in bot.tree.walk_commands():
        print(x.name)

    print("BOT SYNCED!")
    bot.delete_queue_message.start()
    bot.post_queue_message.start()


    print("Setup done.")



class Main(commands.Cog):
    """ debug class
    """

    
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

        await ctx.channel.send("Shutting Down")
        
        autocog=bot.get_cog("AutoCog")
        if autocog!=None:
            await autocog.stop_tasks()

        await ctx.bot.close()
        



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
        if arglength >1:
            print("No config.ini file detected.")

            config["vital"] = {'cipher': args[1]}

            config.write(open('config.ini', 'w'))
            try:
                print("making savedata")
                Path("/saveData").mkdir(parents=True, exist_ok=True) #saveData
            except FileExistsError:
                print("saveData exists already.")

            print("you can restart the bot now.")
        else:
            print("Please restart while passing the bot token into the command line.")
        return None

    else:
        # Read File
        config.read('config.ini')
        return config


async def main(args):
    '''Entry command.'''
    async with bot:

        intent=discord.Intents.default();
        intent.presences=True
        intent.message_content=True
        intent.guilds=True
        intent.members=True
        config=setup(args)

        await bot.add_cog(Main())
        bot.set_ext_directory('./cogs')
        bot.update_ext_list()
        await bot.reload_all()
        if (config!=None):
            await bot.start(config.get("vital", 'cipher'))
             


